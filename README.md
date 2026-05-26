# Scientific Method Reconstruction

Prototype for automatic reconstruction of missing parts in scientific methodology sections using Natural Language Processing and language models.

## Environment

Create a local `.env` file from the example and fill in your Groq API key:

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

## Run the Groq reconstruction step

After creating artificial gaps in `data/gaps/`, run:

```bash
python3 src/4_reconstruct_with_groq.py
```

The reconstructions are saved in `results/reconstructions/`.

For a quick single-file test:

```bash
python3 src/4_reconstruct_with_groq.py --limit 1 --seed 42
```
