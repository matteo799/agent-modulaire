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


# Régression : demander « frais » ne renvoyait que les libellés contenant ce mot,
# donc ni la commission de surperformance ni les coûts de transaction. Une fiche
# de frais tronquée a l'air complète — c'est pire qu'une absence de réponse.
# Détecté par tests/agent_eval/score_accuracy.py (question g02) ; la couverture
# d'outils, elle, notait cette question conforme.
_COSTS = {
    "entry_pct": 5.0, "exit_pct": 0.0, "ongoing_pct": 1.295,
    "transaction_pct": 0.044, "performance_pct": 20.0,
}


@pytest.mark.parametrize("asked", ["frais", "coûts", "commission de surperformance", ""])
def test_summary_fees_are_returned_as_a_whole_block(amundi_tmp, asked):
    _write_fund(amundi_tmp, "COSTS0000001",
                summary={"isin": "COSTS0000001", "name": "Fee Fund", "costs": _COSTS})
    out = amundi.summary_text("COSTS0000001", fields=asked)
    assert "Commission de surperformance : 20.0 %" in out
    assert "Coûts de transaction : 0.044 %" in out
    assert "Frais courants : 1.295 %" in out


def test_summary_unrelated_field_does_not_pull_in_the_fee_block(amundi_tmp):
    _write_fund(amundi_tmp, "COSTS0000002",
                summary={"isin": "COSTS0000002", "name": "Fee Fund",
                         "sfdr": "Art. 8", "costs": _COSTS})
    out = amundi.summary_text("COSTS0000002", fields="sfdr")
    assert "Art. 8" in out
    assert "Commission" not in out and "Frais" not in out


def test_summary_does_not_repeat_a_field_present_in_characteristics(amundi_tmp):
    _write_fund(amundi_tmp, "DUPE00000001",
                summary={"isin": "DUPE00000001", "benchmark": "MSCI World",
                         "characteristics": {"Indice de référence": "MSCI World"}})
    assert amundi.summary_text("DUPE00000001").count("MSCI World") == 1


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


def test_find_fund_resolves_unique_name(amundi_tmp):
    _write_fund(amundi_tmp, "FR0000000001", summary={"isin": "FR0000000001", "name": "Amundi Actions Monde"})
    _write_fund(amundi_tmp, "FR0000000002", summary={"isin": "FR0000000002", "name": "Amundi Oblig Euro"})
    out = TOOLS["find_fund"]["function"]("actions monde")
    assert "FR0000000001" in out and "FR0000000002" not in out


def test_find_fund_lists_ambiguous(amundi_tmp):
    _write_fund(amundi_tmp, "FR0000000003", summary={"isin": "FR0000000003", "name": "Amundi Cash EUR - A"})
    _write_fund(amundi_tmp, "FR0000000004", summary={"isin": "FR0000000004", "name": "Amundi Cash EUR - I"})
    out = TOOLS["find_fund"]["function"]("cash eur")
    assert "FR0000000003" in out and "FR0000000004" in out
    assert "préciser" in out.lower()


def test_find_fund_none(amundi_tmp):
    _write_fund(amundi_tmp, "FR0000000005", summary={"isin": "FR0000000005", "name": "Amundi Actions Monde"})
    assert "aucun fonds" in TOOLS["find_fund"]["function"]("bitcoin").lower()


def test_invested_value_amount_not_treated_as_percent(amundi_tmp):
    # 10 000 € NE doit PAS être divisé par 100 (piège _to_decimal).
    _daily(amundi_tmp, "INVEST000001", 400, 0.0005)
    out = TOOLS["invested_value"]["function"]("INVEST000001", 10000, "1y")
    assert "10 000 €" in out and "100 €" not in out


def test_invested_value_resolves_by_name(amundi_tmp):
    _daily(amundi_tmp, "INVEST000002", 400, 0.0005)
    # _daily nomme le fonds "Fund INVEST000002" → résoluble par nom.
    out = TOOLS["invested_value"]["function"]("Fund INVEST000002", 5000, "1y")
    assert "INVEST000002" in out and "5 000 €" in out


def _wiggly(base, isin):
    """Fonds avec hausses ET baisses (Sortino/Sharpe définis)."""
    from datetime import date, timedelta
    d0, nav, rows = date(2023, 1, 1), 100.0, ["date;nav"]
    for i in range(260):
        nav *= 1 + (0.002 if i % 2 == 0 else -0.001)  # alterne + et -
        rows.append(f"{(d0 + timedelta(days=i)).strftime('%d/%m/%Y')};{nav:.4f}")
    d = base / isin
    d.mkdir()
    (d / "nav.csv").write_text("\n".join(rows), encoding="utf-8")
    (d / "summary.json").write_text(
        json.dumps({"isin": isin, "name": f"Fund {isin}", "costs": {"ongoing_pct": 0.5}}),
        encoding="utf-8")


