"""Parent-Child chunking.

Given the sections produced by `rag.ingestion.sectioning`, we build:
- one **parent chunk** per section (or the section's text truncated if it gets
  silly long — the LLM context budget is finite),
- multiple **child chunks** inside that parent, suitable for dense retrieval.

The split is recursive in the LangChain sense: try paragraph boundaries first,
then sentences, then words, then characters. RecursiveCharacterTextSplitter
is battle-tested for this and we don't reinvent it.

Chunk ids are deterministic — same input PDF reingested twice yields the same
ids, which is the cornerstone of idempotent ingestion (M2.9).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.ingestion.sectioning import Section
from rag.interfaces.types import (
    ChildChunk,
    ChunkMetadata,
    ChunkType,
    ClassificationLevel,
    ParentChunk,
)


@dataclass(slots=True)
class ChunkingConfig:
    """Knobs for the chunker. Defaults are sensible for course PDFs in French.

    `parent_max_chars`: hard cap above which a section is truncated for the
    parent chunk. Children are unaffected — they're built from the full text.
    """

    child_size: int = 800  # characters, ~200 tokens with average French
    child_overlap: int = 120
    parent_max_chars: int = 12_000  # ~3k tokens — fits any LLM context with margin


# Default separators favour paragraph/sentence boundaries, then words.
_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]


def _id_for(source_file: str, *parts: str | int) -> str:
    """Deterministic short id from source + positional parts.

    SHA1 truncated to 16 hex chars — plenty for collision-free use within
    a single corpus (~1e9 unique values).
    """
    raw = source_file + "::" + "::".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def chunk_section(
    section: Section,
    source_file: str,
    section_index: int,
    *,
    config: ChunkingConfig | None = None,
    language: str = "fr",
    classification: ClassificationLevel = ClassificationLevel.PUBLIC,
    parser_version: str = "pymupdf-1",
) -> tuple[ParentChunk, list[ChildChunk]]:
    """Turn one section into (1 parent, N children) with deterministic ids."""
    cfg = config or ChunkingConfig()

    parent_text = section.text[: cfg.parent_max_chars]
    parent_id = _id_for(source_file, "p", section_index)

    base_meta = ChunkMetadata(
        source_file=source_file,
        page=section.start_page,
        section_path=section.section_path,
        chunk_type=ChunkType.TEXT,
        language=language,
        classification_level=classification,
        parser_version=parser_version,
        extra={"start_page": str(section.start_page), "end_page": str(section.end_page)},
    )

    parent = ParentChunk(id=parent_id, text=parent_text, metadata=base_meta)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.child_size,
        chunk_overlap=cfg.child_overlap,
        separators=_DEFAULT_SEPARATORS,
        length_function=len,
    )
    child_texts = splitter.split_text(section.text)

    children: list[ChildChunk] = []
    for i, ctext in enumerate(child_texts):
        children.append(
            ChildChunk(
                id=_id_for(source_file, "c", section_index, i),
                parent_id=parent_id,
                text=ctext,
                metadata=base_meta.model_copy(
                    update={"extra": {**base_meta.extra, "child_index": str(i)}}
                ),
            )
        )
    return parent, children


def chunk_document(
    sections: list[Section],
    source_file: str,
    *,
    config: ChunkingConfig | None = None,
    language: str = "fr",
    classification: ClassificationLevel = ClassificationLevel.PUBLIC,
    parser_version: str = "pymupdf-1",
) -> tuple[list[ParentChunk], list[ChildChunk]]:
    """Chunk a whole document. Same call signature contract as the Protocol expects."""
    parents: list[ParentChunk] = []
    children: list[ChildChunk] = []
    for i, section in enumerate(sections):
        p, cs = chunk_section(
            section,
            source_file=source_file,
            section_index=i,
            config=config,
            language=language,
            classification=classification,
            parser_version=parser_version,
        )
        parents.append(p)
        children.extend(cs)
    return parents, children
