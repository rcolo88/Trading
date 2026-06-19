#!/usr/bin/env python3
"""Stage 0 — Residual Momentum Validation Spike.

Tests whether idiosyncratic (CAPM-residual) 12-1 month cross-sectional momentum
has a real pulse in the S&P 500, long-only, net of realistic costs.

PRE-REGISTERED GO/NO-GO:
  PASS     : net Sharpe ≳ 0.50  AND  beats naive momentum  AND  DSR > 0.90  AND  MCPT p < 0.05
  MARGINAL : ≥ 3 of 4 criteria met — refine signal, re-test
  FAIL     : < 3 criteria — insufficient evidence; do not build the full subsystem

NOTE: Survivorship bias present — uses today's S&P 500 constituents only; the full
      Stage 1 build adds point-in-time membership.  This is an intentional trade-off
      for the spike: we want the OPTIMISTIC signal estimate.  If even that doesn't
      clear the bar, the real edge is very unlikely to survive PIT correction.

Usage:
    python spike_residual_momentum.py [--perm N]   (default: 200 permutations)

Dependencies: pandas, numpy, scipy, yfinance, requests  (all in base env)
"""

from __future__ import annotations
import argparse
import sys
import warnings
from io import StringIO
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from scipy.stats import norm

# ── Import AFML primitives from sibling subsystem ────────────────────────────
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "Trend Reversal"))
from trendrev.afml import deflated_sharpe_ratio  # noqa: E402  (after sys.path)


# ═══════════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════════
CACHE_DIR  = Path(__file__).parent / "spike_cache"
START      = "2010-01-01"
END        = "2025-12-31"
COST_BPS   = 10          # one-way transaction cost (basis points)
QUANTILE   = 0.80        # top-quintile (80th percentile threshold)
WINDOW     = 252         # 12-month lookback in trading days
SKIP       = 21          # skip last month to avoid short-term reversal
REBAL_FREQ = 5           # weekly rebalance (5 trading days)

