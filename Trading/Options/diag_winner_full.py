#!/usr/bin/env python3
"""Full metrics + achieved-vs-target delta diagnostic + GFC replay for the daily-cadence delta-wing
winner: dte=24, short_delta=0.35, long_delta=0.19, profit_target=0.9, stop_loss=0.3, dte_min=5,
fixed_contracts=1. Answers: (1) full 2018-2026 return metrics, (2) how far off the actually-traded
deltas land from the 0.35/0.19 targets given the $5 synthetic strike grid, (3) GFC (2008-09)."""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd, numpy as np
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

WINNER = {"dte_target": 24, "short_delta": 0.35, "long_delta": 0.19,
          "profit_target": 0.9, "stop_loss": 0.3, "dte_min": 5,
          "vix_min": 0, "vix_max": 999}


def run(window, capital, label, specific_file=None):
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = window
    cfg["backtest"]["initial_capital"] = capital
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1

    print(f"\n{'='*70}\n{label}: {window}\n{'='*70}")
    options_data = load_sample_spy_options_data(specific_file=specific_file, config=cfg)
    underlying = fetch_spy_data(*window)

    strat_cfg = cfg["strategies"]["bull_put_spread"]
    strat_cfg["entry"].update(WINNER)
    strat_cfg["entry"].pop("strike_width", None)
    strat_cfg["exit"]["profit_target"] = WINNER["profit_target"]
    strat_cfg["exit"]["stop_loss"] = WINNER["stop_loss"]
    strat_cfg["exit"]["dte_min"] = WINNER["dte_min"]

    bt = OptopsyBacktester(cfg)
    strategy = BullPutSpread(strat_cfg)
    res = bt.run_backtest(strategy=strategy, options_data=options_data, underlying_data=underlying, verbose=False)
    metrics = calculate_performance_metrics(res)

    trades = res["trades"].copy()
    achieved_short = trades["leg1_delta"].abs()
    achieved_long = trades["leg2_delta"].abs()

    print(f"Trades: {len(trades)}")
    print(f"CAGR (annualized_return_pct): {metrics.get('annualized_return_pct'):.2f}%")
    print(f"Total return: {metrics.get('total_return_pct'):.2f}%")
    print(f"Sharpe: {metrics.get('sharpe_ratio'):.3f}   Sortino: {metrics.get('sortino_ratio'):.3f}   Calmar: {metrics.get('calmar_ratio'):.3f}")
    print(f"Max drawdown: {metrics.get('max_drawdown_pct'):.2f}%")
    print(f"Win rate: {metrics.get('win_rate_pct'):.2f}%   Profit factor: {metrics.get('profit_factor'):.3f}")
    print(f"Avg win: ${metrics.get('avg_win'):.2f}   Avg loss: ${metrics.get('avg_loss'):.2f}")
    print(f"Largest win: ${metrics.get('largest_win'):.2f}   Largest loss: ${metrics.get('largest_loss'):.2f}")
    print(f"Avg days in trade: {metrics.get('avg_days_in_trade'):.2f}")
    print(f"Positive months: {metrics.get('positive_months_pct'):.1f}%   Best month: {metrics.get('best_month_pct'):.2f}%   Worst month: {metrics.get('worst_month_pct'):.2f}%")
    print(f"\nAchieved SHORT delta (target 0.35): median={achieved_short.median():.4f} mean={achieved_short.mean():.4f} "
          f"std={achieved_short.std():.4f} min={achieved_short.min():.4f} max={achieved_short.max():.4f}")
    print(f"Achieved LONG  delta (target 0.19): median={achieved_long.median():.4f} mean={achieved_long.mean():.4f} "
          f"std={achieved_long.std():.4f} min={achieved_long.min():.4f} max={achieved_long.max():.4f}")
    # % of trades landing outside +/- 0.03 of the nominal target (i.e. meaningfully off-target)
    off_short = ((achieved_short - 0.35).abs() > 0.03).mean() * 100
    off_long = ((achieved_long - 0.19).abs() > 0.03).mean() * 100
    print(f"% trades with short delta >0.03 off target: {off_short:.1f}%")
    print(f"% trades with long  delta >0.03 off target: {off_long:.1f}%")

    return metrics, trades


if __name__ == "__main__":
    run(("2018-01-02", "2026-07-09"), 150000, "FULL 2018-2026 (daily cadence, fixed 1 contract, $150k)")
    run(("2008-01-01", "2009-12-31"), 150000, "GFC 2008-2009 (daily cadence, fixed 1 contract, $150k)",
        specific_file="SPY_synthetic_options_2008-01-01_2009-12-31.csv")
