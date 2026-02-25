"""
Ticker Resolver Service

Provides comprehensive ticker symbol resolution across multiple data sources.
Automatically finds correct ticker symbols for companies, handling different
naming conventions used by various financial data providers.

Features:
- Query by company name or partial ticker
- Multi-source resolution (SimFin, FMP, yfinance)
- Caching of resolved results
- Fallback chains for reliability

Usage:
    from .ticker_resolver import TickerResolver

    resolver = TickerResolver()

    # Resolve a ticker
    result = resolver.resolve('FISV')
    print(result)
    # {'standard': 'FISV', 'simfin': 'FI', 'fmp': 'FISV', 'yfinance': 'FISV'}

    # Search by company name
    result = resolver.search_by_name('Fiserv')
    print(result)
    # {'FISV': {'simfin': 'FI', ...}, ...}

    # Smart fetch with automatic resolution
    data = resolver.smart_fetch('GOOGL', fetcher)
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .ticker_cache import TickerMappingCache, get_ticker_mapping_cache
from .ticker_mapping import (
    TICKER_MAPPING,
    get_api_ticker,
    is_mapped_ticker,
    add_mapping,
)

logger = logging.getLogger(__name__)


class TickerResolutionResult:
    """
    Result of a ticker resolution operation.

    Attributes:
        query: Original query string
        resolved: Dict mapping API source to resolved ticker
        found: Whether any resolution was successful
        confidence: Confidence level ('high', 'medium', 'low')
        source: Source of the resolution ('cache', 'mapping', 'api')
    """

    def __init__(
        self,
        query: str,
        resolved: Dict[str, str],
        found: bool,
        confidence: str = 'medium',
        source: str = 'mapping'
    ):
        self.query = query
        self.resolved = resolved
        self.found = found
        self.confidence = confidence
        self.source = source

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'query': self.query,
            'resolved': self.resolved,
            'found': self.found,
            'confidence': self.confidence,
            'source': self.source
        }

    def get(self, api_source: str, default: str = None) -> str:
        """Get resolved ticker for a specific API source."""
        return self.resolved.get(api_source, default or self.query)


class TickerResolver:
    """
    Comprehensive ticker symbol resolver for financial data APIs.

    This class handles the complexity of ticker symbol differences across
    different financial data providers. It provides:
    - Ticker mapping translation
    - Company name search
    - Automatic discovery of new mappings
    - Caching for performance

    Example:
        >>> resolver = TickerResolver()
        >>> result = resolver.resolve('FISV')
        >>> print(result.resolved)
        {'standard': 'FISV', 'simfin': 'FI', 'yfinance': 'FISV'}
    """

    def __init__(
        self,
        cache: Optional[TickerMappingCache] = None,
        auto_discover: bool = True
    ):
        """
        Initialize ticker resolver.

        Args:
            cache: Optional TickerMappingCache instance
            auto_discover: Whether to auto-discover new mappings (default: True)
        """
        self.cache = cache or get_ticker_mapping_cache()
        self.auto_discover = auto_discover

    def resolve(self, ticker: str) -> TickerResolutionResult:
        """
        Resolve a standard ticker to all API-specific tickers.

        Args:
            ticker: Standard ticker symbol (e.g., 'FISV', 'GOOGL')

        Returns:
            TickerResolutionResult with resolved tickers for each API
        """
        if not ticker:
            return TickerResolutionResult(
                query='',
                resolved={'standard': ''},
                found=False,
                confidence='low',
                source='none'
            )

        ticker = ticker.upper()
        resolved: Dict[str, str] = {'standard': ticker}
        found_mapping = False

        # Check static mappings first
        for api_source in TICKER_MAPPING.keys():
            mapped = get_api_ticker(ticker, api_source)
            resolved[api_source] = mapped

            if mapped != ticker:
                found_mapping = True
                logger.debug(f"Mapped {ticker} -> {mapped} ({api_source})")

        # Check cache for auto-discovered mappings
        for api_source in TICKER_MAPPING.keys():
            cached = self.cache.get(ticker, api_source)
            if cached and cached != get_api_ticker(ticker, api_source):
                resolved[api_source] = cached
                found_mapping = True
                logger.info(
                    f"Found cached mapping: {ticker} -> {cached} ({api_source})"
                )

        return TickerResolutionResult(
            query=ticker,
            resolved=resolved,
            found=True,
            confidence='high' if found_mapping else 'high',
            source='cache' if found_mapping else 'mapping'
        )

    def resolve_for_api(self, ticker: str, api_source: str) -> str:
        """
        Get API-specific ticker for a single data source.

        Args:
            ticker: Standard ticker symbol
            api_source: API source name ('simfin', 'fmp', etc.)

        Returns:
            API-specific ticker
        """
        # Check cache first
        cached = self.cache.get(ticker, api_source)
        if cached:
            return cached

        # Get from mapping
        mapped = get_api_ticker(ticker, api_source)

        # Cache the result
        self.cache.set(ticker, api_source, mapped)

        return mapped

    def search_by_name(self, company_name: str) -> Dict[str, Dict[str, str]]:
        """
        Search for tickers by company name.

        Note: This requires integration with a search API.
        Currently returns known mappings for common companies.

        Args:
            company_name: Full or partial company name

        Returns:
            Dict mapping standard tickers to their API-specific tickers
        """
        company_name = company_name.lower()

        # Known company name to ticker mappings
        KNOWN_COMPANIES = {
            'fiserv': {'standard': 'FISV', 'simfin': 'FI'},
            'alphabet': {'standard': 'GOOGL', 'simfin': 'GOOG'},
            'google': {'standard': 'GOOGL', 'simfin': 'GOOG'},
            'berkshire': {'standard': 'BRK.B', 'simfin': 'BRK-B'},
            'burger king': {'standard': 'BF.B', 'simfin': 'BF-B'},
        }

        results: Dict[str, Dict[str, str]] = {}

        for name, mapping in KNOWN_COMPANIES.items():
            if name in company_name or company_name in name:
                ticker = mapping['standard']
                result = self.resolve(ticker)
                results[ticker] = result.resolved

        return results

    def auto_discover_mapping(
        self,
        ticker: str,
        api_source: str,
        data_fetcher: Any
    ) -> Optional[str]:
        """
        Attempt to auto-discover ticker mapping by testing data access.

        Args:
            ticker: Standard ticker symbol
            api_source: API source to test
            data_fetcher: Fetcher instance with fetch method

        Returns:
            Discovered API ticker or None if not found
        """
        if not self.auto_discover:
            return None

        # Try with standard ticker first
        try:
            result = data_fetcher.fetch(ticker)
            if result is not None:
                return ticker  # Standard ticker works
        except Exception:
            pass

        # Try with known mappings
        mapping = TICKER_MAPPING.get(api_source, {})
        if ticker in mapping:
            mapped = mapping[ticker]
            try:
                result = data_fetcher.fetch(mapped)
                if result is not None:
                    self.cache.set(ticker, api_source, mapped, discovered=True)
                    return mapped
            except Exception:
                pass

        # Try variations (common patterns)
        variations = [
            ticker.replace('.', '-'),
            ticker.replace('-', '.'),
            ticker.replace('.B', ''),
            ticker.replace('.A', ''),
        ]

        for variant in variations:
            if variant == ticker:
                continue
            try:
                result = data_fetcher.fetch(variant)
                if result is not None:
                    logger.info(
                        f"Auto-discovered ticker mapping: "
                        f"{ticker} -> {variant} ({api_source})"
                    )
                    add_mapping(api_source, ticker, variant)
                    self.cache.set(ticker, api_source, variant, discovered=True)
                    return variant
            except Exception:
                continue

        return None

    def smart_fetch(
        self,
        ticker: str,
        api_source: str,
        data_fetcher: Any,
        max_attempts: int = 3
    ) -> Optional[Any]:
        """
        Fetch data with automatic ticker resolution and fallback.

        Args:
            ticker: Standard ticker symbol
            api_source: API source to use
            data_fetcher: Fetcher instance with fetch method
            max_attempts: Maximum number of resolution attempts

        Returns:
            Fetched data or None if all attempts fail
        """
        # Get API-specific ticker
        api_ticker = self.resolve_for_api(ticker, api_source)

        if api_ticker != ticker:
            logger.warning(
                f"Ticker mapping applied: '{ticker}' -> '{api_ticker}' ({api_source})"
            )

        # Try API-specific ticker first
        try:
            result = data_fetcher.fetch(api_ticker)
            if result is not None:
                return result
        except Exception as e:
            logger.debug(f"Fetch failed for {api_ticker}: {e}")

        # Try auto-discovery if enabled
        if self.auto_discover:
            discovered = self.auto_discover_mapping(
                ticker, api_source, data_fetcher
            )
            if discovered and discovered != api_ticker:
                logger.warning(
                    f"Auto-discovered new mapping: "
                    f"{ticker} -> {discovered} ({api_source})"
                )
                api_ticker = discovered
                try:
                    result = data_fetcher.fetch(api_ticker)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.debug(f"Fetch failed for {discovered}: {e}")

        # Try original ticker as last resort
        if api_ticker != ticker:
            try:
                result = data_fetcher.fetch(ticker)
                if result is not None:
                    logger.warning(
                        f"Fallback to standard ticker: {ticker} ({api_source})"
                    )
                    return result
            except Exception as e:
                logger.debug(f"Fallback fetch failed for {ticker}: {e}")

        return None

    def add_known_mapping(
        self,
        standard_ticker: str,
        api_source: str,
        api_ticker: str
    ) -> None:
        """
        Add a known ticker mapping to both static and cache.

        Args:
            standard_ticker: Standard ticker symbol
            api_source: API source
            api_ticker: API-specific ticker
        """
        add_mapping(api_source, standard_ticker, api_ticker)
        self.cache.set(standard_ticker, api_source, api_ticker)
        logger.info(
            f"Added known mapping: {standard_ticker} -> {api_ticker} ({api_source})"
        )

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the mapping cache."""
        self.cache.clear()


def get_ticker_resolver(
    cache: Optional[TickerMappingCache] = None,
    auto_discover: bool = True
) -> TickerResolver:
    """
    Factory function to get a TickerResolver instance.

    Args:
        cache: Optional TickerMappingCache instance
        auto_discover: Whether to auto-discover new mappings

    Returns:
        TickerResolver instance
    """
    return TickerResolver(cache=cache, auto_discover=auto_discover)
