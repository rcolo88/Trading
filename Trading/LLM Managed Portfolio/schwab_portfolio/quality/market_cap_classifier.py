#!/usr/bin/env python3
"""
Market Cap Classifier - Tier Classification for Quality Analysis Framework

Classifies stocks into market cap tiers based on research guidelines from
UPDATES.md and lookback_calculator.py for consistent tier definitions.

Tiers (matching lookback_calculator.py):
- Mega Cap: > $200B (1.25x lookback multiplier)
- Large Cap: $10B - $200B (1.0x baseline multiplier)
- Mid Cap: $2B - $10B (0.75x multiplier)
- Small Cap: $300M - $2B (0.5x multiplier)
- Micro Cap: < $300M (0.35x multiplier, not eligible for portfolio)

Features:
- Market cap classification with consistent tier boundaries
- Batch ticker processing via yfinance
- 4-hour caching for efficiency
- JSON export capability
- Comprehensive error handling

Author: LLM Portfolio Management System
Date: November 6, 2025
"""

import yfinance as yf
import pickle
import json
import logging
from enum import Enum
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketCapTier(Enum):
    """Market capitalization tier classification with lookback multipliers."""
    MEGA_CAP = "Mega Cap"      # > $200B
    LARGE_CAP = "Large Cap"    # $10B - $200B
    MID_CAP = "Mid Cap"        # $2B - $10B
    SMALL_CAP = "Small Cap"    # $300M - $2B
    MICRO_CAP = "Micro Cap"    # < $300M (not eligible)


# Market cap tier thresholds (in dollars) - matching lookback_calculator.py
MEGA_CAP_THRESHOLD = 200_000_000_000   # $200 billion
LARGE_CAP_THRESHOLD = 10_000_000_000   # $10 billion
MID_CAP_THRESHOLD = 2_000_000_000      # $2 billion
SMALL_CAP_THRESHOLD = 300_000_000      # $300 million


@dataclass
class MarketCapClassification:
    """Market cap classification result for a single ticker"""
    ticker: str
    market_cap: Optional[float]
    tier: Optional[MarketCapTier]
    classification_date: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'ticker': self.ticker,
            'market_cap': self.market_cap,
            'tier': self.tier.value if self.tier else None,
            'classification_date': self.classification_date,
            'error': self.error
        }


@dataclass
class BatchClassificationResult:
    """Results from batch classification of multiple tickers"""
    classifications: Dict[str, MarketCapClassification]
    classification_date: str
    cache_used: bool

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'classifications': {
                ticker: result.to_dict()
                for ticker, result in self.classifications.items()
            },
            'classification_date': self.classification_date,
            'cache_used': self.cache_used
        }


class MarketCapCache:
    """Simple 4-hour file cache for market cap data"""

    def __init__(self, cache_file: str = "market_cap_cache.pkl"):
        self.cache_file = Path(cache_file)
        self.cache_duration = timedelta(hours=4)

    def get(self, ticker: str) -> Optional[MarketCapClassification]:
        """Retrieve cached market cap for ticker if valid"""
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            # Check if ticker is in cache
            if ticker not in cache_data:
                return None

            cached_item = cache_data[ticker]
            cache_time = datetime.fromisoformat(cached_item['timestamp'])

            # Check if cache is still valid (4 hours)
            if datetime.now() - cache_time < self.cache_duration:
                logger.debug(f"Using cached market cap for {ticker} from {cache_time}")
                return cached_item['classification']
            else:
                logger.debug(f"Cache expired for {ticker}")
                return None

        except Exception as e:
            logger.warning(f"Failed to load cache for {ticker}: {e}")
            return None

    def set(self, ticker: str, classification: MarketCapClassification):
        """Cache market cap classification with timestamp"""
        try:
            # Load existing cache
            cache_data = {}
            if self.cache_file.exists():
                try:
                    with open(self.cache_file, 'rb') as f:
                        cache_data = pickle.load(f)
                except Exception:
                    pass  # Start fresh if cache corrupted

            # Update with new data
            cache_data[ticker] = {
                'timestamp': datetime.now().isoformat(),
                'classification': classification
            }

            # Save cache
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.debug(f"Cached market cap for {ticker}")

        except Exception as e:
            logger.warning(f"Failed to save cache for {ticker}: {e}")

    def clear(self):
        """Clear the entire cache"""
        if self.cache_file.exists():
            self.cache_file.unlink()
            logger.info("Market cap cache cleared")


