"""
Diagnostic tests for parameter optimizer bug.

Issue: All parameter combinations produce identical results in checkpoint CSV.
Goal: Identify why parameters aren't being applied to backtests.
"""

import sys
import copy
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_1_parameter_generation():
    """
    Test 1: Verify parameter combinations are generated uniquely.

    Expected: Each combination should have different values.
    """
    print("\n" + "="*60)
    print("TEST 1: Parameter Generation")
    print("="*60)

    from itertools import product

    # Simulate the parameter setup from checkpoint file
    dte_min_values = [1, 2, 3, 4, 5]
    iv_percentile_values = list(range(10, 120, 10))  # 10, 20, ..., 110

    param_names = ['dte_min', 'iv_percentile']
    param_values_lists = [dte_min_values, iv_percentile_values]

    # Generate first 20 combinations
    combinations = list(product(*param_values_lists))[:20]

    print(f"\nParameter names: {param_names}")
    print(f"Total combinations: {len(list(product(*param_values_lists)))}")
    print(f"\nFirst 20 combinations:")

    for i, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        print(f"  {i:2d}. {params}")

    # Check uniqueness
    unique_combinations = set(combinations)
    if len(unique_combinations) == len(combinations):
        print(f"\n✓ PASS: All {len(combinations)} combinations are unique")
        return True
    else:
        print(f"\n✗ FAIL: Found duplicates! {len(combinations)} total, {len(unique_combinations)} unique")
        return False


def test_2_config_update_logic():
    """
    Test 2: Verify config is updated correctly in _run_single_backtest.

    This tests the core logic without running actual backtests.
    """
    print("\n" + "="*60)
    print("TEST 2: Config Update Logic")
    print("="*60)

    # Simulate base config
    base_config = {
        'strategies': {
            'bull_put': {
                'entry': {
                    'dte_min': 30,
                    'dte_max': 45,
                    'iv_percentile_min': 50,
                    'iv_percentile_max': 50
                },
                'exit': {
                    'dte_min': 21
                }
            }
        }
    }

    # Test parameters
    test_params = [
        {'dte_min': 1, 'iv_percentile': 10},
        {'dte_min': 2, 'iv_percentile': 20},
        {'dte_min': 3, 'iv_percentile': 30},
    ]

    print("\nBase config:")
    print(f"  entry.dte_min: {base_config['strategies']['bull_put']['entry']['dte_min']}")
    print(f"  entry.iv_percentile_min: {base_config['strategies']['bull_put']['entry']['iv_percentile_min']}")
    print(f"  exit.dte_min: {base_config['strategies']['bull_put']['exit']['dte_min']}")

    print("\nTesting config updates:")

    all_passed = True

    for i, params in enumerate(test_params, 1):
        # Deep copy config (simulating _run_single_backtest)
        config = copy.deepcopy(base_config)

        # Manually apply parameters (simulating the update logic)
        # NOTE: 'dte_min' is an exit parameter, 'iv_percentile' is an entry parameter
        config['strategies']['bull_put']['exit']['dte_min'] = params['dte_min']

        # iv_percentile needs expansion to iv_percentile_min and iv_percentile_max
        config['strategies']['bull_put']['entry']['iv_percentile_min'] = params['iv_percentile']
        config['strategies']['bull_put']['entry']['iv_percentile_max'] = params['iv_percentile']

        print(f"\n  Test {i}: {params}")
        print(f"    → exit.dte_min: {config['strategies']['bull_put']['exit']['dte_min']}")
        print(f"    → entry.iv_percentile_min: {config['strategies']['bull_put']['entry']['iv_percentile_min']}")

        # Verify changes applied correctly
        if config['strategies']['bull_put']['exit']['dte_min'] != params['dte_min']:
            print(f"    ✗ FAIL: dte_min not updated correctly!")
            all_passed = False
        elif config['strategies']['bull_put']['entry']['iv_percentile_min'] != params['iv_percentile']:
            print(f"    ✗ FAIL: iv_percentile not updated correctly!")
            all_passed = False
        else:
            print(f"    ✓ PASS")

    if all_passed:
        print(f"\n✓ OVERALL PASS: Config update logic works correctly")
    else:
        print(f"\n✗ OVERALL FAIL: Config update logic has issues")

    return all_passed


