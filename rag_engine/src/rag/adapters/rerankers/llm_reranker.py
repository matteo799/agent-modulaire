"""LLMReranker — reranking par un LLM (un seul appel), pendant « API » du cross-encoder.

Au lieu d'un cross-encoder local (BGEReranker), on demande au LLM de classer les
passages candidats par pertinence à la question, en UN appel : il renvoie les
indices des `top_k` meilleurs. Permet un pipeline 100 % API (aucun modèle local
de reranking) — le LLM peut être Claude via une passerelle OpenAI-compatible.

Choix « un appel pour tout classer » (et non un appel par passage comme le grade
CRAG) : bien plus rapide et suffisant pour ordonner une vingtaine de candidats.
"""

from __future__ import annotations

import json
import re
from typing import Any

from rag.interfaces.types import SearchHit
from rag.utils.logging import get_logger

_log = get_logger(__name__)

_PROMPT = """Tu classes des passages par pertinence pour répondre à une question.

Question : {query}

Passages (numérotés) :
{passages}

Renvoie UNIQUEMENT un objet JSON listant les numéros des {k} passages LES PLUS
pertinents, du plus pertinent au moins pertinent, sans aucun autre texte :
{{"top": [<numéros>]}}"""


class LLMReranker:
    """Rerank par LLM en un appel. Implémente le `Reranker` Protocol."""

    def __init__(self, llm: Any, *, max_chars: int = 500) -> None:
        self._llm = llm
        self._max_chars = max_chars

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits or top_k <= 0:
            return []

        passages = "\n".join(
            f"[{i + 1}] {' '.join(h.text.split())[: self._max_chars]}"
            for i, h in enumerate(hits)
        )
        prompt = _PROMPT.format(query=query, passages=passages, k=top_k)
        try:
            raw = self._llm.generate(prompt, max_tokens=200)
            order = _parse_top(raw, n=len(hits))
        except Exception:
            # Dégradation gracieuse : on garde l'ordre d'entrée.
            order = list(range(len(hits)))

        # Indices retournés (1-based → 0-based), puis on complète avec le reste
        # pour ne jamais perdre de candidat si le LLM en oublie.
        seen: list[int] = []
        for i in order:
            if 0 <= i < len(hits) and i not in seen:
                seen.append(i)
        for i in range(len(hits)):
            if i not in seen:
                seen.append(i)

        ranked = [hits[i] for i in seen[:top_k]]
        _log.info("llm.rerank", n_in=len(hits), n_out=len(ranked))
        return ranked


def _parse_top(raw: str, *, n: int) -> list[int]:
    """Extrait la liste d'indices 0-based depuis la sortie JSON du LLM."""
    match = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return [int(x) - 1 for x in data.get("top", [])]
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    # Repli : tous les entiers trouvés dans la réponse.
    return [int(x) - 1 for x in re.findall(r"\d+", raw or "")]
