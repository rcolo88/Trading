#!/usr/bin/env python3
"""
Iron Condor Parameter Optimization Script

Optimizes Iron Condor strategy parameters using grid search on synthetic SPY options data.
Evaluates performance metrics (Sharpe ratio, win rate, profit factor) to find optimal parameters.
Results are exported to CSV for comparison with other strategies.

Usage:
    # DEFAULT: walk-forward validation (optimize in-sample, score out-of-sample)
    python optimize_iron_condor.py
    # FINAL fit on the full window with no holdout (only after walk-forward passes):
    python optimize_iron_condor.py --final

Output:
    - optimization_results/iron_condor_optimization_results_YYYYMMDD_HHMMSS.csv
    - optimization_results/iron_condor_best_params_YYYYMMDD_HHMMSS.yaml
"""

import yaml
import pandas as pd
import numpy as np
from datetime import datetime
from itertools import product
import os
import sys
import copy

from src.strategies.iron_condor import IronCondor
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import PerformanceAnalyzer
from src.optimization import walk_forward


def create_param_combinations():
    """Reflective Iron Condor grid (tastytrade standard: ~45 DTE, ~16-20 delta shorts, 50% profit,
    manage at 21 DTE). This is a FULL grid (Cartesian product), so each list is kept short to stay
    feasible — 2^9 ≈ 512 combos here (~2-3h on full history). Widen only if you can afford the runtime.
    """
    return {
        'dte_min': [35, 40],
        'dte_max': [45, 50],            # <=65 (synthetic data DTE cap)
        'put_short_delta': [0.16, 0.20],
        'put_long_delta': [0.08, 0.10],
        'call_short_delta': [0.16, 0.20],
        'call_long_delta': [0.08, 0.10],
        'profit_target': [0.50],        # tastytrade 50% management
        'stop_loss': [0.75],
        'dte_min_exit': [21],           # close/roll at 21 DTE (gamma ramp)
        'min_credit': [1.00, 1.50],
        'vix_min': [10, 15],
        'vix_max': [30, 40],
    }


def run_single_backtest(base_config, param_dict, options_data, underlying_data):
    """
    Run a single backtest with given parameters.

    Returns:
        Dictionary with results or None if backtest failed
    """
    try:
        # Create a copy of config with updated parameters
        config = yaml.safe_load(yaml.dump(base_config))

        # Update Iron Condor entry parameters
        for key, value in param_dict.items():
            if key in ['dte_min', 'dte_max', 'put_short_delta', 'put_long_delta',
                       'call_short_delta', 'call_long_delta', 'min_credit',
                       'vix_min', 'vix_max', 'max_wing_width']:
                config['strategies']['iron_condor']['entry'][key] = value
            elif key in ['profit_target', 'stop_loss']:
                config['strategies']['iron_condor']['exit'][key] = value
            elif key == 'dte_min_exit':
                config['strategies']['iron_condor']['exit']['dte_min'] = value

        # Create strategy instance
        iron_condor_config = config['strategies']['iron_condor']
        strategy = IronCondor(iron_condor_config)

        # Run backtest
        backtester = OptopsyBacktester(config)
        results = backtester.run_backtest(
            strategy=strategy,
            options_data=options_data,
            underlying_data=underlying_data
        )

        # Calculate additional metrics
        analyzer = PerformanceAnalyzer(
            equity_curve=results['equity_curve'],
            trades=results['trades']
        )
        metrics = analyzer.calculate_all_metrics(config['backtest']['initial_capital'])

        # Return combined results
        return {
            **param_dict,
            'total_trades': len(results['trades']),
            'total_return_pct': results['total_return_pct'],
            'win_rate': results['win_rate_pct'],
            'profit_factor': results['profit_factor'],
            'max_drawdown': results['max_drawdown_pct'],
            'sharpe_ratio': metrics.get('sharpe_ratio', results.get('sharpe_ratio', 0)),
            'days_with_entry': results.get('days_with_entry', 0),
        }

    except Exception as e:
        print(f"  ✗ Backtest failed: {str(e)}")
        return None


