"""Registre d'outils : l'agent connaît ses capacités via TOOLS."""

import re
from pathlib import Path

from agent.finance import amundi, metric_catalog, metrics
from agent.finance.metric_catalog import CATALOG, MetricSpec
from agent.rag_adapter import list_sources, rag_search

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"


def read_file(path: str) -> str:
    """Lit un fichier depuis le workspace, les documents sources ou un chemin direct."""
    name = path.removeprefix("workspace/").removeprefix("documents/")
    for candidate in (WORKSPACE_DIR / name, DOCUMENTS_DIR / name, Path(path)):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return f"Erreur : fichier introuvable : {path}"


def write_file(path: str, content: str) -> str:
    """Écrit un fichier dans le workspace de l'agent."""
    path = path.removeprefix("workspace/")
    target = WORKSPACE_DIR / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Fichier écrit : workspace/{path} ({len(content)} caractères)"


def calculator(expression: str) -> str:
    """Évalue une expression arithmétique simple."""
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        return f"Erreur : expression non autorisée : {expression}"
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as exc:
        return f"Erreur de calcul : {exc}"


# ── Outils « métriques d'optimisation » (projet rating fond) ──────────────
#
# Un outil PAR métrique, généré depuis le catalogue. Chaque outil :
#   1. calcule si une série de rendements / des scalaires sont fournis ;
#   1bis. si `source` est un ISIN du dataset Amundi → calcule le VRAI ratio sur
#         l'historique NAV (documents/amundi/<ISIN>/nav.csv) ;
#   2. sinon tente de lire R et σ dans un document KID via le RAG (best-effort) ;
#   3. sinon explique la métrique SANS inventer de chiffre (garde-fou honnête).
#   La famille « budget » (CVaR/drawdown) est explicative seulement (le calcul
#   réel exige un univers multi-fonds + rendements).

_PCT_RE = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*%")


def _to_decimal(value):
    """Coerce une entrée financière (rendement, vol, rf…) en décimal (None reste None).

    "8 %" → 0.08 ; "0,08" → 0.08 ; 0.08 → 0.08 ; **2 → 0.02 ; 8 → 0.08**.
    Convention : un nombre **≥ 1** est interprété comme un POURCENTAGE (un LLM écrit
    `2` pour 2 %), car en décimal ces grandeurs sont toujours < 1. Un nombre < 1 est
    déjà un décimal et reste inchangé.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        v = float(value)
    else:
        text = str(value).strip().replace(",", ".")
        if not text:
            return None
        if text.endswith("%"):  # pourcentage explicite → décimal, terminé
            return float(text[:-1].strip()) / 100.0
        v = float(text)
    return v / 100.0 if abs(v) >= 1 else v


def _source_r_sigma(source: str) -> tuple[float | None, float | None]:
    """Tente de lire R (perf annualisée) et σ (volatilité) dans le document.

    Best-effort : la plupart des KID ne les impriment pas. On interroge le RAG
    en ciblant le fonds (`source`) et on parse un pourcentage à proximité des
    mots-clés. En cas d'absence, renvoie (None, None) → garde-fou côté outil.
    """
    if not source:
        return None, None

    def _first_pct(query: str):
        text = rag_search(query, source=source)
        if "Aucun passage pertinent" in text:
            return None
        m = _PCT_RE.search(text)
        return float(m.group(1).replace(",", ".")) / 100.0 if m else None

    R = _first_pct("performance annualisée rendement annuel moyen du fonds")
    sigma = _first_pct("volatilité annualisée écart-type du fonds")
    return R, sigma


def build_metric_tool(s: MetricSpec):
    """Construit la fonction-outil d'une métrique à partir de sa spec."""

    def _tool(source: str = "", returns=None, rf=None, periods_per_year: int = 252, **kwargs):
        carac = metric_catalog.render_characteristics(s)

        # Famille « budget » : explicatif seulement.
        if s.scalar_fn is None and s.returns_fn is None:
            return (
                f"Le calcul réel de « {s.nom} » n'est pas disponible : il nécessite "
                f"{s.donnees_requises} (non présents dans le repo). "
                f"Caractéristiques :\n{carac}"
            )

        rf_dec = _to_decimal(rf) or 0.0

        # 1) Série de rendements fournie → calcul direct.
        if returns and s.returns_fn is not None:
            try:
                series = [_to_decimal(r) for r in returns]
                value = s.returns_fn(series, rf_dec, periods_per_year)
                return f"{s.nom} = {value:.4f} (depuis {len(series)} rendements, rf={rf_dec:.2%})"
            except Exception as exc:
                return f"Erreur de calcul ({s.nom}) : {exc}"

        # 1bis) Source = ISIN du dataset Amundi avec historique NAV → VRAI calcul
        # sur la série de rendements lue dans nav.csv (rendements quotidiens → ppy=252).
        if s.returns_fn is not None and source and amundi.has_nav(source):
            try:
                series = amundi.load_returns(source)
                value = s.returns_fn(series, rf_dec, periods_per_year)
                return (
                    f"{s.nom} = {value:.4f} (calculé sur {len(series)} rendements "
                    f"quotidiens de {source}, rf={rf_dec:.2%})"
                )
            except Exception as exc:
                return f"Erreur de calcul ({s.nom}) depuis l'historique NAV de {source} : {exc}"

        # 2) Entrées scalaires fournies (ou récupérables depuis le document).
        # On ne lit QUE les paramètres numériques reconnus : un argument parasite
        # passé par le planner est ignoré, pas coercé.
        provided: dict[str, float] = {"rf": rf_dec}
        for name in ("R", "sigma", "downside_dev", "cvar", "ulcer"):
            if kwargs.get(name) is None:
                continue
            try:
                provided[name] = _to_decimal(kwargs[name])
            except (TypeError, ValueError):
                return f"Erreur d'argument ({s.nom}) : `{name}` n'est pas un nombre ({kwargs[name]!r})."

        missing = [n for n in s.scalar_required if provided.get(n) is None]
        # Sourcing best-effort : seuls R et σ peuvent venir d'un document.
        if missing and source and set(missing) <= {"R", "sigma"}:
            R, sigma = _source_r_sigma(source)
            if R is not None and "R" in missing:
                provided["R"] = R
            if sigma is not None and "sigma" in missing:
                provided["sigma"] = sigma
            missing = [n for n in s.scalar_required if provided.get(n) is None]

        if not missing:
            try:
                value = s.scalar_fn(provided)
                return f"{s.nom} = {value:.4f} (rf={rf_dec:.2%})"
            except Exception as exc:
                return f"Erreur de calcul ({s.nom}) : {exc}"

        # 3) Garde-fou honnête : pas de quoi calculer.
        src = f" pour {source}" if source else ""
        return (
            f"Calcul du {s.nom} impossible{src} : il manque {', '.join(missing)}. "
            f"Cette métrique requiert {s.donnees_requises} — ni entrées fournies, ni "
            f"historique NAV pour cet ISIN. Aucune valeur inventée. Caractéristiques :\n{carac}"
        )

    _tool.__name__ = f"metric_{s.key}"
    _tool.__doc__ = metric_catalog.tool_description(s)
    return _tool


