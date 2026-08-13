#!/usr/bin/env python3
"""Account-size sweep + chart for the recommended daily-cadence structure (2026-08-13).

Under `fixed_contracts` sizing the account value never gates entries, so the strategy books an
IDENTICAL dollar P&L path at any starting capital (verified in diag_capital_denominator.py:
same 2,125 trades, same $111,692, same -$22,822 dollar drawdown at $150k / $50k / $25k).

That makes every percentage metric a pure function of the starting balance, computable exactly
from one backtest: total_value(C, t) = C + pnl_path(t). This sweeps C and renders the tradeoff.

Outputs: charts/daily_cadence_account_size.png
         backtest_results/account_size_sweep.csv

Usage: opt_venv/bin/python make_account_size_chart.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml, numpy as np, pandas as pd
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data

WINDOW = ("2018-01-02", "2026-07-09")
BASE_CAPITAL = 150000
SIZES = list(range(25000, 205000, 5000))
HIGHLIGHT = 150000

SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e3e2de"
C_CAGR, C_DD = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.labelcolor": INK_2, "axes.edgecolor": GRID, "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.bottom": False, "ytick.left": False,
})


PNL_CACHE = Path("backtest_results") / "daily_cadence_pnl_path.csv"


def pnl_path():
    if PNL_CACHE.exists():
        c = pd.read_csv(PNL_CACHE, parse_dates=["date"])
        print(f"Using cached P&L path ({PNL_CACHE}) — delete it to force a re-run.")
        return c["date"].values, c["pnl"].values, None
    with open("config/config.yaml") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["grid_mode"] = "delta_band"
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = WINDOW
    cfg["backtest"]["initial_capital"] = BASE_CAPITAL
    cfg["position_sizing"]["method"] = "fixed_contracts"
    cfg["position_sizing"]["contracts_per_trade"] = 1
    sc = cfg["strategies"]["bull_put_spread"]
    sc["entry"].pop("long_delta", None)
    sc["entry"].update({"dte_target": 21, "short_delta": 0.35, "strike_width": 10})
    sc["entry"]["vix_min"], sc["entry"]["vix_max"] = 0, 999
    sc["exit"].update({"profit_target": 0.80, "stop_loss": 0.30, "dte_min": 5})

    print("Loading corrected (delta_band) 2018-2026 options data...")
    od = load_sample_spy_options_data(config=cfg)
    ud = fetch_spy_data(*WINDOW)
    res = OptopsyBacktester(cfg).run_backtest(strategy=BullPutSpread(sc), options_data=od,
                                              underlying_data=ud, verbose=False)
    eq = res["equity_curve"].copy()
    eq["date"] = pd.to_datetime(eq["date"])
    pnl = (eq["total_value"] - BASE_CAPITAL).values
    PNL_CACHE.parent.mkdir(exist_ok=True)
    pd.DataFrame({"date": eq["date"], "pnl": pnl}).to_csv(PNL_CACHE, index=False)
    return eq["date"].values, pnl, res


RISK_FREE = 0.02   # must match src/analysis/metrics.py:84 -- the project reports EXCESS Sharpe


def metrics_at(capital, pnl, years):
    tv = capital + pnl
    dd = (tv - np.maximum.accumulate(tv)) / np.maximum.accumulate(tv)
    r = pd.Series(tv).pct_change().dropna()
    excess = r - RISK_FREE / 252
    return {
        "capital": capital,
        "cagr_pct": ((tv[-1] / capital) ** (1 / years) - 1) * 100,
        "total_return_pct": (tv[-1] / capital - 1) * 100,
        "max_dd_pct": dd.min() * 100,
        "sharpe": excess.mean() / excess.std() * np.sqrt(252),
        "sharpe_raw_no_rf": r.mean() / r.std() * np.sqrt(252),
    }


def main():
    dates, pnl, res = pnl_path()
    years = (dates[-1] - dates[0]) / np.timedelta64(1, "D") / 365.25
    df = pd.DataFrame([metrics_at(c, pnl, years) for c in SIZES])
    Path("backtest_results").mkdir(exist_ok=True)
    df.to_csv("backtest_results/account_size_sweep.csv", index=False)

    print(f"\nyears={years:.2f}  total P&L=${pnl[-1]:,.0f}  "
          f"dollar maxDD=${(pnl - np.maximum.accumulate(pnl + BASE_CAPITAL) + BASE_CAPITAL).min():,.0f}")
    print(df[df.capital.isin([25000, 50000, 75000, 100000, 150000, 200000])].round(2).to_string(index=False))

    Path("charts").mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    xs = df["capital"] / 1000

    ax.plot(xs, df["cagr_pct"], color=C_CAGR, linewidth=2.2, zorder=3)
    ax.plot(xs, df["max_dd_pct"], color=C_DD, linewidth=2.2, zorder=3)
    ax.axhline(0, color=GRID, linewidth=1)

    # direct labels instead of a legend box (2 series)
    ax.annotate("CAGR", (xs.iloc[-1], df["cagr_pct"].iloc[-1]), xytext=(8, 0),
                textcoords="offset points", va="center", color=C_CAGR, fontsize=10,
                fontweight="bold")
    ax.annotate("max drawdown", (xs.iloc[-1], df["max_dd_pct"].iloc[-1]), xytext=(8, 0),
                textcoords="offset points", va="center", color=C_DD, fontsize=10,
                fontweight="bold")

    row = df[df.capital == HIGHLIGHT].iloc[0]
    for val, col in ((row.cagr_pct, C_CAGR), (row.max_dd_pct, C_DD)):
        ax.plot([HIGHLIGHT / 1000], [val], "o", color=col, markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=4)
        ax.annotate(f"{val:.1f}%", (HIGHLIGHT / 1000, val), xytext=(0, 12 if val > 0 else -20),
                    textcoords="offset points", ha="center", fontsize=9.5, color=INK,
                    fontweight="bold")
    ax.axvline(HIGHLIGHT / 1000, color=INK_2, linewidth=1, linestyle=(0, (4, 4)), alpha=0.5, zorder=1)

    ax.set_xlabel("starting account size ($ thousands)", fontsize=9.5)
    ax.set_ylabel("% of account", fontsize=9.5)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:.0f}k"))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax.set_xlim(xs.min() - 3, xs.max() + 22)

    # NOTE: escape '$' in matplotlib text or it is parsed as mathtext and the string mangles.
    fig.suptitle(r"The same \$111,692 and the same -\$22,822 drawdown, divided by your account",
                 fontsize=12, color=INK, x=0.008, ha="left", y=1.02, fontweight="bold")
    fig.text(0.008, 0.96, "1 contract/day never scales, so every percentage is just a "
             r"denominator choice. Dashed line = the \$150k used in reporting.",
             fontsize=9, color=INK_2, ha="left", va="top")
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    out = Path("charts") / "daily_cadence_account_size.png"
    fig.savefig(out, dpi=170, bbox_inches="tight")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
