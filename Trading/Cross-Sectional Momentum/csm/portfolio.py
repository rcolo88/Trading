"""Portfolio construction: cross-sectional rank → long-only weights → returns.

Execution convention (look-ahead-free, matching Trend Reversal/trendrev/backtest.py):
  - Signals observed at close of day t
  - Position held over the interval starting at open of t+1
  - Returns measured open-to-open (approximated here as close-to-close with a 1-day shift)

Regime filter and vol-scaling are applied as position multipliers BEFORE the execution lag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from csm.signals import spy_regime, vol_scale_factor


def build_positions(
    signals:        pd.DataFrame,
    prices:         pd.DataFrame,
    cfg:            dict,
    pit_df:         pd.DataFrame | None = None,
    rebal_anchor:   str = "start",
) -> pd.DataFrame:
    """Cross-sectional rank → long-only position weights (before execution lag).

    Parameters
    ----------
    signals   : (T, N) DataFrame — primary signal score per stock per day
    prices    : (T, N+1) price panel including SPY
    cfg       : strategy config dict
    pit_df    : point-in-time membership DataFrame; if None, no PIT filtering
    rebal_anchor : "start" (default) anchors the rebalance grid at the FIRST bar —
                use this for backtests so the validated dates never move.  "end"
                anchors the grid at the LAST bar so the final row is always a fresh
                rebalance (used by live `ideas`/`target_book`: the user's run day IS
                the rebalance, not a ffilled hold up to 4 days stale).

    Returns
    -------
    pos : (T, N) DataFrame — target weight per stock (0 ≤ w ≤ 1, rows sum ≤ 1)
    """
    sig_cfg  = cfg.get("signal",    {})
    port_cfg = cfg.get("portfolio", {})
    reg_cfg  = cfg.get("regime_filter", {})
    vs_cfg   = cfg.get("vol_scaling",   {})

    quantile   = float(sig_cfg.get("quantile",   0.80))
    rebal_freq = int(port_cfg.get("rebal_freq",  5))
    max_names  = int(port_cfg.get("max_names",   100))
    min_names  = int(port_cfg.get("min_names",   10))

    stocks    = prices.drop(columns=["SPY"], errors="ignore")
    stock_ret = stocks.ffill(limit=3).pct_change().fillna(0.0)
    index     = stocks.index
    T, N      = len(index), len(stocks.columns)
    scols     = list(stocks.columns)

    # --- Regime filter (broadcast to daily Series) ---
    regime_enabled = reg_cfg.get("enabled", True)
    if regime_enabled:
        regime_ok = spy_regime(
            prices,
            ma_days = int(reg_cfg.get("spy_ma_days", 200)),
            vol_cap = float(reg_cfg.get("vol_cap",    0.25)),
        )
    else:
        regime_ok = pd.Series(True, index=index)

    # --- Point-in-time membership filter ---
    from csm.universe import get_members_on
    def valid_stocks_on(date: pd.Timestamp) -> list[str]:
        if pit_df is None:
            return scols
        members = get_members_on(pit_df, date)
        return [c for c in scols if c in members or c == "SPY"]

    # --- Build rebalance-date target positions ---
    target = pd.DataFrame(np.nan, index=index, columns=scols, dtype=np.float64)

    # First bar with a valid signal
    valid_sig_mask = signals.notna().any(axis=1)
    rebal_mask     = np.zeros(T, dtype=bool)
    if rebal_anchor == "end":
        rebal_mask[np.arange(T - 1, -1, -rebal_freq)] = True
    else:
        rebal_mask[::rebal_freq] = True
    rebal_dates = index[rebal_mask & valid_sig_mask.values]

    for date in rebal_dates:
        if not regime_ok.get(date, True):
            # Regime filter: go flat on this rebalance date
            target.loc[date] = 0.0
            continue

        valid_cols = valid_stocks_on(date)
        row        = signals.loc[date].reindex(valid_cols).dropna()
        if len(row) < min_names:
            target.loc[date] = 0.0
            continue

        thresh = row.quantile(quantile)
        longs  = row.index[row >= thresh].tolist()
        longs  = longs[:max_names]            # cap by max_names
        if not longs:
            target.loc[date] = 0.0
            continue

        target.loc[date, scols] = 0.0         # zero all first
        target.loc[date, longs] = 1.0 / len(longs)

    pos = target.ffill().fillna(0.0)

    # --- Volatility scaling ---
    vs_enabled = vs_cfg.get("enabled", True)
    if vs_enabled:
        # Compute a rough portfolio return series from current positions
        rough_ret  = (pos.shift(1).fillna(0.0) * stock_ret).sum(axis=1)
        scale      = vol_scale_factor(
            rough_ret,
            target_vol = float(vs_cfg.get("target_vol",       0.15)),
            window     = int(vs_cfg.get("estimation_window",  63)),
        )
        pos = pos.multiply(scale, axis=0).clip(upper=1.0)

    return pos


def portfolio_returns(
    positions: pd.DataFrame,
    prices:    pd.DataFrame,
    cfg:       dict,
) -> pd.Series:
    """Compute daily net portfolio returns (close-to-close with next-day execution lag)."""
    from csm.costs import apply_costs

    stocks    = prices.drop(columns=["SPY"], errors="ignore")
    stock_ret = stocks.ffill(limit=3).pct_change().fillna(0.0)

    exec_pos  = positions.shift(1).fillna(0.0)   # next-day execution
    gross     = (exec_pos * stock_ret).sum(axis=1)
    net       = apply_costs(gross, exec_pos, cfg)
    return net


def target_book(
    prices:       pd.DataFrame,
    cfg:          dict,
    pit_df:       pd.DataFrame | None = None,
    as_of:        pd.Timestamp | None = None,
) -> pd.Series:
    """The single source of truth for "what the strategy holds on `as_of`".

    Returns the target weight per ticker, reconstructed with the IDENTICAL engine
    the backtest trades — top-quintile selection → equal-dollar 1/N → vol-scaling
    → regime gate.  Both the live `ideas` command and the `verify-book` self-check
    call this, so trading the book it returns reproduces the validated backtest
    curve by construction.

    The rebalance grid is anchored at the END (`rebal_anchor="end"`) so the `as_of`
    row is a fresh rebalance, not a ffilled hold.

    Returns
    -------
    book : Series of nonzero target weights, indexed by ticker, sorted descending.
    """
    from csm import signals as sig_mod

    signals = sig_mod.primary_signal(prices, cfg)
    pos     = build_positions(signals, prices, cfg, pit_df=pit_df, rebal_anchor="end")

    if as_of is None:
        as_of = pos.index[-1]
    w = pos.loc[as_of].copy()
    w = w[w > 0.0]
    return w.sort_values(ascending=False)
