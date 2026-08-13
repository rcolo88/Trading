#!/usr/bin/env python3
"""
Does exit dte_min (how early to close regardless of P&L) change the picture for the 0.12Δ/0.08Δ
structure that just proved out as the best-performing candidate in the whole investigation?
Every prior test in this project held dte_min=22 fixed -- never varied.

Sweeps dte_min in {22, 15, 10, 5} for 0.12Δ/0.08Δ (pt=0.8, sl=0.8, the best exit combo found) at
both 15% and 20% risk, full continuous 2008-2026 span, $20k.

Usage: python compare_exit_dte.py
Output: backtest_results/exit_dte_sweep.csv
"""
import sys, os, copy
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

FULL_SPAN = ("2008-01-02", "2026-07-09")
DTE_MINS = [22, 15, 10, 5]
RISK_PCTS = [15, 20]


def base_config():
    with open("config/config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["start_date"] = "2008-01-01"
    cfg["synthetic_data"]["end_date"] = "2026-07-10"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = FULL_SPAN
    return cfg


def main():
    cfg = base_config()
    print("Loading full 2008-2026 data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*FULL_SPAN)
    print(f"  {len(options_data):,} rows, {len(underlying)} underlying rows")

    combos = [(dm, rp) for dm in DTE_MINS for rp in RISK_PCTS]
    rows = []
    for i, (dm, rp) in enumerate(combos, 1):
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"]["dte_target"] = 30
        strat_cfg["entry"]["vix_min"] = 10
        strat_cfg["entry"]["vix_max"] = 35
        strat_cfg["entry"]["short_delta"] = 0.12
        strat_cfg["entry"]["long_delta"] = 0.08
        strat_cfg["entry"].pop("strike_width", None)
        strat_cfg["exit"]["profit_target"] = 0.80
        strat_cfg["exit"]["stop_loss"] = 0.80
        strat_cfg["exit"]["dte_min"] = dm
        c["position_sizing"]["max_risk_percent"] = rp

        bt = OptopsyBacktester(c)
        strategy = BullPutSpread(strat_cfg)
        try:
            res = bt.run_backtest(strategy=strategy, options_data=options_data,
                                   underlying_data=underlying, verbose=False)
            m = calculate_performance_metrics(res)
            row = {"dte_min": dm, "risk_pct": rp, "cagr_pct": m.get("annualized_return_pct"),
                   "sharpe": m.get("sharpe_ratio"), "max_dd_pct": m.get("max_drawdown_pct"),
                   "calmar": m.get("calmar_ratio"), "trades": m.get("total_trades"),
                   "win_rate_pct": m.get("win_rate_pct"), "avg_days": None}
            trades = res.get("trades")
            if trades is not None and len(trades) and "days_in_trade" in trades.columns:
                row["avg_days"] = float(trades["days_in_trade"].mean())
            print(f"[{i}/{len(combos)}] dte_min={dm} risk={rp}%: Sharpe={row['sharpe']:.2f} "
                  f"CAGR={row['cagr_pct']:.1f}% DD={row['max_dd_pct']:.1f}% "
                  f"trades={row['trades']} avg_days={row['avg_days']}", flush=True)
        except Exception as e:
            row = {"dte_min": dm, "risk_pct": rp, "error": str(e)}
            print(f"[{i}/{len(combos)}] FAIL: {e}", flush=True)
        rows.append(row)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / "exit_dte_sweep.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
