"""Point d'entrée de l'agent.

Usage :
    python main.py "Analyse les documents et fais un résumé des risques."
"""
import sys

from agent import llm
from agent.executor import run, last_deliverable, _format_memory
from agent.planner import make_plan
from agent.tools import write_file

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
    deliverable = last_deliverable(memory)
    if deliverable:
        return llm.chat(SYNTHESIS_FROM_DELIVERABLE.format(
            user_query=user_query, deliverable=deliverable))
    return llm.chat(SYNTHESIS_FROM_MEMORY.format(
        user_query=user_query, memory=_format_memory(memory)))


def answer_query(user_query: str, verbose: bool = True) -> str:
    """Pipeline complet : planification → boucle agentique → synthèse."""
    if verbose:
        print(f"Tâche : {user_query}")
        print("\n=== 1. Planification ===")
    plan = make_plan(user_query)
    if verbose:
        for i, step in enumerate(plan, 1):
            print(f"  {i}. {step}")
        print("\n=== 2. Exécution (boucle agentique) ===")
    memory = run(user_query, plan)
    if verbose:
        print("\n=== 3. Synthèse finale ===")
    return synthesize(user_query, memory)


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
