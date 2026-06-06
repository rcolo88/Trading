"""Plot live BUY/SELL signal charts you can trade from.

Draws candles colored by the (non-repainting) Trend Reversal state, the EMA 9/14/21 ribbon, and
BUY ▲ / SELL ▼ arrows where the long signal turns on/off — then prints the current state and the
latest signal for each ticker so you know what to do right now.

    python scripts/08_signal_chart.py                 # default basket, last ~9 months
    python scripts/08_signal_chart.py --lookback 120 AAPL NVDA SPY
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "signal_charts")
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY"]
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)


def latest_signal(df: pd.DataFrame, frame: pd.DataFrame) -> str:
    buy = frame["buysignal"]
    sell = frame["sellsignal"]
    last = df.index[-1]
    price = df["close"].iloc[-1]
    if buy.iloc[-1] == 1:
        # When did the current long run start?
        run = buy[buy == 1]
        start = run.index[-1]
        for ts in reversed(buy.index):
            if buy.loc[ts] == 1:
                start = ts
            else:
                break
        entry_px = df["close"].loc[start]
        chg = price / entry_px - 1
        state = (f"BUY/LONG since {start.date()} @ {entry_px:.2f} | now {price:.2f} "
                 f"({chg:+.1%}) as of {last.date()}")
    elif sell.iloc[-1] == 1:
        state = f"SELL/BEARISH (red) — stay out/flat | {price:.2f} as of {last.date()}"
    else:
        state = f"NEUTRAL — no position | {price:.2f} as of {last.date()}"

    # Most recent BUY or SELL arrow.
    entries = buy[(buy == 1) & (buy.shift(1) == 0)]
    exits = buy[(buy == 0) & (buy.shift(1) == 1)]
    last_buy = entries.index[-1].date() if len(entries) else "none"
    last_sell = exits.index[-1].date() if len(exits) else "none"
    return f"{state}\n      last BUY arrow: {last_buy} | last SELL arrow: {last_sell}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS)
    ap.add_argument("--lookback", type=int, default=190,
                    help="trading days to display on the chart (default ~9 months)")
    args = ap.parse_args()
    tickers = args.tickers or DEFAULT_TICKERS
    os.makedirs(OUT, exist_ok=True)

    # Pull enough history to warm the EMAs even for a short lookback.
    start = (pd.Timestamp.today() - pd.DateOffset(days=args.lookback + 200)).strftime("%Y-%m-%d")
    print("\nCurrent Trend Reversal status (non-repainting System-A signals):\n")
    for t in tickers:
        df = data.get_ohlcv(t, start=start, refresh=True)
        frame = strategies.trend_reversal_frame(df, **EMA)
        path = os.path.join(OUT, f"{t}_trade_chart.png")
        plotting.plot_trade_chart(df, frame, path,
                                  title=f"{t} — Trend Reversal BUY/SELL signals",
                                  lookback=args.lookback)
        print(f"  {t:6s} {latest_signal(df, frame)}")
        print(f"         chart: {path}")
    print(f"\nCharts written to {OUT}/ — green ▲ = BUY, red ▼ = SELL, candle color = signal state.")


if __name__ == "__main__":
    main()
