#!/usr/bin/env python3
"""Gate (vix_max=35) vs no-gate (vix_max=999) on the FULL IS/OOS walk-forward window
(2018-01-02 .. 2026-07-09), for the recommended 30d/10d structure, 15% risk.
Reuses the exact IS/OOS split + metrics methodology as compare_low_delta_validated.py."""
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import numpy as np
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.optimization.walk_forward import split_window, _optimizer_for_window
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

WINDOW = ("2018-01-02", "2026-07-09")


def base_config():
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)


def _slice_metrics(eq: pd.DataFrame, lo, hi) -> dict:
    seg = eq[(eq["date"] >= lo) & (eq["date"] < hi)].reset_index(drop=True)
    if len(seg) < 3:
        return {"sharpe": float("nan"), "return_pct": float("nan"), "max_dd_pct": float("nan")}
    rets = seg["total_value"].pct_change().dropna()
    excess = rets - 0.02 / 252.0
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else float("nan")
    start_val, end_val = float(seg["total_value"].iloc[0]), float(seg["total_value"].iloc[-1])
    total_ret = (end_val - start_val) / start_val * 100.0 if start_val else float("nan")
    cummax = seg["total_value"].cummax()
    max_dd = float(((seg["total_value"] - cummax) / cummax).min() * 100.0)
    return {"sharpe": sharpe, "return_pct": total_ret, "max_dd_pct": max_dd}


def main():
    cfg = base_config()
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    print("Loading 2018-2026 data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    underlying = fetch_spy_data(*WINDOW)
    print(f"  {len(options_data):,} rows")

    is_window, oos_window = split_window(*WINDOW, oos_fraction=0.30)
    cut = pd.to_datetime(oos_window[0])
    print(f"IS: {is_window}  OOS: {oos_window}")

    rows = []
    for label, vix_max in [("gate (vix_max=35)", 35), ("no_gate (vix_max=999)", 999)]:
        params = {"dte": 30, "short_delta": 0.30, "long_delta": 0.10, "vix_min": 10, "vix_max": vix_max,
                  "profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}
        c = copy.deepcopy(cfg)
        c["position_sizing"]["max_risk_percent"] = 15

        opt = _optimizer_for_window(c, "vertical", BullPutSpread, options_data, underlying, WINDOW)
        res = opt._run_single_backtest(params, verbose=False, return_raw=True)
        eq = res["equity_curve"].copy()
        eq["date"] = pd.to_datetime(eq["date"])
        full = _slice_metrics(eq, eq["date"].min(), eq["date"].max() + pd.Timedelta(days=1))
        is_m = _slice_metrics(eq, eq["date"].min(), cut)
        oos_m = _slice_metrics(eq, cut, eq["date"].max() + pd.Timedelta(days=1))
        trades = res.get("trades")
        n_trades = len(trades) if trades is not None else 0
        is_trades = len(trades[trades["entry_date"] < cut]) if trades is not None else 0
        oos_trades = n_trades - is_trades

        # CAGR
        years = (eq["date"].max() - eq["date"].min()).days / 365.25
        start_val, end_val = float(eq["total_value"].iloc[0]), float(eq["total_value"].iloc[-1])
        cagr = ((end_val / start_val) ** (1 / years) - 1) * 100.0 if start_val and years > 0 else float("nan")

        row = {"scenario": label, "trades": n_trades, "is_trades": is_trades, "oos_trades": oos_trades,
               "cagr_pct": cagr,
               "full_sharpe": full["sharpe"], "full_return_pct": full["return_pct"], "full_max_dd_pct": full["max_dd_pct"],
               "is_sharpe": is_m["sharpe"], "is_return_pct": is_m["return_pct"], "is_max_dd_pct": is_m["max_dd_pct"],
               "oos_sharpe": oos_m["sharpe"], "oos_return_pct": oos_m["return_pct"], "oos_max_dd_pct": oos_m["max_dd_pct"]}
        rows.append(row)
        print(f"\n[{label}] trades={n_trades} (IS={is_trades} OOS={oos_trades}) CAGR={cagr:.2f}%")
        print(f"  full: Sharpe={full['sharpe']:.3f} return={full['return_pct']:.2f}% maxDD={full['max_dd_pct']:.2f}%")
        print(f"  IS:   Sharpe={is_m['sharpe']:.3f} return={is_m['return_pct']:.2f}% maxDD={is_m['max_dd_pct']:.2f}%")
        print(f"  OOS:  Sharpe={oos_m['sharpe']:.3f} return={oos_m['return_pct']:.2f}% maxDD={oos_m['max_dd_pct']:.2f}%")

    df = pd.DataFrame(rows)
    out = "backtest_results/vix_gate_walkforward.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