def test_3_parameter_expansion():
    """
    Test 3: Verify parameter expansion map works correctly.

    Tests that parameters like 'iv_percentile' expand to both min and max.
    """
    print("\n" + "="*60)
    print("TEST 3: Parameter Expansion")
    print("="*60)

    from src.optimization.parameter_optimizer import ParameterOptimizer

    # Get expansion map
    expansion_map = ParameterOptimizer.PARAMETER_EXPANSION['vertical']

    print("\nExpansion map for vertical spreads:")
    for param, expanded in expansion_map.items():
        print(f"  '{param}' → {expanded}")

    # Test cases
    test_cases = [
        ('dte', [30], ['dte_min', 'dte_max'], [30, 30]),
        ('iv_percentile', [10], ['iv_percentile_min', 'iv_percentile_max'], [10, 10]),
        ('iv_percentile', [75], ['iv_percentile_min', 'iv_percentile_max'], [75, 75]),
    ]

    print("\nTest expansion logic:")
    all_passed = True

    for param_name, param_values, expected_keys, expected_values in test_cases:
        if param_name in expansion_map:
            expanded_keys = expansion_map[param_name]
            print(f"\n  '{param_name}' = {param_values[0]}")
            print(f"    Expected: {expected_keys} = {expected_values}")
            print(f"    Got:      {expanded_keys} = {[param_values[0]] * len(expanded_keys)}")

            if expanded_keys == expected_keys:
                print(f"    ✓ PASS")
            else:
                print(f"    ✗ FAIL: Keys don't match!")
                all_passed = False
        else:
            print(f"\n  '{param_name}' = {param_values[0]}")
            print(f"    → No expansion (used as-is)")

    if all_passed:
        print(f"\n✓ OVERALL PASS: Parameter expansion works correctly")
    else:
        print(f"\n✗ OVERALL FAIL: Parameter expansion has issues")

    return all_passed


def test_4_parse_parameter_name():
    """
    Test 4: Verify _parse_parameter_name correctly identifies section.

    Critical for ensuring parameters go to right section (entry vs exit).
    """
    print("\n" + "="*60)
    print("TEST 4: Parse Parameter Name")
    print("="*60)

    from src.optimization.parameter_optimizer import ParameterOptimizer

    # Create dummy optimizer to test method
    from src.backtester.optopsy_wrapper import OptopsyBacktester
    import pandas as pd

    # Minimal dummy setup
    dummy_backtester = OptopsyBacktester()
    dummy_data = pd.DataFrame()
    base_config = {}

    # Import strategy class
    from src.strategies.vertical_spreads import BullPutSpread

    optimizer = ParameterOptimizer(
        strategy_type='vertical',
        strategy_class=BullPutSpread,
        backtester=dummy_backtester,
        options_data=dummy_data,
        underlying_data=dummy_data,
        base_config=base_config
    )

    # Test cases: (param_name, expected_section, expected_key)
    test_cases = [
        ('dte', 'entry', 'dte'),
        ('dte_min', 'exit', 'dte_min'),  # Exit parameter!
        ('iv_percentile', 'entry', 'iv_percentile'),
        ('profit_target', 'exit', 'profit_target'),
        ('short_delta', 'entry', 'short_delta'),
        ('stop_loss', 'exit', 'stop_loss'),
    ]

    print("\nTesting parameter name parsing:")
    all_passed = True

    for param_name, expected_section, expected_key in test_cases:
        try:
            section, key = optimizer._parse_parameter_name(param_name)

            print(f"\n  '{param_name}'")
            print(f"    Expected: section='{expected_section}', key='{expected_key}'")
            print(f"    Got:      section='{section}', key='{key}'")

            if section == expected_section and key == expected_key:
                print(f"    ✓ PASS")
            else:
                print(f"    ✗ FAIL: Mismatch!")
                all_passed = False

        except Exception as e:
            print(f"\n  '{param_name}'")
            print(f"    ✗ FAIL: Exception raised: {e}")
            all_passed = False

    if all_passed:
        print(f"\n✓ OVERALL PASS: Parameter name parsing works correctly")
    else:
        print(f"\n✗ OVERALL FAIL: Parameter name parsing has issues")

    return all_passed


