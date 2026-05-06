import json
import random
from pathlib import Path

INPUT_DIR = Path("data/methods_extracted")
OUTPUT_DIR = Path("data/gaps")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MISSING_TOKEN = "[MISSING_TEXT]"
MIN_PARAGRAPH_WORDS = 8


def select_removable_paragraph(paragraphs: list):
    candidates = []

    for index, paragraph in enumerate(paragraphs):
        text = paragraph.get("text", "").strip()
        word_count = len(text.split())

        if word_count >= MIN_PARAGRAPH_WORDS:
            candidates.append((index, paragraph))

    if not candidates:
        return None

    return random.choice(candidates)


def create_paragraph_gap(paragraphs: list):
    selected = select_removable_paragraph(paragraphs)

    if selected is None:
        return None

    removed_index, removed_paragraph = selected

    masked_paragraphs = []

    for index, paragraph in enumerate(paragraphs):
        if index == removed_index:
            masked_paragraphs.append(MISSING_TOKEN)
        else:
            masked_paragraphs.append(paragraph.get("text", "").strip())

    context_before = "\n\n".join(
        paragraph.get("text", "").strip()
        for paragraph in paragraphs[:removed_index]
    )

    context_after = "\n\n".join(
        paragraph.get("text", "").strip()
        for paragraph in paragraphs[removed_index + 1:]
    )

    original_text = "\n\n".join(
        paragraph.get("text", "").strip()
        for paragraph in paragraphs
    )

    masked_text = "\n\n".join(masked_paragraphs)

    return {
        "mask_strategy": "paragraph",
        "missing_token": MISSING_TOKEN,
        "original_text": original_text,
        "masked_text": masked_text,
        "removed_excerpt": removed_paragraph.get("text", "").strip(),
        "removed_section": removed_paragraph.get("section", ""),
        "removed_paragraph_index": removed_index,
        "context_before": context_before,
        "context_after": context_after,
    }


def main():
    for json_file in INPUT_DIR.glob("*.json"):
        with json_file.open("r", encoding="utf-8") as file:
            content = json.load(file)

        paragraphs = content.get("paragraphs_clean", [])

        if not paragraphs:
            print(f"Skipping {json_file.name}: no clean methodology paragraphs found.")
            continue

        gap_data = create_paragraph_gap(paragraphs)

        if gap_data is None:
            print(f"Skipping {json_file.name}: no paragraph large enough to remove.")
            continue

        output = {
            "title": content.get("title_clean", ""),
            "source_file": content.get("source_file", ""),
            "method_source_file": json_file.name,
            "num_original_paragraphs": len(paragraphs),
            **gap_data,
        }

        output_path = OUTPUT_DIR / f"{json_file.stem}_gap.json"

        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(output, output_file, ensure_ascii=False, indent=2)

        print(
            f"Gap created for {json_file.name}: "
            f"removed paragraph {gap_data['removed_paragraph_index']} "
            f"from section '{gap_data['removed_section']}'"
        )


if __name__ == "__main__":
    main()
