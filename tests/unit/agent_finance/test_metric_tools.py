"""Tests des outils-métriques (calcul, garde-fou honnête, coercion).

Aucun appel LLM/RAG : on n'utilise jamais `source`, donc `rag_search` n'est
jamais déclenché.
"""

from agent.tools import TOOLS


def _sharpe(**kw):
    return TOOLS["metric_sharpe"]["function"](**kw)


def test_metric_tools_are_registered():
    for key in ("sharpe", "sortino", "starr", "martin", "rdt_max_cvar", "rdt_max_drawdown"):
        assert f"metric_{key}" in TOOLS


def test_sharpe_computes_from_scalars():
    out = _sharpe(R=0.08, sigma=0.10, rf=0.02)
    assert "0.6000" in out


def test_sharpe_accepts_percent_strings():
    out = _sharpe(R="8%", sigma="10%", rf="2%")
    assert "0.6000" in out


def test_sharpe_honest_guard_without_data():
    out = _sharpe()  # aucune donnée, aucun source
    assert "impossible" in out.lower()
    assert "Caractéristiques" in out
    # ne doit pas inventer un chiffre
    assert "= 0." not in out


def test_sortino_from_returns():
    out = TOOLS["metric_sortino"]["function"](
        returns=[0.01, -0.02, 0.03, -0.01, 0.015, -0.005], rf=0.0, periods_per_year=12
    )
    assert "Ratio de Sortino =" in out


def test_budget_family_is_explanatory_only():
    out = TOOLS["metric_rdt_max_cvar"]["function"]()
    assert "n'est pas disponible" in out
    assert "univers multi-fonds" in out


def test_unknown_extra_args_are_tolerated():
    # le planner peut passer un argument parasite : ne doit pas lever
    out = _sharpe(R=0.08, sigma=0.10, rf=0.02, query="bla")
    assert "0.6000" in out
