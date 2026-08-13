"""3-way SPY / macro-regime-tilt / defensive-rotation blend — the 2026-08-05
standout finding (see memory csm-market-neutral-macro-tests): standalone
testing found this beats SPY buy-and-hold's own Sharpe with roughly HALF its
max drawdown, alpha t~2.0-2.06 (the first statistically significant alpha
found anywhere in this project's regime-robustness investigation).

Correctly understood as a DIVERSIFICATION result, not new stock-picking
skill: it combines three imperfectly-correlated return streams — broad
equity beta (SPY; a fair substitute for the CSM equity-picking engine, which
showed no significant differentiation from SPY-beta — see memory
csm-regime-robustness-project), the macro sector/asset regime tilt
(csm/macro_regime.py), and the multi-asset absolute-momentum rotation
(csm/multiasset.py). Fixed weights, monthly rebalanced — deliberately NOT
regime-switched between the three sleeves (switching was tested elsewhere
this project and found to create false-positive costs; this blend's edge is
diversification, not timing).

Self-contained (no runtime RAAM dependency), same principle as
csm/multiasset.py/csm/regime_state.py — the live engine never depends on
another project's directory existing.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

from csm import macro_regime as mr_mod
from csm import multiasset as ma_mod


class BacktestResult(NamedTuple):
    net_ret:       pd.Series
    equity:        pd.Series
    bench_ret:     pd.Series
    bench_equity:  pd.Series
    exec_pos:      pd.DataFrame
    label:         str


def _equity(ret: pd.Series) -> pd.Series:
    return (1.0 + ret.fillna(0.0)).cumprod()


def _cost_rate(cfg: dict) -> float:
    c = cfg.get("costs", {})
    return (float(c.get("commission_bps", 0)) + float(c.get("half_spread_bps", 5))) / 1e4


def _resolve_weights(cfg: dict) -> tuple[float, float, float, int, str]:
    from csm.data import GROWTH_TICKER

    b = cfg.get("blend", {})
    w_spy   = float(b.get("weight_spy",      0.34))
    w_macro = float(b.get("weight_macro",    0.33))
    w_rot   = float(b.get("weight_rotation", 0.33))
    top_n   = int(b.get("rotation_top_n", 2))
    growth_ticker = str(b.get("growth_ticker", GROWTH_TICKER))
    total = w_spy + w_macro + w_rot
    if total <= 0:
        raise ValueError("blend weights must sum to a positive number")
    if abs(total - 1.0) > 1e-6:
        w_spy, w_macro, w_rot = w_spy / total, w_macro / total, w_rot / total
    return w_spy, w_macro, w_rot, top_n, growth_ticker


def blend_target_weights(
    prices:      pd.DataFrame,
    cfg:         dict,
    rebal_dates: pd.DatetimeIndex | None = None,
    cache_dir:   Path | None = None,
) -> pd.DataFrame:
    """Target weight per ticker (growth ticker + macro basket + rotation basket
    + cash), valid for EVERY day (both `macro_regime.macro_tilt_weights` and
    `multiasset.defensive_weights` already forward-fill internally), at the
    configured fixed split. A ticker appearing in both the macro basket and
    the rotation roster (e.g. TLT, GLD) correctly accumulates both legs'
    contributions rather than one overwriting the other.

    The growth sleeve's ticker is `blend.growth_ticker` in config (default
    `csm.data.GROWTH_TICKER` = SPYM — 0.02% expense ratio vs SPY's ~0.09%,
    same S&P 500 exposure; verified 2026-08-05 to have real trading history
    back to 2010, so no backtest gap). This is INDEPENDENT of the benchmark:
    `simulate_blend`'s "SPY buy-and-hold" comparison always reads the literal
    SPY column, regardless of what the growth sleeve actually holds.

    2026-08-05 Phase 1 (blend-return-research): `blend.macro_growth_axis`
    ("price" default | "macro") and `blend.macro_baskets` ("v1" default |
    "v2") select the Phase-1.1/1.2 macro-sleeve variants that attack its
    measured 0.766 daily correlation with the growth sleeve. 2026-08-12
    Phase 2.5 adds `blend.macro_inflation_axis` ("price" default | "macro"),
    the symmetric override for the inflation side — see
    csm.macro_regime.inflation_score_macro's docstring for why it's
    default-off (built but not yet return-tested). `cache_dir` is consulted
    when macro_growth_axis="macro", macro_inflation_axis="macro", or
    `blend.risk_overlay` needs the FRED vintage cache; defaults to
    `cfg["data"]["cache_dir"]` resolved against the current working
    directory, matching every CLI entry point's convention.

    2026-08-05 Phase 2: `blend.risk_overlay` ("none" default | "robust" |
    "gtt" | "ladder" | "fx" | "credit_curve") scales the growth+macro legs
    (the equity-correlated bloc) by a daily exposure e in [0,1], sampled
    only at rebal dates (same monthly cadence as everything else — this
    does NOT raise trading frequency), and routes the freed weight into the
    rotation sleeve. See csm/blend_overlay.py and
    csm/signals.robust_regime_exposure.

    2026-08-12 (GAPS.md #5, "the user's yen question"): `blend.macro_fx_axis`
    ("none" default | "carry_unwind") is framing (a) of the FX/dollar gap —
    a THIRD orthogonal axis alongside growth/inflation that forces the
    'deflation' basket on a carry-unwind stress date (see
    csm.macro_regime.fx_stress_axis). `risk_overlay: fx` is framing (b) —
    the same FX signal used as a standalone continuous exposure gate instead
    (see csm.blend_overlay.fx_carry_unwind_exposure). GAPS.md #5 tests these
    as two SEPARATE hypotheses; both are default-off here.

    2026-08-12 (GAPS.md #6 Protocol A): `risk_overlay: credit_curve` adds HY
    OAS widening / T10Y3M inversion as a risk-off gate (see
    csm.blend_overlay.credit_curve_risk_off_exposure — note its docstring's
    caveat that the HY OAS leg can't cover the 2000-2014 holdout). Default-off.

    2026-08-12 (GAPS.md #11): `blend.macro_inflation_oil` (bool, default
    False) adds a WTI vote to `inflation_score_macro` when
    `macro_inflation_axis: macro` is also set — see that function's
    docstring. Isolates oil's marginal contribution vs. the 3-vote baseline.
    """
    w_spy, w_macro, w_rot, top_n, growth_ticker = _resolve_weights(cfg)

    if rebal_dates is None:
        rebal_dates = ma_mod.month_end_dates(prices.index)

    b = cfg.get("blend", {})
    growth_axis    = str(b.get("macro_growth_axis", "price"))
    inflation_axis = str(b.get("macro_inflation_axis", "price"))
    fx_axis     = str(b.get("macro_fx_axis", "none"))
    baskets_ver = str(b.get("macro_baskets", "v1"))
    overlay     = str(b.get("risk_overlay", "none"))

    needs_fred = (growth_axis == "macro" or inflation_axis == "macro"
                 or fx_axis == "carry_unwind"
                 or overlay in ("gtt", "ladder", "fx", "credit_curve"))
    if needs_fred and cache_dir is None:
        cache_dir = Path(cfg.get("data", {}).get("cache_dir", "outputs/cache"))

    growth_series = None
    if growth_axis == "macro":
        growth_series = mr_mod.growth_score_macro(prices.index, rebal_dates, cache_dir)

    inflation_series = None
    if inflation_axis == "macro":
        include_oil = bool(b.get("macro_inflation_oil", False))
        inflation_series = mr_mod.inflation_score_macro(prices.index, rebal_dates, cache_dir,
                                                         include_oil=include_oil)

    fx_stress_series = None
    if fx_axis == "carry_unwind":
        fx_stress_series = mr_mod.fx_stress_axis(prices.index, rebal_dates, cache_dir)

    baskets = mr_mod.REGIME_BASKETS_V2 if baskets_ver == "v2" else None

    macro_target = mr_mod.macro_tilt_weights(prices, rebal_dates,
                                             growth=growth_series, inflation=inflation_series,
                                             baskets=baskets, fx_stress=fx_stress_series)
    rot_target   = ma_mod.defensive_weights(prices, rebal_dates, top_n=top_n)

    if overlay == "none":
        exposure = pd.Series(1.0, index=prices.index)
    elif overlay == "robust":
        from csm import signals as sig_mod
        exposure = sig_mod.robust_regime_exposure(prices)
    elif overlay == "gtt":
        from csm import blend_overlay as bo_mod
        exposure = bo_mod.growth_trend_timing_exposure(prices, rebal_dates, cache_dir)
    elif overlay == "ladder":
        from csm import blend_overlay as bo_mod
        exposure = bo_mod.combination_ladder_exposure(prices, rebal_dates, cache_dir)
    elif overlay == "fx":
        from csm import blend_overlay as bo_mod
        exposure = bo_mod.fx_carry_unwind_exposure(prices, rebal_dates, cache_dir)
    elif overlay == "credit_curve":
        from csm import blend_overlay as bo_mod
        exposure = bo_mod.credit_curve_risk_off_exposure(prices, rebal_dates, cache_dir)
    else:
        raise ValueError(f"unknown blend.risk_overlay: {overlay!r}")
    exposure = exposure.reindex(prices.index).fillna(1.0)
    freed = (w_spy + w_macro) * (1.0 - exposure)

    all_cols = sorted(set(macro_target.columns) | set(rot_target.columns) | {growth_ticker})
    target = pd.DataFrame(0.0, index=prices.index, columns=all_cols)
    target[growth_ticker] = target[growth_ticker] + w_spy * exposure
    for c in macro_target.columns:
        target[c] = target[c] + w_macro * exposure * macro_target[c]
    for c in rot_target.columns:
        target[c] = target[c] + (w_rot + freed) * rot_target[c]
    return target


def simulate_blend(
    prices:    pd.DataFrame,
    cfg:       dict,
    oos_start: pd.Timestamp,
    oos_end:   pd.Timestamp | None = None,
    label:     str = "blend",
    cache_dir: Path | None = None,
) -> BacktestResult:
    """Event-driven, monthly-rebalance, hold-with-drift simulation — same
    engine shape as `backtest.simulate_live` / RAAM's `simulate_drift`,
    reimplemented self-contained here (fixed weights, not a stock-ranking
    signal, so it doesn't reuse `portfolio.build_positions`).
    """
    rebal_dates = ma_mod.month_end_dates(prices.index)
    target = blend_target_weights(prices, cfg, rebal_dates, cache_dir=cache_dir)
    cols = list(target.columns)
    ret  = prices[cols].ffill(limit=3).pct_change().fillna(0.0)

    rebal_set = set(rebal_dates)
    cost_rate = _cost_rate(cfg)

    before = rebal_dates[rebal_dates < oos_start]
    internal_start = before[-1] if len(before) else prices.index[0]
    sim_idx = prices.loc[internal_start:].index

    h    = pd.Series(0.0, index=cols)
    cash = 1.0
    pending: pd.Series | None = None
    cur_target = pd.Series(0.0, index=cols)

    eq_dates, eq_vals, exec_rows = [], [], []
    for i, date in enumerate(sim_idx):
        if i > 0:
            h = h * (1.0 + ret.loc[date].reindex(cols).fillna(0.0))
        E = float(h.sum() + cash)

        if pending is not None:
            tgt_d = pending.reindex(cols).fillna(0.0) * E
            cost  = float((tgt_d - h).abs().sum()) * cost_rate
            cash  = E - float(tgt_d.sum()) - cost
            h     = tgt_d
            E     = float(h.sum() + cash)
            cur_target = pending.reindex(cols).fillna(0.0)
            pending = None

        eq_dates.append(date); eq_vals.append(E)
        exec_rows.append(cur_target.copy())

        if date in rebal_set:
            w = target.loc[date]
            w = w[w > 0.0]
            pending = w

    equity_full = pd.Series(eq_vals, index=pd.DatetimeIndex(eq_dates))
    net_full    = equity_full.pct_change().fillna(0.0)
    exec_full   = pd.DataFrame(exec_rows, index=pd.DatetimeIndex(eq_dates))

    nr    = net_full.loc[oos_start:oos_end]
    bench = prices["SPY"].pct_change().fillna(0.0).loc[oos_start:oos_end]
    return BacktestResult(
        net_ret      = nr,
        equity       = _equity(nr),
        bench_ret    = bench,
        bench_equity = _equity(bench),
        exec_pos     = exec_full.loc[oos_start:oos_end],
        label        = label,
    )


def walk_forward_blend(
    prices:    pd.DataFrame,
    cfg:       dict,
    oos_frac:  float = 0.30,
    cache_dir: Path | None = None,
) -> BacktestResult:
    index = prices.index
    n     = len(index)
    is_end = index[int(n * (1 - oos_frac)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)
    if len(prices.loc[oos_start:]) < 63:
        raise ValueError(f"OOS window too short ({len(prices.loc[oos_start:])} days).")
    return simulate_blend(prices, cfg, oos_start, label="blend (OOS)", cache_dir=cache_dir)


def walk_forward_blend_folds(
    prices:        pd.DataFrame,
    cfg:           dict,
    n_folds:       int = 5,
    min_fold_days: int = 126,
    cache_dir:     Path | None = None,
) -> dict[str, BacktestResult]:
    index = prices.index
    n     = len(index)
    edges = np.linspace(0, n, n_folds + 1).astype(int)
    results: dict[str, BacktestResult] = {}
    for i in range(n_folds):
        lo, hi = edges[i], edges[i + 1] - 1
        if hi <= lo or (hi - lo) < min_fold_days:
            continue
        fold_start, fold_end = index[lo], index[hi]
        label = f"fold {i+1} ({fold_start.date()}→{fold_end.date()})"
        results[label] = simulate_blend(prices, cfg, fold_start, oos_end=fold_end,
                                        label=label, cache_dir=cache_dir)
    return results


def target_book(
    prices:    pd.DataFrame,
    cfg:       dict,
    as_of:     pd.Timestamp | None = None,
    cache_dir: Path | None = None,
) -> pd.Series:
    """Single source of truth for "what the blend holds on `as_of`" — mirrors
    `portfolio.target_book`'s role for the equity engine. `blend_target_weights`
    already resolves a value for every day (both component functions
    forward-fill internally), so this is just a row lookup.
    """
    target = blend_target_weights(prices, cfg, cache_dir=cache_dir)
    if as_of is None:
        as_of = prices.index[-1]
    w = target.loc[as_of].copy()
    w = w[w > 0.0]
    return w.sort_values(ascending=False)
