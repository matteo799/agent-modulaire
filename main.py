"""Point d'entrée de l'agent.

Usage :
    python main.py "Analyse les documents et fais un résumé des risques."
"""

import sys

from agent import llm
from agent.executor import _format_memory, last_deliverable, run
from agent.finance import select as metric_select
from agent.llm import LLMUnavailable
from agent.planner import make_plan
from agent.tools import write_file

LLM_DOWN_MESSAGE = (
    "Le service LLM est momentanément indisponible (erreur réseau). "
    "Aucune réponse n'a pu être produite — réessayez dans un instant."
)

SYNTHESIS_FROM_DELIVERABLE = """Tâche initiale de l'utilisateur :
{user_query}

L'agent a produit ce livrable :
{deliverable}

Reformule-le en une réponse finale claire et structurée pour l'utilisateur.
N'ajoute, ne retire et ne modifie AUCUNE information : reprends uniquement ce
qui figure dans le livrable ci-dessus.
"""

SYNTHESIS_FROM_MEMORY = """Tâche initiale de l'utilisateur :
{user_query}

Résultats de chaque étape du plan :
{memory}

Rédige la réponse finale pour l'utilisateur, claire et structurée, en t'appuyant
uniquement sur ces résultats.
"""


def synthesize(user_query: str, memory: list) -> str:
    """Rédige la réponse finale. Si l'agent a écrit un livrable, la synthèse le
    reformule SANS voir la mémoire : privée des chunks RAG, elle ne peut pas
    réintroduire d'éléments absents du livrable (source unique de vérité).
    Sinon, repli sur la mémoire."""
    # Garde-fou hors-sujet (déterministe) : si l'agent a cherché dans les
    # documents et que TOUTES les recherches sont revenues sans passage
    # pertinent, on refuse — sans quoi le LLM répond depuis ses connaissances
    # générales (hallucination hors corpus), comme observé sur le golden.
    rag_results = [m["result"] for m in memory if m.get("tool") == "rag_search"]
    if rag_results and all("Aucun passage pertinent" in r for r in rag_results):
        return "Les documents fournis ne permettent pas de répondre à cette question."

    deliverable = last_deliverable(memory)
    try:
        if deliverable:
            return llm.chat(
                SYNTHESIS_FROM_DELIVERABLE.format(user_query=user_query, deliverable=deliverable)
            )
        return llm.chat(
            SYNTHESIS_FROM_MEMORY.format(user_query=user_query, memory=_format_memory(memory))
        )
    except LLMUnavailable:
        # Repli : la synthèse a échoué (réseau), mais on a déjà du travail utile.
        if deliverable:
            return deliverable  # livrable brut, sans reformulation
        return (
            "Réponse partielle — le service LLM a échoué pendant la synthèse "
            "finale. Résultats bruts collectés :\n\n" + _format_memory(memory)
        )


def answer_query(
    user_query: str,
    verbose: bool = True,
    ask_fn=metric_select.stdin_ask,
    return_trace: bool = False,
):
    """Pipeline complet : (sélection métrique) → planification → boucle → synthèse.

    Si la question concerne une métrique de risque/rendement, on résout d'abord
    LAQUELLE (en demandant une clarification quand deux se valent), puis on
    injecte ce choix dans la planification. `ask_fn` est injectable : interactif
    par défaut (stdin), non bloquant pour les démos/éval (`select.auto_ask`).

    `return_trace=True` → renvoie `(réponse, trace)` où `trace` décrit ce que
    l'agent a réellement fait (outils appelés, métrique retenue, nb d'étapes) —
    utilisé par l'évaluation pour mesurer la couverture d'outils.
    """
    metric, rationale, asked = "", "", False
    if metric_select.looks_like_metric_query(user_query):
        if verbose:
            print("\n=== 0. Sélection de la métrique ===")
        try:
            choice = metric_select.select_metric(user_query, ask_fn=_tracking_ask(ask_fn))
            metric, rationale = choice["metric"], choice["rationale"]
            asked = _CLARIFY_FLAG["asked"]
            if verbose:
                print(f"  Métrique retenue : {metric} — {rationale}")
        except LLMUnavailable as exc:
            # Non bloquant : on planifie sans indice de métrique.
            if verbose:
                print(f"  (sélection de métrique ignorée — LLM indisponible : {exc})")
    if verbose:
        print(f"Tâche : {user_query}")
        print("\n=== 1. Planification ===")
    try:
        plan = make_plan(user_query, metric=metric, rationale=rationale)
    except LLMUnavailable:
        if return_trace:
            return LLM_DOWN_MESSAGE, {"tools": [], "metric": None, "n_steps": 0, "error": "llm_down"}
        return LLM_DOWN_MESSAGE
    if verbose:
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step}")
        print("\n=== 2. Exécution (boucle agentique) ===")
    memory = run(user_query, plan)
    if verbose:
        print("\n=== 3. Synthèse finale ===")
    answer = synthesize(user_query, memory)
    if return_trace:
        trace = {
            "tools": [m["tool"] for m in memory],
            "metric": metric or None,
            "clarification_asked": asked,
            "n_steps": len(memory),
            "plan": plan,
            "steps": [
                {
                    "step": m["step"],
                    "tool": m["tool"],
                    "raison": m.get("raison", ""),
                    "args": m.get("args", {}),
                    "result": m["result"],
                }
                for m in memory
            ],
        }
        return answer, trace
    return answer


# Drapeau de clarification : permet à la trace de savoir si l'agent a demandé une
# clarification (sans changer la signature publique de `ask_fn`).
_CLARIFY_FLAG = {"asked": False}


def _tracking_ask(inner):
    """Enveloppe un `ask_fn` pour mémoriser qu'une clarification a eu lieu."""
    _CLARIFY_FLAG["asked"] = False

    def _wrapped(question, options):
        _CLARIFY_FLAG["asked"] = True
        return inner(question, options)

    return _wrapped


def main():
    if len(sys.argv) < 2:
        print('Usage : python main.py "votre question"')
        sys.exit(1)
    user_query = " ".join(sys.argv[1:])
    answer = answer_query(user_query)
    write_file("rapport.md", f"# Rapport final\n\nTâche : {user_query}\n\n{answer}")
    print(answer)
    print("\n(Plan, notes et rapport sauvegardés dans workspace/)")


if __name__ == "__main__":
    main()
