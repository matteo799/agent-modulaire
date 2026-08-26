"""Registre d'outils : l'agent connaît ses capacités via TOOLS."""

import re
from pathlib import Path

from agent import datasets, security
from agent.finance import amundi, metric_catalog, metrics
from agent.finance.metric_catalog import CATALOG, MetricSpec
from agent.rag_adapter import list_sources, rag_search

WORKSPACE_DIR = Path(__file__).resolve().parent.parent / "workspace"
DOCUMENTS_DIR = Path(__file__).resolve().parent.parent / "documents"


def read_file(path: str) -> str:
    """Lit un fichier, CONFINÉ au workspace et aux documents sources.

    Sécurité (cf. `agent/security.confine`) : aucun chemin ne peut sortir de ces
    deux dossiers — pas de `../` traversal, pas de lecture d'un secret hors zone
    (`.env`, clés API) même si un nom de fichier est injecté par un document.
    """
    name = str(path or "").removeprefix("workspace/").removeprefix("documents/")
    candidate = security.confine(name, WORKSPACE_DIR, DOCUMENTS_DIR)
    if candidate is None:
        return f"Erreur : accès refusé (hors zone autorisée) : {path}"
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return f"Erreur : fichier introuvable : {path}"


def write_file(path: str, content: str) -> str:
    """Écrit un fichier dans le workspace de l'agent (et NULLE PART ailleurs).

    Sécurité (cf. `agent/security.confine`) : le chemin est confiné au workspace
    — un `../` ou un chemin absolu ne peut pas écrire hors de cette zone.
    """
    name = str(path or "").removeprefix("workspace/")
    target = security.confine(name, WORKSPACE_DIR)
    if target is None:
        return f"Erreur : écriture refusée (hors du workspace) : {path}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    rel = target.relative_to(WORKSPACE_DIR.resolve())
    return f"Fichier écrit : workspace/{rel} ({len(content)} caractères)"


