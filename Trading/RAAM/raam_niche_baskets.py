"""Tests 3 proposed niche-ETF universes for RAAM's Total Rank mechanism, all
additive to the native 11 (7Twelve): sector SPDRs, dividend-focused ETFs, and
genuine low/negative-market-correlation "diversifier" funds (anti-beta, merger
arb, managed futures, gold miners, senior loans, convertibles) -- the ETFs
most likely to be actively rewarded by RAAM's own Volatility + Correlation
components in risk-off months, unlike simply adding more mutually-correlated
equity exposure (which is why the S&P1500 experiment failed).

Three baskets, same RAAM mechanism throughout (n_select=5, monthly, equal
wM=wV=wC, RAAM's own 10bps cost model, real-data availability mask -- no
synthetic backfill, no weight fitting):

  sectors_div_alt : native 11 + 11 sectors + 5 dividend + 10 alt  = 37 rankable
  alt_lean        : native 11 + 8 diversifiers + 3 sectors        = 22 rankable
  comprehensive   : native 11 + prior-20 expansion + sectors_div_alt's 26 = 57 rankable

Reuses raam_expanded_universe.py's already-generic make_expanded_eligible_fn
and build_expanded_positions as-is (both already take an arbitrary ticker
list) -- no changes to that file or to the validated raam/ package. One shared
OHLC download covers the union of all 3 baskets' tickers.

This is exploratory -- 3 more single-point trials, not DSR/PBO tested (three
points is too few for CSCV to mean anything) -- reported plainly regardless of
outcome, same discipline as every other result in this codebase.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from raam import backtest as bt_mod
from raam import data as data_mod
from raam import universe as univ_mod
from raam.costs import turnover_stats
from raam.validation import compute_metrics

from raam_expanded_universe import (
    NEW_ROSTER as PRIOR_20,
    make_expanded_eligible_fn,
    build_expanded_positions,
)

NICHE_CACHE_DIR = _HERE / "outputs" / "cache_niche"

SECTORS = [
    ("XLE",  "SECTOR - ENERGY"), ("XLF", "SECTOR - FINANCIALS"),
    ("XLK",  "SECTOR - TECHNOLOGY"), ("XLV", "SECTOR - HEALTH CARE"),
    ("XLI",  "SECTOR - INDUSTRIALS"), ("XLP", "SECTOR - CONSUMER STAPLES"),
    ("XLY",  "SECTOR - CONSUMER DISCRETIONARY"), ("XLU", "SECTOR - UTILITIES"),
    ("XLB",  "SECTOR - MATERIALS"), ("XLRE", "SECTOR - REAL ESTATE"),
    ("XLC",  "SECTOR - COMMUNICATION SERVICES"),
]
DIVIDEND = [
    ("RDIV", "DIVIDEND - ULTRA DIVIDEND REVENUE"), ("SPHD", "DIVIDEND - HIGH DIV LOW VOL"),
    ("SCHD", "DIVIDEND - US DIVIDEND EQUITY"), ("DVY", "DIVIDEND - SELECT DIVIDEND"),
    ("SDY",  "DIVIDEND - S&P DIVIDEND ARISTOCRATS"),
]
ALT_FULL = [
    ("BTAL", "ALT - ANTI-BETA MARKET NEUTRAL"), ("MNA", "ALT - MERGER ARBITRAGE"),
    ("DBMF", "ALT - MANAGED FUTURES"), ("GDX", "ALT - GOLD MINERS"),
    ("GDXJ", "ALT - JUNIOR GOLD MINERS"), ("AMLP", "ALT - MLP ENERGY INFRASTRUCTURE"),
    ("BKLN", "ALT - SENIOR LOANS"), ("CWB", "ALT - CONVERTIBLES"),
    ("SOXX", "ALT - SEMICONDUCTORS"), ("PGX", "ALT - PREFERRED STOCK"),
]
ALT_LEAN_DIVERSIFIERS = ALT_FULL[:8]   # BTAL..CWB, excludes SOXX/PGX (less genuinely diversifying)
ALT_LEAN_SECTORS = [("XLE", "SECTOR - ENERGY"), ("XLU", "SECTOR - UTILITIES"),
                    ("XLV", "SECTOR - HEALTH CARE")]

BASKETS: dict[str, list[tuple[str, str]]] = {
    "sectors_div_alt": SECTORS + DIVIDEND + ALT_FULL,
    "alt_lean":        ALT_LEAN_DIVERSIFIERS + ALT_LEAN_SECTORS,
    "comprehensive":   PRIOR_20 + SECTORS + DIVIDEND + ALT_FULL,
}


def load_config(path: Path = _HERE / "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def sleeve_lookup() -> dict[str, str]:
    """ticker -> category label, for the attribution report."""
    look = {t: univ_mod.SLEEVE[t] for t in univ_mod.RANKABLE}
    for roster in (PRIOR_20, SECTORS, DIVIDEND, ALT_FULL):
        for t, label in roster:
            look[t] = label
    look[univ_mod.CASH_TICKER] = "CASH"
    return look


def attribution(pos: pd.DataFrame, look: dict[str, str]) -> pd.Series:
    """% of (rebalance-date x slot) weight going to each category, over dates
    with any nonzero holding -- shows what the model actually used, not just
    what was available."""
    held = pos[pos > 0]
    cat_weight: dict[str, float] = {}
    for col in held.columns:
        cat = look.get(col, "UNKNOWN")
        cat_weight[cat] = cat_weight.get(cat, 0.0) + float(held[col].sum())
    s = pd.Series(cat_weight).sort_values(ascending=False)
    return s / s.sum()


def run_basket(name: str, roster: list[tuple[str, str]], ohlc: pd.DataFrame,
               close: pd.DataFrame, cfg: dict, look: dict[str, str]) -> dict:
    tickers = univ_mod.RANKABLE + [t for t, _ in roster]
    present = [t for t in tickers if t in close.columns]
    missing = [t for t in tickers if t not in close.columns]
    if missing:
        print(f"  [{name}] {len(missing)} tickers had no data — dropped: {missing}")

    eligible_fn = make_expanded_eligible_fn(present)
    pos = build_expanded_positions(ohlc, close, cfg, present, eligible_fn)
    rebal_dates_all = pos.index[pos.astype(bool).any(axis=1)]

    oos_frac = float(cfg.get("validation", {}).get("walk_forward_oos_frac", 0.30))
    index = close.index
    n = len(index)
    is_end = index[int(n * (1 - oos_frac)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)

    from raam import ranking as rank_mod
    rebal_dates = rank_mod.month_end_dates(close.index)

    res_oos = bt_mod.simulate_drift(pos, rebal_dates, close, cfg, oos_start,
                                    label=f"RAAM ({name})")
    m_oos = compute_metrics(res_oos.net_ret, res_oos.bench_ret)
    to_oos = turnover_stats(res_oos.exec_pos)

    attrib = attribution(pos.loc[oos_start:], look)

    return {
        "n_tickers": len(present), "sharpe": m_oos["sharpe"], "cagr": m_oos["cagr"],
        "max_dd": m_oos["max_dd"], "turnover": to_oos["annual_turnover"],
        "attribution": attrib, "oos_start": oos_start, "oos_end": close.index.max(),
    }


def main() -> None:
    cfg = load_config()
    end = pd.Timestamp.today().strftime("%Y-%m-%d")
    look = sleeve_lookup()

    all_new = sorted({t for roster in BASKETS.values() for t, _ in roster})
    fetch_tickers = univ_mod.RANKABLE + all_new + [univ_mod.CASH_TICKER, univ_mod.SPY]
    print(f"─── Union of all 3 baskets: {len(all_new)} new tickers "
          f"(+ native 11 + SHY + SPY = {len(fetch_tickers)} total) ───")
    ohlc = data_mod.load_ohlc_panel(fetch_tickers, start="auto", end=end,
                                    cache_dir=NICHE_CACHE_DIR)
    close = data_mod.close_panel(ohlc)

    print("\n  First real close per new ticker (thinner/newer names to watch):")
    for t in ["XLRE", "XLC", "GDXJ", "DBMF", "RDIV", "MNA", "BTAL"]:
        if t in close.columns:
            s = close[t].dropna()
            first = str(s.index.min().date()) if len(s) else "N/A"
            print(f"    {t:<6} {first}")
        elif t in all_new:
            print(f"    {t:<6} NO DATA — will be dropped")

    print(f"\n{'=' * 90}")
    results = {}
    for name, roster in BASKETS.items():
        print(f"─── Running basket: {name} ───")
        results[name] = run_basket(name, roster, ohlc, close, cfg, look)

    oos_start = next(iter(results.values()))["oos_start"]
    oos_end = next(iter(results.values()))["oos_end"]
    print(f"\n{'=' * 90}\nRAAM niche-ETF baskets — OOS {oos_start.date()} -> {oos_end.date()}\n{'=' * 90}")
    print(f"  {'Basket':22} {'#Tickers':>9} {'Sharpe':>8} {'CAGR':>8} {'MaxDD':>8} {'Turnover':>9}")
    print("  " + "-" * 70)
    for name, r in results.items():
        print(f"  {name:22} {r['n_tickers']:>9} {r['sharpe']:>8.3f} {r['cagr']:>+8.1%} "
              f"{r['max_dd']:>+8.1%} {r['turnover']:>8.1f}x")

    print(f"\n{'=' * 90}\nSleeve attribution — % of OOS holding-weight by category (what RAAM "
          f"actually used)\n{'=' * 90}")
    for name, r in results.items():
        print(f"\n  [{name}]")
        for cat, w in r["attribution"].head(10).items():
            print(f"    {cat:38} {w:>6.1%}")

    print(f"\n{'=' * 90}")
    print("  Caveat: 3 more exploratory single-point trials, not DSR/PBO-tested (three points\n"
          "  is too few for CSCV to be meaningful). Reported plainly regardless of outcome —\n"
          "  not a claim of validated improvement.")
    print("=" * 90)


if __name__ == "__main__":
    main()
