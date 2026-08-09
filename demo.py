#!/usr/bin/env python3
"""Démo client — le parcours COMPLET de l'Agent modulaire sur 3 questions du dataset finance.

Montre, étape par étape, ce que fait le produit quand on lui pose une question :

  1. PLANIFICATION — l'agent décompose la tâche (LLM Claude).
  2. RÉCUPÉRATION  — le moteur RAG modulaire :
        dense (BGE-M3) → parent-child → RERANKER (top k=6) → génération ancrée
        → ground_check (anti-hallucination) → citations [source:page]
  3. SYNTHÈSE      — l'agent rédige une réponse client, citée et vérifiée.

Config : collection `dataset_finance`, reranker ON (k=6, MPS), CRAG off (latence).
Lancement :  python demo.py
"""
from __future__ import annotations

import os

# Trois modes (raccourcis) :
#   (défaut)        → tout en local : dense bge-m3 + reranker bge (in-process).
#   DEMO_API=1      → tout via API : embeddings bge-m3 servis par API (Ollama par
#                     défaut) + Claude reranke + Claude génère. Sémantique, 3/3.
#   DEMO_ALL_API=1  → 100 % sans aucun modèle : BM25 lexical (mots-clés) + Claude.
ALL_API = os.environ.get("DEMO_ALL_API") == "1"
API = os.environ.get("DEMO_API") == "1"

# --- Config de la démo (AVANT tout import du moteur, pour que les settings la voient) ---
os.environ.setdefault("RAG__VECTOR_STORE__COLLECTION", "dataset_finance")
os.environ.setdefault("RAG__RERANKER__ENABLED", "true")
if API:
    # Embeddings via API (Ollama local par défaut ; pour du cloud, surcharger
    # RAG__EMBEDDER__BASE_URL/MODEL/API_KEY) + reranking par Claude.
    os.environ.setdefault("RAG__EMBEDDER__PROVIDER", "openai")
    os.environ.setdefault("RAG__EMBEDDER__BASE_URL", "http://localhost:11434/v1")
    os.environ.setdefault("RAG__EMBEDDER__MODEL", "bge-m3")
    os.environ.setdefault("RAG__EMBEDDER__API_KEY", "ollama")
    os.environ.setdefault("RAG__RERANKER__PROVIDER", "llm")
elif ALL_API:
    os.environ.setdefault("RAG__RERANKER__PROVIDER", "llm")  # Claude reranke (pas de modèle local)
else:
    os.environ.setdefault("RAG__RERANKER__DEVICE", "mps")    # GPU Apple (rapide ; CPU sinon)
# CRAG désactivé pour la latence (la boucle corrective enchaîne 6 jugements LLM
# par passage). On garde RAG + reranker + vérification d'ancrage (ground_check).

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
RAG_ENGINE = ROOT / "rag_engine"

# k = nombre de passages FINAUX après reranking (rerankés depuis le pool dense).
K = 6

# Étiquette de la chaîne de récupération, calculée dans main() selon les providers.
_RETRIEVE_CHAIN = "retrieval"

# Questions choisies (sondées : passages réellement récupérés, sur le corpus finance).
QUESTIONS = [
    "Quels objectifs de gestion et stratégies d'investissement les fonds mettent-ils en œuvre ?",
    "Quels frais de gestion et commissions s'appliquent aux fonds ?",
    "Qui gère les fonds (société de gestion) et par quelle autorité sont-ils agréés ?",
]

# ── petit habillage terminal (sans dépendance) ───────────────────────────────
C = {
    "h": "\033[1;36m", "g": "\033[1;32m", "y": "\033[33m", "r": "\033[31m",
    "d": "\033[2m", "b": "\033[1m", "x": "\033[0m", "cy": "\033[36m",
}


def rule(char: str = "─", n: int = 78) -> str:
    return C["d"] + char * n + C["x"]


def stage(num: str, title: str) -> None:
    print(f"\n{C['h']}┌{'─' * 76}┐{C['x']}")
    print(f"{C['h']}│ {num}  {title:<71}│{C['x']}")
    print(f"{C['h']}└{'─' * 76}┘{C['x']}")


