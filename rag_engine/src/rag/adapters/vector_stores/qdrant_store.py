"""Qdrant `VectorStore` adapter — local-embedded or remote server.

Mode local (pas de Docker) :  QdrantSettings.url == "" ou path fourni.
Mode serveur :                 QdrantSettings.url = "http://localhost:6333".

Le client qdrant-client 1.x supporte les deux via la même API ; on choisit
en fonction de `path` : si non-None on ouvre la base locale, sinon on se
connecte à l'URL.

IDs : Qdrant n'accepte que des UUID ou des entiers non-signés 64 bits.
Nos chunk IDs sont des chaînes hex 16 caractères (64 bits). On stocke
l'ID entier comme ID Qdrant et on met l'ID string original dans le payload
sous la clé `_id`. Le round-trip est transparent pour le reste du code.

Score : Qdrant retourne un score de similarité cosinus dans [0, 1] quand
la collection est créée avec `Distance.COSINE` et des vecteurs normalisés.
On n'a pas besoin de conversion (pas de distance à inverser).

Filtres : on utilise l'API `Filter` de Qdrant (`FieldCondition` / `MatchValue`)
pour une égalité stricte sur les métadonnées.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rag.interfaces.types import SearchHit, VectorItem
from rag.utils.logging import get_logger

_log = get_logger(__name__)

# Nom de la clé payload qui stocke l'ID string original.
_PAYLOAD_ID_KEY = "_id"


def _hex_to_int(hex_id: str) -> int:
    """Convertit un ID hex-string 16 chars en entier Qdrant."""
    try:
        return int(hex_id, 16)
    except ValueError:
        # Fallback : hash 64-bit stable sur les IDs non-hex.
        return abs(hash(hex_id)) % (2**63)


def _build_filter(filters: dict[str, Any]) -> Any:
    """Construit un `qdrant_client.models.Filter` depuis un dict d'égalités."""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()]
    return Filter(must=conditions)


class QdrantVectorStore:
    """Adapter Qdrant (local ou distant).

    Implémente le `VectorStore` Protocol de `rag.interfaces`.
    """

    def __init__(
        self,
        collection: str,
        *,
        url: str = "",
        api_key: str | None = None,
        path: Path | str | None = None,
    ) -> None:
        self._collection_name = collection
        self._url = url
        self._api_key = api_key
        self._path = Path(path) if path else None
        self._client: Any | None = None
        self._dim: int | None = None  # inferred on first upsert

    # --- Protocol -----------------------------------------------------------

    def upsert(self, items: list[VectorItem]) -> None:
        if not items:
            return
        from qdrant_client.models import PointStruct

        client = self._ensure_client()
        self._ensure_collection(len(items[0].vector))

        points = [
            PointStruct(
                id=_hex_to_int(item.id),
                vector=item.vector,
                payload={
                    _PAYLOAD_ID_KEY: item.id,
                    "text": item.text,
                    **_flatten_metadata(item.metadata),
                },
            )
            for item in items
        ]
        # Qdrant recommends batch size ≤ 100 for local mode to avoid OOM.
        batch = 64
        for i in range(0, len(points), batch):
            client.upsert(
                collection_name=self._collection_name,
                points=points[i : i + batch],
            )

    def search(
        self,
        vector: list[float],
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        client = self._ensure_client()
        existing = {c.name for c in client.get_collections().collections}
        if self._collection_name not in existing:
            return []

        qdrant_filter = _build_filter(filters) if filters else None

        res = client.query_points(
            collection_name=self._collection_name,
            query=vector,
            limit=k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        hits: list[SearchHit] = []
        for pt in res.points:
            payload = pt.payload or {}
            original_id = str(payload.get(_PAYLOAD_ID_KEY, str(pt.id)))
            text = str(payload.get("text", ""))
            meta = {k: v for k, v in payload.items() if k not in (_PAYLOAD_ID_KEY, "text")}
            hits.append(
                SearchHit(
                    id=original_id,
                    text=text,
                    score=float(pt.score),
                    metadata=meta,
                )
            )
        return hits

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        from qdrant_client.models import PointIdsList

        self._ensure_client().delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=[_hex_to_int(i) for i in ids]),
        )

    def count(self) -> int:
        client = self._ensure_client()
        existing = {c.name for c in client.get_collections().collections}
        if self._collection_name not in existing:
            return 0
        res = client.count(collection_name=self._collection_name)
        return int(res.count)

    def scroll_all(self) -> list[SearchHit]:
        """Retourne tous les points stockés sans vecteurs (pour index BM25).

        Utilise l'API scroll de Qdrant qui pagine automatiquement.
        Non inclus dans le Protocol VectorStore car Qdrant-spécifique.
        """
        client = self._ensure_client()
        existing = {c.name for c in client.get_collections().collections}
        if self._collection_name not in existing:
            return []

        hits: list[SearchHit] = []
        offset = None
        while True:
            results, next_offset = client.scroll(
                collection_name=self._collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for pt in results:
                payload = pt.payload or {}
                original_id = str(payload.get(_PAYLOAD_ID_KEY, str(pt.id)))
                text = str(payload.get("text", ""))
                meta = {k: v for k, v in payload.items() if k not in (_PAYLOAD_ID_KEY, "text")}
                hits.append(SearchHit(id=original_id, text=text, score=0.0, metadata=meta))
            if next_offset is None:
                break
            offset = next_offset

        _log.info("qdrant.scroll_all", n=len(hits), collection=self._collection_name)
        return hits

    # --- Internals ----------------------------------------------------------

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        from qdrant_client import QdrantClient

        if self._path is not None:
            self._path.mkdir(parents=True, exist_ok=True)
            _log.info("opening qdrant local store", path=str(self._path))
            self._client = QdrantClient(path=str(self._path))
        else:
            _log.info("connecting to qdrant server", url=self._url)
            self._client = QdrantClient(
                url=self._url,
                api_key=self._api_key or None,
            )
        return self._client

    def _ensure_collection(self, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams

        client = self._ensure_client()
        existing = {c.name for c in client.get_collections().collections}
        if self._collection_name not in existing:
            _log.info(
                "creating qdrant collection",
                name=self._collection_name,
                dim=dim,
            )
            client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )


def _flatten_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Aplatit les valeurs complexes en primitives (Qdrant payload est JSON)."""
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, str | int | float | bool) or v is None:
            out[k] = v
        else:
            out[k] = json.dumps(v, ensure_ascii=False)
    return out
