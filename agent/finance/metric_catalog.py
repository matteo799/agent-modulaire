"""Catalogue des métriques d'optimisation — métadonnées + branchement calcul.

Source unique de vérité, reprise fidèlement de
`docs/metriques_optimisation_gold.md`. Sert à :

1. générer les **descriptions d'outils** (pour que le planner choisisse par
   caractéristiques) — voir `agent/tools.py` ;
2. piloter la **sélection de métrique** et la clarification — voir
   `agent/finance/select.py`.

Chaque entrée porte aussi son **branchement de calcul** :
- `scalar_required` / `scalar_fn` : forme scalaire (entrées déjà connues) ;
- `returns_fn` : forme « depuis une série de rendements » (ou None).
La famille 2 (rendement max sous budget) est **explicative uniquement** : un
vrai calcul exige un univers multi-fonds + une matrice de rendements (hors repo).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agent.finance import metrics

# Données requises (valeurs canoniques, réutilisées par le garde-fou des outils).
REQ_R_SIGMA = "le rendement annualisé R et la volatilité σ"
REQ_RETURNS = "une série de rendements (historique de VL)"
REQ_UNIVERSE = "un univers multi-fonds + une matrice de rendements"


@dataclass(frozen=True)
class MetricSpec:
    key: str
    nom: str
    famille: str  # "ratio" | "budget"
    formule: str
    penalise_hausse: bool
    mesure_risque: str
    tendance: str  # défensif / offensif
    donnees_requises: str
    quand_utiliser: str
    avantages: tuple[str, ...]
    inconvenients: tuple[str, ...]
    # Branchement calcul (None = outil explicatif seulement)
    scalar_required: tuple[str, ...] = ()
    scalar_fn: Callable[[dict], float] | None = None
    returns_fn: Callable[..., float] | None = None


CATALOG: dict[str, MetricSpec] = {
    "sharpe": MetricSpec(
        key="sharpe",
        nom="Ratio de Sharpe",
        famille="ratio",
        formule="(R − rf) / σ",
        penalise_hausse=True,
        mesure_risque="volatilité totale (hausses ET baisses)",
        tendance="défensif ++ (refuge monétaire / obligataire)",
        donnees_requises=REQ_R_SIGMA,
        quand_utiliser=(
            "métrique rendement/risque standard ; comparaison universelle ; "
            "quand on accepte de pénaliser aussi la volatilité haussière"
        ),
        avantages=(
            "standard universel, immédiatement compris",
            "vérifiable directement : (R − rf) / σ",
            "optimum global convexe (portefeuille tangent)",
        ),
        inconvenients=(
            "pénalise la volatilité haussière autant que la baissière",
            "suppose des rendements quasi-normaux ; aveugle aux queues épaisses",
            "tendance au refuge monétaire/obligataire en régime de taux élevés",
        ),
        scalar_required=("R", "sigma"),
        scalar_fn=lambda v: metrics.sharpe(v["R"], v["sigma"], v.get("rf", 0.0)),
        returns_fn=metrics.sharpe_from_returns,
    ),
    "sortino": MetricSpec(
        key="sortino",
        nom="Ratio de Sortino",
        famille="ratio",
        formule="(R − rf) / σ_baisse",
        penalise_hausse=False,
        mesure_risque="risque de baisse uniquement (sous le seuil MAR = rf)",
        tendance="défensif + (plus tolérant aux actions que Sharpe)",
        donnees_requises=REQ_RETURNS,
        quand_utiliser=(
            "le client se soucie surtout de la VOLATILITÉ À LA BAISSE ; "
            "stratégies asymétriques (momentum, convexité positive) ; "
            "on ne veut PAS pénaliser la hausse"
        ),
        avantages=(
            "ne pénalise pas la volatilité haussière",
            "tolère plus d'actions que Sharpe à risque égal",
        ),
        inconvenients=(
            "reste un ratio → structurellement défensif",
            "σ_baisse estimé sur moins de points → plus bruité",
            "dépend du seuil de référence (rf)",
        ),
        scalar_required=("R", "downside_dev"),
        scalar_fn=lambda v: metrics.sortino(v["R"], v["downside_dev"], v.get("rf", 0.0)),
        returns_fn=metrics.sortino_from_returns,
    ),
    "starr": MetricSpec(
        key="starr",
        nom="STARR (Rendement / CVaR)",
        famille="ratio",
        formule="(R − rf) / CVaR_5%",
        penalise_hausse=False,
        mesure_risque="risque de queue (sévérité des pertes extrêmes)",
        tendance="défensif (fuit le risque extrême / queue gauche)",
        donnees_requises=REQ_RETURNS,
        quand_utiliser=(
            "le client se soucie des PERTES EXTRÊMES / queues épaisses ; "
            "distributions non normales ; éviter les actifs à queue gauche épaisse"
        ),
        avantages=(
            "mesure de risque cohérente (sous-additive)",
            "focalisée sur ce qui fait mal : les pertes extrêmes",
        ),
        inconvenients=(
            "CVaR estimée sur peu d'observations de queue → instable sur historique court",
            "reste un ratio → tendance défensive",
        ),
        scalar_required=("R", "cvar"),
        scalar_fn=lambda v: metrics.starr(v["R"], v["cvar"], v.get("rf", 0.0)),
        returns_fn=metrics.starr_from_returns,
    ),
    "martin": MetricSpec(
        key="martin",
        nom="Ratio de Martin (Rendement / Ulcer)",
        famille="ratio",
        formule="(R − rf) / Ulcer",
        penalise_hausse=False,
        mesure_risque="douleur de drawdown (profondeur ET durée sous le plus-haut)",
        tendance="défensif (privilégie la régularité)",
        donnees_requises=REQ_RETURNS,
        quand_utiliser=(
            "le client veut de la RÉGULARITÉ, minimiser le « temps passé sous l'eau » ; "
            "comparer des profils de drawdown ; courbes qui montent sans à-coups"
        ),
        avantages=(
            "capture l'expérience réellement vécue (temps sous l'eau)",
            "idéal pour comparer la régularité",
        ),
        inconvenients=(
            "path-dependent → très sensible à la fenêtre",
            "reste un ratio → défensif ; pénalise les actions à drawdowns profonds",
        ),
        scalar_required=("R", "ulcer"),
        scalar_fn=lambda v: metrics.martin(v["R"], v["ulcer"], v.get("rf", 0.0)),
        returns_fn=metrics.martin_from_returns,
    ),
    "rdt_max_cvar": MetricSpec(
        key="rdt_max_cvar",
        nom="Rendement max sous budget de CVaR",
        famille="budget",
        formule="max R sous contrainte CVaR_5% ≤ budget",
        penalise_hausse=False,
        mesure_risque="budget de perte de queue FIXÉ par l'utilisateur",
        tendance="offensif (tilt actions jusqu'à saturer le budget)",
        donnees_requises=REQ_UNIVERSE,
        quand_utiliser=(
            "le client veut MAXIMISER le rendement sous un plafond de perte extrême "
            "qu'il fixe (ex. CVaR ≤ 8 %) ; allocation offensive maîtrisée"
        ),
        avantages=(
            "pilotable : on fixe le risque de queue, l'optimiseur cherche le rendement",
            "ne punit pas la hausse → exploite pleinement les actions",
            "budget interprétable directement en perte extrême",
        ),
        inconvenients=(
            "résultat dépend du budget choisi (à justifier)",
            "CVaR historique → sensible à l'échantillon de queue",
        ),
        # Explicatif seulement : nécessite univers + optimiseur (hors périmètre repo).
    ),
    "rdt_max_drawdown": MetricSpec(
        key="rdt_max_drawdown",
        nom="Rendement max sous budget de drawdown",
        famille="budget",
        formule="max R sous contrainte |MaxDD| ≤ budget",
        penalise_hausse=False,
        mesure_risque="budget de drawdown maximal FIXÉ par l'utilisateur",
        tendance="offensif ++ (dominé par les actions)",
        donnees_requises=REQ_UNIVERSE,
        quand_utiliser=(
            "le client raisonne en « je ne veux pas perdre plus de X % » ; "
            "contrainte la plus parlante ; allocation offensive sous seuil de perte"
        ),
        avantages=(
            "contrainte la plus parlante pour un client",
            "n'inhibe pas la hausse → offensive maîtrisée",
        ),
        inconvenients=(
            "non convexe → solution dépendante du point de départ",
            "le max drawdown historique est un seul épisode → estimateur fragile",
        ),
    ),
}


def spec(key: str) -> MetricSpec:
    return CATALOG[key]


def render_characteristics(s: MetricSpec) -> str:
    """Bloc lisible des caractéristiques d'une métrique (pour réponses & garde-fou)."""
    return (
        f"{s.nom} — {s.formule}\n"
        f"  • Famille : {s.famille} ({s.tendance})\n"
        f"  • Mesure de risque : {s.mesure_risque}\n"
        f"  • Pénalise la hausse : {'oui' if s.penalise_hausse else 'non'}\n"
        f"  • Données requises : {s.donnees_requises}\n"
        f"  • Quand l'utiliser : {s.quand_utiliser}\n"
        f"  • Avantages : {' ; '.join(s.avantages)}\n"
        f"  • Inconvénients : {' ; '.join(s.inconvenients)}"
    )


