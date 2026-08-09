"""Point d'entrée de l'agent.

Usage :
    python main.py "Analyse les documents et fais un résumé des risques."
"""

import sys

from agent import audit, llm, security
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


def _has_structured_result(memory: list) -> bool:
    """Vrai si un outil NON-RAG a produit un résultat exploitable (ni vide, ni erreur).

    Sert à ne pas appliquer le refus hors-sujet quand des données structurées
    (fiches, métriques, screening…) répondent déjà à la question."""
    for m in memory:
        if m.get("tool") in ("rag_search", "write_file"):
            continue
        r = str(m.get("result", "")).strip()
        if not r:
            continue
        low = r.lower()
        if low.startswith("erreur") or "impossible" in low or "aucune fiche" in low:
            continue
        return True
    return False


def synthesize(user_query: str, memory: list) -> str:
    """Rédige la réponse finale. Si l'agent a écrit un livrable, la synthèse le
    reformule SANS voir la mémoire : privée des chunks RAG, elle ne peut pas
    réintroduire d'éléments absents du livrable (source unique de vérité).
    Sinon, repli sur la mémoire."""
    # Désambiguïsation de fonds (déterministe) : si find_fund a renvoyé PLUSIEURS
    # parts pour un même nom, on ne laisse PAS l'agent en choisir une au hasard —
    # on renvoie la liste et on demande à l'utilisateur de préciser (UX chat : il
    # répondra avec l'ISIN ou la part voulue). Garantie par le code, pas par le prompt.
    ambiguous = next(
        (m["result"] for m in memory
         if m.get("tool") == "find_fund" and "Plusieurs fonds correspondent" in str(m.get("result", ""))),
        None,
    )
    if ambiguous:
        return (
            ambiguous
            + "\n\nMerci de préciser la part souhaitée (par son ISIN ou son libellé) "
            "pour que je puisse répondre précisément."
        )

    # Garde-fou hors-sujet (déterministe) : si l'agent a cherché dans les
    # documents et que TOUTES les recherches sont revenues sans passage
    # pertinent, on refuse — sans quoi le LLM répond depuis ses connaissances
    # générales (hallucination hors corpus), comme observé sur le golden.
    # MAIS le refus ne vaut que si le RAG était la SEULE source : si un outil
    # structuré (fund_summary, metric_*, screen_funds…) a produit de vraies
    # données, la réponse est ancrée — on ne doit pas la jeter à cause d'un
    # rag_search vide (cas d'un fonds Amundi absent du corpus finance).
    rag_results = [m["result"] for m in memory if m.get("tool") == "rag_search"]
    all_rag_empty = rag_results and all("Aucun passage pertinent" in r for r in rag_results)
    if all_rag_empty and not _has_structured_result(memory):
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
    # Ouverture du run : piste d'audit (run_id + journal) et budget (kill-switch).
    # Toute requête est tracée et bornée à partir d'ici.
    run_id = audit.start_run(user_query)
    llm.start_run()
    if verbose:
        print(f"[run {run_id}]")

    # === Couche 6 — Sécurité : gate d'entrée anti-détournement ===
    # Refus DÉTERMINISTE avant toute planification : jailbreak / injection de
    # prompt et requêtes hors périmètre finance ne consomment ni plan ni outils.
    verdict = security.screen_query(user_query)
    audit.event("security", allowed=verdict.allowed, category=verdict.category)
    if not verdict.allowed:
        if verbose:
            print(f"\n[Sécurité] Requête refusée ({verdict.category}).")
        audit.end_run("refused", category=verdict.category)
        if return_trace:
            return verdict.message, {
                "tools": [], "metric": None, "n_steps": 0, "refused": verdict.category,
            }
        return verdict.message

    metric, rationale, asked = "", "", False
    if metric_select.looks_like_metric_query(user_query):
        if verbose:
            print("\n=== 0. Sélection de la métrique ===")
        try:
            choice = metric_select.select_metric(user_query, ask_fn=_tracking_ask(ask_fn))
            metric, rationale = choice["metric"], choice["rationale"]
            asked = _CLARIFY_FLAG["asked"]
            audit.event("metric_selected", metric=metric, rationale=rationale, clarification_asked=asked)
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
    except LLMUnavailable as exc:
        # Couvre aussi BudgetExceeded (sous-classe) : budget épuisé dès la
        # planification → arrêt propre, message clair, run clôturé.
        status = "budget" if isinstance(exc, llm.BudgetExceeded) else "llm_down"
        audit.end_run(status, stage="planning")
        if return_trace:
            return LLM_DOWN_MESSAGE, {"tools": [], "metric": None, "n_steps": 0, "error": status}
        return LLM_DOWN_MESSAGE
    audit.event("plan", steps=plan)
    if verbose:
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step}")
        print("\n=== 2. Exécution (boucle agentique) ===")
    memory = run(user_query, plan)
    if verbose:
        print("\n=== 3. Synthèse finale ===")
    answer = synthesize(user_query, memory)
    audit.end_run("ok", n_steps=len(memory), tools=[m["tool"] for m in memory], usage=llm.get_usage())
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
