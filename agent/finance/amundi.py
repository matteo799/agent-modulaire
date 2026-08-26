"""Accès au dataset Amundi structuré — un dossier par ISIN.

`documents/amundi/<ISIN>/`
  - `nav.csv`      : historique NAV (`date;nav`, quotidien) → série de rendements.
  - `summary.json` : fiche structurée du fonds → faits exacts (remplace le RAG).

Ce module est la source de données « structurée » de l'agent (le pendant de
`agent/rag_adapter.py`, mais sur du JSON/CSV au lieu d'un index sémantique). Les
outils `metric_*` l'utilisent pour calculer de VRAIS ratios depuis `nav.csv`, et
l'outil `fund_summary` pour lire les faits depuis `summary.json`.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from agent.finance import metrics

# documents/amundi/ à la racine du dépôt (agent/finance/amundi.py → parents[2]).
DATASET_DIR = Path(__file__).resolve().parents[2] / "documents" / "amundi"


def fund_dir(isin: str) -> Path:
    return DATASET_DIR / isin.strip()


def count_funds() -> int:
    """Nombre de fonds Amundi exploitables (un dossier ISIN avec nav.csv ET summary.json)."""
    if not DATASET_DIR.is_dir():
        return 0
    return sum(
        1
        for d in DATASET_DIR.iterdir()
        if d.is_dir() and (d / "nav.csv").is_file() and (d / "summary.json").is_file()
    )


def has_nav(isin: str) -> bool:
    return (fund_dir(isin) / "nav.csv").is_file()


def has_summary(isin: str) -> bool:
    return (fund_dir(isin) / "summary.json").is_file()


def _all_named() -> list[tuple[str, str]]:
    """(isin, nom) de tous les fonds disposant d'une fiche `summary.json`."""
    out: list[tuple[str, str]] = []
    if not DATASET_DIR.is_dir():
        return out
    for d in DATASET_DIR.iterdir():
        if not (d.is_dir() and (d / "summary.json").is_file()):
            continue
        try:
            name = load_summary(d.name).get("name") or ""
        except (OSError, ValueError):
            continue
        out.append((d.name, name))
    return out


def find_funds(query: str, limit: int = 8) -> list[tuple[str, str]]:
    """Retrouve des fonds par NOM (ou ISIN exact). Renvoie [(isin, nom), …] classés.

    Match sur le nombre de mots de la requête présents dans le nom ; ne garde que
    les fonds atteignant le meilleur score (les mieux couverts). Sans correspondance
    parfaite par ISIN, c'est best-effort : à l'appelant de lever l'ambiguïté.
    """
    q = query.strip().lower()
    if not q:
        return []
    named = _all_named()
    direct = [(i, n) for i, n in named if q == i.lower()]
    if direct:
        return direct[:limit]
    tokens = [t for t in re.split(r"[\s\-/]+", q) if t]
    scored: list[tuple[int, int, str, str]] = []
    for isin, name in named:
        nl = name.lower()
        hits = sum(1 for t in tokens if t in nl)
        if hits:
            scored.append((hits, -len(name), isin, name))  # +couvert, puis nom + court
    if not scored:
        return []
    scored.sort(reverse=True)
    best = scored[0][0]
    return [(i, n) for h, _, i, n in scored if h == best][:limit]


def load_navs(isin: str) -> list[tuple[datetime, float]]:
    """Lit `nav.csv` → liste (date, nav) triée chronologiquement (lignes invalides ignorées)."""
    path = fund_dir(isin) / "nav.csv"
    rows: list[tuple[datetime, float]] = []
    # utf-8-sig : retire le BOM en tête de fichier.
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            raw_date, raw_nav = (r.get("date") or "").strip(), (r.get("nav") or "").strip()
            if not raw_date or not raw_nav:
                continue
            try:
                dt = datetime.strptime(raw_date, "%d/%m/%Y")
                nav = float(raw_nav.replace(",", "."))
            except ValueError:
                continue
            rows.append((dt, nav))
    rows.sort(key=lambda x: x[0])
    return rows


# Au-delà de cette variation quotidienne (±50 %), la donnée est aberrante (NAV cassée,
# split non ajusté, point corrompu) : un vrai fonds ne bouge pas de 50 % en un jour.
ANOMALY_THRESHOLD = 0.5


