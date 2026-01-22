"""
Ticker Symbol Mapping Module

Provides ticker symbol translation between standard tickers (used by users/exchanges)
and API-specific tickers used by different data providers.

This solves the issue where different financial data APIs use different ticker conventions:
- SimFin: GOOGL -> GOOG, FISV -> FI
- Other providers may have their own mappings

Usage:
    from .ticker_mapping import get_api_ticker, TICKER_MAPPING

    # Get SimFin-specific ticker
    simfin_ticker = get_api_ticker('FISV', 'simfin')  # Returns 'FI'

    # Check if mapping exists
    is_mapped = is_mapped_ticker('GOOGL', 'simfin')  # Returns True
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


TICKER_MAPPING: Dict[str, Dict[str, str]] = {
    'simfin': {
        # Alphabet (Google) - SimFin uses GOOG for both share classes
        'GOOGL': 'GOOG',
        'GOOG': 'GOOG',

        # Fiserv - SimFin uses abbreviation
        'FISV': 'FI',
        'FI': 'FI',

        # Berkshire Hathaway
        'BRK.B': 'BRK-B',
        'BRK.A': 'BRK-A',

        # Other common mappings
        'BF.B': 'BF-B',
        'V': 'V',
        'MA': 'MA',
    },
    'fmp': {
        # FMP-specific mappings (if any)
        # Add as discovered
    },
    'yfinance': {
        # yfinance generally uses standard tickers, but some exceptions exist
        # Add as discovered
    },
    'polygon': {
        # Polygon.io specific mappings
        'BRK.B': 'BRK.B',  # Polygon uses dots
        'BRK.A': 'BRK.A',
    },
}


def get_api_ticker(ticker: str, api_source: str) -> str:
    """
    Convert standard ticker to API-specific ticker.

    Args:
        ticker: Standard ticker symbol (e.g., 'GOOGL', 'FISV')
        api_source: Data source ('simfin', 'fmp', 'yfinance', 'polygon')

    Returns:
        API-specific ticker symbol. Returns original ticker if no mapping exists.
    """
    if not ticker:
        return ticker

    ticker = ticker.upper()
    api_source = api_source.lower()

    mapping = TICKER_MAPPING.get(api_source, {})

    if ticker in mapping:
        mapped = mapping[ticker]
        logger.debug(f"Ticker mapping: {ticker} -> {mapped} ({api_source})")
        return mapped

    return ticker


def get_standard_ticker(api_ticker: str, api_source: str) -> str:
    """
    Convert API-specific ticker back to standard ticker.

    Args:
        api_ticker: API-specific ticker (e.g., 'FI' for SimFin)
        api_source: Data source ('simfin', 'fmp', etc.)

    Returns:
        Standard ticker symbol. Returns original ticker if no reverse mapping exists.
    """
    if not api_ticker:
        return api_ticker

    api_ticker = api_ticker.upper()
    api_source = api_source.lower()

    mapping = TICKER_MAPPING.get(api_source, {})

    # Reverse lookup
    for standard, api_specific in mapping.items():
        if api_specific == api_ticker:
            return standard

    return api_ticker


def is_mapped_ticker(ticker: str, api_source: str) -> bool:
    """
    Check if a ticker has a mapping for a specific API source.

    Args:
        ticker: Standard ticker symbol
        api_source: Data source ('simfin', 'fmp', etc.)

    Returns:
        True if a mapping exists, False otherwise.
    """
    if not ticker:
        return False

    ticker = ticker.upper()
    api_source = api_source.lower()

    mapping = TICKER_MAPPING.get(api_source, {})
    return ticker in mapping


def get_all_mappings_for_ticker(ticker: str) -> Dict[str, str]:
    """
    Get all API-specific tickers for a given standard ticker.

    Args:
        ticker: Standard ticker symbol

    Returns:
        Dict mapping API source to API-specific ticker
    """
    if not ticker:
        return {}

    ticker = ticker.upper()
    result = {'standard': ticker}

    for api_source, mapping in TICKER_MAPPING.items():
        if ticker in mapping:
            result[api_source] = mapping[ticker]
        else:
            result[api_source] = ticker

    return result


def add_mapping(api_source: str, standard_ticker: str, api_ticker: str) -> None:
    """
    Add a new ticker mapping at runtime.

    Args:
        api_source: Data source ('simfin', 'fmp', etc.)
        standard_ticker: Standard ticker symbol
        api_ticker: API-specific ticker

    Note:
        This is useful for adding mappings discovered during runtime.
        Mappings added here are not persisted to disk.
    """
    api_source = api_source.lower()

    if api_source not in TICKER_MAPPING:
        TICKER_MAPPING[api_source] = {}

    TICKER_MAPPING[api_source][standard_ticker.upper()] = api_ticker.upper()
    logger.info(f"Added ticker mapping: {standard_ticker} -> {api_ticker} ({api_source})")


def get_known_api_sources() -> list:
    """
    Get list of all known API sources with mappings.

    Returns:
        List of API source names
    """
    return list(TICKER_MAPPING.keys())


def validate_ticker_mapping(ticker: str, api_source: str, expected_api_ticker: str) -> bool:
    """
    Validate that a ticker mapping produces the expected result.

    Args:
        ticker: Standard ticker symbol
        api_source: Data source
        expected_api_ticker: Expected API-specific ticker

    Returns:
        True if mapping matches expected, False otherwise
    """
    actual = get_api_ticker(ticker, api_source)
    return actual == expected_api_ticker.upper()
