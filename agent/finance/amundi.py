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
from datetime import datetime, timedelta
from pathlib import Path

from agent.finance import metrics

# documents/amundi/ à la racine du dépôt (agent/finance/amundi.py → parents[2]).
DATASET_DIR = Path(__file__).resolve().parents[2] / "documents" / "amundi"


def fund_dir(isin: str) -> Path:
    return DATASET_DIR / isin.strip()


def has_nav(isin: str) -> bool:
    return (fund_dir(isin) / "nav.csv").is_file()


def has_summary(isin: str) -> bool:
    return (fund_dir(isin) / "summary.json").is_file()


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


def load_returns(isin: str) -> list[float]:
    """Série de rendements quotidiens = variation relative de la NAV d'un jour à l'autre."""
    navs = [v for _, v in load_navs(isin)]
    if len(navs) < 2:
        raise ValueError(f"historique NAV insuffisant pour {isin} ({len(navs)} point(s))")
    return [navs[i] / navs[i - 1] - 1 for i in range(1, len(navs)) if navs[i - 1] != 0]


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
    # Frais (bloc `costs`) — central pour un gérant.
    costs = d.get("costs") or {}
    cost_labels = [
        ("Frais d'entrée", "entry_pct"), ("Frais de sortie", "exit_pct"),
        ("Frais courants", "ongoing_pct"), ("Coûts de transaction", "transaction_pct"),
        ("Commission de surperformance", "performance_pct"),
    ]
    for lbl, key in cost_labels:
        if costs.get(key) is not None and keep(lbl):
            lines.append(f"{lbl} : {costs[key]} %")
    # Performance YTD (depuis asset_allocation).
    for item in d.get("asset_allocation") or []:
        lbl = item.get("label", "")
        if "perf" in lbl.lower() and keep(lbl):
            lines.append(f"{lbl} : {item.get('pct')}")

    if not lines:
        return f"Aucun champ correspondant à « {fields} » dans la fiche de {isin}."
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


# ── Screening / classement multi-fonds ─────────────────────────────────────

# (calcul, plus_grand_est_meilleur)
_SCREEN_METRICS = {
    "sharpe": (lambda r, rf: metrics.sharpe_from_returns(r, rf), True),
    "sortino": (lambda r, rf: metrics.sortino_from_returns(r, rf), True),
    "rendement": (lambda r, rf: metrics.annualized_return(r), True),
    "volatilite": (lambda r, rf: metrics.annualized_vol(r), False),
    "max_drawdown": (lambda r, rf: metrics.max_drawdown(r), False),
}


def _digits(s: object) -> str:
    return "".join(c for c in str(s) if c.isdigit())


def screen(sort_by: str = "sharpe", top: int = 5, asset_class: str = "",
           sfdr: str = "", sri=None, rf: float = 0.0) -> list[tuple[str, float, str]]:
    """Classe les fonds Amundi par un critère, après filtres optionnels.

    Renvoie [(isin, valeur, nom), …] (top N). Filtre d'abord sur les fiches
    (peu coûteux), ne calcule la métrique que sur les survivants.
    """
    key = sort_by.strip().lower()
    if key not in _SCREEN_METRICS:
        raise ValueError(f"critère inconnu : {sort_by} (au choix : {', '.join(_SCREEN_METRICS)})")
    compute, higher_better = _SCREEN_METRICS[key]
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
        try:
            series = load_returns(d.name)
            if len(series) < 250:  # < ~1 an d'historique → ratios non fiables, écartés
                continue
            value = compute(series, rf)
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
    pct = sort_by.lower() in ("rendement", "volatilite", "max_drawdown")
    lines = []
    for i, (isin, val, name) in enumerate(rows, 1):
        shown = f"{val:.2%}" if pct else f"{val:.3f}"
        lines.append(f"  {i}. {isin}  {shown}  — {name}")
    return head + "\n" + "\n".join(lines)
