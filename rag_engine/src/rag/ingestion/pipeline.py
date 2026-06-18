"""High-level ingestion pipeline.

Glue between parser → embedder → doc store → vector store. Pure orchestration:
no business logic lives here, just sequencing and bookkeeping.

The pipeline is intentionally synchronous in the POC — easier to debug and
fast enough for the corpora we're targeting. If volumes grow, we'll swap in
a worker queue later (deferred to M5+ per the roadmap).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rag.adapters.doc_stores.sqlite_store import SQLiteDocumentStore
from rag.adapters.parsers.pymupdf_parser import PyMuPDFParser
from rag.config.factory import build_embedder, build_vector_store
from rag.config.settings import Settings
from rag.interfaces import VectorStore
from rag.interfaces.types import ChildChunk, VectorItem
from rag.utils.context import query_id_context
from rag.utils.logging import get_logger

_log = get_logger(__name__)

EmbedFn = Callable[[list[str]], list[list[float]]]


def ingest_pdf(
    path: Path,
    *,
    parser: PyMuPDFParser,
    doc_store: SQLiteDocumentStore,
    vector_store: VectorStore,
    embedder_embed: EmbedFn,
) -> dict[str, int]:
    """Ingest a single PDF. Returns a small stats dict for the caller to log."""
    path = Path(path)
    with query_id_context() as qid:
        _log.info("ingest starting", source_file=path.name, query_id=qid)

        parents, children = parser.parse(path)
        doc_store.put(parents)

        if children:
            vectors = embedder_embed([c.text for c in children])
            items = [_to_vector_item(c, v) for c, v in zip(children, vectors, strict=True)]
            vector_store.upsert(items)

        stats = {
            "parents": len(parents),
            "children": len(children),
            "vector_count": vector_store.count(),
            "doc_count": doc_store.count(),
        }
        _log.info("ingest done", source_file=path.name, **stats)
        return stats


def ingest_directory(
    src: Path,
    settings: Settings,
    *,
    pattern: str = "*.pdf",
) -> dict[str, int]:
    """Ingest every PDF in `src` matching `pattern`. Idempotent."""
    src = Path(src)
    if not src.is_dir():
        raise NotADirectoryError(src)

    parser = PyMuPDFParser()
    doc_store = SQLiteDocumentStore(db_path=settings.data_dir / "parents.sqlite")
    vector_store = build_vector_store(settings)
    embedder = build_embedder(settings)

    # Use case-insensitive suffix matching so *.pdf also captures *.PDF.
    target_suffix = Path(pattern).suffix.lower()
    pdfs = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() == target_suffix)

    totals = {"files": 0, "parents": 0, "children": 0}
    for pdf in pdfs:
        stats = ingest_pdf(
            pdf,
            parser=parser,
            doc_store=doc_store,
            vector_store=vector_store,
            embedder_embed=embedder.embed,
        )
        totals["files"] += 1
        totals["parents"] += stats["parents"]
        totals["children"] += stats["children"]

    _log.info("ingest directory done", src=str(src), **totals)
    return totals


# --- helpers ---------------------------------------------------------------


def _to_vector_item(child: ChildChunk, vector: list[float]) -> VectorItem:
    meta = child.metadata.model_dump(mode="json")
    meta["parent_id"] = child.parent_id
    return VectorItem(id=child.id, vector=vector, text=child.text, metadata=meta)
