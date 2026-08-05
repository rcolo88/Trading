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

# Fixed, literature/calendar-defined crisis windows — not fit to this backtest's
# data, so reporting them adds no selection bias. Populated only to the extent
# the price panel's history actually covers them (empty/NaN otherwise, which is
# itself informative — e.g. the current CSM stock panel starts 2010, so dotcom
# and the GFC only populate once a multi-asset/ETF panel with longer history is
# scored, per the Phase 3 plan).
CRISIS_WINDOWS = {
    "dotcom crash (2000-02)":     ("2000-01-01", "2002-12-31"),
    "GFC (2007-09)":              ("2007-01-01", "2009-12-31"),
    "euro debt crisis (2011)":    ("2011-01-01", "2011-12-31"),
    "china scare (2015-16)":      ("2015-06-01", "2016-03-01"),
    "2018 Q4 selloff":            ("2018-09-01", "2018-12-31"),
    "COVID crash (2020 Q1)":      ("2020-01-01", "2020-06-30"),
    "2022 bear":                  ("2022-01-01", "2022-12-31"),
}


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


def alpha_beta(strat_ret: pd.Series, bench_ret: pd.Series,
               periods_per_year: int = 252, rf_annual: float = 0.0) -> dict:
    """OLS market-model regression: strat_ret = alpha + beta*bench_ret + resid.

    Reports the annualized alpha AND its t-stat — a Sharpe edge over a benchmark
    (e.g. SPY) can be entirely explained by beta exposure (this project's own
    2017-2026 gross series regresses to alpha t=1.04, i.e. not distinguishable
    from zero), so beta/alpha should be a standing column on every result, not
    a one-off check.
    """
    import statsmodels.api as sm

    s = strat_ret.dropna()
    b = bench_ret.reindex(s.index).dropna()
    common = s.index.intersection(b.index)
    s, b = s.loc[common], b.loc[common]
    if len(s) < 30:
        return {"ann_alpha": np.nan, "alpha_tstat": np.nan, "beta": np.nan,
                "beta_tstat": np.nan, "r_squared": np.nan, "n_obs": len(s)}

    rf_per = rf_annual / periods_per_year
    X = sm.add_constant((b - rf_per).values)
    y = (s - rf_per).values
    model = sm.OLS(y, X).fit()
    alpha_per, beta = model.params
    return {
        "ann_alpha":    float(alpha_per * periods_per_year),
        "alpha_tstat":  float(model.tvalues[0]),
        "beta":         float(beta),
        "beta_tstat":   float(model.tvalues[1]),
        "r_squared":    float(model.rsquared),
        "n_obs":        int(len(s)),
    }


def regime_breakdown(net_ret: pd.Series, bench_ret: pd.Series) -> pd.DataFrame:
    """Per-calendar-year AND per-crisis-window Sharpe/return/drawdown/alpha/beta.

    `compute_metrics` collapses the whole sample to one number, which is exactly
    how a strategy can look fine on average while quietly failing every crisis
    year. This is the diagnostic that would have caught 2018/2022 immediately.
    """
    rows = []
    idx  = net_ret.dropna().index
    for yr, seg in net_ret.groupby(net_ret.index.year):
        seg = seg.dropna()
        if len(seg) < 20:
            continue
        m  = compute_metrics(seg, bench_ret)
        ab = alpha_beta(seg, bench_ret)
        rows.append({"window": str(yr), "kind": "calendar_year",
                     "n_days": m["n_days"], "return": m["cagr"], "sharpe": m["sharpe"],
                     "max_dd": m["max_dd"], "ann_alpha": ab["ann_alpha"],
                     "alpha_tstat": ab["alpha_tstat"], "beta": ab["beta"]})

    for name, (start, end) in CRISIS_WINDOWS.items():
        seg = net_ret.loc[start:end].dropna()
        if len(seg) < 20:
            rows.append({"window": name, "kind": "crisis", "n_days": len(seg),
                         "return": np.nan, "sharpe": np.nan, "max_dd": np.nan,
                         "ann_alpha": np.nan, "alpha_tstat": np.nan, "beta": np.nan})
            continue
        eq  = (1.0 + seg).cumprod()
        std = seg.std(ddof=1)
        sh  = float(np.sqrt(252) * seg.mean() / std) if std > 0 else 0.0
        dd  = float((eq / eq.cummax() - 1.0).min())
        ab  = alpha_beta(seg, bench_ret)
        rows.append({"window": name, "kind": "crisis", "n_days": len(seg),
                     "return": float(eq.iloc[-1] - 1.0), "sharpe": sh, "max_dd": dd,
                     "ann_alpha": ab["ann_alpha"], "alpha_tstat": ab["alpha_tstat"],
                     "beta": ab["beta"]})

    return pd.DataFrame(rows)


def rolling_window_summary(net_ret: pd.Series, window_months: int = 6,
                           step_months: int = 1, min_obs: int = 40) -> dict:
    """Distribution of Sharpe/return/drawdown across every rolling window —
    the actual "consistent Sharpe" metric. A single full-sample Sharpe can't
    distinguish a strategy that's uniformly OK from one that's brilliant for
    years then catastrophic for a quarter; the WORST window and the fraction
    of profitable windows can.
    """
    r = net_ret.dropna()
    if r.empty:
        return {"n_windows": 0}

    start, end = r.index[0], r.index[-1]
    window = pd.DateOffset(months=window_months)
    step   = pd.DateOffset(months=step_months)

    rows = []
    cur = start
    while cur + window <= end:
        seg = r.loc[cur: cur + window]
        if len(seg) >= min_obs:
            eq  = (1.0 + seg).cumprod()
            std = seg.std(ddof=1)
            sh  = float(np.sqrt(252) * seg.mean() / std) if std > 0 else 0.0
            dd  = float((eq / eq.cummax() - 1.0).min())
            rows.append({"start": cur, "end": cur + window, "sharpe": sh,
                         "return": float(eq.iloc[-1] - 1.0), "max_dd": dd})
        cur = cur + step

    if not rows:
        return {"n_windows": 0}
    df = pd.DataFrame(rows)
    return {
        "n_windows":           len(df),
        "median_sharpe":       float(df["sharpe"].median()),
        "worst_window_sharpe": float(df["sharpe"].min()),
        "pct_profitable":      float((df["return"] > 0).mean()),
        "worst_window_return": float(df["return"].min()),
        "median_max_dd":       float(df["max_dd"].median()),
        "worst_max_dd":        float(df["max_dd"].min()),
        "table":               df,
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
    from csm.data import SIGNAL_EXCLUDE
    rng         = np.random.default_rng(seed)
    ret         = prices.ffill(limit=3).pct_change().fillna(0.0)
    stocks      = ret.drop(columns=SIGNAL_EXCLUDE, errors="ignore")
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
