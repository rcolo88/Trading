#!/usr/bin/env python3
"""Charts for the 2026-08-13 controlled short_delta x stop_loss sweep.

Renders the three figures that carry the argument in DAILY_CADENCE_STRATEGY.md:

  1. charts/daily_cadence_delta_stop_grid.png
     At a FIXED $10 wing: full-span Sharpe rises monotonically with short delta, while max
     drawdown stays flat. The decisive chart for "which short delta".
  2. charts/daily_cadence_width_vs_delta_dd.png
     Max drawdown by short delta, delta-selected wing vs fixed $10 wing. Shows the apparent
     "low delta = deep drawdown" effect is a WIDTH artifact, not a delta effect.
  3. charts/daily_cadence_wing_headtohead.png
     The two finalists at 0.35 delta / SL 30%: delta-selected 0.15 wing vs fixed $10 wing.

Data: backtest_results/compare_delta_stop_grid.csv (delta-gap wing) and
      backtest_results/compare_delta_stop_grid_w10.csv (fixed $10 wing),
      both produced by compare_delta_stop_grid.py.

Usage: opt_venv/bin/python make_delta_width_charts.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = Path("charts")
RES_DIR = Path("backtest_results")

# --- palette (validated: scripts/validate_palette.js, light mode) -----------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e3e2de"
# ordinal blue ramp for stop_loss (an ORDERED variable -> one hue, light->dark, not categorical)
SL_RAMP = {0.30: "#0d366b", 0.50: "#1c5cab", 0.70: "#3987e5", 0.99: "#86b6ef"}
# categorical slots 1-2 for wing TYPE (identity, not magnitude)
C_DELTA_WING = "#eb6834"   # slot 2 orange
C_FIXED_WING = "#2a78d6"   # slot 1 blue

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10,
    "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": GRID,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.bottom": False, "ytick.left": False,
})


def _style(ax, ylabel):
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel(ylabel, fontsize=9.5)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def chart_delta_stop_grid(w10):
    """Sharpe rises with delta; drawdown does not. Two panels, one shared x (short delta)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    deltas = sorted(w10["short_delta"].unique())
    x = range(len(deltas))

    ends = []
    for sl in sorted(w10["stop_loss"].unique()):
        sub = w10[w10["stop_loss"] == sl].sort_values("short_delta")
        lbl = "no stop" if sl > 0.9 else f"SL {sl:.0%}"
        for ax, col in ((ax1, "sharpe_full"), (ax2, "max_dd_pct")):
            ax.plot(x, sub[col], color=SL_RAMP[sl], linewidth=2,
                    marker="o", markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5,
                    zorder=3 if sl == 0.30 else 2)
        ends.append([sub["sharpe_full"].iloc[-1], lbl, sl])

    # Direct labels at the line end (mandatory at 4 series). The SL 50/70/no-stop lines converge
    # within ~0.06 Sharpe, so push the labels apart to a minimum gap instead of letting them stack.
    ends.sort(key=lambda e: e[0])
    min_gap = 0.052
    for i in range(1, len(ends)):
        if ends[i][0] - ends[i - 1][0] < min_gap:
            ends[i][0] = ends[i - 1][0] + min_gap
    for y, lbl, sl in ends:
        ax1.annotate(lbl, (x[-1], y), xytext=(9, 0), textcoords="offset points",
                     va="center", fontsize=9, color=INK if sl == 0.30 else INK_2,
                     fontweight="bold" if sl == 0.30 else "normal")

    for ax in (ax1, ax2):
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"{d:.2f}Δ" for d in deltas])
        ax.set_xlabel("short delta", fontsize=9.5)
        ax.set_xlim(-0.25, len(deltas) - 1 + 0.95)

    _style(ax1, "full-span Sharpe")
    ax1.set_title("Sharpe climbs steadily with short delta", fontsize=11.5, color=INK,
                  loc="left", pad=10, fontweight="bold")
    ax1.set_ylim(0, 1.0)

    _style(ax2, "max drawdown %")
    ax2.set_title("…while drawdown stays flat at the 30% stop", fontsize=11.5, color=INK,
                  loc="left", pad=10, fontweight="bold")
    ax2.set_ylim(-21, 0)
    ax2.axhspan(-11.5, -9.5, color="#2a78d6", alpha=0.07, zorder=0)
    ax2.annotate("SL 30% spans just 1.5 points across the whole delta axis",
                 xy=(-0.15, -8.4), fontsize=8.5, color=INK_2, style="italic")

    fig.suptitle("Short delta is the return knob, not the risk knob  —  wing pinned at $10, "
                 "21 DTE / PT 80% / exit 5 DTE, 2018-2026",
                 fontsize=10, color=INK_2, y=1.0, x=0.008, ha="left")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = OUT_DIR / "daily_cadence_delta_stop_grid.png"
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def chart_width_vs_delta(gap, w10):
    """The 'low delta = deep drawdown' effect is a width artifact."""
    g = gap[gap["stop_loss"] == 0.30].sort_values("short_delta")
    w = w10[w10["stop_loss"] == 0.30].sort_values("short_delta")
    deltas = list(w["short_delta"])
    x = range(len(deltas))
    bw = 0.36

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    b1 = ax.bar([i - bw / 2 - 0.01 for i in x], g["max_dd_pct"], bw, color=C_DELTA_WING,
                label="delta-selected wing (0.20Δ gap)", zorder=3)
    b2 = ax.bar([i + bw / 2 + 0.01 for i in x], w["max_dd_pct"], bw, color=C_FIXED_WING,
                label="fixed $10 wing", zorder=3)
    for bars in (b1, b2):
        for r in bars:
            ax.annotate(f"{r.get_height():.1f}", (r.get_x() + r.get_width() / 2, r.get_height()),
                        xytext=(0, -13), textcoords="offset points", ha="center",
                        fontsize=8.5, color=INK_2)

    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{d:.2f}Δ" for d in deltas])
    ax.set_xlabel("short delta", fontsize=9.5)
    _style(ax, "max drawdown %")
    ax.set_ylim(-32, 0)
    # bars all hang below zero, so the lower-right quadrant is the one empty region
    ax.legend(frameon=False, fontsize=9, loc="lower right", labelcolor=INK_2,
              bbox_to_anchor=(1.0, 0.02))

    fig.suptitle("Drawdown is set by WIDTH, not by short delta", fontsize=12.5, color=INK,
                 x=0.008, ha="left", y=1.10, fontweight="bold")
    fig.text(0.008, 0.995,
             "A constant 0.20Δ gap makes the spread ~3x wider in dollars at 0.20Δ than at 0.35Δ.\n"
             "Pin the width and the delta axis goes flat — the 25Δ spike was never a delta effect.",
             fontsize=9, color=INK_2, ha="left", va="top")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out = OUT_DIR / "daily_cadence_width_vs_delta_dd.png"
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def chart_head_to_head(gap, w10):
    """The two finalists at 0.35 delta / SL 30%. Five metrics, five axes (never one)."""
    d = gap[(gap["short_delta"] == 0.35) & (gap["stop_loss"] == 0.30)].iloc[0]
    f = w10[(w10["short_delta"] == 0.35) & (w10["stop_loss"] == 0.30)].iloc[0]
    calmar = lambda r: r["cagr_pct"] / abs(r["max_dd_pct"])

    panels = [
        ("CAGR %", d["cagr_pct"], f["cagr_pct"], "{:.2f}", False),
        ("Sharpe", d["sharpe_full"], f["sharpe_full"], "{:.3f}", False),
        ("Calmar", calmar(d), calmar(f), "{:.3f}", True),
        ("Max drawdown %", d["max_dd_pct"], f["max_dd_pct"], "{:.1f}", True),
        ("Worst single trade $", d["largest_loss"], f["largest_loss"], "{:,.0f}", True),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(13, 4.1))
    for ax, (title, dv, fv, fmt, fixed_wins) in zip(axes, panels):
        bars = ax.bar([0, 1], [dv, fv], 0.62, color=[C_DELTA_WING, C_FIXED_WING], zorder=3)
        neg = min(dv, fv) < 0
        for r, v in zip(bars, (dv, fv)):
            ax.annotate(fmt.format(v), (r.get_x() + r.get_width() / 2, v),
                        xytext=(0, -14 if neg else 4), textcoords="offset points",
                        ha="center", fontsize=9.5, color=INK, fontweight="bold")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["0.15Δ\nwing", "$10\nwing"], fontsize=9, color=INK_2)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.set_yticklabels([])
        ax.set_title(title, fontsize=10, color=INK, pad=8)
        pad = max(abs(dv), abs(fv)) * 0.28
        ax.set_ylim(min(0, min(dv, fv) - pad), max(0, max(dv, fv) + pad))
        # Mark the winner on its own tick label rather than as a floating badge — a badge above the
        # panel collides with the panel title, and the tick label is already the direct label.
        if fixed_wins:
            ax.get_xticklabels()[1].set_color(C_FIXED_WING)
            ax.get_xticklabels()[1].set_fontweight("bold")
        else:
            ax.get_xticklabels()[0].set_color(C_DELTA_WING)
            ax.get_xticklabels()[0].set_fontweight("bold")

    fig.suptitle("Same 0.35Δ short, same 30% stop — only the wing differs",
                 fontsize=12.5, color=INK, x=0.008, ha="left", y=1.10, fontweight="bold")
    fig.text(0.008, 1.02, "The $10 wing gives up 2.4 points of CAGR and buys a third less "
             "drawdown, a better Calmar, and a smaller worst trade. Bold label = better on "
             "that metric.",
             fontsize=9, color=INK_2, ha="left", va="top")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out = OUT_DIR / "daily_cadence_wing_headtohead.png"
    fig.savefig(out, dpi=170, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {out}")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    gap = pd.read_csv(RES_DIR / "compare_delta_stop_grid.csv")
    w10 = pd.read_csv(RES_DIR / "compare_delta_stop_grid_w10.csv")
    chart_delta_stop_grid(w10)
    chart_width_vs_delta(gap, w10)
    chart_head_to_head(gap, w10)


if __name__ == "__main__":
    main()
