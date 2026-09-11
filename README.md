# Scientific Method Reconstruction

Prototype for automatic reconstruction of missing parts in scientific methodology sections using GROBID, section pattern matching and language models.

## Current Goal

The project currently tests a simple end-to-end flow:

1. Extract structured text from ScienceDirect PDF articles with GROBID.
2. Extract methodology sections using configurable section title patterns.
3. Remove one methodology paragraph on purpose.
4. Ask Gemini to reconstruct the missing excerpt.
5. Optionally test OpenRouter models on the same gaps.

## Project Structure

```text
config/
  grobid_config.json           # Local GROBID client configuration
  section_patterns.json        # Possible names for methodology sections
data/
  raw_pdfs/                    # Input PDFs
  grobid_output/               # GROBID JSON and TEI XML outputs
  methods_extracted/           # Extracted methodology sections
  gaps/                        # Methodologies with artificial gaps
docs/
  pipeline.md                  # Development log and methodological decisions
results/
  reconstructions/             # LLM reconstruction outputs
  openrouter_tests/            # OpenRouter model test outputs
src/
  1_parse_with_grobid.py
  2_extract_method_sections.py
  3_create_gaps.py
  4_reconstruct_with_gemini.py
  5_test_openrouter_models.py
  llm_response_schema.py
  text_cleaning.py
  utils.py
```

## Setup

Install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Create a local `.env` file from the example and fill in your Gemini API key:

```bash
cp .env.example .env
```

```env
gemini-api-key=your_gemini_api_key_here
gemini-model=gemini-flash-latest
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

Run GROBID locally before step 1:

```bash
docker run -d --rm --name scientific-method-grobid -p 8070:8070 lfoppiano/grobid:0.8.2
```

## Run the Pipeline

Place PDF files in:

```text
data/raw_pdfs/
```

Then run:

```bash
.venv/bin/python src/1_parse_with_grobid.py
.venv/bin/python src/2_extract_method_sections.py
.venv/bin/python src/3_create_gaps.py
.venv/bin/python src/4_reconstruct_with_gemini.py
```

For a quick methodology extraction test with only one article:

```bash
.venv/bin/python src/2_extract_method_sections.py --limit 1
```

For a quick reconstruction test with only one gap:

```bash
.venv/bin/python src/4_reconstruct_with_gemini.py --limit 1
```

For a quick OpenRouter test with one gap:

```bash
.venv/bin/python src/5_test_openrouter_models.py --model openrouter/free --limit 1
```

To test the configured free model list with one gap each:

```bash
.venv/bin/python src/5_test_openrouter_models.py --model free-list --limit 1
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

Gemini reconstruction outputs:

```text
results/reconstructions/
```

LLM responses are validated with Pydantic before being saved.

OpenRouter test outputs:

```text
results/openrouter_tests/
```
