import json
import re
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from text_cleaning import (
    clean_extracted_text,
    is_probably_table_or_figure,
    normalize_for_matching,
)

INPUT_DIR = Path("data/grobid_output")
OUTPUT_DIR = Path("data/methods_extracted")
CONFIG_PATH = Path("config/section_patterns.json")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        return json.load(config_file)


def normalize_patterns(patterns: list[str]) -> list[str]:
    return [
        normalize_for_matching(pattern)
        for pattern in patterns
        if pattern.strip()
    ]


CONFIG = load_config()
METHOD_SECTION_PATTERNS = normalize_patterns(CONFIG.get("method_sections", []))
STOP_SECTION_PATTERNS = normalize_patterns(CONFIG.get("stop_sections", []))


def compact_for_matching(text: str) -> str:
    normalized = normalize_for_matching(text)
    return re.sub(r"[^a-z0-9]+", "", normalized)


def pattern_matches(section_name: str, patterns: list[str], compact_contains_min: int = 8) -> bool:
    normalized_section = normalize_for_matching(section_name)
    compact_section = compact_for_matching(section_name)

    for pattern in patterns:
        compact_pattern = compact_for_matching(pattern)

        if normalized_section == pattern:
            return True

        if compact_section == compact_pattern:
            return True

        if re.search(rf"(?<![a-z0-9]){re.escape(pattern)}(?![a-z0-9])", normalized_section):
            return True

        if len(compact_pattern) >= compact_contains_min and compact_pattern in compact_section:
            return True

    return False


def is_noise_section(section_name: str) -> bool:
    cleaned = clean_extracted_text(section_name)
    normalized = normalize_for_matching(section_name)

    if not normalized:
        return True

    if cleaned and cleaned[0].islower():
        return True

    if len(normalized) <= 2:
        return True

    letters = re.findall(r"[a-z]", normalized)
    digits = re.findall(r"\d", normalized)

    if not letters:
        return True

    if digits and len(digits) > len(letters):
        return True

    if len(normalized.split()) > 14:
        return True

    if normalized.startswith(("table ", "figure ", "fig ", "algorithm ")):
        return True

    if " table " in f" {normalized} ":
        return True

    return False


def is_method_section(section_name: str) -> bool:
    if is_noise_section(section_name):
        return False

    if pattern_matches(section_name, STOP_SECTION_PATTERNS, compact_contains_min=5):
        return False

    return pattern_matches(section_name, METHOD_SECTION_PATTERNS)


def extract_method_text(json_path: Path) -> dict:
    with json_path.open("r", encoding="utf-8") as file:
        paper = json.load(file)

    title_raw = paper.get("biblio", {}).get("title", "")
    title_clean = clean_extracted_text(title_raw)
    body_text = paper.get("body_text", [])

    method_paragraphs_raw = []
    method_paragraphs_clean = []
    selected_block_indexes = []

    for index, paragraph in enumerate(body_text):
        section = paragraph.get("head_section", "")
        text_raw = paragraph.get("text", "")

        if not text_raw:
            continue

        if not is_method_section(section):
            continue

        if is_probably_table_or_figure(text_raw):
            continue

        text_clean = clean_extracted_text(text_raw)
        selected_block_indexes.append(index)

        method_paragraphs_raw.append({
            "section": section,
            "text": text_raw,
        })

        method_paragraphs_clean.append({
            "section": clean_extracted_text(section),
            "text": text_clean,
        })

    return {
        "source_file": json_path.name,
        "title_raw": title_raw,
        "title_clean": title_clean,
        "extraction_strategy": "section_pattern_matching",
        "selected_block_indexes": selected_block_indexes,
        "num_paragraphs": len(method_paragraphs_clean),
        "method_text_raw": "\n\n".join(
            paragraph["text"] for paragraph in method_paragraphs_raw
        ),
        "method_text_clean": "\n\n".join(
            paragraph["text"] for paragraph in method_paragraphs_clean
        ),
        "paragraphs_raw": method_paragraphs_raw,
        "paragraphs_clean": method_paragraphs_clean,
    }


def parse_args():
    parser = ArgumentParser(
        description="Extract methodology sections using configurable section title patterns."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=INPUT_DIR,
        help=f"Directory containing GROBID JSON files. Default: {INPUT_DIR}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory where extracted methodologies will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of GROBID JSON files to process.",
    )
    return parser.parse_args()


def load_input_files(input_dir: Path, limit: Optional[int]) -> list[Path]:
    files = sorted(input_dir.glob("*.json"))

    if limit is not None:
        return files[:limit]

    return files


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for old_output in args.output_dir.glob("*.json"):
        old_output.unlink()

    files_processed = 0

    for json_path in load_input_files(args.input_dir, args.limit):
        extracted = extract_method_text(json_path)
        output_path = args.output_dir / f"{json_path.stem}_methods.json"

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(extracted, file, ensure_ascii=False, indent=2)

        files_processed += 1

        print(
            f"{json_path.name}: "
            f"{extracted['num_paragraphs']} methodology blocks extracted"
        )

    print(f"Finished processing {files_processed} files.")


if __name__ == "__main__":
    main()
