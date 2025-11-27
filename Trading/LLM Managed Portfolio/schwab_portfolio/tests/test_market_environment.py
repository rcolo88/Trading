#!/usr/bin/env python3
"""
Test Suite for Market Environment Analyzer

Tests all functionality of market_environment_analyzer.py including:
- S&P 500 data fetching
- VIX data fetching
- Sector performance calculation
- Trend classification logic
- Volatility classification logic
- Summary generation
- Caching behavior
- Error handling

Author: LLM Portfolio Management System
Date: November 3, 2025
"""

import unittest
import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pickle

# Import the module to test
from components.market_environment_analyzer import (
    MarketEnvironment,
    MarketCache,
    MarketEnvironmentAnalyzer,
    SECTOR_ETF_MAP
)


class TestMarketEnvironmentDataclass(unittest.TestCase):
    """Test MarketEnvironment dataclass"""

    def test_market_environment_creation(self):
        """Test creating MarketEnvironment with all fields"""
        env = MarketEnvironment(
            sp500_price=6840.0,
            sp500_50ma=6700.0,
            sp500_200ma=6400.0,
            sp500_1m_return=0.26,
            sp500_ytd_return=28.0,
            trend="BULL",
            vix_level=15.2,
            vix_20ma=16.5,
            volatility_regime="LOW",
            leading_sectors=["Technology", "Communication Services", "Financials"],
            lagging_sectors=["Energy", "Utilities", "Real Estate"],
            sector_performance={"Technology": 8.5, "Energy": -5.2},
            market_breadth="NARROW",
            risk_appetite="RISK_ON",
            summary="Test market summary",
            analysis_date="2025-11-03",
            data_quality="COMPLETE"
        )

        self.assertEqual(env.sp500_price, 6840.0)
        self.assertEqual(env.trend, "BULL")
        self.assertEqual(env.vix_level, 15.2)
        self.assertEqual(len(env.leading_sectors), 3)
        self.assertEqual(env.data_quality, "COMPLETE")


class TestMarketCache(unittest.TestCase):
    """Test MarketCache functionality"""

    def setUp(self):
        """Create temporary cache file"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, "test_cache.pkl")
        self.cache = MarketCache(cache_file=self.cache_file)

    def tearDown(self):
        """Clean up temporary files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cache_miss(self):
        """Test cache miss when file doesn't exist"""
        result = self.cache.get()
        self.assertIsNone(result)

    def test_cache_hit_valid(self):
        """Test cache hit with valid (recent) data"""
        # Create test environment
        env = MarketEnvironment(
            sp500_price=6840.0, sp500_50ma=6700.0, sp500_200ma=6400.0,
            sp500_1m_return=0.26, sp500_ytd_return=28.0, trend="BULL",
            vix_level=15.2, vix_20ma=16.5, volatility_regime="LOW",
            leading_sectors=["Technology"], lagging_sectors=["Energy"],
            sector_performance={}, market_breadth="NARROW",
            risk_appetite="RISK_ON", summary="Test",
            analysis_date="2025-11-03", data_quality="COMPLETE"
        )

        # Cache it
        self.cache.set(env)

        # Retrieve it
        cached_env = self.cache.get()
        self.assertIsNotNone(cached_env)
        self.assertEqual(cached_env.sp500_price, 6840.0)
        self.assertEqual(cached_env.trend, "BULL")

    def test_cache_expiration(self):
        """Test cache expiration after 4 hours"""
        # Create test environment
        env = MarketEnvironment(
            sp500_price=6840.0, sp500_50ma=6700.0, sp500_200ma=6400.0,
            sp500_1m_return=0.26, sp500_ytd_return=28.0, trend="BULL",
            vix_level=15.2, vix_20ma=16.5, volatility_regime="LOW",
            leading_sectors=[], lagging_sectors=[],
            sector_performance={}, market_breadth="NARROW",
            risk_appetite="RISK_ON", summary="Test",
            analysis_date="2025-11-03", data_quality="COMPLETE"
        )

        # Cache it with old timestamp
        cache_data = {
            'timestamp': (datetime.now() - timedelta(hours=5)).isoformat(),
            'environment': env
        }

        with open(self.cache_file, 'wb') as f:
            pickle.dump(cache_data, f)

        # Should return None (expired)
        cached_env = self.cache.get()
        self.assertIsNone(cached_env)


