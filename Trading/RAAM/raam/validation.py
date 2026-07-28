"""Validation suite: performance metrics (incl. the paper's own Figure 19 stat
set, for a direct line-by-line comparison) plus the three overfitting tests —
Deflated Sharpe Ratio, PBO/CSCV, and a Monte Carlo Permutation Test — mirroring
Cross-Sectional Momentum's csm/validation.py structure and afml.py primitives.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from raam.afml import deflated_sharpe_ratio, prob_backtest_overfitting


# ─────────────────────────────────────────────────────────────────────────────
#  Performance metrics
# ─────────────────────────────────────────────────────────────────────────────

def compute_metrics(net_ret: pd.Series, bench_ret: pd.Series) -> dict:
    """Comprehensive performance metrics for a daily net-return Series.

    Includes both the standard metric set (Sharpe, Sortino, Calmar, CAGR,
    true peak-to-trough max drawdown) AND the paper's own Figure 19 stat set
    (absolute performance, worst/best year, worst/best month, annualized STD,
    positive/negative month COUNTS, and a rolling-3-month drawdown) so a
    report can line up against Giordano (2018) term for term. The paper
    reports ONLY the rolling-3-month drawdown (-6.12%), which understates true
    risk; `max_dd` (unbounded peak-to-trough) is reported alongside it so that
    gap is visible rather than hidden.
    """
    r  = net_ret.dropna().replace([np.inf, -np.inf], np.nan).dropna()
    eq = (1.0 + r).cumprod()

    n_years = max(len(r) / 252, 1e-6)
    cagr    = float(eq.iloc[-1] ** (1.0 / n_years) - 1.0)

    std    = r.std(ddof=1)
    sharpe = float(np.sqrt(252) * r.mean() / std) if std > 0 else 0.0

    downside = r[r < 0].std(ddof=1)
    sortino  = float(np.sqrt(252) * r.mean() / downside) if downside > 0 else 0.0

    roll_max = eq.cummax()
    dd       = eq / roll_max - 1.0
    max_dd   = float(dd.min())
    calmar   = cagr / abs(max_dd) if max_dd < 0 else np.inf

    # Paper's own drawdown convention (Figure 19 "Max DrawDown 3m"): worst
    # decline from a peak no more than ~3 trading months (63 days) earlier —
    # structurally smaller than the unbounded max_dd above.
    roll3_max = eq.rolling(63, min_periods=1).max()
    max_dd_3m = float((eq / roll3_max - 1.0).min())

    monthly_ret    = (1.0 + r).resample("ME").prod() - 1.0
    pos_months_n   = int((monthly_ret > 0).sum())
    neg_months_n   = int((monthly_ret < 0).sum())
    pos_months_pct = float((monthly_ret > 0).mean()) if len(monthly_ret) else 0.0

    yearly_ret = (r.groupby(r.index.year)
                   .apply(lambda x: float((1.0 + x).prod() - 1.0)))

    wins   = monthly_ret[monthly_ret > 0]
    losses = monthly_ret[monthly_ret < 0]
    pf     = float(-wins.sum() / losses.sum()) if losses.sum() < 0 else np.inf

    b  = bench_ret.reindex(r.index).dropna()
    if len(b):
        beq          = (1.0 + b).cumprod()
        bn           = max(len(b) / 252, 1e-6)
        bench_cagr   = float(beq.iloc[-1] ** (1.0 / bn) - 1.0)
        bstd         = b.std(ddof=1)
        bench_sharpe = float(np.sqrt(252) * b.mean() / bstd) if bstd > 0 else 0.0
    else:
        bench_cagr, bench_sharpe = 0.0, 0.0

    return {
        "sharpe":               sharpe,
        "sortino":              sortino,
        "calmar":               calmar,
        "cagr":                 cagr,
        "max_dd":               max_dd,
        "max_dd_3m":            max_dd_3m,
        "pos_months":           pos_months_pct,
        "pos_months_n":         pos_months_n,
        "neg_months_n":         neg_months_n,
        "profit_factor":        pf,
        "bench_cagr":           bench_cagr,
        "bench_sharpe":         bench_sharpe,
        "excess_cagr":          cagr - bench_cagr,
        "n_days":               len(r),
        # paper's Figure 19 stat set, same names/units as SALIENT_PUBLISHED
        "absolute_performance": float(eq.iloc[-1] - 1.0),
        "annualized_std":       float(std * np.sqrt(252)) if pd.notna(std) else 0.0,
        "worst_year":           float(yearly_ret.min()) if len(yearly_ret) else 0.0,
        "best_year":            float(yearly_ret.max()) if len(yearly_ret) else 0.0,
        "worst_month":          float(monthly_ret.min()) if len(monthly_ret) else 0.0,
        "best_month":           float(monthly_ret.max()) if len(monthly_ret) else 0.0,
        "ytd":                  float(yearly_ret.iloc[-1]) if len(yearly_ret) else 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Overfitting tests
# ─────────────────────────────────────────────────────────────────────────────

def run_dsr(net_ret: pd.Series, grid_sharpes: list[float]) -> dict:
    """Deflated Sharpe Ratio across every configuration tried (the rank-weight
    sweep) — see sweep_rank_weights.py, which appends to config
    validation.trial_sharpes."""
    sr_trials = np.array(grid_sharpes, dtype=float) / np.sqrt(252)
    dsr_val   = deflated_sharpe_ratio(net_ret.dropna(), sr_trials)
    return {
        "dsr":               dsr_val,
        "n_trials":          len(grid_sharpes),
        "best_trial_sharpe": float(np.max(grid_sharpes)) if grid_sharpes else 0.0,
        "pass":              dsr_val > 0.90,
    }


def run_pbo(returns_matrix: pd.DataFrame, n_partitions: int = 16) -> dict:
    """Probability of Backtest Overfitting (CSCV) across the rank-weight sweep grid."""
    result = prob_backtest_overfitting(returns_matrix, n_partitions=n_partitions)
    return {"pbo": result["pbo"], "logits": result["logits"], "pass": result["pbo"] < 0.50}


def run_mcpt(
    total_rank:      pd.DataFrame,
    M:               pd.DataFrame,
    close:           pd.DataFrame,
    cfg:             dict,
    observed_sharpe: float,
    eval_start:      pd.Timestamp,
    n_perm:          int = 1000,
    seed:            int = 42,
) -> dict:
    """Monte Carlo Permutation Test (Masters).

    At each rebalance date ON OR AFTER `eval_start`, randomly reassign the
    Total Rank VALUES across that date's eligible tickers (destroying the
    correspondence between an asset's own M/V/C/T and its rank, i.e.
    destroying selection skill) while preserving the exact 5-of-K selection
    mechanics, the monthly cadence, and every ticker's TRUE realized return
    path (the cash-substitution check still reads each ticker's real,
    unshuffled Absolute Momentum). Dates BEFORE `eval_start` are left
    unpermuted, so the book warms into the evaluation window exactly as the
    real engine does (same as backtest.simulate_drift's pre-window warm
    start) — only the window actually being scored is randomized. The null
    Sharpe is computed over the SAME [eval_start:] slice as `observed_sharpe`,
    so the two are directly comparable. p = P(null >= observed).
    """
    from raam import portfolio as port_mod
    from raam import ranking as rank_mod

    rng      = np.random.default_rng(seed)
    n_select = int(cfg.get("ranking", {}).get("n_select", 5))
    perm_dates = total_rank.index[total_rank.index >= eval_start]

    null_sharpes = np.empty(n_perm)
    for p in range(n_perm):
        if (p + 1) % 100 == 0:
            print(f"  MCPT {p + 1}/{n_perm} …", end="\r", flush=True)

        perm_total = total_rank.copy()
        for d in perm_dates:
            valid = total_rank.loc[d].dropna()
            if len(valid) < 2:
                continue
            perm_total.loc[d, valid.index] = rng.permutation(valid.values)

        picks = rank_mod.select_book(perm_total, n_select=n_select)
        pos   = port_mod.build_positions(picks, M, close, cfg)
        ret   = port_mod.portfolio_returns(pos, close, cfg)

        r   = ret.loc[eval_start:].dropna()
        std = r.std(ddof=1)
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
