#!/usr/bin/env python3
"""Count trades entered during COVID-19 (Feb-Apr 2020) for each finalist, using the main
2018-2026 continuous backtest (same run walk-forward already used). GFC counts already exist in
backtest_results from stress_test_gfc.py runs -- this fills the COVID gap.
Usage: python check_stress_period_trades.py
Output: backtest_results/covid_trade_counts.csv
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
from validate_finalists import FINALISTS, FIXED_ENTRY, FIXED_EXIT

WINDOW = ("2018-01-02", "2026-07-09")
COVID_START, COVID_END = "2020-02-19", "2020-04-07"  # SPY ~34% peak-to-trough


def base_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)


def main():
    cfg = base_config()
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    print("Loading data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)

    rows = []
    for label, entry_overrides, risk_pct in FINALISTS:
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"]["dte_target"] = FIXED_ENTRY["dte"]
        strat_cfg["entry"]["vix_min"] = FIXED_ENTRY["vix_min"]
        strat_cfg["entry"]["vix_max"] = FIXED_ENTRY["vix_max"]
        strat_cfg["entry"].update(entry_overrides)
        strat_cfg["exit"].update(FIXED_EXIT)
        c["position_sizing"]["max_risk_percent"] = risk_pct

        bt = OptopsyBacktester(c)
        strategy = BullPutSpread(strat_cfg)
        res = bt.run_backtest(strategy=strategy, options_data=options_data,
                               underlying_data=underlying, verbose=False)
        trades = res.get("trades")
        n_covid = 0
        covid_pnl = 0.0
        if trades is not None and len(trades) and "entry_date" in trades.columns:
            td = trades.copy()
            td["entry_date"] = pd.to_datetime(td["entry_date"])
            covid_mask = (td["entry_date"] >= COVID_START) & (td["entry_date"] <= COVID_END)
            n_covid = int(covid_mask.sum())
            covid_pnl = float(td.loc[covid_mask, "net_pnl"].sum()) if "net_pnl" in td.columns else float("nan")
        row = {"label": label, "risk_pct": risk_pct, **entry_overrides,
               "covid_trades": n_covid, "covid_pnl": covid_pnl, "total_trades": len(trades) if trades is not None else 0}
        print(row, flush=True)
        rows.append(row)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    df.to_csv("backtest_results/covid_trade_counts.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
