"""Adaptateur RAG : branche l'agent sur le package `rag` (moteur rag_engine).

Remplace l'ancien mini-moteur maison. On expose le MÊME contrat qu'avant
(`rag_search` et `list_sources` renvoient des chaînes), si bien que
`agent/tools.py`, le planner et `main.py` n'ont pas à changer.

Sous le capot : stack de récupération réelle du package (Dense bge-m3 →
Parent-Child → reranking bge-reranker), montée paresseusement et mise en
cache. On ne renvoie QUE les passages (pas de génération) : c'est le LLM de
l'agent qui synthétise, exactement comme avec l'ancien `rag_search`.

Rejet du hors-corpus : un score reranker ne sépare pas le hors-sujet de
l'in-corpus sur ces corpus (les deux populations se chevauchent vers ~0,50).
On utilise donc le JUGE DE PERTINENCE LLM du package (prompt `grade_documents`,
labels relevant / ambiguous / irrelevant) : chaque passage récupéré est jugé,
on écarte les `irrelevant`, et si aucun ne subsiste on renvoie « aucun passage ».
C'est ce qui garantit le rejet total d'une question étrangère au dataset
(nécessite donc un LLM dispo — Ollama par défaut).

Corpus interrogé = la collection configurée dans rag_engine/configs
(`vector_store.collection`, défaut `dataset_finance`). Une collection PAR
dataset/projet, jamais combinées : le moteur ne cherche que dans le corpus
du projet courant. Pour basculer (ex. cours de droit), lancer l'agent avec
`RAG__VECTOR_STORE__COLLECTION=dataset_droit`.
"""

from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Any

# Racine du moteur rapatrié : ses configs et data sont en chemins relatifs
# (./data, ./configs) pensés pour un cwd = racine du projet. L'agent, lui,
# tourne depuis Harness/ : on force donc des chemins absolus.
RAG_ENGINE_ROOT = Path(__file__).resolve().parent.parent / "rag_engine"

NO_MATCH_MESSAGE = (
    "Aucun passage pertinent trouvé dans les documents pour cette recherche : "
    "le sujet ne semble pas couvert par les documents disponibles."
)

# Nombre de candidats récupérés puis soumis au juge LLM (borne le coût : 1 appel
# LLM par candidat). On en garde au plus `top_k` après filtrage.
GRADE_CANDIDATES = int(os.getenv("RAG__RAG_SEARCH_CANDIDATES", "8"))

_LABEL_RE = re.compile(r'"label"\s*:\s*"(relevant|ambiguous|irrelevant)"', re.IGNORECASE)

_retriever: Any = None
_settings: Any = None
_llm: Any = None


def _bootstrap() -> tuple[Any, Any]:
    """Construit (paresseusement) settings + retriever, puis les met en cache.

    Le premier appel charge les modèles d'embedding/reranking (quelques
    secondes) ; les suivants réutilisent l'instance.
    """
    global _retriever, _settings
    if _retriever is None:
        from rag.config.factory import build_retriever
        from rag.config.settings import load_settings

        settings = load_settings(configs_dir=RAG_ENGINE_ROOT / "configs")
        # Réancre le chemin relatif (./data) sur l'emplacement réel du package.
        settings.data_dir = RAG_ENGINE_ROOT / "data"

        _settings = settings
        _retriever = build_retriever(settings)
    return _retriever, _settings


def _get_llm() -> Any:
    """Construit (paresseusement) le client LLM du juge de pertinence."""
    global _llm
    if _llm is None:
        from rag.config.factory import build_llm

        _, settings = _bootstrap()
        _llm = build_llm(settings)
    return _llm


