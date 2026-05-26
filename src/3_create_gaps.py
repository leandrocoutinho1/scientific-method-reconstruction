import json
import random
import re
from argparse import ArgumentParser
from pathlib import Path

INPUT_DIR = Path("data/methods_extracted")
OUTPUT_DIR = Path("data/gaps")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MISSING_TOKEN = "[MISSING_TEXT]"
DEFAULT_RANDOM_SEED = 42
DEFAULT_GAPS_PER_DOCUMENT = 1
MIN_PARAGRAPH_WORDS = 12
MAX_REMOVED_TEXT_RATIO = 0.35


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text, flags=re.UNICODE))


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_good_gap_candidate(text: str, total_word_count: int) -> bool:
    normalized = normalize_space(text)
    word_count = count_words(normalized)

    if word_count < MIN_PARAGRAPH_WORDS:
        return False

    if total_word_count and word_count / total_word_count > MAX_REMOVED_TEXT_RATIO:
        return False

    bullet_count = normalized.count("•")
    if bullet_count >= 2:
        return False

    return True


def select_removable_paragraph(paragraphs: list, used_indexes: set, rng: random.Random):
    candidates = []
    total_word_count = sum(
        count_words(paragraph.get("text", ""))
        for paragraph in paragraphs
    )

    for index, paragraph in enumerate(paragraphs):
        if index in used_indexes:
            continue

        text = paragraph.get("text", "").strip()

        if is_good_gap_candidate(text, total_word_count):
            candidates.append((index, paragraph))

    if not candidates:
        return None

    return rng.choice(candidates)


def create_paragraph_gap(paragraphs: list, used_indexes: set, rng: random.Random):
    selected = select_removable_paragraph(paragraphs, used_indexes, rng)

    if selected is None:
        return None

    removed_index, removed_paragraph = selected
    used_indexes.add(removed_index)

    masked_paragraphs = []

    for index, paragraph in enumerate(paragraphs):
        if index == removed_index:
            masked_paragraphs.append(MISSING_TOKEN)
        else:
            masked_paragraphs.append(paragraph.get("text", "").strip())

    masked_text = "\n\n".join(masked_paragraphs)
    removed_excerpt = removed_paragraph.get("text", "").strip()

    return {
        "masked_text": masked_text,
        "removed_excerpt": removed_excerpt,
        "removed_section": removed_paragraph.get("section", ""),
    }


def build_output_filename(json_file: Path, gap_index: int, gaps_per_document: int) -> str:
    if gaps_per_document == 1:
        return f"{json_file.stem}_gap.json"

    return f"{json_file.stem}_gap_{gap_index + 1:03d}.json"


def parse_args():
    parser = ArgumentParser(
        description="Create reproducible artificial gaps in extracted method sections."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_RANDOM_SEED,
        help=f"Random seed used to select removable paragraphs. Default: {DEFAULT_RANDOM_SEED}.",
    )
    parser.add_argument(
        "--gaps-per-document",
        type=int,
        default=DEFAULT_GAPS_PER_DOCUMENT,
        help=(
            "Number of different gaps to create for each document. "
            f"Default: {DEFAULT_GAPS_PER_DOCUMENT}."
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.gaps_per_document < 1:
        raise ValueError("--gaps-per-document must be greater than or equal to 1.")

    rng = random.Random(args.seed)
    manifest = {
        "random_seed": args.seed,
        "gaps_per_document": args.gaps_per_document,
        "documents": [],
    }

    for json_file in INPUT_DIR.glob("*.json"):
        with json_file.open("r", encoding="utf-8") as file:
            content = json.load(file)

        paragraphs = content.get("paragraphs_clean", [])
        document_record = {
            "method_source_file": json_file.name,
            "title": content.get("title_clean", ""),
            "status": "processed",
            "gaps_created": [],
            "skip_reason": None,
        }

        if not paragraphs:
            print(f"Skipping {json_file.name}: no clean methodology paragraphs found.")
            document_record["status"] = "skipped"
            document_record["skip_reason"] = "no clean methodology paragraphs found"
            manifest["documents"].append(document_record)
            continue

        used_indexes = set()

        for gap_index in range(args.gaps_per_document):
            gap_data = create_paragraph_gap(paragraphs, used_indexes, rng)

            if gap_data is None:
                if gap_index == 0:
                    print(f"Skipping {json_file.name}: no suitable paragraph to remove.")
                    document_record["status"] = "skipped"
                    document_record["skip_reason"] = "no suitable paragraph to remove"
                break

            output_filename = build_output_filename(
                json_file,
                gap_index,
                args.gaps_per_document,
            )
            output_path = OUTPUT_DIR / output_filename
            gap_id = output_path.stem

            output = {
                "gap_id": gap_id,
                "title": content.get("title_clean", ""),
                **gap_data,
            }

            with output_path.open("w", encoding="utf-8") as output_file:
                json.dump(output, output_file, ensure_ascii=False, indent=2)

            document_record["gaps_created"].append({
                "gap_id": gap_id,
                "output_file": output_filename,
            })

            print(
                f"Gap created for {json_file.name}: "
                f"removed section '{gap_data['removed_section']}'"
            )

        manifest["documents"].append(document_record)

    manifest_path = OUTPUT_DIR / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, ensure_ascii=False, indent=2)

    print(f"Gap creation manifest saved to {manifest_path}.")


if __name__ == "__main__":
    main()
