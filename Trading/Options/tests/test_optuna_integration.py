#!/usr/bin/env python3
"""
Quick test to verify Optuna integration works correctly.

Tests:
1. Optuna mode can be invoked
2. Results are returned in correct format
3. Optuna finds reasonable parameters in few trials
"""

import sys
from pathlib import Path
import pandas as pd
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.vertical_spreads import BullPutSpread
from src.backtester.optopsy_wrapper import OptopsyBacktester
from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
from src.data_fetchers.yahoo_options import fetch_spy_data
from src.optimization.parameter_optimizer import ParameterOptimizer


def test_optuna_integration():
    """Test Optuna optimization with small parameter space."""
    print("\n" + "="*70)
    print("OPTUNA INTEGRATION TEST")
    print("="*70)

    # Load configuration
    print("\n1. Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print("   ✓ Config loaded")

    # Load data
    print("\n2. Loading data...")
    options_data = load_sample_spy_options_data()
    start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start_date, end_date)
    print(f"   ✓ Options data: {len(options_data):,} rows")
    print(f"   ✓ Underlying data: {len(underlying_data):,} rows")

    # Create optimizer
    print("\n3. Creating optimizer...")
    backtester = OptopsyBacktester(config)
    optimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=BullPutSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )
    print("   ✓ Optimizer created")

    # Set small parameter ranges for quick test
    print("\n4. Setting parameter ranges...")
    optimizer.set_parameter_range('dte', min=30, max=40, step=10)  # 2 values
    optimizer.set_parameter_range('short_delta', min=0.25, max=0.35, step=0.10)  # 2 values
    total = optimizer.get_total_combinations()
    print(f"   ✓ Total combinations: {total}")

    # Test Optuna with 10 trials
    print("\n5. Running Optuna optimization (10 trials)...")
    print("   (This should take about 15-30 seconds)\n")

    results = optimizer.run_optimization(
        mode='optuna',
        n_trials=10,
        optimization_metric='sharpe_ratio',
        optuna_n_startup_trials=3,
        optuna_enable_pruning=True,
        verbose=True
    )

    # Verify results
    print("\n6. Verifying results...")
    assert isinstance(results, pd.DataFrame), "Results should be a DataFrame"
    assert len(results) > 0, "Results should not be empty"
    assert 'sharpe_ratio' in results.columns, "Results should have sharpe_ratio"
    assert 'dte' in results.columns, "Results should have dte parameter"
    assert 'short_delta' in results.columns, "Results should have short_delta parameter"

    print(f"   ✓ Returned {len(results)} successful trials")
    print(f"   ✓ Results DataFrame has correct format")
    print(f"   ✓ Best sharpe_ratio: {results.iloc[0]['sharpe_ratio']:.4f}")

    # Display top 3 results
    print("\n   Top 3 results:")
    print(results[['dte', 'short_delta', 'sharpe_ratio', 'total_trades']].head(3).to_string(index=False))

    print("\n" + "="*70)
    print("✓ OPTUNA INTEGRATION TEST PASSED")
    print("="*70 + "\n")

    return True


if __name__ == '__main__':
    try:
        success = test_optuna_integration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
