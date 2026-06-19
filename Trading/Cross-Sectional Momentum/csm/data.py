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


# The cache always stores data from this far back so the signal has warmup headroom.
# Changing start_date in config.yaml restricts the *analysis* window, not the download.
_CACHE_HISTORY_START = "2010-01-01"


def load_price_panel(
    tickers:   list[str],
    start:     str,
    end:       str,
    cache_dir: Path,
) -> pd.DataFrame:
    """Return adj-close price panel (DatetimeIndex × tickers) sliced to [start, end].

    The on-disk cache always covers _CACHE_HISTORY_START → end so the momentum
    signal (252-day window) has enough history regardless of start_date in config.
    Changing start_date in config.yaml does NOT require re-running fetch.

    Cache is refreshed when any ticker's last real close lags end by > 5 trading days.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "prices.parquet"

    yfmt_map = {t: _yfmt(t) for t in tickers}
    inv_map  = {v: k for k, v in yfmt_map.items()}
    needed_yf = sorted(set(yfmt_map.values()) | {"SPY"})
    target_end = pd.Timestamp(end)

    # ── Decide whether the cache is usable ───────────────────────────────────
    cached = pd.DataFrame()
    if cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached.columns = [inv_map.get(c, c) for c in cached.columns]

        missing = [t for t in needed_yf if inv_map.get(t, t) not in cached.columns]
        if not missing:
            last_valid = cached.apply(lambda c: c.dropna().index.max())
            stale = last_valid[last_valid < (target_end - pd.tseries.offsets.BDay(5))]
            if stale.empty:
                present = [t for t in tickers + ["SPY"] if t in cached.columns]
                panel   = cached[present].loc[start:end]
                print(f"Loaded price cache: {len(present)} tickers × {len(panel)} days  "
                      f"(history from {cached.index.min().date()}, "
                      f"fresh through {cached.index.max().date()})")
                return panel
            print(f"Cache STALE: {len(stale)} tickers last valid before "
                  f"{(target_end - pd.tseries.offsets.BDay(5)).date()} "
                  f"(oldest: {stale.min().date()}).  Re-downloading all …")
        else:
            print(f"Cache missing {len(missing)} tickers; re-downloading all …")

    # ── Full download (new or stale): always from _CACHE_HISTORY_START ───────
    raw = yf.download(
        needed_yf, start=_CACHE_HISTORY_START, end=end,
        auto_adjust=True, progress=True, threads=True, timeout=60,
    )
    if isinstance(raw.columns, pd.MultiIndex):
        new_prices = raw["Close"]
    else:
        new_prices = raw[["Close"]].rename(columns={"Close": needed_yf[0]})

    new_prices.index = pd.to_datetime(new_prices.index)
    new_prices = new_prices.rename(columns=inv_map)

    # New data takes priority over anything previously cached
    panel = new_prices.combine_first(cached) if not cached.empty else new_prices
    panel = panel.dropna(axis=1, how="all")

    panel.rename(columns=yfmt_map).to_parquet(cache_path)
    print(f"Price cache updated: {panel.shape[1]} tickers × {panel.shape[0]} days  "
          f"(history from {panel.index.min().date()}, through {panel.index.max().date()})")

    return panel.loc[start:end]


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
