#!/usr/bin/env python3
"""Controlled short_delta x stop_loss sweep (2026-08-13).

The Optuna log CANNOT answer "why not 25-30 delta with a 50-70% stop?" because TPE concentrates
its samples: 58 of 127 trials landed on short_delta=0.35 (the search CEILING) while 0.15-0.25
got 2-5 trials each, every one of them carrying a random companion set of profit_target/dte_min.
So the marginal "low delta is bad" reading is confounded with "low delta was only ever tested
alongside bad exit params".

This holds every other parameter at the published winner (21 DTE / PT 80% / exit 5 DTE) and varies
ONLY short_delta and stop_loss on a full factorial grid, so the comparison is causal.

The long wing is held at a CONSTANT 0.20 delta gap below the short (winner = 0.35/0.15), which
keeps the structural shape comparable instead of silently narrowing the spread as short delta falls.

Also reports what the stop-loss parameter actually MEANS in trader terms: the code triggers on
`(-profit)/max_loss >= stop_loss` where max_loss = width - credit, i.e. it is a fraction of MAX
LOSS, not a fraction of credit received. Those are very different numbers.

Usage: opt_venv/bin/python compare_delta_stop_grid.py
"""
import sys, os, copy, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd, numpy as np
from pathlib import Path
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics
from src.analysis import regime

WINDOW = ("2018-01-02", "2026-07-09")
OOS_START = "2023-12-20"
CAPITAL = 150000

SHORT_DELTAS = [0.20, 0.25, 0.30, 0.35]
STOP_LOSSES = [0.30, 0.50, 0.70, 0.99]   # 0.99 ~= "no stop, ride to PT / DTE floor"
DELTA_GAP = 0.20                          # long = short - gap (winner: 0.35 -> 0.15)
FIXED = {"dte_target": 21, "profit_target": 0.80, "dte_min": 5}

# --width $N pins the DOLLAR wing width instead of the delta gap. The delta-gap mode above is not a
# clean short_delta test on its own: a constant 0.20 gap makes the spread much WIDER in dollars as
# short delta falls (credit is 6.3% of width at 0.20/0.03 vs 20.4% at 0.35/0.15), so risk per
# contract -- and therefore drawdown -- rises as delta drops, confounding delta with position size.
# Fixing the width holds dollar risk per contract roughly constant across the delta axis instead.
FIXED_WIDTH = None


def base_config():
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = CAPITAL
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1
    return cfg


def sharpe_of_slice(equity, start=None, end=None):
    """Annualized Sharpe from the total_value column over a date slice (scale-invariant)."""
    eq = equity.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    if start is not None:
        eq = eq[eq["date"] >= pd.Timestamp(start)]
    if end is not None:
        eq = eq[eq["date"] < pd.Timestamp(end)]
    if len(eq) < 20:
        return np.nan
    r = eq["total_value"].pct_change().dropna()
    if r.std() == 0:
        return np.nan
    return float(r.mean() / r.std() * np.sqrt(252))


