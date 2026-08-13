#!/usr/bin/env python3
"""Diagnostic: is the 0.15Δ underperformance a strike-grid quantization artifact? Compare the
ACTUAL achieved short-leg delta (leg1_delta) vs the 0.12/0.15/0.20 targets, plus avg width/credit,
on the main 2018-2026 dataset (fast) at pt=0.8/sl=0.8/dte_min=22, 20% risk."""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

WINDOW = ("2018-01-02", "2026-07-09")
with open("config/config.yaml") as f:
    cfg = yaml.safe_load(f)
cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
cfg["position_sizing"]["max_risk_percent"] = 20
print("Loading...")
options_data = load_sample_spy_options_data(config=cfg)
underlying = fetch_spy_data(*WINDOW)

for sd, ld in [(0.12, 0.08), (0.15, 0.08), (0.20, 0.10)]:
    c = copy.deepcopy(cfg)
    strat_cfg = c["strategies"]["bull_put_spread"]
    strat_cfg["entry"]["dte_target"] = 30
    strat_cfg["entry"]["vix_min"] = 10
    strat_cfg["entry"]["vix_max"] = 35
    strat_cfg["entry"]["short_delta"] = sd
    strat_cfg["entry"]["long_delta"] = ld
    strat_cfg["entry"].pop("strike_width", None)
    strat_cfg["exit"]["profit_target"] = 0.80
    strat_cfg["exit"]["stop_loss"] = 0.80
    strat_cfg["exit"]["dte_min"] = 22
    bt = OptopsyBacktester(c)
    strategy = BullPutSpread(strat_cfg)
    res = bt.run_backtest(strategy=strategy, options_data=options_data, underlying_data=underlying, verbose=False)
    trades = res["trades"]
    width = (trades["leg1_strike"] - trades["leg2_strike"]).abs()
    credit = -trades["entry_price"]
    achieved_short_delta = trades["leg1_delta"].abs()
    achieved_long_delta = trades["leg2_delta"].abs()
    print(f"\n=== short_delta target={sd} long_delta target={ld} ===")
    print(f"  n_trades={len(trades)}  avg_width=${width.mean():.2f}  avg_credit=${credit.mean():.2f}")
    print(f"  achieved short delta: median={achieved_short_delta.median():.4f} mean={achieved_short_delta.mean():.4f} std={achieved_short_delta.std():.4f}")
    print(f"  achieved long  delta: median={achieved_long_delta.median():.4f} mean={achieved_long_delta.mean():.4f} std={achieved_long_delta.std():.4f}")
    print(f"  net_pnl: mean=${trades['net_pnl'].mean():.2f}  win_rate={100*(trades['net_pnl']>0).mean():.1f}%")
    print(f"  credit/width ratio (efficiency): {(credit/width).mean():.4f}")