class TestTrendClassification(unittest.TestCase):
    """Test trend classification logic"""

    def setUp(self):
        self.analyzer = MarketEnvironmentAnalyzer(enable_cache=False)

    def test_strong_bull_trend(self):
        """Test STRONG_BULL: price > 50MA > 200MA"""
        trend = self.analyzer.classify_trend(
            price=7000.0,
            ma_50=6800.0,
            ma_200=6500.0
        )
        self.assertEqual(trend, "STRONG_BULL")

    def test_bull_trend(self):
        """Test BULL: price > 50MA but 50MA < 200MA"""
        trend = self.analyzer.classify_trend(
            price=6700.0,
            ma_50=6600.0,
            ma_200=6800.0
        )
        self.assertEqual(trend, "BULL")

    def test_strong_bear_trend(self):
        """Test STRONG_BEAR: price < 50MA < 200MA"""
        trend = self.analyzer.classify_trend(
            price=6200.0,
            ma_50=6400.0,
            ma_200=6600.0
        )
        self.assertEqual(trend, "STRONG_BEAR")

    def test_bear_trend(self):
        """Test BEAR: price < 50MA but 50MA > 200MA"""
        trend = self.analyzer.classify_trend(
            price=6400.0,
            ma_50=6600.0,
            ma_200=6500.0
        )
        self.assertEqual(trend, "BEAR")


class TestVolatilityClassification(unittest.TestCase):
    """Test volatility classification logic"""

    def setUp(self):
        self.analyzer = MarketEnvironmentAnalyzer(enable_cache=False)

    def test_low_volatility(self):
        """Test LOW volatility: VIX < 15"""
        regime = self.analyzer.classify_volatility(12.5)
        self.assertEqual(regime, "LOW")

    def test_moderate_volatility(self):
        """Test MODERATE volatility: VIX 15-20"""
        regime = self.analyzer.classify_volatility(17.5)
        self.assertEqual(regime, "MODERATE")

    def test_elevated_volatility(self):
        """Test ELEVATED volatility: VIX 20-30"""
        regime = self.analyzer.classify_volatility(25.0)
        self.assertEqual(regime, "ELEVATED")

    def test_high_volatility(self):
        """Test HIGH volatility: VIX > 30"""
        regime = self.analyzer.classify_volatility(35.0)
        self.assertEqual(regime, "HIGH")


class TestBreadthClassification(unittest.TestCase):
    """Test market breadth classification"""

    def setUp(self):
        self.analyzer = MarketEnvironmentAnalyzer(enable_cache=False)

    def test_narrow_breadth(self):
        """Test NARROW: Tech and Comm Services both in top 3"""
        sector_perf = {
            "Technology": 10.0,
            "Communication Services": 8.0,
            "Healthcare": 6.0,
            "Financials": 2.0,
            "Energy": -5.0
        }
        breadth = self.analyzer.classify_breadth(sector_perf)
        self.assertEqual(breadth, "NARROW")

    def test_broad_breadth(self):
        """Test BROAD: 70%+ sectors positive"""
        sector_perf = {
            "Technology": 5.0,
            "Communication Services": 4.0,
            "Healthcare": 3.0,
            "Financials": 2.0,
            "Industrials": 2.0,
            "Materials": 1.0,
            "Consumer Discretionary": 1.0,
            "Energy": -1.0
        }
        breadth = self.analyzer.classify_breadth(sector_perf)
        self.assertEqual(breadth, "BROAD")

    def test_moderate_breadth(self):
        """Test MODERATE: mixed performance"""
        sector_perf = {
            "Technology": 5.0,
            "Healthcare": 3.0,
            "Financials": 1.0,
            "Energy": -2.0,
            "Utilities": -3.0
        }
        breadth = self.analyzer.classify_breadth(sector_perf)
        self.assertEqual(breadth, "MODERATE")


