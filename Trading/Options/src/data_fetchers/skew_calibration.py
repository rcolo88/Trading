"""Fit the equity skew shape used by SyntheticOptionsGenerator._iv_surface to real quotes.

The generator prices every contract as ``iv = base_vol * skew(m) * term(dte)`` where
``m = ln(strike/spot)``. ``base_vol`` (from VIX) and ``term`` (from the real
^VIX9D/^VIX/^VIX3M/^VIX6M complex) are both validated separately -- this module isolates and
refits ONLY the skew shape against real chains.

Method: for every (quote_date, dte) group that has a quote within |m|<=0.02 of the money (an
ATM anchor), compute the ratio skew_empirical(m) = iv(m) / iv_atm_anchor for every other quote in
that group. This ratio is EXACTLY 1 at the anchor by construction, so the fitted curve's
skew(0)=1 normalization is correct by construction too -- no separate per-group "level" needs to
be estimated or cancelled out. (An earlier version of this module used a within-(date,dte)
fixed-effects demean instead; that recovers the correct relative SHAPE but, because the analyzed
window is asymmetric around m=0 and different days quote different strikes, the panel is
unbalanced and the demeaned level does not actually correspond to skew(0)=1 -- verified by
regenerating a validation sample and finding synthetic put prices priced 30-80% too RICH despite
the shape "fitting" the data. Anchoring directly to each day's own ATM quote avoids that.)

The vol(K) surface is genuinely one continuous function of strike (put-call parity implies a
single implied vol per strike/expiry, independent of instrument type) -- but its curvature is NOT
symmetric around ATM: the low-strike (put) wing carries a crash-risk premium and is measurably
steeper than the high-strike (call) wing. So this module fits TWO quadratics -- ``skew_put(m)``
for m <= 0 and ``skew_call(m)`` for m >= 0 -- both anchored at skew(0) = 1 by construction, so the
piecewise curve is continuous. ``_iv_surface`` dispatches on the sign of m, not on option_type.

Ground truth: the 38 days of genuine Schwab/yfinance-sourced SPY chains logged by
data_collection/chain_logger.py and compiled by data_collection/compile_chains.py
(data/processed/SPY_real_options_2026-06-05_2026-08-07.csv, $1 strikes, real bid/ask) PLUS the
DoltHub 2021-2026 sample (data/processed/SPY_real_options_2021-01-01_2026-06-08.csv, sparser
strikes but 5+ years / multiple VIX regimes). Both already carry a computed `iv` column.

Usage:
    opt_venv/bin/python -m src.data_fetchers.skew_calibration --report
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED = _PROJECT_ROOT / "data" / "processed"

LIVE_CHAINS_FILE = PROCESSED / "SPY_real_options_2026-06-05_2026-08-07.csv"
DOLTHUB_FILE = PROCESSED / "SPY_real_options_2021-01-01_2026-06-08.csv"

# Fitting window: match the bull put's actual entry/exit DTE band. Equity skew is well known to
# flatten with tenor (short-dated skew is much steeper than 60+ DTE skew) — pooling a wider DTE
# range than the strategy trades would blend in a shape the strategy never actually prices against.
DTE_MIN, DTE_MAX = 20, 45
# How close to the money a quote must be to serve as that (date, dte)'s ATM anchor.
ANCHOR_M_ABS_MAX = 0.02

# Put wing: use OTM/near puts, m in [-0.20, 0.0] -- -0.20 covers roughly a 0.03-0.05 delta put at
# 30 DTE; deeper than that the near-zero bid genuinely does dominate the back-solved IV with noise.
PUT_M_MIN, PUT_M_MAX = -0.20, 0.0
# Call wing: the empirical curve is monotonic decreasing only out to about m=+0.065, then TURNS
# BACK UP on far-OTM, thinly-quoted (often penny-priced) calls -- a quadratic cannot fit "down
# then up" without pinning curvature at its upper bound trying to match both the near-ATM slope
# and the far tail at once. Fitting only the genuinely monotonic band gives a clean fit; beyond
# m=+0.06 the model EXTRAPOLATES rather than fits.
CALL_M_MIN, CALL_M_MAX = 0.0, 0.06


def _load_side(path: Path, m_min: float, m_max: float, option_type: str) -> pd.DataFrame:
    """Rows on ONE wing, each carrying its own (date, dte) group's ATM-anchor IV."""
    cols = ["quote_date", "underlying_price", "dte", "strike", "option_type", "bid", "ask", "iv"]
    df = pd.read_csv(path, usecols=cols)
    df = df[(df["dte"].between(DTE_MIN, DTE_MAX)) & (df["bid"] > 0) & (df["ask"] > df["bid"]) & (df["iv"] > 0)]
    df["m"] = np.log(df["strike"] / df["underlying_price"])
    df["grp"] = df["quote_date"].astype(str) + "_" + df["dte"].astype(str)

    anchors = df[df["m"].abs() <= ANCHOR_M_ABS_MAX]
    if anchors.empty:
        return pd.DataFrame(columns=["m", "ratio", "grp"])
    # If multiple quotes qualify as anchors (both option types, several near-ATM strikes), use the
    # single closest-to-the-money one per group -- least skew contamination in the anchor itself.
    anchors = anchors.loc[anchors.groupby("grp")["m"].apply(lambda s: s.abs().idxmin())]
    anchor_iv = anchors.set_index("grp")["iv"]

    side = df[(df["option_type"] == option_type) & (df["m"].between(m_min, m_max))].copy()
    side["iv_atm"] = side["grp"].map(anchor_iv)
    side = side.dropna(subset=["iv_atm"])
    side["ratio"] = side["iv"] / side["iv_atm"]
    return side[["m", "ratio", "grp"]]


