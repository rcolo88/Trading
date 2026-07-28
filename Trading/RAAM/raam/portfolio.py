"""Fixed 20%-per-slot sizing + cash substitution — the single source of truth
for "what RAAM holds on any given date." Both the backtest and the live
`ideas` book build on `target_book` below, so trading it reproduces the
validated backtest by construction (mirrors csm/portfolio.py's target_book).

Deliberately NO vol-scaling and NO SPY regime gate, unlike Cross-Sectional
Momentum: RAAM's risk control IS the model — the Volatility rank, the Trend
term, and the Absolute-Momentum cash filter already do that job. Layering
CSM's overlays on top would stop this from being a recreation of the paper.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from raam import indicators as ind_mod
from raam import ranking as rank_mod
from raam import universe as univ_mod


def build_positions(
    picks:       pd.DataFrame,   # (rebal_dates x tickers) bool, from ranking.select_book
    M:           pd.DataFrame,   # (T x tickers) Absolute Momentum, from indicators
    close:       pd.DataFrame,   # (T x tickers) daily close panel — defines the full daily index
    cfg:         dict,
    tickers:     list[str] | None = None,
    cash_ticker: str | None = None,
) -> pd.DataFrame:
    """Target weight per ticker (incl. cash), forward-filled between rebalances.

    Each of the n_select (default 5) slots gets a fixed 1/n_select weight.
    A slot keeps its name only if it has POSITIVE Absolute Momentum at
    the rebalance date; otherwise (negative/NaN momentum, or the slot has no
    candidate at all because the universe hasn't grown to n_select names yet)
    the slot's weight goes to cash instead. All slots failing -> 100% cash,
    exactly the paper's stated extreme case ("In an extreme case where all 5
    of these ETFs have a negative Absolute Momentum, Cash will assume a 100%
    weighting").

    `tickers`/`cash_ticker` default to RAAM's native 7Twelve universe
    (`univ_mod.RANKABLE` / `univ_mod.CASH_TICKER`) — pass alternatives to
    build a book over a different universe (e.g. S&P 1500 names + SHY).
    """
    n_select    = int(cfg.get("ranking", {}).get("n_select", 5))
    slot_weight = 1.0 / n_select
    cash        = cash_ticker if cash_ticker is not None else univ_mod.CASH_TICKER
    all_cols    = (tickers if tickers is not None else univ_mod.RANKABLE) + [cash]

    target = pd.DataFrame(np.nan, index=close.index, columns=all_cols, dtype=np.float64)

    for d in picks.index:
        if d not in target.index:
            continue
        chosen = list(picks.columns[picks.loc[d]])
        row = pd.Series(0.0, index=all_cols)
        for t in chosen:
            m = M.loc[d, t] if (d in M.index and t in M.columns) else np.nan
            if pd.notna(m) and m > 0.0:
                row[t] += slot_weight
            else:
                row[cash] += slot_weight
        row[cash] += slot_weight * (n_select - len(chosen))   # unfilled slots -> cash
        target.loc[d] = row

    return target.ffill().fillna(0.0)


def portfolio_returns(positions: pd.DataFrame, close: pd.DataFrame, cfg: dict) -> pd.Series:
    """Daily net portfolio returns (close-to-close, 1-day execution lag), costed.

    SHY is priced like every other holding (it is a real short-duration
    Treasury ETF with its own small positive carry, not literal 0% cash) —
    exactly why the paper chose it as the cash sleeve instead of a flat rate.
    """
    from raam.costs import apply_costs
    all_cols = list(positions.columns)
    ret      = close[all_cols].ffill(limit=3).pct_change().fillna(0.0)
    exec_pos = positions.shift(1).fillna(0.0)
    gross    = (exec_pos * ret).sum(axis=1)
    return apply_costs(gross, exec_pos, cfg)


def build_positions_from_scratch(ohlc: pd.DataFrame, close: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Run the full ranking engine (indicators -> Total Rank -> selection -> weights)."""
    indicators = ind_mod.compute_indicators(ohlc, univ_mod.RANKABLE, cfg)
    total_rank = rank_mod.compute_total_rank(indicators, close, cfg)
    n_select   = int(cfg.get("ranking", {}).get("n_select", 5))
    picks      = rank_mod.select_book(total_rank, n_select=n_select)
    return build_positions(picks, indicators["M"], close, cfg)


def target_book(
    ohlc:  pd.DataFrame,
    close: pd.DataFrame,
    cfg:   dict,
    as_of: pd.Timestamp | None = None,
) -> pd.Series:
    """The single source of truth for "what RAAM holds on `as_of`".

    Rebuilds the full ranking -> selection -> weight engine and returns the
    nonzero target weights on `as_of` (defaults to the panel's last date).
    Both the live `ideas` command and `verify-book` call this.
    """
    pos = build_positions_from_scratch(ohlc, close, cfg)
    if as_of is None:
        as_of = pos.index[-1]
    w = pos.loc[as_of].copy()
    w = w[w > 0.0]
    return w.sort_values(ascending=False)
