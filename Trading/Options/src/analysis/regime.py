"""Regime-conditional performance reporting (2026-08-11).

Every optimizer run in this project has scored trials on ONE pooled Sharpe over the whole
backtest window. That hides whether a structure's edge comes from surviving stress or purely from
the ~86.5% of the window that's calm/bull -- exactly the concern that motivated this module. The
fix is NOT to reweight the training sample toward stress (that biases the unconditional estimate
and collapses effective sample size -- COVID is 35 trading days), it's to report calm and stress
performance as SEPARATE columns, never blended into one headline number, so a structure that only
works when markets are calm is visible as such rather than hidden inside a pooled average.

Stress windows are the same ones used earlier in this project's window-composition analysis:
2018 Q4 selloff, the COVID crash, and the 2022 bear market. Together they're ~13.5% of the
2018-2026 window (300 of 2223 business days) -- close to the historical base rate (~15% NBER
recession months), so this is a REPORTING split, not a resampling of the training data.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

# (start, end) inclusive, YYYY-MM-DD. The first three match the composition breakdown established
# earlier in this project's investigation of the 2018-2026 daily-cadence training window; they sit
# entirely inside the IS side of the walk-forward split (2018-01-02..2023-12-19). The last two were
# added 2026-08-11 specifically because they DON'T: without an OOS-side stress window, "OOS stress
# Sharpe" is structurally always NaN/0-trades (checked against data/processed/vix_history.csv) and
# worst_regime_sharpe() on OOS degenerates to -inf every time, regardless of the candidate.
STRESS_WINDOWS = [
    ("2018-10-01", "2018-12-24"),  # 2018 Q4 selloff (IS)
    ("2020-02-19", "2020-04-07"),  # COVID crash (IS)
    ("2022-01-03", "2022-10-13"),  # 2022 bear market (IS)
    ("2024-08-02", "2024-08-09"),  # yen-carry-unwind spike, VIX 38.6 (OOS)
    ("2025-03-28", "2025-05-09"),  # tariff-shock selloff, VIX peaked 52.3 (OOS)
]

# Same annualized excess-return Sharpe convention used everywhere else in this project
# (metrics.py::calculate_performance_metrics, walk_forward.py::evaluate_oos_continuous).
_ANNUAL_RF = 0.02


def is_stress_date(date) -> bool:
    """True if `date` falls inside any of STRESS_WINDOWS."""
    d = pd.Timestamp(date).normalize()
    return any(pd.Timestamp(lo) <= d <= pd.Timestamp(hi) for lo, hi in STRESS_WINDOWS)


def _sharpe_and_dd(equity: pd.DataFrame) -> Dict[str, float]:
    """Sharpe + max drawdown from a `total_value` equity-curve slice, or NaNs if too short."""
    if len(equity) < 3:
        return {"sharpe_ratio": float("nan"), "max_drawdown_pct": float("nan"),
                "total_return_pct": float("nan")}
    rets = equity["total_value"].pct_change().dropna()
    excess = rets - _ANNUAL_RF / 252.0
    sharpe = float(np.sqrt(252) * excess.mean() / excess.std()) if excess.std() > 0 else float("nan")
    cummax = equity["total_value"].cummax()
    max_dd = float(((equity["total_value"] - cummax) / cummax).min() * 100.0)
    start_val, end_val = float(equity["total_value"].iloc[0]), float(equity["total_value"].iloc[-1])
    total_ret = (end_val - start_val) / start_val * 100.0 if start_val else float("nan")
    return {"sharpe_ratio": sharpe, "max_drawdown_pct": max_dd, "total_return_pct": total_ret}


def regime_conditional_metrics(
    equity_curve: pd.DataFrame,
    trades: Optional[pd.DataFrame] = None,
) -> Dict[str, float]:
    """Calm vs. stress Sharpe / max DD / return / win-rate from a raw backtest's equity curve.

    Args:
        equity_curve: the `equity_curve` DataFrame from a raw backtest result (has `date`,
            `total_value`) -- e.g. `OptopsyBacktester.run_backtest(...)['equity_curve']`, or the
            `res["equity_curve"]` used internally by `walk_forward.evaluate_oos_continuous`.
        trades: optional `trades` DataFrame (has `entry_date`, `net_pnl`) for regime-conditional
            win rate and trade counts. Trades are tagged by ENTRY date (the regime the trade was
            put on in), not exit date.

    Returns:
        Flat dict: calm_sharpe_ratio, calm_max_drawdown_pct, calm_total_return_pct, calm_trades,
        calm_win_rate_pct, and the same six keys prefixed `stress_`.
    """
    eq = equity_curve.copy()
    eq["date"] = pd.to_datetime(eq["date"])
    stress_mask = eq["date"].apply(is_stress_date)

    out: Dict[str, float] = {}
    for label, mask in (("calm", ~stress_mask), ("stress", stress_mask)):
        sub = eq[mask].reset_index(drop=True)
        m = _sharpe_and_dd(sub)
        out[f"{label}_sharpe_ratio"] = m["sharpe_ratio"]
        out[f"{label}_max_drawdown_pct"] = m["max_drawdown_pct"]
        out[f"{label}_total_return_pct"] = m["total_return_pct"]
        out[f"{label}_days"] = int(mask.sum())

        if trades is not None and len(trades) and "entry_date" in trades.columns:
            td = trades.copy()
            td["entry_date"] = pd.to_datetime(td["entry_date"])
            td_mask = td["entry_date"].apply(is_stress_date) if label == "stress" else ~td["entry_date"].apply(is_stress_date)
            td_sub = td[td_mask]
            out[f"{label}_trades"] = int(len(td_sub))
            out[f"{label}_win_rate_pct"] = (
                float((td_sub["net_pnl"] > 0).mean() * 100.0) if len(td_sub) else float("nan")
            )
        else:
            out[f"{label}_trades"] = 0
            out[f"{label}_win_rate_pct"] = float("nan")

    return out


def worst_regime_sharpe(metrics: Dict[str, float]) -> float:
    """The lower of calm/stress Sharpe -- a robust-ranking criterion (2026-08-11 Phase 4).

    Ranking candidates by this instead of (or alongside) pooled Sharpe means a structure that only
    works in calm markets can't win purely on the strength of the ~86.5% calm majority -- its
    stress-period Sharpe caps the score. NaN (e.g. too few stress trades to compute a ratio) is
    treated as worst-case (-inf), not ignored, so a candidate can't score well by having so few
    stress trades that its stress Sharpe is undefined.
    """
    calm = metrics.get("calm_sharpe_ratio", float("nan"))
    stress = metrics.get("stress_sharpe_ratio", float("nan"))
    calm = calm if calm == calm else float("-inf")
    stress = stress if stress == stress else float("-inf")
    return min(calm, stress)
