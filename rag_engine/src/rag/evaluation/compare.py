"""Eval comparatif — toutes les stacks retrieval Qdrant.

Lance evaluate_retrieval sur 4 configurations et produit un tableau comparatif :

  1. dense            — DenseRetriever + ParentChild
  2. dense+reranker   — DenseRetriever + ParentChild + BGEReranker
  3. hybrid           — HybridRetriever(Dense+BM25) + ParentChild
  4. hybrid+reranker  — HybridRetriever(Dense+BM25) + ParentChild + BGEReranker

Note sur CRAG vs RAG simple : les deux topologies partagent exactement le
même retriever. CRAG n'affecte que la génération (grade, rewrite, generate),
pas le retrieval. Ces métriques seraient donc identiques dans les deux cas.
Pour évaluer CRAG (faithfulness, answer relevancy), il faut Ollama up + eval-full.

Usage :
    python -m rag.evaluation.compare --config configs/eval.yaml [--output compare_report.md]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from rag.adapters.vector_stores.qdrant_store import QdrantVectorStore
from rag.config.factory import build_doc_store, build_embedder, build_vector_store
from rag.config.settings import load_settings
from rag.evaluation.golden import GoldenSet, load_golden_set
from rag.evaluation.retrieval_metrics import RetrievalReport, evaluate_retrieval
from rag.evaluation.run import load_eval_config
from rag.interfaces import ChildChunk, Retriever
from rag.interfaces.types import ChunkMetadata
from rag.utils.logging import get_logger

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Corpus BM25 — chargé depuis Qdrant via scroll
# ---------------------------------------------------------------------------


def _load_bm25_corpus(store: Any) -> list[ChildChunk]:
    """Charge tous les chunks stockés dans Qdrant pour l'index BM25."""
    if not isinstance(store, QdrantVectorStore):
        raise TypeError("Le mode hybride nécessite un QdrantVectorStore.")

    hits = store.scroll_all()
    corpus: list[ChildChunk] = []
    for h in hits:
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
    _log.info("bm25.corpus_loaded", n=len(corpus))
    return corpus


# ---------------------------------------------------------------------------
# Construction des stacks retrieval
# ---------------------------------------------------------------------------


def _build_stacks(settings: Any) -> list[tuple[str, Retriever]]:
    """Construit les 4 stacks et retourne (nom, retriever)."""
    from typing import cast

    from rag.interfaces import Retriever
    from rag.retrieval.dense import DenseRetriever
    from rag.retrieval.hybrid import HybridRetriever
    from rag.retrieval.parent_child import ParentChildRetriever
    from rag.retrieval.reranking import RerankingRetriever

    embedder = build_embedder(settings)
    vector_store = build_vector_store(settings)
    doc_store = build_doc_store(settings)

    dense = DenseRetriever(embedder=embedder, vector_store=vector_store)
    pc_dense = cast(Retriever, ParentChildRetriever(inner=dense, doc_store=doc_store))

    bm25_corpus = _load_bm25_corpus(vector_store)

    bm25_k = settings.retrieval.bm25_k
    dense_k = settings.retrieval.dense_k
    rrf = settings.retrieval.hybrid_rrf_constant

    from rag.retrieval.bm25 import BM25Retriever

    bm25 = BM25Retriever(bm25_corpus)
    hybrid = cast(
        Retriever,
        HybridRetriever(
            sources=[(dense, dense_k), (bm25, bm25_k)],
            rrf_constant=rrf,
        ),
    )
    pc_hybrid = cast(Retriever, ParentChildRetriever(inner=hybrid, doc_store=doc_store))

    stacks: list[tuple[str, Retriever]] = [
        ("dense", pc_dense),
        ("hybrid", pc_hybrid),
    ]

    if settings.reranker.enabled:
        from rag.adapters.rerankers.bge_reranker import BGEReranker
        from rag.retrieval.reranking import RerankingRetriever

        _log.info("reranker.loading", model=settings.reranker.model)
        reranker = BGEReranker(
            model=settings.reranker.model,
            device=settings.reranker.device,
            batch_size=settings.reranker.batch_size,
        )
        stacks += [
            (
                "dense+reranker",
                cast(
                    Retriever,
                    RerankingRetriever(
                        inner=pc_dense,
                        reranker=reranker,
                        candidate_k=dense_k,
                    ),
                ),
            ),
            (
                "hybrid+reranker",
                cast(
                    Retriever,
                    RerankingRetriever(
                        inner=pc_hybrid,
                        reranker=reranker,
                        candidate_k=dense_k,
                    ),
                ),
            ),
        ]
    else:
        _log.info("reranker.disabled", reason="reranker.enabled=false — stacks +reranker ignorées")

    return stacks


