"""The four Ranking Model components: (M) Absolute Momentum, (V) Volatility Model,
(C) Average Relative Correlation, (T) ATR Trend/Breakout System.

Formulas are transcribed directly from Giordano (2018) Sections III-V. Two
implementation choices the paper leaves underspecified are resolved here and
documented at the point of decision (search "RESOLVED AMBIGUITY"):

  1. The Volatility Model's daily variance input. The paper says the EWMA
     (lambda=0.943, "edited version of GARCH", per RiskMetrics) is "calculated
     on daily OHLC data" but never names the single-day variance proxy. We use
     Garman-Klass range variance (it is the standard way to make an OHLC-based
     — as opposed to close-only — variance estimate), exposed via
     `volatility.method` in config so close-to-close is a one-line swap.

  2. The ATR breakout bands ADD the Average True Range to both the Upper and
     Lower Band (confirmed by the paper's explicit formula and its own prose
     explaining this is deliberate: higher volatility should make the Lower
     Band MORE responsive, i.e. sit closer to price, not less). Implemented
     exactly as specified even though "Lower Band sits above the raw
     105-day-low" reads unusually for a "lower" band.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 4 months ~= 84 trading days at the paper's convention of 21 trading days/month.
DAYS_PER_MONTH = 21


def months_to_days(months: float, days_per_month: int = DAYS_PER_MONTH) -> int:
    return int(round(months * days_per_month))


# ─────────────────────────────────────────────────────────────────────────────
#  (M) Absolute Momentum — 4-month ROC on daily data
# ─────────────────────────────────────────────────────────────────────────────

def absolute_momentum(close: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rate of Change over `window` trading days: C_t / C_{t-window} - 1."""
    return close.div(close.shift(window)) - 1.0


# ─────────────────────────────────────────────────────────────────────────────
#  (V) Volatility Model — RiskMetrics EWMA (lambda=0.943) on OHLC, 10-day smoothed
# ─────────────────────────────────────────────────────────────────────────────