def _fit_skew(df: pd.DataFrame, n_bins: int = 16) -> Tuple[float, float, int, float]:
    """Fit (slope, curv) in skew(m) = 1 - slope*m + curv*m^2 to BINNED medians of the
    ATM-anchored empirical skew ratio, weighted by bin count.

    Per-contract IV is noisy (bid/ask quantization, thin far-wing liquidity), and a handful of
    penny-quoted outliers can dominate a raw per-observation least squares. Binning by moneyness
    and fitting the (robust) median per bin — weighted by how many observations support it — is
    far less sensitive to that noise while still recovering the same underlying shape.
    """
    edges = np.linspace(df["m"].min(), df["m"].max(), n_bins + 1)
    df = df.copy()
    df["bin"] = pd.cut(df["m"], edges, include_lowest=True)
    df["log_ratio"] = np.log(df["ratio"].clip(lower=1e-4))
    binned = df.groupby("bin", observed=True).agg(
        m=("m", "median"), y=("log_ratio", "median"), n=("log_ratio", "size"))
    binned = binned[binned.n >= 20]

    m = binned["m"].to_numpy()
    y = binned["y"].to_numpy()
    w = np.sqrt(binned["n"].to_numpy())

    def residuals(params):
        slope, curv = params
        skew = np.clip(1.0 - slope * m + curv * m * m, 1e-4, None)
        return w * (y - np.log(skew))

    res = least_squares(residuals, x0=[1.0, 2.5], bounds=([0.0, 0.0], [10.0, 20.0]))
    rmse = float(np.sqrt(np.mean(res.fun ** 2)))
    return float(res.x[0]), float(res.x[1]), len(df), rmse


