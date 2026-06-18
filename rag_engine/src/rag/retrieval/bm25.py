"""BM25Retriever — index lexical en mémoire (rank_bm25).

Pourquoi BM25 à côté du dense : les corpus visés (finance, droit) sont saturés
de sigles techniques (« SCPI », « FCPI », « FCPE », « SFDR », « SRI ») et
d'identifiants (codes ISIN). Un encodeur sémantique a tendance à diluer ces
tokens rares ; un sac-de-mots classique les pondère bien (idf élevé). En
hybride RRF (M3.3), le dense et le BM25 se complètent.

Choix d'implémentation :

- index in-memory au démarrage : on charge l'intégralité des `ChildChunk` une
  fois, on construit `BM25Okapi`. Pour le POC c'est largement suffisant (10⁴
  à 10⁵ chunks tiennent en mémoire). Migration future : un index sur disque
  (BM25 dans Tantivy / Lucene) sans changer l'interface.
- tokenisation maison ultra-simple : lowercase + split sur non-alphanumérique.
  On ne stoppe pas les short tokens (« SRI » ferait 3 lettres) et on ne
  stemise pas (perte d'information sur les acronymes). Tests en M3.2 valident
  qu'un sigle remonte.
- normalisation des scores : on divise par le score max du top-k pour rester
  dans [0, 1] avec « higher = better », comme le `VectorStore`. Le ranking
  n'est pas altéré ; c'est juste pour respecter le contrat de `SearchHit`.
- filtres : on applique un filtre par égalité stricte sur les metadata,
  comme la sémantique minimale promise par le `VectorStore` Protocol.
"""

from __future__ import annotations

import re
from typing import Any, cast

from rag.interfaces import ChildChunk, SearchHit

# Pattern de tokenisation : on capture toute séquence de caractères "mot"
# (lettres unicode + chiffres). Les apostrophes, tirets et ponctuations
# coupent ; les accents sont conservés (français). Les acronymes restent
# entiers car ils ne contiennent rien d'autre que des lettres.
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def load_bm25_corpus(store: Any) -> list[ChildChunk]:
    """Charge tous les chunks d'un `QdrantVectorStore` pour bâtir l'index BM25.

    Vit ici (et non dans l'éval) parce que c'est de la construction de corpus de
    récupération : utilisé par le retrieval hybride et par les scripts de démo.
    """
    from rag.adapters.vector_stores.qdrant_store import QdrantVectorStore
    from rag.interfaces.types import ChunkMetadata

    if not isinstance(store, QdrantVectorStore):
        raise TypeError("Le mode hybride nécessite un QdrantVectorStore.")

    corpus: list[ChildChunk] = []
    for h in store.scroll_all():
        source_file = str(h.metadata.get("source_file", "unknown"))
        page_raw = h.metadata.get("page")
        page = int(page_raw) if isinstance(page_raw, int | float) else None
        parent_id = str(h.metadata.get("parent_id", h.id))
        corpus.append(
            ChildChunk(
                id=h.id,
                parent_id=parent_id,
                text=h.text,
                metadata=ChunkMetadata(source_file=source_file, page=page),
            )
        )
    return corpus


class BM25Retriever:
    """Index BM25 (Okapi) en mémoire sur un corpus de `ChildChunk`.

    Implémente le `Retriever` Protocol de `rag.interfaces`.
    """

    def __init__(self, children: list[ChildChunk]) -> None:
        # On stocke les chunks dans l'ordre d'insertion : l'index BM25
        # référence les documents par position, donc cet ordre doit rester stable.
        self._chunks: list[ChildChunk] = list(children)
        self._index: Any | None = None
        self._tokenized: list[list[str]] = [_tokenize(c.text) for c in self._chunks]

    # --- Protocol -----------------------------------------------------------

    def retrieve(
        self,
        query: str,
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if not self._chunks or k <= 0:
            return []

        index = self._ensure_index()
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # `get_scores` retourne un np.ndarray des scores BM25 pour chaque doc.
        # On le passe en list pour ne pas exposer numpy au reste du code.
        raw_scores = cast(list[float], list(index.get_scores(query_tokens)))

        # On indexe tous les chunks, on applique les filtres, on trie, on
        # tronque à k. Le filtre se fait après le scoring : sur un corpus POC
        # c'est moins coûteux que de maintenir des index par metadata.
        scored: list[tuple[int, float]] = [(i, s) for i, s in enumerate(raw_scores) if s > 0.0]
        if filters:
            scored = [(i, s) for i, s in scored if _matches(self._chunks[i], filters)]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:k]
        if not top:
            return []

        max_score = top[0][1] or 1.0  # éviter la div par 0 (déjà filtré >0, mais robuste)
        return [
            SearchHit(
                id=self._chunks[i].id,
                text=self._chunks[i].text,
                score=float(score / max_score),
                metadata=_meta_to_dict(self._chunks[i]),
            )
            for i, score in top
        ]

    # --- Internals ----------------------------------------------------------

    def _ensure_index(self) -> Any:
        if self._index is not None:
            return self._index
        # Import paresseux : laisse rank_bm25 en optional extra, et garde
        # l'import du module bm25.py gratuit pour les tests qui n'instancient pas.
        from rank_bm25 import BM25Okapi

        # `BM25Okapi` exige une liste non vide de docs non vides ; on a déjà
        # vérifié `self._chunks` côté `retrieve`. Pour les chunks vides après
        # tokenisation, on insère un token sentinelle pour ne pas crasher
        # l'init (ils n'auront aucun score > 0 de toute façon).
        corpus = [tokens or ["__empty__"] for tokens in self._tokenized]
        self._index = BM25Okapi(corpus)
        return self._index


def _matches(chunk: ChildChunk, filters: dict[str, Any]) -> bool:
    """Égalité stricte sur les metadata aplatis, comme le VectorStore."""
    meta = _meta_to_dict(chunk)
    return all(meta.get(k) == v for k, v in filters.items())


def _meta_to_dict(chunk: ChildChunk) -> dict[str, Any]:
    """Aplatit les metadata d'un `ChildChunk` au même format que le VectorStore.

    Pourquoi : pour que les hits émis par BM25 et par le DenseRetriever soient
    interchangeables côté caller (notamment `HybridRetriever` et
    `ParentChildRetriever`). Le `parent_id` est injecté dans les metadata car
    le pipeline d'ingestion fait exactement la même chose (cf.
    `rag.ingestion.pipeline._to_vector_item`).
    """
    meta = chunk.metadata.model_dump(mode="json")
    meta["parent_id"] = chunk.parent_id
    return meta