def _is_relevant(llm: Any, query: str, hit: Any) -> bool:
    """Le passage est-il pertinent pour la question ? (juge LLM `grade_documents`)

    On rejette uniquement le label `irrelevant`. En cas d'échec du LLM, on
    laisse passer (dégradation gracieuse plutôt que de masquer un vrai passage).
    """
    from rag.prompts import render

    try:
        raw = llm.generate(render("grade_documents", query=query, doc=hit.text), max_tokens=128)
    except Exception:
        return True
    match = _LABEL_RE.search(raw or "")
    label = match.group(1).lower() if match else "ambiguous"
    return label != "irrelevant"


def rag_search(query: str, top_k: int = 3, source: str = "") -> str:
    """Recherche les passages pertinents. `source` (optionnel) restreint à un
    document (ex. un ISIN). Renvoie un message clair si rien n'est pertinent."""
    retriever, _ = _bootstrap()
    k = max(int(top_k), 3)

    # On sur-récupère (filtrage par source + marge pour le juge LLM).
    fetch = k * 4 if source else GRADE_CANDIDATES
    hits = retriever.retrieve(query, fetch)

    if source:
        needle = source.lower()
        hits = [h for h in hits if needle in str(h.metadata.get("source_file", "")).lower()]

    # Juge de pertinence LLM : on écarte les passages hors-sujet. C'est CE filtre
    # (et non un seuil numérique) qui garantit le rejet d'une question étrangère
    # au dataset.
    llm = _get_llm()
    relevant = [h for h in hits[:GRADE_CANDIDATES] if _is_relevant(llm, query, h)]

    relevant = relevant[:k]
    if not relevant:
        return NO_MATCH_MESSAGE

    return "\n\n".join(f"[{h.metadata.get('source_file', '?')}]\n{h.text}" for h in relevant)


def list_sources() -> str:
    """Liste les documents indexés dans le corpus actif (collection configurée)."""
    retriever, settings = _bootstrap()
    sources = _distinct_sources(retriever, settings)
    if not sources:
        return "Aucun document indexé dans le corpus."
    return "Documents disponibles :\n" + "\n".join(f"- {s}" for s in sources)


def count_sources() -> int:
    """Nombre de documents distincts indexés dans le corpus actif (compté côté code)."""
    retriever, settings = _bootstrap()
    return len(_distinct_sources(retriever, settings))


def _find_vector_store(retriever: Any) -> Any:
    """Descend la chaîne `_inner` du retriever jusqu'au VectorStore sous-jacent."""
    node = retriever
    for _ in range(10):  # garde-fou anti-boucle
        if hasattr(node, "_vector_store"):
            return node._vector_store
        if hasattr(node, "_inner"):
            node = node._inner
            continue
        break
    return None


def _distinct_sources(retriever: Any, settings: Any) -> list[str]:
    """source_file distincts de la collection active.

    On réutilise le client Qdrant DÉJÀ ouvert par le retriever (le store local
    n'autorise qu'un seul accès : ouvrir un 2e client le verrouillerait) et on
    scrolle le payload aplati (clé `source_file`). En cas d'échec, repli sur
    l'inventaire des parents SQLite (qui, lui, couvre tous les corpus).
    """
    try:
        store = _find_vector_store(retriever)
        if store is not None and hasattr(store, "_ensure_client"):
            client = store._ensure_client()
            collection = store._collection_name
            found: set[str] = set()
            offset = None
            while True:
                points, offset = client.scroll(
                    collection,
                    limit=256,
                    with_payload=["source_file"],
                    with_vectors=False,
                    offset=offset,
                )
                for p in points:
                    src = (p.payload or {}).get("source_file")
                    if src:
                        found.add(str(src))
                if offset is None:
                    break
            if found:
                return sorted(found)
    except Exception:
        pass

    # Repli : parents SQLite (peut couvrir plusieurs corpus).
    db = settings.data_dir / "parents.sqlite"
    if not db.exists():
        return []
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT DISTINCT json_extract(metadata, '$.source_file') FROM parents"
        ).fetchall()
    finally:
        con.close()
    return sorted(r[0] for r in rows if r[0])
