"""Transaction cost model: turnover × (commission + half-spread) bps."""
from __future__ import annotations

import numpy as np
import pandas as pd


def apply_costs(gross_ret: pd.Series,
                exec_pos:  pd.DataFrame,
                cfg:       dict) -> pd.Series:
    """Subtract one-way costs on position changes from gross portfolio returns."""
    cost_cfg  = cfg.get("costs", {})
    comm_bps  = float(cost_cfg.get("commission_bps",  5))
    hs_bps    = float(cost_cfg.get("half_spread_bps", 5))
    total_bps = comm_bps + hs_bps                   # one-way cost in bps
    cost_rate = total_bps / 1e4

    turnover = exec_pos.diff().abs().sum(axis=1).fillna(0.0)
    costs    = turnover * cost_rate
    return gross_ret - costs


def turnover_stats(exec_pos: pd.DataFrame) -> dict:
    """Diagnostic: annualised single-leg turnover (fraction of portfolio per year)."""
    daily_turnover = exec_pos.diff().abs().sum(axis=1).fillna(0.0)
    annual_turnover = float(daily_turnover.mean() * 252)
    return {
        "mean_daily_turnover": float(daily_turnover.mean()),
        "annual_turnover":     annual_turnover,
        "rebal_dates":         int((daily_turnover > 0.01).sum()),
    }
