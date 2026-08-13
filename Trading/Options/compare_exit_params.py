#!/usr/bin/env python3
"""
Does a wider profit_target/stop_loss rescue the $5-wide 0.20Δ structure, or is the friction
disadvantage independent of exit timing? Exit params (profit_target=0.60, stop_loss=0.50) were
held FIXED across every width/delta combo in the 2026-08-09 investigation -- this checks whether
that choice specifically penalized the narrowest structure (which churns fastest: a routine market
wobble is a much bigger fraction of a $5-wide spread's total risk than of a wide delta-selected
spread's, so the SAME 50%-of-max-loss stop fires far more often on noise).

Tests 0.20Δ/$5-wide against 0.20Δ/0.10Δ (delta-selected, the winning structure) across a
profit_target x stop_loss grid, same risk budget for both, on the 2018-2026 window.

Usage: python compare_exit_params.py
Output: backtest_results/exit_params_sweep.csv
"""
import sys, os, copy, itertools
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

WINDOW = ("2018-01-02", "2026-07-09")
PROFIT_TARGETS = [0.40, 0.60, 0.80]
STOP_LOSSES = [0.50, 0.70, 0.90]
RISK_PCT = 20

STRUCTURES = [
    ("w5",  {"short_delta": 0.20, "strike_width": 5}),
    ("d10", {"short_delta": 0.20, "long_delta": 0.10}),
]


def base_config() -> dict:
    with open("config/config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["position_sizing"]["max_risk_percent"] = RISK_PCT
    return cfg


def main() -> int:
    cfg = base_config()
    print("Loading synthetic options data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)
    print(f"  {len(options_data):,} rows, {len(underlying)} underlying rows")

    rows = []
    combos = list(itertools.product(STRUCTURES, PROFIT_TARGETS, STOP_LOSSES))
    for i, ((label, entry_over), pt, sl) in enumerate(combos, 1):
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"]["dte_target"] = 30
        strat_cfg["entry"]["vix_min"] = 10
        strat_cfg["entry"]["vix_max"] = 35
        strat_cfg["entry"].update(entry_over)
        strat_cfg["exit"]["profit_target"] = pt
        strat_cfg["exit"]["stop_loss"] = sl
        strat_cfg["exit"]["dte_min"] = 22

        bt = OptopsyBacktester(c)
        strategy = BullPutSpread(strat_cfg)
        try:
            res = bt.run_backtest(strategy=strategy, options_data=options_data,
                                   underlying_data=underlying, verbose=False)
            m = calculate_performance_metrics(res)
            row = {"structure": label, "profit_target": pt, "stop_loss": sl,
                   "cagr_pct": m.get("annualized_return_pct"), "sharpe": m.get("sharpe_ratio"),
                   "max_dd_pct": m.get("max_drawdown_pct"), "calmar": m.get("calmar_ratio"),
                   "trades": m.get("total_trades"), "win_rate_pct": m.get("win_rate_pct")}
            print(f"[{i}/{len(combos)}] {label} pt={pt} sl={sl}: Sharpe={row['sharpe']:.2f} "
                  f"CAGR={row['cagr_pct']:.1f}% DD={row['max_dd_pct']:.1f}% trades={row['trades']}", flush=True)
        except Exception as e:
            row = {"structure": label, "profit_target": pt, "stop_loss": sl, "error": str(e)}
            print(f"[{i}/{len(combos)}] {label} pt={pt} sl={sl}: FAIL {e}", flush=True)
        rows.append(row)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / "exit_params_sweep.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
