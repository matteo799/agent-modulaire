"""Étape 1 : le LLM devient un planificateur."""
from agent import llm
from agent.tools import tools_catalog

PLAN_SYSTEM = "Tu es un planificateur. Tu réponds uniquement en JSON valide."

PLAN_PROMPT = """Décompose cette tâche en étapes concrètes et réalisables avec les outils disponibles.

Tâche :
{user_query}

Outils disponibles :
{catalog}

Règles :
- 3 à 6 étapes maximum.
- Chaque étape doit être une action simple, faisable avec UN seul outil.
- La dernière étape doit produire le livrable final (souvent : écrire un rapport avec write_file).

Retourne uniquement un objet JSON. Exemple :
{{"steps": ["Chercher les informations sur X", "Synthétiser les résultats", "Écrire le rapport final"]}}
"""


def make_plan(user_query: str) -> list[str]:
    """Demande au LLM de décomposer la tâche en liste d'étapes."""
    prompt = PLAN_PROMPT.format(user_query=user_query, catalog=tools_catalog())
    plan = llm.chat_json(prompt, system=PLAN_SYSTEM)
    if isinstance(plan, dict):
        plan = plan.get("steps", list(plan.values())[0] if plan else [])
    return [str(step) for step in plan]
