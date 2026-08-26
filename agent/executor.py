"""Étapes 3 à 6 : sélection d'outil, boucle agentique, mémoire de travail, réflexion."""

from agent import audit, llm, security
from agent.llm import BudgetExceeded, LLMUnavailable
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
- Justifie d'abord ton choix en relisant la description de l'outil : il doit
  correspondre à ce que demande l'étape (ne pas confondre chercher une
  information et faire un calcul).
- Les arguments doivent être des valeurs concrètes, jamais des noms de variables.
- Si l'étape cible un fonds précis (« le 1er fonds », « le 2e fonds »…), renseigne
  l'argument `source` de rag_search avec le nom/ISIN exact de ce fonds, tiré du
  résultat de list_documents présent dans la mémoire (1er fonds = 1er de la liste,
  etc.). Ainsi chaque recherche ne ramène QUE le fonds visé.
- RÈGLE ABSOLUE sur les calculs : dès que l'étape implique une opération
  arithmétique (somme, écart, différence, produit, division, pourcentage,
  "calcule", "combien", "multiplie"…), tu DOIS choisir `calculator`. Ne fais
  JAMAIS le calcul toi-même, ni ici, ni plus tard dans write_file.
- Pour calculator : remplace chaque grandeur par sa valeur numérique exacte tirée
  de la mémoire de travail (ex. "92000 - 80000"). Choisis les BONS opérandes :
  pour un écart entre plusieurs entités (fonds, produits…), prends une valeur de
  chaque entité concernée — jamais deux valeurs d'une même entité. Vérifie que
  l'expression calcule bien ce que demande l'étape ; ne recopie pas une
  expression précédente.
- Pour write_file : ne réutilise que des chiffres réellement présents dans la
  mémoire de travail (y compris les résultats déjà produits par calculator) ;
  n'invente et ne calcule aucune valeur.
