import json
import os
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from llm_response_schema import ReconstructionResponse, validate_reconstruction_response
from runtime_summary import print_runtime_summary, start_timer

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

INPUT_DIR = Path("data/gaps")
OUTPUT_DIR = Path("results/reconstructions_ollama")
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_BASE_URL = "http://localhost:11434"
MISSING_TOKEN = "[MISSING_TEXT]"

SYSTEM_PROMPT = """
You are an assistant specialized in reconstructing missing excerpts from scientific methodology sections.
Your task is to fill only the excerpt marked as [MISSING_TEXT], preserving the language,
academic style, coherence with the surrounding context, and the typical structure of a methodology section.

Mandatory rules:
- Generate only the missing excerpt; do not rewrite the entire methodology.
- Infer the role of the missing passage from its immediate neighbors: a transition, overview, or procedural detail. Do not replace it with a summary of the entire context.
- Do not invent stages, their number or order, equipment, calibration, measurements, or parameter values. Include technical claims only when supported by the visible context.
- Do not describe fuzzy clusters as mutually exclusive or imply hard assignment when the context describes fuzzy membership.
- Use only section numbers and headings explicitly visible in the context; do not invent cross-references.
- Do not add results, conclusions, discussion, or information unsupported by the context.
- Do not cite new sources.
- Preserve exactly the predominant language of the methodology with the gap; for the current corpus, this is expected to be English.
- If the context does not allow a confident reconstruction, generate a conservative reconstruction.
- Keep the technical detail level compatible with the surrounding context.
- Try to produce an excerpt with approximately the expected length.
- Do not include markdown.
- Do not include explanations outside the JSON.
- Write the reconstructed_excerpt value as plain text, without internal line breaks.

Respond exclusively with a valid JSON object in this format:
{
  "reconstructed_excerpt": "reconstructed excerpt"
}
""".strip()


def load_gap_files(input_dir: Path, limit: Optional[int] = None) -> list[Path]:
    gap_files = sorted(
        path
        for path in input_dir.glob("*.json")
        if path.name != "manifest.json"
    )

    if limit is not None:
        return gap_files[:limit]

    return gap_files


def word_limits(gap_data: dict) -> tuple[int, int, int]:
    target = min(max(len(gap_data.get("removed_excerpt", "").split()), 20), 60)
    return target, max(8, target * 3 // 4), (target * 5 + 3) // 4


def validate_local_response(data: dict, gap_data: dict):
    response = validate_reconstruction_response(data)
    _, minimum, maximum = word_limits(gap_data)
    count = len(response.reconstructed_excerpt.split())
    if not minimum <= count <= maximum:
        raise ValueError(f"Expected {minimum}-{maximum} words; received {count}.")
    return response


def build_user_prompt(gap_data: dict) -> str:
    title = gap_data.get("title", "")
    removed_section = gap_data.get("removed_section", "")
    masked_text = gap_data.get("masked_text", "")
    target_word_count, minimum, maximum = word_limits(gap_data)

    return f"""
Reconstruct the missing excerpt from a scientific methodology section.

Article title:
{title}

Section associated with the removed excerpt:
{removed_section}

Approximate target length:
{target_word_count} words
Required range: {minimum}-{maximum} words, counted by whitespace. This applies only to reconstructed_excerpt.

Methodology with gap:
{masked_text}

Remember: replace only the {MISSING_TOKEN} marker, without summarizing the entire section. Return only valid JSON.
""".strip()


def parse_json_response(response_text: str) -> tuple[dict, bool]:
    response_text = response_text.strip()

    if response_text.startswith("```json"):
        response_text = response_text.removeprefix("```json").removesuffix("```").strip()
    elif response_text.startswith("```"):
        response_text = response_text.removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(response_text), True
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0)), True
            except json.JSONDecodeError:
                pass

    return {
        "reconstructed_excerpt": response_text,
    }, False


def build_retry_prompt(original_prompt: str, response_text: str) -> str:
    return f"""
The previous response was invalid or incomplete:
{response_text}

Redo the reconstruction from the original request below.
Respond with exactly one valid JSON object in this format:
{{"reconstructed_excerpt": "reconstructed excerpt"}}

Do not add markdown, comments, or extra fields.

Original request:
{original_prompt}
""".strip()


def generate_with_ollama(base_url: str, model: str, prompt: str, timeout: float) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": ReconstructionResponse.model_json_schema(),
        "options": {"temperature": 0.2, "num_ctx": 8192, "num_predict": 2048},
    }
    request = Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama request failed with status {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {base_url}: {exc}. Open Ollama or run ollama serve."
        ) from exc
    if response_data.get("error"):
        raise RuntimeError(f"Ollama error: {response_data['error']}")
    if response_data.get("done_reason") == "length":
        raise RuntimeError("Ollama response reached the output token limit.")
    return response_data.get("message", {}).get("content", "").strip()


