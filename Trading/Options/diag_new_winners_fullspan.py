#!/usr/bin/env python3
"""Phase 5 prep (2026-08-11): full 2018-2026 combined metrics for the two NEW walk-forward
winners found by the corrected-data re-optimization, matching DAILY_CADENCE_STRATEGY.md's
existing full-span table format.

  delta_new : dte=21, short=0.35, long=0.15, PT=0.8, SL=0.3, dte_min=5
  width_new : dte=24, short=0.31, strike_width=20, PT=0.8, SL=0.3, dte_min=5
"""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics
from src.analysis import regime

CANDIDATES = {
    "delta_new": {"dte_target": 21, "short_delta": 0.35, "long_delta": 0.15,
                  "profit_target": 0.8, "stop_loss": 0.3, "dte_min": 5},
    "width_new": {"dte_target": 24, "short_delta": 0.31, "strike_width": 20,
                  "profit_target": 0.8, "stop_loss": 0.3, "dte_min": 5},
}
WINDOW = ("2018-01-02", "2026-07-09")


def base_config():
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = 150000
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1
    return cfg


def main():
    cfg = base_config()
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)

    for label, params in CANDIDATES.items():
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"].pop("strike_width", None)
        strat_cfg["entry"].pop("long_delta", None)
        strat_cfg["entry"].update({k: v for k, v in params.items() if k not in ("profit_target", "stop_loss", "dte_min")})
        strat_cfg["entry"]["vix_min"], strat_cfg["entry"]["vix_max"] = 0, 999
        strat_cfg["exit"]["profit_target"] = params["profit_target"]
        strat_cfg["exit"]["stop_loss"] = params["stop_loss"]
        strat_cfg["exit"]["dte_min"] = params["dte_min"]

        bt = OptopsyBacktester(c)
        strategy = BullPutSpread(strat_cfg)
        res = bt.run_backtest(strategy=strategy, options_data=options_data, underlying_data=underlying, verbose=False)
        m = calculate_performance_metrics(res)
        trades = res["trades"]

        print(f"\n{'='*70}\n{label}: {params}\n{'='*70}")
        print(f"Trades: {len(trades)}")
        print(f"CAGR: {m.get('annualized_return_pct'):.2f}%   Total return: {m.get('total_return_pct'):.2f}%")
        print(f"Sharpe/Sortino/Calmar: {m.get('sharpe_ratio'):.3f} / {m.get('sortino_ratio'):.3f} / {m.get('calmar_ratio'):.3f}")
        print(f"Max drawdown: {m.get('max_drawdown_pct'):.2f}%")
        print(f"Win rate/Profit factor: {m.get('win_rate_pct'):.2f}% / {m.get('profit_factor'):.3f}")
        print(f"Avg win/loss: ${m.get('avg_win'):.2f} / ${m.get('avg_loss'):.2f}")
        print(f"Largest win/loss: ${m.get('largest_win'):.2f} / ${m.get('largest_loss'):.2f}")
        print(f"Avg days in trade: {m.get('avg_days_in_trade'):.2f}")
        print(f"Positive months: {m.get('positive_months_pct'):.1f}%  Best: {m.get('best_month_pct'):.2f}%  Worst: {m.get('worst_month_pct'):.2f}%")

        rg = regime.regime_conditional_metrics(res["equity_curve"], trades)
        print(f"Calm   Sharpe: {rg['calm_sharpe_ratio']:.3f}  maxDD: {rg['calm_max_drawdown_pct']:.2f}%  trades: {rg['calm_trades']}")
        print(f"Stress Sharpe: {rg['stress_sharpe_ratio']:.3f}  maxDD: {rg['stress_max_drawdown_pct']:.2f}%  trades: {rg['stress_trades']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
