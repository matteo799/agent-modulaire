"""HybridRetriever — fusion de plusieurs retrievers par Reciprocal Rank Fusion.

RRF (Cormack et al., 2009) agrège des rankings indépendants sans avoir besoin
que leurs scores soient comparables :

    score_RRF(d) = Σ_r 1 / (c + rank_r(d))

où `rank_r(d)` est la position 1-indexée de `d` dans les résultats du
retriever `r`, et `c` est une constante (60 par défaut dans la littérature).
On somme uniquement sur les retrievers qui retournent `d` dans leur top-k.

Pourquoi RRF et pas une moyenne de scores : nos retrievers produisent des
échelles incomparables (cosine sim vs BM25 normalisé), et la fusion par rang
est plus robuste aux scores bruyants. C'est aussi ce que recommande la note
d'ingénierie Elastic et le papier original.

L'objet implémente le `Retriever` Protocol → peut être enveloppé par
`ParentChildRetriever` et `RerankingRetriever` sans cas particulier.
"""

from __future__ import annotations

from typing import Any

from rag.interfaces import Retriever, SearchHit


class HybridRetriever:
    """Fusion RRF de plusieurs retrievers.

    Args:
        sources: liste de tuples `(retriever, k_inner)`. Chaque retriever est
            interrogé avec son propre `k_inner` (utile car en pratique on
            veut souvent récupérer plus de candidats côté dense que côté BM25
            ou inversement, cf. `RetrievalSettings.dense_k` / `bm25_k`).
        rrf_constant: la constante `c` ci-dessus. 60 par défaut.
    """

    def __init__(
        self,
        sources: list[tuple[Retriever, int]],
        *,
        rrf_constant: int = 60,
    ) -> None:
        if not sources:
            raise ValueError("HybridRetriever a besoin d'au moins un retriever source")
        if rrf_constant <= 0:
            raise ValueError("rrf_constant doit être > 0")
        self._sources = sources
        self._rrf_constant = rrf_constant

    def retrieve(
        self,
        query: str,
        k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        if k <= 0:
            return []

        # On agrège : id → (score_rrf cumulé, hit représentatif).
        # On garde le premier hit rencontré pour conserver text + metadata
        # (les sous-retrievers sont supposés cohérents sur ces champs).
        aggregated: dict[str, tuple[float, SearchHit]] = {}

        for retriever, k_inner in self._sources:
            hits = retriever.retrieve(query=query, k=k_inner, filters=filters)
            for rank, hit in enumerate(hits, start=1):
                contribution = 1.0 / (self._rrf_constant + rank)
                if hit.id in aggregated:
                    prev_score, prev_hit = aggregated[hit.id]
                    aggregated[hit.id] = (prev_score + contribution, prev_hit)
                else:
                    aggregated[hit.id] = (contribution, hit)

        if not aggregated:
            return []

        # Tri par score RRF décroissant.
        ranked = sorted(aggregated.values(), key=lambda x: x[0], reverse=True)
        top = ranked[:k]

        # Normalisation [0, 1] : on divise par le top pour respecter le contrat
        # « higher = better, scores comparables ». RRF n'est pas naturellement
        # borné, mais le ranking est préservé par la division.
        max_score = top[0][0] or 1.0
        return [
            SearchHit(
                id=hit.id,
                text=hit.text,
                score=score / max_score,
                metadata=hit.metadata,
            )
            for score, hit in top
        ]