def fund_summary(isin: str = "", fields: str = "") -> str:
    """Faits d'un fonds Amundi, lus dans sa fiche structurée `summary.json`."""
    isin = (isin or "").strip()
    if not isin:
        return "Erreur : ISIN manquant pour fund_summary."
    if not amundi.has_summary(isin):
        return f"Erreur : aucune fiche pour l'ISIN {isin} dans le dataset Amundi (documents/amundi/)."
    try:
        return amundi.summary_text(isin, fields)
    except Exception as exc:
        return f"Erreur de lecture de la fiche {isin} : {exc}"


def fund_stats(isin: str = "", rf=None) -> str:
    """Profil risque/rendement COMPLET d'un fonds Amundi, calculé sur son historique NAV."""
    isin = (isin or "").strip()
    if not isin:
        return "Erreur : ISIN manquant pour fund_stats."
    if not amundi.has_nav(isin):
        return f"Erreur : aucun historique NAV pour {isin} — profil risque/rendement non calculable."
    try:
        r = amundi.load_returns(isin)
        rf_dec = _to_decimal(rf) or 0.0
        ann_r, sigma = metrics.annualized_return(r), metrics.annualized_vol(r)
        return "\n".join([
            f"Fonds {isin} — profil risque/rendement "
            f"(sur {len(r)} rendements quotidiens, rf={rf_dec:.2%}) :",
            f"  • Rendement annualisé : {ann_r:.2%}",
            f"  • Volatilité annualisée : {sigma:.2%}",
            f"  • Ratio de Sharpe : {metrics.sharpe(ann_r, sigma, rf_dec):.3f}",
            f"  • Ratio de Sortino : {metrics.sortino_from_returns(r, rf_dec):.3f}",
            f"  • STARR (rendement / CVaR) : {metrics.starr_from_returns(r, rf_dec):.3f}",
            f"  • Ratio de Martin (rendement / Ulcer) : {metrics.martin_from_returns(r):.3f}",
            f"  • Max drawdown : {metrics.max_drawdown(r):.2%}",
            f"  • CVaR 5 % (perte de queue quotidienne) : {metrics.cvar(r):.2%}",
        ])
    except Exception as exc:
        return f"Erreur de calcul du profil de {isin} : {exc}"


