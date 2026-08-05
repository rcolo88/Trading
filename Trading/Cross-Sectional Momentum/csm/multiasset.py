"""Multi-asset defensive/crisis-alpha rotation sleeve — Track B (Phase 3).

Track A (the equity cross-sectional momentum sleeve) was tested and killed:
sector-capping, beta-capping, and inverse-vol weighting all failed to produce
alpha distinguishable from zero (t < 1.5 in every variant — see
config.yaml validation.trial_sharpes and the 2026-08-04 session notes).
"Profitable across all regimes" therefore has to come from portfolio
construction, not better stock-picking: this module is that piece.

Rotates among a small, literature-motivated set of defensive/diversifying
ETFs using 12-1 absolute momentum — the SAME convention as CSM's own equity
signal (see csm/signals.py residual_momentum). Holds the top `top_n`
candidates with POSITIVE momentum, equal-weighted; unfilled slots (negative
momentum, or a name not listed yet) park in SHY (short Treasuries) rather
than literal 0% cash.

Roster, and why each name earns a slot:
  IEF, TLT   — flight-to-quality Treasuries (what the OLD single-asset
               `regime_filter.defensive: IEF` relied on exclusively)
  GLD        — inflation hedge / uncorrelated in stagflationary drawdowns
  DBC        — broad commodities, same rationale as GLD
  DBMF       — a diversified managed-futures/CTA replicator: this ONE ticker
               already carries genuine trend-following crisis-alpha exposure
               across many asset classes, so a single absolute-momentum
               rotation over this roster captures both the "flight to
               quality" and "trend/crisis alpha" ideas from the plan without
               hand-rolling a separate signal
  BTAL       — anti-beta market-neutral, direct hedge against systematic risk

This is the SPECIFIC fix for 2022, where bonds fell alongside equities and a
lone IEF substitution failed for exactly that reason (see
options-regime-conditional-params / options-calendar-vs-bullput-comparison
memory for the analogous VIX-complex lesson): the rotation can hold
DBC/GLD/DBMF/BTAL instead when Treasuries are also drawing down.

Data: the LIVE engine (`csmom.py`) downloads this roster itself via
`csm/data.py::load_price_panel` (added to `DEFENSIVE_ROSTER`/
`ROTATION_CASH_TICKER` there) — this module has NO runtime dependency on
another project's cache for live use. `load_defensive_panel` below is kept
ONLY for standalone research reproducibility against RAAM's longer (2000+)
niche-ETF history, via the same `sys.path` cross-project reuse pattern used
elsewhere in this monorepo (Options/src/utils/trend_gate.py, RAAM/raam_sp1500.py
importing csm.universe) — it is not called anywhere in the live path.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DEFENSIVE_ROSTER = ["IEF", "TLT", "GLD", "DBC", "DBMF", "BTAL"]
CASH_TICKER      = "SHY"


def load_defensive_panel(cache_dir: Path, end: str | None = None) -> pd.DataFrame:
    """RESEARCH-ONLY: close-price panel from RAAM's niche cache (2000→today).

    Not used by the live engine (see module docstring) — kept for reproducing
    the 2026-08-04 session's 2000-2026 validation against a longer history
    than CSM's own price cache (which starts 2010).
    """
    import sys
    raam_root = Path(__file__).resolve().parents[2] / "RAAM"
    if str(raam_root) not in sys.path:
        sys.path.insert(0, str(raam_root))
    from raam import data as raam_data

    tickers = DEFENSIVE_ROSTER + [CASH_TICKER, "SPY"]
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    ohlc = raam_data.load_ohlc_panel(tickers, start="auto", end=end, cache_dir=cache_dir)
    return raam_data.close_panel(ohlc)


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last actual trading day of each calendar month present in `index`.

    Inlined (not imported from RAAM) so the live engine has zero runtime
    dependency on another project's directory existing. Deliberately NOT
    `index.to_series().resample("ME").last()`: that would treat whatever the
    LAST row of a possibly-in-progress month happens to be as if it were the
    month's close — e.g. if `index` ends mid-month, resample("ME") misclassifies
    today as month-end and triggers a rebalance early. Instead, generate the
    canonical business-month-end calendar and only emit one once the panel's
    data actually reaches it.
    """
    if len(index) == 0:
        return pd.DatetimeIndex([])
    canonical = pd.date_range(index.min(), index.max(), freq="BME")
    out = []
    for me in canonical:
        avail = index[index <= me]
        if len(avail):
            out.append(avail[-1])
    return pd.DatetimeIndex(sorted(set(out)))


def absolute_momentum(close: pd.DataFrame, window: int = 252, skip: int = 21) -> pd.DataFrame:
    """12-1 total return — the SAME formation convention as CSM's own equity
    signal (skip the most recent month to avoid short-term reversal)."""
    return close.shift(skip) / close.shift(window) - 1.0


def defensive_weights(
    close:       pd.DataFrame,
    rebal_dates: pd.DatetimeIndex,
    roster:      list[str] | None = None,
    top_n:       int = 2,
    window:      int = 252,
    skip:        int = 21,
    cash_ticker: str = CASH_TICKER,
) -> pd.DataFrame:
    """Target weight per defensive ticker (+ cash_ticker), forward-filled between
    rebalances. Every rebalance date, rank `roster` by 12-1 absolute momentum,
    hold the top `top_n` with POSITIVE momentum equal-weighted; any unfilled
    slot — negative momentum, or a name not listed yet (`dropna()` excludes it,
    "ask the data" not an assumed inception date) — goes to `cash_ticker`.
    """
    roster = roster or DEFENSIVE_ROSTER
    mom = absolute_momentum(close[roster], window=window, skip=skip)
    all_cols = roster + [cash_ticker]
    target = pd.DataFrame(np.nan, index=close.index, columns=all_cols, dtype=np.float64)
    slot_w = 1.0 / top_n

    for d in rebal_dates:
        if d not in target.index:
            continue
        row = mom.loc[d].dropna().sort_values(ascending=False)
        chosen = [t for t in row.index[:top_n] if row[t] > 0.0]
        w = pd.Series(0.0, index=all_cols)
        for t in chosen:
            w[t] = slot_w
        w[cash_ticker] += slot_w * (top_n - len(chosen))
        target.loc[d] = w

    return target.ffill().fillna(0.0)
