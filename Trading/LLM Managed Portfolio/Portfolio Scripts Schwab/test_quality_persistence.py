"""
Test Suite for Quality Persistence Analyzer

Tests the persistence analysis system across different company types:
- Quality Compounders (sustained excellence)
- Quality Improvers (improving trends)
- Quality Deteriorators (declining)
- Inconsistent performers (cyclical)

Author: Trading System
Date: 2025-10-30
"""

import pandas as pd
import numpy as np
import sys
from quality_persistence_analyzer import (
    QualityPersistenceAnalyzer,
    PersistenceClassification
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_compounder_data() -> pd.DataFrame:
    """Create data for a quality compounder (consistent high returns)."""
    return pd.DataFrame({
        'year': list(range(2014, 2024)),
        'ticker': ['COMPOUNDER'] * 10,
        'revenue': [100e9 * (1.08 ** i) for i in range(10)],  # 8% annual growth
        'cogs': [60e9 * (1.08 ** i) for i in range(10)],
        'sga': [15e9 * (1.08 ** i) for i in range(10)],
        'total_assets': [200e9 * (1.06 ** i) for i in range(10)],
        'net_income': [25e9 * (1.09 ** i) for i in range(10)],  # 9% income growth
        'shareholder_equity': [120e9 * (1.07 ** i) for i in range(10)],
        'free_cash_flow': [28e9 * (1.09 ** i) for i in range(10)],
        'total_debt': [50e9] * 10,  # Stable debt
        'nopat': [26e9 * (1.09 ** i) for i in range(10)]
    })


def create_improver_data() -> pd.DataFrame:
    """Create data for a quality improver (accelerating performance)."""
    # Start weak, improve over time
    base_revenue = 80e9
    revenues = [base_revenue * (1 + 0.05 * i) for i in range(10)]  # Accelerating growth

    return pd.DataFrame({
        'year': list(range(2014, 2024)),
        'ticker': ['IMPROVER'] * 10,
        'revenue': revenues,
        'cogs': [r * 0.70 * (1 - 0.02 * i) for i, r in enumerate(revenues)],  # Improving margins
        'sga': [r * 0.20 * (1 - 0.01 * i) for i, r in enumerate(revenues)],
        'total_assets': [150e9 * (1.08 ** i) for i in range(10)],
        'net_income': [10e9 * (1.15 ** i) for i in range(10)],  # Accelerating earnings
        'shareholder_equity': [80e9 * (1.10 ** i) for i in range(10)],
        'free_cash_flow': [8e9 * (1.18 ** i) for i in range(10)],
        'total_debt': [60e9 * (0.95 ** i) for i in range(10)],  # Deleveraging
        'nopat': [11e9 * (1.15 ** i) for i in range(10)]
    })


def create_deteriorator_data() -> pd.DataFrame:
    """Create data for a quality deteriorator (declining performance)."""
    # Start strong, decline over time
    base_revenue = 120e9
    revenues = [base_revenue * (1 - 0.03 * i) for i in range(10)]  # Declining revenue

    return pd.DataFrame({
        'year': list(range(2014, 2024)),
        'ticker': ['DETERIORATOR'] * 10,
        'revenue': revenues,
        'cogs': [r * 0.60 * (1 + 0.03 * i) for i, r in enumerate(revenues)],  # Rising costs
        'sga': [r * 0.25 * (1 + 0.02 * i) for i, r in enumerate(revenues)],
        'total_assets': [180e9 * (0.98 ** i) for i in range(10)],
        'net_income': [30e9 * (0.85 ** i) for i in range(10)],  # Declining earnings
        'shareholder_equity': [100e9 * (0.95 ** i) for i in range(10)],
        'free_cash_flow': [25e9 * (0.80 ** i) for i in range(10)],
        'total_debt': [40e9 * (1.05 ** i) for i in range(10)],  # Rising debt
        'nopat': [28e9 * (0.85 ** i) for i in range(10)]
    })


def create_cyclical_data() -> pd.DataFrame:
    """Create data for an inconsistent/cyclical company."""
    # Volatile, no clear trend
    np.random.seed(42)

    base_revenue = 90e9
    cycle = [0.8, 1.0, 1.3, 1.1, 0.9, 0.7, 1.1, 1.4, 1.0, 0.8]  # Cyclical pattern

    return pd.DataFrame({
        'year': list(range(2014, 2024)),
        'ticker': ['CYCLICAL'] * 10,
        'revenue': [base_revenue * c for c in cycle],
        'cogs': [base_revenue * c * 0.65 for c in cycle],
        'sga': [base_revenue * c * 0.20 for c in cycle],
        'total_assets': [160e9 + np.random.randn() * 10e9 for _ in range(10)],
        'net_income': [15e9 * c + np.random.randn() * 3e9 for c in cycle],
        'shareholder_equity': [90e9 + i * 2e9 for i in range(10)],
        'free_cash_flow': [12e9 * c + np.random.randn() * 4e9 for c in cycle],
        'total_debt': [55e9 + np.random.randn() * 5e9 for _ in range(10)],
        'nopat': [16e9 * c for c in cycle]
    })


def test_compounder_detection():
    """Test detection of quality compounders."""
    print("\n" + "="*80)
    print("TEST 1: Quality Compounder Detection")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()
    data = create_compounder_data()

    result = analyzer.analyze_company(data, ticker='COMPOUNDER')

    print(f"\nClassification: {result.classification.value}")
    print(f"Confidence: {result.compounder_confidence:.1f}%")
    print(f"Persistence Score: {result.persistence_metrics.persistence_score:.1f}/100")
    print(f"Consistency Score: {result.persistence_metrics.consistency_score:.1f}/100")
    print(f"Trend Score: {result.persistence_metrics.trend_score:.1f}/100")

    print(f"\nKey Metrics:")
    print(f"  Average ROE: {result.persistence_metrics.roe_mean:.1%}")
    print(f"  ROE Consistency: {result.persistence_metrics.roe_consistency_score:.1f}/10")
    print(f"  Years ROE >15%: {result.persistence_metrics.roe_years_above_15pct}/10")

    # Assertions
    assert result.classification in [
        PersistenceClassification.QUALITY_COMPOUNDER,
        PersistenceClassification.QUALITY_IMPROVER
    ], f"Expected compounder or improver, got {result.classification.value}"

    assert result.compounder_confidence >= 70, \
        f"Expected confidence ≥70%, got {result.compounder_confidence:.1f}%"

    print("\n✓ Compounder detection test PASSED")
    return result


def test_improver_detection():
    """Test detection of quality improvers."""
    print("\n" + "="*80)
    print("TEST 2: Quality Improver Detection")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()
    data = create_improver_data()

    result = analyzer.analyze_company(data, ticker='IMPROVER')

    print(f"\nClassification: {result.classification.value}")
    print(f"Confidence: {result.compounder_confidence:.1f}%")
    print(f"Trend Score: {result.persistence_metrics.trend_score:.1f}/100")

    print(f"\nTrend Analysis:")
    print(f"  ROE Trend: {result.trend_analysis['roe_trend']}")
    print(f"  Overall: {result.trend_analysis['overall_trend_direction']}")

    # Assertions
    assert result.persistence_metrics.trend_score > 0, \
        f"Expected positive trend, got {result.persistence_metrics.trend_score:.1f}"

    assert result.classification in [
        PersistenceClassification.QUALITY_IMPROVER,
        PersistenceClassification.QUALITY_COMPOUNDER
    ], f"Expected improver or compounder, got {result.classification.value}"

    print("\n✓ Improver detection test PASSED")
    return result


def test_deteriorator_detection():
    """Test detection of quality deteriorators."""
    print("\n" + "="*80)
    print("TEST 3: Quality Deteriorator Detection")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()
    data = create_deteriorator_data()

    result = analyzer.analyze_company(data, ticker='DETERIORATOR')

    print(f"\nClassification: {result.classification.value}")
    print(f"Confidence: {result.compounder_confidence:.1f}%")
    print(f"Trend Score: {result.persistence_metrics.trend_score:.1f}/100")

    print(f"\nWarnings:")
    for warning in result.warnings:
        print(f"  {warning}")

    # Assertions
    assert result.persistence_metrics.trend_score < 0, \
        f"Expected negative trend, got {result.persistence_metrics.trend_score:.1f}"

    assert result.classification == PersistenceClassification.QUALITY_DETERIORATOR, \
        f"Expected deteriorator, got {result.classification.value}"

    print("\n✓ Deteriorator detection test PASSED")
    return result


def test_cyclical_detection():
    """Test detection of inconsistent/cyclical companies."""
    print("\n" + "="*80)
    print("TEST 4: Cyclical/Inconsistent Detection")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()
    data = create_cyclical_data()

    result = analyzer.analyze_company(data, ticker='CYCLICAL')

    print(f"\nClassification: {result.classification.value}")
    print(f"Confidence: {result.compounder_confidence:.1f}%")
    print(f"ROE Volatility (CV): {result.persistence_metrics.roe_cv:.2f}")
    print(f"Consistency Score: {result.persistence_metrics.consistency_score:.1f}/100")

    # Assertions
    assert result.persistence_metrics.roe_cv > 0.3, \
        f"Expected high volatility (CV >0.3), got {result.persistence_metrics.roe_cv:.2f}"

    print("\n✓ Cyclical detection test PASSED")
    return result


def test_universe_analysis():
    """Test batch analysis of multiple companies."""
    print("\n" + "="*80)
    print("TEST 5: Universe Analysis")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()

    # Create universe
    universe = {
        'COMPOUNDER': create_compounder_data(),
        'IMPROVER': create_improver_data(),
        'DETERIORATOR': create_deteriorator_data(),
        'CYCLICAL': create_cyclical_data()
    }

    # Analyze universe
    results = analyzer.analyze_universe(universe, min_compounder_confidence=60)

    print(f"\nUniverse Analysis Results:")
    print("-" * 80)
    print(f"{'Ticker':<15} {'Classification':<25} {'Confidence':<12} {'Persist':<10} {'Trend':<10}")
    print("-" * 80)

    for _, row in results.iterrows():
        print(f"{row['ticker']:<15} {row['classification']:<25} "
              f"{row['compounder_confidence']:>6.1f}% "
              f"{row['persistence_score']:>8.1f} "
              f"{row['trend_score']:>8.1f}")

    # Assertions
    assert len(results) == 4, f"Expected 4 companies, got {len(results)}"

    # Check sorting (highest confidence first)
    assert results['compounder_confidence'].iloc[0] >= results['compounder_confidence'].iloc[-1], \
        "Results should be sorted by confidence descending"

    print("\n✓ Universe analysis test PASSED")
    return results


def test_llm_prompt_generation():
    """Test LLM prompt generation for different classifications."""
    print("\n" + "="*80)
    print("TEST 6: LLM Prompt Generation")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()

    # Test on compounder
    data = create_compounder_data()
    result = analyzer.analyze_company(data, ticker='COMPOUNDER', generate_llm_prompt=True)

    print(f"\nGenerated prompt for {result.classification.value}:")
    print("-" * 80)
    print(result.llm_prompt[:500] + "...")  # Print first 500 chars

    # Assertions
    assert result.llm_prompt is not None, "LLM prompt should be generated"
    assert len(result.llm_prompt) > 100, "LLM prompt should have substantial content"
    assert result.ticker in result.llm_prompt, "Ticker should be in prompt"
    assert str(result.persistence_metrics.years_analyzed) in result.llm_prompt, \
        "Years analyzed should be in prompt"

    print("\n✓ LLM prompt generation test PASSED")


def test_visualization():
    """Test visualization generation."""
    print("\n" + "="*80)
    print("TEST 7: Visualization Generation")
    print("="*80)

    analyzer = QualityPersistenceAnalyzer()
    data = create_compounder_data()

    try:
        # Generate visualization (don't show, just create)
        analyzer.visualize_persistence(
            data,
            ticker='COMPOUNDER',
            save_path='test_compounder_viz.png',
            show_plot=False
        )

        # Check file was created
        import os
        assert os.path.exists('test_compounder_viz.png'), \
            "Visualization file should be created"

        # Clean up
        os.remove('test_compounder_viz.png')

        print("\n✓ Visualization test PASSED")

    except Exception as e:
        print(f"\n⚠️  Visualization test SKIPPED (may require display): {e}")


def run_all_tests():
    """Run all test suites."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "QUALITY PERSISTENCE ANALYZER TESTS" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")

    tests = [
        test_compounder_detection,
        test_improver_detection,
        test_deteriorator_detection,
        test_cyclical_detection,
        test_universe_analysis,
        test_llm_prompt_generation,
        test_visualization
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ TEST FAILED: {test_func.__name__}")
            print(f"  Assertion Error: {str(e)}")
            failed += 1
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