def load_returns(isin: str) -> list[float]:
    """Série de rendements quotidiens = variation relative de la NAV d'un jour à l'autre."""
    navs = [v for _, v in load_navs(isin)]
    if len(navs) < 2:
        raise ValueError(f"historique NAV insuffisant pour {isin} ({len(navs)} point(s))")
    return [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs)) if navs[i - 1] != 0]


def has_anomaly(returns: list[float]) -> bool:
    """Vrai si la série contient une variation quotidienne aberrante (> ANOMALY_THRESHOLD)."""
    return any(abs(r) > ANOMALY_THRESHOLD for r in returns)


def load_summary(isin: str) -> dict:
    """Lit `summary.json` → dict des faits du fonds."""
    return json.loads((fund_dir(isin) / "summary.json").read_text(encoding="utf-8"))


def summary_text(isin: str, fields: str = "") -> str:
    """Rendu lisible des faits d'un fonds (option `fields` = sous-ensemble, séparé par virgules)."""
    d = load_summary(isin)
    wanted = [f.strip().lower() for f in fields.split(",") if f.strip()]

    def keep(label: str) -> bool:
        return not wanted or any(w in label.lower() for w in wanted)

    base = [
        ("Nom", "name"), ("ISIN", "isin"), ("Devise", "currency"),
        ("NAV", "nav"), ("Date NAV", "nav_date"), ("Encours (AUM)", "aum"),
        ("Classification SFDR", "sfdr"), ("Indicateur de risque (SRI)", "risk_sri"),
        ("Indice de référence", "benchmark"),
    ]
    lines = [f"{lbl} : {d[key]}" for lbl, key in base if d.get(key) is not None and keep(lbl)]
    for k, v in (d.get("characteristics") or {}).items():
        if keep(k):
            lines.append(f"{k} : {v}")
    # Frais (bloc `costs`) — central pour un gérant, et traité comme un TOUT.
    #
    # Le filtrage par sous-chaîne ne convient pas ici : demander « frais » ne
    # matchait ni « Commission de surperformance » ni « Coûts de transaction »,
    # et renvoyait donc une tarification silencieusement incomplète. Une fiche de
    # frais tronquée est pire qu'une absence de réponse : elle a l'air complète.
    # Dès qu'un terme de coût est demandé, on rend le bloc entier.
    costs = d.get("costs") or {}
    cost_labels = [
        ("Frais d'entrée", "entry_pct"), ("Frais de sortie", "exit_pct"),
        ("Frais courants", "ongoing_pct"), ("Coûts de transaction", "transaction_pct"),
        ("Commission de surperformance", "performance_pct"),
    ]
    cost_terms = ("frais", "cout", "coût", "cost", "commission", "charge", "tarif")
    wants_costs = any(
        any(term in w for term in cost_terms)
        or any(w in lbl.lower() for lbl, _ in cost_labels)
        for w in wanted
    )
    if not wanted or wants_costs:
        for lbl, key in cost_labels:
            if costs.get(key) is not None:
                lines.append(f"{lbl} : {costs[key]} %")
    # Performance YTD (depuis asset_allocation).
    for item in d.get("asset_allocation") or []:
        lbl = item.get("label", "")
        if "perf" in lbl.lower() and keep(lbl):
            lines.append(f"{lbl} : {item.get('pct')}")

    if not lines:
        return f"Aucun champ correspondant à « {fields} » dans la fiche de {isin}."
    # `characteristics` redonde parfois un champ de base (ex. l'indice de
    # référence) : on dédoublonne en gardant l'ordre.
    lines = list(dict.fromkeys(lines))
    return f"Fiche {isin} :\n" + "\n".join(f"  • {ln}" for ln in lines)


# ── Performance par période ────────────────────────────────────────────────

_PERIOD_DAYS = {"1y": 365, "3y": 1095, "5y": 1825}


