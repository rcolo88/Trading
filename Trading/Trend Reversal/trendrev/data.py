"""Data layer: download OHLCV from yfinance with a local CSV cache (no parquet dependency).

All data is returned as a tidy DataFrame indexed by a tz-naive ``DatetimeIndex`` named ``date``
with lowercase columns ``open, high, low, close, volume``. Prices are split/dividend adjusted
(``auto_adjust=True``) so that close-to-close returns are economically meaningful for backtests.
"""
from __future__ import annotations

import os
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_COLUMNS = ["open", "high", "low", "close", "volume"]


def _cache_path(ticker: str, interval: str) -> str:
    return os.path.join(DATA_DIR, f"{ticker.upper()}_{interval}.csv")


def _meta_path(ticker: str, interval: str) -> str:
    """Sidecar recording the earliest ``start`` ever requested, so we can tell a genuine IPO date
    (don't refetch) from a cache that was truncated by a short ``refresh`` (do refetch)."""
    return os.path.join(DATA_DIR, f"{ticker.upper()}_{interval}.meta")


def _read_earliest_request(ticker: str, interval: str) -> pd.Timestamp | None:
    p = _meta_path(ticker, interval)
    if os.path.exists(p):
        try:
            with open(p) as fh:
                return pd.Timestamp(fh.read().strip())
        except Exception:
            return None
    return None


def _write_earliest_request(ticker: str, interval: str, start: str) -> None:
    prev = _read_earliest_request(ticker, interval)
    earliest = min(pd.Timestamp(start), prev) if prev is not None else pd.Timestamp(start)
    with open(_meta_path(ticker, interval), "w") as fh:
        fh.write(earliest.strftime("%Y-%m-%d"))


def get_ohlcv(
    ticker: str,
    start: str = "2005-01-01",
    end: str | None = None,
    interval: str = "1d",
    refresh: bool = False,
) -> pd.DataFrame:
    """Return an adjusted OHLCV frame for ``ticker``, caching to ``data/<TICKER>_<interval>.csv``.

    On cache hit the local file is reused unless ``refresh=True``. A small network failure with a
    warm cache degrades gracefully to the cached copy.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    path = _cache_path(ticker, interval)

    cached = None
    if os.path.exists(path):
        cached = pd.read_csv(path, index_col=0, parse_dates=True)
        cached.index.name = "date"

    if cached is not None and not refresh:
        # Reuse the cache only if it actually covers the requested window. If a prior short
        # ``refresh`` truncated it (cache starts well after ``start`` we never asked to drop),
        # fall through and re-download the full range instead of returning a thin slice.
        earliest_req = _read_earliest_request(ticker, interval)
        covers_back = earliest_req is not None and earliest_req <= pd.Timestamp(start)
        if covers_back or cached.index.min() <= pd.Timestamp(start) + pd.Timedelta(days=5):
            return _slice(cached, start, end)

    # Download from the widest start we've ever needed so a refresh never shrinks history.
    prev_req = _read_earliest_request(ticker, interval)
    fetch_start = min(pd.Timestamp(start), prev_req) if prev_req is not None else pd.Timestamp(start)
    if cached is not None:
        fetch_start = min(fetch_start, cached.index.min())

    try:
        raw = yf.Ticker(ticker).history(
            start=fetch_start.strftime("%Y-%m-%d"), end=end, interval=interval, auto_adjust=True
        )
    except Exception as exc:  # pragma: no cover - network dependent
        if cached is not None:
            return _slice(cached, start, end)
        raise RuntimeError(f"Failed to download {ticker} and no cache exists: {exc}") from exc

    if raw.empty:
        if cached is not None:
            return _slice(cached, start, end)
        raise RuntimeError(f"yfinance returned no data for {ticker} ({interval}).")

    df = raw.rename(columns=str.lower)[_COLUMNS].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "date"
    # Merge with any existing cache so refreshing a short window never discards older history.
    if cached is not None:
        df = pd.concat([cached, df])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.to_csv(path)
    _write_earliest_request(ticker, interval, start)
    return _slice(df, start, end)


def get_many(
    tickers: Iterable[str], start: str = "2005-01-01", end: str | None = None, interval: str = "1d"
) -> dict[str, pd.DataFrame]:
    """Download several tickers, returning ``{ticker: ohlcv_frame}``."""
    return {t: get_ohlcv(t, start=start, end=end, interval=interval) for t in tickers}


# Trading bars per year for each supported resample rule (used to annualise metrics).
PERIODS_PER_YEAR = {"1D": 252, "2D": 126, "3D": 84, "5D": 50, "1W": 52}

_OHLC_AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample_ohlcv(df: pd.DataFrame, rule: str = "1D") -> pd.DataFrame:
    """Resample a daily OHLCV frame to a coarser bar.

    ``'1D'`` returns the frame unchanged. ``'ND'`` (e.g. ``'2D'``, ``'3D'``) groups every *N* trading
    rows (not calendar days, so no empty weekend bars), aligned so the **last** bar stays current.
    ``'1W'`` is a calendar week ending Friday. open=first, high=max, low=min, close=last, vol=sum.
    """
    if rule in ("1D", "D", None):
        return df
    if rule.endswith("W"):
        out = df.resample("W-FRI").agg(_OHLC_AGG).dropna(subset=["close"])
        out.index.name = "date"
        return out
    n = int(rule[:-1])
    # Pad at the front so the final group is full and ends on the most recent bar.
    grp = (np.arange(len(df)) + (n - len(df) % n) % n) // n
    out = df.groupby(grp).agg(_OHLC_AGG)
    out.index = pd.DatetimeIndex(df.index.to_series().groupby(grp).last().values, name="date")
    return out


def _slice(df: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    if start is not None:
        df = df[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end)]
    return df
