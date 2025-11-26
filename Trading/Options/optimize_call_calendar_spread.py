#!/usr/bin/env python3
"""
Call Calendar Spread Parameter Optimization

Optimizes parameters for Call Calendar Spread strategy and saves results.
Designed to run unattended in Mac terminal, even with screen closed.

Usage:
    # Best practice - prevents Mac sleep during optimization
    caffeinate -i python optimize_call_calendar_spread.py

    # Or simply (but Mac may sleep on battery)
    python optimize_call_calendar_spread.py

Results saved to: optimization_results/CallCalendarSpread_YYYYMMDD_HHMMSS.csv
"""

import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Any
import yaml
import pandas as pd

# Suppress warnings for clean output
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.strategies.calendar_spreads import CallCalendarSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer
from src.optimization.results_compiler import compile_results


def print_header() -> None:
    """Print script header."""
    print("\n" + "="*70)
    print("CALL CALENDAR SPREAD OPTIMIZATION")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")


def load_configuration() -> Dict[str, Any]:
    """Load configuration from config.yaml."""
    print("Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config: Dict[str, Any] = yaml.safe_load(f)
    print("  ✓ Configuration loaded\n")
    return config


def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load options and underlying data."""
    print("Loading market data...")

    # Load options data
    options_data: pd.DataFrame = load_sample_spy_options_data()

    # Load underlying data
    start_date: str = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date: str = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data: pd.DataFrame = fetch_spy_data(start_date, end_date)

    print(f"  ✓ Options data: {len(options_data):,} rows")
    print(f"  ✓ Underlying data: {len(underlying_data):,} rows")
    print(f"  ✓ Date range: {start_date} to {end_date}\n")

    return options_data, underlying_data


def setup_optimizer(config: Dict[str, Any], options_data: pd.DataFrame, underlying_data: pd.DataFrame) -> ParameterOptimizer:
    """Create and configure parameter optimizer."""
    print("Setting up optimizer...")

    backtester: OptopsyBacktester = OptopsyBacktester(config)

    optimizer: ParameterOptimizer = ParameterOptimizer(
        strategy_type='calendar',
        strategy_class=CallCalendarSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Define parameter ranges to test
    # Calendar spread parameters: near_dte (sell), far_dte (buy)
    # Note: Smaller range for testing - expand based on results
    optimizer.set_parameter_range('near_dte', min=20, max=35, step=5)       # 4 values
    optimizer.set_parameter_range('far_dte', min=45, max=75, step=10)       # 4 values
    optimizer.set_parameter_range('target_delta', min=0.45, max=0.55, step=0.05)  # 3 values
    optimizer.set_parameter_range('profit_target', min=0.20, max=0.30, step=0.05)  # 3 values

    total: int = optimizer.get_total_combinations()
    print(f"  ✓ Optimizer configured")
    print(f"  ✓ Total combinations: {total:,}")
    print(f"  ⏱  Estimated runtime: {total * 1.5 / 60:.1f} - {total * 2 / 60:.1f} minutes\n")

    return optimizer


def run_optimization(optimizer: ParameterOptimizer) -> pd.DataFrame:
    """Run the parameter optimization."""

    # ========================================================================
    # OPTIMIZATION MODE CONFIGURATION
    # ========================================================================
    # Choose optimization mode based on search space size
    total_combinations: int = optimizer.get_total_combinations()

    # RECOMMENDED: Use Optuna for large search spaces (>1000 combinations)
    if total_combinations > 1000:
        MODE = 'optuna'
        N_TRIALS = 500  # 200-1000 recommended
    else:
        # Use grid search for small search spaces
        MODE = 'grid'
        N_TRIALS = None  # Not used in grid mode

    # OVERRIDE: Uncomment to force a specific mode
    # MODE = 'optuna'
    # N_TRIALS = 500

    # MODE = 'grid'
    # ========================================================================

    print("Starting optimization...")
    print(f"Mode: {MODE.upper()}")

    if MODE == 'optuna':
        print(f"Trials: {N_TRIALS:,} (out of {total_combinations:,} possible)")
        print(f"Expected speedup: ~{total_combinations / N_TRIALS:.0f}x faster")
        print("(Progress bar will appear below - this may take several minutes)\n")

        # Run Optuna optimization
        results: pd.DataFrame = optimizer.run_optimization(
            mode='optuna',
            n_trials=N_TRIALS,
            optimization_metric='sharpe_ratio',
            optuna_n_startup_trials=20,  # Random exploration first
            optuna_enable_pruning=True   # Stop unpromising trials early
        )
    else:
        print(f"Total combinations: {total_combinations:,}")
        print("(Progress bar will appear below - this may take a while)\n")

        # Run grid search optimization
        results: pd.DataFrame = optimizer.run_optimization(
            mode='grid',
            optimization_metric='sharpe_ratio',
            confirm=False,  # No user input needed for unattended run
            num_samples=3,
            checkpoint_every=10  # Save progress every 10 combinations
        )

    return results


def save_results(results: pd.DataFrame, optimizer: ParameterOptimizer, config: Dict[str, Any]) -> None:
    """Save optimization results to CSV and compile into master."""
    # Create results directory if it doesn't exist
    results_dir: Path = Path('optimization_results')
    results_dir.mkdir(exist_ok=True)

    # Generate filename with timestamp
    timestamp: str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename: str = f'CallCalendarSpread_{timestamp}.csv'
    filepath: Path = results_dir / filename

    # Save full results
    results.to_csv(filepath, index=False)

    # Get best parameters (top 5 from already-sorted results)
    best: pd.DataFrame = results.head(5)

    # Determine which columns to display (parameters + key metrics)
    param_cols: list = list(optimizer.parameter_ranges.keys())
    metric_cols: list = ['sharpe_ratio', 'total_return_pct', 'max_drawdown_pct', 'win_rate_pct']
    display_cols: list = [col for col in param_cols + metric_cols if col in best.columns]

    # Print summary
    print("\n" + "="*70)
    print("OPTIMIZATION COMPLETE")
    print("="*70)
    print(f"Results saved to: {filepath}")
    print(f"Total combinations tested: {len(results):,}")
    print(f"\nTOP 5 PARAMETER COMBINATIONS:")
    print("-"*70)
    print(best[display_cols].to_string(index=False))
    print("="*70)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Compile results into master CSV
    print("Compiling results into master CSV...")
    master_path: Path = compile_results(
        new_results=results,
        strategy_name='CallCalendarSpread',
        config=config
    )
    print(f"✓ Compiled results saved to: {master_path}\n")


def main() -> int:
    """Main execution function."""
    try:
        print_header()

        # Check if running with caffeinate
        if 'caffeinate' not in ' '.join(os.popen('ps aux | grep caffeinate').read().split()):
            print("⚠️  WARNING: Not running with caffeinate!")
            print("   Mac may sleep during optimization (especially on battery)")
            print("   Recommended: caffeinate -i python optimize_call_calendar_spread.py\n")

        config = load_configuration()
        options_data, underlying_data = load_data()
        optimizer = setup_optimizer(config, options_data, underlying_data)
        results = run_optimization(optimizer)
        save_results(results, optimizer, config)

        return 0

    except KeyboardInterrupt:
        print("\n\n⚠️  Optimization interrupted by user (Ctrl+C)")
        print("Partial results saved in optimization_checkpoints/ directory")
        return 1

    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
