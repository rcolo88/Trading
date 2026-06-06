"""Backtest engine: arithmetic, no-look-ahead, and cost accounting."""
import numpy as np
import pandas as pd

from trendrev import backtest, strategies


def test_engine_uses_only_prior_signal(ohlcv):
    """The held position over an interval must equal the *prior* bar's target (shift(1)), and the
    realized return must be exec_pos * open-to-open return minus costs — no peeking at the future."""
    target = strategies.trend_reversal(ohlcv)
    res = backtest.run_backtest(ohlcv, target, commission_bps=0.0, slippage_bps=0.0)

    expected_exec = target.shift(1).fillna(0.0)
    assert np.array_equal(res.exec_pos.values, expected_exec.values)

    interval_ret = ohlcv["open"].shift(-1) / ohlcv["open"] - 1.0
    expected = (expected_exec * interval_ret).fillna(0.0)
    expected.iloc[-1] = 0.0
    assert np.allclose(res.returns.values, expected.values, equal_nan=True)


def test_lookahead_foresight_is_blocked(ohlcv):
    """A target that 'knows' the current interval's sign should NOT capture that return, because the
    engine delays it one bar. Perfect-foresight applied to interval k only pays off if mis-aligned."""
    interval_ret = ohlcv["open"].shift(-1) / ohlcv["open"] - 1.0
    foresight = np.sign(interval_ret).fillna(0.0)  # cheating signal for interval k
    res = backtest.run_backtest(ohlcv, foresight, commission_bps=0.0, slippage_bps=0.0)
    # If the engine peeked, every interval would be positive (sum of |ret|). Assert it does not.
    theoretical_max = interval_ret.abs().sum()
    assert res.returns.sum() < 0.5 * theoretical_max


def test_buy_and_hold_matches_benchmark(ohlcv):
    """The buy&hold strategy has a one-bar entry delay (exec_pos = target.shift(1)), while
    benchmark_equity is invested from interval 0. They must coincide once both are fully invested,
    i.e. when each is rebased at interval 1."""
    res = backtest.run_backtest(ohlcv, strategies.buy_and_hold(ohlcv),
                                commission_bps=0.0, slippage_bps=0.0)
    strat = res.equity.iloc[1:] / res.equity.iloc[1]
    bench = res.benchmark_equity.iloc[1:] / res.benchmark_equity.iloc[1]
    assert np.allclose(strat.values, bench.values)


def test_costs_reduce_returns(ohlcv):
    target = strategies.trend_reversal(ohlcv)
    free = backtest.run_backtest(ohlcv, target, commission_bps=0.0, slippage_bps=0.0)
    costed = backtest.run_backtest(ohlcv, target, commission_bps=1.0, slippage_bps=5.0)
    assert costed.equity.iloc[-1] < free.equity.iloc[-1]


def test_trade_ledger_round_trips(ohlcv):
    target = strategies.trend_reversal(ohlcv)
    res = backtest.run_backtest(ohlcv, target)
    trades = res.trades
    assert {"entry_date", "exit_date", "side", "return_pct"}.issubset(trades.columns)
    assert (trades["side"].isin([-1, 1])).all()
    assert (trades["exit_date"] > trades["entry_date"]).all()
