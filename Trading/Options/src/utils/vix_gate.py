"""Build a VIX IV-Rank entry gate for the options backtester.

A long calendar is **long vega**: it wants to be opened when volatility is cheap *relative to its own
recent range*, so it can mean-revert up. The literature's "IV Rank < 30" filter captures exactly that.
For SPY/SPX the robust way to compute it is off **VIX itself** — VIX is already a clean, liquid 30-day
ATM-IV index, a far better input than an ATM IV back-solved out of a sparse real chain.

    IV Rank(t) = (VIX_t - min(VIX over trailing `window`)) / (max - min) * 100

The series is fetched with a year of WARMUP before the backtest start so the rank is valid on the very
first trading day (otherwise the first ~252 days would rank against a truncated window). The gate is a
drop-in for ``OptopsyBacktester(config, entry_gate=...)`` and composes (AND) with other gates:

    gate = vix_rank_gate(start="2024-06-16", end="2026-06-16", max_rank=30)  # enter only when cheap

It is a FIXED gate (a threshold from the literature, not an optimized parameter), so it adds no
degrees of freedom to the search and does not deflate the Deflated Sharpe.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_CACHE = Path(__file__).resolve().parents[2] / "data" / "processed" / "vix_history.csv"


def _load_vix(start: str, end: str) -> pd.Series:
    """Daily ^VIX close over [start, end], disk-cached. Refetches only if the cache can't cover it."""
    want_start, want_end = pd.Timestamp(start), pd.Timestamp(end)
    if _CACHE.exists():
        cached = pd.read_csv(_CACHE, parse_dates=["date"]).set_index("date")["vix"].sort_index()
        if cached.index.min() <= want_start and cached.index.max() >= want_end:
            return cached

    import yfinance as yf  # local import: only needed when (re)building the cache
    raw = yf.download("^VIX", start=start, end=end, progress=False, auto_adjust=False)
    if raw.empty:
        raise RuntimeError(f"yfinance returned no ^VIX data for {start}..{end}")
    close = raw["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance can return a 1-col frame for a single ticker
        close = close.iloc[:, 0]
    vix = close.dropna()
    vix.index = pd.to_datetime(vix.index).tz_localize(None).normalize()
    vix.name = "vix"
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    vix.rename_axis("date").to_frame().to_csv(_CACHE)
    return vix


def vix_iv_rank(start: str, end: str, window: int = 252, warmup_days: int = 420) -> pd.Series:
    """Trailing-`window` VIX IV-Rank (0-100) per date over [start, end], warmed up `warmup_days` prior.

    Causal w.r.t. the same-day VIX close, matching how the engine's existing absolute VIX filter
    already gates entries (it reads that day's `vix` column). min_periods is set to a half-window so
    a slightly-short warmup still yields a usable (if wider-windowed) rank rather than NaN.
    """
    warm_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_days)).strftime("%Y-%m-%d")
    vix = _load_vix(warm_start, end)
    lo = vix.rolling(window, min_periods=window // 2).min()
    hi = vix.rolling(window, min_periods=window // 2).max()
    rank = (vix - lo) / (hi - lo).replace(0, pd.NA) * 100.0
    return rank.loc[pd.Timestamp(start):pd.Timestamp(end)]


def vix_rank_gate(start: str, end: str, max_rank: float = 30.0,
                  window: int = 252, warmup_days: int = 420):
    """Return ``callable(date) -> bool`` allowing a new entry only when VIX IV-Rank <= ``max_rank``.

    A date with no computable rank (missing/NaN, e.g. a non-trading day or a too-short warmup that
    even min_periods can't cover) is allowed through, so the gate only ever *removes* expensive-vol
    days and never silently blocks the whole backtest on a data gap.
    """
    rank = vix_iv_rank(start, end, window=window, warmup_days=warmup_days)
    rank_by_day = {d.normalize(): float(v) for d, v in rank.items() if pd.notna(v)}

    def _gate(date) -> bool:
        r = rank_by_day.get(pd.Timestamp(date).normalize())
        return True if r is None else r <= max_rank

    return _gate
