#!/usr/bin/env python3
"""Quality (Fundamental Scanner) x timing (Trend Reversal) -> defined-risk options watchlist.

For each top-N quality name from the sibling Fundamental Scanner, compute the current Trend Reversal
System-A state on 3-day bars (the trendrev tuning sweet spot) and flag the names that have *freshly*
flipped to a buy — the moment to express a bullish, defined-risk options view.

We have no single-name option chains, so each idea is a broker-ready TEMPLATE (structure, target
deltas, DTE, dollar risk) rather than a backtested P&L. This is HONEST by construction: it reads
*today's* scanner output and *today's* price state only — no historical selection P&L, no hindsight.

Usage:
    opt_venv/bin/python scanner_options_watchlist.py            # scanner top-12, $500 risk/idea
    opt_venv/bin/python scanner_options_watchlist.py --top-n 20 --risk 1000
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "Trend Reversal"))
from trendrev import data as tr_data          # noqa: E402
from trendrev import scanner as tr_scanner     # noqa: E402
from trendrev.strategies import trend_reversal_frame  # noqa: E402

FRESH_BARS = 2  # a "fresh" flip = within the last N 3-day bars (~ last 6 trading days)


def state_info(ticker: str):
    """Return (state, bars_since_flip, flip_date, price_at_flip, last_price) on 3-day bars."""
    df = tr_data.resample_ohlcv(tr_data.get_ohlcv(ticker, start="2023-01-01"), "3D")
    if len(df) < 30:
        return None
    f = trend_reversal_frame(df)
    buy, sell = f["buysignal"].values, f["sellsignal"].values
    state = "green" if buy[-1] == 1 else "red" if sell[-1] == 1 else "neutral"
    series = buy if state == "green" else sell if state == "red" else None
    bars_since, flip_date, price_at_flip = None, None, None
    if series is not None:
        i = len(series) - 1
        while i > 0 and series[i - 1] == 1:
            i -= 1
        bars_since = len(series) - 1 - i
        flip_date, price_at_flip = df.index[i].date(), float(df["close"].iloc[i])
    return state, bars_since, flip_date, price_at_flip, float(df["close"].iloc[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top-n", type=int, default=12)
    ap.add_argument("--risk", type=float, default=500.0, help="max $ loss per idea (= debit budget)")
    args = ap.parse_args()

    cands = tr_scanner.top_candidates(n=args.top_n, require_gates=True)
    print(f"\nScanner top-{args.top_n} quality names x Trend Reversal (3-day bars). Risk/idea ${args.risk:.0f}.\n")
    print(f"{'TICKER':<7}{'TIER':<16}{'STATE':<9}{'SINCE':<22}{'MOVE':>7}   IDEA")

    fresh = []
    for c in cands:
        info = state_info(c.ticker)
        if info is None:
            continue
        state, bars, flip_date, p0, p1 = info
        move = f"{(p1/p0-1)*100:+.1f}%" if p0 else "  -"
        since = f"{flip_date} ({bars}b)" if flip_date else "-"
        is_fresh = state == "green" and bars is not None and bars <= FRESH_BARS
        if is_fresh:
            idea = "BUY-NOW: bullish call debit spread"
            fresh.append(c.ticker)
        elif state == "green":
            idea = "hold / already extended"
        elif state == "red":
            idea = "AVOID (downtrend) — no bullish entry"
        else:
            idea = "wait for a green flip"
        flag = "* " if is_fresh else "  "
        print(f"{flag}{c.ticker:<5}{c.tier[:15]:<16}{state:<9}{since:<22}{move:>7}   {idea}")

    print("\n" + "=" * 70)
    if fresh:
        print(f"FRESH BUYS ({len(fresh)}): {', '.join(fresh)}")
        print("Broker-ready template for each (defined risk = max loss = the debit you pay):")
        print(f"  * Call DEBIT spread, 45-60 DTE: BUY ~0.60-delta call, SELL ~0.30-delta call (same expiry)")
        print(f"  * Size so the net debit per spread x 100 x contracts <= ${args.risk:.0f}")
        print(f"  * Exit: take profit ~50-75% of width, or cut on a Trend Reversal red flip / green-end")
    else:
        print("No fresh green flips today — nothing to put on. (Quality names that just turned up are")
        print("the trigger; an already-green, extended name is a worse entry.)")
    print("Caveat: a screen, not a backtest. Confirm liquidity/spreads before trading single-name options.\n")


if __name__ == "__main__":
    main()
