"""Long-only swing strategy: buy the green signal, hold for weeks, exit on profit target OR sell.

This is the workflow: enter when Trend Reversal flips to a buy, then hold until either a set profit
amount is reached or a sell signal appears — no shorting, long or cash only. Runs on a handful of
stocks plus SPY and compares against buy & hold on the same engine and costs.

Examples
--------
    # Full history (2005+), 10% target, exit when the green signal ends:
    python scripts/06_long_hold.py

    # Just the past ~6 months of data, your default tickers:
    python scripts/06_long_hold.py --months 6

    # Custom tickers, 15% target, wait for the red sell signal to exit:
    python scripts/06_long_hold.py --months 6 --target 0.15 --exit sell_signal AAPL MSFT SPY
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, plotting  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "long_hold")
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY"]
# A longer slow EMA + the low filter was the tuned sweet spot for long-only (see README findings).
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)


def window(df: pd.DataFrame, pos: pd.Series, months: int | None):
    """Slice to the last ``months`` of data (signals stay warm because pos is computed on full df)."""
    if not months:
        return df, pos
    cutoff = df.index[-1] - pd.DateOffset(months=months)
    mask = df.index >= cutoff
    return df[mask], pos[mask]


def run_ticker(ticker: str, months: int | None, target: float | None, exit_signal: str):
    start = (
        (pd.Timestamp.today() - pd.DateOffset(months=months + 10)).strftime("%Y-%m-%d")
        if months
        else "2005-01-01"
    )
    df = data.get_ohlcv(ticker, start=start)
    pos = strategies.trend_reversal_long_target(
        df, profit_target=target, exit_signal=exit_signal, **EMA
    )
    df_w, pos_w = window(df, pos, months)
    res = backtest.run_backtest(df_w, pos_w, commission_bps=1.0, slippage_bps=5.0)
    bh = backtest.run_backtest(df_w, strategies.buy_and_hold(df_w),
                               commission_bps=0.0, slippage_bps=0.0)
    return df_w, res, bh


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS,
                    help=f"tickers to test (default: {' '.join(DEFAULT_TICKERS)})")
    ap.add_argument("--months", type=int, default=None,
                    help="restrict the backtest to the last N months of data (e.g. 6)")
    ap.add_argument("--target", type=float, default=0.10,
                    help="profit target as a fraction, e.g. 0.10 = 10%% (use 0 for signal-only exit)")
    ap.add_argument("--exit", dest="exit_signal", choices=["buy_end", "sell_signal"],
                    default="buy_end", help="sell trigger: green ends (buy_end) or red appears")
    args = ap.parse_args()
    tickers = args.tickers or DEFAULT_TICKERS
    target = None if args.target in (0, 0.0) else args.target
    os.makedirs(OUT, exist_ok=True)

    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 200)

    tgt_label = "signal-only" if target is None else f"{target:.0%}"
    span = f"last {args.months} months" if args.months else "2005-present"
    print(f"\nLong-only swing | target={tgt_label} | exit={args.exit_signal} | window={span}")
    print("Rule: buy on green signal, hold until profit target OR sell signal, long-or-cash.\n")

    rows = []
    for t in tickers:
        df_w, res, bh = run_ticker(t, args.months, target, args.exit_signal)
        m = metrics.compute_metrics(res)
        rows.append({
            "ticker": t,
            "bars": len(df_w),
            "strat_total_ret": m["total_return"],
            "strat_cagr": m["cagr"],
            "strat_sharpe": m["sharpe"],
            "strat_maxDD": m["max_drawdown"],
            "exposure": m["exposure"],
            "n_trades": m["n_trades"],
            "win_rate": m["win_rate"],
            "bh_total_ret": metrics.compute_metrics(bh)["total_return"],
            "bh_maxDD": metrics.compute_metrics(bh)["max_drawdown"],
        })
        plotting.plot_equity({"long-hold": res},
                             os.path.join(OUT, f"{t}_longhold_equity.png"),
                             title=f"{t} — long-hold (target {tgt_label}) vs buy & hold",
                             benchmark=res.benchmark_equity)

    table = pd.DataFrame(rows).set_index("ticker")
    print(table.to_string())
    print("\n=== Averages across tickers ===")
    avg = table[["strat_total_ret", "strat_cagr", "strat_sharpe", "strat_maxDD",
                 "exposure", "bh_total_ret", "bh_maxDD"]].mean()
    print(avg.to_string())
    table.to_csv(os.path.join(OUT, "long_hold_metrics.csv"))
    print(f"\nEquity plots + long_hold_metrics.csv written to {OUT}/")


if __name__ == "__main__":
    main()
