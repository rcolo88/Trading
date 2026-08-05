"""Macro growth/inflation regime classifier and sector/asset tilt allocation —
"Macro Optics"-style quadrant framework, built from FREE market-observable
proxies (yfinance only). Requested 2026-08-05 after the user shared a macro
framework using four regimes:

  Goldilocks (growth UP,   inflation DOWN) — risk-on, low rates pressure
  Reflation  (growth UP,   inflation UP)   — broad cyclical boom
  Stagflation(growth DOWN, inflation UP)   — defensive + real assets
  Deflation  (growth DOWN, inflation DOWN) — flight to quality

DISCLOSED SUBSTITUTION: the source framework references data this environment
cannot reach (FRED's CPI/M2 series timed out repeatedly; "global liquidity"
and "fiscal policy" are not free, machine-readable series at all). Every input
here is instead a MARKET-OBSERVABLE proxy for the same underlying idea —
arguably more honest for a systematic strategy anyway, since official
macro releases are lagged/revised and a daily market proxy isn't:

  GROWTH   = 63d return of an equal-weight cyclicals basket (XLY, XLI, XLF,
             XLB) minus the same for a defensives basket (XLU, XLP, XLV).
  INFLATION= 63d return of TIP/IEF relative strength (a standard market-based
             breakeven-inflation proxy: TIP outperforming nominal Treasuries
             means the market is pricing MORE inflation) averaged with 63d
             commodity momentum (DBC) — matching the source framework's own
             callout that "oil and commodities are leading indicators."

Both are zero-crossing signals (>0 / <0), not fit or tuned to this backtest's
data — literature/convention-motivated thresholds, same discipline as
`regime_state.py`/`slow_bleed.py`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CYCLICALS  = ["XLY", "XLI", "XLF", "XLB"]
DEFENSIVES = ["XLU", "XLP", "XLV"]

# Per-regime overweight basket, transcribed from the "higher probability"
# column of the user's Macro Optics lens menu, restricted to tickers with
# real, freely available price history (GICS sector SPDRs + a few asset
# classes). Equal-weighted, long-only — consistent with the rest of this
# project. A basket ticker not yet listed on a given date is simply skipped
# ("ask the data", not an assumed inception — same convention as
# universe.eligible_on/multiasset.defensive_weights).
REGIME_BASKETS: dict[str, list[str]] = {
    "goldilocks":  ["XLK", "XLY", "XLC", "XLI", "XLB"],
    "reflation":   ["XLK", "XLE", "XLF", "XLI", "XLB", "XLY", "EEM", "DBC"],
    "stagflation": ["XLE", "XLU", "XLV", "XLP", "GLD", "TIP"],
    "deflation":   ["XLRE", "XLU", "XLV", "XLP", "GLD", "TLT", "LQD"],
}
CASH_TICKER = "SHY"


def growth_score(close: pd.DataFrame, window: int = 63) -> pd.Series:
    cyc = [t for t in CYCLICALS if t in close.columns]
    dfn = [t for t in DEFENSIVES if t in close.columns]
    cyc_ret = close[cyc].pct_change(window).mean(axis=1, skipna=True)
    dfn_ret = close[dfn].pct_change(window).mean(axis=1, skipna=True)
    return cyc_ret - dfn_ret


def inflation_score(close: pd.DataFrame, window: int = 63) -> pd.Series:
    breakeven = close["TIP"].pct_change(window) - close["IEF"].pct_change(window)
    commodity = close["DBC"].pct_change(window)
    return (breakeven + commodity) / 2.0


def classify_regime(close: pd.DataFrame, window: int = 63) -> pd.Series:
    """Returns a Series of {"goldilocks","reflation","stagflation","deflation"}."""
    g = growth_score(close, window=window)
    i = inflation_score(close, window=window)
    regime = pd.Series(index=close.index, dtype=object)
    regime[(g >= 0) & (i < 0)]  = "goldilocks"
    regime[(g >= 0) & (i >= 0)] = "reflation"
    regime[(g < 0)  & (i >= 0)] = "stagflation"
    regime[(g < 0)  & (i < 0)]  = "deflation"
    return regime


def macro_tilt_weights(
    close:       pd.DataFrame,
    rebal_dates: pd.DatetimeIndex,
    window:      int = 63,
    cash_ticker: str = CASH_TICKER,
) -> pd.DataFrame:
    """Target weight per basket ticker (+ cash), forward-filled between
    rebalances. On each rebal date, classify the regime and equal-weight the
    that regime's AVAILABLE basket tickers (those with real price history by
    that date); any basket with zero available tickers falls back to cash.
    """
    regime = classify_regime(close, window=window)
    all_cols = sorted({t for b in REGIME_BASKETS.values() for t in b} | {cash_ticker})
    target = pd.DataFrame(np.nan, index=close.index, columns=all_cols, dtype=np.float64)

    for d in rebal_dates:
        if d not in target.index or d not in regime.index or pd.isna(regime.get(d)):
            continue
        basket = REGIME_BASKETS[regime[d]]
        avail = [t for t in basket if t in close.columns and pd.notna(close.loc[d, t])
                and close[t].loc[:d].notna().sum() >= window]
        w = pd.Series(0.0, index=all_cols)
        if avail:
            for t in avail:
                w[t] = 1.0 / len(avail)
        else:
            w[cash_ticker] = 1.0
        target.loc[d] = w

    return target.ffill().fillna(0.0)
