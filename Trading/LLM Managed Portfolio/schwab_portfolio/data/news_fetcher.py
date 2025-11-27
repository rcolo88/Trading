"""
News Fetcher Module
Fetches real-time financial news from Yahoo Finance (yfinance) with anti-hallucination safeguards
"""

import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pickle
import os
from dataclasses import dataclass, asdict
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """Structured news article data"""
    ticker: str
    title: str
    published: str  # ISO format timestamp
    source: str
    url: str
    summary: str
    category: str = "general"
    sentiment_score: Optional[float] = None  # Reserved for future sentiment analysis

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    def is_stale(self, max_age_hours: int = 168) -> bool:
        """Check if news is older than threshold (default: 7 days)"""
        try:
            article_time = datetime.fromisoformat(self.published.replace('Z', '+00:00'))
            age = datetime.now(article_time.tzinfo) - article_time
            return age.total_seconds() / 3600 > max_age_hours
        except Exception as e:
            logger.warning(f"Failed to parse timestamp {self.published}: {e}")
            return False


class NewsCache:
    """Simple file-based cache for news data"""

    def __init__(self, cache_file: str = "news_cache.pkl", cache_hours: int = 4):
        self.cache_file = cache_file
        self.cache_hours = cache_hours
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    logger.debug(f"Loaded cache with {len(cache)} entries")
                    return cache
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            logger.debug(f"Saved cache with {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def get(self, ticker: str, days_back: int) -> Optional[List[NewsArticle]]:
        """Get cached news if available and fresh"""
        cache_key = f"{ticker}_{days_back}"
        if cache_key in self.cache:
            articles, timestamp = self.cache[cache_key]
            # Check if cache is still fresh
            if datetime.now() - timestamp < timedelta(hours=self.cache_hours):
                logger.debug(f"Cache HIT for {ticker} ({len(articles)} articles)")
                return articles
            else:
                logger.debug(f"Cache EXPIRED for {ticker}")
                del self.cache[cache_key]
        return None

    def set(self, ticker: str, days_back: int, articles: List[NewsArticle]):
        """Cache news articles"""
        cache_key = f"{ticker}_{days_back}"
        self.cache[cache_key] = (articles, datetime.now())
        self._save_cache()
        logger.debug(f"Cached {len(articles)} articles for {ticker}")

    def clear(self):
        """Clear entire cache"""
        self.cache = {}
        self._save_cache()
        logger.info("Cache cleared")


class NewsFetcher:
    """
    Fetch financial news from Yahoo Finance (yfinance) with anti-hallucination safeguards

    Features:
    - Real news articles from Yahoo Finance (no LLM generation)
    - Source URLs for verification
    - Timestamp validation (reject future dates)
    - Deduplication by title similarity
    - 4-hour caching to reduce API calls
    - Graceful error handling
    - No API key required (free and unlimited)

    Source: yfinance Ticker.news property
    """

    def __init__(self, enable_cache: bool = True):
        """
        Initialize Yahoo Finance news fetcher

        Args:
            enable_cache: Enable 4-hour caching (default: True)
        """
        # Initialize cache
        self.cache = NewsCache() if enable_cache else None

        logger.info("NewsFetcher initialized with Yahoo Finance (yfinance)")

    def fetch_company_news(
        self,
        ticker: str,
        days_back: int = 7,
        filter_stale: bool = True
    ) -> List[NewsArticle]:
        """
        Fetch company-specific news from Yahoo Finance

        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back (default: 7)
            filter_stale: Remove news older than days_back (default: True)

        Returns:
            List of NewsArticle objects
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(ticker, days_back)
            if cached is not None:
                return cached

        try:
            logger.info(f"Fetching news for {ticker} (last {days_back} days)")

            # Fetch from Yahoo Finance using yfinance
            stock = yf.Ticker(ticker)
            raw_news = stock.news

            if not raw_news:
                logger.warning(f"No news found for {ticker}")
                return []

            # Convert to NewsArticle objects
            articles = []
            cutoff_time = datetime.now() - timedelta(days=days_back)

            for item in raw_news:
                try:
                    # Extract data from yfinance news format
                    content = item.get('content', {})

                    # Parse publication date
                    pub_date = content.get('pubDate') or content.get('displayTime')
                    if not pub_date:
                        continue

                    # Convert to datetime
                    article_time = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))

                    # Filter by days_back if requested
                    if filter_stale and article_time < cutoff_time.replace(tzinfo=article_time.tzinfo):
                        continue

                    # Create NewsArticle
                    article = NewsArticle(
                        ticker=ticker,
                        title=content.get('title', ''),
                        published=pub_date,
                        source=content.get('provider', {}).get('displayName', 'Yahoo Finance'),
                        url=content.get('canonicalUrl', {}).get('url', ''),
                        summary=content.get('summary', ''),
                        category=content.get('contentType', 'general').lower()
                    )

                    # Anti-hallucination: Validate timestamp
                    if self._is_future_dated(article):
                        logger.warning(f"Rejected future-dated article: {article.title}")
                        continue

                    articles.append(article)

                except Exception as e:
                    logger.warning(f"Failed to parse article for {ticker}: {e}")
                    continue

            # Deduplicate by title similarity
            articles = self._deduplicate(articles)

            logger.info(f"Fetched {len(articles)} articles for {ticker}")

            # Cache results
            if self.cache:
                self.cache.set(ticker, days_back, articles)

            return articles

        except Exception as e:
            logger.error(f"Failed to fetch news for {ticker}: {e}")
            return []

    def fetch_market_news(self, category: str = "general", limit: int = 50) -> List[NewsArticle]:
        """
        Fetch general market news (not supported by Yahoo Finance)

        Note: Yahoo Finance API doesn't provide general market news.
        Use fetch_company_news() for ticker-specific news instead.

        Args:
            category: News category (ignored)
            limit: Maximum number of articles to return (ignored)

        Returns:
            Empty list (feature not available)
        """
        logger.warning("fetch_market_news not supported by Yahoo Finance API")
        logger.info("Use fetch_company_news(ticker) for company-specific news")
        return []

    def batch_fetch_news(
        self,
        tickers: List[str],
        days_back: int = 7
    ) -> Dict[str, List[NewsArticle]]:
        """
        Fetch news for multiple tickers

        Args:
            tickers: List of ticker symbols
            days_back: Number of days to look back

        Returns:
            Dict mapping ticker -> list of NewsArticle objects
        """
        results = {}

        for i, ticker in enumerate(tickers):
            logger.info(f"Fetching news {i+1}/{len(tickers)}: {ticker}")
            articles = self.fetch_company_news(ticker, days_back=days_back)
            results[ticker] = articles

        total_articles = sum(len(articles) for articles in results.values())
        logger.info(f"Batch fetch complete: {total_articles} total articles for {len(tickers)} tickers")

        return results

    def _is_future_dated(self, article: NewsArticle) -> bool:
        """Check if article has a future timestamp (anti-hallucination)"""
        try:
            article_time = datetime.fromisoformat(article.published.replace('Z', '+00:00'))
            return article_time > datetime.now(article_time.tzinfo)
        except Exception:
            return False

    def _deduplicate(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Remove duplicate articles by title similarity"""
        if not articles:
            return []

        unique_articles = []
        seen_titles = set()

        for article in articles:
            # Normalize title for comparison
            normalized_title = article.title.lower().strip()

            if normalized_title not in seen_titles:
                unique_articles.append(article)
                seen_titles.add(normalized_title)

        if len(unique_articles) < len(articles):
            logger.info(f"Removed {len(articles) - len(unique_articles)} duplicate articles")

        return unique_articles

    def export_to_json(self, ticker: str, output_file: str, days_back: int = 7):
        """
        Fetch news and export to JSON file

        Args:
            ticker: Stock ticker symbol
            output_file: Output JSON file path
            days_back: Number of days to look back
        """
        articles = self.fetch_company_news(ticker, days_back=days_back)

        # Convert to dict format
        data = {
            'ticker': ticker,
            'fetch_time': datetime.now().isoformat(),
            'days_back': days_back,
            'article_count': len(articles),
            'articles': [article.to_dict() for article in articles]
        }

        # Write to JSON
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(articles)} articles to {output_file}")


