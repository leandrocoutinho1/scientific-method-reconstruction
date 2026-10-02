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

from llm_response_schema import validate_evaluation_response

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

GAPS_DIR = Path("data/gaps")
GEMINI_RECONSTRUCTIONS_DIR = Path("results/reconstructions")
OPENROUTER_RECONSTRUCTIONS_DIR = Path("results/openrouter_tests")
OUTPUT_DIR = Path("results/evaluations")

DEFAULT_GEMINI_MODEL = "gemini-flash-latest"
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_API_RETRIES = 2

SYSTEM_PROMPT = """
You are an evaluator of scientific methodology reconstruction quality.
Compare a reconstructed missing excerpt against the original removed excerpt and the surrounding methodology context.

Judge whether the reconstruction is faithful, methodologically plausible, coherent with the context, and free from unsupported details.

Scoring rules:
- Use integer scores from 1 to 5.
- semantic_accuracy: similarity to the original removed excerpt in meaning.
- methodological_fit: whether the reconstruction fits the methodology section and preserves scientific procedure.
- context_coherence: whether it fits the text before and after the gap.
- hallucination_risk: 1 means high risk of unsupported invention; 5 means low risk.
- overall_score: final assertiveness/quality score, considering all criteria.
- verdict: one short sentence in English explaining the score.

Respond exclusively with a valid JSON object in this format:
{
  "semantic_accuracy": 1,
  "methodological_fit": 1,
  "context_coherence": 1,
  "hallucination_risk": 1,
  "overall_score": 1,
  "verdict": "short verdict"
}
""".strip()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(data, output_file, ensure_ascii=False, indent=2)


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

    return {}, False


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "__", value)


def load_gap_index(gaps_dir: Path) -> dict[str, dict]:
    gap_index = {}
    for gap_file in sorted(gaps_dir.glob("*.json")):
        if gap_file.name == "manifest.json":
            continue

        gap_data = load_json(gap_file)
        gap_id = gap_data.get("gap_id") or gap_file.stem
        gap_index[gap_id] = gap_data

    return gap_index


def load_reconstruction_files(
    gemini_dir: Path,
    openrouter_dir: Path,
    limit: Optional[int],
) -> list[Path]:
    reconstruction_files = sorted(gemini_dir.glob("*_reconstruction.json"))
    reconstruction_files.extend(sorted(openrouter_dir.glob("*/*_reconstruction.json")))

    if limit is not None:
        return reconstruction_files[:limit]

    return reconstruction_files


def build_user_prompt(gap_data: dict, reconstruction_data: dict) -> str:
    return f"""
Evaluate the reconstructed missing excerpt below.

Article title:
{gap_data.get("title", reconstruction_data.get("title", ""))}

Section associated with the removed excerpt:
{gap_data.get("removed_section", "")}

Methodology with gap:
{gap_data.get("masked_text", "")}

Original removed excerpt:
{gap_data.get("removed_excerpt", reconstruction_data.get("removed_excerpt", ""))}

Reconstructed excerpt:
{reconstruction_data.get("reconstructed_excerpt", "")}

Reconstruction model:
{reconstruction_data.get("model", "")}

Return only the JSON evaluation.
""".strip()


def extract_text_from_gemini_response(response_data: dict) -> str:
    candidates = response_data.get("candidates", [])
    if not candidates:
        return ""

    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


def post_gemini(api_key: str, model: str, prompt: str) -> str:
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
            "temperature": 0.0,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "semantic_accuracy": {"type": "INTEGER"},
                    "methodological_fit": {"type": "INTEGER"},
                    "context_coherence": {"type": "INTEGER"},
                    "hallucination_risk": {"type": "INTEGER"},
                    "overall_score": {"type": "INTEGER"},
                    "verdict": {"type": "STRING"},
                },
                "required": [
                    "semantic_accuracy",
                    "methodological_fit",
                    "context_coherence",
                    "hallucination_risk",
                    "overall_score",
                    "verdict",
                ],
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
            return extract_text_from_gemini_response(response_data)
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"Gemini API request failed with status {exc.code}: {error_body}") from exc
        except URLError as exc:
            if attempt < MAX_API_RETRIES:
                time.sleep(attempt * 5)
                continue
            raise RuntimeError(f"Gemini API request failed: {exc}") from exc

    raise RuntimeError("Gemini API request failed after retries.")


