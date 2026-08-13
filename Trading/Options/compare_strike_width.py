#!/usr/bin/env python3
"""
Bull Put Spread - fixed $5 strike-width wing comparison.

Scenarios (all with the adopted settings: dte_target 30, pt 0.60 / sl 0.50 /
dte_min 22, vix 10-35, fixed_risk 30%, $20k, $0.65 commission):
    control  -> short 24d, long 10d (delta-selected wing, dynamic width)
    w5-24d   -> short 24d, long pinned exactly $5 wide
    w5-20d   -> short 20d, long pinned exactly $5 wide

Runs the full 2018-01-02..2026-07-10 window and the 2024-01-02..2026-06-30
window; prints metrics; renders charts/bull_put_width_comparison.png.

Usage: python compare_strike_width.py
"""

import sys
import os
import copy
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

SCENARIOS = [
    ("control",
     {"dte_target": 30, "short_delta": 0.24, "long_delta": 0.10,
      "vix_min": 10, "vix_max": 35},
     {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}),
    ("w5-24d",
     {"dte_target": 30, "short_delta": 0.24, "strike_width": 5,
      "vix_min": 10, "vix_max": 35},
     {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}),
    ("w5-20d",
     {"dte_target": 30, "short_delta": 0.20, "strike_width": 5,
      "vix_min": 10, "vix_max": 35},
     {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}),
]

WINDOWS = [
    ("full", "2018-01-02", "2026-07-10"),
    ("2024-26", "2024-01-02", "2026-06-30"),
]

COLORS = {"control": "#4C72B0", "w5-24d": "#d62728", "w5-20d": "#2ca02c"}


def base_config() -> dict:
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)


def run_scenario(cfg, label, entry, exit_, options_data, underlying) -> dict:
    c = copy.deepcopy(cfg)
    strat_cfg = c["strategies"]["bull_put_spread"]
    strat_cfg["entry"].update(entry)
    strat_cfg["exit"].update(exit_)

    bt = OptopsyBacktester(c)
    strategy = BullPutSpread(strat_cfg)
    res = bt.run_backtest(strategy=strategy, options_data=options_data,
                          underlying_data=underlying, verbose=False)
    m = calculate_performance_metrics(res)

    trades = res.get("trades", pd.DataFrame())
    stats = {}
    if not trades.empty and "leg1_strike" in trades.columns:
        width = (trades["leg1_strike"] - trades["leg2_strike"]).abs()
        stats["avg_width"] = width.mean()
        stats["avg_credit"] = -trades["entry_price"].mean()
        stats["avg_contracts"] = trades["contracts"].mean()
        stats["avg_days"] = trades["days_in_trade"].mean()

    return {
        "scenario": label,
        "sharpe": m.get("sharpe_ratio"),
        "sortino": m.get("sortino_ratio"),
        "max_dd_pct": m.get("max_drawdown_pct"),
        "calmar": m.get("calmar_ratio"),
        "win_rate_pct": m.get("win_rate_pct"),
        "profit_factor": m.get("profit_factor"),
        "trades": m.get("total_trades"),
        "return_pct": m.get("total_return_pct"),
        **stats,
        "equity": res["equity_curve"],
    }


def fmt_table(rows):
    return pd.DataFrame(rows).drop(columns=["equity"]).to_string(
        index=False, float_format=lambda x: f"{x:.2f}")


