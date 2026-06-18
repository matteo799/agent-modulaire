"""BGEReranker — adapter cross-encoder (`sentence-transformers.CrossEncoder`).

Pourquoi un reranker : le retrieval dense + BM25 produit un top-20 « pas
trop mauvais », mais un cross-encoder (qui encode `(query, passage)`
conjointement) ordonne ce top-20 bien plus finement qu'une similarité
cosinus. Coût : un appel modèle par hit, donc on l'applique sur 20 candidats
maximum, pas sur le corpus.

Modèle par défaut : `BAAI/bge-reranker-v2-m3` — multilingue, open-weights,
même famille que notre embedder (BGE-M3), donc cohérent.

Normalisation : `CrossEncoder.predict` retourne des logits non bornés. On
applique une sigmoïde pour rester dans [0, 1] (« higher = better »),
cohérent avec le contrat de `SearchHit.score`.

Lazy load : le modèle ne se charge qu'au premier `rerank()` — l'import du
module reste gratuit pour les tests qui ne reranke pas vraiment.
"""

from __future__ import annotations

import math
from typing import Any

from rag.interfaces.types import SearchHit
from rag.utils.logging import get_logger

_log = get_logger(__name__)


class BGEReranker:
    """Cross-encoder rerank pass.

    Implémente le `Reranker` Protocol de `rag.interfaces`.
    """

    def __init__(
        self,
        model: str = "BAAI/bge-reranker-v2-m3",
        *,
        device: str = "auto",
        batch_size: int = 32,
    ) -> None:
        self._model_name = model
        self._device_pref = device
        self._batch_size = batch_size
        self._model: Any | None = None

    # --- Protocol -----------------------------------------------------------

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]:
        if not hits or top_k <= 0:
            return []

        model = self._ensure_model()
        # Le CrossEncoder attend des paires (query, passage).
        pairs = [(query, h.text) for h in hits]
        raw_scores = model.predict(
            pairs,
            batch_size=self._batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        rescored = [
            SearchHit(
                id=hit.id,
                text=hit.text,
                score=_sigmoid(float(s)),
                metadata=hit.metadata,
            )
            for hit, s in zip(hits, raw_scores, strict=True)
        ]
        rescored.sort(key=lambda h: h.score, reverse=True)
        return rescored[:top_k]

    # --- Internals ----------------------------------------------------------

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        # Import paresseux : sentence-transformers est lourd, on évite de le
        # charger tant qu'on n'a pas réellement à reranker.
        from sentence_transformers import CrossEncoder

        device = None if self._device_pref == "auto" else self._device_pref
        _log.info(
            "loading reranker model",
            model=self._model_name,
            device=device or "auto",
        )
        self._model = CrossEncoder(self._model_name, device=device)
        return self._model


def _sigmoid(x: float) -> float:
    # math.exp avec un argument > ~700 explose ; on clampe pour la stabilité.
    # En pratique les logits de CrossEncoder restent dans [-10, 10].
    x = max(-50.0, min(50.0, x))
    return 1.0 / (1.0 + math.exp(-x))