def test_compare_funds_table(amundi_tmp):
    _wiggly(amundi_tmp, "CMP000000001")
    _wiggly(amundi_tmp, "CMP000000002")
    out = TOOLS["compare_funds"]["function"]("CMP000000001, CMP000000002")
    assert "CMP000000001" in out and "CMP000000002" in out
    for label in ("Rdt annualisé", "Volatilité", "Sharpe", "Max DD", "Frais courants"):
        assert label in out


def test_compare_funds_needs_two(amundi_tmp):
    assert "au moins 2" in TOOLS["compare_funds"]["function"]("FR0000000001").lower()


def test_screen_by_aum(amundi_tmp):
    _daily(amundi_tmp, "AUM000000001", 300, 0.0005)
    _daily(amundi_tmp, "AUM000000002", 300, 0.0005)
    # On surcharge l'encours dans les fiches (écrites par _daily).
    for isin, aum in [("AUM000000001", 1_000_000.0), ("AUM000000002", 9_000_000.0)]:
        s = json.loads((amundi_tmp / isin / "summary.json").read_text(encoding="utf-8"))
        s["aum"] = aum
        (amundi_tmp / isin / "summary.json").write_text(json.dumps(s), encoding="utf-8")
    out = TOOLS["screen_funds"]["function"](sort_by="aum", top=2)
    assert out.index("AUM000000002") < out.index("AUM000000001")  # plus gros encours en tête
    assert "M€" in out


def test_calendar_returns(amundi_tmp):
    # 100 (fin 2019) → 110 (fin 2020) → 99 (fin 2021) : +10 % puis -10 %.
    _write_fund(amundi_tmp, "CAL000000001", navs=[
        ("31/12/2019", 100.0), ("30/06/2020", 105.0), ("31/12/2020", 110.0),
        ("31/12/2021", 99.0),
    ])
    rows = dict(amundi.calendar_returns("CAL000000001"))
    assert rows[2020] == pytest.approx(0.10)
    assert rows[2021] == pytest.approx(-0.10)


def test_period_return_and_year_shortcut(amundi_tmp):
    _write_fund(amundi_tmp, "PER000000001", navs=[
        ("31/12/2021", 200.0), ("15/06/2022", 180.0), ("30/12/2022", 220.0),
    ])
    out = TOOLS["fund_period"]["function"]("PER000000001", "2022")  # année entière
    assert "+10.00%" in out  # 220/200 - 1


def test_monthly_stats(amundi_tmp):
    _write_fund(amundi_tmp, "MON000000001", navs=[
        ("31/01/2020", 100.0), ("29/02/2020", 110.0), ("31/03/2020", 99.0),
        ("30/04/2020", 108.9),
    ])
    out = TOOLS["fund_monthly"]["function"]("MON000000001")
    assert "Meilleur mois" in out and "Pire mois" in out and "positifs" in out


def test_underwater_recovers(amundi_tmp):
    # baisse puis retour au-dessus du sommet → récupéré.
    _write_fund(amundi_tmp, "UND000000001", navs=[
        ("01/01/2020", 100.0), ("01/02/2020", 80.0), ("01/03/2020", 105.0),
    ])
    out = TOOLS["fund_underwater"]["function"]("UND000000001")
    assert "Max drawdown" in out and "récupéré" in out


def test_tail_risk_panel(amundi_tmp):
    _wiggly(amundi_tmp, "TAIL00000001")
    out = TOOLS["fund_tail_risk"]["function"]("TAIL00000001")
    for label in ("VaR 95", "VaR 99", "CVaR", "Skewness", "Kurtosis"):
        assert label in out


def test_correlation_pair(amundi_tmp):
    _wiggly(amundi_tmp, "COR000000001")
    _wiggly(amundi_tmp, "COR000000002")  # séries identiques → corrélation ≈ +1
    out = TOOLS["funds_correlation"]["function"]("COR000000001, COR000000002")
    assert "COR000000001 ↔ COR000000002" in out and "+1.00" in out


def test_nav_series_audit(amundi_tmp):
    _write_fund(amundi_tmp, "NAV000000001", navs=[
        ("01/01/2020", 100.0), ("02/01/2020", 101.0), ("03/01/2020", 102.0),
    ])
    out = TOOLS["fund_nav_series"]["function"]("NAV000000001", 1)
    assert "3 points" in out and "Premiers" in out and "Derniers" in out


def test_fees_projection(amundi_tmp):
    _write_fund(amundi_tmp, "FEE000000001",
                summary={"isin": "FEE000000001", "name": "F", "costs": {"ongoing_pct": 1.0}})
    out = TOOLS["fees_projection"]["function"]("FEE000000001", 100000, 10)
    assert "100 000 €" in out and "Coût cumulé" in out


def test_rolling_sharpe_needs_window(amundi_tmp):
    _wiggly(amundi_tmp, "ROLL00000001")  # 260 points
    out = TOOLS["fund_rolling_sharpe"]["function"]("ROLL00000001", 60)
    assert "Sharpe glissant" in out and "Moyenne" in out


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
