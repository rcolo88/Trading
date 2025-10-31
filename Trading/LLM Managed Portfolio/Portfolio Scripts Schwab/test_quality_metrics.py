"""
Test Suite for Quality Metrics Calculator

This module provides comprehensive tests and examples for the QualityMetricsCalculator.

Author: Trading System
Date: 2025-10-30
"""

import sys
from typing import Dict, Any
from quality_metrics_calculator import (
    QualityMetricsCalculator,
    QualityAnalysisResult,
    QualityTier,
    format_quality_report
)


def get_sample_companies() -> Dict[str, Dict[str, Any]]:
    """
    Get sample financial data for testing across different quality tiers.

    Returns:
        Dictionary mapping company names to their financial data
    """
    companies = {
        # Elite Quality: Apple Inc. (AAPL) - Hypothetical FY2024
        'AAPL': {
            'ticker': 'AAPL',
            'revenue': 394_328_000_000,
            'cogs': 223_546_000_000,
            'sga': 26_094_000_000,
            'total_assets': 352_755_000_000,
            'net_income': 99_803_000_000,
            'shareholder_equity': 62_146_000_000,
            'free_cash_flow': 111_443_000_000,
            'market_cap': 3_000_000_000_000,
            'total_debt': 111_088_000_000,
            'nopat': 85_000_000_000,
            'roe_history': [0.46, 0.49, 0.55, 0.61, 0.56, 0.50, 0.63, 0.83, 1.00, 1.60],
            'accruals': 0.03,
            'asset_growth': 0.08,
            'margin_change': -0.01,
            'prior_year_revenue': 383_285_000_000,
            'prior_year_cogs': 214_137_000_000
        },

        # Strong Quality: Microsoft (MSFT) - Hypothetical
        'MSFT': {
            'ticker': 'MSFT',
            'revenue': 211_915_000_000,
            'cogs': 65_863_000_000,
            'sga': 55_000_000_000,
            'total_assets': 411_976_000_000,
            'net_income': 72_361_000_000,
            'shareholder_equity': 238_268_000_000,
            'free_cash_flow': 71_000_000_000,
            'market_cap': 2_800_000_000_000,
            'total_debt': 79_000_000_000,
            'nopat': 60_000_000_000,
            'roe_history': [0.28, 0.30, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42, 0.38, 0.30],
            'accruals': 0.04,
            'asset_growth': 0.12,
            'margin_change': 0.01
        },

        # Moderate Quality: Generic Retailer
        'RETAIL': {
            'ticker': 'RETAIL',
            'revenue': 50_000_000_000,
            'cogs': 38_000_000_000,
            'sga': 8_000_000_000,
            'total_assets': 40_000_000_000,
            'net_income': 2_500_000_000,
            'shareholder_equity': 15_000_000_000,
            'free_cash_flow': 1_500_000_000,
            'market_cap': 35_000_000_000,
            'total_debt': 12_000_000_000,
            'nopat': 2_200_000_000,
            'roe_history': [0.14, 0.15, 0.13, 0.16, 0.14, 0.12, 0.15, 0.14, 0.16, 0.17],
            'accruals': 0.04,
            'asset_growth': 0.15,
            'margin_change': -0.02
        },

        # Weak Quality with Red Flags: Troubled Company
        'TROUBLE': {
            'ticker': 'TROUBLE',
            'revenue': 20_000_000_000,
            'cogs': 18_000_000_000,
            'sga': 3_000_000_000,
            'total_assets': 25_000_000_000,
            'net_income': -500_000_000,  # Negative
            'shareholder_equity': 5_000_000_000,
            'free_cash_flow': -800_000_000,  # Negative FCF
            'market_cap': 8_000_000_000,
            'total_debt': 15_000_000_000,  # High leverage
            'nopat': -300_000_000,
            'roe_history': [0.08, 0.06, 0.05, 0.03, 0.02, 0.01, -0.02, -0.05, -0.08, -0.10],
            'accruals': 0.08,  # High accruals
            'asset_growth': 0.25,  # Excessive growth
            'margin_change': -0.05,  # Deteriorating
            'prior_year_revenue': 22_000_000_000,
            'prior_year_cogs': 17_500_000_000
        },

        # High Growth Tech: NVIDIA-like profile
        'NVDA_LIKE': {
            'ticker': 'NVDA_LIKE',
            'revenue': 60_922_000_000,
            'cogs': 16_621_000_000,
            'sga': 11_000_000_000,
            'total_assets': 65_728_000_000,
            'net_income': 29_760_000_000,
            'shareholder_equity': 42_985_000_000,
            'free_cash_flow': 27_000_000_000,
            'market_cap': 2_200_000_000_000,
            'total_debt': 10_000_000_000,
            'nopat': 28_000_000_000,
            'roe_history': [0.25, 0.28, 0.32, 0.38, 0.45, 0.52, 0.60, 0.68, 0.75, 0.69],
            'accruals': 0.02,
            'asset_growth': 0.18,
            'margin_change': 0.03
        }
    }

    return companies


