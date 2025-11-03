"""
Test Suite for News Fetcher Module
Tests news fetching functionality with and without API key
"""

import unittest
import os
import tempfile
from datetime import datetime, timedelta
from news_fetcher import NewsFetcher, NewsArticle, NewsCache, get_sp500_tickers


class TestNewsArticle(unittest.TestCase):
    """Test NewsArticle dataclass"""

    def setUp(self):
        self.article = NewsArticle(
            ticker="AAPL",
            title="Apple Announces New iPhone",
            published=datetime.now().isoformat(),
            source="Reuters",
            url="https://reuters.com/test",
            summary="Apple announced...",
            category="earnings"
        )

    def test_to_dict(self):
        """Test conversion to dictionary"""
        d = self.article.to_dict()
        self.assertEqual(d['ticker'], "AAPL")
        self.assertEqual(d['source'], "Reuters")
        self.assertIn('title', d)

    def test_is_stale_fresh(self):
        """Test that recent article is not stale"""
        self.assertFalse(self.article.is_stale(max_age_hours=24))

    def test_is_stale_old(self):
        """Test that old article is stale"""
        old_article = NewsArticle(
            ticker="AAPL",
            title="Old News",
            published=(datetime.now() - timedelta(days=10)).isoformat(),
            source="Reuters",
            url="https://test.com",
            summary="Old news",
            category="general"
        )
        self.assertTrue(old_article.is_stale(max_age_hours=48))


class TestNewsCache(unittest.TestCase):
    """Test NewsCache functionality"""

    def setUp(self):
        # Use temp file for cache
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pkl')
        self.cache = NewsCache(cache_file=self.temp_file.name, cache_hours=1)
        self.articles = [
            NewsArticle(
                ticker="AAPL",
                title="Test Article",
                published=datetime.now().isoformat(),
                source="Test",
                url="https://test.com",
                summary="Test",
                category="general"
            )
        ]

    def tearDown(self):
        # Clean up temp file
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_set_and_get(self):
        """Test caching and retrieval"""
        self.cache.set("AAPL", 7, self.articles)
        retrieved = self.cache.get("AAPL", 7)
        self.assertIsNotNone(retrieved)
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0].ticker, "AAPL")

    def test_get_miss(self):
        """Test cache miss"""
        retrieved = self.cache.get("NVDA", 7)
        self.assertIsNone(retrieved)

    def test_clear(self):
        """Test cache clearing"""
        self.cache.set("AAPL", 7, self.articles)
        self.cache.clear()
        retrieved = self.cache.get("AAPL", 7)
        self.assertIsNone(retrieved)


