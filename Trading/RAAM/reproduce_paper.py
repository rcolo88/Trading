"""Best-case GROSS reproduction of Giordano (2018) RAAM's headline Sharpe 1.94.

Answers the recurring objection — "the paper won a Dow Award, so reproduce the
1.94 first, THEN test on new data." This script shows the 1.94 is not
reachable with real data under ANY configuration, by giving the paper every
legitimately-reproducible advantage at once:

  * ZERO transaction costs   (the paper is explicitly gross, p.17)
  * the paper's exact window  (Jul 2004 -> Nov 2017)  AND a fully-real subwindow
  * the SINGLE BEST weighting from a full 134-point simplex sweep — i.e. assume
    the paper's undisclosed wM/wV/wC were the luckiest possible (an in-sample
    advantage the paper's own honest number would not have).

The one input we cannot recreate is the paper's admitted synthetic pre-inception
interpolation for DBC (real 2006-02) and IGOV (real 2009-01) back to 2004 ("Data
interpolation was performed on RStudio", p.17). So this is real-data-only. The
residual gap to 1.94 — largest precisely in the fully-real subwindow that has NO
synthetic data — is what that interpolation + full-sample Excel fit was worth.

Result (2026 data): best-of-sweep gross real-data tops out at ~1.13 Sharpe over
2004-2017 and ~0.80 over 2010-2017, both far short of 1.94. Corroborated by an
independent replication (QuantSeeker, Sep 2025), which was likewise "unable to
replicate the main results."

Indicators (M,V,C,T) do not depend on the weights, so they are computed ONCE per
window and only the ranking/selection/simulation re-runs per weight — see the
NOTE in sweep_rank_weights.py on why load_config is duplicated rather than
imported (the raam.py script vs raam/ package name collision).
"""
from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import yaml

from raam import backtest as bt_mod
from raam import data as data_mod
from raam import indicators as ind_mod
from raam import portfolio as port_mod
from raam import ranking as rank_mod
from raam import universe as univ_mod
from raam.validation import compute_metrics

_HERE = Path(__file__).resolve().parent

PAPER_SHARPE = 1.94   # Giordano (2018), Figure 18 (RAAM historical returns)


def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _simplex_grid(step: float = 0.1) -> list[tuple[float, float, float]]:
    n = round(1.0 / step)
    pts = []
    for i in range(n + 1):
        for j in range(n + 1 - i):
            pts.append((round(i * step, 4), round(j * step, 4), round((n - i - j) * step, 4)))
    return pts


def best_gross(panel, close_full, cfg, window_start, window_end, label):
    c0 = copy.deepcopy(cfg)
    c0["costs"]["commission_bps"] = 0.0     # GROSS — match the paper exactly
    c0["costs"]["half_spread_bps"] = 0.0
    n_select = int(c0["ranking"]["n_select"])

    ohlc_w   = panel.loc[:window_end]
    close_w  = close_full.loc[:window_end]
    start_ts = pd.Timestamp(window_start)

    indicators = ind_mod.compute_indicators(ohlc_w, univ_mod.RANKABLE, c0)   # weight-independent
    rebal      = rank_mod.month_end_dates(close_w.index)

    best = equal = None
    for (wM, wV, wC) in [(1 / 3, 1 / 3, 1 / 3)] + _simplex_grid(0.1):
        c = copy.deepcopy(c0)
        c["ranking"]["wM"], c["ranking"]["wV"], c["ranking"]["wC"] = wM, wV, wC
        total_rank = rank_mod.compute_total_rank(indicators, close_w, c)
        picks      = rank_mod.select_book(total_rank, n_select=n_select)
        pos        = port_mod.build_positions(picks, indicators["M"], close_w, c)
        res        = bt_mod.simulate_drift(pos, rebal, close_w, c, start_ts, label="repro")
        m = compute_metrics(res.net_ret, res.bench_ret)
        rec = (m["sharpe"], m["cagr"], m["max_dd"], m["annualized_std"], wM, wV, wC, len(res.net_ret))
        if (wM, wV, wC) == (1 / 3, 1 / 3, 1 / 3):
            equal = rec
        if best is None or rec[0] > best[0]:
            best = rec

    print(f"\n{'=' * 74}\n{label}\n  window {window_start} -> {window_end}   GROSS (0 bps)\n{'=' * 74}", flush=True)
    s, cg, dd, sd, *_, n = equal
    print(f"  equal (1/3,1/3,1/3):  Sharpe={s:6.3f}  CAGR={cg:+6.1%}  MaxDD={dd:+6.1%}  STD={sd:5.1%}  n={n}", flush=True)
    s, cg, dd, sd, wM, wV, wC, n = best
    print(f"  BEST ({wM:.1f},{wV:.1f},{wC:.1f}):    Sharpe={s:6.3f}  CAGR={cg:+6.1%}  MaxDD={dd:+6.1%}  STD={sd:5.1%}  n={n}", flush=True)
    print(f"  paper claim:          Sharpe={PAPER_SHARPE:6.3f}  (gross, undisclosed wts, +interpolated 2008-09 data)", flush=True)
    print(f"  --> even BEST-of-sweep gross real-data falls short of {PAPER_SHARPE} by {PAPER_SHARPE - best[0]:.3f} Sharpe", flush=True)
    return best, equal


def main() -> None:
    cfg       = load_config()
    cache_dir = _HERE / cfg["data"]["cache_dir"]
    tickers   = univ_mod.ALL_TICKERS + [univ_mod.SPY]

    panel = data_mod.load_ohlc_panel(tickers, start="auto",
                                     end=pd.Timestamp.today().strftime("%Y-%m-%d"),
                                     cache_dir=cache_dir)
    close = data_mod.close_panel(panel)

    # Paper's exact window (real-data-only via availability mask — DBC/IGOV ramp in).
    best_gross(panel, close, cfg, "2004-07-01", "2017-11-30",
               "PAPER WINDOW  (real-data-only, availability mask)")
    # Fully-real subwindow: all 11 rankable assets exist throughout (IGOV real
    # 2009-01 + 252d warmup -> ~2010). No synthetic ramp-up anywhere.
    best_gross(panel, close, cfg, "2010-06-01", "2017-11-30",
               "FULLY-REAL SUBWINDOW  (all 11 assets real throughout)")
    print("\nDONE", flush=True)


if __name__ == "__main__":
    main()
