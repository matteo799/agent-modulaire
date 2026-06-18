"""RerankingRetriever — wrap un retriever et applique un Reranker en sortie.

Pattern classique : on récupère un top-N « large » (N = 20) via le retriever
interne (hybride, parent-child, peu importe), puis on rerank ce top-N et on
ne garde que les `top_k` finaux. Le reranker (cross-encoder) ordonne mieux
mais coûte cher → on l'applique sur un petit ensemble.

L'objet implémente `Retriever`, donc se compose comme les autres : on peut
le mettre en bout de chaîne ou en milieu, mais en pratique c'est toujours
la dernière étape avant la génération.
"""

from __future__ import annotations

from typing import Any

from rag.interfaces import Reranker, Retriever, SearchHit


class RerankingRetriever:
    """Retriever interne → reranker → top_k final.

    Args:
        inner: retriever qui produit les candidats à reclasser.
        reranker: cross-encoder qui rescort les hits.
        candidate_k: nombre de candidats demandés à l'inner retriever AVANT
            rerank. Doit être >= au `k` final demandé en `retrieve`. 20 par
            défaut, valeur classique pour un BGE reranker.
    """

    def __init__(
        self,
        inner: Retriever,
        reranker: Reranker,
        *,
        candidate_k: int = 20,
    ) -> None:
        if candidate_k <= 0:
            raise ValueError("candidate_k doit être > 0")
        self._inner = inner
        self._reranker = reranker
        self._candidate_k = candidate_k

    def retrieve(
        self,
        query: str,
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if k <= 0:
            return []
        # On élargit la fenêtre côté inner pour donner du grain au reranker.
        # Si l'appelant demande déjà plus que `candidate_k`, on respecte sa
        # demande : pas de raison de cacher des résultats.
        inner_k = max(self._candidate_k, k)
        candidates = self._inner.retrieve(query=query, k=inner_k, filters=filters)
        if not candidates:
            return []
        return self._reranker.rerank(query=query, hits=candidates, top_k=k)
