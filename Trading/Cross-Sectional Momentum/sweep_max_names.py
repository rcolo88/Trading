"""Empirical test of the claim: "anything past the top ~20 names adds noise and
lowers Sharpe."

Sweeps portfolio.max_names through the REAL OOS engine (simulate_live: weekly
rebalance, hold-with-drift, costs on turnover) — the exact book `ideas` trades —
and reports OOS Sharpe / CAGR / MaxDD / turnover for each cap.

Selection is unchanged otherwise (top-quintile signal, equal-$ 1/N, vol-scaled,
regime-gated); only the cap on how many of the top-quintile names are held moves.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd

import csm.data as data_mod
import csm.universe as univ_mod
import csm.backtest as bt_mod
from csm.validation import compute_metrics
from csm.costs import turnover_stats
from csmom import load_config, _backtest_window

_HERE = Path(__file__).resolve().parent

# NOTE: build_positions now ranks the top quintile by signal and keeps the
# strongest max_names (the conviction cap), so sweeping cfg["portfolio"]
# ["max_names"] directly tests "how many of the highest-conviction names to hold".


def main() -> None:
    cfg       = load_config()
    cache_dir = _HERE / cfg["data"]["cache_dir"]

    pit_path = cache_dir / "universe_pit.parquet"
    if pit_path.exists():
        pit_df = pd.read_parquet(pit_path)
        ever   = univ_mod.get_all_ever_members(pit_df)
        univ_note = "S&P 1500 PIT"
    else:
        from io import StringIO
        import requests
        r = requests.get("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        ever   = pd.read_html(StringIO(r.text))[0]["Symbol"].tolist()
        pit_df = None
        univ_note = "current S&P 500 (survivorship-biased)"

    bt_start, bt_end = _backtest_window(cfg)
    prices = data_mod.load_price_panel(tickers=ever, start=bt_start, end=bt_end,
                                       cache_dir=cache_dir)

    oos_frac = float(cfg.get("validation", {}).get("walk_forward_oos_frac", 0.30))
    caps     = [10, 15, 20, 25, 30, 40, 50, 75, 100, 150]

    print(f"\nUniverse: {univ_note}   Window: {bt_start} → {bt_end}   OOS frac: {oos_frac}")
    print(f"Quantile {cfg['signal']['quantile']} (top-quintile) is fixed; only max_names varies.\n")
    print(f"  {'max_names':>9} {'avg held':>9} {'Sharpe':>8} {'CAGR':>8} "
          f"{'MaxDD':>8} {'Calmar':>7} {'Ann.Turn':>9}")
    print("  " + "-" * 64)

    rows = []
    for cap in caps:
        c = copy.deepcopy(cfg)
        c["portfolio"]["max_names"] = cap
        res = bt_mod.walk_forward(prices, c, pit_df=pit_df, oos_frac=oos_frac)
        m   = compute_metrics(res.net_ret, res.bench_ret)
        to  = turnover_stats(res.exec_pos)
        # average number of names actually held on rebalanced rows
        held = res.exec_pos[(res.exec_pos > 0)].count(axis=1)
        avg_held = float(held[held > 0].mean())
        rows.append((cap, avg_held, m))
        print(f"  {cap:>9} {avg_held:>9.1f} {m['sharpe']:>8.3f} {m['cagr']:>+8.1%} "
              f"{m['max_dd']:>+8.1%} {m['calmar']:>7.2f} {to['annual_turnover']:>8.1f}x")

    # benchmark
    bm = compute_metrics(rows[0][2] and res.bench_ret, res.bench_ret)
    print("  " + "-" * 64)
    print(f"  {'SPY B&H':>9} {'—':>9} {bm['sharpe']:>8.3f} {bm['cagr']:>+8.1%} "
          f"{bm['max_dd']:>+8.1%} {'—':>7} {'—':>9}")

    best = max(rows, key=lambda x: x[2]["sharpe"])
    print(f"\nBest OOS Sharpe: max_names={best[0]} (avg {best[1]:.0f} held) "
          f"→ Sharpe {best[2]['sharpe']:.3f}")


if __name__ == "__main__":
    main()