# ---------------------------------------------------------------------------
# Rapport comparatif Markdown
# ---------------------------------------------------------------------------


def _fmt_pct(v: float) -> str:
    return f"{v * 100:5.1f}%"


_RERANKER_SKIPPED_NOTE = """\
> **Configs `+reranker` non exécutées — contrainte matérielle**
>
> La machine de développement est un MacBook Air M1 8 Go de RAM.
> BGE-M3 (embedder, ~1,9 Go) et BGE-reranker-v2-m3 (~1,1 Go) chargés
> simultanément épuisent le memory pool unifié MPS, provoquant des OOM
> ou des temps de chargement de plusieurs minutes en mode CPU.
> Pour exécuter les stacks `+reranker`, utiliser une machine avec au
> moins 16 Go de RAM ou un GPU dédié (CUDA), et passer :
>     `RAG__RERANKER__ENABLED=true python -m rag.evaluation.compare --config configs/eval.yaml`
"""


def _build_compare_report(
    golden: GoldenSet,
    results: dict[str, RetrievalReport],
    reranker_skipped: bool = False,
) -> str:
    lines: list[str] = [
        "# Eval comparatif — stacks retrieval Qdrant",
        "",
        f"Golden set : `{golden.version}` — {len(golden.items)} questions",
        "",
        "> **Note CRAG** : CRAG vs RAG simple partagent le même retriever et",
        "> donneraient des métriques retrieval **identiques**. Pour évaluer la",
        "> qualité de génération (faithfulness, answer relevancy), activer `ragas.enabled`",
        "> dans la config d'éval et relancer `python -m rag.evaluation.run` avec Ollama up.",
        "",
    ]

    if reranker_skipped:
        lines += [_RERANKER_SKIPPED_NOTE, ""]

    lines += [
        "## Résumé",
        "",
        "| Config | hit@k | recall | MRR | moy. | p50 | p95 | max |",
        "|---|:---:|:---:|:---:|---:|---:|---:|---:|",
    ]

    for name, r in results.items():
        lines.append(
            f"| {name} "
            f"| {_fmt_pct(r.hit_rate)} "
            f"| {_fmt_pct(r.mean_recall)} "
            f"| {r.mrr:.3f} "
            f"| {r.mean_latency_ms:.0f} ms "
            f"| {r.p50_latency_ms:.0f} ms "
            f"| {r.p95_latency_ms:.0f} ms "
            f"| {r.max_latency_ms:.0f} ms |"
        )

    lines.append("")

    # Tableau détaillé par config
    for name, r in results.items():
        lines += [
            f"## {name}",
            "",
            f"- hit@k         : {_fmt_pct(r.hit_rate)}",
            f"- mean_recall   : {_fmt_pct(r.mean_recall)}",
            f"- MRR           : {r.mrr:.3f}",
            f"- latence moy.  : {r.mean_latency_ms:.0f} ms",
            f"- latence p50   : {r.p50_latency_ms:.0f} ms",
            f"- latence p95   : {r.p95_latency_ms:.0f} ms",
            f"- latence max   : {r.max_latency_ms:.0f} ms",
            "",
        ]

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_compare(config_path: str | Path) -> str:
    cfg = load_eval_config(config_path)
    settings = load_settings()

    golden: GoldenSet = load_golden_set(cfg.golden_set)
    k = cfg.retrieval.k

    stacks = _build_stacks(settings)

    results: dict[str, RetrievalReport] = {}
    for name, retriever in stacks:
        _log.info("compare.evaluating", config=name)
        results[name] = evaluate_retrieval(retriever, golden, k=k)

    reranker_skipped = not settings.reranker.enabled
    return _build_compare_report(golden, results, reranker_skipped=reranker_skipped)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rag.evaluation.compare")
    parser.add_argument("--config", default="configs/eval.yaml")
    parser.add_argument("--output", default="compare_report.md")
    args = parser.parse_args(argv)

    md = run_compare(args.config)
    Path(args.output).write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
