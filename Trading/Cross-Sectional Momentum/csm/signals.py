"""Cross-sectional signal computation.

Primary signal: idiosyncratic (CAPM-residual) 12-1 momentum.
The spike (Stage 0) showed residual and naive are nearly equivalent on the
large-cap S&P 500 universe where all betas ≈ 1.  Both are exposed via config.
The meta-model arbitrates in meta-labeling (Stage 3).

Additional features for the meta-model:
  - 1-month reversal (known short-term predictor)
  - 52-week-high distance (George–Hwang 2004)
  - Idiosyncratic volatility
  - SPY regime features (trend, vol)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from csm.data import SIGNAL_EXCLUDE


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cross_z(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score per date (row)."""
    mu = df.mean(axis=1)
    sd = df.std(axis=1).replace(0, np.nan)
    return df.sub(mu, axis=0).div(sd, axis=0)

def _rolling_capm_beta(stocks: pd.DataFrame, mkt: pd.Series, window: int) -> pd.DataFrame:
    """Vectorised rolling CAPM beta for all stocks vs market (population formula)."""
    rm_mean  = mkt.rolling(window).mean()
    rs_mean  = stocks.rolling(window).mean()
    cov_num  = (stocks.multiply(mkt, axis=0)).rolling(window).mean() \
               - rs_mean.multiply(rm_mean, axis=0)
    var_m    = (mkt ** 2).rolling(window).mean() - rm_mean ** 2
    return cov_num.divide(var_m.replace(0, np.nan), axis=0)