class TestRiskAppetite(unittest.TestCase):
    """Test risk appetite assessment"""

    def setUp(self):
        self.analyzer = MarketEnvironmentAnalyzer(enable_cache=False)

    def test_risk_on(self):
        """Test RISK_ON: Low vol + Bull trend"""
        appetite = self.analyzer.assess_risk_appetite("LOW", "STRONG_BULL")
        self.assertEqual(appetite, "RISK_ON")

    def test_risk_off(self):
        """Test RISK_OFF: High vol + Bear trend"""
        appetite = self.analyzer.assess_risk_appetite("HIGH", "STRONG_BEAR")
        self.assertEqual(appetite, "RISK_OFF")

    def test_neutral(self):
        """Test NEUTRAL: Mixed conditions"""
        appetite = self.analyzer.assess_risk_appetite("MODERATE", "NEUTRAL")
        self.assertEqual(appetite, "NEUTRAL")


class TestSummaryGeneration(unittest.TestCase):
    """Test summary generation"""

    def test_summary_generation(self):
        """Test that summary is generated correctly"""
        analyzer = MarketEnvironmentAnalyzer(enable_cache=False)

        env = MarketEnvironment(
            sp500_price=6840.0, sp500_50ma=6700.0, sp500_200ma=6400.0,
            sp500_1m_return=2.5, sp500_ytd_return=28.0, trend="BULL",
            vix_level=15.2, vix_20ma=16.5, volatility_regime="LOW",
            leading_sectors=["Technology", "Healthcare", "Financials"],
            lagging_sectors=["Energy", "Utilities", "Real Estate"],
            sector_performance={"Technology": 8.5},
            market_breadth="NARROW", risk_appetite="RISK_ON",
            summary="", analysis_date="2025-11-03", data_quality="COMPLETE"
        )

        summary = analyzer.generate_summary(env)

        # Check that summary contains key elements
        self.assertIn("6840", summary)
        self.assertIn("Technology", summary)
        self.assertIn("low volatility", summary)
        self.assertIn("Bull", summary)


class TestDataFetching(unittest.TestCase):
    """Test data fetching with mocked yfinance"""

    @patch('market_environment_analyzer.yf.Ticker')
    def test_fetch_sp500_data_success(self, mock_ticker):
        """Test successful S&P 500 data fetch"""
        # Mock yfinance response
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_hist.__len__ = lambda self: 252
        mock_hist['Close'].iloc = MagicMock()
        mock_hist['Close'].iloc.__getitem__ = lambda self, key: {
            -1: 6840.0,  # Current price
            -21: 6800.0,  # 1 month ago
            0: 5500.0     # Start of year
        }.get(key, 6700.0)
        mock_hist['Close'].tail = MagicMock(return_value=MagicMock(mean=lambda: 6750.0))

        mock_ticker.return_value.history.return_value = mock_hist

        analyzer = MarketEnvironmentAnalyzer(enable_cache=False)
        result = analyzer.fetch_sp500_data()

        self.assertIsNotNone(result)
        self.assertIn('price', result)
        self.assertIn('ma_50', result)
        self.assertIn('ma_200', result)

    @patch('market_environment_analyzer.yf.Ticker')
    def test_fetch_sp500_data_failure(self, mock_ticker):
        """Test S&P 500 data fetch failure"""
        # Mock empty response
        mock_ticker.return_value.history.return_value = MagicMock(empty=True)

        analyzer = MarketEnvironmentAnalyzer(enable_cache=False)
        result = analyzer.fetch_sp500_data()

        self.assertIsNone(result)

    @patch('market_environment_analyzer.yf.Ticker')
    def test_fetch_vix_data_success(self, mock_ticker):
        """Test successful VIX data fetch"""
        # Mock yfinance response
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_hist['Close'].iloc = MagicMock()
        mock_hist['Close'].iloc.__getitem__ = lambda self, key: 15.2
        mock_hist['Close'].tail = MagicMock(return_value=MagicMock(mean=lambda: 16.5))

        mock_ticker.return_value.history.return_value = mock_hist

        analyzer = MarketEnvironmentAnalyzer(enable_cache=False)
        result = analyzer.fetch_vix_data()

        self.assertIsNotNone(result)
        self.assertEqual(result['quality'], 'COMPLETE')

    @patch('market_environment_analyzer.yf.Ticker')
    def test_fetch_vix_data_failure(self, mock_ticker):
        """Test VIX data fetch failure (uses default)"""
        # Mock exception
        mock_ticker.side_effect = Exception("API error")

        analyzer = MarketEnvironmentAnalyzer(enable_cache=False)
        result = analyzer.fetch_vix_data()

        # Should return default values
        self.assertEqual(result['level'], 20.0)
        self.assertEqual(result['quality'], 'PARTIAL')


