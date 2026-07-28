"""Output reporting: JSON + human-readable TXT + equity PNG.

Mirrors csm/report.py's structure (backtest + ideas reports), with an added
paper-comparison table lining this run up against Giordano (2018) Figure 19.
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

from raam.backtest import BacktestResult
from raam.benchmarks import SALIENT_PUBLISHED
from raam.costs import turnover_stats
from raam.validation import compute_metrics


def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:+.1%}"


def _fmt_f(v, decimals: int = 3) -> str:
    if v is None:
        return "—"
    return f"{v:+.{decimals}f}"


# ─────────────────────────────────────────────────────────────────────────────
#  Backtest report
# ─────────────────────────────────────────────────────────────────────────────

def write_backtest_report(
    results:     dict[str, BacktestResult],
    dsr_result:  dict | None,
    pbo_result:  dict | None,
    mcpt_result: dict | None,
    out_dir:     Path,
    suffix:      str = "",
    mode:        str = "walk_forward",   # "walk_forward" | "full_sample"
) -> None:
    """Write the backtest report to TXT, JSON, and an equity-curve PNG."""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"backtest_{ts}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_all = {}
    for label, res in results.items():
        m = compute_metrics(res.net_ret, res.bench_ret)
        m.update(turnover_stats(res.exec_pos))
        metrics_all[label] = m

    lines = []
    lines.append("=" * 96)
    lines.append("RAAM — Ranked Asset Allocation Model — Backtest Report")
    lines.append(f"Mode: {mode}    Generated: {datetime.now():%Y-%m-%d %H:%M}")
    lines.append("=" * 96)

    lines.append(f"\n  {'Strategy':<38}{'Sharpe':>8}{'CAGR':>9}{'MaxDD':>9}{'DD(3m)':>9}"
                 f"{'AnnStd':>8}{'Calmar':>8}{'Ann.Turn':>10}")
    lines.append("  " + "-" * 92)
    for label, m in metrics_all.items():
        lines.append(
            f"  {label:<38}{_fmt_f(m['sharpe']):>8}{_fmt_pct(m['cagr']):>9}"
            f"{_fmt_pct(m['max_dd']):>9}{_fmt_pct(m['max_dd_3m']):>9}"
            f"{_fmt_pct(m['annualized_std']):>8}{_fmt_f(m['calmar']):>8}"
            f"{m['annual_turnover']:>9.1f}x"
        )
    if results:
        first = next(iter(results.values()))
        bm    = compute_metrics(first.bench_ret, first.bench_ret)
        lines.append(
            f"  {'SPY buy-and-hold':<38}{_fmt_f(bm['sharpe']):>8}{_fmt_pct(bm['cagr']):>9}"
            f"{_fmt_pct(bm['max_dd']):>9}{_fmt_pct(bm['max_dd_3m']):>9}"
            f"{_fmt_pct(bm['annualized_std']):>8}{'—':>8}{'—':>10}"
        )

    raam_key = next((k for k in metrics_all if k.startswith("RAAM")), None)
    if raam_key:
        rm = metrics_all[raam_key]
        lines.append("\n" + "─" * 96)
        lines.append("Paper comparison — Giordano (2018) Figure 19 vs this run")
        lines.append("  Paper: Jul-2004 -> Nov-2017, GROSS of all costs, undisclosed fitted")
        lines.append("  wM/wV/wC weights, and pre-2006 (DBC)/pre-2009 (IGOV) data filled by")
        lines.append("  interpolation. This run: real data only (no synthetic fill), equal")
        lines.append("  wM=wV=wC, net of commission+spread. See README for the full list.")
        lines.append("─" * 96)
        lines.append(f"  {'Stat':<24}{'Paper (RAAM)':>16}{'Paper (Salient)':>18}{'This run':>14}")
        sal = SALIENT_PUBLISHED
        rows = [
            ("Absolute performance",  None, sal["absolute_return"],    rm["absolute_performance"], "pct"),
            ("Annualized STD",        None, sal["annualized_std"],     rm["annualized_std"],        "pct"),
            ("Sharpe",                1.94, sal["sharpe"],             rm["sharpe"],                 "f"),
            ("Worst year",            None, sal["worst_year"],         rm["worst_year"],            "pct"),
            ("Best year",             None, sal["best_year"],          rm["best_year"],             "pct"),
            ("Worst month",           None, sal["worst_month"],        rm["worst_month"],           "pct"),
            ("Best month",            None, sal["best_month"],         rm["best_month"],             "pct"),
            ("Max DD (3-month)",      None, sal["max_drawdown_3m"],    rm["max_dd_3m"],              "pct"),
            ("Max DD (peak-trough)",  None, None,                       rm["max_dd"],                 "pct"),
        ]
        for name, praam, psal, ours, kind in rows:
            fmt = _fmt_f if kind == "f" else _fmt_pct
            lines.append(f"  {name:<24}{fmt(praam):>16}{fmt(psal):>18}{fmt(ours):>14}")
        lines.append("\n  (\"Paper (RAAM)\" is blank except Sharpe — the paper's Figure 18/19 only")
        lines.append("   reports RAAM's Sharpe explicitly; its other RAAM-specific stats aren't")
        lines.append("   tabulated in the source, only plotted. Paper's claimed RAAM Sharpe: 1.94,")
        lines.append("   gross, full-sample, fitted weights — not a bar this recreation targets.)")

    lines.append("\n─── Overfitting Tests ─────────────────────────────────────────────────")
    if dsr_result:
        icon = "PASS" if dsr_result["pass"] else "FAIL"
        lines.append(f"  [{icon}] Deflated Sharpe Ratio (DSR): {dsr_result['dsr']:.4f}  "
                     f"(threshold > 0.90)  [{dsr_result['n_trials']} configs tried]")
    if pbo_result:
        icon = "PASS" if pbo_result["pass"] else "FAIL"
        lines.append(f"  [{icon}] Probability of Backtest Overfitting (PBO): "
                     f"{pbo_result['pbo']:.3f}  (threshold < 0.50)")
    if mcpt_result:
        icon = "PASS" if mcpt_result["pass"] else "FAIL"
        lines.append(f"  [{icon}] Monte Carlo Permutation Test p-value: "
                     f"{mcpt_result['p_value']:.4f}  (threshold < 0.05)")
        lines.append(f"         Null: mean={mcpt_result['null_mean']:+.3f}  "
                     f"sigma={mcpt_result['null_std']:.3f}  95th pct={mcpt_result['null_95th']:+.3f}")

    lines.append("\n" + "=" * 96)
    txt = "\n".join(lines)
    (out_dir / f"{stem}.txt").write_text(txt)
    print(txt)

    payload = {
        "generated":         datetime.now().isoformat(),
        "mode":              mode,
        "metrics":           metrics_all,
        "salient_published": SALIENT_PUBLISHED,
        "dsr":               dsr_result,
        "pbo":               {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                              for k, v in (pbo_result or {}).items()},
        "mcpt":              {k: (v.tolist() if isinstance(v, np.ndarray) else v)
                              for k, v in (mcpt_result or {}).items()},
    }
    (out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2, default=str))

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

    ax.set_title("RAAM — Ranked Asset Allocation Model — Equity Curve", fontsize=13)
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
    book:    list[dict],
    header:  dict,
    trades:  dict,
    out_dir: Path,
) -> None:
    """Write the target portfolio book + rebalance trade list to JSON and TXT.

    `book` is the exact book the backtest engine holds today (n_select slots
    at fixed weight, cash-substituted per the Absolute Momentum filter) — not
    a truncated idea list. `header` carries slot/cash context; `trades`
    carries the BUY/SELL/RESIZE diff vs the previously held book.
    """
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"ideas_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    has_capital = header.get("capital") is not None

    lines = []
    lines.append("=" * 84)
    lines.append("RAAM — Ranked Asset Allocation Model — Target Portfolio Book")
    lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M}   |   As of month-end close: {header.get('as_of')}")
    lines.append("=" * 84)
    lines.append(f"  Slots filled:   {header.get('n_slots_filled', 0)} / {header.get('n_select', 5)}"
                 f"  ({header.get('n_cash_slots', 0)} in cash — negative momentum or no candidate)")
    lines.append(f"  Cash (SHY):     {header.get('cash_pct', 0.0):.1f}%")
    if has_capital:
        lines.append(f"  Capital:        ${header['capital']:,.0f}")
    lines.append(f"  Exit rule:      {header.get('exit_rule', '')}")
    if header.get("cadence_note"):
        lines.append(f"  Cadence:        {header['cadence_note']}")
    lines.append("=" * 84)

    if has_capital:
        lines.append(f"  {'Rank':<5}{'Ticker':<8}{'Sleeve':<32}{'Weight':>8}{'Buy $':>12}"
                     f"{'~Shares':>10}{'Close':>10}")
        lines.append("  " + "-" * 82)
        for r in book:
            lines.append(
                f"  {r['rank']:<5}{r['ticker']:<8}{r.get('sleeve', ''):<32}"
                f"{r['weight_pct']:>7.2f}% {r.get('dollars', 0):>11,.2f} "
                f"{r.get('shares', 0):>10.4f}{r['last_close']:>10.2f}"
            )
    else:
        lines.append(f"  {'Rank':<5}{'Ticker':<8}{'Sleeve':<32}{'Weight':>8}{'Close':>10}")
        lines.append("  " + "-" * 58)
        for r in book:
            lines.append(
                f"  {r['rank']:<5}{r['ticker']:<8}{r.get('sleeve', ''):<32}"
                f"{r['weight_pct']:>7.2f}% {r['last_close']:>10.2f}"
            )

    buys, sells, resizes = trades.get("buys", []), trades.get("sells", []), trades.get("resizes", [])
    lines.append("\n" + "─" * 84)
    lines.append("REBALANCE — changes vs your previously held book")
    lines.append("─" * 84)
    if not (buys or sells or resizes):
        lines.append("  (no changes — book matches your last run)")
    for t in sells:
        amt = f" ${t['dollars']:,.2f}" if t.get("dollars") is not None else ""
        lines.append(f"  SELL    {t['ticker']:<8}{amt}   (left the book -> close)")
    for t in buys:
        amt = f" ${t['dollars']:,.2f}" if t.get("dollars") is not None else ""
        lines.append(f"  BUY     {t['ticker']:<8}{amt}")
    for t in resizes:
        if t.get("delta_dollars") is not None:
            d    = t["delta_dollars"]
            verb = "ADD " if d > 0 else "TRIM"
            sign = "+" if d >= 0 else "-"
            lines.append(f"  {verb}    {t['ticker']:<8} {sign}${abs(d):,.2f}  "
                         f"(${t['from_dollars']:,.2f} -> ${t['to_dollars']:,.2f})")
        else:
            lines.append(f"  RESIZE  {t['ticker']:<8} {t['from_pct']:.2f}% -> {t['to_pct']:.2f}%")

    lines.append("=" * 84)
    lines.append("\nDISCLAIMER: For research and educational purposes only.")
    lines.append("Past backtests (even OOS) do not guarantee future performance.")
    txt = "\n".join(lines)
    (out_dir / f"{stem}.txt").write_text(txt)
    print(txt)

    payload = {"generated": datetime.now().isoformat(),
               "header": header, "book": book, "trades": trades}
    (out_dir / f"{stem}.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\nBook written to: {out_dir}/{stem}.[txt|json]")
