"""Walk-forward backtest orchestrator: monthly-rebalance, hold-with-drift
simulation. Same spirit as Cross-Sectional Momentum's simulate_live/
walk_forward — every rebalance date, execute the fresh target with a 1-day
lag, hold fixed dollar positions and let them drift with the market until the
next rebalance, charge costs only on real turnover — but on RAAM's month-end
calendar cadence instead of CSM's N-day stride, and generic over WHICH target-
weight panel it drives, so the identical drift/cost engine runs RAAM itself
and both benchmarks (apples-to-apples, one simulator).
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from raam import benchmarks as bench_mod
from raam import portfolio as port_mod
from raam import ranking as rank_mod
from raam import universe as univ_mod


class BacktestResult(NamedTuple):
    net_ret:       pd.Series     # daily net returns
    equity:        pd.Series     # cumulative equity (starts at 1.0)
    bench_ret:     pd.Series     # SPY daily returns (constant reference across all results)
    bench_equity:  pd.Series     # SPY cumulative equity
    exec_pos:      pd.DataFrame  # executed positions (post 1-day lag)
    label:         str


def _equity(ret: pd.Series) -> pd.Series:
    return (1.0 + ret.fillna(0.0)).cumprod()


def _cost_rate(cfg: dict) -> float:
    c = cfg.get("costs", {})
    return (float(c.get("commission_bps", 5)) + float(c.get("half_spread_bps", 5))) / 1e4


def simulate_drift(
    target:      pd.DataFrame,
    rebal_dates: pd.DatetimeIndex,
    close:       pd.DataFrame,
    cfg:         dict,
    start:       pd.Timestamp,
    label:       str = "RAAM",
) -> BacktestResult:
    """Event-driven month-end-rebalance, hold-with-drift simulation.

    `target` is a (T x cols) FRESH target-weight panel (already ffilled
    between rebalances by its builder — build_positions / core_7twelve /
    risk_parity_10vol); this function only handles execution timing, dollar
    drift, and turnover costs. Warms the book from the last rebalance strictly
    before `start` so it is already invested when the reported window begins.

    `close` must be the FULL price panel (including SPY) — SPY is used below
    for the benchmark line even when it isn't one of `target`'s own columns.
    """
    cols = list(target.columns)
    ret  = close[cols].ffill(limit=3).pct_change().fillna(0.0)

    rebal_set = set(rebal_dates)
    cost_rate = _cost_rate(cfg)

    before = rebal_dates[rebal_dates < start]
    internal_start = before[-1] if len(before) else close.index[0]
    sim_idx = close.loc[internal_start:].index

    h    = pd.Series(0.0, index=cols)   # dollar holdings per ticker
    cash = 1.0                          # equity starts at 1.0
    pending: pd.Series | None = None
    cur_target = pd.Series(0.0, index=cols)

    eq_dates, eq_vals, exec_rows = [], [], []
    for i, date in enumerate(sim_idx):
        if i > 0:                                        # 1) drift with the market
            h = h * (1.0 + ret.loc[date].reindex(cols).fillna(0.0))
        E = float(h.sum() + cash)

        if pending is not None:                          # 2) execute the prior decision
            tgt_d = pending.reindex(cols).fillna(0.0) * E
            cost  = float((tgt_d - h).abs().sum()) * cost_rate
            cash  = E - float(tgt_d.sum()) - cost
            h     = tgt_d
            E     = float(h.sum() + cash)
            cur_target = pending.reindex(cols).fillna(0.0)
            pending = None

        eq_dates.append(date); eq_vals.append(E)          # 3) record
        exec_rows.append(cur_target.copy())

        if date in rebal_set:                             # 4) decide the next book
            w = target.loc[date]
            w = w[w > 0.0]
            pending = w

    equity_full = pd.Series(eq_vals, index=pd.DatetimeIndex(eq_dates))
    net_full    = equity_full.pct_change().fillna(0.0)
    exec_full   = pd.DataFrame(exec_rows, index=pd.DatetimeIndex(eq_dates))

    nr    = net_full.loc[start:]
    bench = close[univ_mod.SPY].ffill(limit=3).pct_change().fillna(0.0).loc[start:]
    return BacktestResult(
        net_ret      = nr,
        equity       = _equity(nr),
        bench_ret    = bench,
        bench_equity = _equity(bench),
        exec_pos     = exec_full.loc[start:],
        label        = label,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Per-strategy runners
# ─────────────────────────────────────────────────────────────────────────────

def run_raam(ohlc: pd.DataFrame, close: pd.DataFrame, cfg: dict,
            start: pd.Timestamp, label: str = "RAAM (Total Rank)") -> BacktestResult:
    pos         = port_mod.build_positions_from_scratch(ohlc, close, cfg)
    rebal_dates = rank_mod.month_end_dates(close.index)
    return simulate_drift(pos, rebal_dates, close, cfg, start, label=label)


def run_core_7twelve(close: pd.DataFrame, cfg: dict,
                     start: pd.Timestamp, label: str = "Core 7Twelve (EW)") -> BacktestResult:
    rebal_dates = rank_mod.month_end_dates(close.index)
    pos         = bench_mod.core_7twelve(close, rebal_dates)
    return simulate_drift(pos, rebal_dates, close, cfg, start, label=label)


def run_risk_parity(close: pd.DataFrame, cfg: dict, start: pd.Timestamp,
                    label: str = "Risk Parity 10%vol (reconstructed)") -> BacktestResult:
    rebal_dates = rank_mod.month_end_dates(close.index)
    pos         = bench_mod.risk_parity_10vol(close, cfg)
    return simulate_drift(pos, rebal_dates, close, cfg, start, label=label)


# ─────────────────────────────────────────────────────────────────────────────
#  Walk-forward (headline) and full-sample (paper-comparable)
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward(ohlc: pd.DataFrame, close: pd.DataFrame, cfg: dict,
                 oos_frac: float = 0.30) -> dict[str, BacktestResult]:
    """Honest headline: RAAM vs the paper's own benchmark set, OOS only.

    All series share the SAME rebalance cadence, cost model, and OOS window,
    and RAAM's own ranking pipeline runs on the FULL history (no re-warmup
    inside OOS) before being sliced to the OOS tail — the same
    evaluate_oos_continuous fix csm/backtest.py applies, generalized here by
    computing everything once over the full panel and slicing at the end.
    """
    index  = close.index
    n      = len(index)
    is_end = index[int(n * (1 - oos_frac)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)

    if len(close.loc[oos_start:]) < 63:
        raise ValueError(f"OOS window too short ({len(close.loc[oos_start:])} days). "
                         "Extend the backtest date range.")

    return {
        "RAAM (Total Rank)":                  run_raam(ohlc, close, cfg, oos_start),
        "Core 7Twelve (EW)":                  run_core_7twelve(close, cfg, oos_start),
        "Risk Parity 10%vol (reconstructed)": run_risk_parity(close, cfg, oos_start),
    }


def full_sample(ohlc: pd.DataFrame, close: pd.DataFrame, cfg: dict,
                start: pd.Timestamp | None = None) -> dict[str, BacktestResult]:
    """Paper-comparable run over the full available (real-data-only) history."""
    if start is None:
        start = close.index[0]
    return {
        "RAAM (Total Rank)":                  run_raam(ohlc, close, cfg, start),
        "Core 7Twelve (EW)":                  run_core_7twelve(close, cfg, start),
        "Risk Parity 10%vol (reconstructed)": run_risk_parity(close, cfg, start),
    }
