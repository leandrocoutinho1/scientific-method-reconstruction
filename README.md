# Scientific Method Reconstruction

Prototype for automatic reconstruction of missing parts in scientific methodology sections using GROBID, Natural Language Processing and language models.

## Current Goal

The project currently tests a simple end-to-end flow:

1. Process scientific PDFs with GROBID.
2. Extract methodology sections.
3. Remove one methodology paragraph on purpose.
4. Ask a Groq language model to reconstruct the missing excerpt.

## Project Structure

```text
config/
  section_patterns.json        # Possible names for methodology sections
data/
  raw_pdfs/                    # Input PDFs
  grobid_output/               # GROBID JSON/XML outputs
  methods_extracted/           # Extracted methodology sections
  gaps/                        # Methodologies with artificial gaps
docs/
  pipeline.md                  # Development log and methodological decisions
results/
  reconstructions/             # LLM reconstruction outputs
src/
  1_parse_with_grobid.py
  2_extract_method_sections.py
  3_create_gaps.py
  4_reconstruct_with_groq.py
  text_cleaning.py
  utils.py
```

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` file from the example and fill in your Groq API key:

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

## Run GROBID

Start GROBID before processing PDFs:

```bash
docker run -t --rm -p 8070:8070 lfoppiano/grobid:0.8.2
```

## Run the Pipeline

Place PDF files in:

```text
data/raw_pdfs/
```

Then run:

```bash
python3 src/1_parse_with_grobid.py
python3 src/2_extract_method_sections.py
python3 src/3_create_gaps.py
python3 src/4_reconstruct_with_groq.py
```

For a quick reconstruction test with only one gap:

```bash
python3 src/4_reconstruct_with_groq.py --limit 1 --seed 42
```

## Outputs

Methodology extraction outputs:

```text
data/methods_extracted/
```

Artificial gap outputs:

```text
data/gaps/
```

Groq reconstruction outputs:

```text
results/reconstructions/
```