def run_basic_test():
    """Test basic functionality with a single company."""
    print("=" * 80)
    print("TEST 1: Basic Quality Metrics Calculation")
    print("=" * 80)

    calculator = QualityMetricsCalculator()
    companies = get_sample_companies()

    # Test Apple
    result = calculator.calculate_quality_metrics(companies['AAPL'])

    print(f"\nTicker: {result.ticker}")
    print(f"Composite Score: {result.composite_score}/100")
    print(f"Quality Tier: {result.tier.value}")
    print(f"Red Flags: {len(result.red_flags)}")
    print(f"Consistent ROE Performer: {result.is_consistent_roe_performer}")

    print("\nMetric Breakdown:")
    for ms in result.metric_scores:
        print(f"  {ms.name:25} | Value: {ms.value:7.2%} | Score: {ms.score:4.1f}/10 | "
              f"Weighted: {ms.weighted_score:5.1f}")

    if result.red_flags:
        print("\nRed Flags:")
        for rf in result.red_flags:
            print(f"  [{rf.severity}] {rf.category}: {rf.description}")

    print("\n" + "=" * 80)
    print("✓ Basic test passed")


def run_multi_company_test():
    """Test quality calculation across multiple companies with different tiers."""
    print("\n" + "=" * 80)
    print("TEST 2: Multi-Company Quality Comparison")
    print("=" * 80)

    calculator = QualityMetricsCalculator()
    companies = get_sample_companies()

    results = {}
    for ticker, data in companies.items():
        try:
            result = calculator.calculate_quality_metrics(data)
            results[ticker] = result
            print(f"\n{ticker:12} | Score: {result.composite_score:5.1f} | "
                  f"Tier: {result.tier.value:10} | Red Flags: {len(result.red_flags)}")
        except Exception as e:
            print(f"\n{ticker:12} | ERROR: {str(e)}")

    # Summary table
    print("\n" + "-" * 80)
    print("DETAILED COMPARISON:")
    print("-" * 80)
    print(f"{'Ticker':<12} {'Score':<8} {'Tier':<12} {'GP':<8} {'ROE':<8} {'OP':<8} {'FCF':<8} {'ROIC':<8}")
    print("-" * 80)

    for ticker, result in results.items():
        metrics_dict = {ms.name: ms.value for ms in result.metric_scores}
        print(f"{ticker:<12} {result.composite_score:<8.1f} {result.tier.value:<12} "
              f"{metrics_dict.get('gross_profitability', 0):<8.2%} "
              f"{metrics_dict.get('roe', 0):<8.2%} "
              f"{metrics_dict.get('operating_profitability', 0):<8.2%} "
              f"{metrics_dict.get('fcf_yield', 0):<8.2%} "
              f"{metrics_dict.get('roic', 0):<8.2%}")

    print("\n" + "=" * 80)
    print("✓ Multi-company test passed")


def run_red_flag_detection_test():
    """Test red flag detection with troubled company."""
    print("\n" + "=" * 80)
    print("TEST 3: Red Flag Detection")
    print("=" * 80)

    calculator = QualityMetricsCalculator()
    companies = get_sample_companies()

    result = calculator.calculate_quality_metrics(companies['TROUBLE'])

    print(f"\nAnalyzing: {result.ticker}")
    print(f"Composite Score: {result.composite_score}/100")
    print(f"Quality Tier: {result.tier.value}")
    print(f"\nRed Flags Detected: {len(result.red_flags)}")

    if result.red_flags:
        # Group by severity
        high = [rf for rf in result.red_flags if rf.severity == "HIGH"]
        medium = [rf for rf in result.red_flags if rf.severity == "MEDIUM"]
        low = [rf for rf in result.red_flags if rf.severity == "LOW"]

        if high:
            print(f"\n  HIGH SEVERITY ({len(high)}):")
            for rf in high:
                print(f"    • {rf.category}")
                print(f"      {rf.description}")

        if medium:
            print(f"\n  MEDIUM SEVERITY ({len(medium)}):")
            for rf in medium:
                print(f"    • {rf.category}")
                print(f"      {rf.description}")

        if low:
            print(f"\n  LOW SEVERITY ({len(low)}):")
            for rf in low:
                print(f"    • {rf.category}")

    print("\n" + "=" * 80)
    print("✓ Red flag detection test passed")


def run_percentile_ranking_test():
    """Test percentile ranking against peer group."""
    print("\n" + "=" * 80)
    print("TEST 4: Percentile Ranking vs Peers")
    print("=" * 80)

    calculator = QualityMetricsCalculator()
    companies = get_sample_companies()

    # Use AAPL as target, others as peers
    target_ticker = 'AAPL'
    target_data = companies[target_ticker]
    peer_data = [data for ticker, data in companies.items() if ticker != target_ticker]

    result = calculator.calculate_percentile_scores(target_ticker, target_data, peer_data)

    print(f"\nTarget Company: {result.ticker}")
    print(f"Peer Group Size: {len(peer_data)}")
    print(f"\nMetric Rankings:")
    print("-" * 70)

    for ms in result.metric_scores:
        percentile_str = f"{ms.percentile:.1f}%" if ms.percentile is not None else "N/A"
        print(f"{ms.name:25} | Value: {ms.value:7.2%} | "
              f"Score: {ms.score:4.1f}/10 | Percentile: {percentile_str:>6}")

    print("\n" + "=" * 80)
    print("✓ Percentile ranking test passed")


