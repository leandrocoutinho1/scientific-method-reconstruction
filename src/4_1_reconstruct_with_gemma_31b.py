import json
import os
import re
import time
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from llm_response_schema import validate_reconstruction_response
from runtime_summary import print_runtime_summary, start_timer

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

INPUT_DIR = Path("data/gaps")
OUTPUT_DIR = Path("results/reconstructions_gemma")
DEFAULT_MODEL = "gemma-4-31b-it"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_API_RETRIES = 2
MISSING_TOKEN = "[MISSING_TEXT]"

SYSTEM_PROMPT = """
You are an assistant specialized in reconstructing missing excerpts from scientific methodology sections.
Your task is to fill only the excerpt marked as [MISSING_TEXT], preserving the language,
academic style, coherence with the surrounding context, and the typical structure of a methodology section.

Mandatory rules:
- Generate only the missing excerpt; do not rewrite the entire methodology.
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


def build_user_prompt(gap_data: dict) -> str:
    title = gap_data.get("title", "")
    removed_section = gap_data.get("removed_section", "")
    masked_text = gap_data.get("masked_text", "")
    removed_excerpt = gap_data.get("removed_excerpt", "")
    expected_word_count = len(removed_excerpt.split())
    target_word_count = min(max(expected_word_count, 20), 60)

    return f"""
Reconstruct the missing excerpt from a scientific methodology section.

Article title:
{title}

Section associated with the removed excerpt:
{removed_section}

Approximate target length:
{target_word_count} words

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


def extract_text_from_response(response_data: dict) -> str:
    candidates = response_data.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


def generate_with_gemma(api_key: str, model: str, prompt: str) -> str:
    url = f"{GEMINI_API_BASE_URL}/{model}:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": f"{SYSTEM_PROMPT}\n\n{prompt}",
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": api_key,
        },
        method="POST",
    )

    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            with urlopen(request, timeout=90) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            return extract_text_from_response(response_data)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"Gemma API request failed with status {exc.code}: {error_body}") from exc
        except URLError as exc:
            if attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"Gemma API request failed: {exc}") from exc

    raise RuntimeError("Gemma API request failed after retries.")


def reconstruct_gap(api_key: str, model: str, gap_data: dict) -> dict:
    prompt = build_user_prompt(gap_data)
    raw_response = generate_with_gemma(api_key, model, prompt)
    parsed_response, valid_json = parse_json_response(raw_response)

    if valid_json:
        try:
            validated_response = validate_reconstruction_response(parsed_response)
        except ValidationError as exc:
            first_error = str(exc)
        else:
            return {
                "gap_id": gap_data.get("gap_id"),
                "title": gap_data.get("title"),
                "removed_excerpt": gap_data.get("removed_excerpt"),
                "provider": "gemma",
                "model": model,
                "reconstructed_excerpt": validated_response.reconstructed_excerpt,
            }
    else:
        first_error = "response was not valid JSON"

    repaired_response = generate_with_gemma(
        api_key,
        model,
        build_retry_prompt(prompt, raw_response),
    )
    parsed_response, valid_json = parse_json_response(repaired_response)

    if not valid_json:
        raise RuntimeError(
            "Gemma response was not valid JSON after retry. "
            f"First error: {first_error}. Last response preview: {repaired_response[:500]}"
        )

    try:
        validated_response = validate_reconstruction_response(parsed_response)
    except ValidationError as retry_exc:
        raise RuntimeError(
            "Gemma response failed schema validation after retry. "
            f"First error: {first_error}. Retry error: {retry_exc}"
        ) from retry_exc

    return {
        "gap_id": gap_data.get("gap_id"),
        "title": gap_data.get("title"),
        "removed_excerpt": gap_data.get("removed_excerpt"),
        "provider": "gemma",
        "model": model,
        "reconstructed_excerpt": validated_response.reconstructed_excerpt,
    }


def safe_model_name(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "__", model)


def save_reconstruction(output_dir: Path, gap_file: Path, model: str, result: dict) -> Path:
    model_dir = output_dir / safe_model_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{gap_file.stem}_gemma_reconstruction.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)

    return output_path


def save_error(output_dir: Path, gap_file: Path, model: str, error: Exception) -> Path:
    model_dir = output_dir / safe_model_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{gap_file.stem}_gemma_error.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "gap_id": gap_file.stem,
                "provider": "gemma",
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
        description="Experimentally reconstruct methodology gaps using Gemma 4 31B through the Gemini API."
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
        help=f"Directory where Gemma reconstructions will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Gemma model name. Default: env gemma-31b-model/GEMMA_31B_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Optional maximum number of gap files to process. Default: 1.",
    )
    return parser.parse_args()


def main():
    start_time = start_timer()
    load_dotenv()
    args = parse_args()
    model = args.model or os.getenv("gemma-31b-model") or os.getenv("GEMMA_31B_MODEL") or DEFAULT_MODEL

    api_key = os.getenv("gemini-api-key") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "gemini-api-key not found. Create a .env file based on .env.example."
        )

    gap_files = load_gap_files(args.input_dir, args.limit)
    if not gap_files:
        print(f"No gap files found in {args.input_dir}.")
        return

    reconstructions_saved = 0
    errors = 0

    for gap_file in gap_files:
        with gap_file.open("r", encoding="utf-8") as input_file:
            gap_data = json.load(input_file)

        try:
            result = reconstruct_gap(api_key, model, gap_data)
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