TOOLS = {
    "rag_search": {
        "function": rag_search,
        "description": "Recherche sémantique dans les documents internes (dossier documents/). "
        "À utiliser pour TOUTE information à retrouver dans les documents "
        "(faits, chiffres, dates). NE PAS deviner de nom de fichier. "
        "Si la réponse indique qu'aucun passage pertinent n'existe, c'est que "
        "les documents ne couvrent pas le sujet : ne pas inventer. "
        "Arguments : query (str), top_k (int, optionnel), "
        "source (str, optionnel : restreint la recherche à un document, ex. un ISIN).",
    },
    "list_documents": {
        "function": list_sources,
        "description": "Liste les documents/fonds disponibles dans documents/. Sans argument. "
        "Utile en première étape pour comparer plusieurs fonds un par un "
        "(via le paramètre source de rag_search).",
    },
    "fund_summary": {
        "function": fund_summary,
        "description": "Renvoie les FAITS d'un fonds Amundi à partir de son ISIN, lus dans sa "
        "fiche structurée (nom, devise, NAV, encours/AUM, classification SFDR, indicateur de "
        "risque SRI, indice de référence, dépositaire, gérant, durée recommandée, date de "
        "création, FRAIS — entrée/sortie/courants/surperformance —, performance YTD). EXACT et "
        "sans recherche sémantique — à PRÉFÉRER à rag_search dès qu'on dispose de l'ISIN d'un "
        "fonds Amundi. NE PAS l'utiliser pour calculer un ratio (pour cela : metric_* ou "
        "fund_stats). Arguments : isin (str), fields (str, optionnel : sous-ensemble de "
        "champs, ex. 'frais' ou 'SFDR, SRI').",
    },
    "fund_stats": {
        "function": fund_stats,
        "description": "Calcule le PROFIL risque/rendement COMPLET d'un fonds Amundi à partir de "
        "son historique NAV : rendement annualisé, volatilité, ratios de Sharpe/Sortino/STARR/"
        "Martin, max drawdown, CVaR. À utiliser pour « donne le profil / les statistiques / la "
        "volatilité / le max drawdown / le rendement annualisé du fonds X », ou un panorama de "
        "risque. Pour UN seul ratio précis (ou un choix par intention client), utiliser plutôt "
        "metric_*. Arguments : isin (str), rf (taux sans risque, optionnel — ex. 2 pour 2 %).",
    },
    "read_file": {
        "function": read_file,
        "description": "Lit un fichier texte dont le nom est DÉJÀ connu (ex. une note écrite "
        "à une étape précédente). Pour explorer les documents internes, "
        "utiliser plutôt rag_search. Arguments : path (str).",
    },
    "write_file": {
        "function": write_file,
        "description": "Écrit un fichier dans le workspace : à réserver à la production du "
        "livrable final. Ne reprendre que des valeurs DÉJÀ présentes dans la "
        "mémoire de travail. INTERDICTION de calculer une valeur ici (somme, "
        "écart, produit, pourcentage) : tout calcul doit avoir été fait AVANT "
        "par calculator, et tu ne fais que recopier son résultat. "
        "Arguments : path (str), content (str).",
    },
    "calculator": {
        "function": calculator,
        "description": "OBLIGATOIRE pour TOUT calcul arithmétique, même trivial (somme, "
        "écart/soustraction, produit, division, pourcentage). Tu ne dois "
        "JAMAIS calculer toi-même un nombre dans une réponse ou un fichier : "
        "passe toujours par cet outil. Opère sur des nombres DÉJÀ connus "
        "(présents dans la mémoire). NE PAS l'utiliser pour chercher une "
        "information (pour ça : rag_search). Arguments : expression (str).",
    },
}


# Injection des 6 outils-métriques, générés depuis le catalogue (un par ratio /
# objectif). Leur description porte les caractéristiques décisives pour que le
# planner choisisse le bon outil selon l'intention.
for _spec in CATALOG.values():
    TOOLS[f"metric_{_spec.key}"] = {
        "function": build_metric_tool(_spec),
        "description": metric_catalog.tool_description(_spec),
    }


def tools_catalog() -> str:
    """Description des outils, injectée dans les prompts de sélection."""
    return "\n".join(f"- {name} : {spec['description']}" for name, spec in TOOLS.items())
