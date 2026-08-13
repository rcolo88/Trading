#!/usr/bin/env python3
"""
Bull Put Spread — VIX floor (vix_min) metrics chart.

Renders the return metrics for the adopted vix 10-35 configuration (30 DTE /
24d short / 10d long, pt 0.60 / sl 0.50 / dte_min 22, fixed-risk 30%, $20k)
against the vix_min 15/17.5/20 alternatives, for both the full 2018-2026 window
and the 2024-2026 window.

Numbers are the 2026-08-02 sweep results (see CHANGELOG.md), produced with the
same OptopsyBacktester harness used by stress_test_gfc.py.

Output: charts/bull_put_vix10_35_metrics.png
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec

OUT_PATH = Path("charts") / "bull_put_vix10_35_metrics.png"

# Row layout: (vix_min, trades, max_dd_pct, sharpe, sortino, calmar, win_pct, pf, return_pct)
IDX = {"trades": 1, "max_dd": 2, "sharpe": 3, "sortino": 4, "calmar": 5,
       "win": 6, "pf": 7, "return": 8}

FULL_WINDOW = [
    ("10", 606, -43.09, 1.08, 1.20, 0.81, 72.23, 1.65, 1173.3),
    ("15", 439, -35.68, 0.94, 0.94, 0.76, 70.84, 1.60, 661.3),
    ("17.5", 319, -35.62, 1.15, 1.07, 0.85, 73.67, 2.06, 846.9),
    ("20", 224, -27.26, 1.07, 0.86, 0.88, 74.60, 1.99, 517.5),
]
WINDOW_2024_26 = [
    ("10", 170, -30.26, 1.63, 1.84, 1.88, 73.50, 1.74, 204.7),
    ("15", 119, -30.50, 1.32, 1.32, 1.28, 73.95, 1.71, 126.1),
    ("17.5", 74, -23.96, 1.75, 1.57, 1.86, 79.73, 2.90, 149.0),
    ("20", 41, -16.40, 1.24, 0.81, 1.40, 80.49, 2.78, 67.0),
]

LABELS = [f"vix_min {r[0]}" for r in FULL_WINDOW]
HIGHLIGHT = 0  # vix 10-35 = adopted config
COLORS = ["#d62728" if i == HIGHLIGHT else "#4C72B0" for i in range(len(LABELS))]
EDGES = ["#a3151c" if i == HIGHLIGHT else "#2f4a73" for i in range(len(LABELS))]

# Main panels: (title, metric key, ylim, fmt)
PANELS = [
    ("Sharpe Ratio", "sharpe", (0, 1.4), "{:.2f}"),
    ("Sortino Ratio", "sortino", (0, 2.0), "{:.2f}"),
    ("Calmar Ratio", "calmar", (0, 2.2), "{:.2f}"),
    ("Total Return %", "return", (0, 1300), "{:.0f}"),
    ("Max Drawdown %", "max_dd", (-50, 2), "{:.0f}"),
    ("Trades", "trades", (0, 700), "{:.0f}"),
]

FMT = mticker.FuncFormatter(lambda v, _: "{:.0f}".format(v))


def _bars(ax, data, key, ylim, fmt):
    idx = IDX[key]
    ax.bar(range(len(data)), [r[idx] for r in data], color=COLORS, edgecolor=EDGES,
           linewidth=1.2, alpha=0.9, zorder=3)
    for i, r in enumerate(data):
        val = r[idx]
        ax.text(i, val, fmt.format(val), ha="center",
                va="bottom" if val >= 0 else "top", fontsize=9,
                fontweight="bold" if i == HIGHLIGHT else "normal")
    ax.set_xticks(range(len(data)), LABELS, fontsize=9)
    ax.set_ylim(ylim)
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.set_major_formatter(FMT)


def main() -> int:
    os.makedirs("charts", exist_ok=True)

    fig = plt.figure(figsize=(14, 11))
    fig.suptitle("Bull Put Spread — 30 DTE / 24\u0394 short / 10\u0394 long "
                 "(pt 0.60, sl 0.50, dte_min 22, fixed-risk 30%, $20k)\n"
                 "Full window 2018-01-02..2026-07-09  |  Highlighted: adopted vix 10-35 config",
                 fontsize=12, fontweight="bold")

    gs = GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.25, bottom=0.20)
    for i, (title, key, ylim, fmt) in enumerate(PANELS):
        ax = fig.add_subplot(gs[i // 3, i % 3])
        _bars(ax, FULL_WINDOW, key, ylim, fmt)
        ax.set_title(title, fontsize=11, fontweight="bold")

    # 2024-2026 calm-regime window (one wide panel)
    ax26 = fig.add_subplot(gs[2, :])
    metrics26 = [("Sharpe", "sharpe", (0, 2.0), "{:.2f}"),
                 ("Return %", "return", (0, 260), "{:.0f}"),
                 ("Max DD %", "max_dd", (-35, 2), "{:.0f}"),
                 ("Trades", "trades", (0, 200), "{:.0f}")]
    width = 0.18
    for k, (name, key, ylim, fmt) in enumerate(metrics26):
        idx = IDX[key]
        xs = [k + width * i for i in range(len(LABELS))]
        vals = [r[idx] for r in WINDOW_2024_26]
        ax26.bar(xs, vals, width=width, color=COLORS, edgecolor=EDGES,
                 linewidth=1.0, alpha=0.9, zorder=3)
        for x, v in zip(xs, vals):
            ax26.text(x, v, fmt.format(v), ha="center",
                      va="bottom" if v >= 0 else "top", fontsize=7.5,
                      fontweight="bold" if abs(x - (k + width * HIGHLIGHT)) < 1e-9 else "normal")
        ax26.set_ylim(ylim)
    ax26.set_title("2024-01-02..2026-06-30 (calm-regime window)", fontsize=10, fontweight="bold")
    ax26.set_xticks([k + 1.5 * width for k in range(4)], [m[0] for m in metrics26], fontsize=9)
    ax26.grid(axis="y", alpha=0.3)
    ax26.spines[["top", "right"]].set_visible(False)
    ax26.legend(LABELS, fontsize=7.5, ncol=4, loc="upper right", framealpha=0.9)

    # Full metrics table footer
    table_data = [["vix_min", "Trades", "Max DD %", "Sharpe", "Sortino", "Calmar",
                   "Win %", "PF", "Return %"]]
    for r in FULL_WINDOW:
        table_data.append([r[0], f"{r[IDX['trades']]:.0f}", f"{r[IDX['max_dd']]:.1f}",
                           f"{r[IDX['sharpe']]:.2f}", f"{r[IDX['sortino']]:.2f}",
                           f"{r[IDX['calmar']]:.2f}", f"{r[IDX['win']]:.1f}",
                           f"{r[IDX['pf']]:.2f}", f"{r[IDX['return']]:.0f}"])
    table_ax = fig.add_axes([0.05, 0.02, 0.90, 0.10], frameon=False)
    table_ax.axis("off")
    tbl = table_ax.table(cellText=table_data, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    for j in range(9):
        tbl[(0, j)].set_text_props(fontweight="bold", color="white")
        tbl[(0, j)].set_facecolor("#1f2937")
    for i in range(1, len(table_data)):
        for j in range(9):
            if i - 1 == HIGHLIGHT:
                tbl[(i, j)].set_facecolor("#fde8e8")
            elif i % 2 == 0:
                tbl[(i, j)].set_facecolor("#f3f4f6")
    tbl.scale(1, 1.25)

    fig.savefig(OUT_PATH, dpi=150, bbox_inches="tight")
    print(f"Chart saved: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
