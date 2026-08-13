#!/usr/bin/env python3
"""Is 0.12Δ's full-span edge concentrated in 2008-2017 (pre-real-data, unvalidated pricing)?
Same 3 structures, full 2008-2026 dataset, split trade P&L by era."""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

FULL_SPAN = ("2008-01-02", "2026-07-09")
with open("config/config.yaml") as f:
    cfg = yaml.safe_load(f)
cfg["synthetic_data"]["start_date"] = "2008-01-01"
cfg["synthetic_data"]["end_date"] = "2026-07-10"
cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = FULL_SPAN
cfg["position_sizing"]["max_risk_percent"] = 20
print("Loading full 2008-2026 data...")
options_data = load_sample_spy_options_data(config=cfg)
underlying = fetch_spy_data(*FULL_SPAN)

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
    trades = res["trades"].copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"])
    pre = trades[trades["entry_date"] < "2018-01-01"]
    post = trades[trades["entry_date"] >= "2018-01-01"]
    print(f"\n=== short_delta={sd} long_delta={ld} ===")
    print(f"  2008-2017 (unvalidated pricing): n={len(pre)}  mean_pnl=${pre['net_pnl'].mean():.2f}  "
          f"total_pnl=${pre['net_pnl'].sum():.0f}  win%={100*(pre['net_pnl']>0).mean():.1f}")
    print(f"  2018-2026 (validated-ish pricing): n={len(post)}  mean_pnl=${post['net_pnl'].mean():.2f}  "
          f"total_pnl=${post['net_pnl'].sum():.0f}  win%={100*(post['net_pnl']>0).mean():.1f}")
