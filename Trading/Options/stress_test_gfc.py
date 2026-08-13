#!/usr/bin/env python3
"""
Global Financial Crisis (2008-09) Stress Test for Bull Put Spread

Answers: how would the bull put spread (and its exit-parameter choices) have
performed through the GFC, the worst drawdown period in recent SPY history?

Method:
    1. Regenerates the synthetic options dataset for 2008-01-01..2009-12-31
       (real SPY prices + real ^VIX/^VIX3M/^VIX6M term structure from yfinance;
       ^VIX9D does not exist pre-2011, the generator's fallback handles it).
    2. Backtests several parameter sets over that window, including a
       vix_max sensitivity sweep to answer "what should the max VIX be".
    3. Reports Sharpe, Sortino, max DD, Calmar, win rate, profit factor, trades.

Usage:
    python stress_test_gfc.py            # generate data (if missing) + run all backtests
    python stress_test_gfc.py --no-gen   # skip data generation, reuse existing CSV

Output:
    data/processed/SPY_synthetic_options_2008-01-01_2009-12-31.csv
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
from src.data_fetchers.synthetic_generator import (
    SyntheticOptionsGenerator,
    synthetic_data_filename,
    load_sample_spy_options_data,
)
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import calculate_performance_metrics

GFC_START = "2008-01-01"
GFC_END = "2009-12-31"

# Parameter sets to stress: (label, entry override, exit override, max_risk_percent)
#   best     -> the in-sample Sharpe champion from the 2018-26 search (grid edges: 30d short, 8d wing, no vix gate)
#   exact    -> the user's 30 DTE / 20d short / 10d long with robust exits
#   robust   -> the 24d/10d corner with strong stability + modest DD
#   vixmax-N -> 'exact' with a stricter crisis filter (answers "what should max VIX be")
# 'dte_target' pins the entry expiration to the one closest to 30 DTE (window 30±5,
# mirroring the optimizer's 'dte' dimension). vix_max is the crisis gate being tested.
#
# 2026-08-09 width/delta decision -- 5 finalists from validate_finalists.py's IS/OOS walk-forward
# (2018-01-02..2026-07-09 on the skew/spread-corrected surface), added to see whether the delta and
# risk-budget choices that looked reasonable over 2018-2026 (no true crash of GFC's magnitude)
# survive the worst drawdown period in modern SPY history:
#   user_w5/user_w10 -> the user's original ask (0.20d short, $5 or $10 fixed wide)
#   prior_d08        -> this project's previously-"adopted" config (0.24d short / 0.08d long)
#   grid_w10/grid_d08-> the full-grid's nominal winners (0.30d short, $10 wide or 0.08d long)
SCENARIOS = [
    ("best",    {"dte_target": 30, "short_delta": 0.30, "long_delta": 0.08,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.45, "stop_loss": 0.50, "dte_min": 18}, 30),
    ("exact",   {"dte_target": 30, "short_delta": 0.20, "long_delta": 0.10,
                 "vix_min": 20, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.90, "dte_min": 22}, 30),
    ("robust",  {"dte_target": 30, "short_delta": 0.24, "long_delta": 0.10,
                 "vix_min": 20, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 30),
    ("vixmax-25", {"dte_target": 30, "short_delta": 0.20, "long_delta": 0.10,
                 "vix_min": 20, "vix_max": 25},
                {"profit_target": 0.60, "stop_loss": 0.90, "dte_min": 22}, 30),
    ("vixmax-30", {"dte_target": 30, "short_delta": 0.20, "long_delta": 0.10,
                 "vix_min": 20, "vix_max": 30},
                {"profit_target": 0.60, "stop_loss": 0.90, "dte_min": 22}, 30),
    ("user_w5",   {"dte_target": 30, "short_delta": 0.20, "strike_width": 5,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 15),
    ("user_w10",  {"dte_target": 30, "short_delta": 0.20, "strike_width": 10,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 15),
    ("user_d08",  {"dte_target": 30, "short_delta": 0.20, "long_delta": 0.08,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 20),
    ("user_d10",  {"dte_target": 30, "short_delta": 0.20, "long_delta": 0.10,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 20),
    ("prior_d08", {"dte_target": 30, "short_delta": 0.24, "long_delta": 0.08,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 20),
    ("prior_d10", {"dte_target": 30, "short_delta": 0.24, "long_delta": 0.10,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 20),
    ("grid_w10",  {"dte_target": 30, "short_delta": 0.30, "strike_width": 10,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 30),
    ("grid_d08",  {"dte_target": 30, "short_delta": 0.30, "long_delta": 0.08,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 15),
    ("grid_d10",  {"dte_target": 30, "short_delta": 0.30, "long_delta": 0.10,
                 "vix_min": 10, "vix_max": 35},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 15),
    # 2026-08-09: every scenario above gates NEW entries off at vix_max=35 -- but 30% of GFC
    # trading days had VIX>35 (concentrated exactly in Sep2008-Apr2009, the worst stretch), so
    # none of them actually test what happens if the strategy keeps opening new short-premium
    # positions as vol is exploding. "nogate" variants: same structures, vix_max=999 (effectively
    # unbounded) -- the genuine tail-risk test.
    ("grid_w10_nogate",  {"dte_target": 30, "short_delta": 0.30, "strike_width": 10,
                 "vix_min": 10, "vix_max": 999},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 30),
    ("grid_d08_nogate",  {"dte_target": 30, "short_delta": 0.30, "long_delta": 0.08,
                 "vix_min": 10, "vix_max": 999},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 15),
    ("grid_d10_nogate",  {"dte_target": 30, "short_delta": 0.30, "long_delta": 0.10,
                 "vix_min": 10, "vix_max": 999},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 15),
    ("prior_d10_nogate", {"dte_target": 30, "short_delta": 0.24, "long_delta": 0.10,
                 "vix_min": 10, "vix_max": 999},
                {"profit_target": 0.60, "stop_loss": 0.50, "dte_min": 22}, 20),
]


def gfc_config(capital: float = None) -> dict:
    """Base config with backtest + synthetic_data pointed at the GFC window."""
    with open("config/config.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    cfg["synthetic_data"]["start_date"] = GFC_START
    cfg["synthetic_data"]["end_date"] = GFC_END
    cfg["backtest"]["start_date"] = "2008-01-02"
    cfg["backtest"]["end_date"] = GFC_END
    if capital is not None:
        cfg["backtest"]["initial_capital"] = capital
    return cfg


def generate_gfc_data(cfg: dict, skip: bool = False) -> Path:
    """Build the GFC synthetic dataset (real SPY/VIX history) unless --no-gen."""
    out_path = Path("data/processed") / synthetic_data_filename(cfg)
    if skip and out_path.exists():
        print(f"Using existing dataset: {out_path}")
        return out_path
    if out_path.exists():
        print(f"Dataset already exists: {out_path} (reusing; use --no-gen to skip anyway)")
        return out_path

    print("\n" + "=" * 70)
    print("GENERATING GFC SYNTHETIC OPTIONS DATA (real SPY/VIX history, BS-priced chains)")
    print("=" * 70)
    sd = cfg["synthetic_data"]
    gen = SyntheticOptionsGenerator(
        symbol=sd["symbol"],
        risk_free_rate=0.04,
        dividend_yield=0.015,
        volatility_window=30,
        use_vix_for_iv=True,
    )
    gen.generate_historical_chains(
        start_date=sd["start_date"],
        end_date=sd["end_date"],
        include_weekly=True,
        max_dte=sd["max_dte"],
        save_to_csv=True,
        output_path=str(out_path),
    )
    return out_path


def run_scenario(cfg: dict, label: str, entry: dict, exit_: dict, risk_pct: float = 30) -> dict:
    """One bull-put backtest on the GFC window; returns key metrics."""
    c = copy.deepcopy(cfg)
    strat_cfg = c["strategies"]["bull_put_spread"]
    strat_cfg["entry"].update(entry)
    strat_cfg["exit"].update(exit_)
    c["position_sizing"]["max_risk_percent"] = risk_pct

    bt = OptopsyBacktester(c)
    strategy = BullPutSpread(strat_cfg)
    options_data = load_sample_spy_options_data(config=c)
    start, end = options_data["quote_date"].min(), options_data["quote_date"].max()
    underlying = fetch_spy_data(
        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    res = bt.run_backtest(strategy=strategy, options_data=options_data,
                          underlying_data=underlying, verbose=False)
    m = calculate_performance_metrics(res)
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
    }


def main() -> int:
    skip = "--no-gen" in sys.argv
    risk_override = None
    capital = None
    for a in sys.argv:
        if a.startswith("--risk-pct="):
            risk_override = float(a.split("=")[1])
        if a.startswith("--capital="):
            capital = float(a.split("=")[1])
    cfg = gfc_config(capital=capital)

    out = generate_gfc_data(cfg, skip=skip)

    print("\n" + "=" * 70)
    print("GFC (2008-01-02 .. 2009-12-31) BULL PUT SPREAD STRESS TEST")
    print(f"risk_override={risk_override}  capital={capital}")
    print("=" * 70)

    rows = []
    for label, entry, exit_, risk_pct in SCENARIOS:
        risk_pct = risk_override if risk_override is not None else risk_pct
        try:
            rows.append(run_scenario(cfg, label, entry, exit_, risk_pct))
            print(f"  ✓ {label}")
        except Exception as e:
            rows.append({"scenario": label, "error": str(e)})
            print(f"  ✗ {label}: {e}")

    df = pd.DataFrame(rows)
    if df["trades"].notna().any():
        print("\n" + df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    else:
        print("\n" + df.to_string(index=False))
    print("=" * 70)
    print("Context: SPY fell ~57% peak-to-trough (Oct 2007-Mar 2009); VIX spiked to 80.9 in")
    print("Nov 2008. A vix_max crisis gate skips the worst days; dte exits limit gamma risk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
