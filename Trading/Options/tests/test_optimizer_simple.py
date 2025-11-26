"""
Simple test to verify optimizer bug fix.

Tests that different parameters produce different results.
"""

import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_optimizer_fix():
    """Test that optimizer applies parameters correctly."""
    print("\n" + "="*60)
    print("TEST: Optimizer Parameter Application (Post-Fix)")
    print("="*60)

    # Import dependencies
    import yaml
    from src.optimization.parameter_optimizer import ParameterOptimizer
    from src.strategies.vertical_spreads import BullPutSpread
    from src.backtester.optopsy_wrapper import OptopsyBacktester
    from src.data_fetchers.synthetic_generator import load_sample_spy_options_data
    from src.data_fetchers.yahoo_options import fetch_spy_data

    # Load config
    print("\n1. Loading configuration and data...")
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    options_data = load_sample_spy_options_data()
    start_date = options_data['quote_date'].min().strftime('%Y-%m-%d')
    end_date = options_data['quote_date'].max().strftime('%Y-%m-%d')
    underlying_data = fetch_spy_data(start_date, end_date)

    print(f"   ✓ Data loaded: {len(options_data):,} options, {len(underlying_data):,} underlying")

    # Create optimizer
    print("\n2. Creating optimizer...")
    backtester = OptopsyBacktester(config)
    optimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=BullPutSpread,
        backtester=backtester,
        options_data=options_data,
        underlying_data=underlying_data,
        base_config=config
    )

    # Set minimal parameters for quick test
    print("\n3. Setting parameter ranges...")
    print("   Testing 2 dte_min × 2 iv_percentile = 4 combinations")
    optimizer.set_parameter_range('dte_min', min=1, max=2, step=1)
    optimizer.set_parameter_range('iv_percentile', min=30, max=40, step=10)

    # Run optimization WITHOUT instrumentation (uses actual fixed code)
    print("\n4. Running optimization...")
    results_df = optimizer.run_optimization(
        optimization_metric='sharpe_ratio',
        verbose=True,
        confirm=False,
        checkpoint_every=999999
    )

    # Analyze results
    print("\n" + "="*60)
    print("5. Analyzing results...")
    print("="*60)

    print(f"\nResults summary:")
    print(results_df[['dte_min', 'iv_percentile', 'sharpe_ratio', 'total_trades']].to_string())

    # Check uniqueness
    unique_sharpe = results_df['sharpe_ratio'].nunique()
    unique_trades = results_df['total_trades'].nunique()

    print(f"\nUniqueness check:")
    print(f"  Unique sharpe_ratio values: {unique_sharpe}")
    print(f"  Unique total_trades values: {unique_trades}")
    print(f"  Sharpe values: {results_df['sharpe_ratio'].tolist()}")
    print(f"  Trade counts: {results_df['total_trades'].tolist()}")

    # Verdict
    if unique_sharpe > 1 or unique_trades > 1:
        print(f"\n{'='*60}")
        print("✓ SUCCESS: Parameters ARE being applied correctly!")
        print(f"{'='*60}")
        print(f"\nDifferent parameters produce different results.")
        print(f"Bug is FIXED!")
        return True
    else:
        print(f"\n{'='*60}")
        print("✗ FAILURE: All results are IDENTICAL")
        print(f"{'='*60}")
        print(f"\nParameters are NOT being applied.")
        print(f"Bug still exists!")
        return False


if __name__ == '__main__':
    try:
        success = test_optimizer_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test CRASHED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
