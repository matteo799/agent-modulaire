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
import time
from functools import lru_cache
from pathlib import Path

import httpx

_RAG_ENGINE_ROOT = Path(__file__).resolve().parent.parent / "rag_engine"

# Robustesse réseau : le client du moteur réessaie déjà 3× sur ConnectError /
# ReadTimeout (tenacity), mais d'AUTRES erreurs transport (RemoteProtocolError,
# coupure serveur…) remontent telles quelles et tuent tout le run. On ajoute ici
# un filet au niveau agent : quelques tentatives supplémentaires, puis une
# exception TYPÉE que les étages (planner, executor, synthèse) savent dégrader
# proprement au lieu de planter.
_AGENT_RETRIES = 2
_BACKOFF_S = 1.5

# Compteur d'usage léger (pour l'évaluation : tokens ≈ via count_tokens du client).
# Approximation assumée — sert à comparer le coût relatif entre questions/stacks,
# pas à facturer. reset_usage() avant une requête, get_usage() après.
_usage = {"calls": 0, "in_tokens": 0, "out_tokens": 0}


def reset_usage() -> None:
    _usage.update(calls=0, in_tokens=0, out_tokens=0)


def get_usage() -> dict:
    return dict(_usage)


def _tally(prompt: str, response: str) -> None:
    """Ajoute l'estimation de tokens d'un aller-retour au compteur (best-effort)."""
    try:
        client = _client()
        _usage["calls"] += 1
        _usage["in_tokens"] += client.count_tokens(prompt)
        _usage["out_tokens"] += client.count_tokens(response)
    except Exception:  # le comptage ne doit jamais casser une requête
        pass


class LLMUnavailable(RuntimeError):
    """Le service LLM est injoignable après retries (réseau / timeout / 5xx).

    Distincte d'une erreur de contenu : signale une indisponibilité transitoire
    du service, à traiter par un repli gracieux, pas par une stack trace.
    """


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
    text = "\n\n".join(parts)

    last_exc: Exception | None = None
    for attempt in range(_AGENT_RETRIES + 1):
        try:
            response = _client().generate(text)
            _tally(text, response)
            return response
        except httpx.HTTPError as exc:  # transport + statut HTTP (5xx via raise_for_status)
            last_exc = exc
            if attempt < _AGENT_RETRIES:
                time.sleep(_BACKOFF_S * (attempt + 1))
    raise LLMUnavailable(
        f"LLM injoignable après {_AGENT_RETRIES + 1} tentatives : {last_exc}"
    ) from last_exc


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
