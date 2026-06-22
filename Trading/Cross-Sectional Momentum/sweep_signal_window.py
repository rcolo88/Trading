#!/usr/bin/env python3
"""sweep_signal_window — empirical test of the momentum formation horizon.

Robert's hypothesis: the 12-month (252-day) residual-momentum window is too slow
for current market dynamics; a shorter horizon may react better.  Whether that is
TRUE is an empirical question, not an assertion — and the honest way to answer it
is to run the *same* walk-forward backtest at several horizons and read off the
out-of-sample evidence, deflated for the fact that we tried multiple configs.

`signal.window` drives the whole residual signal at once (rolling CAPM beta, the
residual sum, and idio-vol — see csm/signals.py::residual_momentum), so changing
it changes the strategy itself.  Because the live `ideas` command MUST score the
identical signal the backtest validates, whatever wins here is adopted for BOTH.

For each window we report:
  * OOS Sharpe  — annualised, on that config's own realisable OOS (warmup trimmed)
  * DSR         — Deflated Sharpe of the best config, penalised for N=3 trials
  * PBO         — Probability of Backtest Overfitting (CSCV) across the 3 configs

Run:  python sweep_signal_window.py
This is a read-only diagnostic; it writes nothing and trains no model.
"""
from __future__ import annotations

import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

import csmom
from csm import data as data_mod
from csm import universe as univ_mod
from csm import signals as sig_mod
from csm import portfolio as port_mod
from csm import validation as val_mod

WINDOWS = [126, 189, 252]   # 6mo / 9mo / 12mo formation horizons
OOS_FRAC = 0.30

_HERE = Path(__file__).resolve().parent


def main() -> None:
    cfg = csmom.load_config()
    cache_dir = _HERE / cfg["data"]["cache_dir"]

    pit_df = pd.read_parquet(cache_dir / "universe_pit.parquet")
    ever   = univ_mod.get_all_ever_members(pit_df)

    # Load the price panel ONCE; only signal.window changes across the sweep.
    bt_start, bt_end = csmom._backtest_window(cfg)
    print(f"Backtest window: {bt_start} → {bt_end}  (auto-anchored)\n")
    prices = data_mod.load_price_panel(
        tickers=ever, start=bt_start, end=bt_end, cache_dir=cache_dir,
    )

    # CONTINUOUS OOS: compute each signal on the FULL panel (as live trading and
    # `ideas` do — the signal at every date uses all prior history), then score the
    # SAME OOS dates for all windows. This removes the walk_forward artifact where a
    # longer window re-burns its warmup inside the OOS slice and is then measured on a
    # shorter, more recent, non-comparable period.
    n         = len(prices.index)
    is_end    = prices.index[int(n * (1 - OOS_FRAC)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)
    bench     = prices["SPY"].pct_change().fillna(0.0).loc[oos_start:]
    print(f"Common OOS period (identical for all windows): "
          f"{oos_start.date()} → {prices.index[-1].date()}  "
          f"({len(prices.loc[oos_start:])} days)\n")

    rows = []
    net_rets: dict[int, pd.Series] = {}
    for w in WINDOWS:
        cfg_w   = {**cfg, "signal": {**cfg.get("signal", {}), "window": w}}
        signals = sig_mod.primary_signal(prices, cfg_w)            # full-history signal
        pos     = port_mod.build_positions(signals, prices, cfg_w, pit_df=pit_df)
        net_ret = port_mod.portfolio_returns(pos, prices, cfg_w)
        nr      = net_ret.loc[oos_start:]                          # slice identical OOS
        m       = val_mod.compute_metrics(nr, bench)
        net_rets[w] = nr
        rows.append({
            "window":     w,
            "horizon":    f"{round(w/21)}mo",
            "oos_days":   m["n_days"],
            "sharpe":     m["sharpe"],
            "sortino":    m["sortino"],
            "cagr":       m["cagr"],
            "max_dd":     m["max_dd"],
            "excess_cagr":m["excess_cagr"],
        })
        print(f"  window={w:>3} ({round(w/21)}mo): OOS Sharpe={m['sharpe']:.3f}  "
              f"CAGR={m['cagr']:.2%}  maxDD={m['max_dd']:.2%}  days={m['n_days']}")

    table = pd.DataFrame(rows).set_index("window")
    print("\n" + "=" * 70)
    print("SWEEP RESULTS — continuous signal, identical OOS dates for all windows")
    print("=" * 70)
    print(table.to_string())

    grid_sharpes = [r["sharpe"] for r in rows]
    best_w = max(net_rets, key=lambda k: table.loc[k, "sharpe"])
    print(f"\nBest OOS Sharpe: window={best_w} ({round(best_w/21)}mo)  "
          f"Sharpe={table.loc[best_w,'sharpe']:.3f}")

    # DSR: deflate the best config's Sharpe for having tried len(WINDOWS) configs.
    print("\n─── DSR (deflated for the 3-config search) ───")
    dsr = val_mod.run_dsr(net_rets[best_w], grid_sharpes=grid_sharpes)
    print(f"  DSR={dsr['dsr']:.3f}  (n_trials={dsr['n_trials']}, "
          f"pass>0.90: {dsr['pass']})")

    # PBO: CSCV across the 3 windows on their common evaluable dates.
    print("\n─── PBO (CSCV across the 3 windows) ───")
    common_start = max(s.index[0] for s in net_rets.values())
    common_end   = min(s.index[-1] for s in net_rets.values())
    mat = pd.concat(
        {f"w{w}": s.loc[common_start:common_end] for w, s in net_rets.items()},
        axis=1,
    ).dropna()
    print(f"  common window {common_start.date()} → {common_end.date()}  "
          f"({len(mat)} days, {mat.shape[1]} configs)")
    if mat.shape[1] >= 2 and len(mat) >= 32:
        pbo = val_mod.run_pbo(mat)
        print(f"  PBO={pbo['pbo']:.3f}  (pass<0.50: {pbo['pass']})")
    else:
        print("  PBO skipped — not enough common data.")


if __name__ == "__main__":
    main()
