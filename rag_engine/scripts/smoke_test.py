#!/usr/bin/env python3
"""Smoke test du pipeline retrieval sur les PDFs déjà ingérés.

But : vérifier en quelques secondes (sans LLM) que ton ingestion est saine
et que le retrieval ramène des passages plausibles pour des questions
réalistes sur tes 3 corpus (DPA, pénal spécial, procédure civile).

Usage :

    python scripts/smoke_test.py                # toutes les questions
    python scripts/smoke_test.py --k 3           # top-3 au lieu de top-5
    python scripts/smoke_test.py --ask "Quelle est la définition du vol ?"

Sortie : par question, top-k chunks avec source + page + extrait + score.
Pas d'appel LLM, pas besoin qu'Ollama tourne. Si ce script remonte des
extraits qui ont l'air pertinents, ton retrieval marche → tu peux passer
à `make run-api` et tester `/query` avec Ollama.

Si ça plante au chargement de l'embedder (premier run) : c'est BGE-M3
qui se télécharge depuis HuggingFace (~2 Go). Ça prend une fois.
"""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from rag.config.factory import build_retriever
from rag.config.settings import load_settings

# Questions tests — choisies pour piquer chacun des 3 corpus + un cas
# transverse + un cas qui DOIT échouer (hors-sujet) pour voir si la
# stack reste sereine.
DEFAULT_QUESTIONS: list[tuple[str, str]] = [
    # (catégorie, question)
    ("DPA", "Quelle est la définition du droit pénal des affaires ?"),
    ("DPA", "Quelles sont les sources réglementaires du DPA ?"),
    ("Pénal spécial", "Quels sont les éléments constitutifs du vol ?"),
    ("Pénal spécial", "Quelle est l'évolution historique de la pénalisation de l'avortement ?"),
    ("Procédure civ.", "Quelle est la définition de la procédure civile ?"),
    ("Procédure civ.", "Quelles sont les sources de la procédure civile ?"),
    ("Transverse", "Quelle différence entre infraction matérielle et infraction formelle ?"),
    ("Hors-sujet", "Quelle est la recette de la blanquette de veau ?"),
]


def _print_hit(rank: int, hit: object, *, width: int = 78) -> None:
    """Affiche un hit en 4 lignes lisibles."""
    # Accès dynamique pour ne pas importer SearchHit si pas dispo.
    hid = getattr(hit, "id", "?")
    score = float(getattr(hit, "score", 0.0))
    text = str(getattr(hit, "text", ""))
    meta = getattr(hit, "metadata", {}) or {}
    source = meta.get("source_file", "?")
    page = meta.get("page", "?")

    # On tronque le texte à 3 lignes max.
    snippet = textwrap.shorten(
        " ".join(text.split()),
        width=width * 3,
        placeholder="…",
    )
    print(f"  [{rank}] {source} p.{page}   score={score:.3f}   id={hid}")
    for line in textwrap.wrap(snippet, width=width):
        print(f"      {line}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=5, help="top-k (défaut: 5)")
    parser.add_argument(
        "--ask",
        action="append",
        default=None,
        help="question custom (répétable). Remplace la liste par défaut.",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="filtre sur un source_file (ex. dpa.pdf)",
    )
    args = parser.parse_args(argv)

    # Sanity check : on est bien au bon endroit ?
    repo_root = Path(__file__).resolve().parent.parent
    if not (repo_root / "data" / "parents.sqlite").is_file():
        print(
            "ERREUR : data/parents.sqlite introuvable. " "Lance `make ingest` avant ce smoke test.",
            flush=True,
        )
        return 2

    print(f"== Smoke test retrieval (top-{args.k}) ==", flush=True)
    settings = load_settings()
    print(
        f"settings : vector_store={settings.vector_store.provider}, "
        f"embedder={settings.embedder.model}, reranker={settings.reranker.enabled}",
        flush=True,
    )

    retriever = build_retriever(settings)

    questions: list[tuple[str, str]] = (
        [("custom", q) for q in args.ask] if args.ask else DEFAULT_QUESTIONS
    )

    filters: dict[str, str] | None = {"source_file": args.source} if args.source else None

    for tag, q in questions:
        print(f"\n--- [{tag}] {q}")
        hits = retriever.retrieve(query=q, k=args.k, filters=filters)
        if not hits:
            print("  (aucun résultat)")
            continue
        for i, h in enumerate(hits, start=1):
            _print_hit(i, h)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
