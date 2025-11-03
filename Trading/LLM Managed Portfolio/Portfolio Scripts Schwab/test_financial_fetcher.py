"""
Test Suite for Financial Data Fetcher Module
Tests financial data fetching from yfinance
"""

import unittest
import os
import tempfile
from financial_data_fetcher import (
    FinancialDataFetcher,
    FinancialData,
    FinancialDataCache,
    get_sp500_tickers
)


class TestFinancialData(unittest.TestCase):
    """Test FinancialData dataclass"""

    def setUp(self):
        self.data = FinancialData(
            ticker="AAPL",
            market_cap=2_800_000_000_000,
            sector="Technology",
            industry="Consumer Electronics",
            current_price=180.0,
            revenue=400_000_000_000,
            cogs=200_000_000_000,
            sga=50_000_000_000,
            total_assets=350_000_000_000,
            net_income=100_000_000_000,
            shareholder_equity=150_000_000_000,
            free_cash_flow=110_000_000_000,
            data_quality="complete"
        )

    def test_to_dict(self):
        """Test conversion to dictionary"""
        d = self.data.to_dict()
        self.assertEqual(d['ticker'], "AAPL")
        self.assertEqual(d['sector'], "Technology")
        self.assertIn('market_cap', d)

    def test_validate_complete(self):
        """Test validation with complete data"""
        self.assertTrue(self.data.validate())

    def test_validate_incomplete(self):
        """Test validation with incomplete data"""
        incomplete_data = FinancialData(
            ticker="TEST",
            revenue=100_000_000
            # Missing other required fields
        )
        self.assertFalse(incomplete_data.validate())


class TestFinancialDataCache(unittest.TestCase):
    """Test FinancialDataCache functionality"""

    def setUp(self):
        # Use temp file for cache
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
        self.cache = FinancialDataCache(cache_file=self.temp_file.name, cache_hours=24)
        self.data = FinancialData(
            ticker="AAPL",
            market_cap=2_800_000_000_000,
            revenue=400_000_000_000,
            data_quality="complete"
        )

    def tearDown(self):
        # Clean up temp file
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_set_and_get(self):
        """Test caching and retrieval"""
        self.cache.set("AAPL", self.data)
        retrieved = self.cache.get("AAPL")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.ticker, "AAPL")
        self.assertEqual(retrieved.market_cap, 2_800_000_000_000)

    def test_get_miss(self):
        """Test cache miss"""
        retrieved = self.cache.get("NVDA")
        self.assertIsNone(retrieved)

    def test_clear(self):
        """Test cache clearing"""
        self.cache.set("AAPL", self.data)
        self.cache.clear()
        retrieved = self.cache.get("AAPL")
        self.assertIsNone(retrieved)


class TestFinancialDataFetcher(unittest.TestCase):
    """Test FinancialDataFetcher functionality"""

    def setUp(self):
        """Setup fetcher (yfinance is free, no API key needed)"""
        self.fetcher = FinancialDataFetcher(enable_cache=False)  # Disable cache for tests

    def test_fetch_financial_data_valid_ticker(self):
        """Test fetching data for a valid ticker"""
        # Use a well-known ticker that should have data
        data = self.fetcher.fetch_financial_data("AAPL")

        # Should return FinancialData object
        self.assertIsNotNone(data)
        self.assertIsInstance(data, FinancialData)

        # Check ticker
        self.assertEqual(data.ticker, "AAPL")

        # Should have at least some data
        self.assertIsNotNone(data.market_cap)
        self.assertIsNotNone(data.sector)

        # Check data quality
        self.assertIn(data.data_quality, ["complete", "partial", "insufficient"])

        print(f"\nAAPL Data Quality: {data.data_quality}")
        if data.revenue:
            print(f"Revenue: ${data.revenue:,.0f}")
        if data.market_cap:
            print(f"Market Cap: ${data.market_cap:,.0f}")

    def test_fetch_financial_data_invalid_ticker(self):
        """Test fetching data for invalid ticker"""
        # Should handle gracefully
        data = self.fetcher.fetch_financial_data("INVALIDTICKER12345")

        # May return None or data with insufficient quality
        if data:
            self.assertEqual(data.data_quality, "insufficient")

    def test_batch_fetch(self):
        """Test batch fetching multiple tickers"""
        tickers = ["AAPL", "MSFT", "GOOGL"]
        results = self.fetcher.batch_fetch(tickers)

        # Should return dict
        self.assertIsInstance(results, dict)

        # Should have entries for all tickers
        for ticker in tickers:
            self.assertIn(ticker, results)

        # Check that at least some tickers returned data
        successful = sum(1 for v in results.values() if v and v.data_quality != "insufficient")
        self.assertGreater(successful, 0)

        print(f"\nBatch Fetch Results:")
        for ticker, data in results.items():
            if data:
                print(f"  {ticker}: {data.data_quality}")

    def test_get_earnings_dates(self):
        """Test fetching earnings dates"""
        earnings = self.fetcher.get_earnings_dates("AAPL")

        # May return None or DataFrame
        if earnings is not None:
            print(f"\nEarnings dates available for AAPL: {len(earnings)} dates")

    def test_get_analyst_info(self):
        """Test fetching analyst info"""
        analyst_info = self.fetcher.get_analyst_info("AAPL")

        # Should return dict or None
        if analyst_info:
            self.assertIsInstance(analyst_info, dict)

            # Check for expected fields
            if analyst_info.get('target_mean_price'):
                print(f"\nAAPL Target Mean Price: ${analyst_info['target_mean_price']}")
            if analyst_info.get('recommendation_key'):
                print(f"Recommendation: {analyst_info['recommendation_key']}")

    def test_safe_get(self):
        """Test _safe_get utility method"""
        import pandas as pd

        # Create test DataFrame
        df = pd.DataFrame({
            'col1': [100, 200, 300],
            'col2': [400, 500, 600]
        }, index=['Revenue', 'COGS', 'Net Income'])

        # Test successful get
        value = self.fetcher._safe_get(df, 'Revenue', 0)
        self.assertEqual(value, 100)

        # Test missing key
        value = self.fetcher._safe_get(df, 'Missing', 0)
        self.assertIsNone(value)

    def test_data_validation(self):
        """Test that fetched data is validated"""
        data = self.fetcher.fetch_financial_data("AAPL")

        if data and data.data_quality == "complete":
            # Complete data should pass validation
            self.assertTrue(data.validate())

            # Check for reasonable values (no negative revenue, etc.)
            if data.revenue:
                self.assertGreater(data.revenue, 0)
            if data.market_cap:
                self.assertGreater(data.market_cap, 0)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_get_sp500_tickers(self):
        """Test S&P 500 ticker fetching"""
        tickers = get_sp500_tickers()

        # Should return a list
        self.assertIsInstance(tickers, list)

        # S&P 500 has ~500 stocks
        if tickers:  # Only check if fetch succeeded
            self.assertGreater(len(tickers), 400)
            self.assertLess(len(tickers), 600)

            # Should contain well-known tickers
            self.assertIn("AAPL", tickers)
            self.assertIn("MSFT", tickers)

            print(f"\nFetched {len(tickers)} S&P 500 tickers")


def run_tests():
    """Run test suite with detailed output"""
    print("\n" + "="*60)
    print("FINANCIAL DATA FETCHER TEST SUITE")
    print("="*60)
    print("Using yfinance (free, no API key required)")
    print("="*60 + "\n")

    # Run tests
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    run_tests()
