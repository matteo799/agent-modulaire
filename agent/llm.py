"""Couche d'accès au LLM local (Ollama)."""
import json
import re

import ollama

MODEL = "qwen2.5:7b"
EMBED_MODEL = "nomic-embed-text"


def chat(prompt: str, system: str | None = None, json_mode: bool = False) -> str:
    """Envoie un prompt au modèle et retourne sa réponse texte."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = ollama.chat(model=MODEL, messages=messages,
                           format="json" if json_mode else None)
    return response["message"]["content"]


def _parse_json(raw: str):
    # Le modèle entoure parfois le JSON de ```json ... ``` ou de texte.
    match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if match:
        raw = match.group(1)
    start = min((i for i in (raw.find("["), raw.find("{")) if i != -1), default=0)
    end = max(raw.rfind("]"), raw.rfind("}")) + 1
    # strict=False : tolère les retours à la ligne bruts dans les chaînes.
    return json.loads(raw[start:end], strict=False)


def chat_json(prompt: str, system: str | None = None, retries: int = 2):
    """Comme chat(), mais force et parse une réponse JSON (avec retries)."""
    last_error = None
    for _ in range(retries + 1):
        raw = chat(prompt, system=system, json_mode=True)
        try:
            return _parse_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
    raise last_error


def embed(texts: list[str]) -> list[list[float]]:
    """Retourne les embeddings d'une liste de textes."""
    response = ollama.embed(model=EMBED_MODEL, input=texts)
    return response["embeddings"]
