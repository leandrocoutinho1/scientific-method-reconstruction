from grobid_client.grobid_client import GrobidClient

INPUT_PATH = "data/raw_pdfs"
OUTPUT_PATH = "data/grobid_output"
CONFIG_PATH = "config/grobid_config.json"


def main():
    client = GrobidClient(config_path=CONFIG_PATH)

    client.process(
        service="processFulltextDocument",
        input_path=INPUT_PATH,
        output_path=OUTPUT_PATH,
        n=10,
        generateIDs=False,
        consolidate_header=True,
        consolidate_citations=False,
        include_raw_affiliations=False,
        include_raw_citations=False,
        segmentSentences=True,
        teiCoordinates=False,
        json_output=True,
    )

    print("Finished processing PDFs with GROBID.")


if __name__ == "__main__":
    main()
