"""Fit the time-varying ATM-IV/VIX ratio used by SyntheticOptionsGenerator's base_vol level.

The generator previously used a FIXED level model: base_vol = vix_scale*(vix/100) + vix_offset,
with vix_scale=0.95, vix_offset=0.015 (constants, calibrated once, undated). Real data shows the
true ratio (ATM IV / VIX) has moved materially over time -- it is not a constant:

    year:   2022    2023    2024    2025    2026 (partial)
    ratio:  1.042   1.071   0.963   0.875   0.907

A fixed ~0.95-1.0 level, applied uniformly, overprices ATM vol (and therefore inflates credit
collected on any net-short-premium structure, incl. bull put spreads) in 2024-2026 specifically --
exactly the years this project's OOS/recent-window results draw from. This module fits a smooth
LINEAR TREND in calendar time to the ratio (weighted by yearly sample count, since 2025-2026 have
far more observations than 2022-2023 -- an unweighted per-row fit would overweight the recent years
by sheer row count, defeating the point of capturing the FULL trend).

Ground truth: DoltHub 2021-2026 (excluding 2021 itself -- noisy, thin, its own std is ~5x every
other year's) + the 38-day live chain log. Same ATM definition as skew_calibration.py: option_type
call, |log-moneyness| < 0.02, dte 20-45.

LIMITATION (stated plainly, not glossed over): no options data exists anywhere in this project
before 2021, so nothing pins the level for 2008-2020. This module extrapolates FLAT (holds the
2022 value) for any date before the fitted window rather than projecting the trend further back --
the conservative choice, but still an assumption, not a fit. Backtest years 2008-2021 (which
includes the entire GFC stress-test window) should be read as best-effort, not validated.

Usage:
    opt_venv/bin/python -m src.data_fetchers.vol_level_calibration --report
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED = _PROJECT_ROOT / "data" / "processed"

LIVE_CHAINS_FILE = PROCESSED / "SPY_real_options_2026-06-05_2026-08-07.csv"
DOLTHUB_FILE = PROCESSED / "SPY_real_options_2021-01-01_2026-06-08.csv"

DTE_MIN, DTE_MAX = 20, 45
ATM_M_ABS_MAX = 0.02
FIT_START_YEAR = 2022  # 2021 excluded: thin, ~5x noisier std than any other year


def _load_atm() -> pd.DataFrame:
    frames = []
    for path in (DOLTHUB_FILE, LIVE_CHAINS_FILE):
        if not path.exists():
            continue
        df = pd.read_csv(path, usecols=[
            "quote_date", "underlying_price", "dte", "strike", "option_type", "vix", "iv",
        ])
        frames.append(df)
    if not frames:
        raise FileNotFoundError("No real-chain source found for vol-level calibration.")
    df = pd.concat(frames, ignore_index=True)
    df["m"] = np.log(df["strike"] / df["underlying_price"])
    atm = df[(df["option_type"] == "call") & (df["m"].abs() <= ATM_M_ABS_MAX) &
             (df["dte"].between(DTE_MIN, DTE_MAX)) & (df["vix"] > 0)].copy()
    atm["quote_date"] = pd.to_datetime(atm["quote_date"])
    atm = atm[atm["quote_date"].dt.year >= FIT_START_YEAR]
    atm["ratio"] = atm["iv"] / (atm["vix"] / 100.0)
    return atm


def fit(report: bool = False) -> dict:
    atm = _load_atm()
    yearly = atm.groupby(atm["quote_date"].dt.year).agg(ratio=("ratio", "median"), n=("ratio", "size"))

    yr = yearly.index.to_numpy(dtype=float)
    y = yearly["ratio"].to_numpy()
    w = np.sqrt(yearly["n"].to_numpy())  # weight by sqrt(sample count) per year, not raw count
    A = np.vstack([yr, np.ones_like(yr)]).T * w[:, None]
    slope, intercept = np.linalg.lstsq(A, y * w, rcond=None)[0]

    pred = intercept + slope * yr
    ss_res = float(np.sum(w * (y - pred) ** 2))
    ss_tot = float(np.sum(w * (y - np.average(y, weights=w)) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    if report:
        print(f"Years fit: {list(yearly.index)}  (n per year: {list(yearly.n)})")
        print(yearly.round(4).to_string())
        print(f"\nratio(year) = {intercept:.4f} + ({slope:.5f}) * year")
        print(f"weighted R^2 = {r2:.4f}\n")
        current_scale, current_offset = 0.95, 0.015
        for yv in [2018, 2020, 2022, 2023, 2024, 2025, 2026]:
            new_ratio = intercept + slope * max(yv, FIT_START_YEAR)
            old_ratio_at_vix20 = (current_scale * 0.20 + current_offset) / 0.20  # illustrative
            print(f"  {yv}: new ratio={new_ratio:.4f}  "
                  f"(old constant model's implied ratio ~{old_ratio_at_vix20:.4f} at vix=20)")
        print(f"\nLIMITATION: fit uses only {FIT_START_YEAR}-2026 data (no options quotes exist "
              f"before 2021 anywhere in this project). Years before {FIT_START_YEAR} are held FLAT "
              f"at the {FIT_START_YEAR} ratio ({intercept + slope*FIT_START_YEAR:.4f}) in the "
              f"generator, not extrapolated further -- best-effort, not validated.")

    return {"slope": float(slope), "intercept": float(intercept), "fit_start_year": FIT_START_YEAR,
            "r2": r2, "n_years": len(yearly)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--report", action="store_true")
    p.parse_args()
    fit(report=True)
