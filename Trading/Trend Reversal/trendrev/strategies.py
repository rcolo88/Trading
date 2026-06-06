"""Strategy signal generators.

Each strategy maps an OHLCV frame to a **target position** series in {-1, 0, +1}, where the value
at bar ``t`` is the position *decided at the close of bar ``t``*. The backtest engine
(:mod:`trendrev.backtest`) is responsible for entering that position at the next bar's open, so the
strategies here never need to worry about execution timing — they only express intent.

``trend_reversal`` is the faithful port of the ThinkScript "Trend Reversal" core (System A: the
EMA 9/14/21 ribbon state machine). The others are benchmarks for the bake-off.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind


# --------------------------------------------------------------------------- Trend Reversal (port)
def trend_reversal_frame(
    df: pd.DataFrame,
    superfast: int = 9,
    fast: int = 14,
    slow: int = 21,
    use_low_filter: bool = True,
) -> pd.DataFrame:
    """Compute every intermediate series of the Trend Reversal core, for plotting & inspection.

    Faithful to the ThinkScript: ``buy = EMA9>EMA14>EMA21 and low>EMA9`` latched until
    ``stopbuy = EMA9<=EMA14`` (symmetric for shorts). The ``buysignal``/``sellsignal`` columns are
    the latched 0/1 states that drive the chart's green/red bar colours.
    """
    c = df["close"]
    e9 = ind.ema(c, superfast)
    e14 = ind.ema(c, fast)
    e21 = ind.ema(c, slow)

    buy = (e9 > e14) & (e14 > e21)
    sell = (e9 < e14) & (e14 < e21)
    if use_low_filter:
        buy = buy & (df["low"] > e9)
        sell = sell & (df["high"] < e9)
    stopbuy = e9 <= e14
    stopsell = e9 >= e14

    buy = buy.values
    sell = sell.values
    stopbuy = stopbuy.values
    stopsell = stopsell.values
    n = len(df)
    buysignal = np.zeros(n)
    sellsignal = np.zeros(n)
    for i in range(1, n):
        buynow = buy[i] and not buy[i - 1]
        if buynow and not stopbuy[i]:
            buysignal[i] = 1
        elif buysignal[i - 1] == 1 and stopbuy[i]:
            buysignal[i] = 0
        else:
            buysignal[i] = buysignal[i - 1]

        sellnow = sell[i] and not sell[i - 1]
        if sellnow and not stopsell[i]:
            sellsignal[i] = 1
        elif sellsignal[i - 1] == 1 and stopsell[i]:
            sellsignal[i] = 0
        else:
            sellsignal[i] = sellsignal[i - 1]

    return pd.DataFrame(
        {
            "ema_fast": e9,
            "ema_mid": e14,
            "ema_slow": e21,
            "buysignal": buysignal,
            "sellsignal": sellsignal,
        },
        index=df.index,
    )


def trend_reversal(
    df: pd.DataFrame,
    superfast: int = 9,
    fast: int = 14,
    slow: int = 21,
    use_low_filter: bool = True,
    long_short: bool = True,
) -> pd.Series:
    """Target position from the Trend Reversal core: +1 in the green state, -1 in the red state."""
    f = trend_reversal_frame(df, superfast, fast, slow, use_low_filter)
    pos = pd.Series(0.0, index=df.index, name="trend_reversal")
    pos[f["buysignal"] == 1] = 1.0
    pos[f["sellsignal"] == 1] = -1.0
    if not long_short:
        pos = pos.clip(lower=0.0)
    return pos


# --------------------------------------------------------------------------- benchmark strategies
def supertrend(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0, long_short: bool = True
) -> pd.Series:
    d = ind.supertrend(df, period, multiplier)["dir"]
    pos = d.copy().astype(float)
    if not long_short:
        pos = pos.clip(lower=0.0)
    return pos.rename("supertrend")


def donchian_breakout(df: pd.DataFrame, length: int = 20, long_short: bool = True) -> pd.Series:
    upper, lower = ind.donchian(df, length)
    c = df["close"]
    raw = pd.Series(np.nan, index=df.index)
    raw[c > upper] = 1.0
    raw[c < lower] = -1.0
    pos = raw.ffill().fillna(0.0)
    if not long_short:
        pos = pos.clip(lower=0.0)
    return pos.rename("donchian")


def macd_trend(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, long_short: bool = True
) -> pd.Series:
    macd_line, signal_line, _ = ind.macd(df["close"], fast, slow, signal)
    pos = np.sign(macd_line - signal_line).fillna(0.0)
    if not long_short:
        pos = pos.clip(lower=0.0)
    return pos.rename("macd")


def dual_ma(df: pd.DataFrame, fast: int = 50, slow: int = 200, long_short: bool = True) -> pd.Series:
    f = ind.sma(df["close"], fast)
    s = ind.sma(df["close"], slow)
    pos = np.sign(f - s).fillna(0.0)
    if not long_short:
        pos = pos.clip(lower=0.0)
    return pos.rename("dual_ma")


def rsi2_meanreversion(
    df: pd.DataFrame,
    rsi_len: int = 2,
    trend_len: int = 200,
    exit_len: int = 5,
    lower: float = 10.0,
    upper: float = 90.0,
    long_short: bool = False,
) -> pd.Series:
    """Connors RSI(2) mean reversion with a long-term trend filter and SMA exit.

    Long when oversold above the trend MA; flat once price recovers above the short SMA. Shorting is
    optional and symmetric (off by default — shorting mean reversion is historically punishing).
    """
    c = df["close"]
    r = ind.rsi(c, rsi_len)
    trend = ind.sma(c, trend_len)
    exit_ma = ind.sma(c, exit_len)
    n = len(df)
    pos = np.zeros(n)
    cv, rv, tv, ev = c.values, r.values, trend.values, exit_ma.values
    for i in range(1, n):
        prev = pos[i - 1]
        if prev == 0:
            if cv[i] > tv[i] and rv[i] < lower:
                pos[i] = 1.0
            elif long_short and cv[i] < tv[i] and rv[i] > upper:
                pos[i] = -1.0
            else:
                pos[i] = 0.0
        elif prev > 0:
            pos[i] = 0.0 if cv[i] > ev[i] else 1.0
        else:
            pos[i] = 0.0 if cv[i] < ev[i] else -1.0
    return pd.Series(pos, index=df.index, name="rsi2")


def trend_reversal_long_target(
    df: pd.DataFrame,
    superfast: int = 9,
    fast: int = 14,
    slow: int = 21,
    use_low_filter: bool = True,
    profit_target: float | None = 0.10,
    exit_signal: str = "buy_end",
) -> pd.Series:
    """Long-only swing rule: buy the green signal, hold until a profit target OR a sell signal.

    Entry  : the Trend Reversal buy/green state turns on (``buysignal`` 0 -> 1).
    Exit    : whichever comes first —
              * ``profit_target`` reached: ``close >= entry_fill * (1 + profit_target)`` (set
                ``None`` to disable and exit on signal only), or
              * a sell signal — ``exit_signal='buy_end'`` exits when the green state ends
                (``buysignal`` -> 0, i.e. momentum down); ``exit_signal='sell_signal'`` waits for the
                red state (``sellsignal`` -> 1); ``exit_signal='hold'`` never exits on a signal at
                all (entry-timed buy & hold — used for the "enter on green, then hold" ablation).

    The profit target is evaluated on the **close** and filled at the **next open** (same convention
    as the engine), so the rule is fully causal — a slightly conservative stand-in for an intraday
    limit order. After a target exit it will not re-enter until a *fresh* green signal appears.
    """
    if exit_signal not in ("buy_end", "sell_signal", "hold"):
        raise ValueError("exit_signal must be 'buy_end', 'sell_signal' or 'hold'")
    frame = trend_reversal_frame(df, superfast, fast, slow, use_low_filter)
    buysig = frame["buysignal"].values
    sellsig = frame["sellsignal"].values
    op = df["open"].values
    cl = df["close"].values
    n = len(df)
    pos = np.zeros(n)
    state = 0
    entry_fill = np.nan
    for t in range(n):
        if state == 0:
            entry_trigger = buysig[t] == 1 and (t == 0 or buysig[t - 1] == 0)
            if entry_trigger and t + 1 < n:
                state = 1
                entry_fill = op[t + 1]
                pos[t] = 1.0
        else:
            hit_target = profit_target is not None and cl[t] >= entry_fill * (1 + profit_target)
            if exit_signal == "hold":
                sig_exit = False              # never exit on a signal — entry-timed buy & hold
            elif exit_signal == "sell_signal":
                sig_exit = sellsig[t] == 1     # exit only when a full red 'sell' paints
            else:  # "buy_end"
                sig_exit = buysig[t] == 0      # exit when the green/buy state ends
            if hit_target or sig_exit:
                state = 0
                pos[t] = 0.0
            else:
                pos[t] = 1.0
    return pd.Series(pos, index=df.index, name="tr_long_target")


def buy_and_hold(df: pd.DataFrame, **_) -> pd.Series:
    return pd.Series(1.0, index=df.index, name="buy_hold")


# Registry consumed by the bake-off script. Values are (callable, default_params).
REGISTRY: dict[str, tuple] = {
    "trend_reversal": (trend_reversal, {}),
    "supertrend": (supertrend, {}),
    "donchian": (donchian_breakout, {}),
    "macd": (macd_trend, {}),
    "dual_ma": (dual_ma, {}),
    "rsi2": (rsi2_meanreversion, {}),
    "buy_hold": (buy_and_hold, {}),
}
