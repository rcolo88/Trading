"""Price panel data layer: bulk yfinance download + parquet cache.

All price data is split/dividend-adjusted (auto_adjust=True).
The cache stores a single Close-price parquet keyed by the union of all
tickers requested; incremental re-downloads add new tickers but re-use
cached columns so re-runs are fast.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")


def _yfmt(ticker: str) -> str:
    """Normalise ticker to yfinance format (dots → dashes)."""
    return ticker.strip().replace(".", "-").upper()


def load_price_panel(
    tickers:   list[str],
    start:     str,
    end:       str,
    cache_dir: Path,
) -> pd.DataFrame:
    """Return adj-close price panel (DatetimeIndex × tickers).

    Caches to `cache_dir/prices.parquet`.  If the cache already has all
    requested tickers, it is returned immediately without a network call.
    New tickers trigger an incremental download; already-cached columns are
    not re-fetched.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "prices.parquet"

    yfmt_map = {t: _yfmt(t) for t in tickers}        # original → yf-format
    inv_map  = {v: k for k, v in yfmt_map.items()}   # yf-format → original

    # SPY is always needed (market benchmark and regime filter)
    needed_yf = sorted(set(yfmt_map.values()) | {"SPY"})

    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        # Map cached columns back to originals
        cached.columns = [inv_map.get(c, c) for c in cached.columns]
        missing = [t for t in needed_yf if inv_map.get(t, t) not in cached.columns]
        if not missing:
            present = [t for t in tickers + ["SPY"] if t in cached.columns]
            print(f"Loaded price cache: {len(present)} tickers × {len(cached)} days")
            return cached[present]
        print(f"Cache hit but {len(missing)} tickers missing; downloading incremental …")
        to_download = missing
    else:
        cached = pd.DataFrame()
        to_download = needed_yf

    raw = yf.download(
        to_download, start=start, end=end,
        auto_adjust=True, progress=True, threads=True, timeout=60,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        new_prices = raw["Close"]
    else:
        # Single-ticker download — yf returns flat DataFrame
        new_prices = raw[["Close"]].rename(columns={"Close": to_download[0]})

    new_prices.index = pd.to_datetime(new_prices.index)
    new_prices = new_prices.rename(columns=inv_map)   # yf-format → original

    if not cached.empty:
        panel = cached.combine_first(new_prices)
    else:
        panel = new_prices

    panel = panel.dropna(axis=1, how="all")
    # Persist with yf-format column names for portability
    panel.rename(columns=yfmt_map).to_parquet(cache_path)
    print(f"Price cache updated: {panel.shape[1]} tickers × {panel.shape[0]} days")
    return panel


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns, forward-fill at most 3 days of NaN (halts, etc.)."""
    return prices.ffill(limit=3).pct_change().replace([np.inf, -np.inf], np.nan)


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return np.log1p(daily_returns(prices))


def pit_filter(
    returns:    pd.DataFrame,
    pit_df:     pd.DataFrame,
    query_date: pd.Timestamp,
) -> pd.Series:
    """Restrict a cross-section of returns to PIT-valid tickers on query_date.

    Returns the returns Series for valid tickers on that date.
    """
    from csm.universe import get_members_on
    valid = get_members_on(pit_df, query_date)
    cols  = [c for c in returns.columns if c in valid or c == "SPY"]
    return returns.loc[query_date, cols] if query_date in returns.index else pd.Series(dtype=float)
