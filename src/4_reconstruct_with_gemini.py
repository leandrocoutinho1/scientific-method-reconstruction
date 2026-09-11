import json
import os
import time
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from llm_response_schema import validate_reconstruction_response

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

INPUT_DIR = Path("data/gaps")
OUTPUT_DIR = Path("results/reconstructions")
DEFAULT_MODEL = "gemini-flash-latest"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
MAX_API_RETRIES = 3
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
- Avoid vague sentences when the context requires specific procedures, parameters, hypotheses, or metrics.
- If the context does not allow a confident reconstruction, generate a conservative reconstruction.
- Keep the technical detail level compatible with the surrounding context.
- Avoid excessive summarization when the context indicates procedures, hypotheses, parameters, or metrics.
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


def extract_text_from_gemini_response(response_data: dict) -> str:
    candidates = response_data.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


def generate_with_gemini(api_key: str, model: str, prompt: str) -> str:
    url = f"{GEMINI_API_BASE_URL}/{model}:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "reconstructed_excerpt": {
                        "type": "STRING",
                    },
                },
                "required": ["reconstructed_excerpt"],
            },
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
            break
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 503} and attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"Gemini API request failed with status {exc.code}: {error_body}") from exc
        except URLError as exc:
            if attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"Gemini API request failed: {exc}") from exc

    return extract_text_from_gemini_response(response_data)


def reconstruct_gap(api_key: str, model: str, gap_data: dict) -> dict:
    prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(gap_data)}"
    raw_response = generate_with_gemini(api_key, model, prompt)
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
                "model": model,
                "reconstructed_excerpt": validated_response.reconstructed_excerpt,
            }
    else:
        first_error = "response was not valid JSON"

    repaired_response = generate_with_gemini(
        api_key,
        model,
        build_retry_prompt(prompt, raw_response),
    )
    parsed_response, valid_json = parse_json_response(repaired_response)

    if not valid_json:
        raise RuntimeError(
            "Gemini response was not valid JSON after retry. "
            f"First error: {first_error}."
        )

    try:
        validated_response = validate_reconstruction_response(parsed_response)
    except ValidationError as retry_exc:
        raise RuntimeError(
            "Gemini response failed schema validation after retry. "
            f"First error: {first_error}. Retry error: {retry_exc}"
        ) from retry_exc

    return {
        "gap_id": gap_data.get("gap_id"),
        "title": gap_data.get("title"),
        "removed_excerpt": gap_data.get("removed_excerpt"),
        "model": model,
        "reconstructed_excerpt": validated_response.reconstructed_excerpt,
    }


def save_reconstruction(output_dir: Path, gap_file: Path, result: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{gap_file.stem}_gemini_reconstruction.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)

    return output_path


def parse_args():
    parser = ArgumentParser(
        description="Reconstruct artificial methodology gaps using Gemini."
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
        help=f"Directory where reconstructions will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Gemini model name. Default: env gemini-model/GEMINI_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of gap files to process.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    model = args.model or os.getenv("gemini-model") or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    api_key = os.getenv("gemini-api-key") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "gemini-api-key not found. Create a .env file based on .env.example."
        )

    gap_files = load_gap_files(args.input_dir, args.limit)
    if not gap_files:
        print(f"No gap files found in {args.input_dir}.")
        return

    for gap_file in gap_files:
        with gap_file.open("r", encoding="utf-8") as input_file:
            gap_data = json.load(input_file)

        result = reconstruct_gap(api_key, model, gap_data)
        output_path = save_reconstruction(args.output_dir, gap_file, result)

        print(f"{gap_file.name}: reconstruction saved to {output_path}")


if __name__ == "__main__":
    main()
