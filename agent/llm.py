"""Couche d'accès au LLM de l'agent.

L'agent utilise le **même fournisseur LLM que le moteur RAG**, configuré dans
`rag_engine/configs/default.yaml` (`provider: openai` → Claude via la passerelle
meai.cloud par défaut, ou `ollama` pour du 100 % local). Un seul endroit pour
choisir le modèle ; on peut surcharger ponctuellement via les variables d'env
`RAG__LLM__...` (ex. l'éval force `RAG__LLM__OPENAI__MODEL=claude-haiku-4-5`).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_RAG_ENGINE_ROOT = Path(__file__).resolve().parent.parent / "rag_engine"


@lru_cache(maxsize=1)
def _client():
    """Construit (une fois) le client LLM depuis la config du moteur."""
    from rag.config.factory import build_llm
    from rag.config.settings import load_settings

    return build_llm(load_settings(configs_dir=_RAG_ENGINE_ROOT / "configs"))


def chat(prompt: str, system: str | None = None, json_mode: bool = False) -> str:
    """Envoie un prompt au LLM configuré et retourne sa réponse texte.

    Les clients du moteur prennent un prompt simple : on replie donc le `system`
    en tête. `json_mode` ajoute une consigne JSON explicite — le décodage reste
    tolérant côté `chat_json` (cf. `_parse_json`), ce qui suffit avec Claude.
    """
    parts: list[str] = []
    if system:
        parts.append(system.strip())
    parts.append(prompt)
    if json_mode:
        parts.append("Réponds UNIQUEMENT avec un objet JSON valide, sans aucun texte autour.")
    return _client().generate("\n\n".join(parts))


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
