#!/usr/bin/env python3
"""
Re-test every suspicion raised about the low-delta result, restricted to the 2018-2026 window
(the only part of this project's data with any real-quote grounding -- 2008-2017 has none).

The original low_delta_sweep.csv ran on the full 2008-2026 span and found 0.12Δ/0.08Δ as the
best structure in the whole investigation, with 0.15Δ a total failure. An era-split diagnostic
then showed 0.12Δ's edge was ~23x concentrated in the unvalidated 2008-2017 period ($524/trade)
vs the validated-ish 2018-2026 period ($23/trade, unremarkable). This script re-runs the SAME
grid on 2018-2026 only, and reports BOTH the whole-window metric AND a proper IS(2018-23)/OOS
(2023-26) split from the SAME continuous backtest (evaluate_oos_continuous methodology) --
so the delta question, the exit-parameter question, and out-of-sample validity are all answered
in one pass instead of three.

Usage: python compare_low_delta_validated.py
Output: backtest_results/low_delta_validated.csv
"""
import sys, os, copy, itertools
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import numpy as np
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.optimization.walk_forward import split_window, _optimizer_for_window
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

WINDOW = ("2018-01-02", "2026-07-09")

SHORT_DELTAS = [0.12, 0.15, 0.20]
LONG_DELTAS = [0.08, 0.10]
PROFIT_TARGETS = [0.60, 0.80]
STOP_LOSSES = [0.50, 0.80]
RISK_PCTS = [15, 20]


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

    combos = list(itertools.product(SHORT_DELTAS, LONG_DELTAS, PROFIT_TARGETS, STOP_LOSSES, RISK_PCTS))
    # skip the 0.20/0.08 combos (not part of the original suspicion, keep the grid focused)
    combos = [c for c in combos if not (c[0] == 0.20 and c[1] == 0.08)]

    print(f"Running {len(combos)} backtests ...")
    rows = []
    for i, (sd, ld, pt, sl, rp) in enumerate(combos, 1):
        params = {"dte": 30, "short_delta": sd, "long_delta": ld, "vix_min": 10, "vix_max": 35,
                  "profit_target": pt, "stop_loss": sl, "dte_min": 22}
        c = copy.deepcopy(cfg)
        c["position_sizing"]["max_risk_percent"] = rp

        opt = _optimizer_for_window(c, "vertical", BullPutSpread, options_data, underlying, WINDOW)
        try:
            res = opt._run_single_backtest(params, verbose=False, return_raw=True)
            eq = res["equity_curve"].copy()
            eq["date"] = pd.to_datetime(eq["date"])
            full = _slice_metrics(eq, eq["date"].min(), eq["date"].max() + pd.Timedelta(days=1))
            is_m = _slice_metrics(eq, eq["date"].min(), cut)
            oos_m = _slice_metrics(eq, cut, eq["date"].max() + pd.Timedelta(days=1))
            trades = res.get("trades")
            n_trades = len(trades) if trades is not None else 0
            row = {"short_delta": sd, "long_delta": ld, "profit_target": pt, "stop_loss": sl, "risk_pct": rp,
                   "full_sharpe": full["sharpe"], "full_return_pct": full["return_pct"], "full_max_dd_pct": full["max_dd_pct"],
                   "is_sharpe": is_m["sharpe"], "is_return_pct": is_m["return_pct"], "is_max_dd_pct": is_m["max_dd_pct"],
                   "oos_sharpe": oos_m["sharpe"], "oos_return_pct": oos_m["return_pct"], "oos_max_dd_pct": oos_m["max_dd_pct"],
                   "trades": n_trades}
            print(f"[{i}/{len(combos)}] sd={sd} ld={ld} pt={pt} sl={sl} risk={rp}%: "
                  f"full_Sharpe={row['full_sharpe']:.2f} IS={row['is_sharpe']:.2f} OOS={row['oos_sharpe']:.2f} "
                  f"trades={n_trades}", flush=True)
        except Exception as e:
            row = {"short_delta": sd, "long_delta": ld, "profit_target": pt, "stop_loss": sl, "risk_pct": rp,
                   "error": str(e)}
            print(f"[{i}/{len(combos)}] FAIL: {e}", flush=True)
        rows.append(row)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / "low_delta_validated.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
