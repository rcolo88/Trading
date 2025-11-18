#!/usr/bin/env python3
"""
News Analysis Script
Standalone script to fetch and analyze financial news for portfolio holdings using Yahoo Finance

Features:
- Uses Yahoo Finance (yfinance) for news - no API key required!
- Free and unlimited news access
- Analyzes sentiment with NewsAgent (HuggingFace FinBERT)

Outputs:
- outputs/news_analysis_YYYYMMDD.json: Complete news analysis results
- outputs/news_analysis_YYYYMMDD_summary.txt: Human-readable summary
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Add parent directory to path for imports (Portfolio Scripts Schwab/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.news_fetcher import NewsFetcher, NewsArticle
from agents.news_agent import NewsAgent
from config.hf_config import HFConfig

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsAnalysisScript:
    """
    Standalone news analysis pipeline

    Workflow:
    1. Load current portfolio holdings
    2. Fetch recent news for holdings (Yahoo Finance via yfinance)
    3. Analyze sentiment with NewsAgent (HuggingFace FinBERT)
    4. Export results to JSON and summary text
    """

    def __init__(self, days_back: int = 7):
        """
        Initialize news analysis script

        Args:
            days_back: Number of days to look back for news (default: 7)
        """
        self.days_back = days_back
        self.news_fetcher = NewsFetcher()
        self.news_agent = NewsAgent()
        self.results = {}

    def load_portfolio_holdings(self) -> List[str]:
        """
        Load current portfolio holdings from portfolio_state.json

        Returns:
            List of ticker symbols in portfolio
        """
        # Portfolio state is in parent directory
        portfolio_path = Path(__file__).parent.parent / "portfolio_state.json"

        if not portfolio_path.exists():
            logger.warning(f"Portfolio state not found at {portfolio_path}")
            return []

        try:
            with open(portfolio_path, 'r') as f:
                state = json.load(f)

            holdings = list(state.get('holdings', {}).keys())
            logger.info(f"Loaded {len(holdings)} holdings from portfolio: {holdings}")
            return holdings

        except Exception as e:
            logger.error(f"Failed to load portfolio holdings: {e}")
            return []

    def fetch_news_for_tickers(self, tickers: List[str]) -> Dict[str, List[NewsArticle]]:
        """
        Fetch news for list of tickers

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> list of NewsArticle objects
        """
        logger.info(f"Fetching news for {len(tickers)} tickers ({self.days_back} days back)")

        news_data = self.news_fetcher.batch_fetch_news(tickers, days_back=self.days_back)

        # Log summary
        total_articles = sum(len(articles) for articles in news_data.values())
        logger.info(f"Fetched {total_articles} total articles across {len(tickers)} tickers")

        return news_data

    def analyze_sentiment(self, news_data: Dict[str, List[NewsArticle]]) -> Dict[str, Dict]:
        """
        Analyze sentiment for all news articles

        Args:
            news_data: Dict mapping ticker -> list of NewsArticle objects

        Returns:
            Dict with analysis results per ticker
        """
        analysis_results = {}

        for ticker, articles in news_data.items():
            if not articles:
                logger.info(f"No articles for {ticker}, skipping sentiment analysis")
                analysis_results[ticker] = {
                    'article_count': 0,
                    'sentiment': 'neutral',
                    'confidence': 0.0,
                    'articles': []
                }
                continue

            logger.info(f"Analyzing {len(articles)} articles for {ticker}")

            # Analyze each article
            article_analyses = []
            for article in articles:
                # Combine title and summary for analysis
                text = f"{article.title}. {article.summary}"

                # Analyze sentiment
                result = self.news_agent.analyze(text, context={'ticker': ticker})

                article_analyses.append({
                    'title': article.title,
                    'published': article.published,
                    'source': article.source,
                    'url': article.url,
                    'sentiment': result.sentiment,
                    'confidence': result.confidence,
                    'label': result.label
                })

            # Calculate aggregate sentiment
            positive_count = sum(1 for a in article_analyses if a['sentiment'] == 'positive')
            negative_count = sum(1 for a in article_analyses if a['sentiment'] == 'negative')
            neutral_count = sum(1 for a in article_analyses if a['sentiment'] == 'neutral')

            total_count = len(article_analyses)

            # Determine overall sentiment (majority vote)
            if positive_count > negative_count and positive_count > neutral_count:
                overall_sentiment = 'positive'
                overall_confidence = positive_count / total_count
            elif negative_count > positive_count and negative_count > neutral_count:
                overall_sentiment = 'negative'
                overall_confidence = negative_count / total_count
            else:
                overall_sentiment = 'neutral'
                overall_confidence = neutral_count / total_count

            analysis_results[ticker] = {
                'article_count': total_count,
                'sentiment': overall_sentiment,
                'confidence': overall_confidence,
                'breakdown': {
                    'positive': positive_count,
                    'negative': negative_count,
                    'neutral': neutral_count
                },
                'articles': article_analyses
            }

            logger.info(f"{ticker}: {overall_sentiment} ({overall_confidence:.1%} confidence)")

        return analysis_results

    def export_results(self, analysis_results: Dict[str, Dict]):
        """
        Export analysis results to JSON and summary text

        Args:
            analysis_results: Analysis results dictionary
        """
        # Create outputs directory if it doesn't exist
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d")

        # Export JSON
        json_file = output_dir / f"news_analysis_{timestamp}.json"
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'days_back': self.days_back,
            'ticker_count': len(analysis_results),
            'total_articles': sum(r['article_count'] for r in analysis_results.values()),
            'results': analysis_results
        }

        with open(json_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Exported JSON results to {json_file}")

        # Export summary text
        summary_file = output_dir / f"news_analysis_{timestamp}_summary.txt"
        with open(summary_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("NEWS SENTIMENT ANALYSIS SUMMARY\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Period: Last {self.days_back} days\n")
            f.write(f"Tickers Analyzed: {len(analysis_results)}\n")
            f.write(f"Total Articles: {sum(r['article_count'] for r in analysis_results.values())}\n")
            f.write("="*60 + "\n\n")

            for ticker, result in sorted(analysis_results.items()):
                f.write(f"{ticker}:\n")
                f.write(f"  Sentiment: {result['sentiment'].upper()}\n")
                f.write(f"  Confidence: {result['confidence']:.1%}\n")
                f.write(f"  Articles Analyzed: {result['article_count']}\n")
                if result['article_count'] > 0:
                    f.write(f"  Breakdown: {result['breakdown']['positive']} positive, "
                           f"{result['breakdown']['negative']} negative, "
                           f"{result['breakdown']['neutral']} neutral\n")

                    # Show most recent article
                    if result['articles']:
                        latest = result['articles'][0]
                        f.write(f"  Latest Article:\n")
                        f.write(f"    Title: {latest['title']}\n")
                        f.write(f"    Source: {latest['source']}\n")
                        f.write(f"    Sentiment: {latest['sentiment']}\n")

                f.write("\n")

        logger.info(f"Exported summary to {summary_file}")

        # Print summary to console
        print("\n" + "="*60)
        print("NEWS SENTIMENT ANALYSIS COMPLETE")
        print("="*60)
        print(f"Analyzed {len(analysis_results)} tickers")
        print(f"Total articles: {sum(r['article_count'] for r in analysis_results.values())}")
        print(f"\nResults saved to:")
        print(f"  - {json_file}")
        print(f"  - {summary_file}")
        print("="*60 + "\n")

    def run(self, tickers: Optional[List[str]] = None):
        """
        Run complete news analysis pipeline

        Args:
            tickers: Optional list of tickers to analyze. If None, uses portfolio holdings.
        """
        logger.info("Starting news analysis pipeline")

        # Load holdings if no tickers provided
        if tickers is None:
            tickers = self.load_portfolio_holdings()

        if not tickers:
            logger.error("No tickers to analyze. Exiting.")
            return

        # Fetch news
        news_data = self.fetch_news_for_tickers(tickers)

        # Analyze sentiment
        analysis_results = self.analyze_sentiment(news_data)

        # Export results
        self.export_results(analysis_results)

        logger.info("News analysis pipeline complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch and analyze financial news sentiment for portfolio holdings using Yahoo Finance"
    )
    parser.add_argument(
        '--days-back',
        type=int,
        default=7,
        help='Number of days to look back for news (default: 7)'
    )
    parser.add_argument(
        '--tickers',
        type=str,
        nargs='+',
        help='Specific tickers to analyze (default: portfolio holdings)'
    )

    args = parser.parse_args()

    # Run analysis (no API key required with Yahoo Finance!)
    print("Using Yahoo Finance for news (no API key required)")
    script = NewsAnalysisScript(days_back=args.days_back)
    script.run(tickers=args.tickers)


if __name__ == "__main__":
    main()
