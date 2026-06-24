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
- 3 à 7 étapes maximum.
- Chaque étape doit être une action simple, faisable avec UN seul outil.
- Pour consulter les documents internes, utilise rag_search avec une requête.
  N'invente jamais de nom de fichier pour read_file : tu ne connais pas les noms
  des fichiers, seul rag_search sait y accéder.
- Tâche portant sur PLUSIEURS fonds/documents (comparer, « pour chaque fonds »,
  « les fonds ») : NE FAIS PAS une seule recherche globale (elle ne ramène qu'un
  fonds). À la place :
    1) une étape `list_documents` pour identifier les fonds,
    2) puis UNE étape rag_search PAR fonds, formulée génériquement car tu ne
       connais pas encore les noms — ex. « Rechercher les infos du 1er fonds
       (rag_search, en ciblant ce fonds via source) », « … du 2e fonds », etc.
       (limite-toi à 2 ou 3 fonds pour tenir dans le nombre d'étapes),
    3) puis seulement comparer/calculer, une fois chaque valeur collectée.
- Ne calcule chaque grandeur qu'UNE seule fois : ne crée pas deux étapes de
  calcul pour le même résultat (cela produit des valeurs contradictoires).
- La dernière étape doit produire le livrable final (souvent : écrire un rapport avec write_file).

Chaque étape est une PHRASE (chaîne de caractères), pas un objet. Adapte-les à
la tâche réelle ci-dessus — ne recopie pas l'exemple.
{metric_hint}
Retourne uniquement un objet JSON. Exemple de FORMAT (à ne pas recopier tel quel) :
{{"steps": ["Chercher les informations sur X", "Synthétiser les résultats", "Écrire le rapport final"]}}
"""

METRIC_HINT = """
- Métrique retenue pour cette tâche : `{metric}` ({rationale}). L'étape de calcul
  doit cibler explicitement l'outil `metric_{metric}` (et non un autre ratio).
"""


def _step_text(step) -> str:
    """Normalise une étape en phrase, même si le LLM la renvoie en objet
    structuré (ex. {{"step": 1, "action": "...", "tool": "..."}})."""
    if isinstance(step, dict):
        for key in ("action", "step", "description", "text", "tache", "etape"):
            val = step.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return "; ".join(f"{k}: {v}" for k, v in step.items())
    return str(step)


def make_plan(user_query: str, metric: str = "", rationale: str = "") -> list[str]:
    """Demande au LLM de décomposer la tâche en liste d'étapes.

    `metric` (optionnel) : clé de la métrique retenue en amont par
    `agent.finance.select` — injectée pour que le plan cible le bon outil.
    """
    hint = METRIC_HINT.format(metric=metric, rationale=rationale) if metric else ""
    prompt = PLAN_PROMPT.format(user_query=user_query, catalog=tools_catalog(), metric_hint=hint)
    plan = llm.chat_json(prompt, system=PLAN_SYSTEM)
    if isinstance(plan, dict):
        plan = plan.get("steps", next(iter(plan.values())) if plan else [])
    return [_step_text(step) for step in plan]
