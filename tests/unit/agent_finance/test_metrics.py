"""Tests unitaires des fonctions de calcul PURES (aucun LLM)."""

import math

import pytest

from agent.finance import metrics as m

# ── Ratios scalaires (valeurs exactes) ────────────────────────────────────


def test_sharpe_exact():
    # (0.08 - 0.02) / 0.10 = 0.6
    assert m.sharpe(0.08, 0.10, 0.02) == pytest.approx(0.6)


def test_sortino_starr_martin_exact():
    assert m.sortino(0.08, 0.04, 0.02) == pytest.approx(1.5)
    assert m.starr(0.08, 0.05, 0.02) == pytest.approx(1.2)
    assert m.martin(0.08, 0.04, 0.02) == pytest.approx(1.5)


def test_ratio_guards_on_nonpositive_risk():
    for fn in (m.sharpe, m.sortino, m.starr, m.martin):
        with pytest.raises(ValueError):
            fn(0.08, 0.0, 0.02)
        with pytest.raises(ValueError):
            fn(0.08, -0.1, 0.02)


# ── Briques de risque / rendement ─────────────────────────────────────────


def test_annualized_return_and_vol():
    r = [0.01, -0.02, 0.03, -0.01]
    assert m.annualized_return(r, periods_per_year=4) == pytest.approx(0.01)
    # vol > 0 et croît avec √ppy
    assert m.annualized_vol(r, periods_per_year=4) > m.annualized_vol(r, periods_per_year=1)


def test_downside_deviation_counts_only_losses():
    # [0.02, -0.03], MAR=0 → seul -0.03 compte : sqrt(mean(0, 0.03^2))
    dd = m.downside_deviation([0.02, -0.03], mar_annual=0.0, periods_per_year=1)
    assert dd == pytest.approx(math.sqrt((0.03**2) / 2))


def test_cvar_worst_tail():
    # alpha=0.25 sur 4 points → 1 pire point = -0.05 → CVaR = 0.05
    assert m.cvar([-0.05, -0.01, 0.02, 0.03], alpha=0.25) == pytest.approx(0.05)


def test_max_drawdown_and_ulcer():
    r = [0.1, -0.5]  # equity 1.1 → 0.55 → DD = -0.5
    assert m.max_drawdown(r) == pytest.approx(0.5)
    # drawdowns [0, -0.5] → Ulcer = sqrt(mean(0, 0.25))
    assert m.ulcer_index(r) == pytest.approx(math.sqrt(0.125))


def test_monotonic_path_has_zero_drawdown():
    r = [0.01, 0.02, 0.005]  # courbe strictement croissante
    assert m.max_drawdown(r) == pytest.approx(0.0)
    assert m.ulcer_index(r) == pytest.approx(0.0)


# ── Ratios depuis une série ───────────────────────────────────────────────


def test_sharpe_from_returns_matches_pieces():
    r = [0.01, -0.02, 0.03, -0.01, 0.015, -0.005]
    R = m.annualized_return(r, 12)
    sigma = m.annualized_vol(r, 12)
    assert m.sharpe_from_returns(r, rf=0.0, periods_per_year=12) == pytest.approx(R / sigma)


def test_from_returns_guard_on_constant_series():
    # série constante → σ = 0 → ValueError remontée
    with pytest.raises(ValueError):
        m.sharpe_from_returns([0.001] * 10, rf=0.0, periods_per_year=10)


def test_empty_series_raises():
    with pytest.raises(ValueError):
        m.annualized_return([])


def test_var_historical_quantile():
    # 100 points -10%..+89% ; VaR 5% = 5e pire (index 4) en magnitude positive.
    r = [(-10 + i) / 100 for i in range(100)]  # -0.10, -0.09, …, 0.89
    assert m.var_historical(r, 0.05) == pytest.approx(0.06)  # 5e valeur = -0.06
    assert m.var_historical(r, 0.01) == pytest.approx(0.10)  # pire = -0.10


def test_skewness_sign():
    # queue gauche (une grosse perte) → skewness négative
    assert m.skewness([0.01, 0.01, 0.01, 0.01, -0.2]) < 0


def test_kurtosis_excess_fat_tail_positive():
    # distribution à queues épaisses → kurtosis excédentaire > 0
    assert m.kurtosis_excess([0.0, 0.0, 0.0, 0.0, 0.0, 0.5, -0.5]) > 0


def test_correlation_perfect_and_inverse():
    a = [0.01, -0.02, 0.03, -0.01]
    assert m.correlation(a, a) == pytest.approx(1.0)
    assert m.correlation(a, [-x for x in a]) == pytest.approx(-1.0)


def test_correlation_length_mismatch_raises():
    with pytest.raises(ValueError):
        m.correlation([0.01, 0.02], [0.01])
