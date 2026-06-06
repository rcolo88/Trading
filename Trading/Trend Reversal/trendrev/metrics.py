"""Performance metrics computed from a :class:`~trendrev.backtest.BacktestResult`.

Standard return/risk statistics plus trade-level stats. Overfitting-aware statistics (Probabilistic
and Deflated Sharpe, PBO) live in :mod:`trendrev.afml` because they belong to the de Prado toolkit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .backtest import BacktestResult


def _years(index: pd.DatetimeIndex) -> float:
    span = (index[-1] - index[0]).days / 365.25
    return max(span, 1e-9)


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    r = returns[returns.notna()]
    sd = r.std(ddof=1)
    return float(np.sqrt(periods_per_year) * r.mean() / sd) if sd > 0 else 0.0


def sortino_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    r = returns[returns.notna()]
    downside = r[r < 0].std(ddof=1)
    return float(np.sqrt(periods_per_year) * r.mean() / downside) if downside > 0 else 0.0


def max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())


def cagr(equity: pd.Series) -> float:
    total = equity.iloc[-1] / equity.iloc[0]
    return float(total ** (1.0 / _years(equity.index)) - 1.0)


def compute_metrics(result: BacktestResult, name: str | None = None) -> dict:
    """Return a flat dict of headline metrics for a backtest result."""
    r = result.returns
    eq = result.equity
    ann_vol = float(r[r.notna()].std(ddof=1) * np.sqrt(result.periods_per_year))
    mdd = max_drawdown(eq)
    cg = cagr(eq)

    trades = result.trades
    wins = trades[trades["return_pct"] > 0]["return_pct"]
    losses = trades[trades["return_pct"] <= 0]["return_pct"]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    profit_factor = float(gross_win / gross_loss) if gross_loss > 0 else np.inf

    out = {
        "strategy": name or "",
        "total_return": float(eq.iloc[-1] / eq.iloc[0] - 1.0),
        "cagr": cg,
        "ann_vol": ann_vol,
        "sharpe": sharpe_ratio(r, result.periods_per_year),
        "sortino": sortino_ratio(r, result.periods_per_year),
        "max_drawdown": mdd,
        "calmar": float(cg / abs(mdd)) if mdd < 0 else np.inf,
        "exposure": float((result.exec_pos != 0).mean()),
        "n_trades": int(len(trades)),
        "win_rate": float((trades["return_pct"] > 0).mean()) if len(trades) else 0.0,
        "profit_factor": profit_factor,
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "best_trade": float(trades["return_pct"].max()) if len(trades) else 0.0,
        "worst_trade": float(trades["return_pct"].min()) if len(trades) else 0.0,
    }
    return out


def alpha_beta(strat_returns: pd.Series, bench_returns: pd.Series,
               periods_per_year: int = 252, rf_annual: float = 0.0) -> dict:
    """Jensen's (CAPM) alpha & beta of a strategy vs a benchmark, from an OLS of daily excess returns.

    ``r_strat - rf = alpha + beta * (r_bench - rf) + eps``. Returns annualized alpha (arithmetic,
    ``alpha_daily * periods``), beta, the alpha t-stat (significance), R², and the plain CAGR spread.
    The benchmark here is SPY buy & hold, so ``ann_alpha`` is the return the strategy adds *beyond*
    its market exposure to the S&P 500."""
    import statsmodels.api as sm

    df = pd.concat([strat_returns, bench_returns], axis=1, keys=["s", "b"]).dropna()
    rf_daily = rf_annual / periods_per_year
    y = df["s"] - rf_daily
    x = sm.add_constant(df["b"] - rf_daily)
    model = sm.OLS(y, x).fit()
    alpha_daily = float(model.params["const"])
    return {
        "ann_alpha": alpha_daily * periods_per_year,
        "beta": float(model.params["b"]),
        "alpha_tstat": float(model.tvalues["const"]),
        "r_squared": float(model.rsquared),
        "alpha_daily": alpha_daily,
    }


def metrics_table(results: dict[str, BacktestResult]) -> pd.DataFrame:
    """Build a ranked metrics table (by Sharpe) from ``{name: BacktestResult}``."""
    rows = [compute_metrics(res, name) for name, res in results.items()]
    df = pd.DataFrame(rows).set_index("strategy")
    return df.sort_values("sharpe", ascending=False)