def render_chart(results: dict) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from matplotlib.gridspec import GridSpec

    out = Path("charts") / "bull_put_width_comparison.png"
    os.makedirs("charts", exist_ok=True)

    labels = list(results.keys())
    fig = plt.figure(figsize=(15, 11))
    fig.suptitle(
        "Bull Put Spread - fixed $5 strike-width wing vs delta-selected wing\n"
        "30 DTE / short-delta short leg / pt 0.60, sl 0.50, dte_min 22, "
        "VIX 10-35, fixed-risk 30%, $20k  |  full window 2018-01-02..2026-07-09",
        fontsize=12, fontweight="bold")

    gs = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.25, bottom=0.17)
    panels = [("Sharpe Ratio", "sharpe", (0, 1.4), "{:.2f}"),
              ("Sortino Ratio", "sortino", (0, 2.2), "{:.2f}"),
              ("Calmar Ratio", "calmar", (0, 1.2), "{:.2f}"),
              ("Total Return %", "return_pct", (0, 1400), "{:.0f}"),
              ("Max Drawdown %", "max_dd_pct", (-50, 2), "{:.0f}"),
              ("Trades", "trades", (0, 700), "{:.0f}")]
    fmt_axis = mticker.FuncFormatter(lambda v, _: "{:.0f}".format(v))

    for i, (title, key, ylim, fmt) in enumerate(panels):
        ax = fig.add_subplot(gs[i // 3, i % 3])
        vals = [results[l][key] for l in labels]
        ax.bar(range(3), vals, color=[COLORS[l] for l in labels],
               edgecolor="#333", linewidth=1.0, alpha=0.9, zorder=3)
        for x, v in enumerate(vals):
            ax.text(x, v, fmt.format(v), ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=10, fontweight="bold")
        ax.set_xticks(range(3), labels, fontsize=10)
        ax.set_ylim(ylim)
        ax.grid(axis="y", alpha=0.3, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.set_major_formatter(fmt_axis)
        ax.set_title(title, fontsize=11, fontweight="bold")

    ax_eq = fig.add_subplot(gs[2, :])
    for l in labels:
        eq = results[l]["equity"]
        ax_eq.plot(pd.to_datetime(eq["date"]), eq["total_value"] / 20000,
                   color=COLORS[l], linewidth=1.6, label=l)
    ax_eq.set_yscale("log")
    ax_eq.set_ylabel("growth multiple (log)", fontsize=9)
    ax_eq.grid(alpha=0.3)
    ax_eq.spines[["top", "right"]].set_visible(False)
    ax_eq.set_title("Equity curves - full window (log scale)",
                    fontsize=11, fontweight="bold")
    ax_eq.legend(fontsize=10, loc="upper left", framealpha=0.9)

    cols = ["Trades", "Win %", "PF", "Max DD %", "Sharpe", "Sortino",
            "Calmar", "Return %", "Avg width$", "Avg credit$", "Avg ctr",
            "Avg days"]
    tbl_data = [cols]
    for l in labels:
        d = results[l]
        tbl_data.append([
            f"{d['trades']:.0f}", f"{d['win_rate_pct']:.1f}",
            f"{d['profit_factor']:.2f}", f"{d['max_dd_pct']:.1f}",
            f"{d['sharpe']:.2f}", f"{d['sortino']:.2f}", f"{d['calmar']:.2f}",
            f"{d['return_pct']:.0f}",
            f"{d.get('avg_width', float('nan')):.1f}",
            f"{d.get('avg_credit', float('nan')):.2f}",
            f"{d.get('avg_contracts', float('nan')):.1f}",
            f"{d.get('avg_days', float('nan')):.1f}"])
    table_ax = fig.add_axes([0.05, 0.02, 0.90, 0.11], frameon=False)
    table_ax.axis("off")
    tbl = table_ax.table(cellText=tbl_data, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    for j in range(len(cols)):
        tbl[(0, j)].set_text_props(fontweight="bold", color="white")
        tbl[(0, j)].set_facecolor("#1f2937")
    for i in range(1, len(tbl_data)):
        for j in range(len(cols)):
            tbl[(i, j)].set_facecolor("#f3f4f6" if i % 2 == 0 else "white")
    tbl.scale(1, 1.2)

    fig.savefig(out, dpi=150, bbox_inches="tight")
    return out


def main() -> int:
    cfg = base_config()
    print("Loading synthetic options data (existing CSV) ...")
    options_data = load_sample_spy_options_data(config=cfg)
    print(f"  {len(options_data):,} rows, "
          f"{options_data['quote_date'].nunique()} trading days")
    print("Fetching SPY underlying (once) ...")
    underlying = fetch_spy_data("2018-01-02", "2026-07-10")
    print(f"  {len(underlying)} underlying rows")

    full_results = {}
    only = sys.argv[sys.argv.index("--window") + 1] if "--window" in sys.argv else None
    for win_name, win_start, win_end in WINDOWS:
        if only and win_name != only:
            continue
        print("\n" + "=" * 78)
        print(f"WINDOW {win_name}: {win_start} .. {win_end}")
        print("=" * 78)
        c = copy.deepcopy(cfg)
        c["backtest"]["start_date"] = win_start
        c["backtest"]["end_date"] = win_end
        od = options_data[
            (options_data["quote_date"] >= pd.Timestamp(win_start)) &
            (options_data["quote_date"] <= pd.Timestamp(win_end) + pd.Timedelta(hours=12))
        ].copy()
        win_rows = []
        for label, entry, exit_ in SCENARIOS:
            try:
                r = run_scenario(c, label, entry, exit_, od, underlying)
                win_rows.append(r)
                print(f"  OK {label:<9} Sharpe {r['sharpe']:.2f}  "
                      f"DD {r['max_dd_pct']:.1f}%  {r['trades']:.0f} trades  "
                      f"+{r['return_pct']:.0f}%")
            except Exception as e:
                win_rows.append({"scenario": label, "error": str(e)})
                print(f"  FAIL {label}: {e}")
        if win_name == "full":
            full_results = {r["scenario"]: r for r in win_rows}
        print(fmt_table(win_rows))
        Path("backtest_results").mkdir(exist_ok=True)
        out_csv = Path("backtest_results") / f"strike_width_{win_name}.csv"
        pd.DataFrame([{k: v for k, v in r.items()
                       if k not in ("equity", "error")} for r in win_rows]
                     ).to_csv(out_csv, index=False)
        print(f"Saved: {out_csv}")

    chart = render_chart(full_results)
    print(f"\nChart saved: {chart}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