def performance(isin: str, period: str = "all") -> dict:
    """Performance d'un fonds sur une fenêtre (`ytd`, `1y`, `3y`, `5y`, `all`).

    Renvoie {period, cumulative, annualized, years, start, end} calculé sur la NAV.
    """
    navs = load_navs(isin)
    if len(navs) < 2:
        raise ValueError(f"historique NAV insuffisant pour {isin}")
    end_dt, end_nav = navs[-1]
    p = period.strip().lower()
    if p == "ytd":
        cutoff = end_dt.replace(month=1, day=1)
    elif p in _PERIOD_DAYS:
        cutoff = end_dt - timedelta(days=_PERIOD_DAYS[p])
    else:  # all / depuis création
        cutoff = navs[0][0]
    window = [(d, v) for d, v in navs if d >= cutoff]
    if len(window) < 2:
        raise ValueError(f"historique insuffisant pour la période {p}")
    start_dt, start_nav = window[0]
    cumulative = end_nav / start_nav - 1.0
    years = max((end_dt - start_dt).days / 365.25, 1e-9)
    annualized = (1.0 + cumulative) ** (1.0 / years) - 1.0
    return {"period": p, "cumulative": cumulative, "annualized": annualized,
            "years": years, "start": start_dt.date(), "end": end_dt.date()}


def performance_text(isin: str, periods: str = "ytd,1y,3y,5y,all") -> str:
    """Performance d'un fonds sur plusieurs fenêtres (liste séparée par virgules)."""
    lines = [f"Performance de {isin} (calculée sur l'historique NAV) :"]
    for p in [x.strip() for x in periods.split(",") if x.strip()]:
        try:
            r = performance(isin, p)
            lines.append(
                f"  • {p.upper():4} : cumulée {r['cumulative']:+.2%}, "
                f"annualisée {r['annualized']:+.2%}  ({r['years']:.1f} an(s), "
                f"{r['start']} → {r['end']})"
            )
        except ValueError as exc:
            lines.append(f"  • {p.upper():4} : indisponible ({exc})")
    return "\n".join(lines)


# ── Valeur d'un investissement ─────────────────────────────────────────────

def invested_value(isin: str, amount: float, period: str = "3y") -> dict:
    """Valeur aujourd'hui de `amount` investis sur `period`, depuis la NAV.

    Renvoie {amount, value, gain, period + les champs de performance()}.
    """
    perf = performance(isin, period)
    value = amount * (1.0 + perf["cumulative"])
    return {"amount": amount, "value": value, "gain": value - amount, **perf}


def invested_value_text(isin: str, amount: float, period: str = "3y") -> str:
    r = invested_value(isin, amount, period)
    return (
        f"Investissement dans {isin} :\n"
        f"  • Placé : {r['amount']:,.0f} € (période {r['period'].upper()}, "
        f"{r['start']} → {r['end']})\n".replace(",", " ")
        + f"  • Vaut aujourd'hui : {r['value']:,.0f} €\n".replace(",", " ")
        + f"  • Plus/moins-value : {r['gain']:+,.0f} €  "
        f"(cumulé {r['cumulative']:+.2%}, annualisé {r['annualized']:+.2%})".replace(",", " ")
    )


# ── Comparaison de fonds ───────────────────────────────────────────────────

def compare(isins: list[str], rf: float = 0.0) -> str:
    """Tableau comparatif de plusieurs fonds (rendement, vol, Sharpe, Sortino,
    max drawdown, frais courants), calculé sur la NAV + lu dans la fiche."""
    if not isins:
        return "Erreur : aucun fonds à comparer."
    cols = ["Rdt annualisé", "Volatilité", "Sharpe", "Sortino", "Max DD", "Frais courants"]
    lines = ["Comparaison de fonds :", ""]
    for isin in isins:
        isin = isin.strip()
        try:
            s = load_summary(isin)
            r = load_returns(isin)
            R = metrics.annualized_return(r)
            vol = metrics.annualized_vol(r)
            ongoing = (s.get("costs") or {}).get("ongoing_pct")
            vals = [
                f"{R:+.2%}", f"{vol:.2%}",
                f"{metrics.sharpe_from_returns(r, rf):.3f}",
                f"{metrics.sortino_from_returns(r, rf):.3f}",
                f"{metrics.max_drawdown(r):.2%}",
                f"{ongoing:.2f} %" if ongoing is not None else "n/d",
            ]
            lines.append(f"• {isin} — {s.get('name') or ''}")
            for label, v in zip(cols, vals, strict=True):
                lines.append(f"    {label:14} : {v}")
        except (OSError, ValueError, ZeroDivisionError) as exc:
            lines.append(f"• {isin} — indisponible ({exc})")
        lines.append("")
    return "\n".join(lines).rstrip()


