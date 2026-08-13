#!/usr/bin/env python3
"""
Does a much-lower short delta (12-15) with wide exit parameters (pt/sl ~0.80) work? Neither the
short_delta grid (which stopped at 0.16) nor the exit-parameter sweep (which only tested 0.20Δ)
covered this combination -- a real, unexamined gap flagged directly by the user.

Grid: short_delta {0.12, 0.15} x long_delta {0.08, 0.10} x profit_target {0.60, 0.80} x
stop_loss {0.50, 0.80}, at 15% and 20% risk, full continuous 2008-2026 span, $20k.
Includes the already-established 0.20Δ/0.10Δ/pt0.6/sl0.5/20%risk row for direct comparison.

Usage: python compare_low_delta.py
Output: backtest_results/low_delta_sweep.csv
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

FULL_SPAN = ("2008-01-02", "2026-07-09")

SHORT_DELTAS = [0.12, 0.15]
LONG_DELTAS = [0.08, 0.10]
PROFIT_TARGETS = [0.60, 0.80]
STOP_LOSSES = [0.50, 0.80]
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

    combos = list(itertools.product(SHORT_DELTAS, LONG_DELTAS, PROFIT_TARGETS, STOP_LOSSES, RISK_PCTS))
    # comparison anchor: the already-established 0.20/0.10/pt0.6/sl0.5 at each risk pct
    for rp in RISK_PCTS:
        combos.append((0.20, 0.10, 0.60, 0.50, rp))

    print(f"Running {len(combos)} backtests ...")
    rows = []
    for i, (sd, ld, pt, sl, rp) in enumerate(combos, 1):
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"]["dte_target"] = 30
        strat_cfg["entry"]["vix_min"] = 10
        strat_cfg["entry"]["vix_max"] = 35
        strat_cfg["entry"]["short_delta"] = sd
        strat_cfg["entry"]["long_delta"] = ld
        strat_cfg["entry"].pop("strike_width", None)
        strat_cfg["exit"]["profit_target"] = pt
        strat_cfg["exit"]["stop_loss"] = sl
        strat_cfg["exit"]["dte_min"] = 22
        c["position_sizing"]["max_risk_percent"] = rp

        bt = OptopsyBacktester(c)
        strategy = BullPutSpread(strat_cfg)
        try:
            res = bt.run_backtest(strategy=strategy, options_data=options_data,
                                   underlying_data=underlying, verbose=False)
            m = calculate_performance_metrics(res)
            row = {"short_delta": sd, "long_delta": ld, "profit_target": pt, "stop_loss": sl,
                   "risk_pct": rp, "cagr_pct": m.get("annualized_return_pct"),
                   "sharpe": m.get("sharpe_ratio"), "max_dd_pct": m.get("max_drawdown_pct"),
                   "calmar": m.get("calmar_ratio"), "trades": m.get("total_trades"),
                   "win_rate_pct": m.get("win_rate_pct")}
            print(f"[{i}/{len(combos)}] sd={sd} ld={ld} pt={pt} sl={sl} risk={rp}%: "
                  f"Sharpe={row['sharpe']:.2f} CAGR={row['cagr_pct']:.1f}% "
                  f"DD={row['max_dd_pct']:.1f}% trades={row['trades']}", flush=True)
        except Exception as e:
            row = {"short_delta": sd, "long_delta": ld, "profit_target": pt, "stop_loss": sl,
                   "risk_pct": rp, "error": str(e)}
            print(f"[{i}/{len(combos)}] FAIL: {e}", flush=True)
        rows.append(row)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / "low_delta_sweep.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
