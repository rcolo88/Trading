#!/usr/bin/env python3
"""
Bull Put Spread - width x delta x risk-budget frontier.

Generalizes compare_strike_width.py (delta wing vs a single $5 width, one risk budget) into a
full grid so CAGR / max DD / Sharpe can be compared on equal footing instead of confounding
structure choice with leverage choice (every prior comparison in this project held
max_risk_percent fixed at 30%, which is what drives the ~-43% max drawdown seen everywhere, not
the wing choice).

Grid (fixed: dte_target=30, profit_target=0.60, stop_loss=0.50, dte_min=22, vix 10-35, $20k SPY):
    short_delta      in {0.16, 0.20, 0.24, 0.30}
    wing             in {w5, w10, w15, w20, w30 (fixed strike_width $), d10, d08 (long_delta)}
    max_risk_percent in {5, 10, 15, 20, 30}
    -> 4 x 7 x 5 = 140 runs

Usage:
    python compare_width_frontier.py                  # run the grid -> backtest_results/width_frontier.csv
    python compare_width_frontier.py --chart           # + charts/width_frontier.png (CAGR vs max DD)
    python compare_width_frontier.py --window 2024-26  # restrict to the 2024-01-02..2026-06-30 window
    python compare_width_frontier.py --cost-sensitivity  # finalists x fill_fraction x spread multiplier
"""

import sys
import os
import copy
import itertools
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yaml
import pandas as pd
import numpy as np

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

SHORT_DELTAS = [0.16, 0.20, 0.24, 0.30]

# (label, entry_overrides_beyond_short_delta)
WINGS = [
    ("w5",  {"strike_width": 5}),
    ("w10", {"strike_width": 10}),
    ("w15", {"strike_width": 15}),
    ("w20", {"strike_width": 20}),
    ("w30", {"strike_width": 30}),
    ("d10", {"long_delta": 0.10}),
    ("d08", {"long_delta": 0.08}),
]

RISK_PERCENTS = [5, 10, 15, 20, 30]

FIXED_ENTRY = {"dte_target": 30, "vix_min": 10, "vix_max": 35}
FIXED_EXIT = {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}

WINDOWS = {
    "full": ("2018-01-02", "2026-07-09"),
    "2024-26": ("2024-01-02", "2026-06-30"),
}


def base_config() -> dict:
    with open("config/config.yaml", "r") as f:
        return yaml.safe_load(f)


def run_scenario(cfg, short_delta, wing_label, wing_overrides, risk_pct,
                  options_data, underlying) -> dict:
    c = copy.deepcopy(cfg)
    strat_cfg = c["strategies"]["bull_put_spread"]
    strat_cfg["entry"].update(FIXED_ENTRY)
    strat_cfg["entry"]["short_delta"] = short_delta
    strat_cfg["entry"].update(wing_overrides)
    strat_cfg["exit"].update(FIXED_EXIT)
    c["position_sizing"]["max_risk_percent"] = risk_pct

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
        if "friction_pct_of_credit" in trades.columns:
            fpc = trades["friction_pct_of_credit"].dropna()
            stats["friction_pct_of_credit"] = fpc.mean() if len(fpc) else np.nan
        if "friction_dollars" in trades.columns:
            stats["total_friction_dollars"] = trades["friction_dollars"].sum()

    return {
        "short_delta": short_delta,
        "wing": wing_label,
        "max_risk_percent": risk_pct,
        "cagr_pct": m.get("annualized_return_pct"),
        "sharpe": m.get("sharpe_ratio"),
        "sortino": m.get("sortino_ratio"),
        "max_dd_pct": m.get("max_drawdown_pct"),
        "calmar": m.get("calmar_ratio"),
        "win_rate_pct": m.get("win_rate_pct"),
        "profit_factor": m.get("profit_factor"),
        "trades": m.get("total_trades"),
        "return_pct": m.get("total_return_pct"),
        **stats,
    }


