"""Risk overlays for the 3-way blend — Phase 2 of the 2026-08-05 blend-
return-research pass. Each function returns a daily exposure multiplier in
[0, 1], aligned to the price panel's index. `blend.blend_target_weights`
only ever SAMPLES this at monthly rebalance dates (it doesn't rebalance more
often just because the underlying signal is daily) — same "compute
continuously, act only at rebal" convention already used for the
regime-adaptive weight experiment that was tested and rejected (see memory
csm-market-neutral-macro-tests), so this doesn't raise turnover the way a
daily-applied overlay would.

Two designs, both pre-registered (no parameter here was fit to this
backtest):
  growth_trend_timing_exposure — Philosophical Economics (2016) / Allocate
    Smartly's Growth-Trend Timing: defensive only when BOTH the price trend
    (SPY below its 10-month MA) and the economic trend (UNRATE above its
    12-month MA, point-in-time) are bearish. Two source-specified parameters.
  combination_ladder_exposure — Rapach-Strauss-Zhou (RFS 2010) combination-
    forecasting discipline: equal-weight mean of K un-tuned risk-on votes, no
    fitted weights, so one bad vote costs ~1/K rather than the whole gate.

A third overlay, `signals.robust_regime_exposure` (turbulence + absorption
ratio + slow-bleed, already built and validated), is used as-is — no new
code needed for that variant.

Explicitly DROPPED from the vote list: stock-level breadth (% of the S&P
1500 above its own 200dma). It requires pulling the full stock panel + PIT
universe into what is otherwise a small, self-contained ETF-only module, and
this project's own 2026-08-05 test found it CONTRARIAN on 2010-2026 (low
breadth predicted BETTER, not worse, forward SPY returns) — not worth the
complexity for a vote that doesn't point the expected direction.

A fourth overlay, `fx_carry_unwind_exposure` below (2026-08-12, GAPS.md #5
framing (b), "the user's yen question"), reuses
`csm.macro_regime._fx_carry_unwind_votes` — see that function's docstring
for the FX vote design and parameter rationale.

A fifth, `credit_curve_risk_off_exposure` (2026-08-12, GAPS.md #6 Protocol
A): T10Y3M curve inversion + HY OAS widening. See its docstring for an
important data-coverage caveat on the HY OAS leg.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's RSI. Implemented locally (not imported from Trend Reversal)
    so this module has no live cross-project dependency — same principle as
    csm/multiasset.py and csm/regime_state.py's own docstrings."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.where(avg_loss != 0.0, 100.0)   # no losses in window => RSI 100


def growth_trend_timing_exposure(
    prices:       pd.DataFrame,
    rebal_dates:  pd.DatetimeIndex,
    cache_dir:    Path,
    api_key:      str | None = None,
    spy_ma_days:  int = 210,   # ~10 trading months
    unrate_ma_months: int = 12,
) -> pd.Series:
    """0/1 exposure: 0 only when SPY < its `spy_ma_days` MA AND UNRATE (as
    known point-in-time on each rebal date) is above its trailing
    `unrate_ma_months` MA — the classic GTT conjunction. UNRATE is only ever
    read AT rebal dates (it's a monthly release) and held between them.
    """
    from csm import fred as fred_mod

    spy = prices["SPY"].ffill()
    price_bear = spy < spy.rolling(spy_ma_days).mean()

    unrate_bear = pd.Series(index=rebal_dates, dtype=float)
    for d in rebal_dates:
        obs_start = (d - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
        u = fred_mod.vintage_series("UNRATE", d, obs_start, cache_dir, api_key=api_key)
        if len(u) >= unrate_ma_months:
            ma = u.rolling(unrate_ma_months).mean().iloc[-1]
            if pd.notna(ma):
                unrate_bear.loc[d] = float(u.iloc[-1] > ma)
    unrate_bear = (unrate_bear.reindex(prices.index).ffill()
                  .fillna(0.0).astype(bool))   # unknown => not bearish (fail open)

    defensive = price_bear.reindex(prices.index).fillna(False) & unrate_bear
    return (~defensive).astype(float)


def combination_ladder_exposure(
    prices:       pd.DataFrame,
    rebal_dates:  pd.DatetimeIndex,
    cache_dir:    Path,
    api_key:      str | None = None,
) -> pd.Series:
    """Equal-weight mean of 7 un-tuned risk-on votes: SPY>200dma, turbulence
    percentile<0.90, absorption-ratio standardized-shift<1sigma, VIX<VIX3M,
    NFCI<its 26-week MA, UNRATE<its 12-month MA, SPY RSI(14)>30. Continuous
    in [0,1] (not discretized) — a finer-grained ladder than the 0/0.5/1
    designs, and the Rapach-Strauss-Zhou point precisely: no single vote's
    idiosyncratic error dominates.
    """
    from csm import fred as fred_mod
    from csm import regime_state as rs_mod
    from csm.signals import _vix_contango_vote

    votes = []

    spy = prices["SPY"].ffill()
    votes.append((spy > spy.rolling(200).mean()).reindex(prices.index)
                .fillna(True).astype(float))

    avail = [c for c in rs_mod.REGIME_ASSETS if c in prices.columns]
    if len(avail) == len(rs_mod.REGIME_ASSETS):
        panel = prices[avail].ffill()
        ret = panel.pct_change()
        turb = rs_mod.turbulence_index(ret)
        turb_pct = turb.expanding(min_periods=252).rank(pct=True)
        votes.append((turb_pct.isna() | (turb_pct < 0.90)).reindex(prices.index)
                    .fillna(True).astype(float))

        ar = rs_mod.absorption_ratio(ret)
        d_ar = rs_mod.standardized_shift(ar)
        votes.append((d_ar.isna() | (d_ar < 1.0)).reindex(prices.index)
                    .fillna(True).astype(float))

    votes.append(_vix_contango_vote(prices).reindex(prices.index)
                .fillna(True).astype(float))

    nfci_vote = pd.Series(index=rebal_dates, dtype=float)
    unrate_vote = pd.Series(index=rebal_dates, dtype=float)
    for d in rebal_dates:
        obs_start = (d - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
        n = fred_mod.vintage_series("NFCI", d, obs_start, cache_dir, api_key=api_key)
        if len(n) >= 26:
            ma = n.rolling(26).mean().iloc[-1]
            if pd.notna(ma):
                nfci_vote.loc[d] = float(n.iloc[-1] < ma)   # loosening => risk-on
        u = fred_mod.vintage_series("UNRATE", d, obs_start, cache_dir, api_key=api_key)
        if len(u) >= 12:
            ma = u.rolling(12).mean().iloc[-1]
            if pd.notna(ma):
                unrate_vote.loc[d] = float(u.iloc[-1] < ma)   # improving => risk-on
    votes.append(nfci_vote.reindex(prices.index).ffill().fillna(1.0))
    votes.append(unrate_vote.reindex(prices.index).ffill().fillna(1.0))

    rsi = _rsi(spy, 14)
    votes.append((rsi > 30).reindex(prices.index).fillna(True).astype(float))

    combined = pd.concat(votes, axis=1).mean(axis=1)
    return combined.reindex(prices.index).fillna(1.0)


def fx_carry_unwind_exposure(
    prices:      pd.DataFrame,
    rebal_dates: pd.DatetimeIndex,
    cache_dir:   Path,
    api_key:     str | None = None,
) -> pd.Series:
    """GAPS.md #5 framing (b): standalone risk-off exposure gate, independent
    of both existing growth/inflation axes — DEFAULT-OFF, wired only under
    `blend.risk_overlay: fx`. Same two FX votes as
    `csm.macro_regime.fx_stress_axis` (framing (a); see
    `csm.macro_regime._fx_carry_unwind_votes` for the vote design and
    parameter rationale), but averaged into a continuous [0,1] exposure
    (same combination-forecasting discipline as `combination_ladder_exposure`
    above) rather than a hard basket override: 1.0 if neither vote triggers,
    0.5 if one does, 0.0 if both a sharp yen appreciation AND a sharp dollar
    spike trigger together.
    """
    from csm import macro_regime as mr_mod

    jpy_vote, usd_vote = mr_mod._fx_carry_unwind_votes(rebal_dates, cache_dir, api_key=api_key)
    triggered = (jpy_vote.fillna(0.0) + usd_vote.fillna(0.0)) / 2.0
    exposure = (1.0 - triggered).reindex(prices.index).ffill().fillna(1.0)
    return exposure


def credit_curve_risk_off_exposure(
    prices:      pd.DataFrame,
    rebal_dates: pd.DatetimeIndex,
    cache_dir:   Path,
    api_key:     str | None = None,
    hy_ma_days:  int = 252,
) -> pd.Series:
    """GAPS.md #6 Protocol A: HY OAS widening and/or T10Y3M inversion as a
    risk-off overlay — DEFAULT-OFF, wired only under `blend.risk_overlay:
    credit_curve`. Two un-tuned votes, equal-weighted (same
    combination-forecasting discipline as `combination_ladder_exposure`):

      - `T10Y3M` (Estrella-Mishkin term spread, `revision: none`, full daily
        history since 1982) < 0 (curve inverted) => risk-off. Covers the
        entire 2000-2014 holdout.
      - `BAMLH0A0HYM2` (HY OAS) above its trailing `hy_ma_days` MA (spreads
        widening vs. their own recent history) => risk-off.

    IMPORTANT DATA CAVEAT: this specific FRED series ID's history only
    starts 2023-08-14 (confirmed via the `fred/series` endpoint — see
    csm/fred.py's SERIES_REGISTRY comment; the pre-1997 BAMLH0A0HYM2 history
    some sources cite lives under a DIFFERENT, discontinued ID). It CANNOT
    cover the 2000-2014 holdout or the GFC. This vote fails open (reads as
    neutral risk-on, same convention every other data-scarce vote in this
    module already uses) wherever it has no data — so a holdout-era backtest
    is scored on the T10Y3M vote alone, not blocked or NaN-propagated, and a
    post-2023-08 backtest gets both votes.
    """
    from csm import fred as fred_mod

    curve_vote  = pd.Series(index=rebal_dates, dtype=float)
    credit_vote = pd.Series(index=rebal_dates, dtype=float)
    for d in rebal_dates:
        obs_start = (d - pd.DateOffset(years=20)).strftime("%Y-%m-%d")

        t10y3m = fred_mod.vintage_series("T10Y3M", d, obs_start, cache_dir,
                                         api_key=api_key).dropna()
        if len(t10y3m):
            curve_vote.loc[d] = float(t10y3m.iloc[-1] >= 0.0)   # inverted => risk-off

        hy = fred_mod.vintage_series("BAMLH0A0HYM2", d, obs_start, cache_dir,
                                     api_key=api_key).dropna()
        if len(hy) >= hy_ma_days:
            ma = hy.rolling(hy_ma_days).mean().iloc[-1]
            if pd.notna(ma):
                credit_vote.loc[d] = float(hy.iloc[-1] <= ma)   # tighter-than-avg => risk-on

    curve_vote  = curve_vote.reindex(prices.index).ffill().fillna(1.0)     # unknown => risk-on
    credit_vote = credit_vote.reindex(prices.index).ffill().fillna(1.0)   # fail-open => risk-on
    return (curve_vote + credit_vote) / 2.0
