"""Parameter tuning with overfitting controls.

``grid_search`` evaluates every parameter combination on the same engine and returns both a metrics
table and the per-config return matrix needed for :func:`trendrev.afml.prob_backtest_overfitting`.
``walk_forward`` does anchored out-of-sample selection so the reported edge is the one that survived
being chosen on past data only. The Deflated Sharpe Ratio ties the two together by judging the
selected config against the luckiest of all trials.
"""
from __future__ import annotations

from itertools import product
from typing import Callable

import numpy as np
import pandas as pd

from . import afml
from .backtest import run_backtest
from .metrics import compute_metrics


def _per_obs_sharpe(returns: pd.Series) -> float:
    r = returns[returns.notna()]
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def expand_grid(param_grid: dict[str, list]) -> list[dict]:
    keys = list(param_grid)
    return [dict(zip(keys, combo)) for combo in product(*param_grid.values())]


def grid_search(
    df: pd.DataFrame,
    strategy_fn: Callable[..., pd.Series],
    param_grid: dict[str, list],
    **bt_kwargs,
):
    """Evaluate all combinations. Returns ``(metrics_df, returns_matrix)``.

    ``metrics_df`` is sorted by Sharpe and carries a ``deflated_sharpe`` column that discounts the
    best row for the number of trials run. ``returns_matrix`` (T x N) feeds the PBO estimator.
    """
    combos = expand_grid(param_grid)
    rows, ret_cols = [], {}
    for params in combos:
        pos = strategy_fn(df, **params)
        res = run_backtest(df, pos, **bt_kwargs)
        m = compute_metrics(res)
        m.update(params)
        m["per_obs_sharpe"] = _per_obs_sharpe(res.returns)
        label = ",".join(f"{k}={v}" for k, v in params.items())
        m["config"] = label
        rows.append(m)
        ret_cols[label] = res.returns
    metrics_df = pd.DataFrame(rows).set_index("config").sort_values("sharpe", ascending=False)
    returns_matrix = pd.DataFrame(ret_cols)

    sr_trials = metrics_df["per_obs_sharpe"].values
    best_label = metrics_df.index[0]
    metrics_df["deflated_sharpe"] = np.nan
    metrics_df.loc[best_label, "deflated_sharpe"] = afml.deflated_sharpe_ratio(
        returns_matrix[best_label], sr_trials
    )
    return metrics_df, returns_matrix


def walk_forward(
    df: pd.DataFrame,
    strategy_fn: Callable[..., pd.Series],
    param_grid: dict[str, list],
    n_splits: int = 5,
    select_by: str = "sharpe",
    **bt_kwargs,
):
    """Anchored walk-forward: pick params on the in-sample window, trade them out-of-sample.

    The instrument's history is cut into ``n_splits + 1`` contiguous folds. For each test fold the
    parameters are chosen using only the data strictly before it, then applied to the test fold.
    Returns ``(stitched_oos_result_like, choices_df)`` where the first is a dict of stitched OOS
    series and the second records which config won each fold.
    """
    combos = expand_grid(param_grid)
    n = len(df)
    bounds = np.linspace(0, n, n_splits + 2, dtype=int)

    oos_returns = pd.Series(0.0, index=df.index)
    oos_pos = pd.Series(0.0, index=df.index)
    choices = []

    # Precompute each config's causal position & per-interval returns once on the full history.
    cfg_pos, cfg_ret = {}, {}
    for params in combos:
        label = ",".join(f"{k}={v}" for k, v in params.items())
        pos = strategy_fn(df, **params)
        cfg_pos[label] = pos
        cfg_ret[label] = run_backtest(df, pos, **bt_kwargs).returns

    for k in range(1, n_splits + 1):
        train_idx = df.index[: bounds[k]]
        test_idx = df.index[bounds[k]: bounds[k + 1]]
        if len(test_idx) == 0:
            continue
        best_label, best_score = None, -np.inf
        for label in cfg_ret:
            score = _per_obs_sharpe(cfg_ret[label].loc[train_idx])
            if score > best_score:
                best_label, best_score = label, score
        oos_returns.loc[test_idx] = cfg_ret[best_label].loc[test_idx]
        oos_pos.loc[test_idx] = cfg_pos[best_label].shift(1).fillna(0.0).loc[test_idx]
        choices.append(
            {"fold": k, "train_end": train_idx[-1], "test_start": test_idx[0],
             "test_end": test_idx[-1], "config": best_label, "is_sharpe": best_score}
        )

    oos_equity = (1.0 + oos_returns.fillna(0.0)).cumprod()
    return (
        {"returns": oos_returns, "equity": oos_equity, "exec_pos": oos_pos},
        pd.DataFrame(choices),
    )