def reconstruct_gap(base_url: str, model: str, gap_data: dict, timeout: float = 300) -> dict:
    prompt = build_user_prompt(gap_data)
    raw_response = generate_with_ollama(base_url, model, prompt, timeout)
    parsed_response, valid_json = parse_json_response(raw_response)

    if valid_json:
        try:
            validated_response = validate_local_response(parsed_response, gap_data)
        except (ValidationError, ValueError) as exc:
            first_error = str(exc)
        else:
            return {
                "gap_id": gap_data.get("gap_id"),
                "title": gap_data.get("title"),
                "removed_excerpt": gap_data.get("removed_excerpt"),
                "provider": "ollama",
                "model": model,
                "reconstructed_excerpt": validated_response.reconstructed_excerpt,
            }
    else:
        first_error = "response was not valid JSON"

    repaired_response = generate_with_ollama(
        base_url,
        model,
        build_retry_prompt(f"{prompt}\nPrevious validation error: {first_error}", raw_response),
        timeout,
    )
    parsed_response, valid_json = parse_json_response(repaired_response)

    if not valid_json:
        raise RuntimeError(
            "Ollama response was not valid JSON after retry. "
            f"First error: {first_error}. Last response preview: {repaired_response[:500]}"
        )

    try:
        validated_response = validate_local_response(parsed_response, gap_data)
    except (ValidationError, ValueError) as retry_exc:
        raise RuntimeError(
            "Ollama response failed schema validation after retry. "
            f"First error: {first_error}. Retry error: {retry_exc}"
        ) from retry_exc

    return {
        "gap_id": gap_data.get("gap_id"),
        "title": gap_data.get("title"),
        "removed_excerpt": gap_data.get("removed_excerpt"),
        "provider": "ollama",
        "model": model,
        "reconstructed_excerpt": validated_response.reconstructed_excerpt,
    }


def safe_model_name(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "__", model)


def save_reconstruction(output_dir: Path, gap_file: Path, model: str, result: dict) -> Path:
    model_dir = output_dir / safe_model_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{gap_file.stem}_ollama_reconstruction.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)

    return output_path


def save_error(output_dir: Path, gap_file: Path, model: str, error: Exception) -> Path:
    model_dir = output_dir / safe_model_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{gap_file.stem}_ollama_error.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "gap_id": gap_file.stem,
                "provider": "ollama",
                "model": model,
                "error": str(error),
            },
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    return output_path


def parse_args():
    parser = ArgumentParser(
        description="Reconstruct methodology gaps locally using Ollama."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=INPUT_DIR,
        help=f"Directory containing gap JSON files. Default: {INPUT_DIR}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory where Ollama reconstructions will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Ollama model name. Default: env OLLAMA_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Optional maximum number of gap files to process. Default: 1.",
    )
    parser.add_argument("--base-url", default=None, help="Ollama server URL. Default: OLLAMA_BASE_URL or localhost:11434.")
    parser.add_argument("--timeout", type=float, default=300, help="Request timeout in seconds. Default: 300.")
    args = parser.parse_args()
    if args.limit < 1 or args.timeout <= 0:
        parser.error("--limit and --timeout must be positive")
    return args


def main():
    start_time = start_timer()
    load_dotenv()
    args = parse_args()
    model = args.model or os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL
    base_url = args.base_url or os.getenv("OLLAMA_BASE_URL") or DEFAULT_BASE_URL
    if model.endswith(":cloud"):
        raise ValueError("Use a downloaded local model, not a :cloud model.")

    gap_files = load_gap_files(args.input_dir, args.limit)
    if not gap_files:
        print(f"No gap files found in {args.input_dir}.")
        return

    reconstructions_saved = 0
    errors = 0

    for gap_file in gap_files:
        print(f"{model}: processing {gap_file.name}", flush=True)
        try:
            with gap_file.open("r", encoding="utf-8") as input_file:
                gap_data = json.load(input_file)
            result = reconstruct_gap(base_url, model, gap_data, args.timeout)
            output_path = save_reconstruction(args.output_dir, gap_file, model, result)
            reconstructions_saved += 1
            print(f"{model}: {gap_file.name}: reconstruction saved to {output_path}")
        except Exception as exc:
            errors += 1
            output_path = save_error(args.output_dir, gap_file, model, exc)
            print(f"{model}: {gap_file.name}: error saved to {output_path}")

    print_runtime_summary(
        start_time=start_time,
        total_items=len(gap_files),
        processed_items=reconstructions_saved,
        errors=errors,
        item_label="gaps",
    )
    print(f"Finished reconstructing gaps with {model}.")


if __name__ == "__main__":
    main()
