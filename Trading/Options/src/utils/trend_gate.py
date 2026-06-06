"""Build a SPY Trend Reversal entry gate for the options backtester.

Reuses the indicator from the sibling **Trend Reversal** repo (single source of truth). The gate is
causal: an entry on day t is allowed only if the TR state KNOWN AT THE CLOSE OF t-1 matches the
requested regime (shift(1)), so there is no look-ahead. Pass the returned callable straight into
``OptopsyBacktester(config, entry_gate=...)``.

    gate = spy_trend_gate(end="2026-04-08", direction="bull")   # only enter on SPY 'green' days
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_TREND_REPO = Path(__file__).resolve().parents[3] / "Trend Reversal"
_STATE = {"bull": 1, "bear": -1, "neutral": 0}


def _trendrev():
    if str(_TREND_REPO) not in sys.path:
        sys.path.insert(0, str(_TREND_REPO))
    from trendrev import data as tr_data, strategies as tr_strat
    return tr_data, tr_strat


def spy_trend_state(end: str, start_warmup: str = "2005-01-01") -> pd.Series:
    """Daily TR System-A state on SPY: +1 green / -1 red / 0 neutral, lagged one day (causal)."""
    tr_data, tr_strat = _trendrev()
    spy = tr_data.get_ohlcv("SPY", start=start_warmup, end=end)
    frame = tr_strat.trend_reversal_frame(spy)
    state = pd.Series(0, index=spy.index)
    state[frame["buysignal"] == 1] = 1
    state[frame["sellsignal"] == 1] = -1
    return state.shift(1).fillna(0)


def spy_trend_gate(end: str, direction: str = "bull", start_warmup: str = "2005-01-01"):
    """Return ``callable(date) -> bool`` allowing a new entry only when SPY's lagged TR state matches.

    direction: 'bull' (green / uptrend), 'bear' (red / downtrend), or 'neutral' (no latched signal —
    the chop regime that neutral premium structures like iron condors prefer).
    """
    if direction not in _STATE:
        raise ValueError(f"direction must be one of {list(_STATE)}, got {direction!r}")
    state = spy_trend_state(end, start_warmup)
    days = set(state.index[state == _STATE[direction]].normalize())
    return lambda d: pd.Timestamp(d).normalize() in days