def optimize_parameters(options_data, underlying_data, max_combinations=100, base_config=None):
    """
    Run parameter optimization using grid search.

    Args:
        options_data: Options contract data
        underlying_data: Underlying price data
        max_combinations: Maximum number of parameter combinations to test
        base_config: Optional pre-loaded config (e.g. window-pinned for walk-forward). If None,
            it is read from config/config.yaml.

    Returns:
        DataFrame with optimization results
    """
    # Load base configuration (or use the caller-supplied, window-pinned one for walk-forward).
    if base_config is None:
        with open('config/config.yaml', 'r') as f:
            base_config = yaml.safe_load(f)

    param_grid = create_param_combinations()

    # Generate all parameter combinations
    param_keys = list(param_grid.keys())
    param_values = [param_grid[k] for k in param_keys]
    all_combinations = list(product(*param_values))

    print(f"\nTotal possible combinations: {len(all_combinations)}")
    print(f"Testing up to {max_combinations} combinations...")

    # Limit combinations for performance
    test_combinations = all_combinations[:max_combinations]

    results_list = []
    for i, values in enumerate(test_combinations, 1):
        param_dict = dict(zip(param_keys, values))

        print(f"\n[{i}/{len(test_combinations)}] Testing parameters:")
        print(f"  DTE: {param_dict['dte_min']}-{param_dict['dte_max']}")
        print(f"  Put delta: {param_dict['put_short_delta']:.2f}/{param_dict['put_long_delta']:.2f}")
        print(f"  Call delta: {param_dict['call_short_delta']:.2f}/{param_dict['call_long_delta']:.2f}")
        print(f"  Profit target: {param_dict['profit_target']:.0%}")
        print(f"  Stop loss: {param_dict['stop_loss']:.0%}")

        result = run_single_backtest(base_config, param_dict, options_data, underlying_data)
        if result:
            results_list.append(result)
            print(f"  ✓ Sharpe: {result['sharpe_ratio']:.2f}, "
                  f"Return: {result['total_return_pct']:.2f}%, "
                  f"Win rate: {result['win_rate']:.1%}, "
                  f"Trades: {result['total_trades']}")
        else:
            print(f"  ✗ No trades or error")

    if not results_list:
        print("\n✗ No successful backtests! Check data and configuration.")
        return None

    results_df = pd.DataFrame(results_list)
    return results_df


