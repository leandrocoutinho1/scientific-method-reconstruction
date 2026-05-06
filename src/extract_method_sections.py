import json
import unicodedata
from pathlib import Path

INPUT_DIR = Path("data/grobid_output")
OUTPUT_DIR = Path("data/methods_extracted")
CONFIG_PATH = Path("config/section_patterns.json")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
    CONFIG = json.load(config_file)

METHOD_SECTION_PATTERNS = CONFIG.get("method_sections", [])


def normalize_text(text: str) -> str:
    text = text.lower().strip()

    return "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


NORMALIZED_PATTERNS = [
    normalize_text(pattern)
    for pattern in METHOD_SECTION_PATTERNS
]


def is_method_section(section_name: str) -> bool:
    if not section_name:
        return False

    normalized_section = normalize_text(section_name)

    return any(
        pattern in normalized_section
        for pattern in NORMALIZED_PATTERNS
    )


def extract_method_text(json_path: Path) -> dict:
    with json_path.open("r", encoding="utf-8") as file:
        paper = json.load(file)

    title = paper.get("biblio", {}).get("title", "")
    body_text = paper.get("body_text", [])

    method_paragraphs = []

    for paragraph in body_text:
        section = paragraph.get("head_section", "")
        text = paragraph.get("text", "")

        if is_method_section(section) and text:
            method_paragraphs.append({
                "section": section,
                "text": text
            })

    return {
        "source_file": json_path.name,
        "title": title,
        "num_paragraphs": len(method_paragraphs),
        "method_text": "\n\n".join(p["text"] for p in method_paragraphs),
        "paragraphs": method_paragraphs
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
