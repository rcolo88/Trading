#!/usr/bin/env python3
"""
Watchlist Configuration Module

Provides configurable watchlist system for screening different universes:
- S&P 500 (large cap)
- S&P MidCap 400 (mid cap)
- S&P SmallCap 600 (small cap)
- NASDAQ-100 (tech-focused large cap)
- S&P Composite 1500 (combined SP500 + SP400 + SP600)
- Custom ticker lists

This module replaces the hardcoded S&P 500 watchlist with a flexible
configuration system that enables screening across different market cap tiers.

Usage:
    from data.watchlist_config import WatchlistIndex, WatchlistConfig

    # Screen S&P 500 (default)
    config = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)
    tickers = config.get_tickers()

    # Screen all S&P 1500 (includes mid/small caps)
    config = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)
    tickers = config.get_tickers()

    # Use custom ticker list
    config = WatchlistConfig(
        index=WatchlistIndex.CUSTOM,
        custom_tickers=['NVDA', 'GOOGL', 'MSFT']
    )
    tickers = config.get_tickers()

Academic Foundation:
    - Fama-French (1993): Size and value factors across market caps
    - Banz (1981): Small firm effect - higher returns in small cap
    - S&P index methodology: Transparent, rules-based selection
    - Diversification: Broader universe reduces single-stock risk
"""

import logging
from enum import Enum
from typing import List, Optional, Set
from dataclasses import dataclass

# Import fetcher functions (will be added in Task 2.2)
from data.financial_data_fetcher import (
    get_sp500_tickers,
    get_sp400_tickers,
    get_sp600_tickers,
    get_nasdaq100_tickers
)

logger = logging.getLogger(__name__)


class WatchlistIndex(Enum):
    """Supported watchlist indexes for screening

    Attributes:
        SP500: S&P 500 (large cap ≥$50B, ~500 tickers)
        SP400: S&P MidCap 400 (mid cap $2B-$50B, ~400 tickers)
        SP600: S&P SmallCap 600 (small cap $500M-$2B, ~600 tickers)
        NASDAQ100: NASDAQ-100 (tech-focused large cap, ~100 tickers)
        COMBINED_SP: S&P Composite 1500 (SP500 + SP400 + SP600, ~1500 tickers)
        CUSTOM: Custom ticker list provided by user

    Market Cap Tiers:
        - Large Cap: ≥$50B (dominates SP500, NASDAQ100)
        - Mid Cap: $2B-$50B (dominates SP400)
        - Small Cap: $500M-$2B (dominates SP600)
        - Micro Cap: <$500M (not included in S&P indexes)

    Performance Expectations:
        - SP500 (~500 tickers): 12-17 minutes with ThreadPoolExecutor
        - SP400 (~400 tickers): 10-14 minutes
        - SP600 (~600 tickers): 15-20 minutes
        - NASDAQ100 (~100 tickers): 3-5 minutes
        - COMBINED_SP (~1500 tickers): 45-60 minutes
        - CUSTOM: Depends on list size

    Use Cases:
        - Daily screening: SP500 with limit=50 (2-5 min, uses cache)
        - Weekly screening: SP500 full (12-17 min, refresh data)
        - Monthly screening: COMBINED_SP (45-60 min, find small cap opportunities)
        - Tech focus: NASDAQ100 (3-5 min, tech sector analysis)
        - Custom screening: CUSTOM with hand-picked tickers
    """
    SP500 = "sp500"
    SP400 = "sp400"
    SP600 = "sp600"
    NASDAQ100 = "nasdaq100"
    COMBINED_SP = "combined_sp"
    CUSTOM = "custom"


