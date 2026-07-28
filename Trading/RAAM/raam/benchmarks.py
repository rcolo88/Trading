"""The paper's own comparison set: Core 7Twelve, SPY, and the Salient Risk
Parity Index (Giordano 2018, Fig. 17/19) — reproduced as faithfully as real
data allows, per Robert's instruction to benchmark this recreation against
the paper's own benchmarks rather than a different comparison set.

The Salient Risk Parity Index itself is NOT obtainable: Salient was acquired
by Westwood in 2022 and the index is no longer published; the ticker that
looks like a match, SRPIX, actually resolves to *ProFunds Short Real Estate* —
an unrelated inverse-REIT fund. Checked its stats directly against the paper's
own Figure 19 numbers: -83% absolute return vs the paper's +147%, a
one-hundred-plus-point miss, confirming it is the wrong instrument, not just a
noisy proxy. `risk_parity_10vol` below instead reconstructs what the paper
itself says the index is — "a Risk Parity portfolio with 10% Volatility
Targeting" — from the same 12-ETF universe RAAM ranks, so it is computed on
OUR data with OUR cost model and is a fair apples-to-apples comparison in a
way a scraped third-party series could never be. `SALIENT_PUBLISHED` below
holds the paper's own Figure 19 numbers as reference constants, printed
alongside for context and clearly labelled as such — not as something this
codebase reproduces.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from raam import ranking as rank_mod
from raam import universe as univ_mod

# Giordano (2018), Figure 19 — "Ranked Asset Allocation Model (RAAM) and
# Salient Risk Parity Index summary statistics." The paper's own published
# numbers for its Salient benchmark, Jul-2004 -> Nov-2017, gross of all costs.
SALIENT_PUBLISHED = {
    "source":              "Giordano (2018), Figure 19 — published, not reproduced",
    "period":              "2004-07 to 2017-11",
    "absolute_return":     1.4696,     # 146.96%
    "annualized_std":      0.0980,     #   9.80%
    "sharpe":              0.56,
    "worst_year":          -0.1687,    # -16.87%
    "best_year":            0.1857,    #  18.57%
    "worst_month":         -0.1499,    # -14.99%
    "best_month":            0.0693,   #   6.93%
    "max_drawdown_3m":     -0.2282,    # -22.82% (paper's rolling 3-month DD, not peak-to-trough)
    "positive_months":     102,
    "negative_months":      59,
}


# ─────────────────────────────────────────────────────────────────────────────
#  Core 7Twelve — equal-weight (1/12), incl. SHY's own sleeve slot
# ─────────────────────────────────────────────────────────────────────────────

def core_7twelve(close: pd.DataFrame, rebal_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Equal-weight (1/12) 7Twelve, monthly rebalanced ("each ETF has a weight
    of 8.3% and the allocation does not change according to market conditions"
    — Giordano Sec. II — read as maintained via periodic rebalancing, since
    unrebalanced weights drift).

    Availability-masked exactly like RAAM's own book (raam/portfolio.py): a
    sleeve whose ETF doesn't have real price history yet redirects its 1/12 to
    SHY. This isolates "does the ranking add value over the passive basket" —
    both sides of the comparison face the identical real-data constraint, so
    neither benefits from synthetic pre-inception history.
    """
    cols = univ_mod.ALL_TICKERS
    cash = univ_mod.CASH_TICKER
    slot = 1.0 / len(cols)
    target = pd.DataFrame(np.nan, index=close.index, columns=cols, dtype=np.float64)
    for d in rebal_dates:
        if d not in target.index:
            continue
        row = pd.Series(0.0, index=cols)
        for t in cols:
            avail = (t in close.columns
                      and pd.notna(close.loc[d, t])
                      and int(close[t].loc[:d].notna().sum()) > 0)
            if avail:
                row[t] += slot
            elif t != cash:
                row[cash] += slot
            # t == cash and unavailable: leave unassigned — only possible pre-SHY
            # inception (2002-07-30), before any comparison window of interest.
        target.loc[d] = row
    return target.ffill().fillna(0.0)


# ─────────────────────────────────────────────────────────────────────────────
#  SPY buy-and-hold
# ─────────────────────────────────────────────────────────────────────────────

def spy_buy_hold_returns(close: pd.DataFrame) -> pd.Series:
    return close[univ_mod.SPY].ffill(limit=3).pct_change().fillna(0.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Reconstructed "Risk Parity portfolio with 10% Volatility Targeting"
# ─────────────────────────────────────────────────────────────────────────────

def _inverse_vol_weights(close: pd.DataFrame, cols: list[str], window: int) -> pd.DataFrame:
    """Daily inverse-realized-vol weights, renormalized among tickers with real
    price history on that day (same availability principle as everywhere else)."""
    ret  = close[cols].ffill(limit=3).pct_change()
    vol  = ret.rolling(window).std() * np.sqrt(252)
    inv  = (1.0 / vol.replace(0, np.nan)).where(close[cols].notna())
    return inv.div(inv.sum(axis=1), axis=0)


def risk_parity_10vol(close: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Inverse-vol weights across the 12-ETF universe, monthly rebalanced,
    scaled to a 10% annualized vol target (capped at 100% gross — no
    leverage, matching the no-leverage convention used throughout this repo).
    Returns a target-WEIGHT panel (like build_positions), not a return series,
    so the caller applies the same costed portfolio_returns path as everything
    else — an apples-to-apples comparison.
    """
    rcfg       = cfg.get("benchmarks", {}).get("risk_parity", {})
    window     = int(rcfg.get("vol_window", 63))
    target_vol = float(rcfg.get("target_vol", 0.10))
    cols       = univ_mod.ALL_TICKERS

    w_rel       = _inverse_vol_weights(close, cols, window=window)
    rebal_dates = rank_mod.month_end_dates(close.index)

    target = pd.DataFrame(np.nan, index=close.index, columns=cols, dtype=np.float64)
    on_rebal = target.index.isin(rebal_dates)
    target.loc[on_rebal] = w_rel.loc[on_rebal]
    base_w = target.ffill().fillna(0.0)

    daily_ret = close[cols].ffill(limit=3).pct_change().fillna(0.0)
    rough_ret = (base_w.shift(1).fillna(0.0) * daily_ret).sum(axis=1)
    realized_vol = rough_ret.rolling(window).std() * np.sqrt(252)
    scale = (target_vol / realized_vol).clip(upper=1.0).fillna(1.0).clip(lower=0.0)

    return base_w.multiply(scale, axis=0)