def calculator(expression: str) -> str:
    """Évalue une expression arithmétique simple.

    Sécurité : l'évaluation passe par un **AST en liste blanche**
    (`security.safe_eval`), jamais par `eval`. Seuls nombres, `+ - * / %` et
    parenthèses sont acceptés ; tout le reste (exponentiation, appels, noms…)
    est rejeté par construction.
    """
    try:
        return str(security.safe_eval(expression))
    except security.UnsafeExpression as exc:
        return f"Erreur : expression non autorisée ({exc})."
    except SyntaxError:
        return f"Erreur : expression invalide : {expression}"
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
        warn = ""
        if amundi.has_anomaly(r):
            warn = (
                f"Historique NAV anormal pour {isin} (variation quotidienne > 50 % détectée — "
                "données probablement corrompues). Profil ci-dessous NON FIABLE.\n"
            )
        return warn + "\n".join([
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


def fund_performance(isin: str = "", periods: str = "ytd,1y,3y,5y,all") -> str:
    """Performance d'un fonds Amundi par période, calculée sur l'historique NAV."""
    isin = (isin or "").strip()
    if not isin:
        return "Erreur : ISIN manquant pour fund_performance."
    if not amundi.has_nav(isin):
        return f"Erreur : aucun historique NAV pour {isin} — performance non calculable."
    try:
        return amundi.performance_text(isin, periods)
    except Exception as exc:
        return f"Erreur de calcul de la performance de {isin} : {exc}"


def screen_funds(sort_by: str = "sharpe", top=5, asset_class: str = "",
                 sfdr: str = "", sri=None, rf=None) -> str:
    """Classe/filtre les fonds Amundi du dataset par un critère, renvoie le top N."""
    try:
        return amundi.screen_text(sort_by, int(top), asset_class, sfdr, sri, _to_decimal(rf) or 0.0)
    except Exception as exc:
        return f"Erreur de screening : {exc}"


def _to_amount(value):
    """Coerce un MONTANT (€) en float, SANS la convention pourcentage de _to_decimal.

    "10000", "10 000", "10,000", "10000 €" → 10000.0. None/invalide → None.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    cleaned = re.sub(r"[^\d.,-]", "", str(value)).replace(" ", "")
    # « 10,000 » = séparateur de milliers anglais ; « 10,5 » = décimale française.
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", "." if cleaned.rsplit(",", 1)[-1].__len__() <= 2 else "")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def find_fund(name: str = "") -> str:
    """Retrouve l'ISIN d'un fonds Amundi à partir de son NOM (recherche floue)."""
    name = (name or "").strip()
    if not name:
        return "Erreur : nom (ou ISIN) manquant pour find_fund."
    matches = amundi.find_funds(name)
    if not matches:
        return f"Aucun fonds Amundi ne correspond à « {name} »."
    if len(matches) == 1:
        isin, nom = matches[0]
        return f"Fonds trouvé : {isin} — {nom}"
    listed = "\n".join(f"  - {isin} — {nom}" for isin, nom in matches)
    return f"Plusieurs fonds correspondent à « {name} » (préciser lequel) :\n{listed}"


def _resolve_isin(token: str) -> tuple[str, str]:
    """(isin, erreur) : résout un nom ou un ISIN exact vers un ISIN unique.

    Renvoie (isin, "") si résolu, ("", message) si introuvable ou ambigu."""
    token = (token or "").strip()
    if not token:
        return "", "fonds manquant."
    if amundi.has_summary(token) or amundi.has_nav(token):  # déjà un ISIN exact
        return token, ""
    matches = amundi.find_funds(token)
    if len(matches) == 1:
        return matches[0][0], ""
    if not matches:
        return "", f"aucun fonds ne correspond à « {token} »."
    listed = ", ".join(f"{i} ({n})" for i, n in matches)
    return "", f"« {token} » est ambigu — préciser parmi : {listed}."


def invested_value(fund: str = "", amount=None, period: str = "3y") -> str:
    """Valeur aujourd'hui d'un montant investi sur une période, dans un fonds Amundi."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    amt = _to_amount(amount)
    if amt is None:
        return "Erreur : montant investi manquant ou invalide pour invested_value."
    if not amundi.has_nav(isin):
        return f"Erreur : aucun historique NAV pour {isin} — valeur non calculable."
    try:
        return amundi.invested_value_text(isin, amt, (period or "3y").strip())
    except Exception as exc:
        return f"Erreur de calcul de la valeur investie pour {isin} : {exc}"


def compare_funds(funds: str = "", rf=None) -> str:
    """Tableau comparatif de plusieurs fonds Amundi (noms ou ISIN séparés par virgules)."""
    tokens = [t for t in (funds or "").split(",") if t.strip()]
    if len(tokens) < 2:
        return "Erreur : fournir au moins 2 fonds à comparer (noms ou ISIN séparés par des virgules)."
    isins, errors = [], []
    for t in tokens:
        isin, err = _resolve_isin(t)
        (errors if err else isins).append(err or isin)
    if errors:
        return "Erreur de résolution : " + " ".join(errors)
    try:
        return amundi.compare(isins, _to_decimal(rf) or 0.0)
    except Exception as exc:
        return f"Erreur de comparaison : {exc}"


def _pct(x: float) -> str:
    return f"{x:+.2%}"


def fund_calendar(fund: str = "") -> str:
    """Rendements par année calendaire d'un fonds Amundi, calculés sur la NAV."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    try:
        rows = amundi.calendar_returns(isin)
    except Exception as exc:
        return f"Erreur de calcul des rendements calendaires de {isin} : {exc}"
    lines = [f"Rendements par année civile de {isin} (sur la NAV) :"]
    lines += [f"  • {year} : {_pct(r)}" for year, r in rows]
    return "\n".join(lines)


def fund_period(fund: str = "", start: str = "", end: str = "") -> str:
    """Rendement d'un fonds entre deux dates (ou sur une année : start='2022')."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    s, e = (start or "").strip(), (end or "").strip()
    if s and not e and len(s) == 4 and s.isdigit():  # raccourci « 2022 » = année entière
        s, e = f"01/01/{s}", f"31/12/{s}"
    if not s or not e:
        return "Erreur : period nécessite une date de début ET de fin (ou une année seule)."
    try:
        r = amundi.period_return(isin, s, e)
    except Exception as exc:
        return f"Erreur de calcul de la période pour {isin} : {exc}"
    return (f"Rendement de {isin} du {r['start']} au {r['end']} : {_pct(r['cumulative'])} "
            f"(NAV {r['start_nav']:.2f} → {r['end_nav']:.2f}).")


def fund_monthly(fund: str = "") -> str:
    """Statistiques mensuelles d'un fonds : meilleur/pire mois, % de mois positifs."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    try:
        s = amundi.monthly_stats(isin)
    except Exception as exc:
        return f"Erreur de calcul des stats mensuelles de {isin} : {exc}"
    return "\n".join([
        f"Statistiques mensuelles de {isin} (sur {s['n_months']} mois) :",
        f"  • Meilleur mois : {s['best'][0]} {_pct(s['best'][1])}",
        f"  • Pire mois : {s['worst'][0]} {_pct(s['worst'][1])}",
        f"  • Mois positifs : {s['pct_positive']:.0%}",
        f"  • Mois moyen : {_pct(s['avg'])}",
    ])


def fund_underwater(fund: str = "") -> str:
    """Max drawdown + temps sous l'eau (durée de la baisse, récupéré ou non)."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    try:
        u = amundi.underwater(isin)
    except Exception as exc:
        return f"Erreur de calcul du temps sous l'eau de {isin} : {exc}"
    statut = "récupéré" if u["recovered"] else "PAS encore récupéré (toujours sous l'eau)"
    return "\n".join([
        f"Drawdown & temps sous l'eau de {isin} :",
        f"  • Max drawdown : -{u['max_drawdown']:.2%} (sommet {u['peak_date']} → creux {u['trough_date']})",
        f"  • Plus longue phase sous l'eau : {u['longest_underwater_days']} jours — {statut}",
    ])


def fund_rolling_sharpe(fund: str = "", window=252, rf=None) -> str:
    """Stabilité du Sharpe glissant (fenêtre ~1 an) : min/max/moyenne/écart-type."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    try:
        s = amundi.rolling_sharpe(isin, int(window), _to_decimal(rf) or 0.0)
    except Exception as exc:
        return f"Erreur de calcul du Sharpe glissant de {isin} : {exc}"
    return "\n".join([
        f"Sharpe glissant de {isin} (fenêtre {s['window']} j, {s['n']} points) :",
        f"  • Moyenne : {s['mean']:.3f}  ·  écart-type : {s['std']:.3f} (stabilité)",
        f"  • Min : {s['min']:.3f}  ·  Max : {s['max']:.3f}  ·  Dernier : {s['last']:.3f}",
    ])


def funds_correlation(funds: str = "") -> str:
    """Corrélation des rendements quotidiens entre fonds Amundi (dates communes)."""
    tokens = [t for t in (funds or "").split(",") if t.strip()]
    if len(tokens) < 2:
        return "Erreur : fournir au moins 2 fonds (noms ou ISIN séparés par des virgules)."
    isins, errors = [], []
    for t in tokens:
        isin, err = _resolve_isin(t)
        (errors if err else isins).append(err or isin)
    if errors:
        return "Erreur de résolution : " + " ".join(errors)
    try:
        pairs = amundi.correlation_pairs(isins)
    except Exception as exc:
        return f"Erreur de calcul de corrélation : {exc}"
    lines = ["Corrélation des rendements quotidiens (sur les dates communes) :"]
    lines += [f"  • {a} ↔ {b} : {c:+.2f}" for a, b, c in pairs]
    return "\n".join(lines)


def fund_tail_risk(fund: str = "") -> str:
    """Risque de queue & forme : VaR 95/99, CVaR 5 %, skewness, kurtosis."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    if not amundi.has_nav(isin):
        return f"Erreur : aucun historique NAV pour {isin}."
    try:
        r = amundi.load_returns(isin)
        return "\n".join([
            f"Risque de queue de {isin} (sur {len(r)} rendements quotidiens) :",
            f"  • VaR 95 % : -{metrics.var_historical(r, 0.05):.2%}  ·  VaR 99 % : -{metrics.var_historical(r, 0.01):.2%}",
            f"  • CVaR 5 % (perte moyenne de queue) : -{metrics.cvar(r):.2%}",
            f"  • Skewness : {metrics.skewness(r):+.2f} (< 0 = queue gauche plus épaisse)",
            f"  • Kurtosis excédentaire : {metrics.kurtosis_excess(r):+.2f} (> 0 = queues épaisses)",
        ])
    except Exception as exc:
        return f"Erreur de calcul du risque de queue de {isin} : {exc}"


def fund_nav_series(fund: str = "", sample=5) -> str:
    """Données NAV brutes (auditabilité) : nb de points, plage, min/max, échantillon."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    try:
        a = amundi.nav_audit(isin, int(sample))
    except Exception as exc:
        return f"Erreur de lecture de la NAV de {isin} : {exc}"
    head = " ; ".join(f"{d}={v:.2f}" for d, v in a["head"])
    tail = " ; ".join(f"{d}={v:.2f}" for d, v in a["tail"])
    return "\n".join([
        f"Série NAV de {isin} (source : nav.csv) :",
        f"  • {a['n']} points, du {a['start']} au {a['end']} ; NAV min {a['min']:.2f}, max {a['max']:.2f}",
        f"  • Premiers : {head}",
        f"  • Derniers : {tail}",
    ])


def fees_projection(fund: str = "", amount=None, years=None) -> str:
    """Impact des frais courants sur la durée : coût cumulé d'un placement."""
    isin, err = _resolve_isin(fund)
    if err:
        return f"Erreur : {err}"
    amt = _to_amount(amount)
    n = _to_amount(years)
    if amt is None or n is None:
        return "Erreur : invested_value nécessite un montant et un nombre d'années."
    ongoing = (amundi.load_summary(isin).get("costs") or {}).get("ongoing_pct")
    if ongoing is None:
        return f"Erreur : frais courants non renseignés pour {isin}."
    rate = ongoing / 100.0
    kept = amt * (1.0 - rate) ** n  # capital net de frais récurrents (hors performance)
    cost = amt - kept
    return "\n".join([
        f"Impact des frais courants de {isin} ({ongoing:.2f} %/an) sur {n:.0f} ans :",
        f"  • Placement initial : {amt:,.0f} €".replace(",", " "),
        f"  • Coût cumulé des frais : {cost:,.0f} € ({cost / amt:.1%} du capital)".replace(",", " "),
        "  (hypothèse : frais récurrents seuls, hors performance et hors frais d'entrée)",
    ])


def count_funds(dataset: str = "") -> str:
    """Compte EXACT des éléments d'un dataset (le code compte, pas le LLM).

    `dataset` : la clé ou le libellé d'un dataset déclaré dans `agent.datasets`
    (ex. 'amundi', 'finance'). Sans argument : compte tous les datasets connus.
    Le registre est la seule source de vérité — aucun dataset n'est codé ici.
    """
    targets = datasets.all_datasets()
    if dataset.strip():
        ds = datasets.find(dataset)
        if ds is None:
            known = ", ".join(d.key for d in targets)
            return f"Dataset inconnu : « {dataset} ». Datasets disponibles : {known}."
        targets = [ds]
    return " | ".join(f"{d.label} : {d.count()} {d.unit}" for d in targets)


TOOLS = {
    "rag_search": {
        "function": rag_search,
        "description": "Recherche sémantique dans un corpus de documents en TEXTE LIBRE indexé. "
        "À utiliser quand la réponse est de nature QUALITATIVE et se trouve formulée en toutes "
        "lettres dans des documents : description, stratégie, objectif, explication, contexte, "
        "passage à citer. NE convient PAS aux données STRUCTURÉES (champs chiffrés exacts, "
        "encours, ratios, dates précises) ni au CALCUL ou au COMPTAGE : cet outil lit du texte, "
        "il n'agrège et ne calcule rien. NE PAS deviner de nom de fichier ; si « aucun passage "
        "pertinent », ne pas inventer. Arguments : query (str), top_k (int, optionnel), "
        "source (str, optionnel : restreint la recherche à un document).",
    },
    "list_documents": {
        "function": list_sources,
        "description": "Liste les documents en texte libre présents dans le corpus indexé "
        "actuellement actif. Sans argument. Utile pour repérer puis traiter ces documents un par "
        "un (via le paramètre source de rag_search). N'énumère QUE ce corpus textuel ; ne sert "
        "pas à dénombrer (pour un COMPTE exact, utiliser count_funds).",
    },
    "count_funds": {
        "function": count_funds,
        "description": "Renvoie le NOMBRE EXACT d'éléments d'un dataset (compté par le code, pas "
        "estimé). À utiliser pour « combien de fonds / documents y a-t-il », au lieu de compter "
        "soi-même une liste (source d'erreur). Argument : dataset (str, optionnel : la clé du "
        "dataset concerné ; vide = tous les datasets connus).",
    },
    "find_fund": {
        "function": find_fund,
        "description": "Retrouve l'ISIN d'un fonds à partir de son NOM (recherche floue). À utiliser "
        "EN PREMIER dès que l'utilisateur désigne un fonds par son nom et non par un ISIN, car les "
        "autres outils de fonds ont besoin de l'ISIN. Renvoie l'ISIN si unique, ou la liste des "
        "candidats si le nom est ambigu (à lever avant de continuer). Argument : name (str).",
    },
    "invested_value": {
        "function": invested_value,
        "description": "Calcule combien vaut aujourd'hui une somme investie il y a une certaine durée "
        "dans un fonds, à partir de son historique NAV. À utiliser pour « combien valent X € placés "
        "il y a N ans dans le fonds Y ». Arguments : fund (str : ISIN ou NOM du fonds), amount "
        "(montant investi), period (ytd|1y|3y|5y|all, défaut 3y).",
    },
    "compare_funds": {
        "function": compare_funds,
        "description": "Compare PLUSIEURS fonds côte à côte (rendement annualisé, volatilité, Sharpe, "
        "Sortino, max drawdown, frais courants), calculé sur la NAV. À utiliser pour « compare le "
        "fonds A et le fonds B ». Accepte des NOMS ou des ISIN. Argument : funds (str : 2 fonds ou "
        "plus, séparés par des virgules).",
    },
    "fund_calendar": {
        "function": fund_calendar,
        "description": "Rendements ANNÉE PAR ANNÉE (calendaires) d'un fonds, calculés sur la NAV. À "
        "utiliser pour « rendements année par année / par année civile / en 2022, 2023… ». "
        "Argument : fund (ISIN ou nom).",
    },
    "fund_period": {
        "function": fund_period,
        "description": "Rendement d'un fonds sur une PÉRIODE DATÉE précise (entre deux dates, ou une "
        "année entière). À utiliser pour « comment s'est-il comporté en 2022 / pendant le Covid "
        "(mars 2020) / entre telle et telle date ». Arguments : fund (ISIN ou nom), start (date "
        "JJ/MM/AAAA ou AAAA-MM-JJ, ou une année seule comme '2022'), end (date — inutile si année seule).",
    },
    "fund_monthly": {
        "function": fund_monthly,
        "description": "Statistiques MENSUELLES d'un fonds : meilleur mois, pire mois, % de mois "
        "positifs, mois moyen — calculés sur la NAV. À utiliser pour « son meilleur/pire mois, la "
        "régularité mensuelle, le pourcentage de mois gagnants ». Argument : fund (ISIN ou nom).",
    },
    "fund_underwater": {
        "function": fund_underwater,
        "description": "Max drawdown ET TEMPS SOUS L'EAU : durée de la pire phase de baisse et si le "
        "fonds a récupéré son plus-haut. À utiliser pour « combien de temps sous l'eau / temps de "
        "récupération du drawdown / temps pour revenir au sommet ». Argument : fund (ISIN ou nom).",
    },
    "fund_rolling_sharpe": {
        "function": fund_rolling_sharpe,
        "description": "Sharpe GLISSANT sur une fenêtre (~1 an) : moyenne, écart-type (stabilité), "
        "min/max. À utiliser pour « le Sharpe est-il stable ou erratique / Sharpe glissant 12 mois ». "
        "Arguments : fund (ISIN ou nom), window (jours, défaut 252), rf (taux sans risque, optionnel).",
    },
    "funds_correlation": {
        "function": funds_correlation,
        "description": "CORRÉLATION des rendements quotidiens entre plusieurs fonds (sur leurs dates "
        "communes). À utiliser pour « quelle est la corrélation entre ces fonds / sont-ils corrélés / "
        "diversification ». Argument : funds (str : 2 fonds ou plus, noms ou ISIN séparés par virgules).",
    },
    "fund_tail_risk": {
        "function": fund_tail_risk,
        "description": "Risque de QUEUE et forme de la distribution : VaR 95 %, VaR 99 %, CVaR 5 %, "
        "skewness, kurtosis. À utiliser pour « VaR 95/99, asymétrie/skewness, kurtosis, épaisseur de "
        "la queue gauche ». Pour le profil complet de ratios, utiliser plutôt fund_stats. "
        "Argument : fund (ISIN ou nom).",
    },
    "fund_nav_series": {
        "function": fund_nav_series,
        "description": "Données NAV BRUTES pour AUDIT : nombre de points, plage de dates, min/max et "
        "un échantillon (premières/dernières valeurs). À utiliser pour « montre la série NAV / les "
        "données brutes / sur quoi tu t'es basé / l'auditabilité ». Arguments : fund (ISIN ou nom), "
        "sample (nb de lignes en tête/queue, défaut 5).",
    },
    "fees_projection": {
        "function": fees_projection,
        "description": "Impact des FRAIS COURANTS dans le temps : coût cumulé d'un placement sur N "
        "années (frais récurrents seuls, hors performance). À utiliser pour « impact des frais sur "
        "10 ans sur 100 000 € ». Arguments : fund (ISIN ou nom), amount (montant placé), years (durée).",
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
    "fund_performance": {
        "function": fund_performance,
        "description": "Performance d'un fonds Amundi PAR PÉRIODE (YTD, 1 an, 3 ans, 5 ans, depuis "
        "création), calculée sur l'historique NAV : rendement cumulé ET annualisé par fenêtre. "
        "À utiliser pour « performance / rendement sur 1 an / 3 ans / YTD du fonds X ». Arguments : "
        "isin (str), periods (str, optionnel : liste séparée par virgules parmi ytd,1y,3y,5y,all).",
    },
    "screen_funds": {
        "function": screen_funds,
        "description": "Classe/filtre les fonds Amundi du dataset par un critère et renvoie le TOP N. "
        "À utiliser pour un PALMARÈS / SCREENING : « les meilleurs fonds par Sharpe/Sortino/"
        "rendement », « le top 5 des fonds actions Article 8 par Sortino », mais AUSSI « les plus "
        "GROS fonds / par encours / par taille » (sort_by=aum). Arguments : "
        "sort_by (sharpe|sortino|rendement|volatilite|max_drawdown|aum), top (int, défaut 5), "
        "asset_class (action|obligataire|tresorerie|diversifie|specialise — optionnel), "
        "sfdr (6|8|9 — optionnel), sri (1-7 — optionnel), rf (taux sans risque — optionnel).",
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
