import json
import random
from pathlib import Path

INPUT_DIR = Path("data/methods_extracted")
OUTPUT_DIR = Path("data/gaps")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REMOVAL_PERCENTAGE = 0.20


def create_gap(text: str):
    words = text.split()

    if len(words) < 30:
        return None

    gap_size = int(len(words) * REMOVAL_PERCENTAGE)

    if gap_size <= 0:
        return None

    start_index = random.randint(0, len(words) - gap_size)
    end_index = start_index + gap_size

    removed_excerpt = " ".join(words[start_index:end_index])

    masked_words = words[:start_index] + ["[MISSING_TEXT]"] + words[end_index:]

    masked_text = " ".join(masked_words)

    return {
        "masked_text": masked_text,
        "removed_excerpt": removed_excerpt,
        "start_index": start_index,
        "end_index": end_index,
    }


def main():
    for json_file in INPUT_DIR.glob("*.json"):
        with json_file.open("r", encoding="utf-8") as file:
            content = json.load(file)

        method_text = content.get("method_text", "")

        gap_data = create_gap(method_text)

        if gap_data is None:
            print(f"Skipping {json_file.name}: text too small.")
            continue

        output = {
            "title": content.get("title", ""),
            "source_file": content.get("source_file", ""),
            "original_text": method_text,
            "masked_text": gap_data["masked_text"],
            "removed_excerpt": gap_data["removed_excerpt"],
            "start_index": gap_data["start_index"],
            "end_index": gap_data["end_index"],
        }

        output_path = OUTPUT_DIR / f"{json_file.stem}_gap.json"

        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(output, output_file, ensure_ascii=False, indent=2)

        print(f"Gap created for {json_file.name}")


if __name__ == "__main__":
    main()
