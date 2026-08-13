#!/usr/bin/env python3
"""Is the daily-cadence CAGR an artifact of the reporting denominator? (2026-08-13)

With `position_sizing.method: fixed_contracts` the account value never gates entries, so the
strategy books an essentially FIXED dollar P&L stream regardless of `initial_capital`. If that is
true, then running the identical config at a different starting capital must produce identical
trades and identical DOLLAR P&L, with only the percentage metrics moving.

Runs the recommended structure (21 DTE / 0.35 short / $10 wing / PT 80 / SL 30 / exit 5 DTE) at
several capital bases and reports dollar vs percentage results side by side, plus the actual
defined risk in use (concurrent positions x max loss per contract).

Usage: opt_venv/bin/python diag_capital_denominator.py
"""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd, numpy as np
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

WINDOW = ("2018-01-02", "2026-07-09")
CAPITALS = [150000, 50000, 25000]
ENTRY = {"dte_target": 21, "short_delta": 0.35, "strike_width": 10}
EXIT = {"profit_target": 0.80, "stop_loss": 0.30, "dte_min": 5}


def run(capital, options_data, underlying):
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = capital
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1
    sc = cfg["strategies"]["bull_put_spread"]
    sc["entry"].pop("long_delta", None)
    sc["entry"].update(ENTRY)
    sc["entry"]["vix_min"], sc["entry"]["vix_max"] = 0, 999
    sc["exit"].update(EXIT)

    bt = OptopsyBacktester(cfg)
    res = bt.run_backtest(strategy=BullPutSpread(sc), options_data=options_data,
                          underlying_data=underlying, verbose=False)
    m = calculate_performance_metrics(res)
    tr, eq = res["trades"], res["equity_curve"]

    # dollar drawdown from the equity curve itself
    tv = eq["total_value"]
    dd_dollars = float((tv - tv.cummax()).min())

    # concurrent open positions per day -> the capital actually committed
    conc = np.nan
    peak_risk = np.nan
    if len(tr):
        ed = pd.to_datetime(tr["entry_date"]).dt.normalize()
        xd = pd.to_datetime(tr["exit_date"]).dt.normalize()
        days = pd.to_datetime(eq["date"]).dt.normalize()
        open_ct = np.array([((ed <= d) & (xd > d)).sum() for d in days])
        conc = open_ct.mean()
        width = (tr["leg1_strike"] - tr["leg2_strike"]).abs()
        maxloss = (width + tr["entry_price"]) * 100      # entry_price < 0 for a credit
        peak_risk = float(open_ct.max() * maxloss.median())
    return {
        "capital": capital, "trades": len(tr),
        "pnl_dollars": float(tv.iloc[-1] - capital),
        "cagr_pct": m.get("annualized_return_pct"),
        "total_return_pct": m.get("total_return_pct"),
        "sharpe": m.get("sharpe_ratio"),
        "max_dd_pct": m.get("max_drawdown_pct"), "max_dd_dollars": dd_dollars,
        "avg_concurrent": conc, "peak_defined_risk": peak_risk,
    }


def main():
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    print("Loading corrected (delta_band) 2018-2026 options data...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)

    rows = [run(c, options_data, underlying) for c in CAPITALS]
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print("\n=== identical strategy, different reporting denominator ===")
    print(df.round(2).to_string(index=False))
    out = "backtest_results/diag_capital_denominator.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