class MarketCapClassifier:
    """
    Classifies stocks into market cap tiers for 4-tier portfolio framework.

    Uses yfinance to fetch market capitalization data and classifies stocks
    into Large Cap (≥$50B), Mid Cap ($2B-$50B), Small Cap ($500M-$2B), or
    Micro Cap (<$500M).

    Features:
    - 4-hour caching to reduce API calls
    - Batch processing for multiple tickers
    - Comprehensive error handling
    - JSON export capability

    Example:
        >>> classifier = MarketCapClassifier()
        >>> tier = classifier.classify_ticker("AAPL")
        >>> print(tier.tier)  # MarketCapTier.LARGE_CAP
        >>>
        >>> results = classifier.batch_classify_tickers(["AAPL", "NVDA", "GOOGL"])
        >>> for ticker, result in results.classifications.items():
        ...     print(f"{ticker}: {result.tier.value}")
    """

    def __init__(self, enable_cache: bool = True):
        """
        Initialize market cap classifier

        Args:
            enable_cache: If True, use 4-hour cache for market cap data
        """
        self.cache = MarketCapCache() if enable_cache else None

    @staticmethod
    def classify_by_market_cap(market_cap: float) -> MarketCapTier:
        """
        Classify market cap value into tier.

        Tier boundaries (matching lookback_calculator.py):
        - Mega Cap: > $200B
        - Large Cap: $10B - $200B
        - Mid Cap: $2B - $10B
        - Small Cap: $300M - $2B
        - Micro Cap: < $300M

        Args:
            market_cap: Market capitalization in dollars

        Returns:
            MarketCapTier enum value

        Raises:
            ValueError: If market_cap is negative or zero

        Example:
            >>> MarketCapClassifier.classify_by_market_cap(446_300_000_000_000)
            <MarketCapTier.MEGA_CAP: 'Mega Cap'>
        """
        if market_cap <= 0:
            raise ValueError(f"Market cap must be positive, got {market_cap}")

        if market_cap >= MEGA_CAP_THRESHOLD:
            return MarketCapTier.MEGA_CAP
        elif market_cap >= LARGE_CAP_THRESHOLD:
            return MarketCapTier.LARGE_CAP
        elif market_cap >= MID_CAP_THRESHOLD:
            return MarketCapTier.MID_CAP
        elif market_cap >= SMALL_CAP_THRESHOLD:
            return MarketCapTier.SMALL_CAP
        else:
            return MarketCapTier.MICRO_CAP

    def fetch_market_cap(self, ticker: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Fetch market cap for a single ticker via yfinance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Tuple of (market_cap, error_message)
            - market_cap: Market cap in dollars or None if error
            - error_message: Error description or None if successful
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Try multiple fields for market cap
            market_cap = info.get('marketCap')

            if market_cap is None:
                # Fallback: try calculating from sharesOutstanding and currentPrice
                shares = info.get('sharesOutstanding')
                price = info.get('currentPrice') or info.get('regularMarketPrice')

                if shares and price:
                    market_cap = shares * price
                    logger.debug(f"Calculated market cap for {ticker}: ${market_cap:,.0f}")

            if market_cap is None or market_cap <= 0:
                error = f"Market cap not available or invalid for {ticker}"
                logger.warning(error)
                return None, error

            logger.debug(f"Fetched market cap for {ticker}: ${market_cap:,.0f}")
            return market_cap, None

        except Exception as e:
            error = f"Failed to fetch market cap for {ticker}: {str(e)}"
            logger.error(error)
            return None, error

    def classify_ticker(self, ticker: str, _from_cache: list = None) -> MarketCapClassification:
        """
        Classify a single ticker into market cap tier.

        Checks cache first, then fetches from yfinance if needed.

        Args:
            ticker: Stock ticker symbol
            _from_cache: Internal parameter to track cache hits (list to allow mutation)

        Returns:
            MarketCapClassification with tier and market cap
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(ticker)
            if cached:
                if _from_cache is not None:
                    _from_cache.append(True)  # Mark as cache hit
                return cached

        # Fetch market cap
        market_cap, error = self.fetch_market_cap(ticker)

        # Classify
        tier = None
        if market_cap is not None:
            try:
                tier = self.classify_by_market_cap(market_cap)
            except ValueError as e:
                error = str(e)

        # Create result
        result = MarketCapClassification(
            ticker=ticker,
            market_cap=market_cap,
            tier=tier,
            classification_date=datetime.now().strftime("%Y-%m-%d"),
            error=error
        )

        # Cache result
        if self.cache and error is None:
            self.cache.set(ticker, result)

        return result

    def batch_classify_tickers(self, tickers: List[str]) -> BatchClassificationResult:
        """
        Classify multiple tickers into market cap tiers.

        Efficiently processes multiple tickers using cache when available.

        Args:
            tickers: List of stock ticker symbols

        Returns:
            BatchClassificationResult with all classifications

        Example:
            >>> classifier = MarketCapClassifier()
            >>> results = classifier.batch_classify_tickers(["AAPL", "NVDA", "QS"])
            >>> for ticker, result in results.classifications.items():
            ...     if result.tier:
            ...         print(f"{ticker}: {result.tier.value} (${result.market_cap/1e9:.1f}B)")
        """
        logger.info(f"Classifying {len(tickers)} tickers into market cap tiers")

        classifications = {}
        cache_hit_list = []

        for ticker in tickers:
            result = self.classify_ticker(ticker, _from_cache=cache_hit_list)
            classifications[ticker] = result

        cache_hits = len(cache_hit_list)
        cache_used = cache_hits > 0
        if cache_used:
            logger.info(f"Cache hits: {cache_hits}/{len(tickers)} tickers")

        return BatchClassificationResult(
            classifications=classifications,
            classification_date=datetime.now().strftime("%Y-%m-%d"),
            cache_used=cache_used
        )

    def export_to_json(self, result: BatchClassificationResult, filepath: str):
        """
        Export classification results to JSON file.

        Args:
            result: BatchClassificationResult to export
            filepath: Path to output JSON file
        """
        try:
            output_path = Path(filepath)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)

            logger.info(f"Exported market cap classifications to {output_path}")

        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            raise

    def generate_summary_report(self, result: BatchClassificationResult) -> str:
        """
        Generate human-readable summary report of classifications.

        Args:
            result: BatchClassificationResult to summarize

        Returns:
            Formatted markdown string
        """
        lines = [
            "# Market Cap Classification Report",
            f"**Date:** {result.classification_date}",
            f"**Total Tickers:** {len(result.classifications)}",
            f"**Cache Used:** {'Yes' if result.cache_used else 'No'}",
            "",
            "## Classification Summary",
            ""
        ]

        # Count by tier
        tier_counts = {}
        errors = []

        for ticker, classification in result.classifications.items():
            if classification.error:
                errors.append(f"- {ticker}: {classification.error}")
            elif classification.tier:
                tier_name = classification.tier.value
                tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

        # Tier breakdown
        for tier in MarketCapTier:
            count = tier_counts.get(tier.value, 0)
            lines.append(f"- **{tier.value}**: {count} holdings")

        if errors:
            lines.append("")
            lines.append("## Errors")
            lines.extend(errors)

        lines.append("")
        lines.append("## Detailed Classifications")
        lines.append("")
        lines.append("| Ticker | Market Cap | Tier |")
        lines.append("|--------|-----------|------|")

        for ticker in sorted(result.classifications.keys()):
            classification = result.classifications[ticker]

            if classification.error:
                lines.append(f"| {ticker} | N/A | ERROR |")
            elif classification.market_cap and classification.tier:
                mc_billions = classification.market_cap / 1e9
                lines.append(f"| {ticker} | ${mc_billions:.2f}B | {classification.tier.value} |")

        return "\n".join(lines)


def main():
    """Command-line interface for market cap classifier"""
    import argparse

    parser = argparse.ArgumentParser(description="Market Cap Classifier for 4-Tier Framework")
    parser.add_argument('tickers', nargs='*', help='Ticker symbols to classify')
    parser.add_argument('--no-cache', action='store_true', help='Disable caching')
    parser.add_argument('--json', type=str, help='Export to JSON file')
    parser.add_argument('--clear-cache', action='store_true', help='Clear cache and exit')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize classifier
    classifier = MarketCapClassifier(enable_cache=not args.no_cache)

    # Clear cache if requested
    if args.clear_cache:
        if classifier.cache:
            classifier.cache.clear()
        else:
            logger.warning("Caching is disabled, nothing to clear")
        return

    # Classify tickers
    if not args.tickers:
        # Default test tickers
        args.tickers = ["AAPL", "NVDA", "GOOGL", "MSFT", "QS", "IONQ"]

    result = classifier.batch_classify_tickers(args.tickers)

    # Print summary
    print("\n" + classifier.generate_summary_report(result))

    # Export to JSON if requested
    if args.json:
        classifier.export_to_json(result, args.json)


if __name__ == "__main__":
    main()
