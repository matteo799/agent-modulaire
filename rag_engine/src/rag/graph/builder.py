"""Construction du graphe CRAG (LangGraph StateGraph).

Topologie :

    START
       │
       ▼
    retrieve  ◄────────────────────────────┐
       │                                    │
       ▼                                    │
    grade_and_refine                        │
       │                                    │
       ▼                                    │
    decide ──REWRITE──► rewrite_query ──────┘
       │
       ├──PROCEED──► generate ─► ground_check ─► END
       │
       └──FALLBACK─► fallback_no_answer ────────► END

`grade_and_refine` remplace les anciens nœuds `grade_documents` + `refine_knowledge` :
il classe chaque hit ET extrait les phrases utiles en un seul appel LLM par hit,
réduisant de moitié le nombre d'appels séquentiels au modèle.

Le garde-fou `max_iterations` est appliqué dans `decide` : si on a déjà
atteint la limite, on bascule en FALLBACK même si certains hits étaient
ambigus. Ça garantit que le graphe termine toujours en un nombre fini de
pas (LangGraph aussi a un `recursion_limit`, mais on ne veut pas dépendre
de lui pour la correction métier).

LangGraph n'est pas importé au top du module : un caller qui n'a pas
installé l'extra `langgraph` peut toujours utiliser les nœuds individuels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rag.graph.nodes import (
    make_decide_node,
    make_fallback_no_answer_node,
    make_generate_node,
    make_grade_and_refine_node,
    make_ground_check_node,
    make_retrieve_node,
    make_rewrite_query_node,
)
from rag.interfaces import CRAGState, Decision, LLMClient, Retriever, SearchHit

NodeFn = Callable[[CRAGState], dict[str, Any]]


def _make_prepare_context_node() -> NodeFn:
    """Copie les hits bruts dans refined_chunks sans appel LLM.

    Utilisé dans le graphe simple (sans CRAG) : tous les chunks récupérés
    sont transmis tels quels au nœud generate, sans grading ni filtrage.
    """

    def prepare_context_node(state: CRAGState) -> dict[str, Any]:
        hits: list[SearchHit] = state.hits
        return {
            "refined_chunks": [h.text for h in hits],
            "used_chunk_ids": [h.id for h in hits],
        }

    return prepare_context_node


def _route_from_decide(state: CRAGState) -> str:
    """Sélectionne le nœud suivant en fonction de `state.decision`."""
    if state.decision is Decision.PROCEED:
        return "generate"
    if state.decision is Decision.REWRITE:
        return "rewrite_query"
    # FALLBACK ou None par défaut → on coupe court.
    return "fallback_no_answer"


def build_crag_graph(
    retriever: Retriever,
    llm: LLMClient,
    *,
    retrieve_k: int = 5,
    min_relevant_fraction: float = 0.0,
) -> Any:
    """Construit et compile le graphe LangGraph.

    Args:
        retriever: stack retrieval (typiquement issue de `build_retriever`).
        llm: LLMClient utilisé par les nœuds qui interrogent le modèle.
        retrieve_k: nombre de hits demandés à chaque tour de retrieval.
        min_relevant_fraction: passé à `decide`. 0.0 = au moins 1 RELEVANT
            suffit. Plus strict → plus de réécritures.

    Returns:
        Un graphe LangGraph compilé. On le type en `Any` car LangGraph
        n'expose pas de stub mypy et ce module reste optional-extra.
    """
    # Imports paresseux : LangGraph est dans l'extra `langgraph`. Les
    # callers qui n'en ont pas besoin (les tests des nœuds, par exemple) ne
    # paient pas l'import au top du module.
    from langgraph.graph import END, START, StateGraph

    sg: Any = StateGraph(CRAGState)

    sg.add_node("retrieve", make_retrieve_node(retriever, k=retrieve_k))
    sg.add_node("grade_and_refine", make_grade_and_refine_node(llm))
    sg.add_node("decide", make_decide_node(min_relevant_fraction=min_relevant_fraction))
    sg.add_node("rewrite_query", make_rewrite_query_node(llm))
    sg.add_node("generate", make_generate_node(llm))
    sg.add_node("ground_check", make_ground_check_node())
    sg.add_node("fallback_no_answer", make_fallback_no_answer_node())

    sg.add_edge(START, "retrieve")
    sg.add_edge("retrieve", "grade_and_refine")
    sg.add_edge("grade_and_refine", "decide")

    sg.add_conditional_edges(
        "decide",
        _route_from_decide,
        {
            "generate": "generate",
            "rewrite_query": "rewrite_query",
            "fallback_no_answer": "fallback_no_answer",
        },
    )

    # La réécriture renvoie au retrieval pour un nouveau tour.
    sg.add_edge("rewrite_query", "retrieve")

    # Branche PROCEED : generate → ground_check → END.
    sg.add_edge("generate", "ground_check")
    sg.add_edge("ground_check", END)

    # Branche FALLBACK.
    sg.add_edge("fallback_no_answer", END)

    return sg.compile()


def build_simple_rag_graph(
    retriever: Retriever,
    llm: LLMClient,
    *,
    retrieve_k: int = 5,
) -> Any:
    """Graphe RAG simple sans boucle corrective.

    Topologie :
        START → retrieve → prepare_context → generate → ground_check → END

    `prepare_context` copie les hits bruts dans refined_chunks/used_chunk_ids
    sans appel LLM — tous les chunks sont transmis tels quels au générateur.

    Usage : domaines où le corpus est de haute qualité et où la boucle
    corrective (grading + rewrite) n'apporte pas de valeur.
    Activer via `crag.enabled: false` dans la config.
    """
    from langgraph.graph import END, START, StateGraph

    sg: Any = StateGraph(CRAGState)

    sg.add_node("retrieve", make_retrieve_node(retriever, k=retrieve_k))
    sg.add_node("prepare_context", _make_prepare_context_node())
    sg.add_node("generate", make_generate_node(llm))
    sg.add_node("ground_check", make_ground_check_node())

    sg.add_edge(START, "retrieve")
    sg.add_edge("retrieve", "prepare_context")
    sg.add_edge("prepare_context", "generate")
    sg.add_edge("generate", "ground_check")
    sg.add_edge("ground_check", END)

    return sg.compile()
