#!/usr/bin/env python3
"""Anatomy of the recommended structure's max drawdown (2026-08-13).

Peak DEFINED risk is only ~$13.2k (about 10 concurrent positions x $777 max loss), yet the worst
peak-to-trough equity decline is ~$22.8k. That is not a contradiction -- a drawdown accumulates
SEQUENTIALLY across overlapping cohorts of trades over weeks, it is not a simultaneous max-loss
event. This script locates the actual drawdown window and shows what happened inside it.

Config: 21 DTE / 0.35 short / $10 wing / PT 80% / SL 30% / exit 5 DTE, $150k, 1 contract/day.

Usage: opt_venv/bin/python diag_drawdown_anatomy.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, pandas as pd, numpy as np
from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

WINDOW = ("2018-01-02", "2026-07-09")
CAPITAL = 150000


def main():
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = CAPITAL
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1
    sc = cfg["strategies"]["bull_put_spread"]
    sc["entry"].pop("long_delta", None)
    sc["entry"].update({"dte_target": 21, "short_delta": 0.35, "strike_width": 10})
    sc["entry"]["vix_min"], sc["entry"]["vix_max"] = 0, 999
    sc["exit"].update({"profit_target": 0.80, "stop_loss": 0.30, "dte_min": 5})

    print("Loading corrected (delta_band) 2018-2026 options data...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)

    res = OptopsyBacktester(cfg).run_backtest(
        strategy=BullPutSpread(sc), options_data=options_data,
        underlying_data=underlying, verbose=False)
    eq, tr = res["equity_curve"].copy(), res["trades"].copy()
    eq["date"] = pd.to_datetime(eq["date"])
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["exit_date"] = pd.to_datetime(tr["exit_date"])

    tv = eq["total_value"]
    peak = tv.cummax()
    dd = tv - peak
    i_tr = int(dd.idxmin())
    trough_date, trough_val = eq["date"].iloc[i_tr], tv.iloc[i_tr]
    i_pk = int(tv.iloc[:i_tr + 1].idxmax())
    peak_date, peak_val = eq["date"].iloc[i_pk], tv.iloc[i_pk]

    rec = eq[(eq.index > i_tr) & (tv >= peak_val)]
    rec_date = rec["date"].iloc[0] if len(rec) else None

    print("\n=== MAX DRAWDOWN WINDOW ===")
    print(f"  peak    {peak_date.date()}  ${peak_val:,.0f}")
    print(f"  trough  {trough_date.date()}  ${trough_val:,.0f}")
    print(f"  decline ${trough_val - peak_val:,.0f}  ({(trough_val/peak_val - 1)*100:.2f}%)")
    print(f"  length  {(trough_date - peak_date).days} calendar days")
    print(f"  recovered {rec_date.date() if rec_date is not None else 'NOT within the window'}"
          + (f"  ({(rec_date - trough_date).days} days to recover)" if rec_date is not None else ""))

    win = tr[(tr["exit_date"] >= peak_date) & (tr["exit_date"] <= trough_date)]
    print(f"\n=== TRADES CLOSED INSIDE THE DRAWDOWN ({len(win)}) ===")
    if len(win):
        losers = win[win["net_pnl"] < 0]
        print(f"  net P&L         ${win['net_pnl'].sum():,.0f}")
        print(f"  winners {len(win) - len(losers)} (${win[win['net_pnl']>=0]['net_pnl'].sum():,.0f})"
              f"   losers {len(losers)} (${losers['net_pnl'].sum():,.0f})")
        print(f"  win rate inside {100*(len(win)-len(losers))/len(win):.1f}%  "
              f"(vs 73.7% overall)")
        print(f"  avg loss inside ${losers['net_pnl'].mean():,.0f}   worst ${losers['net_pnl'].min():,.0f}")
        print("\n  exit reasons:")
        print(win["exit_reason"].str.split(":").str[0].value_counts()
              .to_frame("n").assign(pct=lambda d: (d.n/len(win)*100).round(1)).to_string())
        print("\n  worst 8 trades in the window:")
        print(win.nsmallest(8, "net_pnl")[
            ["entry_date", "exit_date", "net_pnl", "days_in_trade"]].to_string(index=False))
        # how much of the loss is concentrated
        srt = losers["net_pnl"].sort_values()
        print(f"\n  worst 10 losers = ${srt.head(10).sum():,.0f} "
              f"({srt.head(10).sum()/losers['net_pnl'].sum()*100:.0f}% of all losses in window)")

    # per-year dollar P&L, for context on where the strategy makes/loses money
    tr["year"] = tr["exit_date"].dt.year
    print("\n=== dollar P&L by year ===")
    yr = tr.groupby("year")["net_pnl"].agg(["count", "sum"]).round(0)
    yr["win_rate"] = tr.groupby("year")["net_pnl"].apply(lambda s: (s >= 0).mean()*100).round(1)
    print(yr.to_string())


if __name__ == "__main__":
    main()
