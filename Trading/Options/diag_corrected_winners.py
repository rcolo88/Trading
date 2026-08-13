#!/usr/bin/env python3
"""Phase 2 diagnostic (2026-08-11): re-run the published daily-cadence winners -- plus targeted
low-delta spot-checks -- on the CORRECTED data (bounded skew-tail extrapolation + $1 vol-adaptive
delta-band strike grid) to isolate what the pricing fix alone changed, before any re-optimization.

Candidates:
  delta_winner : 24 DTE / short 0.35 / long 0.19 (published primary recommendation)
  width_winner : 24 DTE / short 0.31 / $10 wide   (published alternative)
  low_delta_20_10 : 24 DTE / short 0.20 / long 0.10 (live-trading-like, delta wing)
  low_delta_20_w5 : 24 DTE / short 0.20 / $5 wide
  low_delta_20_w10: 24 DTE / short 0.20 / $10 wide
The low-delta spot-checks directly test DAILY_CADENCE_STRATEGY.md caveat 4: live trading reportedly
showed 20Delta outperforming 30Delta, but every ~20Delta combination came back negative Sharpe on
the OLD (unbounded-skew, $5-grid) data. If that was a pricing artifact (the long/protective wing
being overpriced specifically via the unbounded skew extrapolation), corrected pricing should
narrow or reverse the gap.

Usage: opt_venv/bin/python diag_corrected_winners.py
"""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd, numpy as np
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics
from src.analysis import regime

CANDIDATES = {
    "delta_winner":    {"dte_target": 24, "short_delta": 0.35, "long_delta": 0.19},
    "width_winner":    {"dte_target": 24, "short_delta": 0.31, "strike_width": 10},
    "low_delta_20_10": {"dte_target": 24, "short_delta": 0.20, "long_delta": 0.10},
    "low_delta_20_w5": {"dte_target": 24, "short_delta": 0.20, "strike_width": 5},
    "low_delta_20_w10":{"dte_target": 24, "short_delta": 0.20, "strike_width": 10},
}
SHARED_EXIT = {"profit_target": 0.9, "stop_loss": 0.3, "dte_min": 5}
WINDOW = ("2018-01-02", "2026-07-09")
CAPITAL = 150000


def base_config():
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = CAPITAL
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1
    return cfg


def run_one(label, entry_params, options_data, underlying, cfg_template):
    cfg = copy.deepcopy(cfg_template)
    strat_cfg = cfg["strategies"]["bull_put_spread"]
    strat_cfg["entry"].pop("strike_width", None)
    strat_cfg["entry"].pop("long_delta", None)
    strat_cfg["entry"].update(entry_params)
    strat_cfg["entry"]["vix_min"], strat_cfg["entry"]["vix_max"] = 0, 999
    strat_cfg["exit"].update(SHARED_EXIT)

    bt = OptopsyBacktester(cfg)
    strategy = BullPutSpread(strat_cfg)
    print(f"\n{'='*70}\n{label}: {entry_params}\n{'='*70}")
    res = bt.run_backtest(strategy=strategy, options_data=options_data, underlying_data=underlying, verbose=False)
    m = calculate_performance_metrics(res)
    trades = res["trades"].copy()

    print(f"Trades: {len(trades)}   CAGR: {m.get('annualized_return_pct'):.2f}%   "
          f"Total return: {m.get('total_return_pct'):.2f}%")
    print(f"Sharpe: {m.get('sharpe_ratio'):.3f}   Sortino: {m.get('sortino_ratio'):.3f}   "
          f"Calmar: {m.get('calmar_ratio'):.3f}   MaxDD: {m.get('max_drawdown_pct'):.2f}%")
    print(f"Win rate: {m.get('win_rate_pct'):.2f}%   Profit factor: {m.get('profit_factor'):.3f}   "
          f"Avg days in trade: {m.get('avg_days_in_trade'):.2f}")

    if len(trades):
        short_target = entry_params.get("short_delta")
        achieved_short = trades["leg1_delta"].abs()
        off = ((achieved_short - short_target).abs() > 0.03).mean() * 100
        print(f"Achieved SHORT delta (target {short_target}): median={achieved_short.median():.4f} "
              f"std={achieved_short.std():.4f} | %%>0.03 off target: {off:.1f}%")
        if "long_delta" in entry_params:
            long_target = entry_params["long_delta"]
            achieved_long = trades["leg2_delta"].abs()
            off_l = ((achieved_long - long_target).abs() > 0.03).mean() * 100
            print(f"Achieved LONG  delta (target {long_target}): median={achieved_long.median():.4f} "
                  f"std={achieved_long.std():.4f} | %%>0.03 off target: {off_l:.1f}%")

    rg = regime.regime_conditional_metrics(res["equity_curve"], trades)
    print(f"Calm   Sharpe: {rg['calm_sharpe_ratio']:.3f}  maxDD: {rg['calm_max_drawdown_pct']:.2f}%  "
          f"trades: {rg['calm_trades']}  win%: {rg['calm_win_rate_pct']:.1f}")
    print(f"Stress Sharpe: {rg['stress_sharpe_ratio']:.3f}  maxDD: {rg['stress_max_drawdown_pct']:.2f}%  "
          f"trades: {rg['stress_trades']}  win%: {rg['stress_win_rate_pct']:.1f}")

    row = {"label": label, **entry_params, **SHARED_EXIT,
           "trades": len(trades), "cagr_pct": m.get("annualized_return_pct"),
           "total_return_pct": m.get("total_return_pct"), "sharpe": m.get("sharpe_ratio"),
           "sortino": m.get("sortino_ratio"), "calmar": m.get("calmar_ratio"),
           "max_dd_pct": m.get("max_drawdown_pct"), "win_rate_pct": m.get("win_rate_pct"),
           "profit_factor": m.get("profit_factor"), **rg}
    return row


def main():
    cfg = base_config()
    print("Loading corrected (delta_band) 2018-2026 options data...")
    options_data = load_sample_spy_options_data(config=cfg)
    print(f"  {len(options_data):,} rows")
    underlying = fetch_spy_data(*WINDOW)

    rows = [run_one(label, params, options_data, underlying, cfg) for label, params in CANDIDATES.items()]
    df = pd.DataFrame(rows)
    from pathlib import Path
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / "diag_corrected_winners.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df[["label", "trades", "sharpe", "total_return_pct", "max_dd_pct", "win_rate_pct"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