# Parameter grid for the Deflated Sharpe (DSR) denominator.
# Keep small: DSR penalises for the number of configurations tried.
GRID = [
    dict(window=189, skip=21, quantile=0.80),   # 9-month lookback
    dict(window=252, skip=21, quantile=0.80),   # 12-month  ← primary
    dict(window=252, skip=21, quantile=0.75),   # wider top-quintile
    dict(window=252, skip=21, quantile=0.85),   # tighter top-quintile
    dict(window=315, skip=21, quantile=0.80),   # 15-month lookback
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Data helpers
# ═══════════════════════════════════════════════════════════════════════════════
def _get_sp500_tickers() -> list[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    hdrs = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    try:
        r = requests.get(url, headers=hdrs, timeout=20)
        r.raise_for_status()
        return pd.read_html(StringIO(r.text))[0]["Symbol"].tolist()
    except Exception as exc:
        print(f"WARNING: Wikipedia fetch failed ({exc}). Using cached list.")
        return []


def load_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Adj-close price panel, parquet-cached. Columns: tickers + SPY."""
    cache     = CACHE_DIR / "prices.parquet"
    meta_file = CACHE_DIR / "cache_meta.txt"
    meta_key  = f"{start}|{end}|{len(tickers)}"

    if cache.exists() and meta_file.exists() and meta_file.read_text().strip() == meta_key:
        df = pd.read_parquet(cache)
        print(f"Loaded price cache: {df.shape[1]} tickers × {df.shape[0]} days")
        return df

    # yfinance expects BRK-B, not BRK.B
    yfmt = [t.replace(".", "-") for t in tickers]
    if "SPY" not in yfmt:
        yfmt = ["SPY"] + yfmt

    print(f"Downloading prices for {len(yfmt)} tickers ({start}→{end}) …")
    raw = yf.download(yfmt, start=start, end=end, auto_adjust=True,
                      progress=True, threads=True, timeout=60)

    if isinstance(raw.columns, pd.MultiIndex):
        df = raw["Close"]
    else:
        df = raw[["Close"]] if "Close" in raw.columns else raw

    df = df.dropna(axis=1, how="all")
    df.index = pd.to_datetime(df.index)
    df.to_parquet(cache)
    meta_file.write_text(meta_key)
    print(f"Cached: {df.shape[1]} tickers × {df.shape[0]} days")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  Signal computation
# ═══════════════════════════════════════════════════════════════════════════════
def _rolling_beta(stocks: pd.DataFrame, mkt: pd.Series, window: int) -> pd.DataFrame:
    """Vectorized rolling CAPM beta for every stock vs market."""
    rm_mean  = mkt.rolling(window).mean()
    rs_mean  = stocks.rolling(window).mean()
    cov_num  = (stocks.multiply(mkt, axis=0)).rolling(window).mean() \
               - rs_mean.multiply(rm_mean, axis=0)
    # Population variance of market (consistent with population cov above)
    var_m    = (mkt ** 2).rolling(window).mean() - rm_mean ** 2
    return cov_num.divide(var_m.replace(0, np.nan), axis=0)


def compute_residual_momentum(prices: pd.DataFrame,
                               window: int = WINDOW,
                               skip:   int = SKIP) -> pd.DataFrame:
    """Idiosyncratic 12-1 momentum: cumulative CAPM-residual / idio-vol."""
    ret    = np.log1p(prices.pct_change().fillna(0.0))  # log returns
    mkt    = ret["SPY"]
    stocks = ret.drop(columns=["SPY"], errors="ignore")

    beta  = _rolling_beta(stocks, mkt, window)
    resid = stocks - beta.multiply(mkt, axis=0)

    # Cumulative residual [t-window : t-skip] — skip avoids short-term reversal
    cum_resid = resid.rolling(window).sum() - resid.rolling(skip).sum()
    idio_vol  = resid.rolling(window).std().replace(0, np.nan)
    return cum_resid / idio_vol


def compute_naive_momentum(prices: pd.DataFrame,
                            window: int = WINDOW,
                            skip:   int = SKIP) -> pd.DataFrame:
    """Standard 12-1 cross-sectional momentum (raw return, no residualisation)."""
    ret    = prices.pct_change().fillna(0.0)
    stocks = ret.drop(columns=["SPY"], errors="ignore")
    return stocks.rolling(window).sum() - stocks.rolling(skip).sum()


# ═══════════════════════════════════════════════════════════════════════════════
#  Portfolio construction & backtest
# ═══════════════════════════════════════════════════════════════════════════════
def _build_position_matrix(
    signals:    pd.DataFrame,
    stock_cols: list[str],
    index:      pd.DatetimeIndex,
    quantile:   float = QUANTILE,
    rebal_freq: int   = REBAL_FREQ,
) -> pd.DataFrame:
    """Return daily target-position DataFrame (before execution lag)."""
    target = pd.DataFrame(np.nan, index=index, columns=stock_cols)

    # Rebalance every rebal_freq-th bar; skip early bars with no signals
    valid_sig_dates = signals.dropna(how="all").index
    rebal_mask      = np.zeros(len(index), dtype=bool)
    rebal_mask[::rebal_freq] = True
    rebal_dates = index[rebal_mask & index.isin(valid_sig_dates)]

    for date in rebal_dates:
        row   = signals.loc[date].reindex(stock_cols).dropna()
        if len(row) < 20:
            continue
        thresh = row.quantile(quantile)
        longs  = row.index[row >= thresh].tolist()
        if not longs:
            continue
        target.loc[date, stock_cols] = 0.0
        target.loc[date, longs]      = 1.0 / len(longs)

    return target.ffill().fillna(0.0)


def backtest(
    signals:    pd.DataFrame,
    prices:     pd.DataFrame,
    quantile:   float = QUANTILE,
    cost_bps:   float = COST_BPS,
    rebal_freq: int   = REBAL_FREQ,
) -> pd.Series:
    """Long-only, equal-weight, top-quantile portfolio. Returns daily net returns."""
    ret        = prices.pct_change().fillna(0.0)
    stocks     = ret.drop(columns=["SPY"], errors="ignore")
    stock_cols = list(stocks.columns)

    pos      = _build_position_matrix(signals, stock_cols, stocks.index, quantile, rebal_freq)
    exec_pos = pos.shift(1).fillna(0.0)          # next-day execution (no look-ahead)

    port_ret = (exec_pos * stocks).sum(axis=1)
    turnover = exec_pos.diff().abs().sum(axis=1).fillna(0.0)
    costs    = turnover * cost_bps / 1e4
    return port_ret - costs


# ═══════════════════════════════════════════════════════════════════════════════
#  Metrics
# ═══════════════════════════════════════════════════════════════════════════════
def annualized_sharpe(ret: pd.Series) -> float:
    r = ret.dropna().replace([np.inf, -np.inf], np.nan).dropna()
    std = r.std(ddof=1)
    return float(np.sqrt(252) * r.mean() / std) if std > 0 else 0.0


def report_metrics(ret: pd.Series, label: str, width: int = 30) -> None:
    r  = ret.dropna()
    eq = (1.0 + r).cumprod()
    dd = (eq / eq.cummax() - 1.0).min()
    n_years = len(r) / 252
    cagr = eq.iloc[-1] ** (1.0 / n_years) - 1.0 if n_years > 0 else 0.0
    sh   = annualized_sharpe(r)
    print(f"  {label:<{width}}  Sharpe={sh:+.3f}  CAGR={cagr:+.1%}  MaxDD={dd:.1%}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Monte Carlo Permutation Test (Masters)
# ═══════════════════════════════════════════════════════════════════════════════
def mcpt(
    signals:          pd.DataFrame,
    prices:           pd.DataFrame,
    observed_sharpe:  float,
    n_perm:           int   = 200,
    quantile:         float = QUANTILE,
    cost_bps:         float = COST_BPS,
    rebal_freq:       int   = REBAL_FREQ,
    seed:             int   = 42,
) -> tuple[float, np.ndarray]:
    """Masters-style permutation test on the cross-sectional signal.

    Null: at each rebalance date, randomly reassign momentum scores across stocks
    (destroys cross-sectional predictability; preserves market environment and
    return distributions).  Returns (p-value, null-Sharpe array).
    """
    rng       = np.random.default_rng(seed)
    ret       = prices.pct_change().fillna(0.0)
    stocks    = ret.drop(columns=["SPY"], errors="ignore")
    scols     = list(stocks.columns)
    stock_np  = stocks.values.astype(np.float64)      # (T, N)
    T, N      = stock_np.shape
    all_dates = stocks.index

    # Pre-compute rebalance dates (indices into all_dates)
    valid_sig   = signals.dropna(how="all").index
    rebal_mask  = np.zeros(T, dtype=bool)
    rebal_mask[::rebal_freq] = True
    rebal_dates = all_dates[rebal_mask & all_dates.isin(valid_sig)]

    # Pre-fetch signal matrix aligned to rebalance dates
    sig_np = signals.reindex(columns=scols).loc[rebal_dates].values  # (D, N)
    D      = len(rebal_dates)

    # Corresponding row indices in stock_np
    rebal_idx = np.searchsorted(all_dates, rebal_dates)

    null_sharpes = np.empty(n_perm)

    pos_buf = np.zeros((T, N), dtype=np.float64)   # reused each permutation

    for p in range(n_perm):
        if (p + 1) % 50 == 0 or p == 0:
            print(f"  MCPT {p+1}/{n_perm} …", end="\r", flush=True)

        pos_buf[:] = 0.0
        prev_weights = np.zeros(N)

        for d in range(D):
            row   = sig_np[d]                   # (N,)
            valid = ~np.isnan(row)
            if valid.sum() < 20:
                continue
            perm_row = row.copy()
            perm_row[valid] = rng.permutation(row[valid])  # shuffle valid values
            thresh  = np.nanquantile(perm_row, quantile)
            longs   = np.where(valid & (perm_row >= thresh))[0]
            if len(longs) == 0:
                weights = np.zeros(N)
            else:
                weights = np.zeros(N)
                weights[longs] = 1.0 / len(longs)

            # Fill from this rebal date to the next
            start_i = rebal_idx[d]
            end_i   = rebal_idx[d + 1] if d + 1 < D else T
            pos_buf[start_i:end_i] = weights

        # Execution lag: shift by 1 day
        exec_pos = np.roll(pos_buf, 1, axis=0)
        exec_pos[0] = 0.0

        port_ret = (exec_pos * stock_np).sum(axis=1)
        turnover = np.abs(np.diff(exec_pos, axis=0)).sum(axis=1)
        costs    = np.concatenate([[0.0], turnover]) * cost_bps / 1e4
        net_ret  = port_ret - costs

        std = net_ret.std(ddof=1)
        null_sharpes[p] = np.sqrt(252) * net_ret.mean() / std if std > 0 else 0.0

    print()
    p_val = float((null_sharpes >= observed_sharpe).mean())
    return p_val, null_sharpes


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(description="Residual Momentum Stage-0 spike")
    parser.add_argument("--perm", type=int, default=200,
                        help="Number of MCPT permutations (default 200; use 1000 for publication-grade p-value)")
    args = parser.parse_args()

    print("=" * 65)
    print("Stage 0 — Residual Momentum Validation Spike")
    print(f"  Universe : current S&P 500 (survivorship-biased, intentional)")
    print(f"  Period   : {START} → {END}")
    print(f"  Costs    : {COST_BPS} bps one-way")
    print(f"  MCPT     : {args.perm} permutations")
    print("=" * 65)

    # ── 1. Prices ────────────────────────────────────────────────────────────
    tickers = _get_sp500_tickers()
    if not tickers:
        print("ERROR: could not fetch ticker list.  Exiting.")
        sys.exit(1)
    prices = load_prices(tickers, START, END)
    spy_ret = prices["SPY"].pct_change().fillna(0.0)

    # ── 2. Grid search (for DSR denominator) ─────────────────────────────────
    print(f"\n─── Grid search ({len(GRID)} configs, for Deflated Sharpe) ─────────────────")
    grid_sharpes: list[float] = []
    primary_signals: pd.DataFrame | None = None
    primary_net_ret: pd.Series | None    = None

    for cfg in GRID:
        sig  = compute_residual_momentum(prices, window=cfg["window"], skip=cfg["skip"])
        nret = backtest(sig, prices, quantile=cfg["quantile"])
        sh   = annualized_sharpe(nret)
        grid_sharpes.append(sh)
        tag  = " ← primary" if (cfg["window"] == WINDOW and
                                  cfg["skip"]   == SKIP   and
                                  cfg["quantile"] == QUANTILE) else ""
        print(f"  window={cfg['window']:3d}  skip={cfg['skip']:2d}  q={cfg['quantile']:.2f}  "
              f"Sharpe={sh:+.3f}{tag}")
        if tag:
            primary_signals = sig
            primary_net_ret = nret

    # ── 3. Primary vs Naive vs SPY ───────────────────────────────────────────
    print("\n─── Performance comparison ─────────────────────────────────────────")
    naive_sig = compute_naive_momentum(prices)
    naive_ret = backtest(naive_sig, prices)

    report_metrics(primary_net_ret, "Residual mom (primary)")
    report_metrics(naive_ret,       "Naive 12-1 mom (benchmark)")
    report_metrics(spy_ret,         "SPY buy-and-hold")

    # ── 4. Deflated Sharpe ───────────────────────────────────────────────────
    print("\n─── Deflated Sharpe Ratio (DSR) ────────────────────────────────────")
    sr_trials = np.array(grid_sharpes)
    # afml.deflated_sharpe_ratio expects a returns Series + array of per-obs Sharpes
    # Our grid_sharpes are annualized; convert to per-obs (÷ √252) for PSR denominator
    per_obs_trials = sr_trials / np.sqrt(252)
    dsr = deflated_sharpe_ratio(primary_net_ret.dropna(), per_obs_trials)
    print(f"  Grid Sharpes : {[f'{s:.3f}' for s in grid_sharpes]}")
    print(f"  DSR          : {dsr:.4f}  (threshold > 0.90 for PASS)")

    # ── 5. Monte Carlo Permutation Test ─────────────────────────────────────
    print(f"\n─── Monte Carlo Permutation Test ({args.perm} permutations) ─────────────")
    observed_sh = annualized_sharpe(primary_net_ret)
    p_val, null = mcpt(primary_signals, prices, observed_sh, n_perm=args.perm)

    print(f"  Observed Sharpe       : {observed_sh:+.3f}")
    print(f"  Null distribution     : mean={null.mean():+.3f}  σ={null.std():.3f}")
    print(f"  95th pct of null      : {np.percentile(null, 95):+.3f}")
    print(f"  MCPT p-value          : {p_val:.4f}  (threshold < 0.05 for PASS)")

    # ── 6. Verdict ───────────────────────────────────────────────────────────
    resid_sh = annualized_sharpe(primary_net_ret)
    naive_sh  = annualized_sharpe(naive_ret)

    criteria = {
        "Sharpe ≳ 0.50"      : resid_sh >= 0.50,
        "Beats naive momentum": resid_sh > naive_sh,
        "DSR > 0.90"          : dsr > 0.90,
        "MCPT p < 0.05"       : p_val < 0.05,
    }

    print("\n" + "=" * 65)
    print("VERDICT")
    print("=" * 65)
    for label, passed in criteria.items():
        icon = "✓" if passed else "✗"
        print(f"  {icon}  {label}")

    n_pass = sum(criteria.values())
    print()
    if n_pass == 4:
        print("  ▶  ALL PASS — proceed to Stages 1-4 (full build)")
    elif n_pass >= 3:
        print("  ▶  MARGINAL (3/4) — refine signal, then re-test")
        print("     Suggested refinements: vol-scaling overlay, FF3 residuals,")
        print("     52-week-high distance feature, or quality+momentum combo.")
    else:
        print(f"  ▶  FAIL ({n_pass}/4) — insufficient evidence of real edge.")
        print("     Do NOT build the full subsystem. Report result honestly.")
    print("=" * 65)


if __name__ == "__main__":
    main()
