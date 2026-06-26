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

import numpy as np
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


def evaluate_oos_continuous(
    base_config: Dict,
    strategy_type: str,
    strategy_class,
    options_data: pd.DataFrame,
    underlying_data: pd.DataFrame,
    full_window: Window,
    oos_start: str,
    params: Dict,
    entry_gate=None,
) -> Dict:
    """Score `params` out-of-sample the *honest* way: run ONE continuous backtest over the full
    IS+OOS window, then compute metrics from the OOS-date slice of its equity curve.

    This is standard walk-forward methodology (a single equity curve, evaluate its OOS segment) and
    it sidesteps a backtester quirk where an *isolated* OOS-only backtest drastically under-trades
    versus the same dates inside a continuous run (an early degenerate exit + low-capital position
    sizing starve the fresh short window — e.g. 1 trade isolated vs ~70 continuous). Sharpe is built
    on `total_value` pct-change, so it is scale-invariant: evaluating the OOS slice of the compounded
    curve is directly comparable to the IS Sharpe.
    """
    opt = _optimizer_for_window(
        base_config, strategy_type, strategy_class, options_data, underlying_data, full_window, entry_gate
    )
    try:
        res = opt._run_single_backtest(params, verbose=False, return_raw=True)
    except Exception as exc:  # report rather than crash
        return {"error": str(exc), "sharpe_ratio": float("nan"),
                "total_return_pct": float("nan"), "total_trades": 0}

    cut = pd.to_datetime(oos_start)
    eq = res["equity_curve"].copy()
    eq["date"] = pd.to_datetime(eq["date"])
    oos = eq[eq["date"] >= cut].reset_index(drop=True)

    trades = res.get("trades")
    if trades is not None and len(trades) and "entry_date" in trades.columns:
        td = trades.copy()
        td["entry_date"] = pd.to_datetime(td["entry_date"])
        n_oos_trades = int((td["entry_date"] >= cut).sum())
    else:
        n_oos_trades = 0

    if len(oos) < 3:
        return {"sharpe_ratio": float("nan"), "total_return_pct": float("nan"),
                "total_trades": n_oos_trades, "error": "insufficient OOS equity points"}

    # Same annualized excess-return Sharpe convention as the engine (rf = 2%).
    rets = oos["total_value"].pct_change().dropna()
    excess = rets - 0.02 / 252.0
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else float("nan")
    start_val, end_val = float(oos["total_value"].iloc[0]), float(oos["total_value"].iloc[-1])
    total_ret = (end_val - start_val) / start_val * 100.0 if start_val else float("nan")
    cummax = oos["total_value"].cummax()
    max_dd = float(((oos["total_value"] - cummax) / cummax).min() * 100.0)
    return {"sharpe_ratio": sharpe, "total_return_pct": total_ret,
            "total_trades": n_oos_trades, "max_drawdown_pct": max_dd}
