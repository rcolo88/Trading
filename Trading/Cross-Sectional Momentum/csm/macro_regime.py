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

from pathlib import Path

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

# 2026-08-05 blend-return-research Phase 1.2: REGIME_BASKETS above puts 5-8
# sector SPDRs (equity beta) in every quadrant, including stagflation/
# deflation — regimes where the whole point is to hold something OTHER than
# equity beta. This variant pushes those two quadrants to majority
# non-equity (real assets, duration, credit) while leaving goldilocks/
# reflation as equity-tilted (directionally correct when growth is genuinely
# up). Same equal-weight, long-only, "ask the data" convention as v1 — no
# parameter here was fit to this project's backtest.
REGIME_BASKETS_V2: dict[str, list[str]] = {
    "goldilocks":  ["XLK", "XLY", "XLC", "XLI", "XLB"],
    "reflation":   ["XLE", "XLF", "DBC", "EEM", "TIP"],
    "stagflation": ["GLD", "TIP", "DBC", "XLE", "XLU"],
    "deflation":   ["TLT", "IEF", "GLD", "LQD", "XLU"],
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


# 2026-08-05 blend-return-research Phase 1.1: `growth_score` above is a 63d
# cyclicals-minus-defensives EQUITY spread — measured this session at 0.766
# daily correlation with the blend's growth (SPYM) sleeve, i.e. it cannot
# diversify equity by construction. This variant replaces it with an
# equal-weight vote of three MACRO RELEASES (never equity prices), so the
# axis is orthogonal to the growth sleeve by construction rather than by
# fitting: UNRATE below its trailing 12-month MA (labor market improving),
# NFCI below its trailing 26-week MA (financial conditions loosening), and
# T10Y2Y > 0 (a positively-sloped curve, the classic growth-expectations
# proxy). Each vote is z-scored against the SAME point-in-time vintage
# series' own trailing history (no separate look-ahead in the
# standardization step — see csm/fred.py's module docstring for why
# `realtime_start=realtime_end=asof` already excludes both revision and
# publication look-ahead from the raw series itself).
_UNRATE_MA_MONTHS = 12
_NFCI_MA_WEEKS    = 26


def growth_score_macro(
    index:          pd.DatetimeIndex,
    rebal_dates:    pd.DatetimeIndex,
    cache_dir:      Path,
    project_root:   Path | None = None,
    api_key:        str | None = None,
    lookback_years: int = 20,
) -> pd.Series:
    """Macro-release growth axis, computed point-in-time at each date in
    `rebal_dates` (the only dates `macro_tilt_weights` ever reads) and
    forward-filled to `index` so the result is shaped like `growth_score`'s.
    Returns NaN at a date where none of the three inputs have enough
    point-in-time history yet (early-history warmup); `classify_regime`
    already treats a NaN growth/inflation score date as "no basket".
    """
    from csm import fred as fred_mod
    if api_key is None:
        api_key = fred_mod.get_api_key(project_root)

    raw = pd.Series(index=rebal_dates, dtype=float)
    for d in rebal_dates:
        obs_start = (d - pd.DateOffset(years=lookback_years)).strftime("%Y-%m-%d")
        votes = []

        unrate = fred_mod.vintage_series("UNRATE", d, obs_start, cache_dir, api_key=api_key)
        trend = (unrate - unrate.rolling(_UNRATE_MA_MONTHS).mean()).dropna()
        if len(trend) >= _UNRATE_MA_MONTHS and trend.std() > 0:
            votes.append(-(trend.iloc[-1] - trend.mean()) / trend.std())  # below MA => growth+

        nfci = fred_mod.vintage_series("NFCI", d, obs_start, cache_dir, api_key=api_key)
        trend = (nfci - nfci.rolling(_NFCI_MA_WEEKS).mean()).dropna()
        if len(trend) >= _NFCI_MA_WEEKS and trend.std() > 0:
            votes.append(-(trend.iloc[-1] - trend.mean()) / trend.std())  # loosening => growth+

        t10y2y = fred_mod.vintage_series("T10Y2Y", d, obs_start, cache_dir, api_key=api_key)
        t10y2y = t10y2y.dropna()
        if len(t10y2y) >= 252 and t10y2y.std() > 0:
            votes.append((t10y2y.iloc[-1] - t10y2y.mean()) / t10y2y.std())  # steeper => growth+

        if votes:
            raw.loc[d] = float(np.mean(votes))

    return raw.reindex(index).ffill()


# 2026-08-12 Phase 2.5: the inflation-axis counterpart to `growth_score_macro`
# above, DEFAULT-OFF (nothing in `blend.py`/config calls this unless
# `blend.macro_inflation_axis: macro` is explicitly set — see config.yaml).
# Built for symmetry with the growth axis, not yet return-tested the way the
# 2026-08-05 growth-axis variant was (that one was tried and REJECTED for
# overfitting the recent window — see config.yaml's `macro_growth_axis`
# comment). Treat this the same way until it's been through an equivalent
# full-history + OOS + 2000-2014-holdout pass: an available override, not a
# recommendation.
#
# Same equal-weight-vote, own-history-z-score construction as growth_score_
# macro, but on genuine price-level RELEASES rather than labor/financial-
# conditions releases: CPIAUCSL YoY change trending above its own trailing
# 12-month average (headline inflation accelerating), PCEPILFE YoY change
# (core PCE, the Fed's actual target gauge) trending above its own trailing
# 12-month average, and T10YIE (10Y market breakeven) above its own trailing
# history (the market pricing in more inflation). Each vote point-in-time via
# csm.fred.vintage_series, same look-ahead discipline as growth_score_macro.
_CPI_MA_MONTHS = 12
_PCE_MA_MONTHS = 12


def inflation_score_macro(
    index:          pd.DatetimeIndex,
    rebal_dates:    pd.DatetimeIndex,
    cache_dir:      Path,
    project_root:   Path | None = None,
    api_key:        str | None = None,
    lookback_years: int = 20,
) -> pd.Series:
    """Macro-release inflation axis, computed point-in-time at each date in
    `rebal_dates` and forward-filled to `index` — shaped like
    `growth_score_macro`'s output so it can be passed as `classify_regime`'s
    `inflation=` override. Returns NaN at a date where none of the three
    inputs have enough point-in-time history yet (early-history warmup);
    `classify_regime` already treats a NaN growth/inflation score date as
    "no basket".
    """
    from csm import fred as fred_mod
    if api_key is None:
        api_key = fred_mod.get_api_key(project_root)

    raw = pd.Series(index=rebal_dates, dtype=float)
    for d in rebal_dates:
        obs_start = (d - pd.DateOffset(years=lookback_years)).strftime("%Y-%m-%d")
        votes = []

        cpi = fred_mod.vintage_series("CPIAUCSL", d, obs_start, cache_dir, api_key=api_key)
        yoy = cpi.pct_change(12).dropna()
        trend = (yoy - yoy.rolling(_CPI_MA_MONTHS).mean()).dropna()
        if len(trend) >= _CPI_MA_MONTHS and trend.std() > 0:
            votes.append((trend.iloc[-1] - trend.mean()) / trend.std())  # above MA => inflation+

        pce = fred_mod.vintage_series("PCEPILFE", d, obs_start, cache_dir, api_key=api_key)
        yoy = pce.pct_change(12).dropna()
        trend = (yoy - yoy.rolling(_PCE_MA_MONTHS).mean()).dropna()
        if len(trend) >= _PCE_MA_MONTHS and trend.std() > 0:
            votes.append((trend.iloc[-1] - trend.mean()) / trend.std())  # above MA => inflation+

        breakeven = fred_mod.vintage_series("T10YIE", d, obs_start, cache_dir, api_key=api_key)
        breakeven = breakeven.dropna()
        if len(breakeven) >= 252 and breakeven.std() > 0:
            votes.append((breakeven.iloc[-1] - breakeven.mean()) / breakeven.std())  # higher => inflation+

        if votes:
            raw.loc[d] = float(np.mean(votes))

    return raw.reindex(index).ffill()


def classify_regime(
    close:     pd.DataFrame,
    window:    int = 63,
    growth:    pd.Series | None = None,
    inflation: pd.Series | None = None,
) -> pd.Series:
    """Returns a Series of {"goldilocks","reflation","stagflation","deflation"}.

    `growth` overrides the default price-based `growth_score` — pass
    `growth_score_macro(...)`'s output for the Phase 1.1 macro-release axis.
    `inflation` overrides the default price-based `inflation_score` — pass
    `inflation_score_macro(...)`'s output for the Phase 2.5 macro-release axis.
    """
    g = growth if growth is not None else growth_score(close, window=window)
    i = inflation if inflation is not None else inflation_score(close, window=window)
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
    growth:      pd.Series | None = None,
    inflation:   pd.Series | None = None,
    baskets:     dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Target weight per basket ticker (+ cash), forward-filled between
    rebalances. On each rebal date, classify the regime and equal-weight the
    that regime's AVAILABLE basket tickers (those with real price history by
    that date); any basket with zero available tickers falls back to cash.

    `growth` overrides the price-based growth axis (Phase 1.1); `inflation`
    overrides the price-based inflation axis (Phase 2.5); `baskets` overrides
    REGIME_BASKETS (Phase 1.2, e.g. REGIME_BASKETS_V2).
    """
    regime  = classify_regime(close, window=window, growth=growth, inflation=inflation)
    baskets = baskets if baskets is not None else REGIME_BASKETS
    all_cols = sorted({t for b in baskets.values() for t in b} | {cash_ticker})
    target = pd.DataFrame(np.nan, index=close.index, columns=all_cols, dtype=np.float64)

    for d in rebal_dates:
        if d not in target.index or d not in regime.index or pd.isna(regime.get(d)):
            continue
        basket = baskets[regime[d]]
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
