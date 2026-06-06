"""Faithful Trend Reversal backtest on SPY: metrics table + price/equity/drawdown plots.

    python scripts/01_run_trend_reversal.py [TICKER]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "trend_reversal")


def main(ticker: str = "SPY") -> None:
    os.makedirs(OUT, exist_ok=True)
    df = data.get_ohlcv(ticker, start="2005-01-01")
    print(f"{ticker}: {len(df)} daily bars  {df.index[0].date()} -> {df.index[-1].date()}\n")

    frame = strategies.trend_reversal_frame(df)
    pos = strategies.trend_reversal(df, long_short=True)
    res = run = backtest.run_backtest(df, pos, commission_bps=1.0, slippage_bps=5.0)

    # Buy & hold benchmark on the same engine.
    bh = backtest.run_backtest(df, strategies.buy_and_hold(df))

    table = metrics.metrics_table({"trend_reversal": res, "buy_hold": bh})
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 160)
    print(table.T.to_string())

    plotting.plot_price_signals(df, frame, os.path.join(OUT, f"{ticker}_signals.png"),
                                title=f"{ticker} — Trend Reversal signals")
    plotting.plot_equity({"trend_reversal": res}, os.path.join(OUT, f"{ticker}_equity.png"),
                         title=f"{ticker} — Trend Reversal vs buy & hold",
                         benchmark=res.benchmark_equity)
    plotting.plot_drawdown(res.equity, os.path.join(OUT, f"{ticker}_drawdown.png"),
                           title=f"{ticker} — Trend Reversal drawdown")
    print(f"\nPlots written to {OUT}/")
    print(f"Trades: {len(res.trades)} | sample:\n{res.trades.head().to_string(index=False)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "SPY")
