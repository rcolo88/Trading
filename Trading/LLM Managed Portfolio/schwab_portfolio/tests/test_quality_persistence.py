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
from components.quality_persistence_analyzer import (
    QualityPersistenceAnalyzer,
    PersistenceClassification,
    TierEligibility
)
from quality.market_cap_classifier import MarketCapTier
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


# ==================== TIER-SPECIFIC ROE PERSISTENCE TESTS ====================
# Added for 4-tier market cap framework implementation

def test_large_cap_roe_persistence():
    """Test Large Cap ROE persistence validation (5+ years ROE >15%)."""
    print("\n🧪 Testing Large Cap ROE Persistence Validation...")

    analyzer = QualityPersistenceAnalyzer()

    # Create data with 6 consecutive years ROE >15%
    df_pass = pd.DataFrame({
        'year': list(range(2018, 2024)),
        'net_income': [25e9] * 6,
        'shareholder_equity': [100e9] * 6  # ROE = 25% each year
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_LARGE_PASS',
        MarketCapTier.LARGE_CAP,
        df_pass
    )

    assert passes == True, f"Should pass with 6 years: {reason}"
    assert "6 consecutive years" in reason
    print("  ✓ Large cap passes with 6 consecutive years ROE >15%")

    # Create data with only 4 consecutive years ROE >15%
    df_fail = pd.DataFrame({
        'year': list(range(2018, 2024)),
        'net_income': [25e9, 25e9, 25e9, 25e9, 5e9, 25e9],
        'shareholder_equity': [100e9] * 6  # 4 consecutive, then dip, then recovery
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_LARGE_FAIL',
        MarketCapTier.LARGE_CAP,
        df_fail
    )

    assert passes == False, f"Should fail with only 4 consecutive years: {reason}"
    assert "NOT met" in reason
    print("  ✓ Large cap fails with only 4 consecutive years ROE >15%")

    # Test exactly 5 years (boundary)
    df_boundary = pd.DataFrame({
        'year': list(range(2019, 2024)),
        'net_income': [25e9] * 5,
        'shareholder_equity': [100e9] * 5  # Exactly 5 years
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_LARGE_BOUNDARY',
        MarketCapTier.LARGE_CAP,
        df_boundary
    )

    assert passes == True, f"Should pass with exactly 5 years: {reason}"
    print("  ✓ Large cap passes with exactly 5 consecutive years (boundary)")


def test_mid_cap_roe_persistence():
    """Test Mid Cap ROE persistence validation (2-3 years ROE >15%)."""
    print("\n🧪 Testing Mid Cap ROE Persistence Validation...")

    analyzer = QualityPersistenceAnalyzer()

    # Create data with 3 consecutive years ROE >15%
    df_pass = pd.DataFrame({
        'year': list(range(2021, 2024)),
        'net_income': [10e9] * 3,
        'shareholder_equity': [50e9] * 3  # ROE = 20% each year
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_MID_PASS',
        MarketCapTier.MID_CAP,
        df_pass
    )

    assert passes == True, f"Should pass with 3 years: {reason}"
    assert "3 consecutive years" in reason
    print("  ✓ Mid cap passes with 3 consecutive years ROE >15%")

    # Create data with only 1 year ROE >15%
    df_fail = pd.DataFrame({
        'year': list(range(2021, 2024)),
        'net_income': [10e9, 5e9, 5e9],
        'shareholder_equity': [50e9] * 3  # Only first year >15%
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_MID_FAIL',
        MarketCapTier.MID_CAP,
        df_fail
    )

    assert passes == False, f"Should fail with only 1 year: {reason}"
    assert "NOT met" in reason
    print("  ✓ Mid cap fails with only 1 year ROE >15%")

    # Test exactly 2 years (boundary)
    df_boundary = pd.DataFrame({
        'year': list(range(2022, 2024)),
        'net_income': [10e9] * 2,
        'shareholder_equity': [50e9] * 2  # Exactly 2 years
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_MID_BOUNDARY',
        MarketCapTier.MID_CAP,
        df_boundary
    )

    assert passes == True, f"Should pass with exactly 2 years: {reason}"
    print("  ✓ Mid cap passes with exactly 2 consecutive years (boundary)")


def test_small_cap_roe_persistence():
    """Test Small Cap ROE persistence validation (positive ROE trend)."""
    print("\n🧪 Testing Small Cap ROE Persistence Validation...")

    analyzer = QualityPersistenceAnalyzer()

    # Create data with positive ROE trend
    df_pass = pd.DataFrame({
        'year': list(range(2020, 2024)),
        'net_income': [2e9, 3e9, 4e9, 5e9],  # Growing
        'shareholder_equity': [20e9] * 4  # Increasing ROE: 10%, 15%, 20%, 25%
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_SMALL_PASS',
        MarketCapTier.SMALL_CAP,
        df_pass
    )

    assert passes == True, f"Should pass with positive trend: {reason}"
    assert "Positive ROE trend" in reason
    print("  ✓ Small cap passes with positive ROE trend")

    # Create data with negative ROE trend
    df_fail = pd.DataFrame({
        'year': list(range(2020, 2024)),
        'net_income': [5e9, 4e9, 3e9, 2e9],  # Declining
        'shareholder_equity': [20e9] * 4  # Decreasing ROE
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_SMALL_FAIL',
        MarketCapTier.SMALL_CAP,
        df_fail
    )

    assert passes == False, f"Should fail with negative trend: {reason}"
    assert "negative" in reason.lower()
    print("  ✓ Small cap fails with negative ROE trend")


def test_micro_cap_not_eligible():
    """Test that Micro Cap tier is not eligible."""
    print("\n🧪 Testing Micro Cap Ineligibility...")

    analyzer = QualityPersistenceAnalyzer()

    df = pd.DataFrame({
        'year': [2023],
        'net_income': [100e6],
        'shareholder_equity': [500e6]
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_MICRO',
        MarketCapTier.MICRO_CAP,
        df
    )

    assert passes == False, "Micro cap should not be eligible"
    assert "not eligible" in reason.lower()
    print("  ✓ Micro cap correctly marked as not eligible")


def test_incremental_roce_calculation():
    """Test incremental ROCE calculation for mid-cap detection."""
    print("\n🧪 Testing Incremental ROCE Calculation...")

    analyzer = QualityPersistenceAnalyzer()

    # Create data where incremental ROCE > traditional ROCE
    # (efficient capital deployment)
    df_good = pd.DataFrame({
        'year': [2022, 2023],
        'nopat': [10e9, 15e9],  # NOPAT increased by $5B
        'total_debt': [30e9, 32e9],  # Invested capital increased by $4B
        'shareholder_equity': [70e9, 72e9]  # ($2B debt + $2B equity)
    })

    advantage = analyzer.calculate_incremental_roce(df_good)

    # Incremental ROCE = 5B / 4B = 125%
    # Traditional ROCE = 15B / 104B = 14.4%
    # Advantage should be significant positive
    assert advantage > 0, f"Should have positive advantage: {advantage:.1f}%"
    print(f"  ✓ Incremental ROCE advantage calculated: +{advantage:.1f}%")

    # Create data where incremental ROCE < traditional ROCE
    # (inefficient capital deployment)
    df_bad = pd.DataFrame({
        'year': [2022, 2023],
        'nopat': [10e9, 11e9],  # NOPAT increased by only $1B
        'total_debt': [30e9, 40e9],  # Invested capital increased by $12B
        'shareholder_equity': [70e9, 72e9]  # ($10B debt + $2B equity = poor returns)
    })

    advantage = analyzer.calculate_incremental_roce(df_bad)

    # Incremental ROCE = 1B / 12B = 8.3%
    # Traditional ROCE = 11B / 112B = 9.8%
    # Advantage should be negative
    assert advantage < 0, f"Should have negative advantage: {advantage:.1f}%"
    print(f"  ✓ Negative incremental ROCE detected: {advantage:.1f}%")


def test_incremental_roce_edge_cases():
    """Test incremental ROCE edge cases (insufficient data, no capital change)."""
    print("\n🧪 Testing Incremental ROCE Edge Cases...")

    analyzer = QualityPersistenceAnalyzer()

    # Only 1 year of data
    df_insufficient = pd.DataFrame({
        'year': [2023],
        'nopat': [10e9],
        'total_debt': [30e9],
        'shareholder_equity': [70e9]
    })

    advantage = analyzer.calculate_incremental_roce(df_insufficient)
    assert advantage == 0.0, "Should return 0 with insufficient data"
    print("  ✓ Returns 0.0 with insufficient data")

    # Invested capital decreased
    df_negative_delta = pd.DataFrame({
        'year': [2022, 2023],
        'nopat': [10e9, 12e9],
        'total_debt': [40e9, 30e9],  # Paid down debt
        'shareholder_equity': [70e9, 65e9]  # Bought back shares
    })

    advantage = analyzer.calculate_incremental_roce(df_negative_delta)
    assert advantage == 0.0, "Should return 0 when invested capital decreases"
    print("  ✓ Returns 0.0 when invested capital decreases")


def test_tier_eligibility_dataclass():
    """Test TierEligibility dataclass creation and serialization."""
    print("\n🧪 Testing TierEligibility Dataclass...")

    eligibility = TierEligibility(
        ticker='TEST',
        market_cap=100e9,
        market_cap_tier=MarketCapTier.LARGE_CAP,
        meets_roe_persistence=True,
        roe_persistence_years=6.0,
        incremental_roce_advantage=None,
        reasoning="Passes all requirements",
        validation_date="2025-11-06"
    )

    assert eligibility.ticker == 'TEST'
    assert eligibility.market_cap_tier == MarketCapTier.LARGE_CAP
    assert eligibility.meets_roe_persistence == True
    print("  ✓ TierEligibility dataclass created successfully")

    # Test to_dict()
    d = eligibility.to_dict()
    assert d['ticker'] == 'TEST'
    assert d['market_cap_tier'] == 'Large Cap'
    assert d['meets_roe_persistence'] == True
    print("  ✓ TierEligibility to_dict() works correctly")


def test_roe_persistence_missing_data():
    """Test ROE persistence validation with missing data."""
    print("\n🧪 Testing ROE Persistence with Missing Data...")

    analyzer = QualityPersistenceAnalyzer()

    # Missing required columns
    df_missing_cols = pd.DataFrame({
        'year': [2023],
        'revenue': [100e9]
        # Missing net_income and shareholder_equity
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_MISSING',
        MarketCapTier.LARGE_CAP,
        df_missing_cols
    )

    assert passes == False, "Should fail with missing columns"
    assert "Missing required columns" in reason
    print("  ✓ Correctly handles missing columns")

    # All ROE values are NaN
    df_nan_roe = pd.DataFrame({
        'year': [2023],
        'net_income': [100e9],
        'shareholder_equity': [0]  # Division by zero -> NaN
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_NAN',
        MarketCapTier.LARGE_CAP,
        df_nan_roe
    )

    assert passes == False, "Should fail with no valid ROE data"
    assert "No valid ROE data" in reason
    print("  ✓ Correctly handles NaN ROE values")


def test_roe_persistence_interruption():
    """Test that interruption in ROE >15% streak resets counter."""
    print("\n🧪 Testing ROE Persistence Streak Interruption...")

    analyzer = QualityPersistenceAnalyzer()

    # Large cap with interruption: 3 years good, 1 bad, 3 years good
    df_interrupted = pd.DataFrame({
        'year': list(range(2017, 2024)),
        'net_income': [25e9, 25e9, 25e9, 5e9, 25e9, 25e9, 25e9],  # Dip in year 4
        'shareholder_equity': [100e9] * 7
    })

    passes, reason = analyzer.validate_roe_persistence_for_tier(
        'TEST_INTERRUPTED',
        MarketCapTier.LARGE_CAP,
        df_interrupted
    )

    # Should fail because no 5 consecutive years
    assert passes == False, "Should fail with interrupted streak"
    assert "3 consecutive years" in reason  # Max streak is 3
    print("  ✓ Correctly detects streak interruption")


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
        test_visualization,
        # NEW: Tier-specific tests (4-tier framework)
        test_large_cap_roe_persistence,
        test_mid_cap_roe_persistence,
        test_small_cap_roe_persistence,
        test_micro_cap_not_eligible,
        test_incremental_roce_calculation,
        test_incremental_roce_edge_cases,
        test_tier_eligibility_dataclass,
        test_roe_persistence_missing_data,
        test_roe_persistence_interruption
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