class TestNewsFetcher(unittest.TestCase):
    """Test NewsFetcher functionality"""

    def setUp(self):
        """Setup - check if API key is available"""
        self.api_key = os.getenv("FINNHUB_API_KEY")
        self.has_api_key = self.api_key is not None

        if self.has_api_key:
            self.fetcher = NewsFetcher(enable_cache=False)  # Disable cache for tests

    def test_init_without_api_key(self):
        """Test that init fails without API key"""
        if not self.has_api_key:
            with self.assertRaises(ValueError):
                NewsFetcher(api_key=None)

    @unittest.skipIf(not os.getenv("FINNHUB_API_KEY"), "Finnhub API key not set")
    def test_fetch_company_news(self):
        """Test fetching company news (requires API key)"""
        articles = self.fetcher.fetch_company_news("AAPL", days_back=7)

        # Should return a list (may be empty if no news)
        self.assertIsInstance(articles, list)

        # If articles exist, check structure
        if articles:
            article = articles[0]
            self.assertIsInstance(article, NewsArticle)
            self.assertEqual(article.ticker, "AAPL")
            self.assertIsNotNone(article.title)
            self.assertIsNotNone(article.url)
            self.assertIsNotNone(article.source)

    @unittest.skipIf(not os.getenv("FINNHUB_API_KEY"), "Finnhub API key not set")
    def test_fetch_market_news(self):
        """Test fetching market news (requires API key)"""
        news = self.fetcher.fetch_market_news(category="general", limit=10)

        # Should return a list
        self.assertIsInstance(news, list)

        # Check limit is respected
        self.assertLessEqual(len(news), 10)

    @unittest.skipIf(not os.getenv("FINNHUB_API_KEY"), "Finnhub API key not set")
    def test_get_news_sentiment(self):
        """Test getting Finnhub sentiment (requires API key)"""
        sentiment = self.fetcher.get_news_sentiment("AAPL")

        # May return None if no sentiment data available
        if sentiment:
            self.assertIn('sentiment', sentiment)

    @unittest.skipIf(not os.getenv("FINNHUB_API_KEY"), "Finnhub API key not set")
    def test_batch_fetch_news(self):
        """Test batch fetching (requires API key)"""
        tickers = ["AAPL", "MSFT"]
        results = self.fetcher.batch_fetch_news(tickers, days_back=7)

        # Should return dict
        self.assertIsInstance(results, dict)

        # Should have entries for all tickers
        for ticker in tickers:
            self.assertIn(ticker, results)
            self.assertIsInstance(results[ticker], list)

    def test_is_future_dated(self):
        """Test future date detection"""
        if not self.has_api_key:
            self.skipTest("API key not available")

        # Create future-dated article
        future_article = NewsArticle(
            ticker="TEST",
            title="Future News",
            published=(datetime.now() + timedelta(days=1)).isoformat(),
            source="Test",
            url="https://test.com",
            summary="Future",
            category="general"
        )

        self.assertTrue(self.fetcher._is_future_dated(future_article))

        # Create normal article
        normal_article = NewsArticle(
            ticker="TEST",
            title="Normal News",
            published=datetime.now().isoformat(),
            source="Test",
            url="https://test.com",
            summary="Normal",
            category="general"
        )

        self.assertFalse(self.fetcher._is_future_dated(normal_article))

    def test_deduplicate(self):
        """Test deduplication logic"""
        if not self.has_api_key:
            self.skipTest("API key not available")

        # Create duplicate articles
        articles = [
            NewsArticle(
                ticker="AAPL",
                title="Apple Announces iPhone",
                published=datetime.now().isoformat(),
                source="Reuters",
                url="https://reuters.com/1",
                summary="Test",
                category="general"
            ),
            NewsArticle(
                ticker="AAPL",
                title="Apple Announces iPhone",  # Duplicate title
                published=datetime.now().isoformat(),
                source="Bloomberg",
                url="https://bloomberg.com/1",
                summary="Test",
                category="general"
            ),
            NewsArticle(
                ticker="AAPL",
                title="Apple Announces MacBook",  # Different title
                published=datetime.now().isoformat(),
                source="Reuters",
                url="https://reuters.com/2",
                summary="Test",
                category="general"
            )
        ]

        deduplicated = self.fetcher._deduplicate(articles)

        # Should have 2 unique articles
        self.assertEqual(len(deduplicated), 2)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_get_sp500_tickers(self):
        """Test S&P 500 ticker fetching"""
        tickers = get_sp500_tickers()

        # Should return a list
        self.assertIsInstance(tickers, list)

        # S&P 500 has ~500 stocks (may vary slightly)
        if tickers:  # Only check if fetch succeeded
            self.assertGreater(len(tickers), 400)
            self.assertLess(len(tickers), 600)

            # Should contain well-known tickers
            self.assertIn("AAPL", tickers)
            self.assertIn("MSFT", tickers)


def run_tests():
    """Run test suite with detailed output"""
    # Check for API key
    has_key = os.getenv("FINNHUB_API_KEY") is not None

    print("\n" + "="*60)
    print("NEWS FETCHER TEST SUITE")
    print("="*60)
    print(f"Finnhub API Key: {'SET' if has_key else 'NOT SET'}")
    if not has_key:
        print("\nWARNING: Some tests will be skipped without FINNHUB_API_KEY")
        print("Get a free key at: https://finnhub.io/")
    print("="*60 + "\n")

    # Run tests
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    run_tests()