def _r_squared(df: pd.DataFrame, slope: float, curv: float, n_bins: int = 16) -> float:
    edges = np.linspace(df["m"].min(), df["m"].max(), n_bins + 1)
    df = df.copy()
    df["bin"] = pd.cut(df["m"], edges, include_lowest=True)
    df["log_ratio"] = np.log(df["ratio"].clip(lower=1e-4))
    b = df.groupby("bin", observed=True).agg(m=("m", "median"), y=("log_ratio", "median"), n=("log_ratio", "size"))
    b = b[b.n >= 20]
    w = np.sqrt(b["n"].to_numpy())
    skew = np.clip(1.0 - slope * b["m"].to_numpy() + curv * b["m"].to_numpy() ** 2, 1e-4, None)
    yhat = np.log(skew)
    y = b["y"].to_numpy()
    ss_res = np.sum(w * (y - yhat) ** 2)
    ss_tot = np.sum(w * (y - np.average(y, weights=w)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def _fit_side(m_min: float, m_max: float, option_type: str) -> dict:
    frames = []
    for path, label in [(LIVE_CHAINS_FILE, "live_chains"), (DOLTHUB_FILE, "dolthub")]:
        if not path.exists():
            continue
        d = _load_side(path, m_min, m_max, option_type)
        d["source"] = label
        frames.append(d)
    if not frames:
        raise FileNotFoundError("No real-chain source found for skew calibration.")
    raw = pd.concat(frames, ignore_index=True)
    if raw.empty:
        raise ValueError(f"No ATM-anchored rows for option_type={option_type}, m in [{m_min},{m_max}]")
    slope, curv, n, rmse = _fit_skew(raw)
    r2 = _r_squared(raw, slope, curv)
    return {"slope": slope, "curv": curv, "n_obs": n, "resid_rmse": rmse, "r2": r2,
            "n_raw": len(raw), "n_live": int((raw.source == "live_chains").sum()),
            "n_dolthub": int((raw.source == "dolthub").sum())}


def fit(report: bool = False) -> dict:
    put_fit = _fit_side(PUT_M_MIN, PUT_M_MAX, "put")
    call_fit = _fit_side(CALL_M_MIN, CALL_M_MAX, "call")

    if report:
        print(f"PUT wing  (m in [{PUT_M_MIN}, {PUT_M_MAX}]):  "
              f"n_raw={put_fit['n_raw']:,} ({put_fit['n_live']:,} live + {put_fit['n_dolthub']:,} dolthub)  "
              f"n_fit_bins={put_fit['n_obs']:,}")
        print(f"  slope={put_fit['slope']:.4f}  curv={put_fit['curv']:.4f}  "
              f"weighted_R2={put_fit['r2']:.4f}")
        print(f"CALL wing (m in [{CALL_M_MIN}, {CALL_M_MAX}]): "
              f"n_raw={call_fit['n_raw']:,} ({call_fit['n_live']:,} live + {call_fit['n_dolthub']:,} dolthub)  "
              f"n_fit_bins={call_fit['n_obs']:,}")
        print(f"  slope={call_fit['slope']:.4f}  curv={call_fit['curv']:.4f}  "
              f"weighted_R2={call_fit['r2']:.4f}")
        print()
        cur_slope, cur_curv = 1.00, 2.50
        print(f"Current generator (symmetric):  slope={cur_slope:.2f}  curv={cur_curv:.2f}")
        print(f"Fitted put wing:                 slope={put_fit['slope']:.2f}  curv={put_fit['curv']:.2f}")
        print(f"Fitted call wing:                slope={call_fit['slope']:.2f}  curv={call_fit['curv']:.2f}")
        print()
        for m in (-0.15, -0.10, -0.07, -0.05, -0.03, 0.0, 0.03, 0.05, 0.10, 0.15):
            old = 1.0 - cur_slope * m + cur_curv * m * m
            if m <= 0:
                new = 1.0 - put_fit["slope"] * m + put_fit["curv"] * m * m
            else:
                new = 1.0 - call_fit["slope"] * m + call_fit["curv"] * m * m
            print(f"  m={m:+.2f}  old_skew(symmetric)={old:.3f}  new_skew(piecewise)={new:.3f}  "
                  f"delta={100*(new/old-1):+.1f}%")

    return {
        "put_skew_slope": put_fit["slope"], "put_skew_curv": put_fit["curv"],
        "call_skew_slope": call_fit["slope"], "call_skew_curv": call_fit["curv"],
        "put_n_obs": put_fit["n_obs"], "put_r2": put_fit["r2"],
        "call_n_obs": call_fit["n_obs"], "call_r2": call_fit["r2"],
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--report", action="store_true")
    args = p.parse_args()
    fit(report=True)
