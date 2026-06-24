"""Calcul PUR des métriques d'optimisation — aucun LLM, aucun I/O.

Conventions (cf. `docs/metriques_optimisation_gold.md`) :

- `R`, `rf`, `sigma` sont **annualisés** et exprimés en **décimal** (0.08 = 8 %).
- `returns` = série de rendements **par période** (décimal), ex. journaliers.
- `periods_per_year` (ppy) : 252 (journalier), 52 (hebdo), 12 (mensuel).
- `alpha` (queue CVaR) = 0.05 par défaut (5 %).

Toutes les fonctions lèvent `ValueError` sur une entrée invalide (série vide,
dénominateur nul) : la couche outil (`agent/tools.py`) attrape et renvoie un
message « Erreur … » conforme à la convention des autres outils.
"""

from __future__ import annotations

import math
from statistics import fmean, pstdev

# ── Briques de risque / rendement ─────────────────────────────────────────


def _check_series(returns: list[float]) -> list[float]:
    series = [float(r) for r in returns]
    if not series:
        raise ValueError("série de rendements vide")
    return series


def annualized_return(returns: list[float], periods_per_year: int = 252) -> float:
    """Rendement arithmétique annualisé = moyenne des rendements × ppy."""
    return fmean(_check_series(returns)) * periods_per_year


def annualized_vol(returns: list[float], periods_per_year: int = 252) -> float:
    """Volatilité annualisée = écart-type (population) × √ppy."""
    series = _check_series(returns)
    if len(series) < 2:
        raise ValueError("au moins 2 points requis pour une volatilité")
    return pstdev(series) * math.sqrt(periods_per_year)


def downside_deviation(
    returns: list[float], mar_annual: float = 0.0, periods_per_year: int = 252
) -> float:
    """Écart-type des seuls rendements SOUS le seuil minimal acceptable (MAR).

    `mar_annual` est annualisé (souvent `rf`) ; ramené par période en interne.
    Dénominateur = nombre TOTAL de points (convention Sortino standard).
    """
    series = _check_series(returns)
    mar_period = mar_annual / periods_per_year
    downside = [min(0.0, r - mar_period) ** 2 for r in series]
    return math.sqrt(fmean(downside)) * math.sqrt(periods_per_year)


def cvar(returns: list[float], alpha: float = 0.05) -> float:
    """CVaR / Expected Shortfall **par période** : perte moyenne (valeur positive)
    dans les `alpha` pires rendements.

    Renvoie une magnitude positive (une perte de 3 % → 0.03). Pour un usage
    annualisé (ratio STARR), voir `cvar_annualized`.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha doit être dans ]0, 1[")
    series = sorted(_check_series(returns))
    n_tail = max(1, math.floor(len(series) * alpha))
    tail = series[:n_tail]  # les pires (plus négatifs)
    return -fmean(tail)


def cvar_annualized(
    returns: list[float], alpha: float = 0.05, periods_per_year: int = 252
) -> float:
    """CVaR annualisée (approximation √-temps, cf. caveat du doc de référence)."""
    return cvar(returns, alpha) * math.sqrt(periods_per_year)


def _equity_curve(returns: list[float]) -> list[float]:
    curve, level = [], 1.0
    for r in _check_series(returns):
        level *= 1.0 + r
        curve.append(level)
    return curve


def _drawdown_series(returns: list[float]) -> list[float]:
    """Drawdown (≤ 0) à chaque pas : (niveau − plus-haut courant) / plus-haut."""
    peak, draws = -math.inf, []
    for level in _equity_curve(returns):
        peak = max(peak, level)
        draws.append(level / peak - 1.0)
    return draws


def max_drawdown(returns: list[float]) -> float:
    """Drawdown maximal en **magnitude positive** (perte de 20 % → 0.20)."""
    return -min(_drawdown_series(returns))


def ulcer_index(returns: list[float]) -> float:
    """Ulcer Index = racine de la moyenne des drawdowns (en %) au carré.

    Capture profondeur ET durée des pertes sous le dernier plus-haut. Exprimé
    en décimal (un UI de 0.07 ≈ 7 %).
    """
    draws = _drawdown_series(returns)
    return math.sqrt(fmean([d**2 for d in draws]))


# ── Famille 1 — Ratios rendement / risque (forme scalaire) ────────────────


def _ratio(excess: float, risk: float, risk_name: str) -> float:
    if risk <= 0:
        raise ValueError(f"{risk_name} doit être strictement positif (reçu {risk})")
    return excess / risk


def sharpe(R: float, sigma: float, rf: float = 0.0) -> float:
    """Sharpe = (R − rf) / σ (volatilité totale)."""
    return _ratio(R - rf, sigma, "la volatilité σ")


def sortino(R: float, downside_dev: float, rf: float = 0.0) -> float:
    """Sortino = (R − rf) / σ_baisse (risque de baisse uniquement)."""
    return _ratio(R - rf, downside_dev, "l'écart-type baissier")


def starr(R: float, cvar_value: float, rf: float = 0.0) -> float:
    """STARR = (R − rf) / CVaR (risque de queue)."""
    return _ratio(R - rf, cvar_value, "la CVaR")


def martin(R: float, ulcer: float, rf: float = 0.0) -> float:
    """Martin = (R − rf) / Ulcer (douleur de drawdown)."""
    return _ratio(R - rf, ulcer, "l'Ulcer Index")


# ── Famille 1 — Ratios depuis une série de rendements ─────────────────────


def sharpe_from_returns(
    returns: list[float], rf: float = 0.0, periods_per_year: int = 252
) -> float:
    R = annualized_return(returns, periods_per_year)
    sigma = annualized_vol(returns, periods_per_year)
    return sharpe(R, sigma, rf)


def sortino_from_returns(
    returns: list[float], rf: float = 0.0, periods_per_year: int = 252
) -> float:
    R = annualized_return(returns, periods_per_year)
    dd = downside_deviation(returns, mar_annual=rf, periods_per_year=periods_per_year)
    return sortino(R, dd, rf)


def starr_from_returns(
    returns: list[float], rf: float = 0.0, alpha: float = 0.05, periods_per_year: int = 252
) -> float:
    R = annualized_return(returns, periods_per_year)
    es = cvar_annualized(returns, alpha, periods_per_year)
    return starr(R, es, rf)


def martin_from_returns(
    returns: list[float], rf: float = 0.0, periods_per_year: int = 252
) -> float:
    R = annualized_return(returns, periods_per_year)
    return martin(R, ulcer_index(returns), rf)