def export_results(results_df):
    """Sort, display, and export an iron-condor results DataFrame (shared by both modes)."""
    # Sort by Sharpe ratio (primary metric)
    results_df = results_df.sort_values('sharpe_ratio', ascending=False).reset_index(drop=True)

    # Display top results
    print("\nTop 10 Parameter Combinations (by Sharpe Ratio):")
    print("-" * 70)
    top_results = results_df.head(10)
    display_cols = [
        'dte_min', 'dte_max', 'put_short_delta', 'call_short_delta',
        'profit_target', 'stop_loss',
        'total_trades', 'total_return_pct', 'win_rate', 'sharpe_ratio'
    ]
    print(top_results[display_cols].to_string())

    # Save results
    print("\nExporting results...")
    os.makedirs('optimization_results', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Export full results
    results_file = f"optimization_results/iron_condor_optimization_results_{timestamp}.csv"
    results_df.to_csv(results_file, index=False)
    print(f"   ✓ Full results: {results_file}")

    # Export best parameters
    best_params = results_df.iloc[0]
    best_params_file = f"optimization_results/iron_condor_best_params_{timestamp}.yaml"
    best_config = {
        'iron_condor': {
            'entry': {
                'dte_min': int(best_params['dte_min']),
                'dte_max': int(best_params['dte_max']),
                'put_short_delta': float(best_params['put_short_delta']),
                'put_long_delta': float(best_params['put_long_delta']),
                'call_short_delta': float(best_params['call_short_delta']),
                'call_long_delta': float(best_params['call_long_delta']),
                'min_credit': float(best_params['min_credit']),
                'vix_min': 15,
                'vix_max': 35,
                'max_wing_width': 10.0,
            },
            'exit': {
                'profit_target': float(best_params['profit_target']),
                'stop_loss': float(best_params['stop_loss']),
                'dte_min': int(best_params['dte_min_exit']),
                'breach_threshold': 0.02,
            }
        }
    }
    with open(best_params_file, 'w') as f:
        yaml.dump(best_config, f, default_flow_style=False)
    print(f"   ✓ Best parameters: {best_params_file}")

    # Summary statistics
    print("\nOptimization Summary:")
    print("-" * 70)
    print(f"Total combinations tested: {len(results_df)}")
    print(f"Combinations with trades: {len(results_df[results_df['total_trades'] > 0])}")
    print(f"\nBest parameters (Sharpe Ratio: {best_params['sharpe_ratio']:.2f}):")
    print(f"  DTE range: {int(best_params['dte_min'])}-{int(best_params['dte_max'])}")
    print(f"  Put deltas: {best_params['put_short_delta']:.2f}/{best_params['put_long_delta']:.2f}")
    print(f"  Call deltas: {best_params['call_short_delta']:.2f}/{best_params['call_long_delta']:.2f}")
    print(f"  Profit target: {best_params['profit_target']:.0%}")
    print(f"  Stop loss: {best_params['stop_loss']:.0%}")
    print(f"\nMetrics:")
    print(f"  Total return: {best_params['total_return_pct']:.2f}%")
    print(f"  Win rate: {best_params['win_rate']:.1%}")
    print(f"  Profit factor: {best_params['profit_factor']:.2f}")
    print(f"  Trades: {int(best_params['total_trades'])}")


def run_walk_forward(options_data, underlying_data, max_combinations):
    """Optimize on an in-sample window, then score the chosen params on an untouched OOS window.

    A real edge keeps most of its Sharpe out-of-sample; an overfit grid optimum collapses. This is
    the DEFAULT mode; pass --final to optimize over the entire window with no holdout instead. The
    OOS score reuses this script's own run_single_backtest, so IS and OOS scoring are identical.
    """
    with open('config/config.yaml', 'r') as f:
        base_config = yaml.safe_load(f)

    oos_frac = 0.30
    for a in sys.argv:
        if a.startswith('--oos-frac='):
            oos_frac = float(a.split('=', 1)[1])

    bt = base_config['backtest']
    is_win, oos_win = walk_forward.split_window(bt['start_date'], bt['end_date'], oos_frac)
    print("\n" + "=" * 70)
    print(f"WALK-FORWARD  in-sample {is_win[0]}..{is_win[1]}  |  out-of-sample {oos_win[0]}..{oos_win[1]}")
    print("=" * 70)

    # Optimize on IS only.
    is_config = copy.deepcopy(base_config)
    is_config['backtest']['start_date'], is_config['backtest']['end_date'] = is_win
    results_df = optimize_parameters(options_data, underlying_data, max_combinations, base_config=is_config)
    if results_df is None or len(results_df) == 0:
        print("\n✗ In-sample optimization produced no results; aborting walk-forward.")
        return

    results_df = results_df.sort_values('sharpe_ratio', ascending=False).reset_index(drop=True)
    best_row = results_df.iloc[0]

    # Pull the chosen (best IS) parameters, casting integral grid values back to int.
    param_keys = list(create_param_combinations().keys())
    def _cast(v):
        f = float(v)
        return int(f) if f.is_integer() else f
    best_params = {k: _cast(best_row[k]) for k in param_keys if k in best_row}

    # Score those exact params on the held-out OOS window (same backtest path as IS).
    # NOTE: this is an ISOLATED OOS-only backtest. The calendar/vertical scripts moved to scoring the
    # OOS *slice of one continuous IS+OOS run* (walk_forward.evaluate_oos_continuous) because an
    # isolated short window can under-trade (early degenerate exit + low-capital sizing). Iron Condor
    # uses its own hand-rolled grid path, so adopting the continuous slice here is a follow-up — if
    # OOS trades look implausibly low vs a continuous run, that's the cause.
    oos_config = copy.deepcopy(base_config)
    oos_config['backtest']['start_date'], oos_config['backtest']['end_date'] = oos_win
    oos = run_single_backtest(oos_config, best_params, options_data, underlying_data) or {}

    is_sharpe = float(best_row['sharpe_ratio'])
    oos_sharpe = float(oos.get('sharpe_ratio', float('nan')))

    print("\n" + "=" * 70)
    print("WALK-FORWARD RESULT (best in-sample params scored on the untouched OOS window)")
    print("=" * 70)
    print(f"  params: {best_params}")
    print(f"  IS  Sharpe: {is_sharpe:7.3f}  | IS  return: {float(best_row.get('total_return_pct', float('nan'))):7.2f}%")
    print(f"  OOS Sharpe: {oos_sharpe:7.3f}  | OOS return: {float(oos.get('total_return_pct', float('nan'))):7.2f}%"
          f"  | OOS trades: {oos.get('total_trades', '?')}")
    verdict = 'healthy — edge survives OOS' if (oos_sharpe > 1.0 and oos_sharpe > 0.5 * is_sharpe) \
        else 'LARGE degradation — treat the IS optimum as overfit'
    print(f"  IS→OOS Sharpe drop: {is_sharpe - oos_sharpe:7.3f}  ({verdict})")
    print("=" * 70)

    export_results(results_df)


def main():
    print("="*70)
    print("Iron Condor Parameter Optimization")
    print("="*70)

    # Load data
    print("\n1. Loading data...")
    print("   Loading sample options data...")
    options_data = load_sample_spy_options_data()
    print(f"   ✓ Loaded {len(options_data)} option contracts")

    print("   Fetching SPY price data...")
    start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start_date, end_date)
    print(f"   ✓ Loaded {len(underlying_data)} days of price data")

    max_combinations = 50

    # DEFAULT: walk-forward validation (optimize in-sample, score out-of-sample). The bare in-sample
    # Sharpe is optimistic by construction, so --final (full-window fit, no holdout) is opt-in and
    # should only be used after a default run shows the edge survives OOS.
    if '--final' not in sys.argv:
        print("\n2. Running walk-forward validation (default)...")
        run_walk_forward(options_data, underlying_data, max_combinations)
        print("\n" + "="*70)
        print("Walk-forward complete!")
        print("="*70)
        return

    print("\nMODE: FINAL FIT — full window, NO out-of-sample holdout.")
    print("2. Running optimization...")
    results_df = optimize_parameters(options_data, underlying_data, max_combinations=max_combinations)
    if results_df is None or len(results_df) == 0:
        print("\n✗ Optimization failed. No results to export.")
        return

    export_results(results_df)
    print("\n" + "="*70)
    print("Optimization complete!")
    print("="*70)


if __name__ == '__main__':
    main()
