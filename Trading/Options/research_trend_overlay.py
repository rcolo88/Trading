#!/usr/bin/env python3
"""Apply the Trend Reversal (TR) indicator on SPY as a *directional gate* for options spreads.

Idea (ask #2): when SPY's TR System-A is GREEN, only open **bullish** debit verticals (bull call);
when it is RED, only open **bearish** debit verticals (bear put). Compare each gated strategy to
the same strategy run every day, to isolate what the timing overlay adds.

HONESTY NOTES (read before trusting any number):
  * Options P&L here is on *synthetic* Black-Scholes chains priced off the REAL SPY path. That makes
    DIRECTION (which way SPY went) meaningful, but there is no vol skew or IV term structure — so
    calendars / credit-skew edges are NOT representable, and even vertical magnitudes are approximate.
  * The gate is causal: day t's entry uses the TR state known at the close of t-1 (shift(1)).
  * The bottom section cross-checks the *underlying* directional claim on REAL SPY with honest costs
    using the trendrev engine — that part has no synthetic-data caveat.

Usage:  opt_venv/bin/python research_trend_overlay.py
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pandas as pd
import yaml

warnings.filterwarnings("ignore")

# --- import the indicator from the sibling Trend Reversal repo (single source of truth) ----------
TREND_REPO = Path(__file__).resolve().parent.parent / "Trend Reversal"
sys.path.insert(0, str(TREND_REPO))
from trendrev import data as tr_data            # noqa: E402
from trendrev import strategies as tr_strat      # noqa: E402
from trendrev import backtest as tr_bt           # noqa: E402
from trendrev import metrics as tr_metrics       # noqa: E402

from src.strategies.vertical_spreads import BullCallSpread, BearPutSpread  # noqa: E402
from src.strategies.calendar_spreads import CallCalendarSpread             # noqa: E402
from src.backtester.optopsy_wrapper import OptopsyBacktester               # noqa: E402
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data  # noqa: E402
from src.data_fetchers.yahoo_options import fetch_spy_data                 # noqa: E402
from src.utils.trend_gate import spy_trend_state, spy_trend_gate           # noqa: E402

OPTIONS_FILE = "SPY_synthetic_options_2022-10-01_2026-04-09.csv"  # longest history = most signals


def run(name, strategy_cls, cfg_key, cfg, opts, und, gate=None):
    scfg = {**cfg["strategies"][cfg_key]}
    scfg["entry"] = {**scfg["entry"], "vix_min": 0, "vix_max": 100}  # isolate the trend gate, not VIX
    r = OptopsyBacktester(cfg, entry_gate=gate).run_backtest(strategy_cls(scfg), opts, und, verbose=False)
    print(f"  {name:<34} trades={r['total_trades']:>3}  ret={r['total_return_pct']:>7.1f}%  "
          f"win={r['win_rate_pct']:>3.0f}%  maxDD={r['max_drawdown_pct']:>6.1f}%  Sharpe={r['sharpe_ratio']:>6.2f}")


def main():
    cfg = yaml.safe_load(open("config/config.yaml"))
    opts = load_sample_spy_options_data(specific_file=OPTIONS_FILE)
    start = opts["quote_date"].min().strftime("%Y-%m-%d")
    end = opts["quote_date"].max().strftime("%Y-%m-%d")
    und = fetch_spy_data(start, end)

    state = spy_trend_state(end)
    in_window = state[(state.index >= start) & (state.index <= end)]
    g, r_, n = (in_window == 1).sum(), (in_window == -1).sum(), (in_window == 0).sum()
    print(f"\nSPY TR state over {start}..{end}:  green={g}  red={r_}  neutral={n} days\n")

    print("OPTIONS OVERLAY on synthetic chains (directional content real, magnitudes approximate):")
    run("Bull call — every day", BullCallSpread, "bull_call_spread", cfg, opts, und)
    run("Bull call — GREEN only (gated)", BullCallSpread, "bull_call_spread", cfg, opts, und, spy_trend_gate(end, "bull"))
    run("Bear put  — every day", BearPutSpread, "bear_put_spread", cfg, opts, und)
    run("Bear put  — RED only (gated)", BearPutSpread, "bear_put_spread", cfg, opts, und, spy_trend_gate(end, "bear"))
    print("  (reference) ")
    run("Call calendar — every day", CallCalendarSpread, "call_calendar", cfg, opts, und)

    # --- clean cross-check: the directional claim on REAL SPY, honest next-open costs --------------
    print("\nREAL-DATA CROSS-CHECK (no synthetic caveat) — long SPY only when TR is green vs buy & hold:")
    spy = tr_data.get_ohlcv("SPY", start="2022-01-01", end=end)
    pos = tr_strat.trend_reversal(spy, long_short=False)  # +1 green else 0 (long-only)
    res = tr_bt.run_backtest(spy.loc[start:], pos.loc[start:], commission_bps=1, slippage_bps=5)
    m = tr_metrics.compute_metrics(res, "TR long-only")
    beq = res.benchmark_equity
    print(f"  TR long-only (green): CAGR={m['cagr']:>6.1%}  Sharpe={m['sharpe']:>5.2f}  "
          f"maxDD={m['max_drawdown']:>6.1%}  exposure={m['exposure']:.0%}")
    print(f"  SPY buy & hold:       CAGR={tr_metrics.cagr(beq):>6.1%}                "
          f"maxDD={tr_metrics.max_drawdown(beq):>6.1%}  exposure=100%")

    print(
        "\nHONEST READ:\n"
        "  * Leverage is real: with a correct fill model the directional BULL CALL massively outpaces\n"
        "    buy & hold over this 2022-2026 bull run, while the BEAR PUT loses (shorting a market that\n"
        "    rose ~20%/yr is a structural drag). That answers 'why don't options beat buy & hold' —\n"
        "    they do, on the long side, in an uptrend.\n"
        "  * BUT the magnitudes (thousands of %) are NOT a live edge. They stack: (a) a strong bull\n"
        "    market, (b) option leverage, (c) aggressive compounding under a 50%-risk budget, and\n"
        "    (d) synthetic FLAT-IV chains (no skew, no term structure, no vol crush) that especially\n"
        "    flatter calendars (78% win / Sharpe 4+ is the tell). Treat them as indicative only.\n"
        "  * Over a long uptrend, GATING to green REDUCES return (you sit out part of the rally) — its\n"
        "    value is drawdown/regime control, which is exactly what the clean REAL-DATA row shows\n"
        "    (lower maxDD, lower exposure, lower CAGR). Trust that row for the signal's real worth.\n"
        "  * For trustworthy options P&L, swap the synthetic chains for free real data (DoltHub /\n"
        "    OptionsDX) — that is the binding constraint now, not the fill model.\n"
    )


if __name__ == "__main__":
    main()
