"""Validation suite: performance metrics, DSR, PBO/CSCV, and Masters MCPT.

All three overfitting tests are applied:
  1. Deflated Sharpe Ratio (Bailey & López de Prado 2014, AFML Ch. 14)
  2. Probability of Backtest Overfitting via CSCV (AFML Ch. 11-12)
  3. Monte Carlo Permutation Test — Masters ('Statistically Sound Indicators')

The MCPT is the decisive "is it luck?" test: it permutes the cross-sectional
ranking (shuffles which stocks were top-scored on each date) and reruns the
entire portfolio engine, building a null distribution of Sharpe ratios.
p = P(null ≥ observed).  Threshold for claiming real edge: p < 0.05.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from csm.afml import deflated_sharpe_ratio, prob_backtest_overfitting


# ─────────────────────────────────────────────────────────────────────────────
#  Standard performance metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(net_ret: pd.Series, bench_ret: pd.Series) -> dict:
    """Comprehensive performance metrics for a daily net-return Series."""
    r  = net_ret.dropna().replace([np.inf, -np.inf], np.nan).dropna()
    eq = (1.0 + r).cumprod()

    n_years = max(len(r) / 252, 1e-6)
    cagr    = float(eq.iloc[-1] ** (1.0 / n_years) - 1.0)

    std = r.std(ddof=1)
    sharpe = float(np.sqrt(252) * r.mean() / std) if std > 0 else 0.0

    downside = r[r < 0].std(ddof=1)
    sortino  = float(np.sqrt(252) * r.mean() / downside) if downside > 0 else 0.0

    roll_max = eq.cummax()
    dd       = (eq / roll_max - 1.0)
    max_dd   = float(dd.min())
    calmar   = cagr / abs(max_dd) if max_dd < 0 else np.inf

    monthly_ret = (1.0 + r).resample("ME").prod() - 1.0
    pos_months  = float((monthly_ret > 0).mean())

    # Monthly win/loss
    wins   = monthly_ret[monthly_ret > 0]
    losses = monthly_ret[monthly_ret < 0]
    pf     = float(-wins.sum() / losses.sum()) if losses.sum() < 0 else np.inf

    b  = bench_ret.reindex(r.index).dropna()
    beq = (1.0 + b).cumprod()
    bn  = max(len(b) / 252, 1e-6)
    bench_cagr   = float(beq.iloc[-1] ** (1.0 / bn) - 1.0)
    bench_sharpe = float(np.sqrt(252) * b.mean() / b.std(ddof=1)) if b.std(ddof=1) > 0 else 0.0

    excess_cagr = cagr - bench_cagr

    return {
        "sharpe":          sharpe,
        "sortino":         sortino,
        "calmar":          calmar,
        "cagr":            cagr,
        "max_dd":          max_dd,
        "pos_months":      pos_months,
        "profit_factor":   pf,
        "bench_cagr":      bench_cagr,
        "bench_sharpe":    bench_sharpe,
        "excess_cagr":     excess_cagr,
        "n_days":          len(r),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Overfitting tests
# ─────────────────────────────────────────────────────────────────────────────

def run_dsr(net_ret: pd.Series, grid_sharpes: list[float]) -> dict:
    """Deflated Sharpe Ratio (DSR) across the parameter grid.

    The DSR benchmarks the *observed* Sharpe against the expected maximum
    Sharpe of N zero-skill trials, correcting for selection bias.
    grid_sharpes should include the Sharpe of every config tested so far.
    """
    sr_trials = np.array(grid_sharpes, dtype=float) / np.sqrt(252)  # per-obs Sharpes
    dsr_val   = deflated_sharpe_ratio(net_ret.dropna(), sr_trials)
    return {
        "dsr":          dsr_val,
        "n_trials":     len(grid_sharpes),
        "best_trial_sharpe": float(np.max(grid_sharpes)),
        "pass":         dsr_val > 0.90,
    }


def run_pbo(returns_matrix: pd.DataFrame, n_partitions: int = 16) -> dict:
    """Probability of Backtest Overfitting (CSCV).

    returns_matrix: T × N — one column per parameter configuration tried.
    """
    result = prob_backtest_overfitting(returns_matrix, n_partitions=n_partitions)
    return {
        "pbo":       result["pbo"],
        "logits":    result["logits"],
        "pass":      result["pbo"] < 0.50,   # PBO < 50% is not evidence of overfitting
    }


def run_mcpt(
    signals:          pd.DataFrame,
    prices:           pd.DataFrame,
    observed_sharpe:  float,
    portfolio_fn:     Callable[[pd.DataFrame], pd.Series],
    n_perm:           int = 1000,
    seed:             int = 42,
) -> dict:
    """Monte Carlo Permutation Test (Masters).

    At each rebalance date, randomly reassign the momentum scores across stocks
    (destroying cross-sectional predictability while preserving market environment
    and individual return distributions), re-run the entire portfolio engine, and
    collect the null distribution of Sharpe ratios.

    Parameters
    ----------
    signals         : (T, N) primary signal DataFrame
    prices          : (T, N+1) price panel
    observed_sharpe : the actual strategy's annualised Sharpe
    portfolio_fn    : callable(perm_signals) → daily net-return Series
                      (should use the same cfg/costs as the real strategy)
    n_perm          : number of permutations (≥ 1000 for p-value resolution 0.001)
    seed            : RNG seed

    Returns
    -------
    dict with keys: p_value, null_mean, null_std, null_95th, pass
    """
    rng         = np.random.default_rng(seed)
    ret         = prices.ffill(limit=3).pct_change().fillna(0.0)
    stocks      = ret.drop(columns=["SPY"], errors="ignore")
    scols       = list(stocks.columns)

    sig_np = signals.reindex(columns=scols).values.astype(np.float64)  # (T, N)
    T, N   = sig_np.shape

    null_sharpes = np.empty(n_perm)

    for p in range(n_perm):
        if (p + 1) % 100 == 0:
            print(f"  MCPT {p+1}/{n_perm} …", end="\r", flush=True)
        perm_sig = pd.DataFrame(index=signals.index, columns=scols, dtype=np.float64)
        for t in range(T):
            row   = sig_np[t]
            valid = ~np.isnan(row)
            if valid.sum() < 10:
                perm_sig.iloc[t] = row
                continue
            perm_row = row.copy()
            perm_row[valid] = rng.permutation(row[valid])
            perm_sig.iloc[t] = perm_row

        perm_ret = portfolio_fn(perm_sig)
        r        = perm_ret.dropna()
        std      = r.std(ddof=1)
        null_sharpes[p] = np.sqrt(252) * r.mean() / std if std > 0 else 0.0

    print()
    p_val = float((null_sharpes >= observed_sharpe).mean())
    return {
        "p_value":   p_val,
        "null_mean": float(null_sharpes.mean()),
        "null_std":  float(null_sharpes.std()),
        "null_95th": float(np.percentile(null_sharpes, 95)),
        "observed":  observed_sharpe,
        "pass":      p_val < 0.05,
    }
