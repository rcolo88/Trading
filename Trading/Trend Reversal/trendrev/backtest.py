"""Vectorized, look-ahead-free backtest engine.

Execution model (identical for every strategy, per the project plan):

* A strategy's target position for bar ``t`` is decided using data through the **close of ``t``**.
* That position is entered at the **open of ``t+1``** — encoded as ``exec_pos = target.shift(1)``.
* Returns are measured **open-to-open** so the engine captures all price action between the bars at
  which we could actually trade, with no dependence on a bar's own future.
* Costs (commission + slippage, in basis points) are charged on the *change* in position at the
  open where the trade occurs.

Because the held position at the open of ``t`` derives only from the close of ``t-1``, the engine is
structurally incapable of look-ahead — a property the test suite asserts directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

PERIODS_PER_YEAR = 252


@dataclass
class BacktestResult:
    returns: pd.Series  # net strategy return per open-to-open interval
    equity: pd.Series  # cumulative equity, starts at 1.0
    exec_pos: pd.Series  # position actually held over each interval
    trades: pd.DataFrame  # one row per round-trip trade
    benchmark_equity: pd.Series  # buy & hold of the same instrument
    cost_rate: float = field(default=0.0)
    periods_per_year: int = field(default=PERIODS_PER_YEAR)


def run_backtest(
    df: pd.DataFrame,
    target_pos: pd.Series,
    commission_bps: float = 1.0,
    slippage_bps: float = 5.0,
    periods_per_year: int = PERIODS_PER_YEAR,
) -> BacktestResult:
    """Backtest a target-position series against ``df`` with next-open execution and costs.

    ``commission_bps`` + ``slippage_bps`` are one-way costs in basis points charged per unit of
    position change (a 0→1 entry costs one unit, a +1→-1 flip costs two).
    """
    target_pos = target_pos.reindex(df.index).fillna(0.0)
    open_ = df["open"]

    # Position held over the interval beginning at each bar's open (decided at the prior close).
    exec_pos = target_pos.shift(1).fillna(0.0)

    # Open-to-open return of the interval that *starts* at this bar's open.
    interval_ret = open_.shift(-1) / open_ - 1.0

    # Cost charged when the held position changes at this bar's open.
    cost_rate = (commission_bps + slippage_bps) / 1e4
    turnover = exec_pos.diff().abs().fillna(exec_pos.abs())
    costs = turnover * cost_rate

    gross = exec_pos * interval_ret
    net = (gross - costs).fillna(0.0)
    # Drop the final interval (no next open to realize it against).
    net.iloc[-1] = 0.0

    equity = (1.0 + net).cumprod()
    bench_ret = (open_.shift(-1) / open_ - 1.0).fillna(0.0)
    bench_ret.iloc[-1] = 0.0
    benchmark_equity = (1.0 + bench_ret).cumprod()

    trades = _build_trades(open_, exec_pos, cost_rate)

    return BacktestResult(
        returns=net,
        equity=equity,
        exec_pos=exec_pos,
        trades=trades,
        benchmark_equity=benchmark_equity,
        cost_rate=cost_rate,
        periods_per_year=periods_per_year,
    )


def equal_weight_returns(returns_by_ticker: dict[str, pd.Series]) -> tuple[pd.Series, pd.Series]:
    """Aggregate per-ticker interval returns into an equal-weight portfolio.

    Each name carries a fixed ``1/N`` sleeve; on a day a name's return is ``0`` it is simply in cash
    (the long-only overlay returns 0 when not green), so the average naturally rewards being
    diversified and de-risks when names go flat. Names with no data yet (pre-listing ``NaN``) are
    skipped that day rather than counted as zero. Returns ``(portfolio_returns, equity)``.
    """
    mat = pd.concat(returns_by_ticker.values(), axis=1, keys=returns_by_ticker.keys())
    port = mat.mean(axis=1)  # skipna=True: only names that exist that day are averaged
    port = port.fillna(0.0)
    equity = (1.0 + port).cumprod()
    return port, equity


def _build_trades(open_: pd.Series, exec_pos: pd.Series, cost_rate: float) -> pd.DataFrame:
    """Reconstruct round-trip trades from the executed-position path (entries/exits at the open)."""
    pos = exec_pos.values
    px = open_.values
    idx = open_.index
    rows = []
    entry_i = None
    side = 0
    for i in range(len(pos)):
        cur = pos[i]
        if cur != side:
            if side != 0 and entry_i is not None:  # close existing trade at this open
                ret = side * (px[i] / px[entry_i] - 1.0) - 2 * cost_rate
                rows.append(
                    dict(
                        entry_date=idx[entry_i],
                        exit_date=idx[i],
                        side=int(side),
                        entry_price=px[entry_i],
                        exit_price=px[i],
                        bars=i - entry_i,
                        return_pct=ret,
                    )
                )
            entry_i = i if cur != 0 else None
            side = cur
    cols = ["entry_date", "exit_date", "side", "entry_price", "exit_price", "bars", "return_pct"]
    return pd.DataFrame(rows, columns=cols)
