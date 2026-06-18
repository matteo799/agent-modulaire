"""Sentence-Transformers `Embedder` adapter.

Defaults to BAAI/bge-m3 (multilingual, 1024-d, open weights). The model is
loaded lazily on first call so importing this module is cheap (tests can
stay fast as long as they don't actually embed).

Determinism note: sentence-transformers is deterministic for a given model
+ input text. We don't disable cuda determinism or anything — the loss of
exact bit-equality between CPU and CUDA runs is not a concern for retrieval.
"""

from __future__ import annotations

from typing import Any, cast

from rag.utils.logging import get_logger

_log = get_logger(__name__)


class SentenceTransformersEmbedder:
    """Embedder backed by `sentence_transformers.SentenceTransformer`.

    Implements the `Embedder` Protocol from `rag.interfaces`.
    """

    def __init__(
        self,
        model: str = "BAAI/bge-m3",
        *,
        device: str = "auto",
        batch_size: int = 32,
    ) -> None:
        self._model_name = model
        self._device_pref = device
        self._batch_size = batch_size
        self._model: Any | None = None  # lazy
        self._dim: int | None = None

    # --- Protocol -----------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        vectors = model.encode(
            texts,
            batch_size=self._batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # cosine sim ≈ dot product on normalized vectors
            convert_to_numpy=True,
        )
        # `vectors` is a numpy array (no stubs → Any). `.tolist()` produces
        # the right shape; we cast so mypy --strict accepts the return type.
        return cast(list[list[float]], [v.tolist() for v in vectors])

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._ensure_model()
        # _ensure_model populates _dim
        assert self._dim is not None
        return self._dim

    @property
    def model_id(self) -> str:
        return self._model_name

    # --- Internals ----------------------------------------------------------

    def _ensure_model(self) -> Any:
        if self._model is not None:
            return self._model
        # Imported lazily so that mypy + import-time cost stay minimal.
        from sentence_transformers import SentenceTransformer

        device = None if self._device_pref == "auto" else self._device_pref
        _log.info(
            "loading embedding model",
            model=self._model_name,
            device=device or "auto",
        )
        self._model = SentenceTransformer(self._model_name, device=device)
        self._dim = int(self._model.get_sentence_embedding_dimension())
        return self._model
