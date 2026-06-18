"""DenseRetriever — composition Embedder + VectorStore.

Le retriever le plus simple : on embed la requête, on interroge le VectorStore,
on retourne les `SearchHit` tels quels (le VectorStore les a déjà normalisés en
similarité [0, 1] via son adapter).

Implémente le `Retriever` Protocol de `rag.interfaces`. Composé uniquement
d'objets typés par leurs Protocols → testable sans aucune dépendance ML
(cf. tests qui passent des fakes).
"""

from __future__ import annotations

from typing import Any

from rag.interfaces import Embedder, SearchHit, VectorStore


class DenseRetriever:
    """Retriever dense pur : Embedder → VectorStore.search.

    Pourquoi un objet plutôt qu'une fonction : on veut pouvoir l'injecter dans
    `HybridRetriever`, `ParentChildRetriever`, `RerankingRetriever` via le
    Protocol `Retriever`. Une fonction libre romprait cette uniformité.
    """

    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def retrieve(
        self,
        query: str,
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        # `embed` attend une liste — on n'embed qu'un seul texte par requête.
        vectors = self._embedder.embed([query])
        if not vectors:
            # Garde-fou : un Embedder qui renvoie [] sur [query] est cassé,
            # mais on ne va pas faire planter le pipeline pour ça.
            return []
        return self._vector_store.search(vector=vectors[0], k=k, filters=filters)
