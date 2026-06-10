"""Data-quality gate for an options dataset before a backtest is allowed to trust it.

The whole point of moving off synthetic data is to get a real **volatility skew** (IV varies
across strikes within one expiration) and **term structure** (ATM IV varies across expirations).
A flat-IV synthetic chain fails both of these checks — which is exactly why its calendar Sharpe
was an artifact. Run this on any dataset before optimizing on it.

    opt_venv/bin/python -m src.data_fetchers.validate_chain SPY_real_options_2025-10-01_2026-06-08.csv
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

REQUIRED_COLS = [
    "quote_date", "underlying_symbol", "underlying_price", "expiration", "dte",
    "strike", "option_type", "bid", "ask", "delta",
]


def assert_chain_quality(df: pd.DataFrame, skew_min_unique: int = 4) -> List[str]:
    """Return a list of human-readable check results; raise AssertionError on any hard failure."""
    results: List[str] = []

    # 1. Schema — the columns _format_for_optopsy validates.
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    assert not missing, f"missing required columns: {missing}"
    results.append(f"schema: all {len(REQUIRED_COLS)} required columns present")

    # 2. Sanity — tradeable quotes.
    assert (df["ask"] >= df["bid"]).all(), "found ask < bid"
    assert (df["dte"] > 0).all(), "found dte <= 0"
    assert df["underlying_price"].notna().all(), "found rows with no underlying_price"
    results.append(f"sanity: ask>=bid, dte>0, underlying present ({len(df):,} rows)")

    # Pick the most-populated quote_date for the structural checks.
    sample_date = df["quote_date"].value_counts().idxmax()
    day = df[(df["quote_date"] == sample_date) & (df["option_type"] == "call")].copy()

    # 3. SKEW — within the nearest expiration, IV must vary across strikes.
    near_exp = day.loc[day["dte"] == day["dte"].min(), "expiration"].iloc[0]
    near = day[day["expiration"] == near_exp]
    n_iv = near["iv"].round(4).nunique() if "iv" in near else 0
    assert n_iv >= skew_min_unique, (
        f"no volatility skew: nearest expiration has only {n_iv} distinct IV value(s) across "
        f"{near['strike'].nunique()} strikes (flat-IV synthetic data looks like this)"
    )
    results.append(f"skew: {n_iv} distinct IVs across strikes on {pd.Timestamp(sample_date).date()} "
                   f"(exp {pd.Timestamp(near_exp).date()})")

    # 4. TERM STRUCTURE — ATM IV must vary across expirations.
    atm_iv = []
    for _exp, g in day.groupby("expiration"):
        row = g.iloc[(g["delta"] - 0.5).abs().argsort()[:1]]
        atm_iv.append(round(float(row["iv"].iloc[0]), 4))
    n_term = len(set(atm_iv))
    assert n_term >= 2, (
        f"no term structure: ATM IV is identical ({atm_iv}) across "
        f"{day['expiration'].nunique()} expirations (flat synthetic data looks like this)"
    )
    results.append(f"term structure: {n_term} distinct ATM IVs across expirations {sorted(atm_iv)}")

    return results


def main() -> int:
    from src.data_fetchers.synthetic_generator import _read_options_csv

    if len(sys.argv) < 2:
        print("usage: python -m src.data_fetchers.validate_chain <csv-in-data/processed | path>")
        return 2
    arg = sys.argv[1]
    path = Path(arg)
    if not path.exists():
        path = _PROJECT_ROOT / "data" / "processed" / arg
    df = _read_options_csv(path)

    print(f"\nValidating: {path.name}")
    try:
        for line in assert_chain_quality(df):
            print(f"  PASS  {line}")
        print("\n✅ Dataset is suitable for backtesting (real skew + term structure present).")
        return 0
    except AssertionError as exc:
        print(f"  FAIL  {exc}")
        print("\n❌ Dataset failed quality checks — do NOT trust backtest results on it.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
