"""Out-of-sample evaluation for parameter optimization.

Optimizing and reporting the best Sharpe on the *same* window is how backtests lie: the winner is
fit to that period's noise. The honest check is to choose parameters on an in-sample (IS) window and
then score those *fixed* parameters on a held-out out-of-sample (OOS) window the search never saw.
A real edge survives the move from IS to OOS; an overfit one collapses.

This module is deliberately thin — it reuses `ParameterOptimizer._run_single_backtest` (and its
strategy-config mapping/validation) by building a per-window optimizer, so OOS scoring is identical
in semantics to IS scoring.
"""
from __future__ import annotations

import copy
from typing import Dict, Optional, Tuple

import pandas as pd

from ..backtester.optopsy_wrapper import OptopsyBacktester
from .parameter_optimizer import ParameterOptimizer

Window = Tuple[str, str]  # (start_date, end_date) as YYYY-MM-DD strings


def split_window(start: str, end: str, oos_fraction: float = 0.3) -> Tuple[Window, Window]:
    """Split [start, end] into (in-sample, out-of-sample) by trading days; OOS is the tail."""
    days = pd.bdate_range(start, end)
    if len(days) < 10:
        raise ValueError(f"window {start}..{end} too short to split ({len(days)} business days)")
    cut = int(round(len(days) * (1 - oos_fraction)))
    cut = min(max(cut, 1), len(days) - 1)
    is_window = (days[0].strftime("%Y-%m-%d"), days[cut - 1].strftime("%Y-%m-%d"))
    oos_window = (days[cut].strftime("%Y-%m-%d"), days[-1].strftime("%Y-%m-%d"))
    return is_window, oos_window


def _optimizer_for_window(
    base_config: Dict,
    strategy_type: str,
    strategy_class,
    options_data: pd.DataFrame,
    underlying_data: pd.DataFrame,
    window: Window,
    entry_gate=None,
) -> ParameterOptimizer:
    """A ParameterOptimizer whose backtester is pinned to `window` (same data, different dates)."""
    cfg = copy.deepcopy(base_config)
    cfg.setdefault("backtest", {})
    cfg["backtest"]["start_date"], cfg["backtest"]["end_date"] = window
    backtester = OptopsyBacktester(cfg, entry_gate=entry_gate)
    return ParameterOptimizer(
        strategy_type=strategy_type,
        strategy_class=strategy_class,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=cfg,
    )


def evaluate_params(
    base_config: Dict,
    strategy_type: str,
    strategy_class,
    options_data: pd.DataFrame,
    underlying_data: pd.DataFrame,
    window: Window,
    params: Dict,
    entry_gate=None,
) -> Dict:
    """Run a single backtest of `params` over `window`; return the performance metrics dict.

    Used to score IS-chosen parameters on the OOS window (and vice-versa) with identical semantics.
    """
    opt = _optimizer_for_window(
        base_config, strategy_type, strategy_class, options_data, underlying_data, window, entry_gate
    )
    try:
        return opt._run_single_backtest(params, verbose=False)
    except Exception as exc:  # e.g. no trades in the OOS window — report rather than crash
        return {"error": str(exc), "sharpe_ratio": float("nan"), "total_return_pct": float("nan")}
