"""Indicator correctness and the central repaint property."""
import numpy as np
import pandas as pd

from trendrev import indicators as ind
from trendrev import strategies


def test_ema_matches_pandas(ohlcv):
    e = ind.ema(ohlcv["close"], 9)
    ref = ohlcv["close"].ewm(span=9, adjust=False).mean()
    assert np.allclose(e.values, ref.values)


def test_atr_positive(ohlcv):
    a = ind.atr(ohlcv, 14)
    assert (a.dropna() > 0).all()


def test_trend_reversal_does_not_repaint(ohlcv):
    """System A (EMA ribbon) must be causal: signals on closed bars never change when more future
    bars arrive. We recompute on progressively longer histories and require the overlap to match."""
    full = strategies.trend_reversal_frame(ohlcv)
    for cutoff in (300, 700, 1100):
        truncated = strategies.trend_reversal_frame(ohlcv.iloc[:cutoff])
        overlap = full.iloc[:cutoff][["buysignal", "sellsignal"]]
        assert np.array_equal(overlap.values, truncated[["buysignal", "sellsignal"]].values), (
            f"Trend Reversal state changed retroactively at cutoff {cutoff} — would be repaint."
        )


def test_zigzag_causal_is_causal(ohlcv):
    """The honest ZigZag is causal; the repainting one is NOT (it must differ from its own
    truncated recomputation), which is exactly the bias the demo exists to measure."""
    full_causal = ind.zigzag_causal(ohlcv)
    trunc_causal = ind.zigzag_causal(ohlcv.iloc[:800])
    assert np.array_equal(full_causal.iloc[:800].values, trunc_causal.values)

    full_repaint = ind.zigzag_repaint(ohlcv)
    trunc_repaint = ind.zigzag_repaint(ohlcv.iloc[:800])
    assert not np.array_equal(full_repaint.iloc[:800].values, trunc_repaint.values)


def test_supertrend_direction_values(ohlcv):
    st = ind.supertrend(ohlcv)
    assert set(np.unique(st["dir"])).issubset({-1.0, 1.0})


def test_positions_are_discrete(ohlcv):
    pos = strategies.trend_reversal(ohlcv, long_short=True)
    assert set(np.unique(pos.values)).issubset({-1.0, 0.0, 1.0})


def test_long_target_is_long_only_and_causal(ohlcv):
    """The swing rule never shorts (positions in {0,1}) and is causal: positions on past bars do not
    change when more future data arrives (the only future input is the next open used for the fill)."""
    pos = strategies.trend_reversal_long_target(ohlcv, profit_target=0.10)
    assert set(np.unique(pos.values)).issubset({0.0, 1.0})

    full = strategies.trend_reversal_long_target(ohlcv)
    trunc = strategies.trend_reversal_long_target(ohlcv.iloc[:800])
    assert np.array_equal(full.iloc[:799].values, trunc.iloc[:799].values)
