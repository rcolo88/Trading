#!/usr/bin/env python3
"""
Iron Condor Parameter Optimization Script

Optimizes Iron Condor strategy parameters using grid search on synthetic SPY options data.
Evaluates performance metrics (Sharpe ratio, win rate, profit factor) to find optimal parameters.
Results are exported to CSV for comparison with other strategies.

Usage:
    python optimize_iron_condor.py

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

from src.strategies.iron_condor import IronCondor
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.analysis.metrics import PerformanceAnalyzer


def create_param_combinations():
    """Define parameter grid for Iron Condor optimization."""
    return {
        'dte_min': [25, 30, 35],
        'dte_max': [40, 45, 50],
        'put_short_delta': [0.15, 0.20, 0.25],
        'put_long_delta': [0.05, 0.10, 0.15],
        'call_short_delta': [0.15, 0.20, 0.25],
        'call_long_delta': [0.05, 0.10, 0.15],
        'profit_target': [0.40, 0.50, 0.60],
        'stop_loss': [0.60, 0.75, 0.90],
        'dte_min_exit': [7, 14, 21],
        'min_credit': [1.00, 1.50, 2.00],
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
                       'call_short_delta', 'call_long_delta', 'min_credit']:
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
            'win_rate': results['win_rate'],
            'profit_factor': results['profit_factor'],
            'max_drawdown': results['max_drawdown'],
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'days_with_entry': results.get('days_with_entry', 0),
        }

    except Exception as e:
        print(f"  ✗ Backtest failed: {str(e)}")
        return None


def optimize_parameters(options_data, underlying_data, max_combinations=100):
    """
    Run parameter optimization using grid search.

    Args:
        options_data: Options contract data
        underlying_data: Underlying price data
        max_combinations: Maximum number of parameter combinations to test

    Returns:
        DataFrame with optimization results
    """
    # Load base configuration
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

    # Run optimization
    print("\n2. Running optimization...")
    results_df = optimize_parameters(options_data, underlying_data, max_combinations=50)

    if results_df is None or len(results_df) == 0:
        print("\n✗ Optimization failed. No results to export.")
        return

    # Sort by Sharpe ratio (primary metric)
    results_df = results_df.sort_values('sharpe_ratio', ascending=False)

    # Display top results
    print("\n3. Top 10 Parameter Combinations (by Sharpe Ratio):")
    print("-" * 70)
    top_results = results_df.head(10)
    display_cols = [
        'dte_min', 'dte_max', 'put_short_delta', 'call_short_delta',
        'profit_target', 'stop_loss',
        'total_trades', 'total_return_pct', 'win_rate', 'sharpe_ratio'
    ]
    print(top_results[display_cols].to_string())

    # Save results
    print("\n4. Exporting results...")
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
                'iv_percentile_min': 60,
                'iv_percentile_max': 85,
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
    print("\n5. Optimization Summary:")
    print("-" * 70)
    print(f"Total combinations tested: {len(results_df)}")
    print(f"Combinations with trades: {len(results_df[results_df['total_trades'] > 0])}")
    print(f"\nBest parameters (Sharpe Ratio: {best_params['sharpe_ratio']:.2f}):")
    print(f"  DTE range: {int(best_params['dte_min'])}-{int(best_params['dte_max'])}")
    print(f"  Put deltas: {best_params['put_short_delta']:.2f}%/{best_params['put_long_delta']:.2f}%")
    print(f"  Call deltas: {best_params['call_short_delta']:.2f}%/{best_params['call_long_delta']:.2f}%")
    print(f"  Profit target: {best_params['profit_target']:.0%}")
    print(f"  Stop loss: {best_params['stop_loss']:.0%}")
    print(f"\nMetrics:")
    print(f"  Total return: {best_params['total_return_pct']:.2f}%")
    print(f"  Win rate: {best_params['win_rate']:.1%}")
    print(f"  Profit factor: {best_params['profit_factor']:.2f}")
    print(f"  Trades: {int(best_params['total_trades'])}")

    print("\n" + "="*70)
    print("Optimization complete!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review results in optimization_results/ directory")
    print("2. Update config/config.yaml with best parameters")
    print("3. Calculate Kelly % from backtest results")
    print("4. Run backtest comparison with Bull Put Spread")


if __name__ == '__main__':
    main()