def get_sp500_tickers() -> List[str]:
    """
    Get S&P 500 ticker list from Wikipedia

    Returns:
        List of ticker symbols
    """
    try:
        import pandas as pd
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        logger.info(f"Fetched {len(tickers)} S&P 500 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 tickers: {e}")
        return []


# Example usage
if __name__ == "__main__":
    # Initialize fetcher (no API key required!)
    fetcher = NewsFetcher()

    # Example 1: Fetch news for a single ticker
    print("\n" + "="*60)
    print("Example 1: Fetch news for AAPL")
    print("="*60)
    aapl_news = fetcher.fetch_company_news("AAPL", days_back=7)
    print(f"Found {len(aapl_news)} articles for AAPL")
    if aapl_news:
        print(f"\nMost recent article:")
        print(f"  Title: {aapl_news[0].title}")
        print(f"  Source: {aapl_news[0].source}")
        print(f"  Published: {aapl_news[0].published}")
        print(f"  URL: {aapl_news[0].url}")
        if aapl_news[0].summary:
            print(f"  Summary: {aapl_news[0].summary[:100]}...")

    # Example 2: Batch fetch for multiple tickers
    print("\n" + "="*60)
    print("Example 2: Batch fetch for multiple tickers")
    print("="*60)
    tickers = ["AAPL", "MSFT", "NVDA"]
    batch_results = fetcher.batch_fetch_news(tickers, days_back=7)
    for ticker, articles in batch_results.items():
        print(f"  {ticker}: {len(articles)} articles")

    # Example 3: Export to JSON
    print("\n" + "="*60)
    print("Example 3: Export to JSON")
    print("="*60)
    fetcher.export_to_json("AAPL", "news_aapl.json", days_back=7)
    print("Exported to news_aapl.json")
