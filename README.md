# Scientific Method Reconstruction

Prototype for automatic reconstruction of missing parts in scientific methodology sections using GROBID, section pattern matching and language models.

## Current Goal

The project currently tests a simple end-to-end flow:

1. Extract structured text from ScienceDirect PDF articles with GROBID.
2. Extract methodology sections using configurable section title patterns.
3. Remove one methodology paragraph on purpose.
4. Ask Gemini to reconstruct the missing excerpt.
5. Optionally test OpenRouter models on the same gaps.
6. Evaluate reconstruction quality with Gemini and OpenRouter as judges.

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
  reconstructions_gemma/       # Experimental Gemma reconstruction outputs
  openrouter_tests/            # OpenRouter model test outputs
  evaluations/                 # LLM evaluation outputs
src/
  1_parse_with_grobid.py
  2_extract_method_sections.py
  3_create_gaps.py
  4_reconstruct_with_gemini.py
  4_1_reconstruct_with_gemma_31b.py
  4_2_reconstruct_with_gemma_26b.py
  5_test_openrouter_models.py
  6_evaluate_reconstructions.py
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
gemini-evaluator-model=gemini-flash-latest
gemma-31b-model=gemma-4-31b-it
gemma-26b-model=gemma-4-26b-a4b-it
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_EVALUATOR_MODEL=nvidia/nemotron-3-super-120b-a12b:free
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

For an experimental Gemma 31B reconstruction test with only one gap:

```bash
.venv/bin/python src/4_1_reconstruct_with_gemma_31b.py --limit 1
```

For an experimental Gemma 26B reconstruction test with only one gap:

```bash
.venv/bin/python src/4_2_reconstruct_with_gemma_26b.py --limit 1
```

For a quick OpenRouter test with one gap:

```bash
.venv/bin/python src/5_test_openrouter_models.py --model openrouter/free --limit 1
```

To test the configured free model list with one gap each:

```bash
.venv/bin/python src/5_test_openrouter_models.py --model free-list --limit 1
```

To evaluate all saved reconstructions for one gap with Gemini and OpenRouter:

```bash
.venv/bin/python src/6_evaluate_reconstructions.py --limit 1
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

Experimental Gemma reconstruction outputs:

```text
results/reconstructions_gemma/
```

LLM responses are validated with Pydantic before being saved.

OpenRouter test outputs:

```text
results/openrouter_tests/
```

Evaluation outputs:

```text
results/evaluations/
```

## Local reconstruction with Ollama (step 4.3)

With Ollama running and `qwen3:8b` downloaded:

```bash
.venv/bin/python src/4_3_reconstruct_with_ollama.py --limit 1
```

Use `--model` to select another downloaded model. Optional environment variables:
`OLLAMA_MODEL` and `OLLAMA_BASE_URL` (default `http://localhost:11434`).
The script disables thinking, requests structured JSON, and validates it with
Pydantic. It uses an 8192-token context and a 300-second request timeout
(configurable with `--timeout`). The original excerpt is not sent to the model;
only its word count is used to set the target length, as in the other reconstrutors.
Outputs: `results/reconstructions_ollama/<model>/`.
Step 6 does not yet discover this directory automatically.

The Ollama experiment additionally enforces a word range of roughly 75–125%
of the target (which remains clamped to 20–60 words). An invalid length triggers
one correction attempt, then an error file. This controls length, not factual accuracy.
