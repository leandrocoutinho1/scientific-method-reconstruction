import json
from pathlib import Path

from text_cleaning import (
    clean_extracted_text,
    is_probably_table_or_figure,
    normalize_for_matching,
)

INPUT_DIR = Path("data/grobid_output")
OUTPUT_DIR = Path("data/methods_extracted")
CONFIG_PATH = Path("config/section_patterns.json")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
    CONFIG = json.load(config_file)

METHOD_SECTION_PATTERNS = CONFIG.get("method_sections", [])

STOP_SECTIONS = [
    "resultados",
    "results",
    "discussao",
    "discussao e resultados",
    "discussion",
    "conclusao",
    "conclusoes",
    "conclusion",
    "referencias",
    "references",
    "agradecimentos",
    "acknowledgments"
]

NORMALIZED_PATTERNS = [
    normalize_for_matching(pattern)
    for pattern in METHOD_SECTION_PATTERNS
]

NORMALIZED_STOP_SECTIONS = [
    normalize_for_matching(section)
    for section in STOP_SECTIONS
]


def is_method_section(section_name: str) -> bool:
    if not section_name:
        return False

    normalized_section = normalize_for_matching(section_name)

    return any(
        pattern in normalized_section
        for pattern in NORMALIZED_PATTERNS
    )



def is_stop_section(section_name: str) -> bool:
    if not section_name:
        return False

    normalized_section = normalize_for_matching(section_name)

    return any(
        stop_section in normalized_section
        for stop_section in NORMALIZED_STOP_SECTIONS
    )



def extract_method_text(json_path: Path) -> dict:
    with json_path.open("r", encoding="utf-8") as file:
        paper = json.load(file)

    title_raw = paper.get("biblio", {}).get("title", "")
    title_clean = clean_extracted_text(title_raw)

    body_text = paper.get("body_text", [])

    method_paragraphs_raw = []
    method_paragraphs_clean = []

    inside_methodology = False

    for paragraph in body_text:
        section = paragraph.get("head_section", "")
        text_raw = paragraph.get("text", "")

        if not text_raw:
            continue

        if is_method_section(section):
            inside_methodology = True

        elif inside_methodology and is_stop_section(section):
            break

        if not inside_methodology:
            continue

        if is_probably_table_or_figure(text_raw):
            continue

        text_clean = clean_extracted_text(text_raw)

        method_paragraphs_raw.append({
            "section": section,
            "text": text_raw
        })

        method_paragraphs_clean.append({
            "section": clean_extracted_text(section),
            "text": text_clean
        })

    return {
        "source_file": json_path.name,
        "title_raw": title_raw,
        "title_clean": title_clean,
        "num_paragraphs": len(method_paragraphs_clean),
        "method_text_raw": "\n\n".join(
            p["text"] for p in method_paragraphs_raw
        ),
        "method_text_clean": "\n\n".join(
            p["text"] for p in method_paragraphs_clean
        ),
        "paragraphs_raw": method_paragraphs_raw,
        "paragraphs_clean": method_paragraphs_clean
    }



def main():
    files_processed = 0

    for json_path in INPUT_DIR.glob("*.json"):
        extracted = extract_method_text(json_path)

        output_path = OUTPUT_DIR / f"{json_path.stem}_methods.json"

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(extracted, file, ensure_ascii=False, indent=2)

        files_processed += 1

        print(
            f"{json_path.name}: "
            f"{extracted['num_paragraphs']} methodology paragraphs extracted"
        )

    print(f"Finished processing {files_processed} files.")


if __name__ == "__main__":
    main()
