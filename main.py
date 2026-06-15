"""Point d'entrée de l'agent.

Usage :
    python main.py "Analyse les documents et fais un résumé des risques."
"""
import sys

from agent import llm
from agent.executor import run, _format_memory
from agent.planner import make_plan
from agent.tools import write_file

SYNTHESIS_PROMPT = """Tâche initiale de l'utilisateur :
{user_query}

Résultats de chaque étape du plan :
{memory}

Rédige la réponse finale pour l'utilisateur, claire et structurée, en t'appuyant
uniquement sur ces résultats.
"""


def main():
    if len(sys.argv) < 2:
        print('Usage : python main.py "votre question"')
        sys.exit(1)
    user_query = " ".join(sys.argv[1:])

    print(f"Tâche : {user_query}")
    print("\n=== 1. Planification ===")
    plan = make_plan(user_query)
    for i, step in enumerate(plan, 1):
        print(f"  {i}. {step}")

    print("\n=== 2. Exécution (boucle agentique) ===")
    memory = run(user_query, plan)

    print("\n=== 3. Synthèse finale ===")
    answer = llm.chat(SYNTHESIS_PROMPT.format(
        user_query=user_query, memory=_format_memory(memory)))
    write_file("rapport.md", f"# Rapport final\n\nTâche : {user_query}\n\n{answer}")
    print(answer)
    print("\n(Plan, notes et rapport sauvegardés dans workspace/)")


if __name__ == "__main__":
    main()