def _garman_klass_variance(o: pd.Series, h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    """Single-day range-based variance estimate (Garman & Klass 1980)."""
    log_hl = np.log(h / l)
    log_co = np.log(c / o)
    return 0.5 * log_hl ** 2 - (2.0 * np.log(2.0) - 1.0) * log_co ** 2


def _close_to_close_variance(o: pd.Series, h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    """Vanilla RiskMetrics daily variance proxy: squared close-to-close log return."""
    r = np.log(c / c.shift(1))
    return r ** 2


_VARIANCE_METHODS = {
    "garman_klass":    _garman_klass_variance,
    "close_to_close":  _close_to_close_variance,
}


def _ewma_vol(daily_var: pd.Series, lam: float = 0.943, min_periods: int = 21) -> pd.Series:
    """RiskMetrics recursion sigma^2_t = lambda*sigma^2_{t-1} + (1-lambda)*v_t.

    pandas' .ewm(alpha=a, adjust=False).mean() computes y_t = (1-a) y_{t-1} + a x_t,
    so alpha = (1 - lambda) reproduces the RiskMetrics recursion exactly.
    """
    var = daily_var.ewm(alpha=1.0 - lam, adjust=False, min_periods=min_periods).mean()
    return np.sqrt(var.clip(lower=0.0))


def volatility_model(
    ohlc:    pd.DataFrame,
    tickers: list[str],
    lam:     float = 0.943,
    method:  str = "garman_klass",
) -> pd.DataFrame:
    """Daily RiskMetrics-EWMA volatility per ticker (NOT yet the 10-day-smoothed variant)."""
    fn  = _VARIANCE_METHODS[method]
    out = {}
    for t in tickers:
        o, h, l, c = (ohlc[(f, t)].ffill(limit=3) for f in ("Open", "High", "Low", "Close"))
        out[t] = _ewma_vol(fn(o, h, l, c), lam=lam)
    return pd.DataFrame(out)


def smoothed_volatility(vol: pd.DataFrame, smooth_days: int = 10) -> pd.DataFrame:
    """The '10-day smoothed variant' the paper says is what's actually ranked."""
    return vol.rolling(smooth_days).mean()


# ─────────────────────────────────────────────────────────────────────────────
#  (C) Average Relative Correlation — 4-month avg pairwise correlation
# ─────────────────────────────────────────────────────────────────────────────

def _rolling_corr_pair(r_i: pd.Series, r_j: pd.Series, window: int) -> pd.Series:
    """Rolling population correlation (matches csm/signals.py's _rolling_capm_beta
    style: covariance/variance built from rolling means, not pandas' .corr())."""
    mean_i = r_i.rolling(window).mean()
    mean_j = r_j.rolling(window).mean()
    cov    = (r_i * r_j).rolling(window).mean() - mean_i * mean_j
    std_i  = np.sqrt((r_i ** 2).rolling(window).mean() - mean_i ** 2)
    std_j  = np.sqrt((r_j ** 2).rolling(window).mean() - mean_j ** 2)
    denom  = (std_i * std_j).replace(0, np.nan)
    return (cov / denom).clip(-1.0, 1.0)


def avg_relative_correlation(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """Each ticker's average pairwise correlation vs every OTHER ticker in `returns`.

    LOWER = more diversifying = better (rank-1-is-best convention, see ranking.py).
    A ticker not yet listed contributes all-NaN pairwise correlations, which are
    excluded from the average — the same pairwise-deletion behaviour as pandas'
    own .corr() — so an asset's avg-correlation is only ever computed against
    tickers that actually have return history over the window.

    O(N^2) in the number of tickers (a Python-level loop over every pair, each
    doing a full rolling computation over the WHOLE daily index) — fine for
    RAAM's native ~11-ticker universe (55 pairs), intractable for a large
    universe (e.g. S&P 1500's ~1000+ eligible names). See
    `avg_relative_correlation_at_dates` for that case.
    """
    tickers = list(returns.columns)
    sums    = {t: pd.Series(0.0, index=returns.index) for t in tickers}
    counts  = {t: pd.Series(0.0, index=returns.index) for t in tickers}
    for a in range(len(tickers)):
        for b in range(a + 1, len(tickers)):
            ti, tj = tickers[a], tickers[b]
            c     = _rolling_corr_pair(returns[ti], returns[tj], window)
            valid = c.notna()
            sums[ti]   = sums[ti]   + c.fillna(0.0)
            sums[tj]   = sums[tj]   + c.fillna(0.0)
            counts[ti] = counts[ti] + valid.astype(float)
            counts[tj] = counts[tj] + valid.astype(float)
    return pd.DataFrame({t: sums[t] / counts[t].replace(0, np.nan) for t in tickers})


def avg_relative_correlation_at_dates(
    returns: pd.DataFrame,
    window:  int,
    dates:   pd.DatetimeIndex,
) -> pd.DataFrame:
    """Same definition as `avg_relative_correlation` — each ticker's average
    pairwise correlation vs every other ticker, lower = better — but computed
    ONLY at `dates` (e.g. monthly rebalance dates) using pandas' vectorized,
    BLAS-backed `.corr()` (pairwise-complete-observation, same NaN handling as
    the brute-force version) instead of a per-PAIR Python loop over the daily
    index.

    `ranking.compute_total_rank` only ever reads Correlation at rebalance
    dates in the first place, so this loses no information the daily version
    provided — it just skips computing values nothing consumes. Existing for
    large-universe use (e.g. S&P 1500, ~1000+ tickers, where the O(N^2)
    per-pair daily version is not tractable); cross-validated against
    `avg_relative_correlation` on RAAM's own small universe before being
    trusted at scale (see raam_sp1500.py).
    """
    out = pd.DataFrame(np.nan, index=dates, columns=returns.columns)
    for d in dates:
        if d not in returns.index:
            continue
        window_ret = returns.loc[:d].tail(window)
        # Require the FULL window non-NaN, matching _rolling_corr_pair's
        # implicit min_periods=window (pandas .rolling(window).mean() default)
        # — a ticker with only a handful of days since listing must be
        # excluded here exactly as it is there, not given a noisy few-point
        # correlation pandas' pairwise-complete .corr() would otherwise happily
        # compute.
        cols = [c for c in window_ret.columns if window_ret[c].notna().sum() >= window]
        if len(cols) < 2:
            continue
        corr = window_ret[cols].corr()
        n = len(cols)
        avg = (corr.sum(axis=1) - 1.0) / (n - 1)   # exclude self-correlation (=1)
        out.loc[d, cols] = avg.values
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  (T) ATR Trend/Breakout System
# ─────────────────────────────────────────────────────────────────────────────

def _true_range(h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    prev_c = c.shift(1)
    return pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)


def _wilder_atr(h: pd.Series, l: pd.Series, c: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed ATR (RMA) — the paper cites Wilder (1978) directly."""
    tr = _true_range(h, l, c)
    return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def _breakout_state(
    h: pd.Series, l: pd.Series, c: pd.Series,
    atr_period: int, upper_lookback: int, lower_lookback: int,
) -> pd.Series:
    """Stateful +2/-2 trend flag for a single ticker.

    Upper Band = ATR(atr_period) + rolling max(Close, upper_lookback)
    Lower Band = ATR(atr_period) + rolling max(Low, lower_lookback)
    (ATR is ADDED to both bands — see module docstring.)

    Matches the paper's exact next-day mechanic: day t's High/Low is compared
    against the band as known at close of t-1; a breach changes the state
    EFFECTIVE t+1 (recorded here as state.iloc[i+1]), not at t itself — so
    state.iloc[i] never uses same-day information and is safe to use as the
    "known at close of day i" signal ranking.py ranks on.
    """
    atr   = _wilder_atr(h, l, c, atr_period)
    upper = atr + c.rolling(upper_lookback).max()
    lower = atr + l.rolling(lower_lookback).max()
    upper_prev = upper.shift(1)
    lower_prev = lower.shift(1)

    # numpy-backed indexing, not .iloc[i] scalar access — same math, but this
    # loop runs O(tickers x days) times (via atr_trend_breakout's per-ticker
    # call), so at S&P1500 scale (~1500 tickers x ~4000 days) the pandas
    # scalar-indexing overhead is worth avoiding. Verified bit-identical
    # against the prior .iloc-based version (see raam_sp1500.py regression
    # check / README).
    h_v, l_v = h.to_numpy(), l.to_numpy()
    up_v, dn_v = upper_prev.to_numpy(), lower_prev.to_numpy()
    n = len(c.index)
    state_v = np.full(n, np.nan)

    cur, started = -2.0, False
    for i in range(n):
        if not started:
            if not np.isnan(up_v[i]) and not np.isnan(dn_v[i]):
                started = True
            else:
                continue
        state_v[i] = cur
        hi, lo = h_v[i], l_v[i]
        up, dn = up_v[i], dn_v[i]
        if not np.isnan(hi) and not np.isnan(up) and hi > up:
            cur = 2.0
        elif not np.isnan(lo) and not np.isnan(dn) and lo < dn:
            cur = -2.0
    return pd.Series(state_v, index=c.index)


def atr_trend_breakout(
    ohlc: pd.DataFrame, tickers: list[str],
    atr_period: int = 42, upper_lookback: int = 63, lower_lookback: int = 105,
) -> pd.DataFrame:
    out = {}
    for t in tickers:
        h, l, c = (ohlc[(f, t)].ffill(limit=3) for f in ("High", "Low", "Close"))
        out[t] = _breakout_state(h, l, c, atr_period, upper_lookback, lower_lookback)
    return pd.DataFrame(out)


# ─────────────────────────────────────────────────────────────────────────────
#  Convenience wrapper — everything ranking.py needs, from config
# ─────────────────────────────────────────────────────────────────────────────

def compute_indicators(ohlc: pd.DataFrame, tickers: list[str], cfg: dict) -> dict[str, pd.DataFrame]:
    """Compute M, V (smoothed), C, T panels for `tickers` per config.indicators."""
    icfg = cfg.get("indicators", {})
    close = ohlc["Close"][tickers]
    ret   = close.ffill(limit=3).pct_change()

    mom_window  = months_to_days(float(icfg.get("momentum_months", 4)))
    corr_window = months_to_days(float(icfg.get("correlation_months", 4)))

    vcfg = icfg.get("volatility", {})
    vol_raw = volatility_model(
        ohlc, tickers,
        lam    = float(vcfg.get("lambda", 0.943)),
        method = str(vcfg.get("method", "garman_klass")),
    )
    vol_smoothed = smoothed_volatility(vol_raw, smooth_days=int(vcfg.get("smooth_days", 10)))

    tcfg = icfg.get("trend", {})
    T = atr_trend_breakout(
        ohlc, tickers,
        atr_period     = int(tcfg.get("atr_period", 42)),
        upper_lookback = int(tcfg.get("upper_lookback", 63)),
        lower_lookback = int(tcfg.get("lower_lookback", 105)),
    )

    return {
        "M": absolute_momentum(close, mom_window),
        "V": vol_smoothed,
        "C": avg_relative_correlation(ret, corr_window),
        "T": T,
    }
