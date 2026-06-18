#!/usr/bin/env python3
"""Démo client — le parcours COMPLET de Harness sur 3 questions du dataset finance.

Montre, étape par étape, ce que fait le produit quand on lui pose une question :

  1. PLANIFICATION   — l'agent décompose la tâche (LLM Claude).
  2. RÉCUPÉRATION + CRAG — le moteur RAG modulaire :
        dense (BGE-M3) → parent-child → RERANKER (top k=6)
        → CRAG : grade des passages → décision → génération ancrée → ground-check
  3. SYNTHÈSE        — l'agent rédige une réponse client, citée et vérifiée.

Config imposée : collection `dataset_finance`, reranker ON (k=6), CRAG ON.
Lancement :  python demo.py
"""
from __future__ import annotations

import os

# --- Config de la démo (AVANT tout import du moteur, pour que les settings la voient) ---
os.environ.setdefault("RAG__VECTOR_STORE__COLLECTION", "dataset_finance")
os.environ.setdefault("RAG__RERANKER__ENABLED", "true")
os.environ.setdefault("RAG__CRAG__ENABLED", "true")          # boucle corrective

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
RAG_ENGINE = ROOT / "rag_engine"

# k = nombre de passages FINAUX après reranking (rerankés depuis le pool dense).
K = 6

QUESTIONS = [
    "Quelle est la politique de distribution des revenus du produit SCPI ?",
    "Quel avantage fiscal offre la souscription à un FCPI éligible ?",
    "Pendant combien d'années les parts d'un FCPI sont-elles bloquées ?",
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
        print(f"   {C['cy']}● retrieve{C['x']} — dense BGE-M3 → parent-child → "
              f"{C['b']}reranker (top {len(hits)}){C['x']}{_lat(dt)}")
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
    print(rule("═"))
    print(f"{C['b']}  HARNESS — démo produit : agent + RAG modulaire (Corrective RAG){C['x']}")
    print(rule("═"))

    from rag.config.factory import build_llm, build_retriever
    from rag.config.settings import load_settings
    from rag.graph.builder import build_crag_graph
    from rag.interfaces.types import CRAGState

    from agent import llm
    from agent.planner import make_plan

    settings = load_settings(configs_dir=RAG_ENGINE / "configs")
    settings.data_dir = RAG_ENGINE / "data"  # chemins absolus (cwd = racine Harness)

    print(f"  collection : {C['b']}{settings.vector_store.collection}{C['x']}    "
          f"reranker : {C['b']}{'ON' if settings.reranker.enabled else 'OFF'} "
          f"(k={K}){C['x']}    "
          f"CRAG : {C['b']}{'ON' if settings.crag.enabled else 'OFF'}{C['x']}")
    print(f"  LLM        : {C['b']}{settings.llm.openai.model}{C['x']} "
          f"(via {settings.llm.openai.base_url})")
    print(f"  {C['d']}chargement des modèles d'embedding + reranker…{C['x']}")
    t0 = time.time()
    # Pool de candidats = retrieval.dense_k (20), rerankés → K=6 passages finaux.
    retriever = build_retriever(settings)
    graph = build_crag_graph(retriever=retriever, llm=build_llm(settings), retrieve_k=K)
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

        # 2) RÉCUPÉRATION + CRAG  (latence affichée nœud par nœud)
        stage("2", "RÉCUPÉRATION + CRAG — dense → parent-child → reranker → boucle corrective")
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
        print(f"   {C['b']}⏱ total CRAG : {time.time() - t:.1f}s{C['x']}")

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
    print(f"  {C['d']}plan → retrieval+reranker → CRAG (grade/décide/ancre/vérifie) → synthèse{C['x']}")
    print(rule("═"))
    return 0


def _wrap(text: str, width: int) -> list[str]:
    import textwrap
    return textwrap.wrap(" ".join(str(text).split()), width=width) or [""]


if __name__ == "__main__":
    raise SystemExit(main())
