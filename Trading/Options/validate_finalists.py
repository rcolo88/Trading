#!/usr/bin/env python3
"""
Phase 3 validation: walk-forward OOS for a short, PRE-REGISTERED list of finalists.

The full 140-trial grid (compare_width_frontier.py -> backtest_results/width_frontier_full.csv)
failed its own deflated-Sharpe check (DSR=0.042 on the grid-search winner) -- picking a NEW
"best of 140" finalist here would just repeat that overfitting. Instead this validates a short,
motivated list fixed BEFORE looking at OOS results:
    1. user_w5   -- the user's original ask: 0.20 delta short, $5 fixed wide, moderate risk
    2. user_w10  -- the user's likely fallback: 0.20 delta short, $10 fixed wide
    3. prior_d08 -- this project's previously-"adopted" config: 0.24 delta short, 0.08 delta long
    4. grid_w10  -- the full-grid's nominal top CAGR/Sharpe: 0.30 delta short, $10 wide, 30% risk
    5. grid_d08  -- the full-grid's best Calmar/lowest-DD-among-real-trade-count row: 0.30/0.08

Each is scored via evaluate_oos_continuous: ONE continuous backtest over 2018-01-02..2026-07-09,
IS = first 70%, OOS = last 30% (the honest walk-forward slice, not an isolated re-fit).

Usage: python validate_finalists.py
Output: backtest_results/finalists_walkforward.csv
"""
import sys, os, copy
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd

import numpy as np

from src.strategies.vertical_spreads import BullPutSpread
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.walk_forward import split_window, _optimizer_for_window
from src.analysis.overfitting import summarize_overfitting


def _slice_metrics(eq: pd.DataFrame, lo, hi) -> dict:
    """Sharpe/return/maxDD for one date slice of a continuous equity curve (rf=2%, matches engine)."""
    seg = eq[(eq["date"] >= lo) & (eq["date"] < hi)].reset_index(drop=True)
    if len(seg) < 3:
        return {"sharpe": float("nan"), "return_pct": float("nan"), "max_dd_pct": float("nan"), "n_days": len(seg)}
    rets = seg["total_value"].pct_change().dropna()
    excess = rets - 0.02 / 252.0
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else float("nan")
    start_val, end_val = float(seg["total_value"].iloc[0]), float(seg["total_value"].iloc[-1])
    total_ret = (end_val - start_val) / start_val * 100.0 if start_val else float("nan")
    cummax = seg["total_value"].cummax()
    max_dd = float(((seg["total_value"] - cummax) / cummax).min() * 100.0)
    return {"sharpe": sharpe, "return_pct": total_ret, "max_dd_pct": max_dd, "n_days": len(seg)}


def evaluate_is_oos(base_config, strategy_type, strategy_class, options_data, underlying_data,
                     full_window, oos_start, params) -> dict:
    """IS and OOS metrics from ONE continuous run (see evaluate_oos_continuous's docstring for why
    a continuous run, not an isolated OOS-only backtest, is the honest way to score this)."""
    opt = _optimizer_for_window(base_config, strategy_type, strategy_class,
                                 options_data, underlying_data, full_window)
    res = opt._run_single_backtest(params, verbose=False, return_raw=True)
    eq = res["equity_curve"].copy()
    eq["date"] = pd.to_datetime(eq["date"])
    cut = pd.to_datetime(oos_start)
    is_m = _slice_metrics(eq, eq["date"].min(), cut)
    oos_m = _slice_metrics(eq, cut, eq["date"].max() + pd.Timedelta(days=1))

    trades = res.get("trades")
    n_is = n_oos = 0
    if trades is not None and len(trades) and "entry_date" in trades.columns:
        td = trades.copy()
        td["entry_date"] = pd.to_datetime(td["entry_date"])
        n_is = int((td["entry_date"] < cut).sum())
        n_oos = int((td["entry_date"] >= cut).sum())

    is_sh, oos_sh = is_m["sharpe"], oos_m["sharpe"]
    if np.isnan(is_sh) or np.isnan(oos_sh):
        verdict = "insufficient data"
    elif oos_sh > 1.0 and oos_sh > 0.5 * is_sh:
        verdict = "healthy"
    elif oos_sh > 0.5:
        verdict = "degraded"
    else:
        verdict = "collapse"

    return {
        "is_sharpe": is_sh, "is_return_pct": is_m["return_pct"], "is_max_dd_pct": is_m["max_dd_pct"], "is_trades": n_is,
        "oos_sharpe": oos_sh, "oos_return_pct": oos_m["return_pct"], "oos_max_dd_pct": oos_m["max_dd_pct"], "oos_trades": n_oos,
        "verdict": verdict,
    }

FULL_WINDOW = ("2018-01-02", "2026-07-09")

FIXED_ENTRY = {"dte": 30, "vix_min": 10, "vix_max": 35}
FIXED_EXIT = {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}

FINALISTS = [
    # (label, entry_overrides, risk_pct)
    ("user_w5",   {"short_delta": 0.20, "strike_width": 5},  15),
    ("user_w10",  {"short_delta": 0.20, "strike_width": 10}, 15),
    ("user_d08",  {"short_delta": 0.20, "long_delta": 0.08}, 20),
    ("user_d10",  {"short_delta": 0.20, "long_delta": 0.10}, 20),
    ("prior_d08", {"short_delta": 0.24, "long_delta": 0.08}, 20),
    ("prior_d10", {"short_delta": 0.24, "long_delta": 0.10}, 20),
    ("grid_w10",  {"short_delta": 0.30, "strike_width": 10}, 30),
    ("grid_d08",  {"short_delta": 0.30, "long_delta": 0.08}, 15),
    ("grid_d10",  {"short_delta": 0.30, "long_delta": 0.10}, 15),
]


def base_config() -> dict:
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)


def main() -> int:
    cfg = base_config()
    print("Loading synthetic options data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    print(f"  {len(options_data):,} rows")
    underlying = fetch_spy_data(*FULL_WINDOW)
    print(f"  {len(underlying)} underlying rows")

    is_window, oos_window = split_window(*FULL_WINDOW, oos_fraction=0.30)
    print(f"IS window: {is_window}   OOS window: {oos_window}")

    rows = []
    for label, entry_overrides, risk_pct in FINALISTS:
        params = dict(FIXED_ENTRY)
        params.update(entry_overrides)
        params.update(FIXED_EXIT)

        c = copy.deepcopy(cfg)
        c["position_sizing"]["max_risk_percent"] = risk_pct

        print(f"\n--- {label}: {entry_overrides}, risk={risk_pct}% ---")
        res = evaluate_is_oos(
            base_config=c,
            strategy_type="vertical",
            strategy_class=BullPutSpread,
            options_data=options_data,
            underlying_data=underlying,
            full_window=FULL_WINDOW,
            oos_start=oos_window[0],
            params=params,
        )
        res["label"] = label
        res["risk_pct"] = risk_pct
        res.update(entry_overrides)
        rows.append(res)
        print(f"  IS  Sharpe={res['is_sharpe']:.2f}  return={res['is_return_pct']:.1f}%  "
              f"DD={res['is_max_dd_pct']:.1f}%  trades={res['is_trades']}")
        print(f"  OOS Sharpe={res['oos_sharpe']:.2f}  return={res['oos_return_pct']:.1f}%  "
              f"DD={res['oos_max_dd_pct']:.1f}%  trades={res['oos_trades']}  -> {res['verdict']}")

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    out = Path("backtest_results") / "finalists_walkforward.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
