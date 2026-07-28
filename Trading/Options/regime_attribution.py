#!/usr/bin/env python3
"""Phase 1 regime-attribution diagnostic for the bull put spread.

Runs ONE continuous full-window backtest (no search, no refit) for each of the two parameter
sets already validated (walk-forward IS-chosen, and the --final production fit), labels every
trade and every equity-curve day by fixed-rule market regime (VIX level, VIX IV-rank, SPY trend,
composite), and reports per-regime trade/return/drawdown stats.

This is diagnostic only: it answers "does performance actually differ by regime, and where does
the -47% full-window drawdown live" BEFORE any regime-conditional parameter refit is attempted
(see the plan's Phase 2/3 gating). No optimization, no new degrees of freedom.

Usage:
    python regime_attribution.py
"""
from __future__ import annotations

import warnings
warnings.filterwarnings('ignore')

import yaml
import pandas as pd

from src.strategies.vertical_spreads import BullPutSpread
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.walk_forward import _optimizer_for_window
from src.utils import regime as rg

pd.set_option('display.width', 140)
pd.set_option('display.max_columns', 20)

# Walk-forward IS-chosen params (OOS Sharpe 1.19, DSR 0.65) and the --final production fit
# (full-window Sharpe 1.36, DSR 0.881). See options-vertical-spread-fix memory / CHANGELOG.
PARAM_SETS = {
    'walk_forward_IS': {'dte': 30, 'short_delta': 0.30, 'long_delta': 0.10,
                         'profit_target': 0.55, 'stop_loss': 0.70, 'dte_min': 22, 'vix_min': 20},
    'final_production': {'dte': 30, 'short_delta': 0.30, 'long_delta': 0.08,
                          'profit_target': 0.45, 'stop_loss': 0.50, 'dte_min': 20, 'vix_min': 10},
}


def _annualized_sharpe(returns: pd.Series, rf: float = 0.02) -> float:
    excess = returns - rf / 252.0
    if len(excess) < 2 or excess.std() == 0:
        return float('nan')
    return float((252 ** 0.5) * excess.mean() / excess.std())


def _regime_isolated_drawdown(returns_by_day: pd.Series) -> float:
    """Compound ONLY this regime's daily returns back-to-back (ignores calendar gaps) and take
    the worst peak-to-trough dip. Not a literal chronological contribution to the full-window DD
    (the regime's days aren't contiguous) — it answers 'if you were only ever in this regime,
    how bad would the ride have been', which is the useful diagnostic question here.
    """
    if returns_by_day.empty:
        return float('nan')
    curve = (1.0 + returns_by_day.fillna(0)).cumprod()
    dd = (curve - curve.cummax()) / curve.cummax()
    return float(dd.min() * 100.0)


def attribute(label_name: str, labels: pd.Series, trades: pd.DataFrame, equity: pd.DataFrame) -> pd.DataFrame:
    """Per-regime-label stats for one label series (e.g. vix_level_regime)."""
    lab_by_day = {pd.Timestamp(d).normalize(): v for d, v in labels.items() if pd.notna(v)}

    t = trades.copy()
    t['regime'] = t['entry_date'].apply(lambda d: lab_by_day.get(pd.Timestamp(d).normalize()))

    e = equity.copy()
    e['date'] = pd.to_datetime(e['date'])
    e['regime'] = e['date'].apply(lambda d: lab_by_day.get(d.normalize()))

    rows = []
    for r in sorted(x for x in labels.dropna().unique()):
        tr = t[t['regime'] == r]
        eq = e[e['regime'] == r]
        rets = eq['returns'].dropna()
        rows.append({
            'label_set': label_name,
            'regime': r,
            'n_days': len(eq),
            'n_trades': len(tr),
            'win_rate_pct': (tr['net_pnl'] > 0).mean() * 100 if len(tr) else float('nan'),
            'total_pnl': tr['net_pnl'].sum() if len(tr) else 0.0,
            'avg_pnl_per_trade': tr['net_pnl'].mean() if len(tr) else float('nan'),
            'regime_sharpe': _annualized_sharpe(rets),
            'regime_isolated_dd_pct': _regime_isolated_drawdown(rets),
        })
    return pd.DataFrame(rows)


def run_for_params(name: str, params: dict, config: dict, options_data, underlying_data,
                    composite_df: pd.DataFrame, rank_labels: pd.Series) -> None:
    print("\n" + "=" * 78)
    print(f"PARAM SET: {name}  {params}")
    print("=" * 78)

    full_window = (config['backtest']['start_date'], config['backtest']['end_date'])
    opt = _optimizer_for_window(config, 'vertical', BullPutSpread, options_data, underlying_data, full_window)
    res = opt._run_single_backtest(params, verbose=False, return_raw=True)

    trades = res['trades']
    equity = res['equity_curve']
    print(f"Full-window: {len(trades)} trades, Sharpe {res['sharpe_ratio']:.3f}, "
          f"return {((equity['total_value'].iloc[-1] / equity['total_value'].iloc[0]) - 1) * 100:.1f}%, "
          f"max DD {equity['drawdown'].min() * 100:.1f}%")

    # Where does the worst drawdown live?
    trough_idx = equity['drawdown'].idxmin()
    trough_date = pd.Timestamp(equity.loc[trough_idx, 'date'])
    peak_idx = equity.loc[:trough_idx, 'total_value'].idxmax()
    peak_date = pd.Timestamp(equity.loc[peak_idx, 'date'])
    peak_regime = composite_df['composite'].get(peak_date.normalize(), 'n/a')
    trough_regime = composite_df['composite'].get(trough_date.normalize(), 'n/a')
    print(f"Worst drawdown episode: peak {peak_date.date()} ({peak_regime}) -> "
          f"trough {trough_date.date()} ({trough_regime}), {equity['drawdown'].min()*100:.1f}%")

    for label_name, labels in [
        ('vix_level_regime', composite_df['vix_level_regime']),
        ('trend_regime', composite_df['trend_regime']),
        ('composite', composite_df['composite']),
        ('vix_rank_regime', rank_labels),
    ]:
        tbl = attribute(label_name, labels, trades, equity)
        print(f"\n-- {label_name} --")
        print(tbl.drop(columns='label_set').to_string(index=False))


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
    print("Building regime labels...")
    composite_df = rg.composite_regime(bt_start, bt_end)
    composite_df.index = composite_df.index.normalize()
    rank_labels = rg.vix_rank_regime(bt_start, bt_end)
    print(composite_df['composite'].value_counts().to_string())
    print()

    for name, params in PARAM_SETS.items():
        run_for_params(name, params, config, options_data, underlying_data, composite_df, rank_labels)

    print("\n" + "=" * 78)
    rg.current_regime()
    print("=" * 78)


if __name__ == '__main__':
    main()