# ── Analyses temporelles (rendements datés) ────────────────────────────────

def _parse_day(s: str) -> datetime:
    """Parse une date « JJ/MM/AAAA » ou « AAAA-MM-JJ »."""
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"date illisible : {s} (attendu JJ/MM/AAAA ou AAAA-MM-JJ)")


def _nav_on_or_before(navs: list[tuple[datetime, float]], when: datetime) -> tuple[datetime, float] | None:
    """Dernière NAV à la date `when` ou juste avant (None si aucune)."""
    found = None
    for d, v in navs:  # navs trié chronologiquement
        if d <= when:
            found = (d, v)
        else:
            break
    return found


def calendar_returns(isin: str) -> list[tuple[int, float]]:
    """Rendement par ANNÉE CALENDAIRE : [(année, perf), …], calculé sur la NAV.

    Perf d'une année = dernière NAV de l'année / dernière NAV de l'année précédente
    − 1 (pour la 1re année, depuis la première NAV disponible)."""
    navs = load_navs(isin)
    if len(navs) < 2:
        raise ValueError(f"historique insuffisant pour {isin}")
    last_by_year: dict[int, float] = {}
    for d, v in navs:
        last_by_year[d.year] = v  # navs trié → la dernière écrasante = fin d'année
    first_nav = navs[0][1]
    out: list[tuple[int, float]] = []
    prev = None
    for year in sorted(last_by_year):
        base = prev if prev is not None else first_nav
        if base:
            out.append((year, last_by_year[year] / base - 1.0))
        prev = last_by_year[year]
    return out


def period_return(isin: str, start: str, end: str) -> dict:
    """Rendement entre deux dates (NAV la plus proche à/avant chaque borne)."""
    navs = load_navs(isin)
    a = _nav_on_or_before(navs, _parse_day(start))
    b = _nav_on_or_before(navs, _parse_day(end))
    if a is None or b is None or a[1] == 0:
        raise ValueError(f"NAV indisponible pour la période {start} → {end} sur {isin}")
    return {"start": a[0].date(), "end": b[0].date(), "start_nav": a[1], "end_nav": b[1],
            "cumulative": b[1] / a[1] - 1.0}


def monthly_returns(isin: str) -> list[tuple[str, float]]:
    """Rendements MENSUELS : [('AAAA-MM', perf), …] depuis la NAV."""
    navs = load_navs(isin)
    if len(navs) < 2:
        raise ValueError(f"historique insuffisant pour {isin}")
    last_by_month: dict[str, float] = {}
    order: list[str] = []
    for d, v in navs:
        key = f"{d.year:04d}-{d.month:02d}"
        if key not in last_by_month:
            order.append(key)
        last_by_month[key] = v
    out, prev = [], navs[0][1]
    for key in order:
        if prev:
            out.append((key, last_by_month[key] / prev - 1.0))
        prev = last_by_month[key]
    return out


def monthly_stats(isin: str) -> dict:
    """Meilleur/pire mois, % de mois positifs, moyenne — depuis les rendements mensuels."""
    m = monthly_returns(isin)
    if not m:
        raise ValueError(f"aucun rendement mensuel pour {isin}")
    vals = [r for _, r in m]
    best = max(m, key=lambda x: x[1])
    worst = min(m, key=lambda x: x[1])
    pos = sum(1 for v in vals if v > 0)
    return {"n_months": len(vals), "best": best, "worst": worst,
            "pct_positive": pos / len(vals), "avg": sum(vals) / len(vals)}


