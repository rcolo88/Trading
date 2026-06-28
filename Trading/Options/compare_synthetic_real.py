#!/usr/bin/env python3
"""
Compare synthetic vs real (DoltHub) options data.

For each overlapping (quote_date, expiration, strike, option_type) tuple,
compare IV, mid price, and delta.  Report error metrics grouped by DTE bucket,
moneyness bucket, and VIX regime so we can see *where* the synthetic model
deviates from reality — and calibrate accordingly.
"""
import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from src.data_fetchers.synthetic_generator import _read_options_csv

PROCESSED = Path("data/processed")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _moneyness(strike, spot, option_type):
    """Return moneyness label for a contract."""
    ratio = strike / spot
    if option_type == 'call':
        if ratio < 0.90:   return 'deep_ITM'
        if ratio < 0.97:   return 'ITM'
        if ratio <= 1.03:  return 'ATM'
        if ratio <= 1.10:  return 'OTM'
        return 'deep_OTM'
    else:
        if ratio > 1.10:   return 'deep_ITM'
        if ratio > 1.03:   return 'ITM'
        if ratio >= 0.97:  return 'ATM'
        if ratio >= 0.90:  return 'OTM'
        return 'deep_OTM'


def _dte_bucket(dte):
    if dte <= 7:          return '0-7'
    if dte <= 14:         return '7-14'
    if dte <= 30:         return '14-30'
    if dte <= 45:         return '30-45'
    if dte <= 60:         return '45-60'
    return '60-90'


def _vix_regime(vix):
    if vix < 15:          return 'low (<15)'
    if vix < 25:          return 'normal (15-25)'
    if vix < 35:          return 'high (25-35)'
    return 'extreme (>35)'


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    real_file = PROCESSED / "SPY_real_options_2021-01-01_2026-06-08.csv"
    synth_file = None
    for p in sorted(PROCESSED.glob("SPY_synthetic_options_2024-01-01_*.csv")):
        synth_file = p

    if synth_file is None:
        print("No synthetic dataset found matching 2024-01-01_*.csv")
        sys.exit(1)

    print("Loading real data...")
    real = _read_options_csv(real_file)
    print("Loading synthetic data...")
    synth = _read_options_csv(synth_file)

    # Normalize dates and extract date-only for merge key
    for df in (real, synth):
        df['quote_date'] = pd.to_datetime(df['quote_date'])
        df['expiration'] = pd.to_datetime(df['expiration'])
        df['_date']      = df['quote_date'].dt.normalize()
        df['_exp']       = df['expiration'].dt.normalize()

    # Overlap period (compare by calendar date, ignoring time-of-day)
    start = max(real['_date'].min(), synth['_date'].min())
    end   = min(real['_date'].max(), synth['_date'].max())
    print(f"\nOverlap period: {start.date()} to {end.date()}")

    real  = real[(real['_date'] >= start) & (real['_date'] <= end)].copy()
    synth = synth[(synth['_date'] >= start) & (synth['_date'] <= end)].copy()

    print(f"Real contracts in overlap:      {len(real):,}")
    print(f"Synthetic contracts in overlap: {len(synth):,}")

    # Merge on the natural key (date-normalized)
    key_cols = ['_date', '_exp', 'strike', 'option_type']
    # Add source-suffix so we can diff
    merged = real.merge(
        synth, on=key_cols, how='inner', suffixes=('_real', '_synth')
    )

    print(f"Aligned (matching key) rows:    {len(merged):,}")
    if len(merged) == 0:
        print("Nothing to compare — no overlapping keys.")
        return

    # --- Metrics ---
    merged['mid_real']  = (merged['bid_real']  + merged['ask_real'])  / 2.0
    merged['mid_synth'] = (merged['bid_synth'] + merged['ask_synth']) / 2.0
    merged['iv_diff']   = merged['iv_real'] - merged['iv_synth']
    merged['iv_abs']    = merged['iv_diff'].abs()
    merged['mid_diff']  = merged['mid_real'] - merged['mid_synth']
    merged['mid_abs']   = merged['mid_diff'].abs()
    merged['mid_pct']   = np.where(merged['mid_real'] > 0.01,
                                   merged['mid_diff'] / merged['mid_real'], np.nan)
    merged['dte_bucket']   = merged['dte_real'].map(_dte_bucket)
    merged['moneyness']    = merged.apply(
        lambda r: _moneyness(r['strike'], r['underlying_price_real'], r['option_type']),
        axis=1
    )
    merged['vix_regime']   = merged['vix_real'].map(_vix_regime) if 'vix_real' in merged.columns else 'N/A'
    print(f"  VIX range in merged data: {merged['vix_real'].min():.1f} - {merged['vix_real'].max():.1f}")

    # --- Aggregate errors ---
    def stats(grp):
        n = len(grp)
        iv_bias   = grp['iv_diff'].mean()
        iv_rmse   = np.sqrt((grp['iv_diff'] ** 2).mean())
        iv_mae    = grp['iv_abs'].mean()
        mid_bias  = grp['mid_diff'].mean()
        mid_rmse  = np.sqrt((grp['mid_diff'] ** 2).mean())
        mid_mae   = grp['mid_abs'].mean()
        mid_map   = grp['mid_pct'].dropna().mean() * 100
        return pd.Series({
            'N': n,
            'IV_bias': iv_bias, 'IV_RMSE': iv_rmse, 'IV_MAE': iv_mae,
            'Mid_bias': mid_bias, 'Mid_RMSE': mid_rmse, 'Mid_MAE': mid_mae,
            'Mid_MAPE%': mid_map,
        })

    print("\n" + "=" * 120)
    print("AGGREGATE (all aligned rows)")
    print("=" * 120)
    all_stats = stats(merged)
    for k, v in all_stats.items():
        if k == 'N':
            print(f"  {k}: {v:,.0f}")
        elif 'MAPE' in k:
            print(f"  {k}: {v:.2f}%")
        else:
            print(f"  {k}: {v:.4f}")

    for label, col in [("DTE bucket", 'dte_bucket'),
                       ("Moneyness",  'moneyness'),
                       ("VIX regime", 'vix_regime')]:
        print(f"\n{'=' * 120}")
        print(f"BY {label}")
        print(f"{'=' * 120}")
        grouped = merged.groupby(col).apply(stats).reset_index()
        print(grouped.to_string(index=False, float_format=lambda x: f'{x:.4f}',
                                na_rep='-'))

    # --- Per-bucket cross-tab: DTE ÷ Moneyness ---
    print(f"\n{'=' * 120}")
    print("IV_RMSE by DTE × Moneyness")
    print(f"{'=' * 120}")
    pivot = merged.groupby(['dte_bucket', 'moneyness']).apply(
        lambda g: np.sqrt((g['iv_diff'] ** 2).mean())
    ).unstack()
    print(pivot.to_string(float_format=lambda x: f'{x:.4f}' if pd.notna(x) else '-'))

    print("\nDone.")


if __name__ == '__main__':
    main()
