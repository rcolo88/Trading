"""Robustness diagnostic for the undisclosed wM/wV/wC Total Rank weights.

The paper never discloses its own Total Rank component weights — they were
fit in Excel, full-sample, no OOS split, no transaction costs. RAAM trades
EQUAL weights (1/3 each) by design, with no fitting. This script sweeps a
grid over the (wM, wV, wC) simplex through the REAL walk-forward OOS engine
(the same compute_total_rank -> select_book -> build_positions ->
simulate_drift path `raam.py backtest` and `ideas` use) and reports OOS
Sharpe for every combination:

  - A FLAT PLATEAU across the grid is evidence the model isn't secretly
    weight-sensitive — equal weights sitting inside a broad, unremarkable
    region means the paper's hidden weights aren't doing unreplicable work.
  - A SHARP, ISOLATED PEAK somewhere else would be a red flag that some
    particular weighting (ours or otherwise) is fitting noise.

Every trial's OOS Sharpe should be appended to config.yaml's
validation.trial_sharpes so the Deflated Sharpe Ratio stays honestly
deflated against the full search this script performs — same convention as
Cross-Sectional Momentum's sweep_max_names.py (manually curated, not
auto-written, so a human reviews the numbers before they change the DSR grid).

NOTE on imports: this repo's CLI is `raam.py` (a script) sitting next to the
`raam/` package — same base name is fine for the CLI itself (it runs as
__main__, so there's no clash), but it means OTHER scripts can't do
`from raam import load_config` (that resolves to the PACKAGE, not the
script). `load_config`/`_backtest_window` are duplicated here (they're a few
lines each) rather than fighting that.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import yaml

from raam import backtest as bt_mod
from raam import data as data_mod
from raam import universe as univ_mod
from raam.costs import turnover_stats
from raam.validation import compute_metrics, run_pbo

_HERE = Path(__file__).resolve().parent


def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _backtest_window(cfg: dict) -> tuple[str, str]:
    data_cfg = cfg.get("data", {})
    start = data_cfg.get("start_date")
    if start in (None, "", "auto"):
        start = data_mod._CACHE_HISTORY_START
    start = pd.Timestamp(start)
    ceiling = pd.Timestamp.today().normalize()
    end_cfg = data_cfg.get("end_date")
    end = ceiling if end_cfg in (None, "", "auto") else min(pd.Timestamp(end_cfg), ceiling)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _simplex_grid(step: float = 0.1) -> list[tuple[float, float, float]]:
    """All (wM, wV, wC) with each a multiple of `step`, summing to 1.0."""
    n = round(1.0 / step)
    pts = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            k = n - i - j
            pts.append((round(i * step, 4), round(j * step, 4), round(k * step, 4)))
    return pts


def main() -> None:
    cfg       = load_config()
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    tickers   = univ_mod.ALL_TICKERS + [univ_mod.SPY]

    bt_start, bt_end = _backtest_window(cfg)
    oos_frac = float(cfg.get("validation", {}).get("walk_forward_oos_frac", 0.30))

    panel = data_mod.load_ohlc_panel(tickers, start=bt_start, end=bt_end, cache_dir=cache_dir)
    close = data_mod.close_panel(panel)

    grid = _simplex_grid(step=0.1)
    print(f"\nWindow: {bt_start} -> {bt_end}   OOS frac: {oos_frac}   "
          f"{len(grid)} (wM,wV,wC) combinations (step=0.1)\n")
    print(f"  {'wM':>5} {'wV':>5} {'wC':>5}   {'Sharpe':>8} {'CAGR':>8} "
          f"{'MaxDD':>8} {'Calmar':>7} {'Ann.Turn':>9}")
    print("  " + "-" * 62)

    # Traded default (1/3, 1/3, 1/3) explicitly, not just a nearby grid point —
    # the 0.1-step grid can never land exactly on 1/3 for all three at once.
    trial_points = [(1 / 3, 1 / 3, 1 / 3)] + grid
    oos_start = close.index[int(len(close) * (1 - oos_frac))]

    rows, ret_cols = [], {}
    for wM, wV, wC in trial_points:
        c = copy.deepcopy(cfg)
        c["ranking"]["wM"] = wM
        c["ranking"]["wV"] = wV
        c["ranking"]["wC"] = wC
        res = bt_mod.run_raam(panel, close, c, start=oos_start)
        m  = compute_metrics(res.net_ret, res.bench_ret)
        to = turnover_stats(res.exec_pos)
        rows.append((wM, wV, wC, m, to))
        ret_cols[f"{wM:.2f}_{wV:.2f}_{wC:.2f}"] = res.net_ret
        tag = " <- EQUAL (traded default)" if (wM, wV, wC) == (1 / 3, 1 / 3, 1 / 3) else ""
        print(f"  {wM:>5.2f} {wV:>5.2f} {wC:>5.2f}   {m['sharpe']:>8.3f} {m['cagr']:>+8.1%} "
              f"{m['max_dd']:>+8.1%} {m['calmar']:>7.2f} {to['annual_turnover']:>8.1f}x{tag}",
              flush=True)

    grid_rows   = rows[1:]                     # the 0.1-step grid only (excludes the equal-weight extra)
    grid_sharpes = [r[3]["sharpe"] for r in grid_rows]
    equal_row    = rows[0]
    equal_sharpe = equal_row[3]["sharpe"]

    lo, hi = min(grid_sharpes), max(grid_sharpes)
    best   = max(grid_rows, key=lambda r: r[3]["sharpe"])
    worst  = min(grid_rows, key=lambda r: r[3]["sharpe"])
    rank_of_equal = sorted(grid_sharpes + [equal_sharpe], reverse=True).index(equal_sharpe) + 1

    print("\n" + "=" * 62)
    print(f"Sharpe range across the {len(grid_rows)}-point grid: [{lo:.3f}, {hi:.3f}]  "
          f"(spread = {hi - lo:.3f})")
    print(f"Best:  wM={best[0]:.1f} wV={best[1]:.1f} wC={best[2]:.1f}  Sharpe={best[3]['sharpe']:.3f}")
    print(f"Worst: wM={worst[0]:.1f} wV={worst[1]:.1f} wC={worst[2]:.1f}  Sharpe={worst[3]['sharpe']:.3f}")
    print(f"Equal (traded default) wM=wV=wC=1/3: Sharpe={equal_sharpe:.3f}  "
          f"(rank {rank_of_equal} of {len(grid_rows) + 1})")
    verdict = ("FLAT PLATEAU" if (hi - lo) < 0.30
              else "SHARP PEAK — dispersion is real; see config.yaml validation.trial_sharpes "
                   "comment for the economic explanation (wV~=0 costs drawdown control) and why "
                   "equal weights are kept anyway")
    print(f"\nVerdict: {verdict}")

    # ── PBO (Probability of Backtest Overfitting) via CSCV across the sweep ──
    ret_matrix = pd.DataFrame(ret_cols)
    pbo = run_pbo(ret_matrix, n_partitions=int(cfg.get("validation", {}).get("n_partitions_pbo", 16)))
    icon = "PASS" if pbo["pass"] else "FAIL"
    print(f"\n[{icon}] Probability of Backtest Overfitting (PBO) across all "
          f"{ret_matrix.shape[1]} trials: {pbo['pbo']:.3f}  (threshold < 0.50)")

    print("\n--- paste into config.yaml validation.trial_sharpes (grid only, for DSR) ---")
    print("trial_sharpes: [" + ", ".join(f"{s:.4f}" for s in grid_sharpes) + "]")


if __name__ == "__main__":
    main()
