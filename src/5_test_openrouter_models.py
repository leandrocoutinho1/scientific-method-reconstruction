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

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

INPUT_DIR = Path("data/gaps")
OUTPUT_DIR = Path("results/openrouter_tests")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_API_RETRIES = 1
MISSING_TOKEN = "[MISSING_TEXT]"

DEFAULT_MODEL = "openrouter/free"

FREE_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/llama-nemotron-rerank-vl-1b-v2:free",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",
    "poolside/laguna-m.1:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
    "cohere/north-mini-code:free",
    "google/gemma-4-26b-a4b-it:free",
    "liquid/lfm-2.5-1.2b-thinking:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]


SYSTEM_PROMPT = """
You are an assistant specialized in reconstructing missing excerpts from scientific methodology sections.
Your task is to fill only the excerpt marked as [MISSING_TEXT], preserving the language,
academic style, coherence with the surrounding context, and the typical structure of a methodology section.

Mandatory rules:
- Do not reveal your reasoning or analysis.
- Do not write phrases such as "we need to", "likely", "probably", or "the missing text should".
- Generate only the missing excerpt; do not rewrite the entire methodology.
- Do not add results, conclusions, discussion, or information unsupported by the context.
- Do not cite new sources.
- Do not invent preprocessing steps, statistical tests, variables, thresholds, datasets, parameters, equations, or tools unless they are clearly supported by the surrounding text.
- Prefer a conservative reconstruction over a more detailed but speculative one.
- If the surrounding context only supports a general statement, write a general statement.
- Preserve exactly the predominant language of the methodology with the gap; for the current corpus, this is expected to be English.
- Avoid vague sentences when the context requires specific procedures, parameters, hypotheses, or metrics.
- If the context does not allow a confident reconstruction, generate a conservative reconstruction.
- Keep the technical detail level compatible with the surrounding context.
- Avoid excessive summarization when the context indicates procedures, hypotheses, parameters, or metrics.
- Try to produce an excerpt with approximately the expected length.
- Match the function of the missing excerpt in the paragraph: if it introduces a method, introduce it; if it defines hypotheses, define hypotheses; if it describes data collection, describe data collection.
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


def load_selected_gap_files(input_dir: Path, gap_file: Optional[Path], limit: Optional[int]) -> list[Path]:
    if gap_file is None:
        return load_gap_files(input_dir, limit)

    selected_gap = gap_file
    if not selected_gap.is_absolute():
        selected_gap = input_dir / selected_gap

    return [selected_gap]


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
Be conservative: use only information supported by the text before and after the marker.
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


def safe_model_name(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "__", model)


def resolve_models(model_arg: str) -> list[str]:
    if model_arg == "free-list":
        return FREE_MODELS

    if model_arg == "openrouter-free":
        return [DEFAULT_MODEL]

    return [
        model.strip()
        for model in model_arg.split(",")
        if model.strip()
    ]


def build_payload(model: str, messages: list[dict], reasoning: bool) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1200,
        "response_format": {
            "type": "json_object",
        },
    }

    payload["reasoning"] = {"enabled": reasoning}

    return payload


def post_openrouter(api_key: str, payload: dict) -> dict:
    request = Request(
        OPENROUTER_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"OpenRouter API request failed with status {exc.code}: {error_body}") from exc
        except URLError as exc:
            if attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"OpenRouter API request failed: {exc}") from exc

    raise RuntimeError("OpenRouter API request failed after retries.")


def extract_message(response_data: dict) -> dict:
    choices = response_data.get("choices", [])
    if not choices:
        return {}

    return choices[0].get("message", {})


def reconstruct_gap(api_key: str, model: str, gap_data: dict, reasoning: bool) -> dict:
    user_prompt = build_user_prompt(gap_data)
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]
    response_data = post_openrouter(api_key, build_payload(model, messages, reasoning))
    message = extract_message(response_data)
    raw_response = message.get("content") or ""
    parsed_response, valid_json = parse_json_response(raw_response)
    last_invalid_response = raw_response
    first_error = "response was not valid JSON"

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
                "provider": "openrouter",
                "model": model,
                "reconstructed_excerpt": validated_response.reconstructed_excerpt,
            }

    else:
        first_error = "response was not valid JSON"

    retry_messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": build_retry_prompt(user_prompt, raw_response),
        },
    ]
    retry_response_data = post_openrouter(
        api_key,
        build_payload(model, retry_messages, reasoning),
    )
    retry_message = extract_message(retry_response_data)
    last_invalid_response = retry_message.get("content") or ""
    parsed_response, valid_json = parse_json_response(last_invalid_response)

    if not valid_json:
        raise RuntimeError(
            "OpenRouter response was not valid JSON after retry. "
            f"Last response preview: {last_invalid_response[:500]}"
        )

    try:
        validated_response = validate_reconstruction_response(parsed_response)
    except ValidationError as exc:
        raise RuntimeError(
            "OpenRouter response failed schema validation after retry. "
            f"First error: {first_error}. Retry error: {exc}. "
            f"Last response preview: {last_invalid_response[:500]}"
        ) from exc

    return {
        "gap_id": gap_data.get("gap_id"),
        "title": gap_data.get("title"),
        "removed_excerpt": gap_data.get("removed_excerpt"),
        "provider": "openrouter",
        "model": model,
        "reconstructed_excerpt": validated_response.reconstructed_excerpt,
    }


def save_result(output_dir: Path, model: str, gap_file: Path, result: dict) -> Path:
    model_dir = output_dir / safe_model_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{gap_file.stem}_openrouter_reconstruction.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)

    return output_path


def save_error(output_dir: Path, model: str, gap_file: Path, error: Exception) -> Path:
    model_dir = output_dir / safe_model_name(model)
    model_dir.mkdir(parents=True, exist_ok=True)
    output_path = model_dir / f"{gap_file.stem}_openrouter_error.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(
            {
                "gap_id": gap_file.stem,
                "provider": "openrouter",
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
        description="Test OpenRouter models on artificial methodology gaps."
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
        help=f"Directory where OpenRouter test outputs will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "Model to test, comma-separated models, 'openrouter-free', or 'free-list'. "
            f"Default: {DEFAULT_MODEL}."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Optional maximum number of gap files to process. Default: 1.",
    )
    parser.add_argument(
        "--gap-file",
        type=Path,
        default=None,
        help="Specific gap JSON file to process. Relative paths are resolved from --input-dir.",
    )
    parser.add_argument(
        "--reasoning",
        action="store_true",
        help="Enable OpenRouter reasoning for models that support it.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY not found. Add it to your .env file."
        )

    gap_files = load_selected_gap_files(args.input_dir, args.gap_file, args.limit)
    if not gap_files:
        print(f"No gap files found in {args.input_dir}.")
        return

    models = resolve_models(args.model)

    for model in models:
        for gap_file in gap_files:
            with gap_file.open("r", encoding="utf-8") as input_file:
                gap_data = json.load(input_file)

            try:
                result = reconstruct_gap(api_key, model, gap_data, args.reasoning)
                output_path = save_result(args.output_dir, model, gap_file, result)
                print(f"{model}: {gap_file.name}: saved to {output_path}")
            except Exception as exc:
                output_path = save_error(args.output_dir, model, gap_file, exc)
                print(f"{model}: {gap_file.name}: error saved to {output_path}")


if __name__ == "__main__":
    main()
