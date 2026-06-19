"""Output reporting: JSON + human-readable TXT + equity PNG.

Follows the Fundamental Scanner output convention:
  outputs/backtest_YYYYMMDD.json
  outputs/backtest_YYYYMMDD.txt
  outputs/backtest_YYYYMMDD.png
  outputs/ideas_YYYYMMDD.json
  outputs/ideas_YYYYMMDD.txt
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from csm.backtest import BacktestResult
from csm.validation import compute_metrics
from csm.costs import turnover_stats


def _fmt_pct(v: float) -> str:
    return f"{v:+.1%}"


def _fmt_f(v: float, decimals: int = 3) -> str:
    return f"{v:+.{decimals}f}"


# ─────────────────────────────────────────────────────────────────────────────
#  Backtest report
# ─────────────────────────────────────────────────────────────────────────────

def write_backtest_report(
    results:      dict[str, BacktestResult],
    dsr_result:   dict | None,
    pbo_result:   dict | None,
    mcpt_result:  dict | None,
    out_dir:      Path,
    suffix:       str = "",
) -> None:
    """Write backtest report to JSON, TXT, and PNG."""
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem    = f"backtest_{ts}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Compute metrics for each result ---
    metrics_all = {}
    for label, res in results.items():
        m = compute_metrics(res.net_ret, res.bench_ret)
        to = turnover_stats(res.exec_pos)
        m.update(to)
        metrics_all[label] = m

    # ── TXT report ──
    lines = []
    lines.append("=" * 70)
    lines.append("Cross-Sectional Residual Momentum — Backtest Report")
    lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M}")
    lines.append("=" * 70)
    lines.append("\nNOTE: Survivorship bias present (current constituents only).")
    lines.append("      PIT correction reduces these numbers; treat as optimistic estimate.\n")

    headers = ["Strategy", "Sharpe", "CAGR", "MaxDD", "Calmar", "+Months", "Ann.Turn"]
    lines.append(f"  {'Strategy':<28}  {'Sharpe':>7}  {'CAGR':>8}  {'MaxDD':>8}  "
                 f"{'Calmar':>7}  {'+Months':>8}  {'Ann.Turn':>8}")
    lines.append("  " + "-" * 70)
    for label, m in metrics_all.items():
        lines.append(
            f"  {label:<28}  {_fmt_f(m['sharpe']):>7}  {_fmt_pct(m['cagr']):>8}  "
            f"{_fmt_pct(m['max_dd']):>8}  {_fmt_f(m['calmar']):>7}  "
            f"{m['pos_months']:>8.1%}  {m['annual_turnover']:>8.1f}x"
        )

    # Benchmark row
    if results:
        first = next(iter(results.values()))
        bm    = compute_metrics(first.bench_ret, first.bench_ret)
        lines.append(
            f"  {'SPY buy-and-hold':<28}  {_fmt_f(bm['sharpe']):>7}  "
            f"{_fmt_pct(bm['cagr']):>8}  {_fmt_pct(bm['max_dd']):>8}  "
            f"{'—':>7}  {'—':>8}  {'—':>8}"
        )

    # Overfitting tests
    lines.append("\n─── Overfitting Tests ─────────────────────────────────────────")
    if dsr_result:
        icon = "✓" if dsr_result["pass"] else "✗"
        lines.append(f"  {icon}  Deflated Sharpe Ratio (DSR): {dsr_result['dsr']:.4f}  "
                     f"(threshold > 0.90)  [{dsr_result['n_trials']} configs tried]")
    if pbo_result:
        icon = "✓" if pbo_result["pass"] else "✗"
        lines.append(f"  {icon}  Probability of Backtest Overfitting (PBO): "
                     f"{pbo_result['pbo']:.3f}  (threshold < 0.50)")
    if mcpt_result:
        icon = "✓" if mcpt_result["pass"] else "✗"
        lines.append(f"  {icon}  Monte Carlo Permutation Test p-value: "
                     f"{mcpt_result['p_value']:.4f}  (threshold < 0.05)")
        lines.append(f"       Null: mean={mcpt_result['null_mean']:+.3f}  "
                     f"σ={mcpt_result['null_std']:.3f}  "
                     f"95th pct={mcpt_result['null_95th']:+.3f}")

    lines.append("\n" + "=" * 70)
    txt = "\n".join(lines)
    (out_dir / f"{stem}.txt").write_text(txt)
    print(txt)

    # ── JSON report ──
    payload = {
        "generated": datetime.now().isoformat(),
        "metrics":   metrics_all,
        "dsr":       dsr_result,
        "pbo":       {k: v.tolist() if isinstance(v, np.ndarray) else v
                      for k, v in (pbo_result or {}).items()},
        "mcpt":      {k: v.tolist() if isinstance(v, np.ndarray) else v
                      for k, v in (mcpt_result or {}).items()},
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2, default=str))

    # ── Equity curve PNG ──
    _plot_equity(results, out_dir / f"{stem}.png")
    print(f"\nReport written to: {out_dir}/{stem}.[txt|json|png]")


def _plot_equity(results: dict[str, BacktestResult], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    colors  = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0"]
    first   = next(iter(results.values()))

    for (label, res), color in zip(results.items(), colors):
        ax.plot(res.equity.index, res.equity.values, label=label, linewidth=1.5, color=color)

    ax.plot(first.bench_equity.index, first.bench_equity.values,
            label="SPY buy-and-hold", linewidth=1.0, color="grey", linestyle="--")

    ax.set_title("Cross-Sectional Residual Momentum — Equity Curve", fontsize=13)
    ax.set_ylabel("Equity (starts at 1.0)")
    ax.set_yscale("log")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(str(path), dpi=130)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
#  Trade-idea report
# ─────────────────────────────────────────────────────────────────────────────

def write_ideas_report(
    ideas:   list[dict],
    out_dir: Path,
) -> None:
    """Write ranked trade ideas to JSON and TXT."""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"ideas_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── TXT ──
    lines = []
    lines.append("=" * 75)
    lines.append("Cross-Sectional Residual Momentum — Trade Ideas")
    lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M}")
    lines.append("Holding horizon: 1–3 months  |  Direction: LONG only")
    lines.append("=" * 75)
    lines.append(f"  {'Rank':<5}  {'Ticker':<8}  {'Score':>7}  {'P(take)':>8}  "
                 f"{'Entry':>10}  {'Stop':>10}  {'Target':>10}  {'Horizon':>8}")
    lines.append("  " + "-" * 70)
    for idea in ideas:
        lines.append(
            f"  {idea['rank']:<5}  {idea['ticker']:<8}  "
            f"{idea['signal_score']:>+7.3f}  "
            f"{idea['prob_take']:>8.1%}  "
            f"{idea['entry_price']:>10.2f}  "
            f"{idea['stop']:>10.2f}  "
            f"{idea['target']:>10.2f}  "
            f"{idea['horizon_days']:>5}d"
        )
    lines.append("=" * 75)
    lines.append("\nDISCLAIMER: For research and educational purposes only.")
    lines.append("Past backtests (even OOS) do not guarantee future performance.")
    txt = "\n".join(lines)
    (out_dir / f"{stem}.txt").write_text(txt)
    print(txt)

    # ── JSON ──
    (out_dir / f"{stem}.json").write_text(json.dumps(ideas, indent=2, default=str))
    print(f"\nIdeas written to: {out_dir}/{stem}.[txt|json]")
