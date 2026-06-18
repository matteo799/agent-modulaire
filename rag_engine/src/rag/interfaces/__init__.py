"""Public re-exports for the interfaces package.

Always import from `rag.interfaces`, never from the submodules, so we can
reshuffle internals without breaking adapters.
"""

from rag.interfaces.protocols import (
    DocumentParser,
    DocumentStore,
    Embedder,
    LLMClient,
    Reranker,
    Retriever,
    VectorStore,
)
from rag.interfaces.types import (
    Answer,
    ChildChunk,
    ChunkMetadata,
    ChunkType,
    Citation,
    ClassificationLevel,
    CRAGState,
    Decision,
    GradedHit,
    ParentChunk,
    RelevanceLabel,
    SearchHit,
    VectorItem,
)

__all__ = [
    "Answer",
    "CRAGState",
    "ChildChunk",
    "ChunkMetadata",
    "ChunkType",
    "Citation",
    "ClassificationLevel",
    "Decision",
    "DocumentParser",
    "DocumentStore",
    "Embedder",
    "GradedHit",
    "LLMClient",
    "ParentChunk",
    "RelevanceLabel",
    "Reranker",
    "Retriever",
    "SearchHit",
    "VectorItem",
    "VectorStore",
]
