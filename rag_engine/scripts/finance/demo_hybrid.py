#!/usr/bin/env python3
"""Démo finance : Hybrid retrieval, SANS reranker, SANS CRAG.

Stack montée :
    Hybrid(Dense + BM25 via RRF) → ParentChild → (pas de reranker)
    Graphe RAG simple : retrieve → prepare_context → generate → ground_check
    LLM : qwen/qwen3.5-9b via LM Studio (Tailscale)

Usage :
    python scripts/finance/demo_hybrid.py

Pré-requis : corpus finance ingéré dans Qdrant + data/parents.sqlite,
LM Studio joignable avec le modèle chargé.
"""

from __future__ import annotations

import textwrap
import time
from typing import Any

from rag.config.factory import build_crag_graph_from_settings
from rag.config.settings import load_settings
from rag.retrieval.bm25 import load_bm25_corpus
from rag.config.factory import build_vector_store
from rag.interfaces.types import CRAGState

# 10 questions extraites du golden set finance (SCPI / FCPI / FCPE)
# + 1 hors-corpus (n°10) pour observer le comportement anti-hallucination
# SANS la boucle CRAG (seul le ground_check reste actif).
QUESTIONS: list[tuple[str, str]] = [
    ("SCPI", "Quelle est la politique de distribution des revenus du produit SCPI ?"),
    ("SCPI", "Combien de temps est-il recommandé de conserver une part de SCPI, "
             "et peut-on retirer ses fonds de façon anticipée ?"),
    ("FCPI", "Qui a agréé le FCPI Amundi Avenir Innovation et sous quel numéro ?"),
    ("FCPI", "Quel avantage fiscal offre la souscription à un FCPI éligible ?"),
    ("FCPI", "Pendant combien d'années les parts d'un FCPI sont-elles bloquées ?"),
    ("Frais", "Comment est calculée la commission de gestion annuelle du fonds ?"),
    ("Risque", "En quoi consiste le risque de liquidité pour un fonds commun de placement ?"),
    ("Rachats", "Comment fonctionne le mécanisme de plafonnement des rachats (Gates) ?"),
    ("FCPE", "Quel est le régime fiscal applicable aux plus-values et revenus du FCPE "
             "pour un investisseur particulier ?"),
    ("Hors-corpus", "Quel est le taux de TVA applicable aux loyers d'habitation en France ?"),
]


def _print_answer(question: str, final: Any, elapsed: float) -> None:
    def get(name: str) -> Any:
        if isinstance(final, dict):
            return final.get(name)
        return getattr(final, name, None)

    answer = get("answer")
    fallback = bool(get("fallback_triggered"))
    grounded = getattr(answer, "grounded", None) if answer else None

    print(f"\n>>> {question}")
    print(f"    (latence : {elapsed:.1f}s, fallback : {fallback}, grounded : {grounded})")
    if answer is None:
        print("    [pas de réponse]")
        return
    body = textwrap.fill(
        " ".join((answer.text or "").split()),
        width=92,
        initial_indent="    ",
        subsequent_indent="    ",
    )
    print(body)
    citations = getattr(answer, "citations", []) or []
    if citations:
        print("    Citations :")
        for c in citations:
            page = getattr(c, "page", None)
            src = getattr(c, "source_file", "?")
            print(f"      - {src} p.{page}")


def main() -> int:
    settings = load_settings()
    print(
        f"== Démo finance | retrieval=hybrid={settings.retrieval.hybrid_enabled} "
        f"reranker={settings.reranker.enabled} crag={settings.crag.enabled}"
    )
    print(f"== LLM = {settings.llm.provider}: {settings.llm.lmstudio.model}")

    # Charge le corpus children depuis Qdrant pour alimenter l'index BM25
    # (requis par le mode hybride).
    vector_store = build_vector_store(settings)
    print("Chargement du corpus BM25 depuis Qdrant...", flush=True)
    bm25_corpus = load_bm25_corpus(vector_store)
    print(f"  → {len(bm25_corpus)} children chargés.", flush=True)

    # Qdrant local pose un lock exclusif sur le dossier. On relâche ce client
    # avant que le factory n'en ouvre un autre pour le DenseRetriever, sinon
    # « Storage folder already accessed by another instance ».
    client = getattr(vector_store, "_client", None)
    if client is not None:
        client.close()
        vector_store._client = None

    print("Compilation du graphe RAG simple (sans CRAG)...", flush=True)
    graph = build_crag_graph_from_settings(settings, bm25_corpus=bm25_corpus)

    for tag, q in QUESTIONS:
        print(f"\n--- [{tag}]", flush=True)
        state = CRAGState(original_query=q, query=q, max_iterations=1)
        t0 = time.perf_counter()
        try:
            final = graph.invoke(state)
        except Exception as exc:  # on veut tout afficher pour debug
            import traceback

            print(f"    EXCEPTION : {type(exc).__name__}: {exc}")
            traceback.print_exc()
            continue
        elapsed = time.perf_counter() - t0
        _print_answer(q, final, elapsed)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