def run_full_report_test():
    """Test full report generation."""
    print("\n" + "=" * 80)
    print("TEST 5: Full Report Generation")
    print("=" * 80)

    calculator = QualityMetricsCalculator()
    companies = get_sample_companies()

    # Generate report for NVDA-like company
    result = calculator.calculate_quality_metrics(companies['NVDA_LIKE'])

    # Use the format_quality_report function
    full_report = format_quality_report(result, include_raw_data=True)
    print(full_report)

    print("\n" + "=" * 80)
    print("✓ Full report generation test passed")


def run_edge_case_tests():
    """Test edge cases and error handling."""
    print("\n" + "=" * 80)
    print("TEST 6: Edge Cases and Error Handling")
    print("=" * 80)

    calculator = QualityMetricsCalculator()

    # Test 1: Missing required field
    print("\n1. Testing missing required field...")
    try:
        incomplete_data = {
            'ticker': 'TEST',
            'revenue': 100_000_000,
            # Missing other required fields
        }
        calculator.calculate_quality_metrics(incomplete_data)
        print("  ✗ FAILED: Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ PASSED: Correctly raised ValueError - {str(e)}")

    # Test 2: Zero denominator
    print("\n2. Testing zero shareholder equity...")
    try:
        zero_equity = {
            'ticker': 'TEST',
            'revenue': 100_000_000,
            'cogs': 60_000_000,
            'sga': 20_000_000,
            'total_assets': 50_000_000,
            'net_income': 10_000_000,
            'shareholder_equity': 0,  # Zero!
            'free_cash_flow': 5_000_000,
            'market_cap': 100_000_000,
            'total_debt': 20_000_000,
            'nopat': 8_000_000
        }
        calculator.calculate_quality_metrics(zero_equity)
        print("  ✗ FAILED: Should have raised ValueError")
    except ValueError as e:
        print(f"  ✓ PASSED: Correctly raised ValueError - {str(e)}")

    # Test 3: Extreme values (all perfect metrics)
    print("\n3. Testing perfect metrics...")
    try:
        perfect_company = {
            'ticker': 'PERFECT',
            'revenue': 100_000_000,
            'cogs': 20_000_000,  # 80% gross margin
            'sga': 10_000_000,
            'total_assets': 100_000_000,
            'net_income': 50_000_000,  # 50% ROE
            'shareholder_equity': 100_000_000,
            'free_cash_flow': 20_000_000,  # 10% FCF yield
            'market_cap': 200_000_000,
            'total_debt': 10_000_000,
            'nopat': 45_000_000,  # 40%+ ROIC
            'accruals': 0.01,
            'asset_growth': 0.10,
            'margin_change': 0.02
        }
        result = calculator.calculate_quality_metrics(perfect_company)
        print(f"  ✓ PASSED: Score = {result.composite_score:.1f}, Tier = {result.tier.value}")
    except Exception as e:
        print(f"  ✗ FAILED: {str(e)}")

    # Test 4: Extreme values (all terrible metrics)
    print("\n4. Testing terrible metrics...")
    try:
        terrible_company = {
            'ticker': 'TERRIBLE',
            'revenue': 100_000_000,
            'cogs': 95_000_000,  # 5% gross margin
            'sga': 10_000_000,
            'total_assets': 200_000_000,
            'net_income': -20_000_000,  # Negative
            'shareholder_equity': 50_000_000,
            'free_cash_flow': -10_000_000,  # Negative
            'market_cap': 30_000_000,
            'total_debt': 150_000_000,  # 3x D/E
            'nopat': -5_000_000,
            'accruals': 0.10,
            'asset_growth': 0.30,
            'margin_change': -0.10
        }
        result = calculator.calculate_quality_metrics(terrible_company)
        print(f"  ✓ PASSED: Score = {result.composite_score:.1f}, Tier = {result.tier.value}")
        print(f"    Red Flags: {len(result.red_flags)}")
    except Exception as e:
        print(f"  ✗ FAILED: {str(e)}")

    print("\n" + "=" * 80)
    print("✓ Edge case tests completed")


def run_all_tests():
    """Run all test suites."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "QUALITY METRICS CALCULATOR TEST SUITE" + " " * 21 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        run_basic_test,
        run_multi_company_test,
        run_red_flag_detection_test,
        run_percentile_ranking_test,
        run_full_report_test,
        run_edge_case_tests
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n✗ TEST FAILED: {test_func.__name__}")
            print(f"  Error: {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Final summary
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "TEST SUMMARY" + " " * 36 + "║")
    print("╠" + "=" * 78 + "╣")
    print(f"║  Total Tests: {len(tests):<10}  Passed: {passed:<10}  Failed: {failed:<10}" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! 🎉\n")
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED ⚠️\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
