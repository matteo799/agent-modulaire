"""Protocols every adapter must implement.

These are duck-typed (`typing.Protocol`) on purpose: an adapter doesn't need to
inherit anything, it just needs to expose the right methods. This keeps the
adapter packages free from any dependency on `rag.interfaces` if you ever want
to ship one standalone.

Rule of thumb: if you find yourself importing a concrete adapter outside of
`rag.adapters.*` or the composition root (`rag.config.factory`), you're doing
it wrong — depend on the Protocol instead.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from rag.interfaces.types import (
    ChildChunk,
    ParentChunk,
    SearchHit,
    VectorItem,
)


@runtime_checkable
class DocumentParser(Protocol):
    """Turns a raw file (PDF for now) into structured parent + child chunks.

    Implementations: PyMuPDFParser (fast, baseline), UnstructuredParser (richer
    tables), MarkerParser (best quality, slower). All must return the same shape.
    """

    def parse(self, path: Path) -> tuple[list[ParentChunk], list[ChildChunk]]: ...


@runtime_checkable
class Embedder(Protocol):
    """Turns text into vectors. Must be deterministic for a given (model, text)."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dim(self) -> int: ...

    @property
    def model_id(self) -> str:
        """Stable identifier persisted alongside vectors so we can detect mismatches."""
        ...


@runtime_checkable
class VectorStore(Protocol):
    """Dense vector storage + ANN search. THE interface that makes swapping the vector store trivial.

    Implementations MUST:
    - be idempotent on upsert (same id overwrites cleanly),
    - support metadata filtering (at least equality on flat string keys),
    - return hits with normalized scores (cosine similarity, 0..1).
    """

    def upsert(self, items: list[VectorItem]) -> None: ...

    def search(
        self,
        vector: list[float],
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    def delete(self, ids: list[str]) -> None: ...

    def count(self) -> int: ...


@runtime_checkable
class DocumentStore(Protocol):
    """Key-value store for parent chunks. Separate from VectorStore on purpose:
    parents don't need ANN, they need fast id→text lookup. SQLite in POC, Postgres later.
    """

    def put(self, parents: list[ParentChunk]) -> None: ...

    def get(self, ids: list[str]) -> list[ParentChunk]: ...

    def delete(self, ids: list[str]) -> None: ...


@runtime_checkable
class Reranker(Protocol):
    """Cross-encoder rerank pass on a small candidate set (typically top 20 → top 5)."""

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[SearchHit]: ...


@runtime_checkable
class LLMClient(Protocol):
    """Generation backend. Sync + streaming. Token counting matters for prompt budgeting."""

    def generate(self, prompt: str, **kwargs: Any) -> str: ...

    def stream_generate(self, prompt: str, **kwargs: Any) -> Iterator[str]: ...

    def count_tokens(self, text: str) -> int: ...

    @property
    def model_id(self) -> str: ...


@runtime_checkable
class Retriever(Protocol):
    """High-level retrieval. The CRAG graph only knows about this.

    Concrete retrievers compose: HybridRetriever(DenseRetriever + BM25Retriever),
    ParentChildRetriever(inner), RerankingRetriever(inner). All implement this Protocol.
    """

    def retrieve(
        self,
        query: str,
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...