@dataclass
class WatchlistConfig:
    """Configuration for watchlist screening

    Attributes:
        index: Which index to screen (WatchlistIndex enum)
        custom_tickers: List of tickers (only used if index=CUSTOM)
        limit: Optional limit for number of tickers (for performance)

    Examples:
        # Screen top 50 from S&P 500 (daily quick check)
        config = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)

        # Screen full S&P 500 (weekly full screening)
        config = WatchlistConfig(index=WatchlistIndex.SP500)

        # Screen all S&P 1500 for mid/small cap opportunities (monthly)
        config = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)

        # Screen custom list
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=['NVDA', 'GOOGL', 'MSFT', 'AMZN']
        )

    Validation:
        - If index=CUSTOM, custom_tickers must be provided
        - If limit is set, it applies AFTER deduplication for COMBINED_SP
        - Empty ticker lists will log warning but not raise error
    """
    index: WatchlistIndex
    custom_tickers: Optional[List[str]] = None
    limit: Optional[int] = None

    def get_tickers(self) -> List[str]:
        """Get ticker list based on configuration

        Returns:
            List of ticker symbols (deduplicated, uppercase)

        Raises:
            ValueError: If index=CUSTOM but custom_tickers not provided

        Process:
            1. Validate configuration
            2. Fetch ticker list from appropriate source
            3. Deduplicate (important for COMBINED_SP)
            4. Apply limit if specified
            5. Log statistics

        Performance:
            - Uses 24-hour cache for financial data (downstream)
            - Index lists fetched fresh each time (lightweight operation)
            - ThreadPoolExecutor used for parallel data fetching (downstream)
        """
        logger.info(f"Fetching watchlist tickers for index: {self.index.value}")

        # Validate custom ticker configuration
        if self.index == WatchlistIndex.CUSTOM:
            if not self.custom_tickers:
                raise ValueError(
                    "custom_tickers must be provided when index=CUSTOM"
                )
            tickers = self.custom_tickers
            logger.info(f"Using custom ticker list with {len(tickers)} tickers")

        # Fetch from appropriate index
        elif self.index == WatchlistIndex.SP500:
            tickers = get_sp500_tickers()
            logger.info(f"Fetched {len(tickers)} tickers from S&P 500")

        elif self.index == WatchlistIndex.SP400:
            tickers = get_sp400_tickers()
            logger.info(f"Fetched {len(tickers)} tickers from S&P MidCap 400")

        elif self.index == WatchlistIndex.SP600:
            tickers = get_sp600_tickers()
            logger.info(f"Fetched {len(tickers)} tickers from S&P SmallCap 600")

        elif self.index == WatchlistIndex.NASDAQ100:
            tickers = get_nasdaq100_tickers()
            logger.info(f"Fetched {len(tickers)} tickers from NASDAQ-100")

        elif self.index == WatchlistIndex.COMBINED_SP:
            # Combine all three S&P indexes
            sp500 = get_sp500_tickers()
            sp400 = get_sp400_tickers()
            sp600 = get_sp600_tickers()

            # Deduplicate using set (some tickers may appear in multiple indexes)
            tickers_set: Set[str] = set(sp500) | set(sp400) | set(sp600)
            tickers = list(tickers_set)

            logger.info(
                f"Combined S&P 1500: "
                f"SP500={len(sp500)}, SP400={len(sp400)}, SP600={len(sp600)}, "
                f"Total (deduplicated)={len(tickers)}"
            )

        else:
            # Should never reach here due to enum validation
            raise ValueError(f"Unknown index type: {self.index}")

        # Normalize tickers (uppercase, strip whitespace)
        tickers = [ticker.strip().upper() for ticker in tickers if ticker]

        # Remove duplicates (in case source data has duplicates)
        tickers = list(dict.fromkeys(tickers))  # Preserves order, removes duplicates

        # Apply limit if specified
        if self.limit:
            original_count = len(tickers)
            tickers = tickers[:self.limit]
            logger.info(
                f"Applied limit: {original_count} → {len(tickers)} tickers"
            )

        # Warn if no tickers found
        if not tickers:
            logger.warning(
                f"No tickers found for index {self.index.value}. "
                "Check internet connection or data source."
            )

        return tickers

    def get_ticker_count(self) -> int:
        """Get expected number of tickers (for progress bars, etc.)

        Returns:
            Expected number of tickers (before limit applied)
        """
        return len(self.get_tickers())

    def __str__(self) -> str:
        """Human-readable string representation"""
        if self.index == WatchlistIndex.CUSTOM:
            ticker_preview = (
                f"{len(self.custom_tickers or [])} tickers: "
                f"{', '.join((self.custom_tickers or [])[:5])}"
                f"{'...' if len(self.custom_tickers or []) > 5 else ''}"
            )
            return f"WatchlistConfig(index=CUSTOM, {ticker_preview})"
        else:
            limit_str = f", limit={self.limit}" if self.limit else ""
            return f"WatchlistConfig(index={self.index.value}{limit_str})"


# Default configurations for common use cases
DEFAULT_DAILY_CONFIG = WatchlistConfig(index=WatchlistIndex.SP500, limit=50)
DEFAULT_WEEKLY_CONFIG = WatchlistConfig(index=WatchlistIndex.SP500)
DEFAULT_MONTHLY_CONFIG = WatchlistConfig(index=WatchlistIndex.COMBINED_SP)


def get_default_watchlist_config(frequency: str = "weekly") -> WatchlistConfig:
    """Get default watchlist configuration for common frequencies

    Args:
        frequency: One of "daily", "weekly", "monthly"

    Returns:
        WatchlistConfig appropriate for the frequency

    Raises:
        ValueError: If frequency not recognized
    """
    frequency = frequency.lower()

    if frequency == "daily":
        return DEFAULT_DAILY_CONFIG
    elif frequency == "weekly":
        return DEFAULT_WEEKLY_CONFIG
    elif frequency == "monthly":
        return DEFAULT_MONTHLY_CONFIG
    else:
        raise ValueError(
            f"Unknown frequency: {frequency}. "
            "Valid options: 'daily', 'weekly', 'monthly'"
        )
