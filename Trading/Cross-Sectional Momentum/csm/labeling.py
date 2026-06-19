"""Triple-barrier meta-labels for the cross-sectional meta-model.

Wraps the vendored afml.py (de Prado, AFML Ch. 3) to label each candidate
long as 'take the bet' (bin=1) or 'skip it' (bin=0) based on whether the
trade actually hit its profit-take or stop-loss barrier first.

For a long-only strategy, side is always +1; the meta-label therefore asks:
  "Given that this stock passed the primary momentum filter, did holding it
   for up to `barrier_window` days actually make money?"

The resulting (ticker, event_date) → bin labels are pooled across all
stocks to train the meta-classifier in model.py.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from csm.afml import (
    get_daily_vol,
    add_vertical_barrier,
    get_events,
    get_bins,
    num_co_events,
    return_attribution_weights,
)


def label_ticker(
    close:          pd.Series,
    entry_dates:    pd.DatetimeIndex,
    barrier_window: int   = 42,
    pt_multiple:    float = 1.5,
    sl_multiple:    float = 1.0,
    vol_span:       int   = 50,
) -> pd.DataFrame:
    """Triple-barrier meta-labels for one ticker's candidate entry dates.

    Parameters
    ----------
    close          : adjusted-close price Series (DatetimeIndex)
    entry_dates    : dates when the primary signal nominated this stock as a long
    barrier_window : vertical barrier in trading days (≈ intended holding period)
    pt_multiple    : profit-take as a multiple of daily idio-vol
    sl_multiple    : stop-loss as a multiple of daily idio-vol
    vol_span       : EWM span for volatility estimation (afml.get_daily_vol)

    Returns
    -------
    DataFrame with index = entry_dates that had valid labels, columns:
      ret  : realised fractional return to first-touched barrier
      bin  : 1 (take the bet) or 0 (skip it)
      t1   : barrier-touch date (label end time, used for purged CV)
    """
    if entry_dates.empty:
        return pd.DataFrame(columns=["ret", "bin", "t1"])

    target  = get_daily_vol(close, span=vol_span).reindex(close.index).ffill()
    vbar    = add_vertical_barrier(entry_dates, close, num_days=barrier_window)
    side    = pd.Series(1.0, index=entry_dates)   # always long

    events  = get_events(
        close, entry_dates,
        pt_sl   = [pt_multiple, sl_multiple],
        target  = target,
        min_ret = 0.0,
        vertical= vbar,
        side    = side,
    )
    bins = get_bins(events, close)
    return bins.dropna(subset=["bin"])


def compute_sample_weights(
    bins:  pd.DataFrame,
    close: pd.Series,
) -> pd.Series:
    """Return-attribution sample weights (de Prado AFML Ch. 4).

    Down-weights labels that share price action (overlapping triple-barrier
    windows), so the classifier isn't fooled by correlated duplicates.
    """
    t1 = bins["t1"]
    co = num_co_events(close.index, t1)
    w  = return_attribution_weights(t1, co, close)
    w  = w.reindex(bins.index).fillna(0.0)
    mean_w = w.mean()
    if mean_w > 0:
        w = (w / mean_w).clip(upper=10.0)
    return w


def label_universe(
    prices:         pd.DataFrame,
    candidate_pos:  pd.DataFrame,
    cfg:            dict,
) -> tuple[pd.DataFrame, pd.Series]:
    """Label all (ticker, entry_date) candidates and assemble pooled training data.

    Parameters
    ----------
    prices        : (T, N) adjusted-close price panel (includes SPY)
    candidate_pos : (T, N) boolean or float position matrix from portfolio.build_positions
                    (rows where stock > 0 are candidate entry dates for that stock)
    cfg           : strategy config dict

    Returns
    -------
    all_bins : pooled DataFrame indexed by (ticker, entry_date) with ret/bin/t1
    all_weights : pooled sample weights
    """
    ml_cfg = cfg.get("meta_labeling", {})
    bw     = int(ml_cfg.get("barrier_window", 42))
    pt_m   = float(ml_cfg.get("pt_multiple",  1.5))
    sl_m   = float(ml_cfg.get("sl_multiple",  1.0))

    stocks = prices.drop(columns=["SPY"], errors="ignore")
    bins_list  : list[pd.DataFrame] = []
    weight_list: list[pd.Series]    = []

    for ticker in stocks.columns:
        close = stocks[ticker].dropna()
        if len(close) < 300:
            continue

        # Entry dates = days the stock was in the long portfolio (position > 0)
        if ticker not in candidate_pos.columns:
            continue
        in_port = candidate_pos[ticker]
        # Take the first day of each contiguous holding block as the "entry date"
        entered = (in_port > 0) & (in_port.shift(1).fillna(0) == 0)
        entry_dates = entered[entered].index
        if len(entry_dates) < 5:
            continue

        # Only use entry dates that fall within the close index
        entry_dates = entry_dates[entry_dates.isin(close.index)]
        if len(entry_dates) < 5:
            continue

        try:
            bins_tk = label_ticker(close, entry_dates,
                                   barrier_window=bw,
                                   pt_multiple=pt_m,
                                   sl_multiple=sl_m)
            if len(bins_tk) < 3:
                continue
            w_tk = compute_sample_weights(bins_tk, close)

            # Add ticker level to index
            bins_tk.index = pd.MultiIndex.from_arrays(
                [[ticker] * len(bins_tk), bins_tk.index],
                names=["ticker", "date"]
            )
            w_tk.index = bins_tk.index
            bins_list.append(bins_tk)
            weight_list.append(w_tk)
        except Exception:
            continue

    if not bins_list:
        return pd.DataFrame(columns=["ret", "bin", "t1"]), pd.Series(dtype=float)

    all_bins    = pd.concat(bins_list)
    all_weights = pd.concat(weight_list)
    return all_bins, all_weights
