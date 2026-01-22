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
    get_nasdaq100_tickers,
    get_russell3000_tickers,
    get_russell1000_tickers,
    get_russell2000_tickers
)

logger = logging.getLogger(__name__)


class WatchlistIndex(Enum):
    """Supported watchlist indexes for screening

    Attributes:
        SP500: S&P 500 (large cap ≥$50B, ~500 tickers)
        SP400: S&P MidCap 400 (mid cap $2B-$50B, ~400 tickers)
        SP600: S&P SmallCap 600 (small cap $500M-$2B, ~600 tickers)
        NASDAQ100: NASDAQ-100 (tech-focused large cap, ~100 tickers)
        RUSSELL1000: Russell 1000 approximation (~900 tickers)
        RUSSELL2000: S&P 600 as Russell 2000 approximation (~600 tickers)
        RUSSELL3000: Russell 3000 approximation (~1500 tickers)
        COMBINED_SP: S&P Composite 1500 (SP500 + SP400 + SP600, ~1500 tickers)
        MULTI: Multiple indices combined (custom combination)
        CUSTOM: Custom ticker list provided by user

    Market Cap Tiers:
        - Large Cap: ≥$50B (dominates SP500, NASDAQ100, Russell 1000)
        - Mid Cap: $2B-$50B (dominates SP400, Russell 1000)
        - Small Cap: $500M-$2B (dominates SP600, Russell 2000)
        - Micro Cap: <$500M (not included in major indexes)

    Use Cases:
        - Daily screening: SP500 with limit=50 (2-5 min, uses cache)
        - Weekly screening: SP500 full (12-17 min, refresh data)
        - Monthly screening: COMBINED_SP (45-60 min, find small cap opportunities)
        - Custom combination: MULTI with sp500,sp400,sp600
        - Tech focus: NASDAQ100 (3-5 min, tech sector analysis)
        - Large/Mid cap focus: RUSSELL1000 (30-40 min, covers top 1000)
        - Small cap focus: RUSSELL2000 (60-80 min, pure small cap)
        - Custom screening: CUSTOM with hand-picked tickers
    """
    SP500 = "sp500"
    SP400 = "sp400"
    SP600 = "sp600"
    NASDAQ100 = "nasdaq100"
    RUSSELL1000 = "russell1000"
    RUSSELL2000 = "russell2000"
    RUSSELL3000 = "russell3000"
    COMBINED_SP = "combined_sp"
    MULTI = "multi"
    CUSTOM = "custom"


