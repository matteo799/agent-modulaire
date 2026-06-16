"""Étapes 3 à 6 : sélection d'outil, boucle agentique, mémoire de travail, réflexion."""
from agent import llm
from agent.tools import TOOLS, WORKSPACE_DIR, tools_catalog, write_file

MAX_RETRIES = 1  # une réflexion + nouvelle tentative par étape

SELECT_SYSTEM = "Tu choisis l'outil adapté à une étape. Tu réponds uniquement en JSON valide."

SELECT_PROMPT = """Tâche globale :
{user_query}

Étape à exécuter :
{step}

Outils disponibles :
{catalog}

Résultats des étapes précédentes (mémoire de travail) :
{memory}

Choisis UN outil et ses arguments pour exécuter cette étape.

Règles importantes :
- Les arguments doivent être des valeurs concrètes, jamais des noms de variables.
- Pour calculator : remplace chaque grandeur par sa valeur numérique exacte tirée
  de la mémoire de travail (ex. "92000 - 80000"), et vérifie que l'expression
  calcule bien ce que demande l'étape — ne recopie pas une expression précédente.
- Pour write_file : ne réutilise que des chiffres réellement présents dans la
  mémoire de travail ; n'invente aucune valeur.

Retourne uniquement un objet JSON : {{"tool": "<nom>", "args": {{...}}}}
"""


def _format_memory(memory: list[dict]) -> str:
    if not memory:
        return "(aucun résultat pour l'instant)"
    return "\n\n".join(
        f"### Étape : {m['step']}\nOutil : {m['tool']}\nRésultat :\n{m['result'][:1500]}"
        for m in memory
    )


def choose_tool(user_query: str, step: str, memory: list[dict], feedback: str = "") -> dict:
    """Le LLM décide quel outil utiliser pour une étape donnée."""
    prompt = SELECT_PROMPT.format(
        user_query=user_query, step=step, catalog=tools_catalog(),
        memory=_format_memory(memory),
    )
    if feedback:
        prompt += f"\nTentative précédente insuffisante. Conseil : {feedback}\n"
    return llm.chat_json(prompt, system=SELECT_SYSTEM)


def reflect(step: str, result: str) -> dict:
    """Auto-correction : on ne retente que si l'outil a renvoyé une vraie erreur.

    Décision déterministe plutôt que confiée au LLM : un modèle 7B juge sans
    cesse « insuffisant » des résultats corrects, ce qui déclenche des retries
    parasites. Un résultat est considéré réussi sauf s'il est vide ou commence
    par « Erreur » (convention de tous les outils)."""
    clean = result.strip()
    if not clean or clean.startswith("Erreur"):
        return {"sufficient": False, "feedback": clean[:200] or "résultat vide"}
    return {"sufficient": True, "feedback": ""}


def execute_step(choice: dict) -> str:
    name = choice.get("tool", "")
    if name not in TOOLS:
        return f"Erreur : outil inconnu : {name}"
    args = choice.get("args") or {}
    try:
        return str(TOOLS[name]["function"](**args))
    except TypeError as exc:
        return f"Erreur d'arguments pour {name} : {exc}"


def run(user_query: str, plan: list[str]) -> list[dict]:
    """Boucle agentique : pour chaque étape — choix d'outil, exécution, réflexion."""
    WORKSPACE_DIR.mkdir(exist_ok=True)
    write_file("plan.md", f"# Plan\n\nTâche : {user_query}\n\n"
               + "\n".join(f"{i}. {s}" for i, s in enumerate(plan, 1)))

    memory: list[dict] = []
    for i, step in enumerate(plan, 1):
        print(f"\n--- Étape {i}/{len(plan)} : {step}")
        feedback = ""
        for attempt in range(MAX_RETRIES + 1):
            choice = choose_tool(user_query, step, memory, feedback)
            print(f"    Outil : {choice.get('tool')} | args : {choice.get('args')}")
            result = execute_step(choice)
            verdict = reflect(step, result)
            if verdict["sufficient"]:
                break
            feedback = verdict["feedback"]
            print(f"    Réflexion : insuffisant — {feedback}")
        memory.append({"step": step, "tool": choice.get("tool", "?"), "result": result})
        write_file("notes.md", "# Mémoire de travail\n\n" + _format_memory(memory))
        print(f"    Résultat : {result[:200].replace(chr(10), ' ')}...")
    return memory
