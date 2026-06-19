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


# ─────────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

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
    stocks = ret.drop(columns=["SPY"], errors="ignore")

    beta     = _rolling_capm_beta(stocks, mkt, window)
    resid    = stocks - beta.multiply(mkt, axis=0)
    cum_full = resid.rolling(window).sum()
    cum_skip = resid.rolling(skip).sum()
    idio_vol = resid.rolling(window).std().replace(0, np.nan)
    return (cum_full - cum_skip) / idio_vol


def naive_momentum(prices: pd.DataFrame, window: int = 252, skip: int = 21) -> pd.DataFrame:
    """Standard 12-1 cross-sectional price momentum (raw cumulative return, skip last month)."""
    ret    = prices.ffill(limit=3).pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    stocks = ret.drop(columns=["SPY"], errors="ignore")
    return stocks.rolling(window).sum() - stocks.rolling(skip).sum()


def primary_signal(prices: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Select residual or naive momentum per config key `signal.type`."""
    sig_type = cfg.get("signal", {}).get("type", "residual")
    window   = int(cfg.get("signal", {}).get("window", 252))
    skip     = int(cfg.get("signal", {}).get("skip",   21))
    if sig_type == "naive":
        return naive_momentum(prices, window=window, skip=skip)
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
    stocks = ret.drop(columns=["SPY"], errors="ignore")
    log_s  = log_r.drop(columns=["SPY"], errors="ignore")

    # CAPM residuals for idio-vol
    beta    = _rolling_capm_beta(log_s, mkt, window)
    resid   = log_s - beta.multiply(mkt, axis=0)
    idio_v  = resid.rolling(window).std().replace(0, np.nan)

    high_52 = prices.drop(columns=["SPY"], errors="ignore").rolling(252).max()
    dist_52 = prices.drop(columns=["SPY"], errors="ignore") / high_52 - 1.0

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