def tool_description(s: MetricSpec) -> str:
    """Description courte injectée dans le catalogue d'outils du planner.

    Condense les caractéristiques décisives pour le CHOIX d'outil : famille,
    pénalise-hausse, quand l'utiliser, données requises.
    """
    if s.famille == "budget":
        action = (
            f"Explique l'objectif « {s.nom} » et ses caractéristiques. "
            f"Calcul réel NON disponible (nécessite {s.donnees_requises})."
        )
    else:
        action = (
            f"Calcule le {s.nom}. Si `source` est l'ISIN d'un fonds Amundi (documents/amundi/), "
            f"calcule le VRAI ratio depuis son historique NAV (nav.csv) ; sinon calcule à partir "
            f"des entrées fournies (R et σ, ou une série `returns`) ; sinon explique la métrique "
            f"sans inventer de chiffre."
        )
    return (
        f"{action} Formule : {s.formule}. "
        f"Pénalise la hausse : {'OUI' if s.penalise_hausse else 'non'}. "
        f"Tendance : {s.tendance}. À utiliser quand : {s.quand_utiliser}. "
        f"Arguments : source (str, ISIN — optionnel), R, sigma, rf, "
        f"downside_dev, cvar, ulcer (floats — optionnels), returns (liste de "
        f"rendements — optionnel)."
    )


def selection_catalog() -> str:
    """Vue compacte de toutes les métriques pour le prompt de sélection."""
    lines = []
    for s in CATALOG.values():
        lines.append(
            f"- {s.key} ({s.nom}) : pénalise-hausse={'oui' if s.penalise_hausse else 'non'} ; "
            f"tendance={s.tendance} ; quand={s.quand_utiliser}"
        )
    return "\n".join(lines)