def underwater(isin: str) -> dict:
    """Max drawdown + temps SOUS L'EAU : durée de la pire phase de baisse et si
    elle a été récupérée (retour au plus-haut précédent)."""
    navs = load_navs(isin)
    if len(navs) < 2:
        raise ValueError(f"historique insuffisant pour {isin}")
    peak_val, peak_date = navs[0][1], navs[0][0]
    max_dd, trough_date, dd_peak_date = 0.0, navs[0][0], navs[0][0]
    longest_days, cur_start, recovered = 0, None, True
    for d, v in navs:
        if v >= peak_val:
            if cur_start is not None:  # on vient de récupérer un plus-haut
                longest_days = max(longest_days, (d - cur_start).days)
                cur_start = None
            peak_val, peak_date = v, d
        else:
            if cur_start is None:
                cur_start = peak_date
            dd = v / peak_val - 1.0
            if dd < max_dd:
                max_dd, trough_date, dd_peak_date = dd, d, peak_date
    if cur_start is not None:  # encore sous l'eau à la fin
        recovered = False
        longest_days = max(longest_days, (navs[-1][0] - cur_start).days)
    return {"max_drawdown": -max_dd, "peak_date": dd_peak_date.date(),
            "trough_date": trough_date.date(), "recovered": recovered,
            "longest_underwater_days": longest_days}


def rolling_sharpe(isin: str, window: int = 252, rf: float = 0.0) -> dict:
    """Stabilité du Sharpe GLISSANT sur une fenêtre (252 j ≈ 1 an) : min/max/moyenne/écart-type."""
    r = load_returns(isin)
    w = max(20, int(window))
    if len(r) < w + 1:
        raise ValueError(f"historique trop court pour une fenêtre de {w} jours ({len(r)} points)")
    rolls = [metrics.sharpe_from_returns(r[i - w:i], rf) for i in range(w, len(r) + 1)]
    n = len(rolls)
    mean = sum(rolls) / n
    std = (sum((x - mean) ** 2 for x in rolls) / n) ** 0.5
    return {"window": w, "n": n, "min": min(rolls), "max": max(rolls),
            "mean": mean, "std": std, "last": rolls[-1]}


def correlation_pairs(isins: list[str]) -> list[tuple[str, str, float]]:
    """Corrélation des rendements quotidiens, par paire, sur les DATES COMMUNES."""
    series = {i.strip(): dict(load_navs(i.strip())) for i in isins if i.strip()}
    keys = list(series)
    if len(keys) < 2:
        raise ValueError("au moins 2 fonds requis pour une corrélation")
    out = []
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            ka, kb = keys[a], keys[b]
            common = sorted(set(series[ka]) & set(series[kb]))
            if len(common) < 30:
                raise ValueError(f"trop peu de dates communes entre {ka} et {kb} ({len(common)})")
            na = [series[ka][d] for d in common]
            nb = [series[kb][d] for d in common]
            ra = [na[i] / na[i - 1] - 1 for i in range(1, len(na)) if na[i - 1]]
            rb = [nb[i] / nb[i - 1] - 1 for i in range(1, len(nb)) if nb[i - 1]]
            out.append((ka, kb, metrics.correlation(ra, rb)))
    return out


def nav_audit(isin: str, sample: int = 5) -> dict:
    """Données NAV brutes (auditabilité) : nombre de points, plage, min/max, échantillon."""
    navs = load_navs(isin)
    if not navs:
        raise ValueError(f"aucune NAV pour {isin}")
    vals = [v for _, v in navs]
    k = max(1, int(sample))
    head = [(d.date().isoformat(), v) for d, v in navs[:k]]
    tail = [(d.date().isoformat(), v) for d, v in navs[-k:]]
    return {"n": len(navs), "start": navs[0][0].date(), "end": navs[-1][0].date(),
            "min": min(vals), "max": max(vals), "head": head, "tail": tail}


# ── Screening / classement multi-fonds ─────────────────────────────────────

# Critères calculés sur la série de rendements (NAV). (calcul, plus_grand_est_meilleur)
_SCREEN_METRICS = {
    "sharpe": (lambda r, rf: metrics.sharpe_from_returns(r, rf), True),
    "sortino": (lambda r, rf: metrics.sortino_from_returns(r, rf), True),
    "rendement": (lambda r, rf: metrics.annualized_return(r), True),
    "volatilite": (lambda r, rf: metrics.annualized_vol(r), False),
    "max_drawdown": (lambda r, rf: metrics.max_drawdown(r), False),
}

# Critères lus directement dans la fiche (pas besoin de la NAV). (champ, plus_grand_est_meilleur).
# « les plus gros fonds » = par encours (AUM). `aum` et `encours` sont synonymes.
_SUMMARY_METRICS = {
    "aum": ("aum", True),
    "encours": ("aum", True),
}


def _digits(s: object) -> str:
    return "".join(c for c in str(s) if c.isdigit())


