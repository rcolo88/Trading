"""Cross-asset regime-state detectors — Kritzman & Li (2010) financial
turbulence and Kritzman/Li/Page/Rigobon (2011) absorption ratio.

Built to replace `signals.regime_exposure`'s binary/graded SPY-trend gate,
which this project's own 2026-08-04 testing showed FAILS on slow-grinding
bear markets: blending "SPY when regime-on, defensive rotation when
regime-off" using the old `above_ma OR low_vol` gate lost money through
dotcom, the GFC, and 2022 — the gate barely ever fires in those regimes (it
never triggered once in all of 2018). Both signals here are literature
thresholds/conventions, not fit to this backtest's data, so using them adds
no extra degrees of freedom to the search (same principle already applied to
Options/src/utils/regime.py's VIX-complex gates in this monorepo).

Asset panel: SPY, EFA, EEM, AGG, TLT, RWR, GLD — a 7-asset-class cross-section
(US equities, non-US equities, EM equities, US bonds, US long bonds, US real
estate, gold) chosen so every ticker has real Yahoo history by 2004-11-18,
giving a valid rolling estimate well before the 2007-2008 GFC. This is
deliberately a DIFFERENT, broader panel than `multiasset.DEFENSIVE_ROSTER`
(the rotation CANDIDATES) — this one's job is only to detect stress, not to
decide what to hold.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REGIME_ASSETS = ["SPY", "EFA", "EEM", "AGG", "TLT", "RWR", "GLD"]


def load_regime_panel(cache_dir: Path, end: str | None = None) -> pd.DataFrame:
    """Close-price panel for the 7-asset regime-state universe.

    Reuses RAAM's niche-ETF cache the same way `multiasset.load_defensive_panel`
    does — same cross-project `sys.path` reuse pattern.
    """
    import sys
    raam_root = Path(__file__).resolve().parents[2] / "RAAM"
    if str(raam_root) not in sys.path:
        sys.path.insert(0, str(raam_root))
    from raam import data as raam_data

    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    ohlc = raam_data.load_ohlc_panel(REGIME_ASSETS, start="auto", end=end, cache_dir=cache_dir)
    return raam_data.close_panel(ohlc)


def turbulence_index(returns: pd.DataFrame, window: int = 252,
                     min_periods: int | None = None) -> pd.Series:
    """Mahalanobis-distance financial turbulence (Kritzman & Li 2010).

    d_t = (r_t - mu)^T Sigma^-1 (r_t - mu) / n

    mu, Sigma are estimated from the TRAILING `window` days strictly BEFORE t
    (no look-ahead: today's return is never part of its own reference
    distribution). Spikes during genuine market stress — extreme moves,
    decoupling of normally-correlated assets, or convergence of normally-
    uncorrelated ones (all three happened in 2008).
    """
    min_periods = min_periods or window
    cols = list(returns.columns)
    n = len(cols)
    vals = returns[cols].values
    idx = returns.index
    out = np.full(len(idx), np.nan)

    for t in range(len(idx)):
        if t < min_periods:
            continue
        window_vals = vals[max(0, t - window):t]   # strictly before t
        row = vals[t]
        if np.isnan(row).any():
            continue
        valid_rows = ~np.isnan(window_vals).any(axis=1)
        if valid_rows.sum() < min_periods // 2:
            continue
        hist = window_vals[valid_rows]
        mu = hist.mean(axis=0)
        cov = np.cov(hist, rowvar=False)
        try:
            inv = np.linalg.pinv(cov)
        except np.linalg.LinAlgError:
            continue
        diff = row - mu
        out[t] = float(diff @ inv @ diff.T) / n

    return pd.Series(out, index=idx, name="turbulence")


def absorption_ratio(returns: pd.DataFrame, window: int = 500,
                     n_eigen: int | None = None,
                     min_periods: int | None = None) -> pd.Series:
    """Fraction of trailing-window variance explained by the top `n_eigen`
    eigenvectors of the return covariance matrix (Kritzman/Li/Page/Rigobon
    2011). High absorption = markets are tightly coupled / fragile (a shock
    anywhere propagates everywhere); this is the eigen-concentration signal
    that historically spiked BEFORE the 2008 drawdown, not just during it.

    `n_eigen` defaults to max(1, round(n_assets/5)) — the paper's own
    convention for how many components to retain, scaled to a small
    (n=7) asset panel. `window` defaults to 500 (~2yr), following the paper.
    """
    cols = list(returns.columns)
    n = len(cols)
    n_eigen = n_eigen or max(1, round(n / 5))
    min_periods = min_periods or window
    vals = returns[cols].values
    idx = returns.index
    out = np.full(len(idx), np.nan)

    for t in range(len(idx)):
        if t < min_periods:
            continue
        window_vals = vals[max(0, t - window):t]
        valid_rows = ~np.isnan(window_vals).any(axis=1)
        if valid_rows.sum() < min_periods // 2:
            continue
        hist = window_vals[valid_rows]
        cov = np.cov(hist, rowvar=False)
        eigvals = np.linalg.eigvalsh(cov)   # ascending
        total = eigvals.sum()
        if total <= 0:
            continue
        top = eigvals[-n_eigen:].sum()
        out[t] = float(top / total)

    return pd.Series(out, index=idx, name="absorption_ratio")


def standardized_shift(ar: pd.Series, short: int = 15, long: int = 252) -> pd.Series:
    """Kritzman's "standardized shift in the absorption ratio":
    (MA_short(AR) - MA_long(AR)) / std_long(AR) — a z-score-like measure of
    whether market coupling is acutely INCREASING (positive = risk-off signal)
    relative to its own recent history.
    """
    ma_short = ar.rolling(short, min_periods=max(1, short // 2)).mean()
    ma_long  = ar.rolling(long,  min_periods=long // 2).mean()
    sd_long  = ar.rolling(long,  min_periods=long // 2).std()
    return (ma_short - ma_long) / sd_long.replace(0, np.nan)


def regime_state_exposure(
    close:            pd.DataFrame,
    turb_window:      int = 252,
    ar_window:        int = 500,
    ar_short:         int = 15,
    ar_long:          int = 252,
    turb_pctile_cut:  float = 0.90,
    delta_ar_cut:     float = 1.0,
) -> pd.Series:
    """0/0.5/1 exposure ladder from turbulence + absorption-ratio shift —
    a drop-in replacement candidate for `signals.regime_exposure`.

    Two conditions, both literature thresholds (not fit to this data):
      (a) turbulence NOT in its own trailing top decile (`turb_pctile_cut`)
      (b) absorption-ratio standardized shift NOT above `delta_ar_cut` (1 std)
    2/2 -> 1.0 (risk-on), 1/2 -> 0.5, 0/2 -> 0.0 (risk-off) — same shape as
    `signals.regime_exposure`'s existing "graded" mode, just with cross-asset
    stress detectors instead of a single SPY-trend/vol rule.
    """
    ret = close.pct_change()
    turb = turbulence_index(ret, window=turb_window)
    ar   = absorption_ratio(ret, window=ar_window)
    d_ar = standardized_shift(ar, short=ar_short, long=ar_long)

    # Expanding percentile rank of turbulence vs its OWN trailing history —
    # "top decile" is relative to what this asset panel has seen so far, not
    # a fixed absolute level (turbulence's scale depends on n_assets and vol
    # regime, so a relative threshold is the honest, literature-consistent
    # choice — same principle as the Options VIX-rank gate in this monorepo).
    turb_pct = turb.expanding(min_periods=turb_window).rank(pct=True)

    calm_turb = turb_pct.isna() | (turb_pct < turb_pctile_cut)
    calm_ar   = d_ar.isna() | (d_ar < delta_ar_cut)

    score = calm_turb.astype(int) + calm_ar.astype(int)
    expo = pd.Series(np.select([score >= 2, score == 1], [1.0, 0.5], default=0.0),
                     index=close.index)
    return expo
