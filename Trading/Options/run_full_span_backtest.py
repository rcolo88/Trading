#!/usr/bin/env python3
"""
Full continuous 2008-01-02..2026-07-09 backtest for the pre-registered finalists.

Answers the "what's the real CAGR/Sharpe/return over the whole span" question directly, rather
than stitching together the disjoint 2008-09 (GFC) and 2018-2026 windows this project tested
separately. Uses data/processed/SPY_synthetic_options_2008-01-01_2026-07-10.csv (built by
scripts_gen_2008_2026.py on the skew+spread+level-corrected generator).

CAVEAT (see synthetic_generator.py's vol-level docstring): no options data exists anywhere before
2021, so 2008-2020 pricing is a flat extrapolation of the 2022-2026 level fit, not validated
against real quotes. Treat 2008-2020-era numbers as best-effort.

Usage:
    python run_full_span_backtest.py
    python run_full_span_backtest.py --risk-pct=100 --capital=2000   # full-account-risk, $2k
    python run_full_span_backtest.py --risk-pct=100 --no-vix-ceiling # full span, no VIX gate
Output: backtest_results/finalists_full_span[_suffix].csv
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
from validate_finalists import FINALISTS, FIXED_ENTRY, FIXED_EXIT

FULL_SPAN = ("2008-01-02", "2026-07-09")


def base_config(capital: float = None) -> dict:
    with open("config/config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["start_date"] = "2008-01-01"
    cfg["synthetic_data"]["end_date"] = "2026-07-10"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = FULL_SPAN
    if capital is not None:
        cfg["backtest"]["initial_capital"] = capital
    return cfg


def main() -> int:
    risk_override = None
    if "--risk-pct" in " ".join(sys.argv):
        for a in sys.argv:
            if a.startswith("--risk-pct="):
                risk_override = float(a.split("=")[1])
    no_vix_ceiling = "--no-vix-ceiling" in sys.argv
    capital = None
    for a in sys.argv:
        if a.startswith("--capital="):
            capital = float(a.split("=")[1])

    suffix = ""
    if risk_override is not None:
        suffix += f"_risk{int(risk_override)}"
    if no_vix_ceiling:
        suffix += "_novix"
    if capital is not None:
        suffix += f"_cap{int(capital)}"

    cfg = base_config(capital=capital)
    print(f"Config: risk_override={risk_override} no_vix_ceiling={no_vix_ceiling} capital={capital}")
    print("Loading full 2008-2026 synthetic options data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    print(f"  {len(options_data):,} rows")
    underlying = fetch_spy_data(*FULL_SPAN)
    print(f"  {len(underlying)} underlying rows")

    rows = []
    for label, entry_overrides, risk_pct in FINALISTS:
        c = copy.deepcopy(cfg)
        strat_cfg = c["strategies"]["bull_put_spread"]
        strat_cfg["entry"]["dte_target"] = FIXED_ENTRY["dte"]
        strat_cfg["entry"]["vix_min"] = FIXED_ENTRY["vix_min"]
        strat_cfg["entry"]["vix_max"] = 999 if no_vix_ceiling else FIXED_ENTRY["vix_max"]
        strat_cfg["entry"].update(entry_overrides)
        strat_cfg["exit"].update(FIXED_EXIT)
        risk_pct = risk_override if risk_override is not None else risk_pct
        c["position_sizing"]["max_risk_percent"] = risk_pct

        bt = OptopsyBacktester(c)
        strategy = BullPutSpread(strat_cfg)
        print(f"\n--- {label}: {entry_overrides}, risk={risk_pct}% ---")
        try:
            res = bt.run_backtest(strategy=strategy, options_data=options_data,
                                   underlying_data=underlying, verbose=False)
            m = calculate_performance_metrics(res)
            row = {
                "label": label, "risk_pct": risk_pct, **entry_overrides,
                "cagr_pct": m.get("annualized_return_pct"), "sharpe": m.get("sharpe_ratio"),
                "sortino": m.get("sortino_ratio"), "max_dd_pct": m.get("max_drawdown_pct"),
                "calmar": m.get("calmar_ratio"), "total_return_pct": m.get("total_return_pct"),
                "win_rate_pct": m.get("win_rate_pct"), "profit_factor": m.get("profit_factor"),
                "trades": m.get("total_trades"),
            }
            print(f"  CAGR={row['cagr_pct']:.2f}%  Sharpe={row['sharpe']:.2f}  "
                  f"MaxDD={row['max_dd_pct']:.2f}%  TotalReturn={row['total_return_pct']:.1f}%  "
                  f"trades={row['trades']}")
        except Exception as e:
            row = {"label": label, "risk_pct": risk_pct, **entry_overrides, "error": str(e)}
            print(f"  FAIL: {e}")
        rows.append(row)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / f"finalists_full_span{suffix}.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
