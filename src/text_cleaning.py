import re
import unicodedata


COMMON_EXTRACTION_FIXES = {
    "c ¸": "ç",
    "C ¸": "Ç",
    "a ¸": "aç",
    "A ¸": "Aç",
    "e ¸": "eç",
    "E ¸": "Eç",
    "i ¸": "iç",
    "I ¸": "Iç",
    "o ¸": "oç",
    "O ¸": "Oç",
    "u ¸": "uç",
    "U ¸": "Uç",
    "dist ú": "distú",
    "Dist ú": "Distú",
    "m á": "má",
    "M á": "Má",
    "pri-vacidade": "privacidade",
    "atenc ¸": "atenç",
    "detecc ¸": "detecç",
    "aplicac ¸": "aplicaç",
    "extrac ¸": "extraç",
    "selec ¸": "seleç",
    "conduc ¸": "conduç",
    "avaliac ¸": "avaliaç",
    "classificac ¸": "classificaç",
    "limitac ¸": "limitaç",
    "comparac ¸": "comparaç",
    "informac ¸": "informaç",
    "combinac ¸": "combinaç",
    "integrac ¸": "integraç",
    "adoc ¸": "adoç",
    "direc ¸": "direç",
    "func ¸": "funç",
    "relac ¸": "relaç",
    "sec ¸": "seç",
    "populac ¸": "populaç",
    "interpretac ¸": "interpretaç",
    "medic ¸": "mediç",
    "crianc ¸": "crianç",
    "trac ¸": "traç",
    "avanc ¸": "avanç"
}


def normalize_for_matching(text: str) -> str:
    if not text:
        return ""

    text = text.lower().strip()
    text = "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )
    text = re.sub(r"\s+", " ", text)
    return text


def clean_extracted_text(text: str) -> str:
    if not text:
        return ""

    cleaned = text

    for wrong, correct in COMMON_EXTRACTION_FIXES.items():
        cleaned = cleaned.replace(wrong, correct)

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    cleaned = cleaned.strip()

    return cleaned


def is_probably_table_or_figure(text: str) -> bool:
    normalized = normalize_for_matching(text)

    ignored_prefixes = [
        "table ",
        "tabela ",
        "figure ",
        "figura ",
        "quadri ",
        "quadro "
    ]

    return any(normalized.startswith(prefix) for prefix in ignored_prefixes)
