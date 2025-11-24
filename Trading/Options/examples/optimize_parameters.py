#!/usr/bin/env python3
"""
Example: Parameter Optimization for Options Strategies

Demonstrates how to use the ParameterOptimizer class to find optimal
strategy parameters through grid search.
"""

import sys
import yaml
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization.parameter_optimizer import (
    ParameterOptimizer,
    quick_optimize_calendar,
    quick_optimize_vertical
)
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.strategies.vertical_spreads import BullPutSpread
from src.strategies.calendar_spreads import CallCalendarSpread
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
import yfinance as yf


def load_data_and_config():
    """Load sample data and configuration."""
    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Load SPY options data (synthetic)
    print("Loading SPY options data...")
    options_data, underlying_data = load_sample_spy_options_data(
        start_date='2022-01-01',
        end_date='2024-12-31'
    )

    print(f"Options data: {len(options_data)} rows")
    print(f"Underlying data: {len(underlying_data)} rows")

    return options_data, underlying_data, config


def example_calendar_spread_optimization():
    """Example: Optimize call calendar spread parameters."""
    print("\n" + "="*70)
    print("EXAMPLE 1: CALENDAR SPREAD PARAMETER OPTIMIZATION")
    print("="*70 + "\n")

    # Load data
    options_data, underlying_data, config = load_data_and_config()

    # Create backtester
    backtester = OptopsyBacktester(config)

    # Create optimizer for calendar spreads
    optimizer = ParameterOptimizer(
        strategy_type='calendar',
        strategy_class=CallCalendarSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Define parameter ranges to test
    print("Setting parameter ranges...\n")

    # Entry parameters
    optimizer.set_parameter_range('near_dte_min', min=5, max=10)
    optimizer.set_parameter_range('near_dte_max', min=10, max=15)
    optimizer.set_parameter_range('far_dte_min', min=30, max=40)
    optimizer.set_parameter_range('far_dte_max', min=40, max=50)

    # Target delta for strike selection
    optimizer.set_parameter_range('target_delta', min=0.45, max=0.55, step=0.05)

    # Exit parameters
    optimizer.set_parameter_range('profit_target', min=0.20, max=0.30, step=0.05)
    optimizer.set_parameter_range('dte_exit', min=5, max=10)

    # Optional: VIX filters
    # optimizer.set_parameter_range('vix_max', min=30, max=50, step=10)

    print(f"\nTotal combinations to test: {optimizer.get_total_combinations():,}")

    # Run optimization
    results = optimizer.run_optimization(
        optimization_metric='sharpe_ratio',
        verbose=True
    )

    # Get best parameters
    print("\n" + "="*70)
    print("TOP 5 PARAMETER COMBINATIONS")
    print("="*70 + "\n")

    top_5 = optimizer.get_best_parameters(metric='sharpe_ratio', top_n=5)
    print(top_5.to_string(index=False))

    # Save results
    optimizer.save_results('backtest_results/calendar_optimization_results.csv')

    # Plot parameter sensitivity (if matplotlib available)
    try:
        optimizer.plot_parameter_sensitivity(
            param_name='profit_target',
            metric='sharpe_ratio',
            save_path='backtest_results/profit_target_sensitivity.png'
        )

        optimizer.plot_heatmap(
            param_x='profit_target',
            param_y='target_delta',
            metric='sharpe_ratio',
            save_path='backtest_results/calendar_heatmap.png'
        )
    except ImportError:
        print("\nSkipping plots (matplotlib not available)")

    return results


def example_vertical_spread_optimization():
    """Example: Optimize bull put spread parameters."""
    print("\n" + "="*70)
    print("EXAMPLE 2: VERTICAL SPREAD PARAMETER OPTIMIZATION")
    print("="*70 + "\n")

    # Load data
    options_data, underlying_data, config = load_data_and_config()

    # Create backtester
    backtester = OptopsyBacktester(config)

    # Create optimizer for vertical spreads
    optimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=BullPutSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Define parameter ranges to test
    print("Setting parameter ranges...\n")

    # Entry parameters
    optimizer.set_parameter_range('dte', min=30, max=45, step=5)

    # Delta for both legs
    optimizer.set_parameter_range('short_delta', min=0.25, max=0.40, step=0.05)
    optimizer.set_parameter_range('long_delta', min=0.10, max=0.25, step=0.05)

    # Exit parameters
    optimizer.set_parameter_range('profit_target', min=0.40, max=0.60, step=0.10)
    optimizer.set_parameter_range('stop_loss', min=1.5, max=2.5, step=0.5)

    print(f"\nTotal combinations to test: {optimizer.get_total_combinations():,}")

    # Run optimization
    results = optimizer.run_optimization(
        optimization_metric='profit_factor',
        verbose=True
    )

    # Get best parameters
    print("\n" + "="*70)
    print("TOP 5 PARAMETER COMBINATIONS")
    print("="*70 + "\n")

    top_5 = optimizer.get_best_parameters(metric='profit_factor', top_n=5)
    print(top_5.to_string(index=False))

    # Save results
    optimizer.save_results('backtest_results/vertical_optimization_results.csv')

    return results


def example_quick_optimization():
    """Example: Use quick optimization functions."""
    print("\n" + "="*70)
    print("EXAMPLE 3: QUICK OPTIMIZATION (PRE-CONFIGURED RANGES)")
    print("="*70 + "\n")

    # Load data
    options_data, underlying_data, config = load_data_and_config()

    # Create backtester
    backtester = OptopsyBacktester(config)

    # Quick calendar spread optimization
    print("Running quick calendar spread optimization...\n")
    calendar_results = quick_optimize_calendar(
        strategy_class=CallCalendarSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        config=config,
        near_dte_range=(5, 15),
        far_dte_range=(30, 45),
        delta_range=(0.45, 0.55),
        profit_target_range=(0.20, 0.30)
    )

    print("\nBest calendar spread parameters:")
    print(calendar_results.head(1).to_string(index=False))

    # Quick vertical spread optimization
    print("\n\nRunning quick vertical spread optimization...\n")
    vertical_results = quick_optimize_vertical(
        strategy_class=BullPutSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        config=config,
        dte_range=(30, 45),
        short_delta_range=(0.25, 0.40),
        long_delta_range=(0.10, 0.25),
        profit_target_range=(0.40, 0.60)
    )

    print("\nBest vertical spread parameters:")
    print(vertical_results.head(1).to_string(index=False))


if __name__ == "__main__":
    # Run examples
    # Comment out examples you don't want to run

    # Example 1: Calendar spread optimization (detailed)
    example_calendar_spread_optimization()

    # Example 2: Vertical spread optimization (detailed)
    # example_vertical_spread_optimization()

    # Example 3: Quick optimization with pre-configured ranges
    # example_quick_optimization()

    print("\n" + "="*70)
    print("OPTIMIZATION COMPLETE")
    print("="*70)
