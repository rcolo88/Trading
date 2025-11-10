"""
Test Suite for Market Cap Classifier

Tests all functionality of market_cap_classifier.py including:
- Market cap tier classification
- Edge cases (threshold boundaries, negative values)
- Batch processing
- Caching functionality
- Error handling
- JSON export

Author: LLM Portfolio Management System
Date: November 6, 2025
"""

import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from market_cap_classifier import (
    MarketCapClassifier,
    MarketCapTier,
    MarketCapClassification,
    BatchClassificationResult,
    MarketCapCache,
    LARGE_CAP_THRESHOLD,
    MID_CAP_THRESHOLD,
    SMALL_CAP_THRESHOLD
)


class TestMarketCapTier(unittest.TestCase):
    """Test MarketCapTier enum"""

    def test_tier_values(self):
        """Test tier enum has correct values"""
        self.assertEqual(MarketCapTier.LARGE_CAP.value, "Large Cap")
        self.assertEqual(MarketCapTier.MID_CAP.value, "Mid Cap")
        self.assertEqual(MarketCapTier.SMALL_CAP.value, "Small Cap")
        self.assertEqual(MarketCapTier.MICRO_CAP.value, "Micro Cap")

    def test_tier_count(self):
        """Test we have exactly 4 tiers"""
        self.assertEqual(len(MarketCapTier), 4)


class TestMarketCapThresholds(unittest.TestCase):
    """Test market cap threshold constants"""

    def test_threshold_values(self):
        """Test threshold values match research document"""
        self.assertEqual(LARGE_CAP_THRESHOLD, 50_000_000_000)  # $50B
        self.assertEqual(MID_CAP_THRESHOLD, 2_000_000_000)     # $2B
        self.assertEqual(SMALL_CAP_THRESHOLD, 500_000_000)     # $500M

    def test_threshold_ordering(self):
        """Test thresholds are in descending order"""
        self.assertGreater(LARGE_CAP_THRESHOLD, MID_CAP_THRESHOLD)
        self.assertGreater(MID_CAP_THRESHOLD, SMALL_CAP_THRESHOLD)


