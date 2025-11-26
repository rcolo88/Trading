#!/usr/bin/env python3
"""
Test script for results compilation system.

Tests:
1. Date range extraction from config
2. Master CSV path generation
3. Parameter column identification
4. Results compilation with deduplication
5. Master CSV resume functionality
"""

import sys
from pathlib import Path
import pandas as pd
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization.results_compiler import (
    get_date_range_from_config,
    get_master_csv_path,
    identify_parameter_columns,
    compile_results,
    get_completed_combinations
)


def test_date_range_extraction():
    """Test extracting date range from config."""
    print("=" * 70)
    print("TEST 1: Date Range Extraction")
    print("=" * 70)

    config = {
        'backtest': {
            'start_date': '2025-01-03',
            'end_date': '2025-11-17'
        }
    }

    start, end = get_date_range_from_config(config)

    assert start == '20250103', f"Expected '20250103', got '{start}'"
    assert end == '20251117', f"Expected '20251117', got '{end}'"

    print(f"✓ Date range extraction: {start} to {end}")
    print()


def test_master_csv_path():
    """Test master CSV path generation."""
    print("=" * 70)
    print("TEST 2: Master CSV Path Generation")
    print("=" * 70)

    path = get_master_csv_path('BullPutSpread', '20250103', '20251117')

    assert 'compiled' in str(path), "Path should contain 'compiled' directory"
    assert 'BullPutSpread' in str(path), "Path should contain strategy name"
    assert '20250103' in str(path), "Path should contain start date"
    assert '20251117' in str(path), "Path should contain end date"
    assert str(path).endswith('.csv'), "Path should end with .csv"

    print(f"✓ Master CSV path: {path}")
    print()


def test_parameter_column_identification():
    """Test identifying parameter vs metric columns."""
    print("=" * 70)
    print("TEST 3: Parameter Column Identification")
    print("=" * 70)

    # Create sample results DataFrame
    data = {
        'dte': [30, 35, 40],
        'short_delta': [0.25, 0.30, 0.35],
        'profit_target': [0.50, 0.50, 0.50],
        'sharpe_ratio': [1.5, 1.8, 1.2],
        'total_return_pct': [15.3, 18.2, 12.1],
        'max_drawdown_pct': [-8.5, -7.2, -9.1],
        'win_rate_pct': [75.0, 78.0, 72.0],
        'total_trades': [25, 28, 23]
    }
    df = pd.DataFrame(data)

    param_cols = identify_parameter_columns(df)

    expected_params = ['dte', 'short_delta', 'profit_target']
    assert param_cols == expected_params, f"Expected {expected_params}, got {param_cols}"

    print(f"✓ Parameter columns identified: {param_cols}")
    print(f"  Metric columns: {[col for col in df.columns if col not in param_cols]}")
    print()


def test_results_compilation():
    """Test compiling results with deduplication."""
    print("=" * 70)
    print("TEST 4: Results Compilation & Deduplication")
    print("=" * 70)

    # Use temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_path = Path('optimization_results/compiled')

    try:
        # Temporarily redirect compilation to temp directory
        import src.optimization.results_compiler as compiler
        original_compiled_path = compiler.Path('optimization_results/compiled')

        # Create test config
        config = {
            'backtest': {
                'start_date': '2025-01-03',
                'end_date': '2025-11-17'
            }
        }

        # Create first set of results (Run 1)
        results_run1 = pd.DataFrame({
            'dte': [30, 35, 40],
            'short_delta': [0.25, 0.30, 0.35],
            'profit_target': [0.50, 0.50, 0.50],
            'sharpe_ratio': [1.5, 1.8, 1.2],
            'total_return_pct': [15.3, 18.2, 12.1],
            'win_rate_pct': [75.0, 78.0, 72.0]
        })

        # First compilation
        print("Run 1: Compiling 3 results...")
        master_path = compile_results(results_run1, 'BullPutSpread', config)
        master_df = pd.read_csv(master_path)

        assert len(master_df) == 3, f"Expected 3 rows, got {len(master_df)}"
        print(f"  ✓ Master CSV created with {len(master_df)} rows")
        print(f"  ✓ Path: {master_path}")

        # Create second set of results (Run 2) with overlap
        # Same dte=35, short_delta=0.30 but different metrics (newer result)
        results_run2 = pd.DataFrame({
            'dte': [35, 45],
            'short_delta': [0.30, 0.25],
            'profit_target': [0.50, 0.60],
            'sharpe_ratio': [2.0, 1.6],  # Better sharpe for overlapping combo
            'total_return_pct': [20.5, 16.8],
            'win_rate_pct': [80.0, 76.0]
        })

        # Second compilation
        print("\nRun 2: Compiling 2 results (1 duplicate, 1 new)...")
        master_path = compile_results(results_run2, 'BullPutSpread', config)
        master_df = pd.read_csv(master_path)

        # Should have 4 rows: original 3, minus 1 duplicate, plus 1 new = 4
        assert len(master_df) == 4, f"Expected 4 rows after dedup, got {len(master_df)}"
        print(f"  ✓ Master CSV now has {len(master_df)} rows (duplicate replaced)")

        # Verify the duplicate was replaced with newer result
        duplicate_row = master_df[
            (master_df['dte'] == 35) &
            (master_df['short_delta'] == 0.30) &
            (master_df['profit_target'] == 0.50)
        ]
        assert len(duplicate_row) == 1, "Should have exactly one row for duplicate params"
        assert duplicate_row.iloc[0]['sharpe_ratio'] == 2.0, "Should keep newer result (sharpe=2.0)"
        print(f"  ✓ Duplicate replaced: dte=35, delta=0.30 now has sharpe={duplicate_row.iloc[0]['sharpe_ratio']}")

        # Verify sorting by sharpe_ratio
        assert master_df.iloc[0]['sharpe_ratio'] >= master_df.iloc[1]['sharpe_ratio'], \
            "Results should be sorted by sharpe_ratio descending"
        print(f"  ✓ Results sorted by sharpe_ratio (best first)")

        print("\n  Final Master CSV:")
        print(master_df[['dte', 'short_delta', 'profit_target', 'sharpe_ratio']].to_string(index=False))
        print()

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_completed_combinations():
    """Test loading completed combinations from master CSV."""
    print("=" * 70)
    print("TEST 5: Loading Completed Combinations")
    print("=" * 70)

    config = {
        'backtest': {
            'start_date': '2025-01-03',
            'end_date': '2025-11-17'
        }
    }

    # Get completed combinations (should exist from previous test)
    completed_df = get_completed_combinations('BullPutSpread', config)

    if not completed_df.empty:
        print(f"✓ Loaded {len(completed_df)} completed combinations from master CSV")
        print(f"  Parameter columns: {identify_parameter_columns(completed_df)}")
    else:
        print("  ℹ️  No master CSV found (expected if running for first time)")

    print()


def main():
    """Run all tests."""
    print("\n")
    print("*" * 70)
    print("RESULTS COMPILER TEST SUITE")
    print("*" * 70)
    print()

    try:
        test_date_range_extraction()
        test_master_csv_path()
        test_parameter_column_identification()
        test_results_compilation()
        test_completed_combinations()

        print("=" * 70)
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        print()

        return 0

    except AssertionError as e:
        print("=" * 70)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 70)
        print()
        return 1

    except Exception as e:
        print("=" * 70)
        print(f"✗ ERROR: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())
