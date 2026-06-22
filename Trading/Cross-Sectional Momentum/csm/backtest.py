"""Walk-forward backtest orchestrator.

Splits the full history into in-sample and out-of-sample windows, fits the
meta-model on IS, evaluates strictly OOS, then compares primary-only vs
meta-labeled performance.  The OOS equity curve is the headline result.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

from csm import signals as sig_mod
from csm import portfolio as port_mod
from csm.labeling import label_universe
from csm.model import (
    build_feature_matrix,
    train_meta_model,
    apply_meta_filter,
    save_meta_model,
)


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
#  Walk-forward backtest
# ─────────────────────────────────────────────────────────────────────────────

def walk_forward(
    prices:       pd.DataFrame,
    cfg:          dict,
    pit_df:       pd.DataFrame | None = None,
    oos_frac:     float = 0.30,
    meta_enabled: bool  = True,
    out_dir:      Path | None = None,
) -> tuple[BacktestResult, BacktestResult | None]:
    """Walk-forward split: fit meta-model on IS, evaluate on OOS.

    Returns (primary_result, meta_result) for the OOS period only.
    meta_result is None if meta_labeling is disabled in cfg or no labels.
    """
    index   = prices.index
    n       = len(index)
    is_end  = index[int(n * (1 - oos_frac)) - 1]
    oos_start = is_end + pd.Timedelta(days=1)

    is_prices  = prices.loc[:is_end]
    oos_prices = prices.loc[oos_start:]

    if len(oos_prices) < 63:
        raise ValueError(f"OOS window too short ({len(oos_prices)} days).  "
                         "Extend the backtest date range.")

    # --- Primary strategy scored on OOS using a continuous full-history signal ---
    # (NOT run_primary_backtest(oos_prices), which would re-burn ~2×window warmup
    #  inside OOS and badly understate long-window configs — see evaluate_oos_continuous.)
    primary_oos = evaluate_oos_continuous(prices, cfg, oos_start, pit_df=pit_df,
                                          label="primary (OOS)")

    if not meta_enabled or not cfg.get("meta_labeling", {}).get("enabled", True):
        return primary_oos, None

    # --- Meta-labeling on the CONTINUOUS signal (mirrors the primary OOS fix) ---
    # Compute the signal & positions ONCE on the full panel — leak-free, because every
    # date's signal/features use only data up to that date (rolling windows look back) —
    # then slice IS for training and OOS for application. The old path recomputed the
    # signal on each slice ALONE, re-burning ~2×window warmup inside OOS, which both
    # understated the meta result and made it non-comparable to the (now continuous)
    # primary OOS curve.
    print("  Computing continuous signal & positions on the full panel …")
    full_signals = sig_mod.primary_signal(prices, cfg)
    full_pos     = port_mod.build_positions(full_signals, prices, cfg, pit_df=pit_df)
    is_pos       = full_pos.loc[:is_end]

    print("  Computing triple-barrier labels on IS …")
    # Label IS on is_prices (close TRUNCATED at is_end): a late-IS entry's vertical
    # barrier then cannot resolve using OOS prices, so no future data leaks into a
    # training label. Unresolved boundary labels drop out naturally (NaN bin).
    bins, weights = label_universe(is_prices, is_pos, cfg)
    if len(bins) < 30:
        print("  WARNING: too few IS labels; skipping meta-labeling.")
        return primary_oos, None

    print(f"  IS labels: {len(bins)} entries, take-rate={int((bins['bin']==1).mean()*100)}%")

    print("  Building feature matrix …")
    # Features on the full (warmed) panel; leak-free because each feature at event_date
    # uses only rolling windows ending on/before that date.
    X = build_feature_matrix(bins, prices, cfg)
    if X.empty or len(X) < 30:
        print("  WARNING: feature matrix too sparse; skipping meta-labeling.")
        return primary_oos, None

    y = bins.loc[X.index, "bin"].astype(int)
    w = weights.reindex(X.index).fillna(1.0)

    print("  Training meta-model (PurgedKFoldPanel CV) …")
    clf, oos_prob_is, cv_acc = train_meta_model(X, y, w, bins, cfg)
    print(f"  IS PurgedCV accuracy: {cv_acc.mean():.3f} ± {cv_acc.std():.3f}  "
          f"(base rate {max(y.mean(), 1-y.mean()):.3f})")

    if out_dir is not None:
        save_meta_model(clf, X.columns.tolist(), is_end, out_dir)

    # --- Apply meta-model to OOS, using the SAME continuous positions/features ---
    print("  Applying meta-model to OOS candidates …")
    # Detect entries on the full continuous positions (so a holding carried across the
    # IS/OOS boundary isn't mis-flagged as a new entry), label with full close for warmed
    # vol/barriers, then keep OOS entries only.
    all_bins, _ = label_universe(prices, full_pos, cfg)
    oos_bins    = all_bins[all_bins.index.get_level_values("date") >= oos_start]
    if len(oos_bins) < 5:
        print("  WARNING: too few OOS entries to apply meta-model.")
        return primary_oos, None

    X_oos = build_feature_matrix(oos_bins, prices, cfg)
    if X_oos.empty:
        return primary_oos, None

    col1 = list(clf.classes_).index(1) if 1 in clf.classes_ else -1
    if col1 < 0:
        return primary_oos, None
    oos_prob_oos = clf.predict_proba(X_oos)[:, col1]

    # Filter the continuous positions, score continuously, then slice to OOS so the meta
    # curve is measured on exactly the same dates and benchmark as primary_oos.
    meta_pos_full = apply_meta_filter(full_pos, prices, oos_bins, clf, X_oos, oos_prob_oos, cfg)
    meta_net_ret  = port_mod.portfolio_returns(meta_pos_full, prices, cfg).loc[oos_start:]
    meta_exec     = meta_pos_full.shift(1).fillna(0.0).loc[oos_start:]
    bench_ret     = prices["SPY"].pct_change().fillna(0.0).loc[oos_start:]

    meta_oos = BacktestResult(
        net_ret      = meta_net_ret,
        equity       = _equity(meta_net_ret),
        bench_ret    = bench_ret,
        bench_equity = _equity(bench_ret),
        exec_pos     = meta_exec,
        label        = "meta-labeled (OOS)",
    )
    return primary_oos, meta_oos
