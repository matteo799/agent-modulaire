"""Métriques retrieval (M6.2) : hit@k, recall@k, MRR.

Définitions (toutes calculées à partir des chunk_ids retournés par le
retriever, comparés à `expected_chunk_ids` du golden) :

- **hit@k** : 1 si AU MOINS UN des expected_chunk_ids apparaît dans les
  top-k résultats, 0 sinon. On agrège ensuite en moyenne sur les items.
- **recall@k** : proportion des expected_chunk_ids présents dans le top-k.
  Si `expected_chunk_ids` est vide (question out-of-domain), on retourne
  1.0 par convention : il n'y avait rien à trouver, mission accomplie.
- **MRR** (Mean Reciprocal Rank) : moyenne de 1 / rank du premier hit
  pertinent (1-indexé). Si aucun expected n'apparaît dans la liste, on
  contribue avec 0.

Ces métriques sont indépendantes du LLM → tests rapides + déterministes,
exécutables en CI sans Ollama.
"""

from __future__ import annotations

import time

from pydantic import BaseModel, Field
from rag.interfaces import Retriever, SearchHit

from .golden import GoldenItem, GoldenSet


class ItemRetrievalResult(BaseModel):
    """Détail par item — utile pour le rapport et le debugging."""

    item_id: str
    hit_at_k: int  # 0 ou 1
    recall_at_k: float
    reciprocal_rank: float  # 1 / rank, 0 si pas trouvé
    latency_ms: float = 0.0  # durée du retrieve() en millisecondes
    retrieved_ids: list[str] = Field(default_factory=list)
    retrieved_labels: list[str] = Field(default_factory=list)  # source_file p.N


class RetrievalReport(BaseModel):
    """Résumé agrégé sur tout le golden set."""

    k: int
    n_items: int
    hit_rate: float
    mean_recall: float
    mrr: float
    mean_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    per_item: list[ItemRetrievalResult] = Field(default_factory=list)


def _hit_label(hit: SearchHit) -> str:
    src = hit.metadata.get("source_file", "?")
    page = hit.metadata.get("page", "?")
    return f"{src} p.{page}"


def _evaluate_one(
    item: GoldenItem,
    hits: list[SearchHit],
    k: int,
    latency_ms: float,
) -> ItemRetrievalResult:
    all_hits = hits[:k]
    retrieved_ids = [h.id for h in all_hits]
    retrieved_labels = [_hit_label(h) for h in all_hits]
    expected = set(item.expected_chunk_ids)

    if not expected:
        # Question out-of-domain : par convention le retriever fait son job
        # quel que soit ce qu'il retourne (le CRAG décidera de tomber en
        # fallback). On marque hit=1 et recall=1.0 pour ne pas pénaliser.
        return ItemRetrievalResult(
            item_id=item.id,
            hit_at_k=1,
            recall_at_k=1.0,
            reciprocal_rank=1.0,
            latency_ms=latency_ms,
            retrieved_ids=retrieved_ids,
            retrieved_labels=retrieved_labels,
        )

    matched = [i for i, rid in enumerate(retrieved_ids, start=1) if rid in expected]
    hit = 1 if matched else 0
    recall = len(set(retrieved_ids) & expected) / len(expected)
    rr = 1.0 / matched[0] if matched else 0.0
    return ItemRetrievalResult(
        item_id=item.id,
        hit_at_k=hit,
        recall_at_k=recall,
        reciprocal_rank=rr,
        latency_ms=latency_ms,
        retrieved_ids=retrieved_ids,
        retrieved_labels=retrieved_labels,
    )


def evaluate_retrieval(
    retriever: Retriever,
    golden: GoldenSet,
    *,
    k: int = 5,
) -> RetrievalReport:
    """Lance le retrieval sur chaque item du golden et agrège les métriques.

    Le retriever n'a PAS besoin d'être le retriever « final » du graphe
    CRAG. C'est utile pour comparer plusieurs stratégies (dense pur,
    hybrid, parent-child, post-rerank…) sur le même golden.
    """
    per_item: list[ItemRetrievalResult] = []
    for item in golden.items:
        t0 = time.perf_counter()
        hits = retriever.retrieve(query=item.question, k=k)
        latency_ms = (time.perf_counter() - t0) * 1000
        per_item.append(_evaluate_one(item, hits, k, latency_ms))

    n = len(per_item)
    if n == 0:
        return RetrievalReport(k=k, n_items=0, hit_rate=0.0, mean_recall=0.0, mrr=0.0)

    latencies = sorted(r.latency_ms for r in per_item)
    p50_idx = max(0, int(n * 0.50) - 1)
    p95_idx = max(0, int(n * 0.95) - 1)

    return RetrievalReport(
        k=k,
        n_items=n,
        hit_rate=sum(r.hit_at_k for r in per_item) / n,
        mean_recall=sum(r.recall_at_k for r in per_item) / n,
        mrr=sum(r.reciprocal_rank for r in per_item) / n,
        mean_latency_ms=sum(latencies) / n,
        p50_latency_ms=latencies[p50_idx],
        p95_latency_ms=latencies[p95_idx],
        max_latency_ms=latencies[-1],
        per_item=per_item,
    )


__all__ = [
    "ItemRetrievalResult",
    "RetrievalReport",
    "evaluate_retrieval",
]
