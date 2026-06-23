"""Walk-forward backtest orchestrator.

Splits the full history into in-sample and out-of-sample windows and evaluates
strictly on OOS via simulate_live — the SAME weekly-rebalance, hold-with-drift
engine the live `ideas` book uses.  The OOS equity curve is the headline result.
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from csm import signals as sig_mod
from csm import portfolio as port_mod


class BacktestResult(NamedTuple):
    net_ret:       pd.Series    # daily net strategy returns
    equity:        pd.Series    # cumulative equity (starts at 1.0)
    bench_ret:     pd.Series    # SPY daily returns
    bench_equity:  pd.Series    # SPY cumulative equity
    exec_pos:      pd.DataFrame # executed positions (after lag)
    label:         str          # 'primary' or 'meta-labeled'


def _equity(ret: pd.Series) -> pd.Series:
    return (1.0 + ret.fillna(0.0)).cumprod()


# ─────────────────────────────────────────────────────────────────────────────
#  Single-window backtest (no split)
# ─────────────────────────────────────────────────────────────────────────────

def run_primary_backtest(
    prices:  pd.DataFrame,
    cfg:     dict,
    pit_df:  pd.DataFrame | None = None,
    label:   str = "primary",
) -> BacktestResult:
    """Primary-signal-only backtest (no meta-labeling)."""
    signals = sig_mod.primary_signal(prices, cfg)
    pos     = port_mod.build_positions(signals, prices, cfg, pit_df=pit_df)
    net_ret = port_mod.portfolio_returns(pos, prices, cfg)

    exec_pos   = pos.shift(1).fillna(0.0)
    bench_ret  = prices["SPY"].pct_change().fillna(0.0)
    return BacktestResult(
        net_ret      = net_ret,
        equity       = _equity(net_ret),
        bench_ret    = bench_ret,
        bench_equity = _equity(bench_ret),
        exec_pos     = exec_pos,
        label        = label,
    )


def evaluate_oos_continuous(
    prices:    pd.DataFrame,
    cfg:       dict,
    oos_start: pd.Timestamp,
    pit_df:    pd.DataFrame | None = None,
    label:     str = "primary (OOS)",
) -> BacktestResult:
    """Primary backtest scored on OOS dates using a CONTINUOUS full-history signal.

    The signal/positions/returns are computed ONCE on the entire panel — each date
    uses only data up to that date (rolling windows look backward), so there is no
    look-ahead leakage — and only then sliced to the OOS window for reporting.

    This is the leak-free, realistic evaluation: at any live OOS date the signal
    legitimately sees all prior history (IS data is the past, available in real
    time).  It fixes the artifact in run_primary_backtest(oos_prices), which
    recomputes the signal on the OOS slice ALONE and so re-burns ~2×window days of
    warmup *inside* OOS — starving long-window configs and measuring them on a
    shorter, more recent, non-comparable tail (e.g. window=252 fell from a true
    OOS Sharpe ~0.88 to ~0.01 purely from this artifact).
    """
    signals  = sig_mod.primary_signal(prices, cfg)
    pos      = port_mod.build_positions(signals, prices, cfg, pit_df=pit_df)
    net_ret  = port_mod.portfolio_returns(pos, prices, cfg)
    exec_pos = pos.shift(1).fillna(0.0)
    bench    = prices["SPY"].pct_change().fillna(0.0)

    nr = net_ret.loc[oos_start:]
    br = bench.loc[oos_start:]
    return BacktestResult(
        net_ret      = nr,
        equity       = _equity(nr),
        bench_ret    = br,
        bench_equity = _equity(br),
        exec_pos     = exec_pos.loc[oos_start:],
        label        = label,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Weekly-rebalance, hold-with-drift simulation  (identical to live trading)
# ─────────────────────────────────────────────────────────────────────────────

def _cost_rate(cfg: dict) -> float:
    c = cfg.get("costs", {})
    return (float(c.get("commission_bps", 5)) + float(c.get("half_spread_bps", 5))) / 1e4


def _rebalance_dates(index: pd.DatetimeIndex, rebal_freq: int) -> pd.DatetimeIndex:
    """Rebalance every `rebal_freq` trading days, anchored at the first bar
    (same grid build_positions uses, so pos.loc[date] is a fresh target)."""
    mask = np.zeros(len(index), dtype=bool)
    mask[::rebal_freq] = True
    return index[mask]


def simulate_live(
    prices:        pd.DataFrame,
    cfg:           dict,
    pit_df:        pd.DataFrame | None,
    oos_start:     pd.Timestamp,
    label:         str = "primary (OOS)",
) -> BacktestResult:
    """Event-driven simulation of the *actual* live process.

    Every `rebal_freq` trading days, rebalance the whole book to the fresh target
    (top-quintile → equal-$ → vol-scale → regime gate — the SAME
    portfolio.target_book logic), then HOLD fixed shares and let the weights DRIFT
    until the next rebalance.  Costs are charged only on real rebalance turnover; a
    1-day execution lag is applied.

    This makes the backtest identical-by-construction to `ideas`/`target_book`:
    the same per-date book, chained weekly with realistic drift and costs.
    """
    stocks  = prices.drop(columns=["SPY"], errors="ignore")
    ret     = stocks.ffill(limit=3).pct_change().fillna(0.0)
    cols    = list(stocks.columns)

    signals = sig_mod.primary_signal(prices, cfg)
    pos     = port_mod.build_positions(signals, prices, cfg, pit_df=pit_df)  # start-anchor grid

    rebal_freq = int(cfg.get("portfolio", {}).get("rebal_freq", 5))
    all_rebal  = _rebalance_dates(prices.index, rebal_freq)
    rebal_set  = set(all_rebal)

    # Warm the book: begin at the last rebalance strictly before OOS so the
    # portfolio is already invested when the reported OOS window starts.
    before = all_rebal[all_rebal < oos_start]
    internal_start = before[-1] if len(before) else prices.index[0]
    sim_idx = prices.loc[internal_start:].index

    cost_rate = _cost_rate(cfg)
    h    = pd.Series(0.0, index=cols)   # dollar holdings per name
    cash = 1.0                          # equity starts at 1.0, fully in cash
    pending: pd.Series | None = None    # target weights to execute next bar (exec lag)
    cur_target = pd.Series(0.0, index=cols)   # stepwise held target (for honest turnover)

    eq_dates, eq_vals, exec_rows = [], [], []
    for i, date in enumerate(sim_idx):
        if i > 0:                                       # 1) drift with the market
            h = h * (1.0 + ret.loc[date].reindex(cols).fillna(0.0))
        E = float(h.sum() + cash)

        if pending is not None:                         # 2) execute yesterday's decision
            tgt_d = pending.reindex(cols).fillna(0.0) * E
            cost  = float((tgt_d - h).abs().sum()) * cost_rate
            cash  = E - float(tgt_d.sum()) - cost
            h     = tgt_d
            E     = float(h.sum() + cash)
            cur_target = pending.reindex(cols).fillna(0.0)
            pending = None

        eq_dates.append(date); eq_vals.append(E)        # 3) record
        exec_rows.append(cur_target.copy())

        if date in rebal_set:                           # 4) decide tomorrow's book
            w = pos.loc[date]
            w = w[w > 0.0]
            pending = w

    equity_full = pd.Series(eq_vals, index=pd.DatetimeIndex(eq_dates))
    net_full    = equity_full.pct_change().fillna(0.0)
    exec_full   = pd.DataFrame(exec_rows, index=pd.DatetimeIndex(eq_dates))

    nr    = net_full.loc[oos_start:]
    bench = prices["SPY"].pct_change().fillna(0.0).loc[oos_start:]
    return BacktestResult(
        net_ret      = nr,
        equity       = _equity(nr),
        bench_ret    = bench,
        bench_equity = _equity(bench),
        exec_pos     = exec_full.loc[oos_start:],
        label        = label,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Walk-forward backtest
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward(
    prices:       pd.DataFrame,
    cfg:          dict,
    pit_df:       pd.DataFrame | None = None,
    oos_frac:     float = 0.30,
) -> BacktestResult:
    """Walk-forward split: evaluate the strategy on the OOS period only.

    Simulates the ACTUAL live process on OOS — weekly rebalance to the fresh target
    book, hold shares with drift between, real turnover costs (see simulate_live).
    Identical-by-construction to the live `ideas`/`target_book` engine, so what you
    trade is exactly what is measured.
    """
    index   = prices.index
    n       = len(index)
    is_end  = index[int(n * (1 - oos_frac)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)

    if len(prices.loc[oos_start:]) < 63:
        raise ValueError(f"OOS window too short ({len(prices.loc[oos_start:])} days).  "
                         "Extend the backtest date range.")

    return simulate_live(prices, cfg, pit_df, oos_start, label="primary (OOS)")
