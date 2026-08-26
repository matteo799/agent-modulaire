"""Sélection de la métrique adaptée à l'intention — avec clarification.

Le boss veut que la planification s'appuie sur les **caractéristiques** des
métriques et **demande une clarification** quand deux métriques se valent
(typiquement Sharpe vs Sortino). On garde le LLM dans la boucle pour mapper
l'intention, mais la décision finale d'ambiguïté passe par `ask_fn` — injectable
pour rester interactif en CLI et non bloquant en démo/éval.
"""

from __future__ import annotations

from collections.abc import Callable

from agent import llm
from agent.finance.metric_catalog import CATALOG, selection_catalog

# Vocabulaire déclencheur : évite un appel LLM quand la question n'a rien à voir.
_METRIC_VOCAB = (
    "sharpe",
    "sortino",
    "starr",
    "martin",
    "ulcer",
    "cvar",
    "drawdown",
    "ratio",
    "volatil",
    "métrique",
    "metrique",
    "optimis",
    "rendement/risque",
    "risque de baisse",
    "perte extrême",
    "perte extreme",
    "budget de risque",
)

AskFn = Callable[[str, list[str]], str]

SELECT_SYSTEM = (
    "Tu es un conseiller en métriques de risque/rendement. Tu réponds uniquement en JSON valide."
)

SELECT_PROMPT = """Intention / question du client :
{user_query}

Métriques disponibles et caractéristiques :
{catalog}

Choisis LA métrique la plus adaptée, en te basant sur les caractéristiques
(pénalise-hausse, tendance, quand l'utiliser). Repères :
- volatilité À LA BAISSE / risque de baisse → sortino
- pertes extrêmes / queues épaisses → starr
- régularité / « temps sous l'eau » / drawdowns → martin
- maximiser le rendement sous un plafond de perte fixé → rdt_max_cvar ou rdt_max_drawdown
- rendement/risque standard, on accepte de pénaliser la hausse → sharpe

Si DEUX métriques se valent vraiment pour cette intention (ex. « meilleure
métrique rendement/risque » sans précision → Sharpe vs Sortino), marque
"ambiguous": true et propose 2 `key` à départager.

Réponds en JSON :
{{"metric": "<key ou null si ambigu>", "ambiguous": <true|false>,
  "rationale": "<raison courte fondée sur les caractéristiques>",
  "question": "<question de clarification si ambigu, sinon \\"\\">",
  "options": ["<key1>", "<key2>"]}}
"""


def looks_like_metric_query(user_query: str) -> bool:
    """Pré-filtre lexical : la question concerne-t-elle une métrique ?"""
    q = user_query.lower()
    return any(token in q for token in _METRIC_VOCAB)


def stdin_ask(question: str, options: list[str]) -> str:
    """Demande interactive (CLI) : pose la question, lit le choix sur stdin.

    Accepte un numéro ou une `key`. Entrée vide / invalide → 1re option.
    """
    print(f"\n{question}")
    for i, key in enumerate(options, 1):
        print(f"   {i}. {key} — {CATALOG[key].nom}")
    try:
        raw = input("Votre choix : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        raw = ""
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    for key in options:
        if raw == key or raw == CATALOG[key].nom.lower():
            return key
    return options[0]


def auto_ask(question: str, options: list[str]) -> str:
    """Résolveur non interactif (démo/éval) : prend la 1re option, journalise."""
    print(f"[clarification auto] {question} → {options[0]} (par défaut)")
    return options[0]


def select_metric(user_query: str, ask_fn: AskFn = stdin_ask) -> dict:
    """Renvoie {metric, rationale, alternatives}. Demande si ambigu via ask_fn."""
    raw = llm.chat_json(
        SELECT_PROMPT.format(user_query=user_query, catalog=selection_catalog()),
        system=SELECT_SYSTEM,
    )
    metric = raw.get("metric")
    ambiguous = bool(raw.get("ambiguous"))
    options = [o for o in (raw.get("options") or []) if o in CATALOG]

    if ambiguous:
        if len(options) < 2:  # garde-fou : défaut le plus fréquent
            options = ["sharpe", "sortino"]
        question = raw.get("question") or "Quelle métrique préférez-vous ?"
        metric = ask_fn(question, options)
        rationale = f"Choisi par l'utilisateur après clarification ({metric})."
    else:
        rationale = raw.get("rationale", "")

    if metric not in CATALOG:  # repli si le LLM renvoie une clé inconnue
        metric = options[0] if options else "sharpe"
    return {"metric": metric, "rationale": rationale, "alternatives": options}
