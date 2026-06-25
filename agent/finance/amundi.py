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
from datetime import datetime
from pathlib import Path

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
    for item in d.get("asset_allocation") or []:
        lbl = item.get("label", "")
        if "perf" in lbl.lower() and keep(lbl):
            lines.append(f"{lbl} : {item.get('pct')}")

    if not lines:
        return f"Aucun champ correspondant à « {fields} » dans la fiche de {isin}."
    return f"Fiche {isin} :\n" + "\n".join(f"  • {ln}" for ln in lines)
