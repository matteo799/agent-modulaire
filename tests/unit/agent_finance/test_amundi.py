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