- Pour une étape portant sur une MÉTRIQUE de risque/rendement (Sharpe, Sortino,
  STARR, Martin, budget CVaR/drawdown), choisis l'outil `metric_<nom>` dont les
  caractéristiques (pénalise-hausse, tendance, quand l'utiliser) correspondent à
  l'intention. Passe l'ISIN du fonds dans `source`, et toute valeur connue
  (R, sigma, rf, returns…) en arguments. Si le plan a déjà retenu une métrique,
  utilise EXACTEMENT cet outil.

Retourne uniquement un objet JSON, en commençant par la justification :
{{"raison": "<pourquoi cet outil convient à l'étape>", "tool": "<nom>", "args": {{...}}}}
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
        user_query=user_query,
        step=step,
        catalog=tools_catalog(),
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


JUDGE_SYSTEM = "Tu évalues si le résultat d'une étape suffit. Tu réponds uniquement en JSON valide."

JUDGE_PROMPT = """Étape demandée :
{step}

Résultat obtenu :
{result}

Ce résultat permet-il de considérer l'étape comme accomplie ?

Retourne uniquement : {{"sufficient": true|false, "feedback": "<quoi corriger si false>"}}
"""


def llm_reflect(step: str, result: str) -> dict:
    """Variante LLM de `reflect` : un juge sémantique au lieu de la règle.

    C'est la version ÉCARTÉE en conception (cf. docs/design-decisions.md §5) :
    sur un petit modèle, elle produisait des faux positifs (« insuffisant » sur
    des résultats corrects) et un appel LLM supplémentaire par étape. Conservée
    ici pour que l'ablation puisse MESURER ce que coûte et rapporte ce choix,
    au lieu de s'appuyer sur un souvenir d'expérimentation.

    En cas d'indisponibilité LLM, on retombe sur la règle déterministe : le
    bras d'ablation ne doit pas s'effondrer à cause du juge lui-même.
    """
    try:
        verdict = llm.chat_json(
            JUDGE_PROMPT.format(step=step, result=result[:1500]), system=JUDGE_SYSTEM
        )
    except (LLMUnavailable, ValueError, TypeError):
        return reflect(step, result)
    if not isinstance(verdict, dict):
        return reflect(step, result)
    return {
        "sufficient": bool(verdict.get("sufficient", True)),
        "feedback": str(verdict.get("feedback", ""))[:200],
    }


def execute_step(choice: dict) -> str:
    name = choice.get("tool", "")
    if name not in TOOLS:
        return f"Erreur : outil inconnu : {name}"
    args = choice.get("args") or {}
    # Validation générique des arguments AVANT l'appel (cf. agent/security) :
    # rejette tôt un args non-mapping ou une valeur démesurée.
    guard = security.validate_args(args)
    if guard:
        return guard
    try:
        return str(TOOLS[name]["function"](**args))
    except TypeError as exc:
        return f"Erreur d'arguments pour {name} : {exc}"


def run(
    user_query: str,
    plan: list[str],
    max_retries: int = MAX_RETRIES,
    reflect_fn=reflect,
) -> list[dict]:
    """Boucle agentique : pour chaque étape — choix d'outil, exécution, réflexion.

    `max_retries` et `reflect_fn` sont paramétrables pour l'ablation
    (`tests/agent_eval/run_ablation.py`) : `max_retries=0` retire la boucle de
    correction, `reflect_fn=llm_reflect` remplace la règle déterministe par un
    juge LLM. Les valeurs par défaut reproduisent exactement le comportement de
    production — aucun appelant existant n'est affecté.
    """
    WORKSPACE_DIR.mkdir(exist_ok=True)
    write_file(
        "plan.md",
        f"# Plan\n\nTâche : {user_query}\n\n"
        + "\n".join(f"{i}. {s}" for i, s in enumerate(plan, 1)),
    )

    memory: list[dict] = []
    for i, step in enumerate(plan, 1):
        print(f"\n--- Étape {i}/{len(plan)} : {step}")
        feedback = ""
        choice, result = {}, ""
        for _attempt in range(max_retries + 1):
            # Robustesse : un appel LLM qui échoue (réseau) ne tue pas le run —
            # l'étape est marquée en erreur et la boucle passe à la suivante.
            try:
                choice = choose_tool(user_query, step, memory, feedback)
            except BudgetExceeded as exc:
                # Kill-switch : budget du run épuisé → on ARRÊTE toute la boucle
                # (inutile de tenter les étapes suivantes, chaque appel LLM
                # relèverait aussitôt). Le peu déjà produit reste exploitable.
                print(f"    [Budget] {exc}")
                audit.event("budget_exceeded", step_index=i, detail=str(exc))
                memory.append({
                    "step": step, "tool": "?", "result": f"Erreur : {exc}",
                    "raison": "", "args": {},
                })
                audit.step(i, step, "?", {}, str(exc), ok=False)
                return memory
            except LLMUnavailable as exc:
                choice = {"tool": "?", "args": {}}
                result = f"Erreur : service LLM indisponible pour cette étape ({exc})."
                print(f"    {result}")
                break
            if choice.get("raison"):
                print(f"    Raison : {choice['raison']}")
            print(f"    Outil : {choice.get('tool')} | args : {choice.get('args')}")
            result = execute_step(choice)
            verdict = reflect_fn(step, result)
            if verdict["sufficient"]:
                break
            feedback = verdict["feedback"]
            print(f"    Réflexion : insuffisant — {feedback}")
        entry = {
            "step": step,
            "tool": choice.get("tool", "?"),
            "result": result,
            "raison": choice.get("raison", ""),
            "args": choice.get("args") or {},
        }
        # On garde le contenu réellement écrit (write_file ne renvoie qu'une
        # confirmation) pour que la synthèse finale s'appuie sur le livrable.
        if entry["tool"] == "write_file" and not result.startswith("Erreur"):
            entry["content"] = (choice.get("args") or {}).get("content", "")
        memory.append(entry)
        write_file("notes.md", "# Mémoire de travail\n\n" + _format_memory(memory))
        audit.step(
            i, step, entry["tool"], entry["args"], result,
            ok=not (not result.strip() or result.strip().startswith("Erreur")),
        )
        print(f"    Résultat : {result[:200].replace(chr(10), ' ')}...")
    return memory


def last_deliverable(memory: list[dict]) -> str:
    """Contenu du dernier fichier écrit par l'agent (le livrable), s'il existe."""
    return next((m["content"] for m in reversed(memory) if m.get("content")), "")