def screen(sort_by: str = "sharpe", top: int = 5, asset_class: str = "",
           sfdr: str = "", sri=None, rf: float = 0.0) -> list[tuple[str, float, str]]:
    """Classe les fonds Amundi par un critère, après filtres optionnels.

    Renvoie [(isin, valeur, nom), …] (top N). Filtre d'abord sur les fiches
    (peu coûteux), ne calcule la métrique que sur les survivants. Le critère est
    soit calculé sur la NAV (sharpe, rendement…), soit lu dans la fiche (aum).
    """
    key = sort_by.strip().lower()
    from_summary = key in _SUMMARY_METRICS
    if not from_summary and key not in _SCREEN_METRICS:
        choices = ", ".join([*_SCREEN_METRICS, *_SUMMARY_METRICS])
        raise ValueError(f"critère inconnu : {sort_by} (au choix : {choices})")
    higher_better = (_SUMMARY_METRICS if from_summary else _SCREEN_METRICS)[key][1]
    sfdr_d = _digits(sfdr)

    results: list[tuple[str, float, str]] = []
    for d in DATASET_DIR.iterdir():
        if not d.is_dir() or not (d / "nav.csv").is_file() or not (d / "summary.json").is_file():
            continue
        s = load_summary(d.name)
        car = s.get("characteristics") or {}
        if asset_class and asset_class.lower() not in str(car.get("Classe d'actifs", "")).lower():
            continue
        if sfdr_d and sfdr_d not in _digits(s.get("sfdr")):
            continue
        if sri is not None and str(sri).strip() != _digits(s.get("risk_sri")):
            continue
        if from_summary:
            raw = s.get(_SUMMARY_METRICS[key][0])
            if raw is None:  # fonds sans encours renseigné → écarté
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
        else:
            try:
                series = load_returns(d.name)
                if len(series) < 250 or has_anomaly(series):  # historique court/NAV corrompue → écarté
                    continue
                value = _SCREEN_METRICS[key][0](series, rf)
            except (ValueError, ZeroDivisionError):
                continue
        results.append((d.name, value, s.get("name") or ""))

    results.sort(key=lambda x: x[1], reverse=higher_better)
    return results[: max(1, int(top))]


def screen_text(sort_by: str = "sharpe", top: int = 5, asset_class: str = "",
                sfdr: str = "", sri=None, rf: float = 0.0) -> str:
    rows = screen(sort_by, top, asset_class, sfdr, sri, rf)
    filt = ", ".join(
        f for f in [
            f"classe={asset_class}" if asset_class else "",
            f"SFDR Art.{_digits(sfdr)}" if _digits(sfdr) else "",
            f"SRI={sri}" if sri is not None else "",
        ] if f
    )
    head = f"Top {len(rows)} fonds par {sort_by}" + (f" ({filt})" if filt else "") + " :"
    key = sort_by.lower()
    pct = key in ("rendement", "volatilite", "max_drawdown")
    aum = key in _SUMMARY_METRICS
    lines = []
    for i, (isin, val, name) in enumerate(rows, 1):
        if aum:
            shown = f"{val / 1e6:,.0f} M€".replace(",", " ")  # encours en millions d'euros
        elif pct:
            shown = f"{val:.2%}"
        else:
            shown = f"{val:.3f}"
        lines.append(f"  {i}. {isin}  {shown}  — {name}")
        # Mini-profil pour CHAQUE fonds du top N (sinon la synthèse ne remplit que
        # la 1re ligne, cf. bug g22) : calculé ici sur les seuls fonds retenus.
        try:
            r = load_returns(isin)
            lines.append(
                f"      rendement {metrics.annualized_return(r):+.2%} · vol {metrics.annualized_vol(r):.2%} "
                f"· Sharpe {metrics.sharpe_from_returns(r, rf):.3f} "
                f"· max DD -{metrics.max_drawdown(r):.2%} · frais "
                + (lambda o: f"{o:.2f} %" if o is not None else "n/d")(
                    (load_summary(isin).get("costs") or {}).get("ongoing_pct")
                )
            )
        except (OSError, ValueError, ZeroDivisionError):
            lines.append("      (profil détaillé indisponible)")
    return head + "\n" + "\n".join(lines)