def post_openrouter(api_key: str, model: str, messages: list[dict]) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 1024,
        "response_format": {
            "type": "json_object",
        },
    }
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
            with urlopen(request, timeout=90) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            choices = response_data.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content") or ""
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


def validate_raw_evaluation(raw_response: str) -> dict:
    parsed_response, valid_json = parse_json_response(raw_response)
    if not valid_json:
        raise RuntimeError(f"Evaluator response was not valid JSON: {raw_response[:500]}")

    try:
        validated_response = validate_evaluation_response(parsed_response)
    except ValidationError as exc:
        raise RuntimeError(f"Evaluator response failed schema validation: {exc}") from exc

    return validated_response.model_dump()


def evaluate_with_gemini(api_key: str, model: str, prompt: str) -> dict:
    raw_response = post_gemini(api_key, model, f"{SYSTEM_PROMPT}\n\n{prompt}")
    return validate_raw_evaluation(raw_response)


def evaluate_with_openrouter(api_key: str, model: str, prompt: str) -> dict:
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    raw_response = post_openrouter(api_key, model, messages)
    return validate_raw_evaluation(raw_response)


def build_evaluation_result(
    evaluator_provider: str,
    evaluator_model: str,
    reconstruction_file: Path,
    reconstruction_data: dict,
    evaluation: dict,
) -> dict:
    return {
        "gap_id": reconstruction_data.get("gap_id"),
        "title": reconstruction_data.get("title"),
        "reconstruction_provider": reconstruction_data.get("provider", "gemini"),
        "reconstruction_model": reconstruction_data.get("model"),
        "evaluator_provider": evaluator_provider,
        "evaluator_model": evaluator_model,
        "reconstruction_file": str(reconstruction_file),
        "removed_excerpt": reconstruction_data.get("removed_excerpt"),
        "reconstructed_excerpt": reconstruction_data.get("reconstructed_excerpt"),
        "evaluation": evaluation,
    }


def save_evaluation(
    output_dir: Path,
    evaluator_provider: str,
    evaluator_model: str,
    reconstruction_file: Path,
    result: dict,
) -> Path:
    evaluator_dir = output_dir / safe_name(evaluator_provider) / safe_name(evaluator_model)
    output_path = evaluator_dir / f"{reconstruction_file.stem}_evaluation.json"
    save_json(output_path, result)
    return output_path


def save_error(
    output_dir: Path,
    evaluator_provider: str,
    evaluator_model: str,
    reconstruction_file: Path,
    error: Exception,
) -> Path:
    evaluator_dir = output_dir / safe_name(evaluator_provider) / safe_name(evaluator_model)
    output_path = evaluator_dir / f"{reconstruction_file.stem}_evaluation_error.json"
    save_json(
        output_path,
        {
            "evaluator_provider": evaluator_provider,
            "evaluator_model": evaluator_model,
            "reconstruction_file": str(reconstruction_file),
            "error": str(error),
        },
    )
    return output_path