def get(obj, key, default=None):
    """Accès uniforme dict OU pydantic."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def short(text: str, n: int = 150) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n] + "…"


# ── narration d'un nœud CRAG ─────────────────────────────────────────────────
_LABEL_STYLE = {"relevant": ("g", "✓ pertinent"),
                "ambiguous": ("y", "~ ambigu"),
                "irrelevant": ("r", "✗ hors-sujet")}


def _lat(dt: float) -> str:
    """Étiquette de latence pour une étape (mise en évidence si > 5 s)."""
    col = C["y"] if dt >= 5 else C["d"]
    return f"  {col}⏱ {dt:.1f}s{C['x']}"


def narrate_node(node: str, update, dt: float) -> None:
    if node == "retrieve":
        hits = get(update, "hits", []) or []
        print(f"   {C['cy']}● retrieve{C['x']} — {_RETRIEVE_CHAIN} "
              f"{C['b']}(top {len(hits)}){C['x']}{_lat(dt)}")
        for i, h in enumerate(hits, 1):
            src = get(get(h, "metadata", {}) or {}, "source_file", "?")
            page = get(get(h, "metadata", {}) or {}, "page", None)
            loc = f"{src}" + (f" p.{page}" if page is not None else "")
            print(f"      {i}. {C['d']}[score {float(get(h, 'score', 0)):.3f}]{C['x']} "
                  f"{C['cy']}{loc}{C['x']}  {C['d']}{short(get(h, 'text', ''), 90)}{C['x']}")
    elif node == "grade_and_refine":
        graded = get(update, "graded_hits", []) or []
        counts: dict[str, int] = {}
        for gh in graded:
            lab = str(get(get(gh, "label", ""), "value", get(gh, "label", "")))
            counts[lab] = counts.get(lab, 0) + 1
        parts = []
        for lab, (col, txt) in _LABEL_STYLE.items():
            if counts.get(lab):
                parts.append(f"{C[col]}{counts[lab]} {txt}{C['x']}")
        print(f"   {C['cy']}● grade{C['x']} — le LLM juge chaque passage : "
              + "  ".join(parts or [f"{C['d']}(aucun){C['x']}"]) + _lat(dt))
    elif node == "prepare_context":
        n = len(get(update, "refined_chunks", []) or [])
        print(f"   {C['cy']}● contexte{C['x']} — {n} passages transmis au générateur{_lat(dt)}")
    elif node == "decide":
        dec = str(get(get(update, "decision", ""), "value", get(update, "decision", "")))
        print(f"   {C['cy']}● decide{C['x']} — décision corrective : {C['b']}{dec}{C['x']}{_lat(dt)}")
    elif node == "rewrite_query":
        print(f"   {C['y']}● rewrite{C['x']} — passages insuffisants → reformulation et nouveau tour{_lat(dt)}")
    elif node == "generate":
        print(f"   {C['cy']}● generate{C['x']} — rédaction ancrée sur les passages retenus{_lat(dt)}")
    elif node == "ground_check":
        ans = get(update, "answer", None)
        grounded = get(ans, "grounded", None) if ans else None
        tag = (f"{C['g']}✓ ancrée (grounded){C['x']}" if grounded
               else f"{C['r']}⚠ non ancrée{C['x']}")
        print(f"   {C['cy']}● ground_check{C['x']} — vérification anti-hallucination : {tag}{_lat(dt)}")
    elif node == "fallback_no_answer":
        print(f"   {C['r']}● fallback{C['x']} — hors corpus : le système refuse d'inventer{_lat(dt)}")


def main() -> int:
    global _RETRIEVE_CHAIN

    from rag.config.factory import build_llm, build_retriever
    from rag.config.settings import load_settings
    from rag.graph.builder import build_simple_rag_graph
    from rag.interfaces.types import CRAGState

    from agent import llm
    from agent.planner import make_plan

    settings = load_settings(configs_dir=RAG_ENGINE / "configs")
    settings.data_dir = RAG_ENGINE / "data"  # chemins absolus (cwd = racine du dépôt)

    # Étiquettes dérivées des providers réels (la narration dit la vérité du mode).
    if ALL_API:
        embed_label = "BM25 lexical (aucun embedding)"
    else:
        embed_label = "dense bge-m3 (API)" if settings.embedder.provider == "openai" else "dense bge-m3 (local)"
    rerank_label = {"bge": "reranker bge (local)", "api": "rerank API",
                    "llm": "Claude rerank"}.get(settings.reranker.provider, settings.reranker.provider)
    _RETRIEVE_CHAIN = f"{embed_label} → parent-child → {rerank_label}"
    # « 100 % API » si rien ne tourne en local (ni embedding ni reranker locaux).
    local_models = (not ALL_API and settings.embedder.provider == "sentence_transformers") \
        or settings.reranker.provider == "bge"
    badge = "modèles en local (in-process)" if local_models else "100 % via API (aucun modèle in-process)"

    print(rule("═"))
    print(f"{C['b']}  HARNESS — démo produit : agent + RAG modulaire — {badge}{C['x']}")
    print(rule("═"))
    print(f"  collection : {C['b']}{settings.vector_store.collection}{C['x']}    (k={K})")
    print(f"  pipeline   : {C['b']}{embed_label} → {rerank_label} → Claude génère{C['x']}")
    print(f"  LLM        : {C['b']}{settings.llm.openai.model}{C['x']} "
          f"(via {settings.llm.openai.base_url})")
    if local_models:
        print(f"  {C['d']}chargement des modèles locaux…{C['x']}")

    t0 = time.time()
    if ALL_API:
        # Candidats BM25 lexical (lit les textes depuis Qdrant, pas d'embedding)
        # → parent-child → reranker configuré.
        from rag.config.factory import build_doc_store, build_reranker, build_vector_store
        from rag.retrieval.bm25 import BM25Retriever, load_bm25_corpus
        from rag.retrieval.parent_child import ParentChildRetriever
        from rag.retrieval.reranking import RerankingRetriever

        store = build_vector_store(settings)
        bm25 = BM25Retriever(load_bm25_corpus(store))
        pc = ParentChildRetriever(inner=bm25, doc_store=build_doc_store(settings))
        retriever = RerankingRetriever(
            inner=pc, reranker=build_reranker(settings), candidate_k=settings.retrieval.dense_k
        )
    else:
        # build_retriever assemble dense(embedder configuré) → parent-child → reranker
        # configuré : selon les providers, c'est local OU API, sans changer de code.
        retriever = build_retriever(settings)
    graph = build_simple_rag_graph(retriever=retriever, llm=build_llm(settings), retrieve_k=K)
    print(f"  {C['d']}prêt en {time.time() - t0:.1f}s{C['x']}")

    for i, q in enumerate(QUESTIONS, 1):
        print("\n\n" + rule("━"))
        print(f"{C['b']}  QUESTION {i}/3{C['x']}  «{C['h']} {q} {C['x']}»")
        print(rule("━"))
        q_start = time.time()

        # 1) PLANIFICATION
        stage("1", "PLANIFICATION — l'agent décompose la tâche")
        t = time.time()
        plan = make_plan(q)
        for j, step in enumerate(plan, 1):
            print(f"   {C['g']}{j}.{C['x']} {step}")
        print(f"   {C['b']}⏱ étape : {time.time() - t:.1f}s{C['x']}")

        # 2) RÉCUPÉRATION  (latence affichée nœud par nœud)
        stage("2", "RÉCUPÉRATION — dense BGE-M3 → parent-child → reranker → génération ancrée")
        t = time.time()
        state = CRAGState(original_query=q, query=q, max_iterations=settings.crag.max_iterations)
        final_answer = None
        t_node = time.time()
        for chunk in graph.stream(state):
            for node, update in chunk.items():
                narrate_node(node, update, time.time() - t_node)
                t_node = time.time()
                ans = get(update, "answer", None)
                if ans is not None:
                    final_answer = ans
        print(f"   {C['b']}⏱ total récupération+génération : {time.time() - t:.1f}s{C['x']}")

        # réponse ancrée + citations produites par le RAG
        if final_answer is not None:
            cits = get(final_answer, "citations", []) or []
            cit_txt = "  ".join(
                f"[{get(c, 'source_file', '?')}"
                + (f":p{get(c, 'page')}" if get(c, "page") is not None else "")
                + "]"
                for c in cits
            )
            print(f"\n   {C['b']}Réponse ancrée du RAG :{C['x']}")
            for line in _wrap(get(final_answer, "text", ""), 72):
                print(f"   {line}")
            if cit_txt:
                print(f"   {C['d']}Sources : {cit_txt}{C['x']}")

        # 3) SYNTHÈSE par l'agent
        stage("3", "SYNTHÈSE — l'agent rédige la réponse client")
        t = time.time()
        base = get(final_answer, "text", "") if final_answer else ""
        client = llm.chat(
            "Reformule pour un client, en 2 phrases claires et professionnelles, "
            "cette réponse issue de nos documents (n'ajoute aucune information) :\n\n" + base
        )
        for line in _wrap(client, 72):
            print(f"   {C['g']}{line}{C['x']}")
        print(f"   {C['b']}⏱ étape : {time.time() - t:.1f}s{C['x']}")

        print(f"\n  {C['h']}⏱ TOTAL QUESTION {i} : {time.time() - q_start:.1f}s{C['x']}")

    print("\n" + rule("═"))
    print(f"{C['b']}  Fin de la démo — 3 questions traitées de bout en bout.{C['x']}")
    print(f"  {C['d']}plan → retrieval + reranker → génération ancrée & citée → synthèse client{C['x']}")
    print(rule("═"))
    return 0


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(" ".join(str(text).split()), width=width) or [""]


if __name__ == "__main__":
    raise SystemExit(main())
