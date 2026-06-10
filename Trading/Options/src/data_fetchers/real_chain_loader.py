"""Fetch REAL SPY option chains from DoltHub into the backtester's canonical schema.

This is the honest replacement for the flat-IV synthetic data: DoltHub's
``post-no-preference/options`` database carries real end-of-day chains with a genuine
**volatility skew** (IV varies across strikes) and **term structure** (IV varies across
expirations) — exactly what the Black-Scholes synthetic generator cannot produce, and the
reason the calendar optimizer was reporting an 8+ Sharpe with a non-binding stop.

Source (no auth needed for public repos), DoltHub SQL-over-HTTP API:
    GET https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master?q=<SQL>
``option_chain`` columns: date, act_symbol, expiration, strike, call_put, bid, ask, vol(IV),
delta, gamma, theta, vega, rho.  (No underlying price / VIX / DTE — we add those.)

Each SPY date holds ~200 contracts within 90 DTE, well under the API row cap, so we pull one
day per request, merge the SPY close + VIX from yfinance, compute dte/abs_delta, and write a
single drop-in CSV that ``load_sample_spy_options_data`` reads:

    data/processed/SPY_real_options_<start>_<end>.csv

Usage:
    opt_venv/bin/python -m src.data_fetchers.real_chain_loader --start 2025-10-01 --end 2026-06-08
    opt_venv/bin/python -m src.data_fetchers.real_chain_loader --start 2026-05-01 --end 2026-06-08 --max-dte 90
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd

# Allow both ``python -m src.data_fetchers.real_chain_loader`` and direct execution.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_fetchers.synthetic_generator import real_data_filename  # noqa: E402

DOLT_BASE = "https://www.dolthub.com/api/v1alpha1/post-no-preference/options/master"
PROCESSED_DIR = _PROJECT_ROOT / "data" / "processed"

# Canonical column order shared with the synthetic generator's output (so either dataset is a
# drop-in for the backtester's loader / _format_for_optopsy validation).
CANONICAL_COLS = [
    "quote_date", "underlying_symbol", "underlying_price", "vix", "expiration", "dte",
    "strike", "option_type", "bid", "ask", "last", "volume", "open_interest",
    "iv", "delta", "abs_delta", "gamma", "theta", "vega",
]


def _dolt_query(sql: str, max_retries: int = 4, timeout: int = 40) -> List[dict]:
    """Run one read-only SQL query against the DoltHub API; return the rows (list of dicts)."""
    import requests

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(DOLT_BASE, params={"q": sql}, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            status = payload.get("query_execution_status")
            if status == "RowLimit":
                # We page one day at a time and never expect to hit this; surface it loudly so the
                # caller can shrink the span rather than silently truncating the chain.
                raise RuntimeError("DoltHub RowLimit hit — narrow the query span")
            if status != "Success":
                raise RuntimeError(f"DoltHub status={status}: {payload.get('query_execution_message')}")
            return payload.get("rows", [])
        except Exception as exc:  # network blip, 5xx, timeout — back off and retry
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"DoltHub query failed after {max_retries} attempts: {last_err}\nSQL: {sql}")


def _fetch_underlying(start: str, end: str, symbol: str = "SPY") -> pd.DataFrame:
    """SPY close + VIX by trading date (the price/regime context DoltHub's chain lacks).

    Mirrors the yfinance pattern in ``synthetic_generator.fetch_underlying_data`` so the
    underlying here is consistent with what the optimizer loads separately.
    """
    import yfinance as yf

    # yfinance's end is exclusive; pad a day so the requested end date is included.
    end_excl = (pd.to_datetime(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    spy = yf.Ticker(symbol).history(start=start, end=end_excl, interval="1d")
    if spy.empty:
        raise ValueError(f"No {symbol} price data from yfinance for {start}..{end}")
    spy.index = spy.index.tz_localize(None).normalize()
    out = spy["Close"].rename("underlying_price").to_frame()

    vix = yf.Ticker("^VIX").history(start=start, end=end_excl, interval="1d")
    if not vix.empty:
        vix.index = vix.index.tz_localize(None).normalize()
        out = out.join(vix["Close"].rename("vix"), how="left")
        out["vix"] = out["vix"].ffill()
    else:
        out["vix"] = np.nan

    return out


def _normalize(raw: pd.DataFrame, underlying: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Map DoltHub rows + underlying context to the canonical backtester schema."""
    df = raw.copy()
    for col in ["strike", "bid", "ask", "vol", "delta", "gamma", "theta", "vega"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["quote_date"] = pd.to_datetime(df["date"])
    df["expiration"] = pd.to_datetime(df["expiration"])
    df["dte"] = (df["expiration"] - df["quote_date"]).dt.days
    df["option_type"] = df["call_put"].str.lower()
    df["underlying_symbol"] = symbol
    df["iv"] = df["vol"]                       # DoltHub 'vol' is implied vol as a decimal
    df["abs_delta"] = df["delta"].abs()
    df["last"] = (df["bid"] + df["ask"]) / 2.0  # no traded 'last' in source — use the mid
    df["volume"] = np.nan                      # not provided by this dataset
    df["open_interest"] = np.nan

    # Merge SPY close + VIX by calendar date.
    u = underlying.copy()
    u.index = pd.to_datetime(u.index).normalize()
    key = df["quote_date"].dt.normalize()
    df["underlying_price"] = key.map(u["underlying_price"])
    df["vix"] = key.map(u["vix"])

    # Keep only sane, tradeable rows.
    df = df[
        df["underlying_price"].notna()
        & (df["dte"] > 0)
        & (df["ask"] > 0)
        & (df["bid"] >= 0)
        & (df["ask"] >= df["bid"])
    ]

    df = df[CANONICAL_COLS].sort_values(
        ["quote_date", "expiration", "strike", "option_type"]
    ).reset_index(drop=True)
    return df


def build_real_dataset(
    start: str,
    end: str,
    symbol: str = "SPY",
    max_dte: int = 90,
    sleep: float = 0.3,
    save: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """Pull real SPY chains [start, end] from DoltHub and write the canonical CSV."""
    if verbose:
        print(f"\n{'='*70}\nFETCHING REAL {symbol} OPTION CHAINS (DoltHub)\n{'='*70}")
        print(f"Range: {start} -> {end}  | max DTE: {max_dte}")

    underlying = _fetch_underlying(start, end, symbol)
    dates = [d.strftime("%Y-%m-%d") for d in underlying.index]
    if verbose:
        print(f"Trading days to fetch: {len(dates)}\n")

    frames: List[pd.DataFrame] = []
    empty_days = 0
    for i, ds in enumerate(dates):
        sql = (
            "SELECT date, expiration, strike, call_put, bid, ask, vol, delta, gamma, theta, vega "
            "FROM option_chain "
            f"WHERE act_symbol='{symbol}' AND date='{ds}' "
            f"AND expiration > date AND DATEDIFF(expiration, date) <= {max_dte}"
        )
        rows = _dolt_query(sql)
        if rows:
            frames.append(pd.DataFrame(rows))
        else:
            empty_days += 1
        if verbose and (i + 1) % 10 == 0:
            print(f"  {i+1:>4}/{len(dates)} days  ({(i+1)/len(dates)*100:4.0f}%)  "
                  f"rows so far: {sum(len(f) for f in frames):,}")
        time.sleep(sleep)

    if not frames:
        raise RuntimeError(
            "No chains returned for any date. DoltHub may not cover this range for "
            f"{symbol}, or the dates are non-trading days."
        )

    raw = pd.concat(frames, ignore_index=True)
    df = _normalize(raw, underlying, symbol)

    if verbose:
        print(f"\n{'='*70}\nDONE\n{'='*70}")
        print(f"Contracts: {len(df):,}  | days with data: {df['quote_date'].nunique()} "
              f"(empty: {empty_days})")
        print(f"Date range: {df['quote_date'].min().date()} -> {df['quote_date'].max().date()}")
        print(f"Expirations: {df['expiration'].nunique()}  | strikes: {df['strike'].nunique()}")

    if save:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out = PROCESSED_DIR / real_data_filename(
            {"real_data": {"symbol": symbol, "start_date": start, "end_date": end}}
        )
        df.to_csv(out, index=False)
        if verbose:
            print(f"Saved -> {out}")

    return df


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch real SPY option chains from DoltHub.")
    ap.add_argument("--start", required=True, help="start date YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="end date YYYY-MM-DD (inclusive)")
    ap.add_argument("--symbol", default="SPY")
    ap.add_argument("--max-dte", type=int, default=90)
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between API calls (be polite)")
    args = ap.parse_args()

    try:
        build_real_dataset(
            start=args.start, end=args.end, symbol=args.symbol,
            max_dte=args.max_dte, sleep=args.sleep,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\n✗ ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