def parse_args():
    parser = ArgumentParser(
        description="Evaluate reconstruction assertiveness with Gemini and OpenRouter."
    )
    parser.add_argument(
        "--gaps-dir",
        type=Path,
        default=GAPS_DIR,
        help=f"Directory containing gap JSON files. Default: {GAPS_DIR}.",
    )
    parser.add_argument(
        "--gemini-reconstructions-dir",
        type=Path,
        default=GEMINI_RECONSTRUCTIONS_DIR,
        help=f"Directory containing Gemini reconstructions. Default: {GEMINI_RECONSTRUCTIONS_DIR}.",
    )
    parser.add_argument(
        "--openrouter-reconstructions-dir",
        type=Path,
        default=OPENROUTER_RECONSTRUCTIONS_DIR,
        help=f"Directory containing OpenRouter reconstructions. Default: {OPENROUTER_RECONSTRUCTIONS_DIR}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory where evaluations will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--gemini-model",
        default=None,
        help=f"Gemini evaluator model. Default: env gemini-evaluator-model/GEMINI_EVALUATOR_MODEL or {DEFAULT_GEMINI_MODEL}.",
    )
    parser.add_argument(
        "--openrouter-model",
        default=None,
        help=(
            "OpenRouter evaluator model. Default: env OPENROUTER_EVALUATOR_MODEL "
            f"or {DEFAULT_OPENROUTER_MODEL}."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["both", "gemini", "openrouter"],
        default="both",
        help="Evaluator provider to call. Default: both.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Maximum number of reconstruction files to evaluate. Default: 1.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    gap_index = load_gap_index(args.gaps_dir)
    reconstruction_files = load_reconstruction_files(
        args.gemini_reconstructions_dir,
        args.openrouter_reconstructions_dir,
        args.limit,
    )

    if not reconstruction_files:
        print("No reconstruction files found.")
        return

    gemini_model = (
        args.gemini_model
        or os.getenv("gemini-evaluator-model")
        or os.getenv("GEMINI_EVALUATOR_MODEL")
        or os.getenv("gemini-model")
        or os.getenv("GEMINI_MODEL")
        or DEFAULT_GEMINI_MODEL
    )
    openrouter_model = (
        args.openrouter_model
        or os.getenv("OPENROUTER_EVALUATOR_MODEL")
        or DEFAULT_OPENROUTER_MODEL
    )

    gemini_api_key = os.getenv("gemini-api-key") or os.getenv("GEMINI_API_KEY")
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

    if args.provider in {"both", "gemini"} and not gemini_api_key:
        raise ValueError("gemini-api-key not found. Add it to your .env file.")

    if args.provider in {"both", "openrouter"} and not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not found. Add it to your .env file.")

    for reconstruction_file in reconstruction_files:
        reconstruction_data = load_json(reconstruction_file)
        gap_id = reconstruction_data.get("gap_id")
        gap_data = gap_index.get(gap_id)

        if gap_data is None:
            print(f"{reconstruction_file}: skipped, gap_id not found in {args.gaps_dir}.")
            continue

        prompt = build_user_prompt(gap_data, reconstruction_data)

        if args.provider in {"both", "gemini"}:
            try:
                evaluation = evaluate_with_gemini(gemini_api_key, gemini_model, prompt)
                result = build_evaluation_result(
                    "gemini",
                    gemini_model,
                    reconstruction_file,
                    reconstruction_data,
                    evaluation,
                )
                output_path = save_evaluation(
                    args.output_dir,
                    "gemini",
                    gemini_model,
                    reconstruction_file,
                    result,
                )
                print(f"gemini: {reconstruction_file.name}: saved to {output_path}")
            except Exception as exc:
                output_path = save_error(
                    args.output_dir,
                    "gemini",
                    gemini_model,
                    reconstruction_file,
                    exc,
                )
                print(f"gemini: {reconstruction_file.name}: error saved to {output_path}")

        if args.provider in {"both", "openrouter"}:
            try:
                evaluation = evaluate_with_openrouter(openrouter_api_key, openrouter_model, prompt)
                result = build_evaluation_result(
                    "openrouter",
                    openrouter_model,
                    reconstruction_file,
                    reconstruction_data,
                    evaluation,
                )
                output_path = save_evaluation(
                    args.output_dir,
                    "openrouter",
                    openrouter_model,
                    reconstruction_file,
                    result,
                )
                print(f"openrouter: {reconstruction_file.name}: saved to {output_path}")
            except Exception as exc:
                output_path = save_error(
                    args.output_dir,
                    "openrouter",
                    openrouter_model,
                    reconstruction_file,
                    exc,
                )
                print(f"openrouter: {reconstruction_file.name}: error saved to {output_path}")


if __name__ == "__main__":
    main()
