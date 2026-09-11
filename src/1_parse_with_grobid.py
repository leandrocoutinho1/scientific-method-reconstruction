import shutil
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory

from grobid_client.grobid_client import GrobidClient

INPUT_PATH = "data/raw_pdfs"
OUTPUT_PATH = "data/grobid_output"
CONFIG_PATH = "config/grobid_config.json"


def parse_args():
    parser = ArgumentParser(
        description="Process PDFs with GROBID."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of PDFs to process.",
    )
    return parser.parse_args()


def prepare_input_path(limit: int):
    if limit is None:
        return INPUT_PATH, None

    temp_dir = TemporaryDirectory()
    temp_path = Path(temp_dir.name)

    for pdf_path in sorted(Path(INPUT_PATH).glob("*.pdf"))[:limit]:
        shutil.copy2(pdf_path, temp_path / pdf_path.name)

    return str(temp_path), temp_dir


def main():
    args = parse_args()
    output_dir = Path(OUTPUT_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)

    for old_output in output_dir.glob("*.json"):
        old_output.unlink()

    for old_output in output_dir.glob("*.tei.xml"):
        old_output.unlink()

    client = GrobidClient(config_path=CONFIG_PATH)
    input_path, temp_dir = prepare_input_path(args.limit)

    try:
        client.process(
            service="processFulltextDocument",
            input_path=input_path,
            output=OUTPUT_PATH,
            n=1,
            generateIDs=False,
            consolidate_header=True,
            consolidate_citations=False,
            include_raw_affiliations=False,
            include_raw_citations=False,
            segment_sentences=True,
            tei_coordinates=False,
            json_output=True,
            force=True,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    print("Finished processing PDFs with GROBID.")


if __name__ == "__main__":
    main()
