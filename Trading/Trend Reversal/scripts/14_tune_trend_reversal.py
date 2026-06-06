"""Tune Trend Reversal: EMA lengths x timeframe, judged honestly (Sharpe, drawdown, noise, overfit).

Sweeps the EMA ribbon lengths (superfast, fast, slow) and the low-filter on/off, across four
timeframes (daily, 2-day, 3-day, weekly resampled from daily), evaluated as the equal-weight
long-only **full-timing** portfolio (buy on the green paint, sell on the red) over a universe — by
default the Fundamental Scanner top-20 (your real candidates).

For every (timeframe, config) it records annualised Sharpe, max drawdown, CAGR, and a *noise* proxy
(trades/year + average hold length). Then it keeps itself honest:
  * **Deflated Sharpe Ratio** — discounts the winning config for how many were tried (AFML Ch.14),
  * **Probability of Backtest Overfitting** (CSCV, AFML Ch.11-12) per timeframe,
  * a **70/30 walk-forward holdout** — pick the best config on the first 70% only, then measure it on
    the untouched last 30%, vs the 9/14/21 daily baseline.

A config only counts as a real improvement if it beats 9/14/21 daily *and* survives those checks.

    python scripts/14_tune_trend_reversal.py                       # scanner top-20, all 4 timeframes
    python scripts/14_tune_trend_reversal.py --tickers SPY QQQ IWM --timeframes 1D 1W
"""
import argparse
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from trendrev import data, strategies, backtest, metrics, afml, scanner  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "tuning")
BASELINE = dict(superfast=9, fast=14, slow=21, use_low_filter=True)
SUPERFAST = [5, 9, 13]
FAST = [14, 21, 34]
SLOW = [21, 34, 50]


def configs():
    """Valid EMA configs (superfast < fast < slow) x low-filter on/off; includes the 9/14/21 default."""
    out = []
    for sf, f, s, lf in itertools.product(SUPERFAST, FAST, SLOW, [True, False]):
        if sf < f < s:
            out.append(dict(superfast=sf, fast=f, slow=s, use_low_filter=lf))
    return out


def _label(cfg) -> str:
    return f"{cfg['superfast']}/{cfg['fast']}/{cfg['slow']}{'+lf' if cfg['use_low_filter'] else ''}"


def portfolio_returns(frames, cfg):
    """Equal-weight long-only full-timing (buy green / sell red) portfolio returns + total trades."""
    rmap, n_trades = {}, 0
    for t, df in frames.items():
        if len(df) < 30:           # too few bars to warm the EMAs / form a signal
            continue
        pos = strategies.trend_reversal_long_target(
            df, profit_target=None, exit_signal="sell_signal",
            superfast=cfg["superfast"], fast=cfg["fast"], slow=cfg["slow"],
            use_low_filter=cfg["use_low_filter"])
        res = backtest.run_backtest(df, pos, 1.0, 5.0)
        rmap[t] = res.returns
        n_trades += len(res.trades)
    if not rmap:
        return pd.Series(dtype=float), 0
    port, _ = backtest.equal_weight_returns(rmap)
    return port, n_trades


def evaluate(frames, cfg, ppy, years):
    port, n_trades = portfolio_returns(frames, cfg)
    eq = (1 + port.fillna(0)).cumprod()
    r = port[port.notna()]
    per_obs = float(r.mean() / r.std(ddof=1)) if r.std(ddof=1) > 0 else 0.0
    exposure = float((port != 0).mean())
    trades_per_yr = n_trades / (len(frames) * years) if years > 0 else 0.0
    # avg hold in bars ~ exposure*total_bars / trades, expressed in bars
    avg_hold = (exposure * len(port)) / (n_trades / len(frames)) if n_trades else float("nan")
    return {
        "config": _label(cfg), **cfg,
        "sharpe": metrics.sharpe_ratio(port, ppy),
        "cagr": metrics.cagr(eq),
        "max_dd": metrics.max_drawdown(eq),
        "exposure": exposure,
        "trades_per_yr": trades_per_yr,
        "avg_hold_bars": avg_hold,
        "per_obs_sharpe": per_obs,
        "_returns": port,
    }


