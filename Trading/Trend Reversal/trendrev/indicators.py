"""Technical indicators used by the strategies.

Every indicator here is **causal**: the value at bar ``t`` depends only on bars ``<= t``. The two
ZigZag implementations are the deliberate exception used to *demonstrate* repaint — ``zigzag_causal``
emits a reversal only on the bar where it is confirmed, while ``zigzag_repaint`` back-dates the
pivot the way ThinkScript's ``ZigZagHighLow`` does (look-ahead; for bias measurement only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- moving averages / vol
def ema(series: pd.Series, length: int) -> pd.Series:
    """Exponential moving average matching ThinkScript ``ExpAverage`` (alpha = 2/(n+1), SMA seed)."""
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, length: int = 14, wilder: bool = True) -> pd.Series:
    """Average True Range. Wilder smoothing (default) matches ThinkScript's ``ATR`` reference."""
    tr = true_range(df)
    if wilder:
        return tr.ewm(alpha=1 / length, adjust=False).mean()
    return tr.rolling(length).mean()


def rsi(series: pd.Series, length: int = 2) -> pd.Series:
    """Wilder's RSI (length 2 by default for the Connors mean-reversion strategy)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return (macd_line, signal_line, histogram)."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


# --------------------------------------------------------------------------- trend indicators
def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """SuperTrend (ATR bands with trend-following flip). Returns columns ``supertrend`` and ``dir``.

    ``dir`` is +1 in an uptrend, -1 in a downtrend. Fully causal: each band/flip uses only the
    current and prior bar.
    """
    hl2 = (df["high"] + df["low"]) / 2
    atr_ = atr(df, period)
    upper = hl2 + multiplier * atr_
    lower = hl2 - multiplier * atr_

    close = df["close"].values
    upper = upper.values
    lower = lower.values
    n = len(df)
    final_upper = np.full(n, np.nan)
    final_lower = np.full(n, np.nan)
    direction = np.ones(n)
    # Seed the bands so the recursive comparisons don't propagate NaN (which would pin dir to +1).
    final_upper[0] = upper[0]
    final_lower[0] = lower[0]

    for i in range(1, n):
        final_upper[i] = (
            upper[i]
            if (upper[i] < final_upper[i - 1]) or (close[i - 1] > final_upper[i - 1])
            else final_upper[i - 1]
        )
        final_lower[i] = (
            lower[i]
            if (lower[i] > final_lower[i - 1]) or (close[i - 1] < final_lower[i - 1])
            else final_lower[i - 1]
        )
        if np.isnan(final_upper[i - 1]):
            direction[i] = 1
        elif close[i] > final_upper[i - 1]:
            direction[i] = 1
        elif close[i] < final_lower[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]

    st = np.where(direction == 1, final_lower, final_upper)
    return pd.DataFrame({"supertrend": st, "dir": direction}, index=df.index)


def donchian(df: pd.DataFrame, length: int = 20):
    """Donchian channel using only *prior* bars (``shift(1)``) so a breakout is testable at close."""
    upper = df["high"].rolling(length).max().shift(1)
    lower = df["low"].rolling(length).min().shift(1)
    return upper, lower


# --------------------------------------------------------------------------- ZigZag (repaint demo)
def zigzag_causal(df: pd.DataFrame, pct: float = 5.0) -> pd.Series:
    """Causal ZigZag direction: flips to +1/-1 on the bar where a ``pct`` reversal is *confirmed*.

    This is the honest analogue of ThinkScript's reversal arrows: the signal exists only once price
    has actually moved ``pct`` percent off the running extreme, so it never uses future bars.
    Returns a series in {-1, +1}.
    """
    close = df["close"].values
    n = len(close)
    direction = np.ones(n)
    extreme = close[0]
    cur_dir = 1
    thr = pct / 100.0
    for i in range(n):
        price = close[i]
        if cur_dir == 1:
            extreme = max(extreme, price)
            if price <= extreme * (1 - thr):
                cur_dir = -1
                extreme = price
        else:
            extreme = min(extreme, price)
            if price >= extreme * (1 + thr):
                cur_dir = 1
                extreme = price
        direction[i] = cur_dir
    return pd.Series(direction, index=df.index, name="zz_causal")


def zigzag_repaint(df: pd.DataFrame, pct: float = 5.0) -> pd.Series:
    """Look-ahead ('repainting') ZigZag: assigns each bar the direction of its *final* leg.

    A leg is anchored at confirmed pivots, then the direction is back-filled to the pivot bar — i.e.
    the value at bar ``t`` can depend on bars ``> t``. This mirrors how the on-chart arrows shift
    after the fact. It exists ONLY to quantify the optimism that repaint injects; never trade it.
    Returns a series in {-1, +1}.
    """
    close = df["close"].values
    n = len(close)
    thr = pct / 100.0
    # Identify confirmed pivots, then label the segment leading up to each pivot with the leg sign.
    pivots = [0]
    cur_dir = 1
    extreme_idx = 0
    extreme = close[0]
    for i in range(n):
        price = close[i]
        if cur_dir == 1:
            if price > extreme:
                extreme, extreme_idx = price, i
            elif price <= extreme * (1 - thr):
                pivots.append(extreme_idx)
                cur_dir, extreme, extreme_idx = -1, price, i
        else:
            if price < extreme:
                extreme, extreme_idx = price, i
            elif price >= extreme * (1 + thr):
                pivots.append(extreme_idx)
                cur_dir, extreme, extreme_idx = 1, price, i
    pivots.append(n - 1)

    direction = np.ones(n)
    for a, b in zip(pivots[:-1], pivots[1:]):
        leg = 1 if close[b] >= close[a] else -1
        direction[a : b + 1] = leg  # back-fill the whole leg => look-ahead
    return pd.Series(direction, index=df.index, name="zz_repaint")
