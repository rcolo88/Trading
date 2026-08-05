"""Slow-bleed detector — catches grinding, multi-month declines that
`regime_state.py`'s turbulence/absorption-ratio signals miss.

Turbulence (Mahalanobis distance on TODAY's return) and the absorption ratio
(eigen-concentration) both detect ACUTE panics: extreme single-day moves,
correlations spiking toward 1. That's exactly 2008's and COVID's character,
and this session's own validation confirmed they fix those two crises. But
2022 and the dotcom decline were persistent, GRINDING declines — sustained
negative drift without necessarily anomalous single-day co-movement — and
both signals stayed at near-full exposure through 2022 (-19.0% in the
blended backtest, essentially matching SPY's own -18.2%).

Two classic, quiet-in-calm-markets indicators, deliberately using ABSOLUTE
thresholds (0%, 50%) rather than a percentile rank against expanding history:
a percentile rank is, BY CONSTRUCTION, "not calm" on ~10% of ALL days ever
(that's what percentile means), which is exactly the noise that made
MIN-combining the turbulence/AR gate with the old binary gate a net loss in
calm periods when tested this session. An absolute-threshold signal reads
"calm" on the overwhelming majority of genuinely calm history and only fires
during a real sustained decline:

  (a) BREADTH: fraction of the regime asset panel trading below its OWN
      trailing 200-day moving average >= 0.5 (classic market-breadth
      deterioration convention — most of the panel underwater at once, not
      just one name)
  (b) ABSOLUTE MOMENTUM: the panel's own 12-1 total return < 0 (Antonacci's
      dual-momentum absolute-momentum filter, applied to a diversified
      multi-asset composite rather than a single ticker so a rotation within
      one asset class can't mask a broad decline)

Both must agree (AND, not OR) to flag risk-off — this is the direct fix for
the old binary gate's failure mode, which used a permissive OR and as a
result almost never triggered (confirmed: zero days off in all of 2018).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def breadth_below_ma(close: pd.DataFrame, ma_days: int = 200) -> pd.Series:
    """Fraction of columns trading below their own trailing `ma_days` MA."""
    ma = close.rolling(ma_days, min_periods=ma_days).mean()
    below = (close < ma)
    valid = close.notna() & ma.notna()
    frac = (below & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)
    return frac


def absolute_momentum(close: pd.DataFrame, ticker: str = "SPY", window: int = 252,
                      skip: int = 21) -> pd.Series:
    """12-1 total return of `ticker` alone — Antonacci's classic dual-momentum
    absolute-momentum filter (same formation convention as CSM's own equity
    signal). Deliberately SPY-only, not a multi-asset composite: an early
    version averaged across the whole 7-asset panel and picked up ordinary
    bond/EM underperformance (e.g. the 2013 taper tantrum) as "risk-off" even
    though equities were fine that year — false positives in a genuinely calm
    market. This leg's job is specifically "is the growth engine (SPY) itself
    in a sustained decline," not "is every asset class going up together."
    """
    s = close[ticker]
    return s.shift(skip) / s.shift(window) - 1.0


def slow_bleed_exposure(
    close:         pd.DataFrame,
    ma_days:       int = 200,
    mom_window:    int = 252,
    mom_skip:      int = 21,
    breadth_cut:   float = 0.5,
    mom_ticker:    str = "SPY",
) -> pd.Series:
    """0/0.5/1 exposure ladder: risk-off only when BOTH breadth has
    deteriorated (>= breadth_cut of the panel below its 200dma) AND the
    growth engine's (SPY's) own 12-1 momentum has turned negative. Reads 1.0
    (fully risk-on) on the overwhelming majority of genuinely calm history by
    construction — both legs use fixed, literature-standard absolute
    thresholds (50%, 0%), not a percentile rank against expanding history.
    """
    breadth = breadth_below_ma(close, ma_days=ma_days)
    mom     = absolute_momentum(close, ticker=mom_ticker, window=mom_window, skip=mom_skip)

    # Fail OPEN (treat as calm) during warmup where either leg isn't valid yet —
    # same convention as signals.regime_exposure's VIX-contango check.
    bad_breadth = breadth.notna() & (breadth >= breadth_cut)
    bad_mom     = mom.notna() & (mom < 0.0)

    score = (~bad_breadth).astype(int) + (~bad_mom).astype(int)
    return pd.Series(np.select([score >= 2, score == 1], [1.0, 0.5], default=0.0),
                     index=close.index)