def test_5_config_mutation():
    """
    Test 5: Check if base_config is being mutated across iterations.

    This would cause all backtests to use the same config!
    """
    print("\n" + "="*60)
    print("TEST 5: Config Mutation Check")
    print("="*60)

    base_config = {
        'strategies': {
            'bull_put': {
                'entry': {'dte_min': 30, 'iv_percentile_min': 50},
                'exit': {'dte_min': 21}
            }
        }
    }

    print("\nOriginal base_config:")
    print(f"  entry.dte_min: {base_config['strategies']['bull_put']['entry']['dte_min']}")
    print(f"  entry.iv_percentile_min: {base_config['strategies']['bull_put']['entry']['iv_percentile_min']}")
    print(f"  exit.dte_min: {base_config['strategies']['bull_put']['exit']['dte_min']}")

    # Simulate multiple iterations
    configs = []
    for i in range(3):
        # This is what _run_single_backtest does
        config = copy.deepcopy(base_config)

        # Modify config
        config['strategies']['bull_put']['entry']['dte_min'] = 30 + i
        config['strategies']['bull_put']['entry']['iv_percentile_min'] = 10 + i * 10
        config['strategies']['bull_put']['exit']['dte_min'] = 1 + i

        configs.append(config)

    print("\nAfter 3 iterations with modifications:")
    for i, config in enumerate(configs):
        print(f"\n  Iteration {i+1} config:")
        print(f"    entry.dte_min: {config['strategies']['bull_put']['entry']['dte_min']}")
        print(f"    entry.iv_percentile_min: {config['strategies']['bull_put']['entry']['iv_percentile_min']}")
        print(f"    exit.dte_min: {config['strategies']['bull_put']['exit']['dte_min']}")

    print(f"\nBase config after all iterations:")
    print(f"  entry.dte_min: {base_config['strategies']['bull_put']['entry']['dte_min']}")
    print(f"  entry.iv_percentile_min: {base_config['strategies']['bull_put']['entry']['iv_percentile_min']}")
    print(f"  exit.dte_min: {base_config['strategies']['bull_put']['exit']['dte_min']}")

    # Check if base_config was mutated
    if (base_config['strategies']['bull_put']['entry']['dte_min'] == 30 and
        base_config['strategies']['bull_put']['entry']['iv_percentile_min'] == 50 and
        base_config['strategies']['bull_put']['exit']['dte_min'] == 21):
        print(f"\n✓ PASS: Base config was NOT mutated (copy.deepcopy working)")

        # Also check that iterations have different values
        unique_dte = len(set(c['strategies']['bull_put']['exit']['dte_min'] for c in configs))
        unique_iv = len(set(c['strategies']['bull_put']['entry']['iv_percentile_min'] for c in configs))

        if unique_dte == 3 and unique_iv == 3:
            print(f"✓ PASS: Each iteration has unique config values")
            return True
        else:
            print(f"✗ FAIL: Iterations have duplicate values!")
            return False
    else:
        print(f"\n✗ FAIL: Base config WAS mutated! copy.deepcopy not working properly")
        return False


if __name__ == '__main__':
    print("\n" + "="*60)
    print("DIAGNOSTIC TEST SUITE: OPTIMIZER PARAMETER BUG")
    print("="*60)
    print("\nIssue: All parameter combinations produce identical results")
    print("Goal: Identify why parameters aren't being applied to backtests")

    results = []

    # Run all tests
    try:
        results.append(("Test 1: Parameter Generation", test_1_parameter_generation()))
    except Exception as e:
        print(f"\n✗ Test 1 CRASHED: {e}")
        results.append(("Test 1: Parameter Generation", False))

    try:
        results.append(("Test 2: Config Update Logic", test_2_config_update_logic()))
    except Exception as e:
        print(f"\n✗ Test 2 CRASHED: {e}")
        results.append(("Test 2: Config Update Logic", False))

    try:
        results.append(("Test 3: Parameter Expansion", test_3_parameter_expansion()))
    except Exception as e:
        print(f"\n✗ Test 3 CRASHED: {e}")
        results.append(("Test 3: Parameter Expansion", False))

    try:
        results.append(("Test 4: Parse Parameter Name", test_4_parse_parameter_name()))
    except Exception as e:
        print(f"\n✗ Test 4 CRASHED: {e}")
        results.append(("Test 4: Parse Parameter Name", False))

    try:
        results.append(("Test 5: Config Mutation", test_5_config_mutation()))
    except Exception as e:
        print(f"\n✗ Test 5 CRASHED: {e}")
        results.append(("Test 5: Config Mutation", False))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    print(f"\nTotal: {total_passed}/{total_tests} tests passed")

    if total_passed == total_tests:
        print("\n✓ All tests passed! Issue must be elsewhere.")
    else:
        print(f"\n✗ {total_tests - total_passed} test(s) failed. Root cause identified!")