def holdout_oos(frames, cfg_grid, ppy, baseline_cfg):
    """Pick the best config on the first 70% of dates, score it on the last 30% vs the baseline."""
    any_idx = next(iter(frames.values())).index
    cut = any_idx[int(len(any_idx) * 0.70)]
    is_frames = {t: d[d.index <= cut] for t, d in frames.items()}
    oos_frames = {t: d[d.index > cut] for t, d in frames.items()}
    best, best_sh = None, -np.inf
    for cfg in cfg_grid:
        p, _ = portfolio_returns(is_frames, cfg)
        sh = metrics.sharpe_ratio(p, ppy)
        if sh > best_sh:
            best, best_sh = cfg, sh
    out = {}
    for tag, cfg in [("picked", best), ("baseline", baseline_cfg)]:
        p, _ = portfolio_returns(oos_frames, cfg)
        out[tag] = {"config": _label(cfg), "oos_sharpe": metrics.sharpe_ratio(p, ppy),
                    "oos_maxdd": metrics.max_drawdown((1 + p.fillna(0)).cumprod())}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="*", default=None, help="default: Fundamental Scanner top-20")
    ap.add_argument("--timeframes", nargs="+", default=["1D", "2D", "3D", "1W"])
    ap.add_argument("--top-n", type=int, default=20)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    tickers = args.tickers or [c.ticker for c in scanner.top_candidates(args.top_n)]
    grid = configs()
    print(f"\nTuning Trend Reversal | universe: {len(tickers)} names | {len(grid)} EMA configs "
          f"x {len(args.timeframes)} timeframes = {len(grid)*len(args.timeframes)} trials")
    print(f"  {', '.join(tickers)}\n  downloading daily data ...")

    daily = {}
    for t in tickers:
        try:
            daily[t] = data.get_ohlcv(t, start="2005-01-01")
        except Exception as exc:
            print(f"  ! skip {t}: {exc}")

    all_rows = []
    best_overall = None
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}")
    for tf in args.timeframes:
        ppy = data.PERIODS_PER_YEAR.get(tf, 252)
        frames = {t: data.resample_ohlcv(d, tf) for t, d in daily.items()}
        years = (next(iter(frames.values())).index[-1]
                 - next(iter(frames.values())).index[0]).days / 365.25

        evals = [evaluate(frames, cfg, ppy, years) for cfg in grid]
        ret_mat = pd.DataFrame({e["config"]: e["_returns"] for e in evals})
        sr_trials = np.array([e["per_obs_sharpe"] for e in evals])
        edf = pd.DataFrame([{k: v for k, v in e.items() if k != "_returns"} for e in evals])
        edf["timeframe"] = tf
        edf = edf.sort_values("sharpe", ascending=False).reset_index(drop=True)

        best = edf.iloc[0]
        dsr = afml.deflated_sharpe_ratio(ret_mat[best["config"]], sr_trials)
        pbo = afml.prob_backtest_overfitting(ret_mat)["pbo"]
        base = edf[edf["config"] == "9/14/21+lf"].iloc[0]

        print(f"\n================  {tf}  (annualise x{ppy})  ================")
        cols = ["config", "sharpe", "cagr", "max_dd", "trades_per_yr", "avg_hold_bars", "exposure"]
        print("Top 5 by Sharpe:")
        print(edf[cols].head(5).to_string(index=False))
        print(f"\n  baseline 9/14/21+lf : Sharpe {base['sharpe']:.3f} | maxDD {base['max_dd']:.3f} "
              f"| {base['trades_per_yr']:.1f} trades/yr")
        print(f"  best {best['config']:>10} : Sharpe {best['sharpe']:.3f} | maxDD {best['max_dd']:.3f} "
              f"| {best['trades_per_yr']:.1f} trades/yr")
        print(f"  overfit checks -> Deflated Sharpe(best) = {dsr:.2%}  |  PBO = {pbo:.2%}  "
              f"({'trust' if dsr > 0.9 and pbo < 0.3 else 'CAUTION'})")

        all_rows.append(edf)
        cand = dict(timeframe=tf, sharpe=best["sharpe"], config=best["config"], dsr=dsr, pbo=pbo)
        if best_overall is None or cand["sharpe"] > best_overall["sharpe"]:
            best_overall = cand

    pd.concat(all_rows).to_csv(os.path.join(OUT, "tune_results.csv"), index=False)

    # Honest OOS check on the daily timeframe (the user's own frame).
    print("\n================  WALK-FORWARD OOS (daily, 70/30 holdout)  ================")
    daily_frames = {t: d for t, d in daily.items()}
    oos = holdout_oos(daily_frames, grid, 252, BASELINE)
    print(f"  picked on first 70%: {oos['picked']['config']:>10} -> OOS Sharpe "
          f"{oos['picked']['oos_sharpe']:.3f} | OOS maxDD {oos['picked']['oos_maxdd']:.3f}")
    print(f"  baseline 9/14/21+lf        -> OOS Sharpe {oos['baseline']['oos_sharpe']:.3f} "
          f"| OOS maxDD {oos['baseline']['oos_maxdd']:.3f}")

    print("\n================  VERDICT  ================")
    print(f"  Highest in-sample Sharpe: {best_overall['config']} on {best_overall['timeframe']} "
          f"(Sharpe {best_overall['sharpe']:.3f}, DSR {best_overall['dsr']:.0%}, PBO {best_overall['pbo']:.0%})")
    print(f"  Full results -> {os.path.join(OUT, 'tune_results.csv')}")
    print("  Trust a change only if it beats 9/14/21 daily AND DSR>90% AND PBO<30% AND OOS holds up.")


if __name__ == "__main__":
    main()