class TestClassifyByMarketCap(unittest.TestCase):
    """Test classify_by_market_cap static method"""

    def test_large_cap_classification(self):
        """Test large cap classification (≥$50B)"""
        tier = MarketCapClassifier.classify_by_market_cap(50_000_000_000)
        self.assertEqual(tier, MarketCapTier.LARGE_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(100_000_000_000)
        self.assertEqual(tier, MarketCapTier.LARGE_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(3_000_000_000_000)  # $3T (AAPL-like)
        self.assertEqual(tier, MarketCapTier.LARGE_CAP)

    def test_mid_cap_classification(self):
        """Test mid cap classification ($2B-$50B)"""
        tier = MarketCapClassifier.classify_by_market_cap(2_000_000_000)
        self.assertEqual(tier, MarketCapTier.MID_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(25_000_000_000)  # $25B midpoint
        self.assertEqual(tier, MarketCapTier.MID_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(49_999_999_999)  # Just below large cap
        self.assertEqual(tier, MarketCapTier.MID_CAP)

    def test_small_cap_classification(self):
        """Test small cap classification ($500M-$2B)"""
        tier = MarketCapClassifier.classify_by_market_cap(500_000_000)
        self.assertEqual(tier, MarketCapTier.SMALL_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(1_000_000_000)  # $1B midpoint
        self.assertEqual(tier, MarketCapTier.SMALL_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(1_999_999_999)  # Just below mid cap
        self.assertEqual(tier, MarketCapTier.SMALL_CAP)

    def test_micro_cap_classification(self):
        """Test micro cap classification (<$500M)"""
        tier = MarketCapClassifier.classify_by_market_cap(499_999_999)
        self.assertEqual(tier, MarketCapTier.MICRO_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(100_000_000)  # $100M
        self.assertEqual(tier, MarketCapTier.MICRO_CAP)

        tier = MarketCapClassifier.classify_by_market_cap(1_000_000)  # $1M
        self.assertEqual(tier, MarketCapTier.MICRO_CAP)

    def test_exact_threshold_boundaries(self):
        """Test exact threshold values are classified correctly"""
        # Exactly $50B -> Large Cap
        tier = MarketCapClassifier.classify_by_market_cap(50_000_000_000)
        self.assertEqual(tier, MarketCapTier.LARGE_CAP)

        # Exactly $2B -> Mid Cap
        tier = MarketCapClassifier.classify_by_market_cap(2_000_000_000)
        self.assertEqual(tier, MarketCapTier.MID_CAP)

        # Exactly $500M -> Small Cap
        tier = MarketCapClassifier.classify_by_market_cap(500_000_000)
        self.assertEqual(tier, MarketCapTier.SMALL_CAP)

        # Just below $50B -> Mid Cap
        tier = MarketCapClassifier.classify_by_market_cap(49_999_999_999)
        self.assertEqual(tier, MarketCapTier.MID_CAP)

    def test_negative_market_cap_raises_error(self):
        """Test negative market cap raises ValueError"""
        with self.assertRaises(ValueError):
            MarketCapClassifier.classify_by_market_cap(-1000000)

    def test_zero_market_cap_raises_error(self):
        """Test zero market cap raises ValueError"""
        with self.assertRaises(ValueError):
            MarketCapClassifier.classify_by_market_cap(0)


class TestMarketCapClassification(unittest.TestCase):
    """Test MarketCapClassification dataclass"""

    def test_classification_creation(self):
        """Test creating MarketCapClassification"""
        classification = MarketCapClassification(
            ticker="AAPL",
            market_cap=3_000_000_000_000,
            tier=MarketCapTier.LARGE_CAP,
            classification_date="2025-11-06"
        )

        self.assertEqual(classification.ticker, "AAPL")
        self.assertEqual(classification.market_cap, 3_000_000_000_000)
        self.assertEqual(classification.tier, MarketCapTier.LARGE_CAP)
        self.assertEqual(classification.error, None)

    def test_classification_with_error(self):
        """Test classification with error"""
        classification = MarketCapClassification(
            ticker="INVALID",
            market_cap=None,
            tier=None,
            classification_date="2025-11-06",
            error="Ticker not found"
        )

        self.assertEqual(classification.ticker, "INVALID")
        self.assertIsNone(classification.market_cap)
        self.assertIsNone(classification.tier)
        self.assertEqual(classification.error, "Ticker not found")

    def test_to_dict(self):
        """Test conversion to dictionary"""
        classification = MarketCapClassification(
            ticker="NVDA",
            market_cap=1_000_000_000_000,
            tier=MarketCapTier.LARGE_CAP,
            classification_date="2025-11-06"
        )

        d = classification.to_dict()
        self.assertEqual(d['ticker'], "NVDA")
        self.assertEqual(d['market_cap'], 1_000_000_000_000)
        self.assertEqual(d['tier'], "Large Cap")
        self.assertIsNone(d['error'])


class TestMarketCapCache(unittest.TestCase):
    """Test MarketCapCache functionality"""

    def setUp(self):
        """Create temporary cache file for testing"""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = Path(self.temp_dir) / "test_cache.pkl"
        self.cache = MarketCapCache(cache_file=str(self.cache_file))

    def tearDown(self):
        """Clean up cache file"""
        if self.cache_file.exists():
            self.cache_file.unlink()
        Path(self.temp_dir).rmdir()

    def test_cache_miss_on_nonexistent_file(self):
        """Test cache returns None when file doesn't exist"""
        result = self.cache.get("AAPL")
        self.assertIsNone(result)

    def test_cache_set_and_get(self):
        """Test caching and retrieving data"""
        classification = MarketCapClassification(
            ticker="AAPL",
            market_cap=3_000_000_000_000,
            tier=MarketCapTier.LARGE_CAP,
            classification_date="2025-11-06"
        )

        # Set cache
        self.cache.set("AAPL", classification)

        # Get from cache
        cached = self.cache.get("AAPL")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.ticker, "AAPL")
        self.assertEqual(cached.market_cap, 3_000_000_000_000)
        self.assertEqual(cached.tier, MarketCapTier.LARGE_CAP)

    def test_cache_miss_for_different_ticker(self):
        """Test cache returns None for ticker not in cache"""
        classification = MarketCapClassification(
            ticker="AAPL",
            market_cap=3_000_000_000_000,
            tier=MarketCapTier.LARGE_CAP,
            classification_date="2025-11-06"
        )

        self.cache.set("AAPL", classification)

        # Different ticker should miss
        result = self.cache.get("NVDA")
        self.assertIsNone(result)

    def test_clear_cache(self):
        """Test clearing cache"""
        classification = MarketCapClassification(
            ticker="AAPL",
            market_cap=3_000_000_000_000,
            tier=MarketCapTier.LARGE_CAP,
            classification_date="2025-11-06"
        )

        self.cache.set("AAPL", classification)
        self.assertTrue(self.cache_file.exists())

        self.cache.clear()
        self.assertFalse(self.cache_file.exists())


class TestMarketCapClassifier(unittest.TestCase):
    """Test MarketCapClassifier class"""

    def setUp(self):
        """Create classifier with caching disabled for predictable tests"""
        self.classifier = MarketCapClassifier(enable_cache=False)

    @patch('market_cap_classifier.yf.Ticker')
    def test_fetch_market_cap_success(self, mock_ticker):
        """Test successful market cap fetch"""
        # Mock yfinance response
        mock_info = {'marketCap': 3_000_000_000_000}
        mock_ticker.return_value.info = mock_info

        market_cap, error = self.classifier.fetch_market_cap("AAPL")

        self.assertEqual(market_cap, 3_000_000_000_000)
        self.assertIsNone(error)

    @patch('market_cap_classifier.yf.Ticker')
    def test_fetch_market_cap_fallback_calculation(self, mock_ticker):
        """Test fallback to sharesOutstanding * price if marketCap missing"""
        # Mock yfinance response without marketCap
        mock_info = {
            'marketCap': None,
            'sharesOutstanding': 15_000_000_000,
            'currentPrice': 200.0
        }
        mock_ticker.return_value.info = mock_info

        market_cap, error = self.classifier.fetch_market_cap("AAPL")

        # Should calculate: 15B shares * $200 = $3T
        self.assertEqual(market_cap, 3_000_000_000_000)
        self.assertIsNone(error)

    @patch('market_cap_classifier.yf.Ticker')
    def test_fetch_market_cap_missing_data(self, mock_ticker):
        """Test error when market cap data is missing"""
        # Mock yfinance response with no market cap data
        mock_info = {'marketCap': None}
        mock_ticker.return_value.info = mock_info

        market_cap, error = self.classifier.fetch_market_cap("INVALID")

        self.assertIsNone(market_cap)
        self.assertIsNotNone(error)
        self.assertIn("not available", error)

    @patch('market_cap_classifier.yf.Ticker')
    def test_classify_ticker(self, mock_ticker):
        """Test classifying a single ticker"""
        # Mock large cap stock
        mock_info = {'marketCap': 100_000_000_000}
        mock_ticker.return_value.info = mock_info

        result = self.classifier.classify_ticker("TEST")

        self.assertEqual(result.ticker, "TEST")
        self.assertEqual(result.market_cap, 100_000_000_000)
        self.assertEqual(result.tier, MarketCapTier.LARGE_CAP)
        self.assertIsNone(result.error)

    @patch('market_cap_classifier.yf.Ticker')
    def test_batch_classify_tickers(self, mock_ticker):
        """Test batch classification of multiple tickers"""
        # Mock different market caps for different tickers
        def mock_info_side_effect(ticker):
            info_map = {
                'AAPL': {'marketCap': 3_000_000_000_000},  # Large
                'MID': {'marketCap': 10_000_000_000},       # Mid
                'SMALL': {'marketCap': 1_000_000_000},      # Small
            }
            mock = MagicMock()
            mock.info = info_map.get(ticker, {'marketCap': None})
            return mock

        mock_ticker.side_effect = lambda t: mock_info_side_effect(t)

        result = self.classifier.batch_classify_tickers(['AAPL', 'MID', 'SMALL'])

        self.assertEqual(len(result.classifications), 3)
        self.assertEqual(result.classifications['AAPL'].tier, MarketCapTier.LARGE_CAP)
        self.assertEqual(result.classifications['MID'].tier, MarketCapTier.MID_CAP)
        self.assertEqual(result.classifications['SMALL'].tier, MarketCapTier.SMALL_CAP)


class TestBatchClassificationResult(unittest.TestCase):
    """Test BatchClassificationResult dataclass"""

    def test_batch_result_creation(self):
        """Test creating batch result"""
        classifications = {
            'AAPL': MarketCapClassification(
                ticker='AAPL',
                market_cap=3_000_000_000_000,
                tier=MarketCapTier.LARGE_CAP,
                classification_date='2025-11-06'
            )
        }

        result = BatchClassificationResult(
            classifications=classifications,
            classification_date='2025-11-06',
            cache_used=False
        )

        self.assertEqual(len(result.classifications), 1)
        self.assertEqual(result.classification_date, '2025-11-06')
        self.assertFalse(result.cache_used)

    def test_to_dict(self):
        """Test conversion to dictionary"""
        classifications = {
            'NVDA': MarketCapClassification(
                ticker='NVDA',
                market_cap=1_000_000_000_000,
                tier=MarketCapTier.LARGE_CAP,
                classification_date='2025-11-06'
            )
        }

        result = BatchClassificationResult(
            classifications=classifications,
            classification_date='2025-11-06',
            cache_used=True
        )

        d = result.to_dict()
        self.assertIn('classifications', d)
        self.assertIn('NVDA', d['classifications'])
        self.assertTrue(d['cache_used'])


class TestJSONExport(unittest.TestCase):
    """Test JSON export functionality"""

    def setUp(self):
        """Create classifier and temp directory"""
        self.classifier = MarketCapClassifier(enable_cache=False)
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_export_to_json(self):
        """Test exporting results to JSON file"""
        classifications = {
            'AAPL': MarketCapClassification(
                ticker='AAPL',
                market_cap=3_000_000_000_000,
                tier=MarketCapTier.LARGE_CAP,
                classification_date='2025-11-06'
            )
        }

        result = BatchClassificationResult(
            classifications=classifications,
            classification_date='2025-11-06',
            cache_used=False
        )

        output_path = Path(self.temp_dir) / "test_output.json"
        self.classifier.export_to_json(result, str(output_path))

        # Verify file exists and is valid JSON
        self.assertTrue(output_path.exists())

        with open(output_path, 'r') as f:
            data = json.load(f)

        self.assertIn('classifications', data)
        self.assertIn('AAPL', data['classifications'])
        self.assertEqual(data['classifications']['AAPL']['tier'], 'Large Cap')


class TestSummaryReport(unittest.TestCase):
    """Test summary report generation"""

    def setUp(self):
        """Create classifier"""
        self.classifier = MarketCapClassifier(enable_cache=False)

    def test_generate_summary_report(self):
        """Test generating summary report"""
        classifications = {
            'LARGE': MarketCapClassification(
                ticker='LARGE',
                market_cap=100_000_000_000,
                tier=MarketCapTier.LARGE_CAP,
                classification_date='2025-11-06'
            ),
            'MID': MarketCapClassification(
                ticker='MID',
                market_cap=10_000_000_000,
                tier=MarketCapTier.MID_CAP,
                classification_date='2025-11-06'
            )
        }

        result = BatchClassificationResult(
            classifications=classifications,
            classification_date='2025-11-06',
            cache_used=False
        )

        report = self.classifier.generate_summary_report(result)

        # Verify report structure
        self.assertIn('Market Cap Classification Report', report)
        self.assertIn('Large Cap', report)
        self.assertIn('Mid Cap', report)
        self.assertIn('| LARGE |', report)
        self.assertIn('| MID |', report)


def run_tests():
    """Run all tests and print results"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"{'='*60}")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
