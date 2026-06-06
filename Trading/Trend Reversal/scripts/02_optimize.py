"""Fine-tune the Trend Reversal EMA lengths with overfitting controls.

Runs a full grid, reports the Deflated Sharpe Ratio of the best config, the Probability of Backtest
Overfitting (CSCV), an anchored walk-forward out-of-sample curve, and a Sharpe heatmap.

    python scripts/02_optimize.py [TICKER]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from trendrev import data, strategies, optimize, afml, plotting, metrics, backtest  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "optimize")

PARAM_GRID = {
    "superfast": [5, 7, 9, 11, 13],
    "fast": [14, 18, 21],
    "slow": [21, 30, 50, 100],
    "use_low_filter": [True, False],
}


def main(ticker: str = "SPY") -> None:
    os.makedirs(OUT, exist_ok=True)
    df = data.get_ohlcv(ticker, start="2005-01-01")

    # Keep only valid (superfast < fast < slow) combinations.
    def strat(d, superfast, fast, slow, use_low_filter):
        return strategies.trend_reversal(d, superfast, fast, slow, use_low_filter, long_short=True)

    grid = {k: v for k, v in PARAM_GRID.items()}
    metrics_df, ret_matrix = optimize.grid_search(df, strat, grid,
                                                  commission_bps=1.0, slippage_bps=5.0)
    # Drop degenerate orderings (superfast must be < fast < slow).
    keep = [c for c in metrics_df.index
            if _ordered(metrics_df.loc[c])]
    metrics_df = metrics_df.loc[keep]
    ret_matrix = ret_matrix[keep]

    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    pd.set_option("display.width", 200)
    cols = ["superfast", "fast", "slow", "use_low_filter", "cagr", "sharpe", "max_drawdown",
            "n_trades", "deflated_sharpe"]
    print(f"\n=== {ticker}: top configs by Sharpe ({len(metrics_df)} valid of grid) ===")
    print(metrics_df[cols].head(12).to_string())

    best = metrics_df.iloc[0]
    print(f"\nBest config Deflated Sharpe (prob. true skill after {len(metrics_df)} trials): "
          f"{best['deflated_sharpe']:.2%}")

    pbo = afml.prob_backtest_overfitting(ret_matrix, n_partitions=10)
    print(f"Probability of Backtest Overfitting (CSCV): {pbo['pbo']:.2%}")
    plotting.plot_pbo(pbo["logits"], pbo["pbo"], os.path.join(OUT, f"{ticker}_pbo.png"))

    # Heatmap of Sharpe across (superfast, slow) with low_filter on.
    sub = metrics_df[metrics_df["use_low_filter"]]
    plotting.plot_heatmap(sub.reset_index(), x="superfast", y="slow", value="sharpe",
                          path=os.path.join(OUT, f"{ticker}_sharpe_heatmap.png"),
                          title=f"{ticker} — Sharpe across (superfast, slow)")

    # Anchored walk-forward out-of-sample.
    wf, choices = optimize.walk_forward(df, strat, grid, n_splits=5,
                                        commission_bps=1.0, slippage_bps=5.0)
    is_sharpe = best["sharpe"]
    oos_sharpe = metrics.sharpe_ratio(wf["returns"])
    print(f"\nWalk-forward (5 folds): in-sample best Sharpe {is_sharpe:.2f} | "
          f"stitched OOS Sharpe {oos_sharpe:.2f}")
    print(choices.to_string(index=False))

    # Plot default (9/14/21) vs best vs walk-forward OOS.
    default_res = backtest.run_backtest(df, strategies.trend_reversal(df))
    best_pos = strategies.trend_reversal(df, int(best["superfast"]), int(best["fast"]),
                                         int(best["slow"]), bool(best["use_low_filter"]))
    best_res = backtest.run_backtest(df, best_pos)
    fig_results = {"default 9/14/21": default_res, "grid-best": best_res}
    plotting.plot_equity(fig_results, os.path.join(OUT, f"{ticker}_optimize_equity.png"),
                         title=f"{ticker} — default vs optimized", benchmark=default_res.benchmark_equity)
    print(f"\nPlots written to {OUT}/")


def _ordered(row) -> bool:
    return row["superfast"] < row["fast"] < row["slow"]


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "SPY")