def _log_ret(prices: pd.DataFrame) -> pd.DataFrame:
    # ffill(limit=3) handles genuine ≤3-day halts; fill_method=None ensures
    # longer gaps stay NaN (prevents phantom signals from stale tickers).
    return np.log1p(
        prices.ffill(limit=3).pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Primary momentum signals
# ─────────────────────────────────────────────────────────────────────────────

def residual_momentum(prices: pd.DataFrame, window: int = 252, skip: int = 21) -> pd.DataFrame:
    """Idiosyncratic 12-1 momentum: cumulative CAPM-residual / idio-vol.

    Citation: Blitz, Huij & Martens (2011).  Avoids momentum crashes because
    longs are low-beta outperformers rather than high-beta outperformers.
    """
    ret    = _log_ret(prices)
    mkt    = ret["SPY"]
    stocks = ret.drop(columns=SIGNAL_EXCLUDE, errors="ignore")

    beta     = _rolling_capm_beta(stocks, mkt, window)
    resid    = stocks - beta.multiply(mkt, axis=0)
    cum_full = resid.rolling(window).sum()
    cum_skip = resid.rolling(skip).sum()
    idio_vol = resid.rolling(window).std().replace(0, np.nan)
    return (cum_full - cum_skip) / idio_vol


def naive_momentum(prices: pd.DataFrame, window: int = 252, skip: int = 21) -> pd.DataFrame:
    """Standard 12-1 cross-sectional price momentum (raw cumulative return, skip last month)."""
    ret    = prices.ffill(limit=3).pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    stocks = ret.drop(columns=SIGNAL_EXCLUDE, errors="ignore")
    return stocks.rolling(window).sum() - stocks.rolling(skip).sum()


def fip_score(prices: pd.DataFrame, window: int = 252, skip: int = 21) -> pd.DataFrame:
    """Frog-in-the-Pan information continuity (Da, Gurun & Warachka), sign-flipped.

    Their information-discreteness measure is ID = sign(PRET) × (%neg − %pos)
    over the formation window; LOW ID (continuous small-step information flow)
    predicts stronger momentum continuation.  We return −ID = sign(PRET) ×
    (%pos − %neg), so HIGHER = better momentum candidate.  The day-sign balance
    is measured over the same 12-1 formation window as the momentum signal
    (skip the most recent month, look back the remaining ~11 months).
    """
    ret  = _log_ret(prices).drop(columns=SIGNAL_EXCLUDE, errors="ignore")
    w2   = window - skip
    # mean of sign(r) over the formation window ≈ %pos − %neg (zeros dilute both)
    sgn_mean = np.sign(ret.shift(skip)).rolling(w2, min_periods=int(w2 * 0.8)).mean()
    pret     = ret.rolling(window).sum() - ret.rolling(skip).sum()
    return np.sign(pret) * sgn_mean


def high52_proximity(prices: pd.DataFrame) -> pd.DataFrame:
    """George–Hwang (2004): current price relative to the 52-week high.

    Returns price/high − 1 (≤ 0); closer to 0 = nearer the high = stronger
    under-reaction anchor.  Both the rolling max and the current price are
    known at close t — no look-ahead.
    """
    px   = prices.drop(columns=SIGNAL_EXCLUDE, errors="ignore").ffill(limit=3)
    high = px.rolling(252, min_periods=200).max()
    return px / high - 1.0


def composite_signal(prices: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Equal-weight mean of cross-sectional z-scores: residual momentum + FIP
    continuity + 52-week-high proximity.

    Weights are fixed at equal by design (no weight optimization — that is a
    trial-mining trap).  A date/ticker needs a valid residual-momentum score to
    receive a composite score; FIP and 52wk-high fill in as available.
    """
    window = int(cfg.get("signal", {}).get("window", 252))
    skip   = int(cfg.get("signal", {}).get("skip",   21))

    z_rm = _cross_z(residual_momentum(prices, window=window, skip=skip))
    z_fp = _cross_z(fip_score(prices, window=window, skip=skip)).reindex_like(z_rm)
    z_hp = _cross_z(high52_proximity(prices)).reindex_like(z_rm)

    comp = pd.DataFrame(
        np.nanmean(np.stack([z_rm.values, z_fp.values, z_hp.values]), axis=0),
        index=z_rm.index, columns=z_rm.columns,
    )
    return comp.where(z_rm.notna())   # residual momentum is the required core


def primary_signal(prices: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Select residual, naive, or composite momentum per config key `signal.type`."""
    sig_type = cfg.get("signal", {}).get("type", "residual")
    window   = int(cfg.get("signal", {}).get("window", 252))
    skip     = int(cfg.get("signal", {}).get("skip",   21))
    if sig_type == "naive":
        return naive_momentum(prices, window=window, skip=skip)
    if sig_type == "composite":
        return composite_signal(prices, cfg)
    return residual_momentum(prices, window=window, skip=skip)


# ─────────────────────────────────────────────────────────────────────────────
#  Regime filter and vol-scaling overlays
# ─────────────────────────────────────────────────────────────────────────────

def spy_regime(prices: pd.DataFrame, ma_days: int = 200, vol_cap: float = 0.25) -> pd.Series:
    """Boolean Series: True = favorable regime for new longs.

    Daniel–Moskowitz (2016): suppress momentum when SPY < 200-dma AND vol is elevated.
    Long-only: we simply go to cash when regime = False rather than shorting.
    """
    spy   = prices["SPY"].ffill()
    above_ma = spy > spy.rolling(ma_days).mean()
    spy_ret  = spy.pct_change()
    real_vol = spy_ret.rolling(63).std() * np.sqrt(252)
    low_vol  = real_vol < vol_cap
    return above_ma | low_vol   # bad regime = below MA AND high vol


_ROBUST_REGIME_ASSETS = ["SPY", "EFA", "EEM", "AGG", "TLT", "RWR", "GLD"]


def robust_regime_exposure(prices: pd.DataFrame) -> pd.Series:
    """0/½/1 exposure from MIN(turbulence/absorption-ratio, slow-bleed) —
    the 2026-08-04 regime-robustness project's validated replacement for the
    SPY-trend/vol gate (see memory csm-regime-robustness-project).

    `regime_state.regime_state_exposure` (Kritzman turbulence + absorption
    ratio) catches ACUTE panics — extreme single-day moves, correlations
    spiking toward 1 (2008, COVID) — but was shown to miss slow, grinding
    declines (2022, dotcom) entirely. `slow_bleed.slow_bleed_exposure`
    (breadth below 200dma AND negative SPY absolute momentum) catches those
    instead but is weaker on acute panics. Combining via MIN(both) — go
    defensive if EITHER flags stress — was validated on real 2000-2026 data:
    it is the only tested variant with no catastrophic loss in ANY tested
    crisis window, and beats SPY buy-and-hold on Sharpe, MaxDD, and even its
    own worst rolling-12-month window over the full 26-year sample.

    Falls back to full exposure (1.0) wherever the 7-asset regime panel isn't
    fully available (e.g. before all tickers have real price history) — same
    fail-open convention as the VIX-contango check in `regime_exposure`.
    """
    from csm import regime_state as rs_mod
    from csm import slow_bleed as sb_mod

    avail = [c for c in _ROBUST_REGIME_ASSETS if c in prices.columns]
    if len(avail) < len(_ROBUST_REGIME_ASSETS):
        return pd.Series(1.0, index=prices.index)

    panel = prices[avail].ffill()
    turb_ar = rs_mod.regime_state_exposure(panel)
    bleed   = sb_mod.slow_bleed_exposure(panel)
    combined = pd.concat([turb_ar, bleed], axis=1).min(axis=1)
    return combined.reindex(prices.index).fillna(1.0)


def regime_exposure(prices: pd.DataFrame, cfg: dict) -> pd.Series:
    """Daily exposure multiplier in [0, 1] from the regime filter.

    mode "binary" (legacy) — spy_regime as a 0/1 gate: off only when SPY is
    below its 200-dma AND realized vol is elevated.

    mode "graded" — 0/½/1 from three point-in-time conditions:
      (a) SPY above its `spy_ma_days` MA        (slow bears, e.g. 2022)
      (b) SPY 63d realized vol below `vol_cap`  (sustained stress)
      (c) VIX term structure not inverted, ^VIX < ^VIX3M  (acute vol shocks,
          e.g. 2020, that the MA lags by weeks)
    3/3 → 1.0, 2/3 → 0.5, ≤1/3 → 0.0.  Graded exposure avoids the all-or-
    nothing whipsaw of the binary gate around the 200-dma.  Condition (c)
    fails OPEN where VIX history is missing so warmup dates aren't gated by
    absent data.  All inputs are closes known at t (decision executes t+1).

    mode "robust" — see `robust_regime_exposure`: MIN(turbulence/absorption
    ratio, slow-bleed breadth+momentum), validated on 2000-2026 data to beat
    SPY buy-and-hold with no catastrophic loss in any tested crisis.
    """
    reg_cfg = cfg.get("regime_filter", {})
    if not reg_cfg.get("enabled", True):
        return pd.Series(1.0, index=prices.index)

    mode = str(reg_cfg.get("mode", "binary"))
    if mode == "robust":
        return robust_regime_exposure(prices)

    ma_days = int(reg_cfg.get("spy_ma_days", 200))
    vol_cap = float(reg_cfg.get("vol_cap",    0.25))

    if mode != "graded":
        return spy_regime(prices, ma_days=ma_days, vol_cap=vol_cap).astype(float)

    spy      = prices["SPY"].ffill()
    above_ma = spy > spy.rolling(ma_days).mean()
    real_vol = spy.pct_change().rolling(63).std() * np.sqrt(252)
    low_vol  = real_vol < vol_cap
    if "^VIX" in prices.columns and "^VIX3M" in prices.columns:
        vix      = prices["^VIX"].ffill()
        vix3m    = prices["^VIX3M"].ffill()
        contango = (vix < vix3m) | vix.isna() | vix3m.isna()
    else:
        contango = pd.Series(True, index=prices.index)

    score = above_ma.astype(int) + low_vol.astype(int) + contango.astype(int)
    return pd.Series(np.select([score >= 3, score == 2], [1.0, 0.5], default=0.0),
                     index=prices.index)


def vol_scale_factor(portfolio_ret: pd.Series,
                     target_vol: float = 0.15,
                     window: int = 63) -> pd.Series:
    """Barroso–Santa-Clara (2015) volatility scaling.

    Returns a daily scalar [0, 2] that scales position size so realised vol
    tracks the target.  Apply to positions BEFORE execution lag.
    """
    real_vol = portfolio_ret.rolling(window).std() * np.sqrt(252)
    scale    = (target_vol / real_vol).clip(0.0, 2.0)
    return scale.fillna(1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Feature matrix for the meta-model (one row per (ticker, event_date))
# ─────────────────────────────────────────────────────────────────────────────

def build_features(prices: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Cross-sectional feature panel for meta-model training.

    Returns a wide DataFrame: rows = trading days, columns = (feature, ticker).
    The caller stacks this at (event_date, ticker) to feed the meta-model.
    """
    window = int(cfg.get("signal", {}).get("window", 252))
    ret    = prices.ffill(limit=3).pct_change().replace([np.inf, -np.inf], np.nan)
    log_r  = _log_ret(prices)
    mkt    = log_r["SPY"]
    stocks = ret.drop(columns=SIGNAL_EXCLUDE, errors="ignore")
    log_s  = log_r.drop(columns=SIGNAL_EXCLUDE, errors="ignore")

    # CAPM residuals for idio-vol
    beta    = _rolling_capm_beta(log_s, mkt, window)
    resid   = log_s - beta.multiply(mkt, axis=0)
    idio_v  = resid.rolling(window).std().replace(0, np.nan)

    high_52 = prices.drop(columns=SIGNAL_EXCLUDE, errors="ignore").rolling(252).max()
    dist_52 = prices.drop(columns=SIGNAL_EXCLUDE, errors="ignore") / high_52 - 1.0

    spy_ma200 = prices["SPY"] / prices["SPY"].rolling(200).mean() - 1.0
    spy_vol   = prices["SPY"].pct_change().rolling(63).std() * np.sqrt(252)

    # Assemble per-stock features as multi-level columns
    features = {
        "resid_mom"   : residual_momentum(prices, window=window, skip=21),
        "naive_mom"   : naive_momentum(prices, window=window, skip=21),
        "ret1m"       : -stocks.rolling(21).sum(),                   # short-term reversal (negative)
        "ret3m"       : stocks.rolling(63).sum(),
        "idio_vol"    : idio_v,
        "dist_52wk"   : dist_52,                                     # George–Hwang
        "beta"        : beta,
    }

    panels = {}
    for feat_name, df in features.items():
        panels[feat_name] = df

    # SPY regime features (broadcast across all stocks)
    n_stocks = len(stocks.columns)
    spy_feat = pd.DataFrame({
        "spy_ma200": spy_ma200,
        "spy_vol":   spy_vol,
    })
    # Don't include in the cross-sectional dict yet — caller receives panel per ticker

    return panels, spy_feat
