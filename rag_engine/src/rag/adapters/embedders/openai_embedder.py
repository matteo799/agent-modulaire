"""OpenAIEmbedder — `Embedder` adapter pour toute API d'embeddings OpenAI-compatible.

Couvre OpenAI, mais aussi tout serveur exposant `/v1/embeddings` : LM Studio,
vLLM, ou Ollama via son endpoint OpenAI (`http://localhost:11434/v1`). C'est le
pendant « API / serveur » de `SentenceTransformersEmbedder` (in-process) : on
choisit l'un ou l'autre via `embedder.provider` — d'où la modularité local ↔ API.

L'espace vectoriel doit correspondre à l'index : si on change de *modèle*
d'embedding (pas seulement de fournisseur), il faut RÉ-INGÉRER le corpus.

La clé éventuelle vient de la config (`RAG__EMBEDDER__API_KEY`), jamais en clair.
"""

from __future__ import annotations

import math
from typing import Any, cast

import httpx

from rag.utils.logging import get_logger

_log = get_logger(__name__)


class OpenAIEmbedder:
    """Embedder via HTTP `/v1/embeddings`. Implémente le `Embedder` Protocol."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        *,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        batch_size: int = 64,
        normalize: bool = True,
        timeout_s: float = 60.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/").removesuffix("/v1")
        self._api_key = api_key
        self._batch_size = batch_size
        self._normalize = normalize
        self._timeout = httpx.Timeout(timeout_s, connect=10.0)
        self._client: httpx.Client | None = None
        self._dim: int | None = None

    # --- Protocol -----------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            resp = self._post({"model": self._model, "input": batch})
            data = sorted(resp["data"], key=lambda d: d.get("index", 0))
            for item in data:
                vec = [float(x) for x in item["embedding"]]
                out.append(_l2_normalize(vec) if self._normalize else vec)
        if out and self._dim is None:
            self._dim = len(out[0])
        return out

    @property
    def dim(self) -> int:
        if self._dim is None:
            self.embed(["dimension probe"])
        assert self._dim is not None
        return self._dim

    @property
    def model_id(self) -> str:
        return self._model

    # --- Internals ----------------------------------------------------------

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._ensure_client()
        resp = client.post("/v1/embeddings", json=payload)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            _log.info("openai embedder", model=self._model, base_url=self._base_url)
            self._client = httpx.Client(base_url=self._base_url, timeout=self._timeout, headers=headers)
        return self._client


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]
