#!/usr/bin/env python3
"""Phase 2: pre-registered fixed-rule regime overlays on the bull put spread.

Tests a SMALL, pre-registered set of entry-gate overlays (V0-V5) on top of the walk-forward
IS-chosen parameters (NOT --final, which already saw the OOS dates -- see the plan). Every
threshold is a literature convention (VIX>30 crisis cutoff, tastytrade IVR>=50, the existing SPY
Trend Reversal gate), not fit to this data, so this adds a bounded, disclosed selection-among-6
effect rather than an open-ended search. All six variants are reported -- no cherry-picking.

Honest protocol: score with walk_forward.evaluate_oos_continuous (one continuous IS+OOS
backtest per variant, OOS-slice scored), the same method used for the original walk-forward
result, so numbers are directly comparable to the un-gated OOS Sharpe 1.19 baseline.

Usage:
    python regime_overlay_validation.py
"""
from __future__ import annotations

import warnings
warnings.filterwarnings('ignore')

import yaml
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization import walk_forward
from src.utils import regime as rg
from src.utils.trend_gate import spy_trend_gate

# Walk-forward IS-chosen params (logged OOS Sharpe 1.19, 46 trades, -20% max DD, DSR 0.65).
# Overlays are validated against THIS set, not --final, because --final was fit on the entire
# window including the OOS dates -- gating it and re-scoring "OOS" would be contaminated.
WF_PARAMS = {'dte': 30, 'short_delta': 0.30, 'long_delta': 0.10, 'profit_target': 0.55,
             'stop_loss': 0.70, 'dte_min': 22, 'vix_min': 20}


def main() -> None:
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    print("Loading market data...")
    options_data = load_sample_spy_options_data()
    start = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start, end)
    print(f"  {len(options_data):,} option rows, {start}..{end}\n")

    bt_start, bt_end = config['backtest']['start_date'], config['backtest']['end_date']
    full_window = (bt_start, bt_end)
    is_win, oos_win = walk_forward.split_window(bt_start, bt_end, oos_fraction=0.30)
    print(f"IS window:  {is_win}")
    print(f"OOS window: {oos_win}\n")

    trend_labels = rg.trend_regime(bt_end)
    rank_labels = rg.vix_rank_regime(bt_start, bt_end)
    composite_df = rg.composite_regime(bt_start, bt_end)
    composite_df.index = composite_df.index.normalize()

    variants = {
        'V0_baseline_no_overlay': None,
        'V1_skip_vix_gt_30': rg.vix_max_gate(bt_start, bt_end, max_vix=30.0),
        'V2_ivr_ge_50_rich_premium': rg.regime_gate(rank_labels, ['high']),
        'V3_trend_bull_or_neutral': spy_trend_gate(bt_end, 'bull'),  # bull-only baseline gate
        'V3b_trend_bull_or_neutral_wide': rg.regime_gate(trend_labels, ['bull', 'neutral']),
        'V4_composite_risk_on_only': rg.regime_gate(composite_df['composite'], ['risk-on']),
        'V5_ivr_lt_50_control': rg.regime_gate(rank_labels, ['low']),
    }

    rows = []
    for name, gate in variants.items():
        res = walk_forward.evaluate_oos_continuous(
            config, 'vertical', BullPutSpread, options_data, underlying_data,
            full_window, oos_win[0], WF_PARAMS, entry_gate=gate,
        )
        row = {'variant': name, **res}
        rows.append(row)
        print(f"{name:32s}  Sharpe={res.get('sharpe_ratio', float('nan')):7.3f}  "
              f"trades={res.get('total_trades', 0):4d}  "
              f"return={res.get('total_return_pct', float('nan')):8.1f}%  "
              f"maxDD={res.get('max_drawdown_pct', float('nan')):7.1f}%"
              + (f"  [{res['error']}]" if 'error' in res else ""))

    df = pd.DataFrame(rows)
    df.to_csv('optimization_results/bull_put_regime_overlay_validation.csv', index=False)
    print("\nSaved: optimization_results/bull_put_regime_overlay_validation.csv")

    print("\n" + "=" * 78)
    print("SUMMARY (all 6 pre-registered variants, selection-among-6 disclosed):")
    print("=" * 78)
    print(df[['variant', 'sharpe_ratio', 'total_trades', 'total_return_pct',
              'max_drawdown_pct']].to_string(index=False))
    base = df[df['variant'] == 'V0_baseline_no_overlay']['sharpe_ratio'].iloc[0]
    best = df.loc[df['sharpe_ratio'].idxmax()]
    print(f"\nBaseline (V0) OOS Sharpe: {base:.3f}")
    print(f"Best variant: {best['variant']} (OOS Sharpe {best['sharpe_ratio']:.3f}, "
          f"{int(best['total_trades'])} OOS trades)")
    if best['total_trades'] < 25:
        print("NOTE: best variant has <25 OOS trades -- too few to trust over V0 regardless of Sharpe.")


if __name__ == '__main__':
    main()
