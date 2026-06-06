"""Quantify the repaint trap.

The ThinkScript reversal arrows come from a ZigZag, which only confirms a pivot after price has
already reversed — so on a live chart the arrows shift backward in time ('repaint'). This script
backtests two versions of the *same* ZigZag rule:

* ``zigzag_causal``  — acts only once the reversal is confirmed (honest, tradeable).
* ``zigzag_repaint`` — uses the final pivot location (look-ahead; impossible to trade).

The gap between them is the fake edge that a naive backtest of a repainting indicator would report.

    python scripts/04_repaint_demo.py [TICKER]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, indicators, backtest, metrics, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "repaint")


def main(ticker: str = "SPY", pct: float = 5.0) -> None:
    os.makedirs(OUT, exist_ok=True)
    df = data.get_ohlcv(ticker, start="2005-01-01")

    causal = backtest.run_backtest(df, indicators.zigzag_causal(df, pct),
                                   commission_bps=1.0, slippage_bps=5.0)
    repaint = backtest.run_backtest(df, indicators.zigzag_repaint(df, pct),
                                    commission_bps=1.0, slippage_bps=5.0)

    table = metrics.metrics_table({"zigzag_causal (honest)": causal,
                                   "zigzag_repaint (look-ahead)": repaint})
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 160)
    print(f"\n=== {ticker}: repaint bias at {pct:.0f}% ZigZag ===")
    print(table.T.to_string())

    c, r = table.loc["zigzag_causal (honest)"], table.loc["zigzag_repaint (look-ahead)"]
    print(f"\nFake edge from repaint: CAGR {c['cagr']:.1%} -> {r['cagr']:.1%}, "
          f"Sharpe {c['sharpe']:.2f} -> {r['sharpe']:.2f}.")
    print("Takeaway: trade System A (EMA ribbon, non-repainting). Treat the reversal arrows as the "
          "causal version only; the repainting numbers are an illusion of hindsight.")

    plotting.plot_equity({"causal": causal, "repaint (look-ahead)": repaint},
                         os.path.join(OUT, f"{ticker}_repaint_demo.png"),
                         title=f"{ticker} — repaint look-ahead vs honest ZigZag")
    print(f"\nPlot written to {OUT}/")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "SPY")
