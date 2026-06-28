#!/usr/bin/env python3
"""Append today's SPY option chain to data/raw/chains/SPY_chain_YYYY-MM-DD.csv.

Run this daily after the close to build a REAL point-in-time option-chain history — the honest fix
for the synthetic-data limitation. After a few weeks you can backtest on real chains.

Two sources, in order of preference (auto-detected):
  1. SCHWAB API via schwab-py — real greeks/IV. Needs a one-time OAuth (see data_collection/README.md)
     and env vars SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_TOKEN_PATH.
  2. yfinance fallback — bid/ask/IV from Yahoo; greeks are filled from IV with the repo's Black-Scholes
     so delta-based strike selection still works. No account needed.

Output columns match the synthetic generator, so the file is a drop-in for the backtester's loader.

    opt_venv/bin/python data_collection/chain_logger.py            # auto source, max 70 DTE
    opt_venv/bin/python data_collection/chain_logger.py --max-dte 90 --source yfinance
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.black_scholes import calculate_all_greeks  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "chains"
SYMBOL = "SPY"
R, Q = 0.04, 0.015  # risk-free, SPY dividend yield (for filling greeks on the yfinance path)


def _current_vix() -> float | None:
    """Latest ^VIX close (the regime gate strategies filter on). None if unavailable."""
    try:
        import yfinance as yf
        hist = yf.Ticker("^VIX").history(period="5d")["Close"].dropna()
        return float(hist.iloc[-1]) if not hist.empty else None
    except Exception:
        return None


def from_yfinance(max_dte: int) -> pd.DataFrame:
    import yfinance as yf

    tk = yf.Ticker(SYMBOL)
    spot = float(tk.history(period="1d")["Close"].iloc[-1])
    today = pd.Timestamp.today().normalize()
    rows = []
    for exp in tk.options:
        exp_ts = pd.Timestamp(exp)
        dte = (exp_ts - today).days
        if dte <= 0 or dte > max_dte:
            continue
        chain = tk.option_chain(exp)
        for opt_type, df in (("call", chain.calls), ("put", chain.puts)):
            for _, o in df.iterrows():
                iv = float(o.get("impliedVolatility") or 0.0)
                g = calculate_all_greeks(spot, float(o["strike"]), dte / 365.0, R, iv, opt_type, Q) \
                    if iv > 0 else {"delta": None, "gamma": None, "theta": None, "vega": None}
                rows.append({
                    "underlying_price": spot, "expiration": exp_ts, "dte": dte,
                    "strike": float(o["strike"]), "option_type": opt_type,
                    "bid": float(o.get("bid") or 0.0), "ask": float(o.get("ask") or 0.0),
                    "last": float(o.get("lastPrice") or 0.0),
                    "volume": o.get("volume"), "open_interest": o.get("openInterest"),
                    "iv": iv, "delta": g["delta"], "gamma": g["gamma"],
                    "theta": (g["theta"] / 365.0) if g["theta"] is not None else None, "vega": g["vega"],
                })
    return pd.DataFrame(rows)


def from_schwab(max_dte: int) -> pd.DataFrame:
    from schwab.auth import client_from_token_file

    client = client_from_token_file(
        token_path=os.environ["SCHWAB_TOKEN_PATH"],
        api_key=os.environ["SCHWAB_APP_KEY"],
        app_secret=os.environ["SCHWAB_APP_SECRET"],
    )
    data = client.get_option_chain(symbol=SYMBOL).json()
    spot = float(data.get("underlyingPrice") or 0.0)
    rows = []
    for side, opt_type in (("callExpDateMap", "call"), ("putExpDateMap", "put")):
        for _exp, strikes in data.get(side, {}).items():
            for _strike, contracts in strikes.items():
                o = contracts[0]
                dte = int(o.get("daysToExpiration", -1))
                if dte <= 0 or dte > max_dte:
                    continue
                rows.append({
                    "underlying_price": spot,
                    "expiration": pd.Timestamp(o["expirationDate"]).normalize(), "dte": dte,
                    "strike": float(o["strikePrice"]), "option_type": opt_type,
                    "bid": float(o.get("bid") or 0.0), "ask": float(o.get("ask") or 0.0),
                    "last": float(o.get("last") or 0.0),
                    "volume": o.get("totalVolume"), "open_interest": o.get("openInterest"),
                    "iv": (float(o.get("volatility") or 0.0) / 100.0), "delta": o.get("delta"),
                    "gamma": o.get("gamma"), "theta": o.get("theta"), "vega": o.get("vega"),
                })
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["auto", "schwab", "yfinance"], default="auto")
    ap.add_argument("--max-dte", type=int, default=70)
    # Storage-smart: a full SPY chain is ~4,500 contracts/day. A +/-moneyness band around spot keeps
    # every strategy leg (calendar ATM + vertical/IC legs out to ~0.08 delta ~= +/-10%) while dropping
    # the far wings. Moneyness is the ROBUST default: yfinance IV (and thus delta) is frequently
    # garbage (~1e-5) pre-/post-market, which collapses a delta filter to almost nothing. A delta
    # band is opt-in for reliable-greek sources (Schwab) and only fires when IV looks healthy.
    ap.add_argument("--moneyness", type=float, default=0.12,
                    help="keep strikes within +/- this fraction of spot (default 0.12; 0 = keep all)")
    ap.add_argument("--delta-min", type=float, default=0.05,
                    help="opt-in delta-band lower |delta| (used only with --delta-max and healthy IV)")
    ap.add_argument("--delta-max", type=float, default=0.0,
                    help="opt-in: also require |delta| <= this (e.g. 0.72); 0 = disabled (use moneyness)")
    args = ap.parse_args()

    use_schwab = args.source == "schwab" or (args.source == "auto" and os.environ.get("SCHWAB_APP_KEY"))
    try:
        df = from_schwab(args.max_dte) if use_schwab else from_yfinance(args.max_dte)
        source = "schwab" if use_schwab else "yfinance"
    except Exception as exc:
        if use_schwab and args.source == "auto":
            print(f"  Schwab failed ({exc}); falling back to yfinance.")
            df, source = from_yfinance(args.max_dte), "yfinance"
        else:
            print(f"  ERROR: {exc}")
            return 1

    if df.empty:
        print("  No contracts returned — market closed or source unavailable.")
        return 1

    df.insert(0, "quote_date", pd.Timestamp.today().normalize())
    df.insert(1, "underlying_symbol", SYMBOL)
    df["abs_delta"] = df["delta"].abs() if "delta" in df else None

    # Capture the current VIX so logged chains satisfy the strategies' VIX gates without a post-hoc
    # merge (and so compile_chains.py doesn't have to backfill it).
    df["vix"] = _current_vix()

    # Storage-smart filter: a full SPY chain is ~4,500 contracts/day (~15 expirations x dense $1
    # strikes). A +/-12% moneyness band keeps every strategy leg (calendar ATM; vertical/IC legs to
    # ~0.08 delta ~= +/-10%) and drops the far wings -- ~700 KB -> ~640 KB/snap, ~160 MB/yr at 2
    # snaps/day vs ~480 unfiltered. The optional delta band cuts harder (~1/3 kept) but only fires
    # when IV is healthy, because yfinance IV is often ~1e-5 (degenerate 0/1 deltas) pre-/post-market.
    if not df.empty and (args.delta_max or args.moneyness):
        before = len(df)
        how = None
        ad = df["delta"].abs() if "delta" in df.columns else None
        # Try the opt-in delta band first, but accept it only if it retains a plausible fraction of
        # the chain (a real chain has ~1/3 in this band). yfinance IV is often ~1e-5 pre-/post-market,
        # which makes deltas a degenerate 0/1 step function; then the band keeps almost nothing, so we
        # reject it and fall back to the robust, greek-independent moneyness band.
        if args.delta_max and ad is not None and ad.notna().mean() >= 0.5:
            cand = df[(ad >= args.delta_min) & (ad <= args.delta_max)]
            if len(cand) >= 0.15 * before:
                df, how = cand.copy(), f"|delta| in [{args.delta_min:.2f}, {args.delta_max:.2f}]"
        if how is None and args.moneyness and "underlying_price" in df.columns:
            spot = float(df["underlying_price"].iloc[0])
            lo, hi = spot * (1 - args.moneyness), spot * (1 + args.moneyness)
            df = df[(df["strike"] >= lo) & (df["strike"] <= hi)].copy()
            how = f"strike within +/-{args.moneyness:.0%} of ${spot:.0f}"
        if how:
            print(f"  storage-smart: kept {len(df):,}/{before:,} contracts ({how})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Stamp date + HHMM so multiple intraday snapshots (e.g. 10:00 and 15:00) coexist instead of
    # overwriting each other.
    out = OUT_DIR / f"SPY_chain_{datetime.now():%Y-%m-%d_%H%M}.csv"
    df.to_csv(out, index=False)
    print(f"  [{source}] wrote {len(df):,} contracts -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