def run_grid(cfg, options_data, underlying, window_name: str, short_deltas=None) -> pd.DataFrame:
    """short_deltas: restrict to a subset (for sharding the grid across parallel processes) --
    each shard writes its OWN csv (width_frontier_<window>_d<delta>.csv); merge separately."""
    win_start, win_end = WINDOWS[window_name]
    c = copy.deepcopy(cfg)
    c["backtest"]["start_date"] = win_start
    c["backtest"]["end_date"] = win_end
    od = options_data[
        (options_data["quote_date"] >= pd.Timestamp(win_start)) &
        (options_data["quote_date"] <= pd.Timestamp(win_end) + pd.Timedelta(hours=12))
    ].copy()

    deltas = short_deltas if short_deltas else SHORT_DELTAS
    combos = list(itertools.product(deltas, WINGS, RISK_PERCENTS))
    print(f"Running {len(combos)} backtests over window {window_name} "
          f"({win_start}..{win_end}), short_deltas={deltas} ...", flush=True)
    rows = []
    for i, (short_delta, (wing_label, wing_overrides), risk_pct) in enumerate(combos, 1):
        try:
            r = run_scenario(c, short_delta, wing_label, wing_overrides, risk_pct, od, underlying)
        except Exception as e:
            r = {"short_delta": short_delta, "wing": wing_label,
                 "max_risk_percent": risk_pct, "error": str(e)}
        rows.append(r)
        print(f"  [{i}/{len(combos)}] delta={short_delta} wing={wing_label} "
              f"risk%={risk_pct}  "
              f"{'FAIL: ' + r['error'] if 'error' in r else 'Sharpe=%.2f CAGR=%.1f%% DD=%.1f%% trades=%d' % (r['sharpe'] or 0, r['cagr_pct'] or 0, r['max_dd_pct'] or 0, r['trades'] or 0)}",
              flush=True)

    df = pd.DataFrame(rows)
    Path("backtest_results").mkdir(exist_ok=True)
    suffix = f"_d{deltas[0]}" if short_deltas and len(deltas) == 1 else ""
    out_csv = Path("backtest_results") / f"width_frontier_{window_name}{suffix}.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}  ({len(df)} rows)", flush=True)
    return df


