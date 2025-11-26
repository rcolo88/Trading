"""
Test optimizer with REAL code to trace parameter application.

This test will:
1. Load actual config and data
2. Run optimizer with 4 combinations
3. Add debug logging to trace config updates
4. Verify results are different
"""

import sys
import copy
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_real_optimizer():
    """Test optimizer with real backtest to see if parameters are applied."""
    print("\n" + "="*60)
    print("TEST: Real Optimizer with Debug Logging")
    print("="*60)

    # Import dependencies
    import yaml
    from src.optimization.parameter_optimizer import ParameterOptimizer
    from src.strategies.vertical_spreads import BullPutSpread
    from src.backtester.optopsy_wrapper import OptopsyBacktester

    # Load config
    print("\n1. Loading configuration...")
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print("   ✓ Config loaded")

    # Load data
    print("\n2. Loading synthetic data...")
    from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
    from src.data_fetchers.yahoo_options import fetch_spy_data

    options_data = load_sample_spy_options_data()

    start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start_date, end_date)

    print(f"   ✓ Options data: {len(options_data):,} rows")
    print(f"   ✓ Underlying data: {len(underlying_data):,} rows")

    # Create backtester
    print("\n3. Creating backtester...")
    backtester = OptopsyBacktester(config)
    print("   ✓ Backtester created")

    # Create optimizer
    print("\n4. Creating optimizer...")
    optimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=BullPutSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )
    print("   ✓ Optimizer created")

    # Set up MINIMAL parameter ranges for quick test
    print("\n5. Setting parameter ranges...")
    print("   Testing 2 dte_min values x 2 iv_percentile values = 4 combinations")
    optimizer.set_parameter_range('dte_min', min=1, max=2, step=1)  # Just 2 values
    optimizer.set_parameter_range('iv_percentile', min=30, max=40, step=10)  # Just 2 values

    total_combinations = optimizer.get_total_combinations()
    print(f"   Total combinations: {total_combinations}")

    # PATCH _run_single_backtest to add debug logging
    print("\n6. Adding debug instrumentation...")
    original_run_single_backtest = optimizer._run_single_backtest

    def instrumented_run_single_backtest(params, verbose=False):
        """Wrapper that logs config before running backtest."""
        print(f"\n   ┌─ Running backtest with params: {params}")

        # Create config (same as original)
        config = copy.deepcopy(optimizer.base_config)
        strategy_name = optimizer.strategy_class.__name__

        config_key_map = {
            'BullPutSpread': 'bull_put',
            'BullCallSpread': 'bull_call',
            'BearPutSpread': 'bear_put',
            'BearCallSpread': 'bear_call',
            'CallCalendarSpread': 'call_calendar',
            'PutCalendarSpread': 'put_calendar'
        }

        config_key = config_key_map.get(strategy_name)

        # Log BEFORE update
        print(f"   │  Config BEFORE:")
        if config_key in config['strategies']:
            entry = config['strategies'][config_key].get('entry', {})
            exit_cfg = config['strategies'][config_key].get('exit', {})
            print(f"   │    entry.iv_percentile_min: {entry.get('iv_percentile_min', 'N/A')}")
            print(f"   │    entry.iv_percentile_max: {entry.get('iv_percentile_max', 'N/A')}")
            print(f"   │    exit.dte_min: {exit_cfg.get('dte_min', 'N/A')}")

        # Apply parameters (same as original)
        for param_name, param_value in params.items():
            section, key = optimizer._parse_parameter_name(param_name)

            if config_key not in config['strategies']:
                config['strategies'][config_key] = {'entry': {}, 'exit': {}}

            if section not in config['strategies'][config_key]:
                config['strategies'][config_key][section] = {}

            # Check if parameter needs expansion
            expansion_map = optimizer.PARAMETER_EXPANSION.get(optimizer.strategy_type, {})
            if key in expansion_map:
                # Expand to multiple config keys
                for expanded_key in expansion_map[key]:
                    config['strategies'][config_key][section][expanded_key] = param_value
                    print(f"   │  Expanded '{param_name}' → {section}.{expanded_key} = {param_value}")
            else:
                # Use parameter as-is
                config['strategies'][config_key][section][key] = param_value
                print(f"   │  Set {section}.{key} = {param_value}")

        # Log AFTER update
        print(f"   │  Config AFTER:")
        entry = config['strategies'][config_key].get('entry', {})
        exit_cfg = config['strategies'][config_key].get('exit', {})
        print(f"   │    entry.iv_percentile_min: {entry.get('iv_percentile_min', 'N/A')}")
        print(f"   │    entry.iv_percentile_max: {entry.get('iv_percentile_max', 'N/A')}")
        print(f"   │    exit.dte_min: {exit_cfg.get('dte_min', 'N/A')}")

        # Create strategy with updated config
        strategy = optimizer.strategy_class(config)

        # Log what strategy instance received
        print(f"   │  Strategy instance config:")
        print(f"   │    entry_config: {strategy.entry_config}")
        print(f"   │    exit_config: {strategy.exit_config}")

        # Run backtest
        backtest_results = optimizer.backtester.run_backtest(
            strategy=strategy,
            options_data=optimizer.options_data,
            underlying_data=optimizer.underlying_data
        )

        # Calculate metrics
        from src.analysis.metrics import calculate_performance_metrics
        metrics = calculate_performance_metrics(backtest_results)

        print(f"   │  Results: sharpe={metrics.get('sharpe_ratio', 'N/A'):.4f}, trades={metrics.get('total_trades', 'N/A')}")
        print(f"   └─ Done")

        return metrics

    # Replace method with instrumented version
    optimizer._run_single_backtest = instrumented_run_single_backtest

    # Run optimization
    print("\n7. Running optimization (no confirmation, no checkpoints)...")
    print("="*60)

    results_df = optimizer.run_optimization(
        optimization_metric='sharpe_ratio',
        verbose=False,  # Disable verbose to reduce clutter
        confirm=False,  # Skip confirmation
        checkpoint_every=999999  # Effectively disable checkpoints
    )

    # Analyze results
    print("\n" + "="*60)
    print("8. Analyzing results...")
    print("="*60)

    print(f"\nResults DataFrame:")
    print(results_df[['dte_min', 'iv_percentile', 'sharpe_ratio', 'total_trades', 'win_rate']])

    # Check if results are different
    unique_sharpe = results_df['sharpe_ratio'].nunique()
    unique_trades = results_df['total_trades'].nunique()

    print(f"\nUniqueness check:")
    print(f"  Unique sharpe_ratio values: {unique_sharpe}")
    print(f"  Unique total_trades values: {unique_trades}")

    if unique_sharpe > 1 or unique_trades > 1:
        print(f"\n✓ PASS: Results are DIFFERENT! Parameters are being applied correctly.")
        return True
    else:
        print(f"\n✗ FAIL: All results are IDENTICAL! Parameters NOT being applied.")
        print(f"\nAll sharpe values: {results_df['sharpe_ratio'].tolist()}")
        print(f"All trade counts: {results_df['total_trades'].tolist()}")
        return False


if __name__ == '__main__':
    try:
        success = test_real_optimizer()
        if success:
            print("\n" + "="*60)
            print("CONCLUSION: Optimizer is working correctly!")
            print("="*60)
        else:
            print("\n" + "="*60)
            print("CONCLUSION: BUG CONFIRMED - Parameters not being applied!")
            print("="*60)
    except Exception as e:
        print(f"\n✗ Test CRASHED: {e}")
        import traceback
        traceback.print_exc()
