"""Overfitting-aware statistics for parameter optimization (Bailey & López de Prado).

When you optimize over N parameter combinations and report the single best Sharpe, that number is
inflated by selection: even with **no real edge**, the maximum of N noisy Sharpe ratios is large.
This module quantifies and removes that inflation so a headline like "Sharpe 8.2" is contextualized.

Two tools:
  * `expected_max_sharpe(n_trials, sharpe_std)` — the Sharpe you'd expect to see from the *best* of
    N trials under the null of zero true skill. This is the benchmark the winner must beat.
  * `deflated_sharpe_ratio(...)` — the probability the strategy's true (annualized) Sharpe exceeds
    that selection-implied benchmark, accounting for sample length, skew, and fat tails. DSR > 0.95
    means the result is unlikely to be a fluke of the search.

References: Bailey & López de Prado, "The Deflated Sharpe Ratio" (2014); "The Probability of
Backtest Overfitting" (2015).
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence

import numpy as np

try:
    from scipy.stats import norm
    _PPF = norm.ppf
    _CDF = norm.cdf
except Exception:  # scipy not available — use math.erf-based fallbacks
    def _CDF(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _PPF(p: float) -> float:
        # Acklam's rational approximation to the inverse normal CDF (good to ~1e-9).
        if p <= 0.0:
            return -math.inf
        if p >= 1.0:
            return math.inf
        a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
             1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
             6.680131188771972e+01, -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
             -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
             3.754408661907416e+00]
        plow, phigh = 0.02425, 1 - 0.02425
        if p < plow:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p > phigh:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                    ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

_EULER_MASCHERONI = 0.5772156649015329


def expected_max_sharpe(n_trials: int, sharpe_std: float) -> float:
    """Expected maximum of `n_trials` IID Sharpe ratios under the null of zero true skill.

    Bailey & López de Prado's extreme-value estimate:
        E[max] ≈ σ · [ (1-γ)·Φ⁻¹(1 - 1/N) + γ·Φ⁻¹(1 - 1/(N·e)) ]
    where σ is the cross-trial std of Sharpe ratios and γ is the Euler-Mascheroni constant. This is
    the benchmark the winning Sharpe must beat to be considered real. Same frequency as `sharpe_std`.
    """
    if n_trials < 2 or sharpe_std <= 0:
        return 0.0
    g = _EULER_MASCHERONI
    term = (1 - g) * _PPF(1 - 1.0 / n_trials) + g * _PPF(1 - 1.0 / (n_trials * math.e))
    return sharpe_std * term


def probabilistic_sharpe_ratio(
    observed_sharpe: float,
    benchmark_sharpe: float,
    n_obs: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """P(true Sharpe > benchmark) given the estimate's standard error. All Sharpes per-observation.

    PSR = Φ( (SR̂ - SR*)·√(n-1) / √(1 - skew·SR̂ + (kurt-1)/4·SR̂²) ).
    Pass *non-annualized* (per-period) Sharpes; `kurtosis` is the raw (normal = 3) value.
    """
    if n_obs < 2:
        return float("nan")
    denom = 1.0 - skew * observed_sharpe + ((kurtosis - 1.0) / 4.0) * observed_sharpe ** 2
    denom = max(denom, 1e-12)
    z = (observed_sharpe - benchmark_sharpe) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    return float(_CDF(z))


def deflated_sharpe_ratio(
    observed_sharpe_annual: float,
    n_obs: int,
    n_trials: int,
    trial_sharpes_annual: Optional[Sequence[float]] = None,
    sharpe_std_annual: Optional[float] = None,
    periods_per_year: int = 252,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> Dict[str, float]:
    """Deflate an annualized Sharpe for multiple testing. Returns a dict of diagnostics.

    Provide either the full list of trial Sharpes (preferred — their std drives the benchmark) or a
    precomputed cross-trial Sharpe std. Sharpes are passed annualized and de-annualized internally.
    """
    if sharpe_std_annual is None:
        if trial_sharpes_annual is None or len(trial_sharpes_annual) < 2:
            raise ValueError("provide trial_sharpes_annual (>=2) or sharpe_std_annual")
        sharpe_std_annual = float(np.nanstd(np.asarray(trial_sharpes_annual, dtype=float), ddof=1))

    scale = math.sqrt(periods_per_year)
    obs = observed_sharpe_annual / scale          # per-period
    sr_std = sharpe_std_annual / scale            # per-period
    sr_star = expected_max_sharpe(n_trials, sr_std)

    dsr = probabilistic_sharpe_ratio(obs, sr_star, n_obs, skew, kurtosis)
    return {
        "deflated_sharpe_ratio": dsr,                      # probability in [0,1]; want > 0.95
        "observed_sharpe_annual": observed_sharpe_annual,
        "expected_max_sharpe_annual": sr_star * scale,     # selection benchmark, annualized
        "haircut_sharpe_annual": (obs - sr_star) * scale,  # point estimate after removing selection
        "sharpe_std_annual": sharpe_std_annual,
        "n_trials": int(n_trials),
        "n_obs": int(n_obs),
    }


def summarize_overfitting(
    results_df,
    n_obs: int,
    metric: str = "sharpe_ratio",
    periods_per_year: int = 252,
) -> Dict[str, float]:
    """Convenience: compute DSR diagnostics from an optimizer results DataFrame + a printable note.

    `n_obs` is the number of return observations behind each Sharpe (e.g., backtest trading days).
    """
    sr = results_df[metric].dropna().astype(float)
    if len(sr) < 2:
        return {"note": "too few trials for a deflated-Sharpe estimate"}
    diag = deflated_sharpe_ratio(
        observed_sharpe_annual=float(sr.max()),
        n_obs=n_obs,
        n_trials=int(len(sr)),
        trial_sharpes_annual=sr.values,
        periods_per_year=periods_per_year,
    )
    diag["note"] = (
        f"Best Sharpe {diag['observed_sharpe_annual']:.2f} vs selection benchmark "
        f"{diag['expected_max_sharpe_annual']:.2f} (expected best of {diag['n_trials']} trials under "
        f"no-skill). Haircut Sharpe ≈ {diag['haircut_sharpe_annual']:.2f}. "
        f"Deflated Sharpe Ratio (P real > selection) = {diag['deflated_sharpe_ratio']:.3f} "
        f"({'PASS' if diag['deflated_sharpe_ratio'] > 0.95 else 'WEAK — likely overfit/selection'})."
    )
    return diag
