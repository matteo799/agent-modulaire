"""APIReranker — `Reranker` adapter pour un service de rerank HTTP.

Pendant « API » de `BGEReranker` (cross-encoder local) : on choisit l'un ou
l'autre via `reranker.provider`. Suit le schéma `/rerank` commun à Cohere et
Jina AI :

    POST {base_url}/rerank
    { "model": ..., "query": ..., "documents": [...], "top_n": k }
    → { "results": [ { "index": i, "relevance_score": s }, ... ] }

La clé vient de la config (`RAG__RERANKER__API_KEY`), jamais en clair.

NB : aucun fournisseur de rerank n'est branché par défaut dans ce dépôt (la
passerelle Claude n'en sert pas) ; cet adapter existe pour rendre le reranker
modulaire local ↔ API dès qu'un endpoint Cohere/Jina-compatible est fourni.
"""

from __future__ import annotations

from typing import Any, cast

import httpx

from rag.interfaces.types import SearchHit
from rag.utils.logging import get_logger

_log = get_logger(__name__)


class APIReranker:
    """Rerank via un service HTTP. Implémente le `Reranker` Protocol."""

    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        api_key: str = "",
        timeout_s: float = 60.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)
        self._client: httpx.Client | None = None

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits or top_k <= 0:
            return []
        payload = {
            "model": self._model,
            "query": query,
            "documents": [h.text for h in hits],
            "top_n": top_k,
        }
        client = self._ensure_client()
        resp = client.post("/rerank", json=payload)
        resp.raise_for_status()
        results = cast(dict[str, Any], resp.json()).get("results", [])

        out: list[SearchHit] = []
        for r in results:
            i = int(r.get("index", -1))
            if 0 <= i < len(hits):
                h = hits[i]
                out.append(
                    SearchHit(
                        id=h.id,
                        text=h.text,
                        score=float(r.get("relevance_score", h.score)),
                        metadata=h.metadata,
                    )
                )
        return out[:top_k]

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            _log.info("api reranker", model=self._model, base_url=self._base_url)
            self._client = httpx.Client(base_url=self._base_url, timeout=self._timeout, headers=headers)
        return self._client