@dataclass
class WatchlistConfig:
    """Configuration for watchlist screening

    Attributes:
        index: Which index to screen (WatchlistIndex enum)
        custom_tickers: List of tickers (only used if index=CUSTOM)
        limit: Optional limit for number of tickers (for performance)
        multi_indices: List of indices to combine (only used if index=MULTI)

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

        # Screen multiple indices (e.g., SP500 + SP400 + SP600)
        # Note: Use the string "multi" as index and provide multi_indices list
        config = WatchlistConfig(
            index=WatchlistIndex["multi"],
            multi_indices=[WatchlistIndex.SP500, WatchlistIndex.SP400, WatchlistIndex.SP600]
        )

    Validation:
        - If index=CUSTOM, custom_tickers must be provided
        - If index=MULTI, multi_indices must be provided with at least 2 indices
        - If limit is set, it applies AFTER deduplication for COMBINED_SP/MULTI
        - Empty ticker lists will log warning but not raise error
    """
    index: WatchlistIndex
    custom_tickers: Optional[List[str]] = None
    limit: Optional[int] = None
    multi_indices: Optional[List[WatchlistIndex]] = None

    def _get_tickers_for_index(self, idx: WatchlistIndex) -> List[str]:
        """Get tickers for a single index"""
        if idx == WatchlistIndex.SP500:
            return get_sp500_tickers()
        elif idx == WatchlistIndex.SP400:
            return get_sp400_tickers()
        elif idx == WatchlistIndex.SP600:
            return get_sp600_tickers()
        elif idx == WatchlistIndex.NASDAQ100:
            return get_nasdaq100_tickers()
        elif idx == WatchlistIndex.RUSSELL1000:
            return get_russell1000_tickers()
        elif idx == WatchlistIndex.RUSSELL2000:
            return get_russell2000_tickers()
        elif idx == WatchlistIndex.RUSSELL3000:
            return get_russell3000_tickers()
        elif idx == WatchlistIndex.COMBINED_SP:
            sp500 = get_sp500_tickers()
            sp400 = get_sp400_tickers()
            sp600 = get_sp600_tickers()
            return list(set(sp500) | set(sp400) | set(sp600))
        elif idx == WatchlistIndex.CUSTOM:
            return self.custom_tickers or []
        else:
            return []

    def get_tickers(self) -> List[str]:
        """Get ticker list based on configuration

        Returns:
            List of ticker symbols (deduplicated, uppercase)

        Raises:
            ValueError: If index=CUSTOM but custom_tickers not provided
            ValueError: If index=MULTI but multi_indices not provided

        Process:
            1. Validate configuration
            2. Fetch ticker list from appropriate source(s)
            3. Deduplicate (important for COMBINED_SP/MULTI)
            4. Apply limit if specified
            5. Log statistics

        Performance:
            - Uses 24-hour cache for financial data (downstream)
            - Index lists fetched fresh each time (lightweight operation)
            - ThreadPoolExecutor used for parallel data fetching (downstream)
        """
        logger.info(f"Fetching watchlist tickers for index: {self.index.value}")

        # Validate and get tickers based on index type
        if self.index == WatchlistIndex.CUSTOM:
            if not self.custom_tickers:
                raise ValueError(
                    "custom_tickers must be provided when index=CUSTOM"
                )
            tickers = self.custom_tickers
            logger.info(f"Using custom ticker list with {len(tickers)} tickers")

        elif self.index == WatchlistIndex.MULTI:
            if not self.multi_indices or len(self.multi_indices) < 2:
                raise ValueError(
                    "multi_indices must be provided with at least 2 indices when index=MULTI"
                )
            index_names = [idx.value for idx in self.multi_indices]
            logger.info(f"Combining {len(self.multi_indices)} indices: {index_names}")

            all_tickers: Set[str] = set()
            for idx in self.multi_indices:
                idx_tickers = self._get_tickers_for_index(idx)
                all_tickers.update(idx_tickers)
                logger.info(f"  {idx.value}: {len(idx_tickers)} tickers")

            tickers = list(all_tickers)
            logger.info(f"Combined total (deduplicated): {len(tickers)} tickers")

        elif self.index == WatchlistIndex.COMBINED_SP:
            sp500 = get_sp500_tickers()
            sp400 = get_sp400_tickers()
            sp600 = get_sp600_tickers()

            tickers_set: Set[str] = set(sp500) | set(sp400) | set(sp600)
            tickers = list(tickers_set)

            logger.info(
                f"Combined S&P 1500: "
                f"SP500={len(sp500)}, SP400={len(sp400)}, SP600={len(sp600)}, "
                f"Total (deduplicated)={len(tickers)}"
            )

        elif self.index in [WatchlistIndex.SP500, WatchlistIndex.SP400, WatchlistIndex.SP600,
                           WatchlistIndex.NASDAQ100, WatchlistIndex.RUSSELL1000,
                           WatchlistIndex.RUSSELL2000, WatchlistIndex.RUSSELL3000]:
            tickers = self._get_tickers_for_index(self.index)
            logger.info(f"Fetched {len(tickers)} tickers from {self.index.value}")

        else:
            raise ValueError(f"Unknown index type: {self.index}")

        # Normalize tickers (uppercase, strip whitespace)
        tickers = [ticker.strip().upper() for ticker in tickers if ticker]

        # Remove duplicates (in case source data has duplicates)
        tickers = list(dict.fromkeys(tickers))

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