def run_one(short_delta, stop_loss, options_data, underlying, cfg_template):
    cfg = copy.deepcopy(cfg_template)
    sc = cfg["strategies"]["bull_put_spread"]
    sc["entry"].pop("strike_width", None)
    sc["entry"].pop("long_delta", None)
    if FIXED_WIDTH is not None:
        long_delta = np.nan
        wing = {"strike_width": FIXED_WIDTH}
    else:
        long_delta = round(max(0.03, short_delta - DELTA_GAP), 2)
        wing = {"long_delta": long_delta}
    sc["entry"].update({"dte_target": FIXED["dte_target"], "short_delta": short_delta, **wing})
    sc["entry"]["vix_min"], sc["entry"]["vix_max"] = 0, 999
    sc["exit"].update({"profit_target": FIXED["profit_target"],
                       "stop_loss": stop_loss, "dte_min": FIXED["dte_min"]})

    bt = OptopsyBacktester(cfg)
    res = bt.run_backtest(strategy=BullPutSpread(sc), options_data=options_data,
                          underlying_data=underlying, verbose=False)
    m = calculate_performance_metrics(res)
    trades = res["trades"].copy()
    eq = res["equity_curve"]

    # --- what the stop-loss parameter means in trader terms, measured on real entries ---
    credit_pct_of_width = np.nan
    stop_as_pct_of_credit = np.nan
    if len(trades):
        width = (trades["leg1_strike"] - trades["leg2_strike"]).abs()
        credit = -trades["entry_price"]           # entry_price < 0 for a credit spread
        ok = (width > 0) & (credit > 0)
        if ok.any():
            ratio = (credit[ok] / width[ok]).median()
            credit_pct_of_width = ratio * 100
            # loss at trigger = stop_loss * max_loss = stop_loss * (width - credit)
            # express that as a multiple of the credit collected
            stop_as_pct_of_credit = stop_loss * (1 - ratio) / ratio * 100

    # --- exit reason mix: is the stop even binding? ---
    reasons = {}
    if len(trades) and "exit_reason" in trades:
        def bucket(s):
            s = str(s)
            if s.startswith("Profit target"):
                return "profit_target"
            if s.startswith("Stop loss"):
                return "stop_loss"
            if "DTE" in s or "dte" in s:
                return "dte_exit"
            if "Expired" in s:
                return "expired"
            return "other"
        vc = trades["exit_reason"].map(bucket).value_counts(normalize=True) * 100
        reasons = vc.to_dict()

    rg = regime.regime_conditional_metrics(eq, trades)
    is_sharpe = sharpe_of_slice(eq, end=OOS_START)
    oos_sharpe = sharpe_of_slice(eq, start=OOS_START)

    row = {
        "short_delta": short_delta, "long_delta": long_delta, "stop_loss": stop_loss,
        "trades": len(trades),
        "sharpe_full": m.get("sharpe_ratio"), "sharpe_is": is_sharpe, "sharpe_oos": oos_sharpe,
        "cagr_pct": m.get("annualized_return_pct"),
        "total_return_pct": m.get("total_return_pct"),
        "max_dd_pct": m.get("max_drawdown_pct"),
        "win_rate_pct": m.get("win_rate_pct"),
        "profit_factor": m.get("profit_factor"),
        "avg_win": m.get("avg_win"), "avg_loss": m.get("avg_loss"),
        "largest_loss": m.get("largest_loss"),
        "avg_days_in_trade": m.get("avg_days_in_trade"),
        "calm_sharpe": rg.get("calm_sharpe_ratio"), "stress_sharpe": rg.get("stress_sharpe_ratio"),
        "stress_max_dd_pct": rg.get("stress_max_drawdown_pct"),
        "credit_pct_of_width": credit_pct_of_width,
        "stop_as_pct_of_credit": stop_as_pct_of_credit,
        "pct_exit_stop": reasons.get("stop_loss", 0.0),
        "pct_exit_pt": reasons.get("profit_target", 0.0),
        "pct_exit_dte": reasons.get("dte_exit", 0.0),
    }
    print(f"  {short_delta:.2f}/{long_delta:.2f} SL={stop_loss:.2f} | "
          f"Sharpe full={row['sharpe_full']:.3f} IS={is_sharpe:.3f} OOS={oos_sharpe:.3f} | "
          f"DD={row['max_dd_pct']:.1f}% win={row['win_rate_pct']:.1f}% | "
          f"stop-exits={row['pct_exit_stop']:.1f}% | SL={stop_as_pct_of_credit:.0f}% of credit")
    return row


def main():
    global FIXED_WIDTH
    if "--width" in sys.argv:
        FIXED_WIDTH = int(sys.argv[sys.argv.index("--width") + 1])
        print(f"FIXED-WIDTH mode: wing pinned at ${FIXED_WIDTH} across all short deltas")
    cfg = base_config()
    print("Loading corrected (delta_band) 2018-2026 options data...")
    options_data = load_sample_spy_options_data(config=cfg)
    print(f"  {len(options_data):,} rows")
    underlying = fetch_spy_data(*WINDOW)

    rows = []
    print(f"\nControlled grid: {len(SHORT_DELTAS)}x{len(STOP_LOSSES)} = "
          f"{len(SHORT_DELTAS)*len(STOP_LOSSES)} runs, all else fixed at {FIXED}\n")
    for sd, sl in itertools.product(SHORT_DELTAS, STOP_LOSSES):
        rows.append(run_one(sd, sl, options_data, underlying, cfg))

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / (f"compare_delta_stop_grid_w{FIXED_WIDTH}.csv" if FIXED_WIDTH else "compare_delta_stop_grid.csv")
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}\n")

    for metric in ["sharpe_full", "sharpe_oos", "max_dd_pct", "stress_sharpe", "pct_exit_stop"]:
        print(f"=== {metric} (rows=short_delta, cols=stop_loss) ===")
        print(df.pivot(index="short_delta", columns="stop_loss", values=metric).round(3).to_string())
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
