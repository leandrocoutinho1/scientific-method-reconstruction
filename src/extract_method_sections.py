import json
import re
from pathlib import Path

INPUT_DIR = Path("data/grobid_output")
OUTPUT_DIR = Path("data/methods_extracted")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

METHOD_SECTION_PATTERNS = [
    r"\\bmethods?\\b",
    r"\\bmethodology\\b",
    r"\\bmaterials and methods\\b",
    r"\\bexperimental setup\\b",
    r"\\bexperiments?\\b",
    r"\\bproposed method\\b",
    r"\\bapproach\\b",
]


def is_method_section(section_name: str) -> bool:
    if not section_name:
        return False

    section_name = section_name.lower().strip()

    return any(
        re.search(pattern, section_name)
        for pattern in METHOD_SECTION_PATTERNS
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
