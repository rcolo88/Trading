"""Download SPY EOD options data from Massive.com (formerly Polygon.io) free Basic tier.

The free Basic tier provides:
  - 2 years of historical data
  - End-of-day data
  - 100% market coverage
  - 5 API calls/minute (= 1 call per 12 seconds)

Strategy (avoids the snapshot endpoint which requires paid tier):
  1. GET /v3/reference/options/contracts  → list of SPY contract tickers
  2. GET /v2/aggs/ticker/{O:...}/range/1/day/{from}/{to}  → daily OHLCV per contract
  3. Derive IV from the daily close mid via Black-Scholes
  4. Compute full greeks (delta, gamma, theta, vega) from IV
  5. Estimate bid/ask via a modeled spread on the mid

Output: data/processed/SPY_real_options_<start>_<end>.csv
  — identical schema to optionsdx_loader.py so mode:real loads it with no extra plumbing.

Resume: progress is checkpointed to data/raw/massive/progress.json after every contract so
the script can be stopped and restarted without losing work.

CLI:
    opt_venv/bin/python -m src.data_fetchers.massive_loader --api-key YOUR_KEY
    opt_venv/bin/python -m src.data_fetchers.massive_loader --api-key YOUR_KEY --start 2024-01-01 --end 2026-06-15

Get your free API key at: https://massive.com  (sign up → dashboard → API keys)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://api.polygon.io"
RATE_LIMIT_DELAY = 12.1      # seconds between calls (5/min free tier = 12s minimum)
DEFAULT_START = "2024-01-01"
DEFAULT_END   = date.today().strftime("%Y-%m-%d")

# Strike filter is relative to SPY's actual close near each contract's own relevant
# trading window (anchor = expiration - ANCHOR_OFFSET_DAYS), not a static historical
# range — a contract deep ITM/OTM on its own date is unusable (no liquidity, no
# extrinsic value to back-solve IV from) even if its strike sits inside the full
# 2-year SPY range.
ANCHOR_OFFSET_DAYS = 45      # ~midpoint of the near/far DTE window this strategy trades
MONEYNESS_BAND  = 0.15       # keep strikes within ±15% of SPY's anchor-date close
MAX_DTE         = 90         # skip contracts with more than 90 DTE at listing

RISK_FREE_RATE   = 0.04
DIVIDEND_YIELD   = 0.015
SPREAD_FRAC      = 0.03      # half-spread = max(SPREAD_FRAC * mid, MIN_SPREAD) / 2
MIN_SPREAD       = 0.05

OUT_COLS = [
    "quote_date", "underlying_symbol", "underlying_price", "vix",
    "expiration", "dte", "strike", "option_type",
    "bid", "ask", "last", "volume", "open_interest",
    "iv", "delta", "abs_delta", "gamma", "theta", "vega",
]


# ---------------------------------------------------------------------------
# BS helpers (wraps src/utils/black_scholes.py)
# ---------------------------------------------------------------------------
def _bs_greeks(S: float, K: float, T: float, r: float, q: float,
               iv: float, option_type: str) -> dict:
    """Return all greeks + mid price for one contract."""
    from src.utils.black_scholes import (
        black_scholes_price, delta, gamma, theta, vega
    )
    mid  = black_scholes_price(S, K, T, r, iv, option_type)
    d    = delta(S, K, T, r, iv, option_type, q)
    g    = gamma(S, K, T, r, iv, q)
    th   = theta(S, K, T, r, iv, option_type, q) / 365.0  # per-day
    v    = vega(S, K, T, r, iv, q)
    return {"mid": mid, "delta": d, "gamma": g, "theta": th, "vega": v}


def _bs_iv(mid: float, S: float, K: float, T: float, r: float, q: float,
           option_type: str) -> Optional[float]:
    """Back-solve implied volatility from mid price. Returns None if fails."""
    from src.utils.black_scholes import implied_volatility
    if mid <= 0 or T <= 0:
        return None
    try:
        iv = implied_volatility(mid, S, K, T, r, option_type, q)
        if iv is None or iv <= 0.01 or iv > 5.0:
            return None
        return float(iv)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
class NotAuthorizedError(Exception):
    """Raised when the API key's plan doesn't cover the requested date range."""


def _get(session: requests.Session, url: str, params: dict, api_key: str,
         retries: int = 3) -> Optional[dict]:
    """Rate-limited GET with retries."""
    params = dict(params, apiKey=api_key)
    for attempt in range(retries):
        try:
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                print("    [rate-limit] sleeping 60s …")
                time.sleep(60)
                continue
            if resp.status_code == 404:
                return None
            if resp.status_code in (401, 403):
                # 401 = bad/missing API key; 403 = key valid but plan doesn't cover the request.
                # Both are FATAL and must never be retried/swallowed: the generic RequestException
                # path below returns None, which the caller treats as "no data" and marks the
                # contract done — so an auth failure would silently mark the whole universe done.
                body = resp.json() if resp.content else {}
                msg = body.get("message") or resp.text[:200]
                raise NotAuthorizedError(f"HTTP {resp.status_code}: {msg}")
            resp.raise_for_status()
            return resp.json()
        except NotAuthorizedError:
            raise
        except requests.RequestException as e:
            print(f"    [error] {e}  attempt {attempt+1}/{retries}")
            time.sleep(15 * (attempt + 1))
    return None


def _paginate_contracts(session: requests.Session, api_key: str,
                        start: str, end: str,
                        expired: str = "true") -> list[dict]:
    """Fetch SPY option contracts with pagination.

    expired="true"  → only expired contracts (default; safe for historical pulls)
    expired="false" → only currently-active contracts (needed to fill the gap where
                      far-leg expirations fall past the original pull's end date)
    """
    contracts = []
    url = f"{BASE_URL}/v3/reference/options/contracts"
    params = {
        "underlying_ticker": "SPY",
        "expired": expired,
        "expiration_date.gte": start,
        "expiration_date.lte": end,
        "limit": 1000,
    }
    page = 0
    while True:
        page += 1
        print(f"  Fetching contract page {page} …")
        data = _get(session, url, params, api_key)
        time.sleep(RATE_LIMIT_DELAY)
        if data is None or "results" not in data:
            break
        contracts.extend(data["results"])
        nxt = data.get("next_url")
        if not nxt:
            break
        # next_url already contains cursor — extract and reuse
        url = nxt.split("?")[0]
        import urllib.parse
        params = dict(urllib.parse.parse_qs(urllib.parse.urlsplit(nxt).query),
                      apiKey=api_key)
        params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        url = f"{BASE_URL}/v3/reference/options/contracts"
        params["cursor"] = urllib.parse.parse_qs(urllib.parse.urlsplit(nxt).query).get(
            "cursor", [None])[0]
    return contracts


def _fetch_aggs(session: requests.Session, api_key: str,
                ticker: str, start: str, end: str) -> list[dict]:
    """Fetch daily OHLCV for one options ticker. Returns list of bar dicts."""
    url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}"
    params = {"adjusted": "false", "sort": "asc", "limit": 5000}
    data = _get(session, url, params, api_key)
    if data is None or data.get("resultsCount", 0) == 0:
        return []
    return data.get("results", [])


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------
def download_massive(
    api_key: str,
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    symbol: str = "SPY",
    out_dir: str = "data/processed",
    raw_dir: str = "data/raw/massive",
    option_type: str = "both",
    moneyness_band: float = MONEYNESS_BAND,
    expired: str = "true",
) -> str:
    """Download and convert Massive EOD options data into the project's long-format CSV."""
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    progress_file = Path(raw_dir) / "progress.json"

    # ---- Load checkpoint ------------------------------------------------
    progress: dict = {}
    if progress_file.exists():
        progress = json.loads(progress_file.read_text())
        print(f"Resuming from checkpoint: {len(progress['done'])} contracts already done.")

    done_set: set = set(progress.get("done", []))
    rows_cache: list = progress.get("rows", [])

    # ---- Fetch underlying (SPY) + VIX prices ----------------------------
    print("Fetching SPY + VIX prices from yfinance …")
    import yfinance as yf
    # Extra lookback so the anchor-spot filter below can estimate SPY's price near
    # each contract's relevant trading window, even for contracts expiring shortly
    # after `start`.
    fetch_start = (pd.Timestamp(start) - pd.Timedelta(days=ANCHOR_OFFSET_DAYS + 5)).strftime("%Y-%m-%d")
    spy_hist = yf.Ticker("SPY").history(start=fetch_start, end=end, interval="1d")
    spy_hist.index = pd.to_datetime(spy_hist.index).tz_localize(None).normalize()
    spy_close = spy_hist["Close"].sort_index()

    vix_hist = yf.Ticker("^VIX").history(start=fetch_start, end=end, interval="1d")
    vix_hist.index = pd.to_datetime(vix_hist.index).tz_localize(None).normalize()
    vix_close = vix_hist["Close"]

    # ---- Fetch contract list --------------------------------------------
    # Cache key includes expired flag so an active-contract supplemental run
    # doesn't collide with the original expired-contract cache file.
    contracts_file = Path(raw_dir) / f"contracts_{start}_{end}_exp{expired}.json"
    # Also accept the original filename (no suffix) as a legacy cache hit so
    # existing checkpoints don't re-fetch thousands of contracts.
    legacy_file = Path(raw_dir) / f"contracts_{start}_{end}.json"
    if contracts_file.exists():
        print("Loading cached contract list …")
        all_contracts = json.loads(contracts_file.read_text())
    elif expired == "true" and legacy_file.exists():
        print("Loading cached contract list (legacy filename) …")
        all_contracts = json.loads(legacy_file.read_text())
    else:
        print(f"Fetching SPY contract list from Massive (expired={expired}) …")
        with requests.Session() as sess:
            all_contracts = _paginate_contracts(sess, api_key, start, end, expired=expired)
        contracts_file.write_text(json.dumps(all_contracts))
        print(f"  Found {len(all_contracts):,} total SPY contracts")

    # ---- Filter to near-ATM (at each contract's own anchor date), bounded DTE -----
    def _anchor_spot(exp_date: pd.Timestamp) -> Optional[float]:
        anchor = exp_date - pd.Timedelta(days=ANCHOR_OFFSET_DAYS)
        pos = spy_close.index.get_indexer([anchor], method="ffill")[0]
        if pos == -1:
            pos = 0   # anchor before our fetched history — fall back to earliest close
        return float(spy_close.iloc[pos])

    # Scope filters (each narrows the API-call budget). option_type='call' collects only calls —
    # cutting runtime ~half — for a call-only study like the call calendar; moneyness_band tightens
    # the ATM strike window the strategy actually trades. Both default to the full universe so other
    # strategies (puts, wider strikes) are unaffected unless explicitly narrowed.
    type_filter = {"call", "put"} if option_type == "both" else {option_type}
    filtered = []
    for c in all_contracts:
        ct = c.get("contract_type", "").lower()
        if ct not in type_filter:
            continue
        k = float(c.get("strike_price", 0))
        exp = pd.Timestamp(c.get("expiration_date", ""))
        spot = _anchor_spot(exp)
        if not (spot * (1 - moneyness_band) <= k <= spot * (1 + moneyness_band)):
            continue
        # Keep a contract if it is tradeable on SOME day in [start, end] with DTE in [0, MAX_DTE].
        # That holds iff its expiration falls in [start, end + MAX_DTE]:
        #   exp < start          -> already expired before the window begins (skip)
        #   exp > end + MAX_DTE  -> never within MAX_DTE during the window (skip)
        # The previous proxy measured DTE from the SINGLE window-start date, so it silently dropped
        # every expiration beyond start + (MAX_DTE+30) days — collecting only the first ~4 months of a
        # multi-year window (e.g. 2024-06..2026-06 yielded data only through 2024-10). This per-window
        # test keeps every expiration the strategy could actually trade across the whole range.
        if not (pd.Timestamp(start) <= exp <= pd.Timestamp(end) + pd.Timedelta(days=MAX_DTE)):
            continue
        filtered.append(c)

    print(f"  After filter: {len(filtered):,} contracts "
          f"({option_type}, ±{moneyness_band:.0%} ATM, expiry in [{start}, {end}+{MAX_DTE}d])")

    remaining = [c for c in filtered if c["ticker"] not in done_set]
    total = len(filtered)
    done_n = total - len(remaining)
    print(f"  {done_n} done, {len(remaining)} remaining\n")

    # ---- Preflight: confirm the plan actually covers `start` -------------
    # The free tier's "2 years historical data" is a ROLLING window from today, not a
    # fixed calendar date — requesting dates older than ~2 years back gets a silent
    # NOT_AUTHORIZED on every single contract. Check ONE contract before burning the
    # rate-limit budget on the rest.
    if remaining:
        probe = remaining[0]
        with requests.Session() as sess:
            try:
                _fetch_aggs(sess, api_key, probe["ticker"], start, end)
            except NotAuthorizedError as e:
                if "HTTP 401" in str(e):
                    # Bad/missing key — NOT a date-coverage problem. The most common cause is
                    # passing the literal 'YOUR_KEY' placeholder instead of a real key.
                    print(f"\n✗ ABORTED — API key rejected (401): {e}")
                    print("  Pass your REAL Massive/Polygon key to --api-key (not the literal "
                          "'YOUR_KEY' placeholder).")
                    print("  Get it at massive.com → dashboard → API keys. Checkpoint left untouched.")
                    return ""
                from datetime import timedelta
                est_earliest = (date.today() - timedelta(days=729)).strftime("%Y-%m-%d")
                print(f"\n✗ ABORTED — plan does not cover start={start}: {e}")
                print(f"  The free tier's 2-year history is a rolling window from today, "
                      f"not a fixed date. Estimated earliest authorized date: ~{est_earliest}.")
                print(f"  Delete the stale checkpoint and retry with a later --start:")
                print(f"    rm {progress_file} {contracts_file}")
                print(f"    opt_venv/bin/python -m src.data_fetchers.massive_loader "
                      f"--api-key YOUR_KEY --start {est_earliest} --end {end}")
                return ""
            time.sleep(RATE_LIMIT_DELAY)

    # ---- Download daily aggs per contract --------------------------------
    with requests.Session() as sess:
        for i, contract in enumerate(remaining):
            ticker   = contract["ticker"]           # e.g. O:SPY240119C00500000
            strike   = float(contract["strike_price"])
            opt_type = contract["contract_type"].lower()
            exp_date = pd.Timestamp(contract["expiration_date"]).normalize()

            pct = 100 * (done_n + i + 1) / total
            print(f"  [{pct:5.1f}%] {ticker} … ", end="", flush=True)

            try:
                bars = _fetch_aggs(sess, api_key, ticker, start, end)
            except NotAuthorizedError as e:
                print(f"\n✗ ABORTED — {ticker}: {e}")
                _save_progress(progress_file, done_set, rows_cache)
                _flush_partial(rows_cache, out_dir, symbol, start, end)
                print(f"  Checkpoint saved ({len(rows_cache):,} rows). Adjust --start and rerun.")
                return ""
            time.sleep(RATE_LIMIT_DELAY)

            if not bars:
                print("no data")
                done_set.add(ticker)
                continue

            n_rows = 0
            for bar in bars:
                ts_ms   = bar.get("t", 0)
                q_date  = pd.Timestamp(ts_ms, unit="ms").normalize()
                mid     = float(bar.get("c", 0))     # close = EOD mid
                volume  = float(bar.get("v", 0))

                if mid <= 0:
                    continue

                # SPY spot + VIX for this day
                spot = spy_close.get(q_date)
                vix  = vix_close.get(q_date)
                if spot is None or pd.isna(spot):
                    # try next business day's spot
                    continue
                spot = float(spot)
                vix_val = float(vix) if vix is not None and not pd.isna(vix) else np.nan

                dte_days = (exp_date - q_date).days
                if dte_days < 0:
                    continue
                T = max(dte_days, 0) / 365.0

                # Back-solve IV from EOD mid price
                iv = _bs_iv(mid, spot, strike, T, RISK_FREE_RATE, DIVIDEND_YIELD, opt_type)
                if iv is None:
                    continue

                # Greeks
                try:
                    g = _bs_greeks(spot, strike, T, RISK_FREE_RATE, DIVIDEND_YIELD, iv, opt_type)
                except Exception:
                    continue

                # Bid/ask from spread model (same as reprice_from_iv)
                half = max(SPREAD_FRAC * mid, MIN_SPREAD) / 2.0
                bid  = max(mid - half, 0.01)
                ask  = mid + half

                rows_cache.append({
                    "quote_date":        q_date.strftime("%Y-%m-%d"),
                    "underlying_symbol": symbol,
                    "underlying_price":  round(spot, 4),
                    "vix":               round(vix_val, 4) if not np.isnan(vix_val) else "",
                    "expiration":        exp_date.strftime("%Y-%m-%d"),
                    "dte":               int(dte_days),
                    "strike":            strike,
                    "option_type":       opt_type,
                    "bid":               round(bid, 4),
                    "ask":               round(ask, 4),
                    "last":              round(mid, 4),
                    "volume":            int(volume),
                    "open_interest":     "",
                    "iv":                round(iv, 6),
                    "delta":             round(g["delta"], 6),
                    "abs_delta":         round(abs(g["delta"]), 6),
                    "gamma":             round(g["gamma"], 6),
                    "theta":             round(g["theta"], 6),
                    "vega":              round(g["vega"], 6),
                })
                n_rows += 1

            print(f"{n_rows} rows")
            done_set.add(ticker)

            # Checkpoint every 50 contracts
            if (i + 1) % 50 == 0:
                _save_progress(progress_file, done_set, rows_cache)
                # Flush rows to disk as partial CSV too
                _flush_partial(rows_cache, out_dir, symbol, start, end)
                print(f"    [checkpoint] {len(done_set)}/{total} done, {len(rows_cache):,} rows saved")

    # ---- Write final CSV ------------------------------------------------
    _save_progress(progress_file, done_set, rows_cache)
    out_path = _flush_partial(rows_cache, out_dir, symbol, start, end, final=True)
    print(f"\n✓ Done. {len(rows_cache):,} rows → {out_path}")
    print(f"  Set config.yaml: real_data.start_date={start}, end_date={end}, mode: real, price_from_iv: false")
    return out_path


def merge_into(base_csv: str, supplement_csv: str, out_csv: str | None = None) -> str:
    """Merge a supplemental Massive pull into the base dataset.

    Deduplicates on (quote_date, expiration, strike, option_type) keeping the
    base row when there is a conflict (supplement only adds new contracts).
    Writes back to base_csv (in-place) unless out_csv is given.
    """
    base = pd.read_csv(base_csv)
    supp = pd.read_csv(supplement_csv)
    combined = pd.concat([base, supp], ignore_index=True)
    combined = combined.drop_duplicates(
        subset=["quote_date", "expiration", "strike", "option_type"], keep="first"
    ).sort_values(["quote_date", "expiration", "strike", "option_type"]).reset_index(drop=True)
    dest = out_csv or base_csv
    combined.to_csv(dest, index=False)
    print(f"Merged: {len(base):,} base + {len(supp):,} supplement → {len(combined):,} rows")
    print(f"  Trading days: {combined['quote_date'].nunique()}")
    print(f"  Written to: {dest}")
    return dest


def _save_progress(progress_file: Path, done_set: set, rows: list) -> None:
    progress_file.write_text(json.dumps({"done": list(done_set), "rows": rows}))


def _flush_partial(rows: list, out_dir: str, symbol: str,
                   start: str, end: str, final: bool = False) -> str:
    if not rows:
        return ""
    df = pd.DataFrame(rows, columns=OUT_COLS)
    df = df.sort_values(["quote_date", "expiration", "strike", "option_type"]).drop_duplicates()
    out_name = f"{symbol}_real_options_{start}_{end}.csv"
    out_path = str(Path(out_dir) / out_name)
    df.to_csv(out_path, index=False)
    if final:
        print(f"  Trading days : {df['quote_date'].nunique()}")
        print(f"  Expirations  : {df['expiration'].nunique()}")
        print(f"  Calls / Puts : {(df['option_type']=='call').sum():,} / {(df['option_type']=='put').sum():,}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    p = argparse.ArgumentParser(
        description="Download Massive.com (Polygon.io) free-tier EOD SPY options data."
    )
    p.add_argument("--api-key", required=True,
                   help="Your Massive/Polygon.io API key (get free at massive.com)")
    p.add_argument("--start", default=DEFAULT_START, help="Start date YYYY-MM-DD")
    p.add_argument("--end",   default=DEFAULT_END,   help="End date YYYY-MM-DD")
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--out-dir", default="data/processed")
    p.add_argument("--raw-dir", default="data/raw/massive")
    p.add_argument("--option-type", default="both", choices=["call", "put", "both"],
                   help="Collect only calls or puts to cut runtime (default: both). "
                        "Use 'call' for a call-only study like the call calendar.")
    p.add_argument("--moneyness-band", type=float, default=MONEYNESS_BAND,
                   help=f"Keep strikes within ±band of anchor-date spot (default {MONEYNESS_BAND}). "
                        "Tighten (e.g. 0.06) for ATM strategies to cut the contract count.")
    p.add_argument("--include-active", action="store_true",
                   help="Fetch currently-active (not-yet-expired) contracts instead of expired ones. "
                        "Use with a narrow expiration window (--start/--end = the expiration range "
                        "you need, NOT the quote-date range) to fill the gap where far-leg expirations "
                        "fall past the original pull's end date. Example: "
                        "--include-active --start 2026-06-17 --end 2026-09-19")
    p.add_argument("--merge-into",
                   help="After downloading, merge the result into this existing CSV (in-place). "
                        "Use to patch the gap: pass the base dataset path here and the supplemental "
                        "rows are deduped and appended.")
    args = p.parse_args()
    out_path = download_massive(
        api_key=args.api_key,
        start=args.start,
        end=args.end,
        symbol=args.symbol,
        out_dir=args.out_dir,
        raw_dir=args.raw_dir,
        option_type=args.option_type,
        moneyness_band=args.moneyness_band,
        expired="false" if args.include_active else "true",
    )
    if args.merge_into and out_path:
        merge_into(args.merge_into, out_path)


if __name__ == "__main__":
    main()
