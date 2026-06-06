"""Strategy bake-off: every strategy on the same engine, costs, and instruments.

    python scripts/03_bakeoff.py [TICKER ...]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "bakeoff")


def run_one(ticker: str) -> pd.DataFrame:
    df = data.get_ohlcv(ticker, start="2005-01-01")
    results = {}
    for name, (fn, params) in strategies.REGISTRY.items():
        pos = fn(df, **params)
        results[name] = backtest.run_backtest(df, pos, commission_bps=1.0, slippage_bps=5.0)
    table = metrics.metrics_table(results)
    plotting.plot_equity(results, os.path.join(OUT, f"{ticker}_bakeoff_equity.png"),
                         title=f"{ticker} — strategy bake-off")
    table.insert(0, "ticker", ticker)
    return table


def main(tickers) -> None:
    os.makedirs(OUT, exist_ok=True)
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 200)
    cols = ["ticker", "cagr", "sharpe", "sortino", "max_drawdown", "calmar", "exposure",
            "n_trades", "win_rate", "profit_factor"]
    all_tables = []
    for t in tickers:
        table = run_one(t)
        print(f"\n=== {t} ===")
        print(table[cols].to_string())
        all_tables.append(table)
    combined = pd.concat(all_tables)
    combined.to_csv(os.path.join(OUT, "bakeoff_metrics.csv"))
    # Average Sharpe rank across instruments.
    print("\n=== Mean Sharpe across instruments ===")
    print(combined.groupby(level=0)["sharpe"].mean().sort_values(ascending=False).to_string())
    print(f"\nMetrics CSV + equity plots written to {OUT}/")


if __name__ == "__main__":
    args = sys.argv[1:] or ["SPY", "QQQ", "IWM"]
    main(args)
