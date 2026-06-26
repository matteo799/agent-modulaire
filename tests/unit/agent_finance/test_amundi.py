"""Tests du dataset Amundi : lecture nav.csv → rendements, branchement des outils.

Dataset temporaire (monkeypatch de DATASET_DIR) → déterministe, indépendant des
24 Mo réels de documents/amundi/.
"""
import json

import pytest

from agent.finance import amundi
from agent.tools import TOOLS


@pytest.fixture
def amundi_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(amundi, "DATASET_DIR", tmp_path)
    return tmp_path


def _write_fund(base, isin, navs=None, summary=None):
    d = base / isin
    d.mkdir(parents=True)
    if navs is not None:
        body = "\n".join(["date;nav"] + [f"{dt};{v}" for dt, v in navs])
        (d / "nav.csv").write_text("﻿" + body, encoding="utf-8")  # BOM comme les vrais fichiers
    if summary is not None:
        (d / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_load_returns_computes_relative_changes(amundi_tmp):
    _write_fund(amundi_tmp, "TEST00000001", navs=[
        ("01/01/2020", 100.0), ("02/01/2020", 110.0), ("03/01/2020", 99.0),
    ])
    # 110/100-1 = 0.10 ; 99/110-1 = -0.10
    assert amundi.load_returns("TEST00000001") == pytest.approx([0.10, -0.10])


def test_load_navs_sorts_and_skips_bad_rows(amundi_tmp):
    _write_fund(amundi_tmp, "TEST00000002", navs=[
        ("03/01/2020", 99.0), ("01/01/2020", 100.0), ("bad", "x"), ("02/01/2020", 110.0),
    ])
    assert [v for _, v in amundi.load_navs("TEST00000002")] == [100.0, 110.0, 99.0]


def test_metric_tool_computes_from_navcsv(amundi_tmp):
    _write_fund(amundi_tmp, "FUND00000001",
                navs=[(f"0{i}/01/2020", 100 + i * (1 if i % 2 else -1)) for i in range(1, 9)])
    out = TOOLS["metric_sharpe"]["function"](source="FUND00000001", rf=0.0)
    assert "Ratio de Sharpe =" in out and "FUND00000001" in out


def test_metric_guard_when_no_nav(amundi_tmp):
    out = TOOLS["metric_sortino"]["function"](source="ABSENT0000")
    assert "impossible" in out.lower()
    assert "= -" not in out and "= 0." not in out  # aucune valeur inventée


def test_fund_summary_reads_json(amundi_tmp):
    _write_fund(amundi_tmp, "SUMMARY00001",
                summary={"isin": "SUMMARY00001", "name": "Test Fund", "sfdr": "Art. 8", "risk_sri": 3})
    out = TOOLS["fund_summary"]["function"]("SUMMARY00001")
    assert "Test Fund" in out and "Art. 8" in out


def test_fund_summary_missing(amundi_tmp):
    assert "aucune fiche" in TOOLS["fund_summary"]["function"]("NOPE0000000").lower()


def test_fund_stats_panel(amundi_tmp):
    _write_fund(amundi_tmp, "STATS0000001",
                navs=[(f"{i:02d}/01/2020", 100 + (i % 3)) for i in range(1, 20)])
    out = TOOLS["fund_stats"]["function"]("STATS0000001", rf=2)
    assert "profil risque/rendement" in out.lower()
    for label in ("Volatilité", "Sharpe", "Sortino", "Max drawdown"):
        assert label in out


def test_fund_stats_guard_no_nav(amundi_tmp):
    assert "aucun historique" in TOOLS["fund_stats"]["function"]("ABSENT0000").lower()


def _daily(base, isin, n, drift):
    """Crée un fonds avec n NAV à variation quotidienne constante + une fiche action Art. 8."""
    from datetime import date, timedelta
    d0, nav, rows = date(2023, 1, 1), 100.0, ["date;nav"]
    for i in range(n):
        nav *= 1 + drift
        rows.append(f"{(d0 + timedelta(days=i)).strftime('%d/%m/%Y')};{nav:.4f}")
    d = base / isin
    d.mkdir()
    (d / "nav.csv").write_text("\n".join(rows), encoding="utf-8")
    (d / "summary.json").write_text(
        json.dumps({"isin": isin, "name": f"Fund {isin}", "sfdr": "Art. 8",
                    "characteristics": {"Classe d'actifs": "action"}}),
        encoding="utf-8")


def test_fund_performance_periods(amundi_tmp):
    _daily(amundi_tmp, "PERF00000001", 400, 0.0003)
    out = TOOLS["fund_performance"]["function"]("PERF00000001", periods="1y,all")
    assert "1Y" in out and "ALL" in out and "%" in out


def test_screen_funds_ranks_and_filters(amundi_tmp):
    _daily(amundi_tmp, "AAAA00000001", 300, 0.0005)  # progresse plus vite
    _daily(amundi_tmp, "BBBB00000001", 300, 0.0001)  # progresse moins vite
    out = TOOLS["screen_funds"]["function"](sort_by="rendement", top=2, asset_class="action", sfdr="8")
    assert "Top" in out
    assert out.index("AAAA00000001") < out.index("BBBB00000001")  # meilleur rendement en tête


def test_has_anomaly():
    assert amundi.has_anomaly([0.01, 0.6, -0.02]) is True  # +60 % en un jour = aberrant
    assert amundi.has_anomaly([0.01, -0.02, 0.03]) is False


def test_screen_excludes_corrupted_funds(amundi_tmp):
    from datetime import date, timedelta
    _daily(amundi_tmp, "GOOD00000001", 300, 0.0005)
    # Fonds corrompu : la NAV décuple en un jour → variation > 50 %.
    d, nav, rows, d0 = amundi_tmp / "BADX00000001", 100.0, ["date;nav"], date(2023, 1, 1)
    d.mkdir()
    for i in range(300):
        nav = nav * 10 if i == 150 else nav * 1.0005
        rows.append(f"{(d0 + timedelta(days=i)).strftime('%d/%m/%Y')};{nav:.4f}")
    (d / "nav.csv").write_text("\n".join(rows), encoding="utf-8")
    (d / "summary.json").write_text(
        json.dumps({"isin": "BADX00000001", "name": "Corrompu", "sfdr": "Art. 8",
                    "characteristics": {"Classe d'actifs": "action"}}), encoding="utf-8")
    out = TOOLS["screen_funds"]["function"](sort_by="rendement", top=5, asset_class="action", sfdr="8")
    assert "GOOD00000001" in out
    assert "BADX00000001" not in out  # exclu : NAV aberrante
