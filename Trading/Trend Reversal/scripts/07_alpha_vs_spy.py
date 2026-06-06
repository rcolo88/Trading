"""Alpha of the long-only swing strategy vs a buy & hold of SPY (the S&P 500).

For each ticker we run the long-only Trend Reversal swing (signal-only exit by default — the variant
that lets winners run), then regress its daily returns on SPY buy & hold to get CAPM alpha/beta. We
also build an equal-weight portfolio of the per-ticker strategies and measure its alpha. 'ann_alpha'
is the annualized return added *beyond* S&P 500 market exposure; a positive, significant alpha
(|t| > 2) is the real edge.

    python scripts/07_alpha_vs_spy.py [--target 0.0] [--exit buy_end] [--months N] TICKER...
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "alpha")
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "SPY"]
EMA = dict(superfast=9, fast=14, slow=21, use_low_filter=True)


def strat_returns(ticker, start, target, exit_signal):
    df = data.get_ohlcv(ticker, start=start)
    pos = strategies.trend_reversal_long_target(df, profit_target=target, exit_signal=exit_signal, **EMA)
    res = backtest.run_backtest(df, pos, commission_bps=1.0, slippage_bps=5.0)
    return df, res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="*", default=DEFAULT_TICKERS)
    ap.add_argument("--target", type=float, default=0.0,
                    help="profit target fraction (0 = signal-only, the recommended variant)")
    ap.add_argument("--exit", dest="exit_signal", choices=["buy_end", "sell_signal"],
                    default="buy_end")
    ap.add_argument("--months", type=int, default=None)
    args = ap.parse_args()
    tickers = args.tickers or DEFAULT_TICKERS
    target = None if args.target in (0, 0.0) else args.target
    start = ((pd.Timestamp.today() - pd.DateOffset(months=args.months + 10)).strftime("%Y-%m-%d")
             if args.months else "2005-01-01")

    # SPY buy & hold benchmark (open-to-open, no cost) over the full available window.
    spy_df = data.get_ohlcv("SPY", start=start)
    spy_bh = backtest.run_backtest(spy_df, strategies.buy_and_hold(spy_df),
                                   commission_bps=0.0, slippage_bps=0.0)
    spy_bh_ret = spy_bh.returns
    spy_bh_cagr = metrics.cagr(spy_bh.benchmark_equity)

    def windowed(ret):
        if not args.months:
            return ret
        cutoff = ret.index[-1] - pd.DateOffset(months=args.months)
        return ret[ret.index >= cutoff]

    bench = windowed(spy_bh_ret)
    rows, strat_ret_map = [], {}
    for t in tickers:
        _, res = strat_returns(t, start, target, args.exit_signal)
        sret = windowed(res.returns)
        strat_ret_map[t] = sret
        ab = metrics.alpha_beta(sret, bench)
        scagr = metrics.cagr((1 + sret.fillna(0)).cumprod())
        rows.append({
            "ticker": t,
            "strat_cagr": scagr,
            "spy_bh_cagr": spy_bh_cagr,
            "cagr_minus_spy": scagr - spy_bh_cagr,
            "ann_alpha": ab["ann_alpha"],
            "alpha_tstat": ab["alpha_tstat"],
            "beta": ab["beta"],
            "r2": ab["r_squared"],
        })

    # Equal-weight portfolio of the per-ticker strategies.
    port = pd.concat(strat_ret_map.values(), axis=1).mean(axis=1)
    pab = metrics.alpha_beta(port, bench)
    port_cagr = metrics.cagr((1 + port.fillna(0)).cumprod())
    rows.append({
        "ticker": "PORTFOLIO(eq-wt)",
        "strat_cagr": port_cagr,
        "spy_bh_cagr": spy_bh_cagr,
        "cagr_minus_spy": port_cagr - spy_bh_cagr,
        "ann_alpha": pab["ann_alpha"],
        "alpha_tstat": pab["alpha_tstat"],
        "beta": pab["beta"],
        "r2": pab["r_squared"],
    })

    table = pd.DataFrame(rows).set_index("ticker")
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 200)
    tgt = "signal-only" if target is None else f"{target:.0%}"
    span = f"last {args.months}m" if args.months else "2005-present"
    print(f"\nAlpha vs SPY buy & hold | long-only | target={tgt} | exit={args.exit_signal} | {span}")
    print(f"SPY buy & hold CAGR over window: {spy_bh_cagr:.2%}\n")
    print(table.to_string())
    print("\nReading it: ann_alpha = annualized return beyond S&P 500 exposure; "
          "alpha_tstat |t|>2 ~ statistically significant; beta = market sensitivity.")
    table.to_csv(os.path.join(OUT, "alpha_vs_spy.csv"))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    main()
