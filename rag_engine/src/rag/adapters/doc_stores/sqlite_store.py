"""SQLite-backed `DocumentStore` for parent chunks.

Why SQLite for parents (and not the vector store): parents are looked up by id only —
no ANN search, no embedding. A relational K-V table on disk is the cheapest
and most observable option. Easy to migrate to Postgres later (same schema).

Idempotency: `put` uses INSERT OR REPLACE, so reingesting the same PDF
overwrites instead of duplicating. Combined with deterministic chunk ids
from `rag.ingestion.chunker`, the whole pipeline is safely re-runnable.

Thread-safety: we open one connection per call. SQLite handles concurrent
readers fine; writers are serialised at the file level. For the POC volume
this is plenty; if it ever becomes a bottleneck, switch to a single
long-lived connection guarded by a lock.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from rag.interfaces.types import ChunkMetadata, ParentChunk

_SCHEMA = """
CREATE TABLE IF NOT EXISTS parents (
    id          TEXT PRIMARY KEY,
    text        TEXT NOT NULL,
    metadata    TEXT NOT NULL          -- JSON-encoded ChunkMetadata
);

CREATE INDEX IF NOT EXISTS idx_parents_source
    ON parents (json_extract(metadata, '$.source_file'));
"""


class SQLiteDocumentStore:
    """Persistent key-value store for parent chunks."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # --- Protocol methods ---------------------------------------------------

    def put(self, parents: list[ParentChunk]) -> None:
        if not parents:
            return
        rows = [(p.id, p.text, p.metadata.model_dump_json()) for p in parents]
        with self._connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO parents (id, text, metadata) VALUES (?, ?, ?)",
                rows,
            )

    def get(self, ids: list[str]) -> list[ParentChunk]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            cur = conn.execute(
                f"SELECT id, text, metadata FROM parents WHERE id IN ({placeholders})",
                ids,
            )
            rows = cur.fetchall()
        # Preserve caller's ordering (SQL doesn't guarantee it).
        by_id = {
            r[0]: ParentChunk(
                id=r[0],
                text=r[1],
                metadata=ChunkMetadata.model_validate(json.loads(r[2])),
            )
            for r in rows
        }
        return [by_id[i] for i in ids if i in by_id]

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM parents WHERE id IN ({placeholders})",
                ids,
            )

    # --- Helpers ------------------------------------------------------------

    def count(self) -> int:
        """Not in the Protocol, but handy for diagnostics and idempotency tests."""
        with self._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM parents")
            row = cur.fetchone()
            return int(row[0]) if row else 0

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
