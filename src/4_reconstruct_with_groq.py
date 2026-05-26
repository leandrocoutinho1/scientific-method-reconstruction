import json
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv():
        return False

INPUT_DIR = Path("data/gaps")
OUTPUT_DIR = Path("results/reconstructions")
DEFAULT_MODEL = "llama-3.1-8b-instant"
DEFAULT_GENERATION_SEED = 42
MISSING_TOKEN = "[MISSING_TEXT]"


SYSTEM_PROMPT = """
Você é um assistente especializado em reconstrução de trechos metodológicos científicos.
Sua tarefa é preencher exclusivamente o trecho marcado como [MISSING_TEXT], mantendo o
idioma, o estilo acadêmico, a coerência com o contexto anterior e posterior e a estrutura
típica de uma seção de metodologia.

Regras obrigatórias:
- Gere apenas o trecho ausente, não reescreva a metodologia inteira.
- Não adicione resultados, conclusões, discussão ou informações que não sejam sustentadas pelo contexto.
- Não cite fontes novas.
- Preserve o idioma predominante do texto de entrada.
- Evite frases vagas como "diversos métodos foram utilizados" quando o contexto exigir especificidade.
- Se o contexto não permitir uma reconstrução segura, gere uma reconstrução conservadora e marque confiança baixa.

Responda exclusivamente em JSON válido, sem markdown, com os campos:
{
  "reconstructed_excerpt": "trecho reconstruído"
}
""".strip()


def load_gap_files(input_dir: Path, limit: Optional[int] = None) -> list[Path]:
    gap_files = sorted(
        path
        for path in input_dir.glob("*.json")
        if path.name != "manifest.json"
    )

    if limit is not None:
        return gap_files[:limit]

    return gap_files


def build_user_prompt(gap_data: dict) -> str:
    title = gap_data.get("title", "")
    removed_section = gap_data.get("removed_section", "")
    masked_text = gap_data.get("masked_text", "")

    return f"""
Reconstrua o trecho ausente de uma metodologia científica.

Título do artigo:
{title}

Seção associada ao trecho removido:
{removed_section}

Metodologia com lacuna:
{masked_text}

Lembre-se: substitua apenas o marcador {MISSING_TOKEN}. Retorne somente JSON válido.
""".strip()


def parse_json_response(response_text: str) -> tuple[dict, bool]:
    try:
        return json.loads(response_text), True
    except json.JSONDecodeError:
        return {
            "reconstructed_excerpt": response_text.strip(),
        }, False


def reconstruct_gap(client, model: str, gap_data: dict, seed: int) -> dict:
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=700,
        seed=seed,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(gap_data)},
        ],
    )

    raw_response = response.choices[0].message.content or ""
    parsed_response, valid_json = parse_json_response(raw_response)

    return {
        "gap_id": gap_data.get("gap_id"),
        "title": gap_data.get("title"),
        "removed_excerpt": gap_data.get("removed_excerpt"),
        "model": model,
        "reconstructed_excerpt": parsed_response.get("reconstructed_excerpt", ""),
    }


def save_reconstruction(output_dir: Path, gap_file: Path, result: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{gap_file.stem}_groq_reconstruction.json"

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)

    return output_path


def parse_args():
    parser = ArgumentParser(
        description="Reconstruct artificial methodology gaps using a Groq language model."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=INPUT_DIR,
        help=f"Directory containing gap JSON files. Default: {INPUT_DIR}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Directory where reconstructions will be saved. Default: {OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Groq model name. Default: env GROQ_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of gap files to process.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_GENERATION_SEED,
        help=(
            "Generation seed sent to Groq for more reproducible outputs. "
            f"Default: {DEFAULT_GENERATION_SEED}."
        ),
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()
    model = args.model or os.getenv("GROQ_MODEL", DEFAULT_MODEL)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found. Create a .env file based on .env.example."
        )

    gap_files = load_gap_files(args.input_dir, args.limit)
    if not gap_files:
        print(f"No gap files found in {args.input_dir}.")
        return

    try:
        from groq import Groq
    except ImportError as exc:
        raise ImportError(
            "The groq package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    client = Groq(api_key=api_key)

    for gap_file in gap_files:
        with gap_file.open("r", encoding="utf-8") as input_file:
            gap_data = json.load(input_file)

        result = reconstruct_gap(client, model, gap_data, args.seed)
        output_path = save_reconstruction(args.output_dir, gap_file, result)

        print(f"{gap_file.name}: reconstruction saved to {output_path}")


if __name__ == "__main__":
    main()
