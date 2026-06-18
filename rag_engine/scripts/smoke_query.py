#!/usr/bin/env python3
"""Smoke test du pipeline CRAG complet sur les PDFs déjà ingérés.

Identique à un `POST /query` mais en CLI, plus simple à itérer et à
débugger. Pré-requis :
- ingestion terminée (cf. `scripts/smoke_test.py` pour vérifier),
- Ollama up sur `RAG__LLM__OLLAMA__BASE_URL` (défaut: http://localhost:11434),
- modèle pull : `ollama pull mistral:7b-instruct` (ou ce qui est configuré).

Usage :

    python scripts/smoke_query.py                         # 5 questions par défaut
    python scripts/smoke_query.py --ask "Quelle est la définition du vol ?"
    python scripts/smoke_query.py --trace                 # affiche les nœuds traversés
    python scripts/smoke_query.py --max-iterations 1      # désactive le retry CRAG
    python scripts/smoke_query.py --k 2                   # 2 hits → 4 LLM calls au lieu de 8
"""

from __future__ import annotations

import argparse
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import httpx
from rag.config.factory import build_crag_graph_from_settings
from rag.config.settings import load_settings
from rag.interfaces.types import CRAGState

# Questions ciblées sur les 3 corpus. La dernière (« blanquette de veau »)
# DOIT déclencher le fallback `je ne sais pas` — c'est notre test
# anti-hallucination.
DEFAULT_QUESTIONS: list[tuple[str, str]] = [
    ("DPA", "Quelle est la définition du droit pénal des affaires ?"),
    ("Pénal spécial", "Quels sont les éléments constitutifs du vol ?"),
    ("Procédure civ.", "Quelle est la définition de la procédure civile ?"),
    ("Transverse", "Quelle différence entre infraction matérielle et infraction formelle ?"),
    ("Hors-sujet", "Quelle est la recette de la blanquette de veau ?"),
]


def _check_ollama(base_url: str, timeout: float = 3.0) -> str | None:
    """Renvoie None si Ollama répond, sinon un message d'erreur lisible."""
    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return f"Ollama répond {resp.status_code} sur {base_url}"
        return None
    except httpx.HTTPError as exc:
        return f"Ollama injoignable sur {base_url} ({type(exc).__name__}: {exc})"


def _print_answer(question: str, final: Any, elapsed: float) -> None:
    """Affiche la réponse finale de manière compacte."""

    # LangGraph renvoie un dict ou un pydantic selon la version.
    def get(name: str) -> Any:
        if isinstance(final, dict):
            return final.get(name)
        return getattr(final, name, None)

    answer = get("answer")
    fallback = bool(get("fallback_triggered"))
    iteration = int(get("iteration") or 0)

    print(f"\n>>> {question}")
    print(
        f"    (latence : {elapsed:.1f}s, itérations CRAG : {iteration}, "
        f"fallback : {fallback}, grounded : {getattr(answer, 'grounded', None)})"
    )
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
            chunk_id = getattr(c, "chunk_id", "?")
            print(f"      - {src} p.{page}   chunk_id={chunk_id}")


def _trace_run(graph: Any, state: CRAGState) -> Any:
    """Exécute le graphe en stream pour montrer les nœuds traversés."""
    stream_fn = getattr(graph, "stream", None)
    if not callable(stream_fn):
        return graph.invoke(state)

    accumulated: dict[str, Any] = {}
    for update in stream_fn(state):
        if not isinstance(update, dict):
            continue
        for node_name, delta in update.items():
            keys = sorted(list((delta or {}).keys())) if isinstance(delta, dict) else []
            print(f"    · {node_name:<22} updated: {', '.join(keys) or '∅'}")
            if isinstance(delta, dict):
                accumulated.update(delta)
    return accumulated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ask", action="append", help="question custom, répétable")
    parser.add_argument(
        "--max-iterations", type=int, default=2, help="cap de retries CRAG (défaut: 2, comme l'API)"
    )
    parser.add_argument(
        "--trace", action="store_true", help="affiche les nœuds traversés (via graph.stream)"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="nombre de hits à récupérer (écrase RAG__RETRIEVAL__DENSE_K)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    if not (repo_root / "data" / "parents.sqlite").is_file():
        print(
            "ERREUR : data/parents.sqlite introuvable. Lance `python -m rag.ingestion.cli` d'abord.",
            file=sys.stderr,
        )
        return 2

    settings = load_settings()
    print(
        f"== Smoke query (LLM = {settings.llm.provider}: "
        f"{settings.llm.ollama.model if settings.llm.provider == 'ollama' else '?'})"
    )

    # Fail-fast si Ollama n'est pas joignable — l'erreur de httpx au milieu
    # du graphe serait moins lisible.
    if settings.llm.provider == "ollama":
        err = _check_ollama(settings.llm.ollama.base_url)
        if err:
            print(f"ERREUR : {err}", file=sys.stderr)
            print("  → vérifie `ollama serve` et `ollama list`.", file=sys.stderr)
            return 3

    if args.k is not None:
        settings.retrieval.dense_k = args.k
        settings.retrieval.bm25_k = args.k

    print("Compilation du graphe CRAG...", flush=True)
    graph = build_crag_graph_from_settings(settings)

    questions = [("custom", q) for q in args.ask] if args.ask else DEFAULT_QUESTIONS

    for tag, q in questions:
        print(f"\n--- [{tag}]", flush=True)
        state = CRAGState(original_query=q, query=q, max_iterations=args.max_iterations)
        t0 = time.perf_counter()
        try:
            if args.trace:
                print("    Nœuds traversés :")
                final = _trace_run(graph, state)
            else:
                final = graph.invoke(state)
        except Exception as exc:  # — on veut tout afficher pour debug
            print(f"    EXCEPTION : {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        elapsed = time.perf_counter() - t0
        _print_answer(q, final, elapsed)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
