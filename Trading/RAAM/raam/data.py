"""OHLC price panel data layer: yfinance download + parquet cache.

RAAM needs Open/High/Low/Close (not just Close) for the ATR breakout system and
the Garman-Klass volatility estimator — unlike Cross-Sectional Momentum's
Close-only panel. With only 13 tickers (11 rankable ETFs + SHY + SPY) a full
re-download takes seconds, so unlike csm/data.py there is no tail-splice/re-basis
machinery here: "refresh" is just auto (serve the cache when fresh) or full
(redownload everything). The two data-integrity guards from csm/data.py — drop an
in-progress session row, drop a partial trailing row — are ported unchanged, since
both failure modes are generic to any yfinance panel, not specific to CSM's
larger-universe machinery.
"""
from __future__ import annotations

import warnings
from datetime import time as _dtime
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

FIELDS = ["Open", "High", "Low", "Close"]

# The cache always stores data from this far back — before any 7Twelve ETF's
# inception (earliest is IJH/IJR 2000-05-26) — so changing config start_date
# never requires re-running `fetch`, matching csm/data.py's decoupling.
_CACHE_HISTORY_START = "2000-01-01"


def market_close_passed() -> bool:
    """True once today's NYSE regular-session close (16:00 ET + buffer) has passed."""
    return pd.Timestamp.now(tz="America/New_York").time() >= _dtime(16, 5)


def _drop_intraday_row(panel: pd.DataFrame,
                       now: pd.Timestamp | None = None) -> pd.DataFrame:
    """Drop a trailing row dated today while today's session is still open.

    Ported from csm/data.py: Yahoo reports the live intraday price as today's
    "close" during market hours; an in-progress row must never be cached or scored.
    """
    if now is None:
        now = pd.Timestamp.now(tz="America/New_York")
    if (len(panel) and panel.index[-1].date() == now.date()
            and now.time() < _dtime(16, 5)):
        print(f"  Dropping in-progress session row {panel.index[-1].date()} — "
              f"intraday prices are not closes.")
        panel = panel.iloc[:-1]
    return panel


def _drop_partial_tail(panel: pd.DataFrame, min_frac: float = 0.5) -> pd.DataFrame:
    """Drop trailing rows whose ticker coverage collapses vs the recent norm.

    Ported from csm/data.py. Checked on the Close field as a proxy for the whole
    OHLC row — a partial Close download means a partial row across the board.
    """
    if panel.empty:
        return panel
    close = panel["Close"] if isinstance(panel.columns, pd.MultiIndex) else panel
    cov = close.notna().sum(axis=1)
    while len(panel) > 21:
        ref = float(cov.iloc[-22:-1].median())
        if ref > 0 and float(cov.iloc[-1]) < min_frac * ref:
            print(f"  Dropping partial trailing row {panel.index[-1].date()} "
                  f"({int(cov.iloc[-1])}/{int(ref)} tickers) — incomplete download.")
            panel = panel.iloc[:-1]
            cov   = cov.iloc[:-1]
        else:
            break
    return panel


def _download_ohlc(tickers: list[str], start, end) -> pd.DataFrame:
    """Bulk-download adjusted OHLC. Returns columns MultiIndex (field, ticker)."""
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True,
                      progress=False, threads=True, timeout=60)
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance returned no data — check network / tickers.")
    if isinstance(raw.columns, pd.MultiIndex):
        cols = {f: raw[f] for f in FIELDS}
    else:
        # Single-ticker fallback (not expected in normal use — universe is 13 tickers).
        cols = {f: raw[[f]].rename(columns={f: tickers[0]}) for f in FIELDS}
    panel = pd.concat(cols, axis=1)
    panel.index = pd.to_datetime(panel.index)
    return panel.sort_index()


def load_ohlc_panel(
    tickers:   list[str],
    start:     str,
    end:       str,
    cache_dir: Path,
    refresh:   str = "auto",
) -> pd.DataFrame:
    """Return an OHLC panel — columns MultiIndex (field, ticker) — sliced to [start, end].

    The on-disk cache always covers _CACHE_HISTORY_START -> end regardless of the
    `start` argument, so indicator warmup (ATR's 105-day band, the vol/correlation
    windows) always has headroom and config start_date changes are free.

    refresh = "auto" (serve the cache when it has all `tickers` and is fresh
    through `end` within 5 business days) | "full" (always redownload).
    """
    if start in (None, "", "auto"):
        start = _CACHE_HISTORY_START

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "ohlc.parquet"
    target_end = pd.Timestamp(end)

    cached = pd.DataFrame()
    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached = _drop_intraday_row(cached)
        cached = _drop_partial_tail(cached)

    if refresh == "auto" and not cached.empty and isinstance(cached.columns, pd.MultiIndex):
        have        = set(cached["Close"].columns)
        missing     = [t for t in tickers if t not in have]
        panel_last  = cached.index[-1]
        if not missing and panel_last >= target_end - pd.tseries.offsets.BDay(5):
            panel = cached.loc[start:end]
            n_tk  = len(cached["Close"].columns)
            print(f"Loaded OHLC cache: {n_tk} tickers x {len(panel)} days  "
                  f"(history from {cached.index.min().date()}, "
                  f"fresh through {panel_last.date()})")
            return panel
        print(f"Cache stale/incomplete (latest {panel_last.date()}"
              + (f", {len(missing)} tickers missing" if missing else "")
              + ") — full re-download …")

    print(f"Downloading OHLC for {len(tickers)} tickers "
          f"({_CACHE_HISTORY_START} -> {end}) …")
    panel = _download_ohlc(tickers, _CACHE_HISTORY_START, end)
    panel = _drop_intraday_row(panel)
    panel = _drop_partial_tail(panel)
    if panel.empty:
        raise RuntimeError("Price download returned no data — check network / tickers.")
    panel.to_parquet(cache_path)
    n_tk = len(panel["Close"].columns)
    print(f"OHLC cache updated: {n_tk} tickers x {len(panel)} days  "
          f"(history from {panel.index.min().date()}, through {panel.index.max().date()})")
    return panel.loc[start:end]


def close_panel(ohlc: pd.DataFrame) -> pd.DataFrame:
    """Extract the Close field as a plain (date x ticker) DataFrame."""
    return ohlc["Close"]
