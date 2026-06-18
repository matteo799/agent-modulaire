"""Shared data types used across all interfaces.

These are intentionally pydantic models (not dataclasses) to get:
- runtime validation at module boundaries,
- free JSON (de)serialization for the API and storage,
- a single source of truth for what a "chunk" / "hit" looks like.

If you need to extend a type, prefer adding an optional field with a default
over changing existing signatures. Anything stored on disk should remain
backward-compatible.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    FIGURE_CAPTION = "figure_caption"
    FORMULA = "formula"


class ClassificationLevel(str, Enum):
    """Placeholder taxonomy. Mirror the client's real taxonomy when available."""

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


class ChunkMetadata(BaseModel):
    """Metadata attached to every chunk, parent or child.

    Designed so retrieval can filter on any of these without re-indexing.
    """

    source_file: str
    page: int | None = None
    section_path: list[str] = Field(default_factory=list)  # ["Chapter 3", "3.2 ..."]
    chunk_type: ChunkType = ChunkType.TEXT
    language: str = "fr"
    classification_level: ClassificationLevel = ClassificationLevel.PUBLIC
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    parser_version: str = "0.0.0"
    extra: dict[str, Any] = Field(default_factory=dict)


class ParentChunk(BaseModel):
    """A coarse-grained chunk (section / page group). Stored in the DocumentStore.

    Child chunks reference this via `parent_id`. Parents are what we feed the LLM.
    """

    id: str
    text: str
    metadata: ChunkMetadata


class ChildChunk(BaseModel):
    """A fine-grained chunk (paragraph / sentence). Stored in the VectorStore.

    Carries a back-reference to its parent so we can hydrate context at query time.
    """

    id: str
    parent_id: str
    text: str
    metadata: ChunkMetadata


class VectorItem(BaseModel):
    """What gets upserted into a VectorStore."""

    id: str
    vector: list[float]
    text: str
    metadata: dict[str, Any]


class SearchHit(BaseModel):
    """Generic retrieval result. Adapters must normalize their native shape into this."""

    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class RelevanceLabel(str, Enum):
    RELEVANT = "relevant"
    AMBIGUOUS = "ambiguous"
    IRRELEVANT = "irrelevant"


class GradedHit(BaseModel):
    hit: SearchHit
    label: RelevanceLabel
    reason: str | None = None


class Citation(BaseModel):
    """A pointer back to the source, attached to each generated claim."""

    source_file: str
    page: int | None = None
    chunk_id: str


class Answer(BaseModel):
    text: str
    citations: list[Citation]
    grounded: bool  # set by the ground_check node
    used_chunks: list[str]  # chunk ids actually injected in the prompt


class Decision(str, Enum):
    """Sortie du nœud `decide` : que faire après le grading des documents ?

    - PROCEED  : le retrieval est jugé bon, on passe à la génération.
    - REWRITE  : le retrieval est ambigu/insuffisant, on reformule et on retente.
    - FALLBACK : tout est irrelevant ou on a atteint max_iterations, on rend
                 la main au nœud `fallback_no_answer`.
    """

    PROCEED = "proceed"
    REWRITE = "rewrite"
    FALLBACK = "fallback"


class CRAGState(BaseModel):
    """État porté par le graphe CRAG (LangGraph).

    Pourquoi pydantic et pas un TypedDict : on veut la validation au début
    de chaque nœud (les nœuds reçoivent un dict, on parse en `CRAGState`).
    Ça évite qu'un nœud foireux corrompe silencieusement l'état partagé.

    Le champ `iteration` est incrémenté par `rewrite_query` à chaque tour.
    `max_iterations` est lu depuis `CRAGSettings.max_iterations`. Si on tente
    une réécriture alors que `iteration >= max_iterations`, le `decide` doit
    basculer en FALLBACK.
    """

    # --- entrée ---
    original_query: str  # la requête utilisateur brute (jamais réécrite)
    query: str  # la requête courante (peut être == original_query, ou réécrite)

    # --- retrieval ---
    hits: list[SearchHit] = Field(default_factory=list)
    graded_hits: list[GradedHit] = Field(default_factory=list)

    # --- contrôle de boucle ---
    decision: Decision | None = None
    iteration: int = 0
    max_iterations: int = 2

    # --- post-traitement / génération ---
    refined_chunks: list[str] = Field(default_factory=list)  # phrases gardées par refine_knowledge
    used_chunk_ids: list[str] = Field(
        default_factory=list
    )  # chunks effectivement injectés dans le prompt
    answer: Answer | None = None

    # --- bookkeeping ---
    fallback_triggered: bool = False  # vrai si on a basculé en fallback_no_answer