class TestExport(unittest.TestCase):
    """Test export functionality"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.analyzer = MarketEnvironmentAnalyzer(enable_cache=False)

        self.env = MarketEnvironment(
            sp500_price=6840.0, sp500_50ma=6700.0, sp500_200ma=6400.0,
            sp500_1m_return=2.5, sp500_ytd_return=28.0, trend="BULL",
            vix_level=15.2, vix_20ma=16.5, volatility_regime="LOW",
            leading_sectors=["Technology", "Healthcare", "Financials"],
            lagging_sectors=["Energy", "Utilities", "Real Estate"],
            sector_performance={"Technology": 8.5, "Energy": -5.2},
            market_breadth="NARROW", risk_appetite="RISK_ON",
            summary="Test market summary",
            analysis_date="2025-11-03", data_quality="COMPLETE"
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_to_json(self):
        """Test JSON export"""
        json_file = os.path.join(self.temp_dir, "test_market.json")
        self.analyzer.export_to_json(self.env, json_file)

        # Verify file exists and is valid JSON
        self.assertTrue(Path(json_file).exists())

        with open(json_file, 'r') as f:
            data = json.load(f)

        self.assertEqual(data['sp500_price'], 6840.0)
        self.assertEqual(data['trend'], "BULL")
        self.assertIn("Technology", data['leading_sectors'])

    def test_export_to_markdown(self):
        """Test markdown export"""
        md_file = os.path.join(self.temp_dir, "test_market.md")
        self.analyzer.export_to_markdown(self.env, md_file)

        # Verify file exists and contains expected content
        self.assertTrue(Path(md_file).exists())

        with open(md_file, 'r') as f:
            content = f.read()

        self.assertIn("Market Environment Analysis", content)
        self.assertIn("6840", content)
        self.assertIn("Technology", content)
        self.assertIn("BULL", content)


class TestIntegration(unittest.TestCase):
    """Integration tests with real yfinance calls (may be slow)"""

    def test_full_analysis_with_cache(self):
        """Test full analysis workflow with caching"""
        temp_dir = tempfile.mkdtemp()
        cache_file = os.path.join(temp_dir, "integration_test_cache.pkl")

        try:
            # First run - should fetch from API
            analyzer1 = MarketEnvironmentAnalyzer(enable_cache=True)
            analyzer1.cache.cache_file = Path(cache_file)

            env1 = analyzer1.analyze_market_environment()

            self.assertIsNotNone(env1)
            self.assertGreater(env1.sp500_price, 0)
            self.assertIn(env1.trend, ["STRONG_BULL", "BULL", "NEUTRAL", "BEAR", "STRONG_BEAR"])
            self.assertIn(env1.volatility_regime, ["LOW", "MODERATE", "ELEVATED", "HIGH"])

            # Second run - should use cache
            analyzer2 = MarketEnvironmentAnalyzer(enable_cache=True)
            analyzer2.cache.cache_file = Path(cache_file)

            env2 = analyzer2.analyze_market_environment()

            # Should be identical (from cache)
            self.assertEqual(env1.sp500_price, env2.sp500_price)
            self.assertEqual(env1.analysis_date, env2.analysis_date)

        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMarketEnvironmentDataclass))
    suite.addTests(loader.loadTestsFromTestCase(TestMarketCache))
    suite.addTests(loader.loadTestsFromTestCase(TestTrendClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestVolatilityClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestBreadthClassification))
    suite.addTests(loader.loadTestsFromTestCase(TestRiskAppetite))
    suite.addTests(loader.loadTestsFromTestCase(TestSummaryGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestDataFetching))
    suite.addTests(loader.loadTestsFromTestCase(TestExport))

    # Integration test is optional (can be slow)
    # suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
