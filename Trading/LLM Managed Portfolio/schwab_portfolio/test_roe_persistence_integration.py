#!/usr/bin/env python3
"""
Test script for ROE persistence integration with historical data fetching
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.financial_data_fetcher import FinancialDataFetcher
from components.quality_persistence_analyzer import QualityPersistenceAnalyzer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_historical_data_fetching():
    """Test the new fetch_historical_financials() method"""
    logger.info("="*60)
    logger.info("TEST 1: Historical Data Fetching")
    logger.info("="*60)

    fetcher = FinancialDataFetcher(enable_cache=False)  # Disable cache for testing

    # Test with a well-known ticker
    ticker = "AAPL"
    logger.info(f"\nFetching historical financials for {ticker}...")

    hist_data = fetcher.fetch_historical_financials(ticker)

    if hist_data is None:
        logger.error(f"❌ FAILED: No historical data returned for {ticker}")
        return False

    logger.info(f"✅ SUCCESS: Fetched {len(hist_data)} years of data")
    logger.info(f"Available years: {hist_data['year'].tolist()}")
    logger.info(f"\nDataFrame columns: {hist_data.columns.tolist()}")
    logger.info(f"\nFirst row (oldest):")
    logger.info(hist_data.iloc[0])
    logger.info(f"\nLast row (newest):")
    logger.info(hist_data.iloc[-1])

    # Validate data structure
    required_columns = ['year', 'revenue', 'cogs', 'sga', 'total_assets',
                       'net_income', 'shareholder_equity', 'free_cash_flow',
                       'total_debt', 'nopat']

    missing_columns = [col for col in required_columns if col not in hist_data.columns]
    if missing_columns:
        logger.error(f"❌ FAILED: Missing columns: {missing_columns}")
        return False

    logger.info(f"✅ SUCCESS: All required columns present")

    # Check minimum data requirements
    if len(hist_data) < 2:
        logger.warning(f"⚠️  WARNING: Only {len(hist_data)} years of data (need 2+ for small cap)")
        return False

    logger.info(f"✅ SUCCESS: Sufficient data for analysis ({len(hist_data)} years)")

    return True


def test_roe_persistence_analysis():
    """Test ROE persistence analysis with historical data"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: ROE Persistence Analysis")
    logger.info("="*60)

    fetcher = FinancialDataFetcher(enable_cache=False)
    analyzer = QualityPersistenceAnalyzer()

    # Test with multiple tickers
    test_tickers = ["AAPL", "MSFT", "GOOGL"]

    for ticker in test_tickers:
        logger.info(f"\n--- Testing {ticker} ---")

        # Fetch historical data
        hist_data = fetcher.fetch_historical_financials(ticker)

        if hist_data is None or len(hist_data) < 2:
            logger.warning(f"⚠️  Skipping {ticker}: insufficient data")
            continue

        # Analyze ROE persistence
        try:
            result = analyzer.analyze_company(hist_data, ticker=ticker)

            if result is None:
                logger.warning(f"⚠️  No persistence result for {ticker}")
                continue

            logger.info(f"✅ SUCCESS for {ticker}:")
            logger.info(f"  Classification: {result.classification.value}")
            logger.info(f"  Persistence Years: {result.persistence_years}")
            logger.info(f"  Trend Quarters: {result.trend_quarters}")
            logger.info(f"  Incremental ROCE: {result.incremental_roce:.2f}%")
            logger.info(f"  Average ROE: {result.average_roe:.2f}%")

        except Exception as e:
            logger.error(f"❌ FAILED for {ticker}: {e}")
            import traceback
            traceback.print_exc()
            return False

    return True


def test_tier_validation():
    """Test tier-specific ROE persistence validation"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Tier-Specific Validation")
    logger.info("="*60)

    fetcher = FinancialDataFetcher(enable_cache=False)
    analyzer = QualityPersistenceAnalyzer()

    # Test with a ticker and check different tier requirements
    ticker = "MSFT"  # Large cap
    logger.info(f"\nTesting tier validation for {ticker}...")

    hist_data = fetcher.fetch_historical_financials(ticker)

    if hist_data is None or len(hist_data) < 2:
        logger.error(f"❌ FAILED: Insufficient data for {ticker}")
        return False

    # Test large cap requirement (5+ years ROE >15%)
    from core.market_cap_classifier import MarketCapTier

    try:
        passed, message = analyzer.validate_roe_persistence_for_tier(
            ticker, MarketCapTier.LARGE_CAP, hist_data
        )
        logger.info(f"Large Cap Validation: {message}")
        if passed:
            logger.info(f"✅ {ticker} meets large cap requirement")
        else:
            logger.warning(f"⚠️  {ticker} does not meet large cap requirement")

    except Exception as e:
        logger.error(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Run all tests"""
    logger.info("Starting ROE Persistence Integration Tests\n")

    tests = [
        ("Historical Data Fetching", test_historical_data_fetching),
        ("ROE Persistence Analysis", test_roe_persistence_analysis),
        ("Tier-Specific Validation", test_tier_validation)
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ EXCEPTION in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False

    # Print summary
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")

    total_tests = len(results)
    passed_tests = sum(results.values())

    logger.info(f"\nOverall: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        logger.info("✅ All tests PASSED!")
        return 0
    else:
        logger.error("❌ Some tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