def render_frontier_chart(df: pd.DataFrame, window_name: str) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path("charts") / f"width_frontier_{window_name}.png"
    os.makedirs("charts", exist_ok=True)

    # Degenerate trials (near-zero-variance equity curve on very few trades) can produce Sharpe
    # in the 1e15+ range -- exclude on |sharpe| alone (a real Sharpe never approaches this) rather
    # than trust total_trades, since the CSV here is a merged multi-shard file.
    d = df.dropna(subset=["cagr_pct", "max_dd_pct", "sharpe"])
    d = d[d["sharpe"].abs() < 10]

    wings = sorted(d["wing"].unique())  # fixed order -- color assigned once, never re-cycled per facet
    cmap = plt.get_cmap("tab10")
    colors = {w: cmap(i % 10) for i, w in enumerate(wings)}
    deltas = sorted(d["short_delta"].unique())

    # Small multiples: one panel per short_delta. Cramming all 4 deltas onto one axis (as an
    # earlier version of this chart did) conflated a 3rd data dimension into 2D lines and produced
    # a meaningless zigzag connecting unrelated deltas -- faceting is the fix, not more color.
    fig, axes = plt.subplots(1, len(deltas), figsize=(5.5 * len(deltas), 5.5), sharex=True, sharey=True)
    if len(deltas) == 1:
        axes = [axes]

    for ax, delta in zip(axes, deltas):
        sub_delta = d[d["short_delta"] == delta]
        for w in wings:
            sub = sub_delta[sub_delta["wing"] == w].sort_values("max_risk_percent")
            if sub.empty:
                continue
            ax.plot(sub["max_dd_pct"].abs(), sub["cagr_pct"], color=colors[w],
                    linewidth=1.2, alpha=0.6, zorder=2)
            ax.scatter(sub["max_dd_pct"].abs(), sub["cagr_pct"], color=colors[w],
                       s=45, edgecolor="#222", linewidth=0.5, zorder=3, label=w)
        ax.set_title(f"{delta}Δ short", fontsize=11, fontweight="bold")
        ax.set_xlabel("Max Drawdown % (abs)")
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("CAGR %")
    handles = [plt.Line2D([0], [0], color=colors[w], marker="o", lw=2, label=w) for w in wings]
    fig.legend(handles=handles, loc="lower center", ncol=len(wings), fontsize=9,
               bbox_to_anchor=(0.5, -0.04))
    fig.suptitle(f"CAGR vs Max Drawdown — bull put, {window_name} window\n"
                 "each point = one (wing, risk-budget) combination; line connects risk budgets 5-30%",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig.savefig(out, dpi=150, bbox_inches="tight")
    return out


def cost_sensitivity(cfg, options_data, underlying, window_name: str,
                      finalists: list) -> pd.DataFrame:
    """Rerun a short list of (short_delta, wing_label, wing_overrides, risk_pct) finalists across
    limit_fill_fraction x spread multiplier, to see whether the edge survives worse execution
    assumptions than the calibrated defaults."""
    win_start, win_end = WINDOWS[window_name]
    od = options_data[
        (options_data["quote_date"] >= pd.Timestamp(win_start)) &
        (options_data["quote_date"] <= pd.Timestamp(win_end) + pd.Timedelta(hours=12))
    ].copy()

    fill_fractions = [0.5, 0.75, 1.0]
    spread_multipliers = [1.0, 2.0, 3.0]
    rows = []
    for short_delta, wing_label, wing_overrides, risk_pct in finalists:
        for ff in fill_fractions:
            for sm in spread_multipliers:
                c = copy.deepcopy(cfg)
                c["backtest"]["start_date"] = win_start
                c["backtest"]["end_date"] = win_end
                c["position_sizing"]["max_risk_percent"] = risk_pct
                c["costs"]["limit_fill_fraction"] = ff
                strat_cfg = c["strategies"]["bull_put_spread"]
                strat_cfg["entry"].update(FIXED_ENTRY)
                strat_cfg["entry"]["short_delta"] = short_delta
                strat_cfg["entry"].update(wing_overrides)
                strat_cfg["exit"].update(FIXED_EXIT)

                od2 = od.copy()
                od2["bid"], od2["ask"] = _widen_spread(od2["bid"], od2["ask"], sm)

                bt = OptopsyBacktester(c)
                strategy = BullPutSpread(strat_cfg)
                try:
                    res = bt.run_backtest(strategy=strategy, options_data=od2,
                                           underlying_data=underlying, verbose=False)
                    m = calculate_performance_metrics(res)
                    rows.append({
                        "short_delta": short_delta, "wing": wing_label, "max_risk_percent": risk_pct,
                        "fill_fraction": ff, "spread_multiplier": sm,
                        "cagr_pct": m.get("annualized_return_pct"), "sharpe": m.get("sharpe_ratio"),
                        "max_dd_pct": m.get("max_drawdown_pct"), "trades": m.get("total_trades"),
                    })
                except Exception as e:
                    rows.append({"short_delta": short_delta, "wing": wing_label,
                                 "max_risk_percent": risk_pct, "fill_fraction": ff,
                                 "spread_multiplier": sm, "error": str(e)})
    df = pd.DataFrame(rows)
    out_csv = Path("backtest_results") / f"cost_sensitivity_{window_name}.csv"
    df.to_csv(out_csv, index=False)
    print(f"Saved: {out_csv}")
    return df


def _widen_spread(bid: pd.Series, ask: pd.Series, multiplier: float):
    mid = (bid + ask) / 2.0
    half = (ask - bid) / 2.0 * multiplier
    return (mid - half).clip(lower=0.01), mid + half


def main() -> int:
    cfg = base_config()
    print("Loading synthetic options data ...")
    options_data = load_sample_spy_options_data(config=cfg)
    print(f"  {len(options_data):,} rows, "
          f"{options_data['quote_date'].nunique()} trading days")
    print("Fetching SPY underlying (once) ...")
    underlying = fetch_spy_data("2018-01-02", "2026-07-10")
    print(f"  {len(underlying)} underlying rows")

    window_name = "full"
    if "--window" in sys.argv:
        window_name = sys.argv[sys.argv.index("--window") + 1]

    if "--cost-sensitivity" in sys.argv:
        # Same 5 pre-registered finalists as validate_finalists.py (2026-08-09 width/delta decision).
        # d08 dropped after the grid + full-span backtest both confirmed d10 beats d08 at every
        # delta tested -- no need to re-spend cost-sensitivity compute re-confirming that.
        finalists = [
            (0.20, "user_w5",   {"strike_width": 5},  15),
            (0.20, "user_w10",  {"strike_width": 10}, 15),
            (0.20, "user_d10",  {"long_delta": 0.10}, 20),
            (0.24, "prior_d10", {"long_delta": 0.10}, 20),
            (0.30, "grid_w10",  {"strike_width": 10}, 30),
            (0.30, "grid_d10",  {"long_delta": 0.10}, 15),
        ]
        cost_sensitivity(cfg, options_data, underlying, window_name, finalists)
        return 0

    short_deltas = None
    if "--short-delta" in sys.argv:
        short_deltas = [float(sys.argv[sys.argv.index("--short-delta") + 1])]

    df = run_grid(cfg, options_data, underlying, window_name, short_deltas=short_deltas)

    if "--chart" in sys.argv:
        chart = render_frontier_chart(df, window_name)
        print(f"Chart saved: {chart}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
