"""
FMP Data Fetcher

Fetches historical financial data from Financial Modeling Prep (FMP) API.
OPTIMIZED to use only 2 API endpoints per stock (60% reduction from original 5).

Endpoints used:
1. /api/v3/ratios - 10 years of ROE, margins, safety metrics, growth ratios
2. /api/v4/score - Pre-calculated Piotroski F-Score + Altman Z-Score
"""

import requests
from typing import Dict, Optional
import logging
from .fmp_cache_tracker import FMPCacheTracker
from .fmp_config import get_api_calls_needed, get_years_of_data, get_market_cap_tier, MarketCapTier, CACHE_EXPIRY_BY_ENDPOINT

logger = logging.getLogger(__name__)


# List of known premium-only symbols on FMP FREE tier
PREMIUM_ONLY_SYMBOLS = {
    'FISV',  # Fiserv - confirmed premium-only
    # Add other premium symbols as discovered
}

def is_premium_symbol(ticker: str) -> bool:
    """
    Check if a symbol requires premium FMP subscription.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        True if symbol requires premium subscription
    """
    return ticker.upper() in PREMIUM_ONLY_SYMBOLS

# Legacy function - use get_years_of_data() from fmp_config instead
def get_fmp_limit_by_market_cap(market_cap: float) -> int:
    """
    DEPRECATED: Use get_years_of_data() from fmp_config instead.
    This function maintained for backward compatibility.
    """
    return get_years_of_data(market_cap)


class FMPDataFetcher:
    """
    Fetches historical financial data from Financial Modeling Prep API.

    OPTIMIZED APPROACH:
    - Only 2 API calls per stock (60% reduction)
    - FREE tier: 250 calls/day = 125 stocks/day
    - Uses FMPCacheTracker to manage limits
    - Market cap aware (skip small-caps to save calls)
    """

    def __init__(self, api_key: str, cache_tracker: FMPCacheTracker):
        """
        Initialize FMP data fetcher.

        Args:
            api_key: FMP API key (get free key at financialmodelingprep.com)
            cache_tracker: FMPCacheTracker instance for rate limiting
        """
        self.api_key = api_key
        self.base_url = "https://financialmodelingprep.com/stable"
        self.cache_tracker = cache_tracker

    def fetch_historical_financials(
        self,
        ticker: str,
        market_cap: Optional[float] = None,
        years: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict:
        """
        Fetch historical financial data with OPTIMIZED 2-endpoint approach.

        Endpoints:
        1. /ratios - ROE history, margins, safety metrics (10 years)
        2. /score - Pre-calculated Piotroski + Altman Z-Score

        Args:
            ticker: Stock ticker symbol
            market_cap: Market cap in dollars (for tiered fetching)
            years: Number of years to fetch (overrides market cap logic)
            force_refresh: Force refresh even if cached

        Returns:
            Dict with:
                - ratios: List of annual financial ratios (10 years)
                - score: Pre-calculated Piotroski + Altman Z-Score
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached = self.cache_tracker.get_cached_data(ticker)
            if cached:
                logger.debug(f"Using cached FMP data for {ticker}")
                return cached

        # Check if this is a premium-only symbol first
        if is_premium_symbol(ticker):
            logger.warning(
                f"Skipping FMP for {ticker} (premium-only symbol), "
                "using yfinance only"
            )
            return {}  # Skip FMP entirely for premium symbols

        # Check if we can fetch today
        if not self.cache_tracker.can_fetch(ticker):
            logger.warning(
                f"Daily limit reached or {ticker} data is fresh, using cache"
            )
            return self.cache_tracker.get_cached_data(ticker) or {}

        # Determine years to fetch (market cap tiering)
        if years is None and market_cap is not None:
            years = get_fmp_limit_by_market_cap(market_cap)
            if years == 0:
                logger.info(
                    f"Skipping FMP for {ticker} (small-cap: ${market_cap:,.0f}), "
                    "using yfinance only"
                )
                return {}  # Skip FMP entirely for small-caps
        elif years is None:
            years = 10  # Default to full historical

        logger.info(f"Fetching {years} years of FMP data for {ticker}")

        # ENHANCED: Up to 4 API calls for complete growth data
        results = {}
        calls_used = 0

        # Call 1: Get N years of financial ratios (ROE, margins, safety, growth)
        ratios_data = self._fetch_ratios(ticker, years)
        if ratios_data is not None:
            results['ratios'] = ratios_data
            calls_used += 1

        # Call 2: Get pre-calculated financial scores
        score_data = self._fetch_score(ticker)
        if score_data is not None:
            results['score'] = score_data
            calls_used += 1

        # Call 3: Get income statement for revenue history (growth metrics)
        if market_cap and market_cap >= 10_000_000_000:  # Only for large caps (need growth data)
            income_data = self._fetch_income_statement(ticker, years)
            if income_data is not None:
                results['income'] = income_data
                calls_used += 1

        # Call 4: Get balance sheet for asset history (growth metrics)
        if market_cap and market_cap >= 10_000_000_000:  # Only for large caps (need growth data)
            balance_data = self._fetch_balance_sheet(ticker, years)
            if balance_data is not None:
                results['balance'] = balance_data
                calls_used += 1
        
        # Call 5: Get cash flow statement for earnings quality (priority for mega-caps)
        if market_cap and market_cap >= 500_000_000_000:  # Only for mega-caps (earnings quality)
            cash_flow_data = self._fetch_cash_flow(ticker, years)
            if cash_flow_data is not None:
                results['cash_flow'] = cash_flow_data
                calls_used += 1

        # Save to cache
        if calls_used > 0:
            self.cache_tracker.record_fetch(ticker, results, calls_used)
        else:
            logger.error(f"Failed to fetch any FMP data for {ticker}")

        return results

    def _fetch_ratios(self, ticker: str, years: int) -> Optional[list]:
        """
        Fetch financial ratios endpoint.

        Returns 40+ ratios over N years:
        - returnOnEquity (ROE history)
        - grossProfitRatio, netProfitMargin (margin trends)
        - currentRatio, debtToEquity (safety metrics)
        - revenueGrowth, ebitGrowth (growth metrics)

        Args:
            ticker: Stock ticker
            years: Number of years to fetch

        Returns:
            List of ratio dicts (one per year) or None on error
        """
        url = f"{self.base_url}/ratios?symbol={ticker}&limit={years}&apikey={self.api_key}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                logger.debug(
                    f"Fetched {len(data)} years of ratios for {ticker} "
                    f"(requested {years})"
                )
                return data
            elif response.status_code == 401:
                logger.error("FMP API key invalid or expired")
                return None
            elif response.status_code == 429:
                logger.error("FMP rate limit exceeded")
                return None
            elif response.status_code == 402:
                logger.warning(f"FMP Premium symbol {ticker} not available in FREE tier - requires paid subscription")
                return None
            else:
                logger.warning(
                    f"FMP API error for {ticker}/ratios: "
                    f"{response.status_code} - {response.text[:100]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {ticker}/ratios")
            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker}/ratios: {e}")
            return None

    def _fetch_score(self, ticker: str) -> Optional[Dict]:
        """
        Fetch financial score endpoint (Piotroski + Altman Z-Score).

        Returns pre-calculated scores:
        - piotroskiScore: 0-9 (9-component earnings quality score)
        - altmanZScore: Bankruptcy prediction metric
        - Plus underlying financial data used in calculation

        Args:
            ticker: Stock ticker

        Returns:
            Score dict or None on error
        """
        url = f"{self.base_url}/financial-scores?symbol={ticker}&apikey={self.api_key}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Response can be list or dict
                if isinstance(data, list) and len(data) > 0:
                    score_data = data[0]
                elif isinstance(data, dict):
                    score_data = data
                else:
                    logger.warning(f"Unexpected score response format for {ticker}")
                    return None

                logger.debug(
                    f"Fetched scores for {ticker}: "
                    f"Piotroski={score_data.get('piotroskiScore')}, "
                    f"Altman={score_data.get('altmanZScore')}"
                )
                return score_data

            elif response.status_code == 401:
                logger.error("FMP API key invalid or expired")
                return None
            elif response.status_code == 429:
                logger.error("FMP rate limit exceeded")
                return None
            elif response.status_code == 402:
                logger.warning(f"FMP Premium symbol {ticker} not available in FREE tier - requires paid subscription")
                return None
            else:
                logger.warning(
                    f"FMP API error for {ticker}/score: "
                    f"{response.status_code} - {response.text[:100]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {ticker}/score")
            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker}/score: {e}")
            return None

    def _fetch_income_statement(self, ticker: str, years: int) -> Optional[list]:
        """
        Fetch income statement endpoint for revenue history.

        Returns revenue and related metrics over N years:
        - revenue: Total revenue history
        - netIncome: Net income history
        - grossProfit: Gross profit history

        Args:
            ticker: Stock ticker
            years: Number of years to fetch

        Returns:
            List of income statement data or None on error
        """
        url = f"{self.base_url}/income-statement?symbol={ticker}&limit={years}&apikey={self.api_key}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    logger.debug(f"Fetched {len(data)} years of income data for {ticker}")
                    return data
                else:
                    logger.warning(f"No income data found for {ticker}")
                    return None

            elif response.status_code == 429:
                logger.error("FMP rate limit exceeded")
                return None
            elif response.status_code == 402:
                logger.warning(f"FMP Premium symbol {ticker} not available in FREE tier - requires paid subscription")
                return None
            else:
                logger.warning(
                    f"FMP API error for {ticker}/income-statement: "
                    f"{response.status_code} - {response.text[:100]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {ticker}/income-statement")
            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker}/income-statement: {e}")
            return None

    def _fetch_balance_sheet(self, ticker: str, years: int) -> Optional[list]:
        """
        Fetch balance sheet endpoint for asset history.

        Returns assets and related metrics over N years:
        - totalAssets: Total assets history
        - totalLiabilities: Total liabilities history
        - shareholdersEquity: Equity history

        Args:
            ticker: Stock ticker
            years: Number of years to fetch

        Returns:
            List of balance sheet data or None on error
        """
        url = f"{self.base_url}/balance-sheet-statement?symbol={ticker}&limit={years}&apikey={self.api_key}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    logger.debug(f"Fetched {len(data)} years of balance data for {ticker}")
                    return data
                else:
                    logger.warning(f"No balance sheet data found for {ticker}")
                    return None

            elif response.status_code == 429:
                logger.error("FMP rate limit exceeded")
                return None
            elif response.status_code == 402:
                logger.warning(f"FMP Premium symbol {ticker} not available in FREE tier - requires paid subscription")
                return None
            else:
                logger.warning(
                    f"FMP API error for {ticker}/balance-sheet-statement: "
                    f"{response.status_code} - {response.text[:100]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {ticker}/balance-sheet-statement")
            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker}/balance-sheet: {e}")
            return None

    def _fetch_cash_flow(self, ticker: str, years: int) -> Optional[list]:
        """
        Fetch cash flow statement endpoint for earnings quality.

        Returns operating cash flow and related metrics over N years:
        - operatingCashFlow: Operating cash flow history
        - netIncome: Net income history
        - capitalExpenditure: CapEx history

        Args:
            ticker: Stock ticker
            years: Number of years to fetch

        Returns:
            List of cash flow data or None on error
        """
        url = f"{self.base_url}/cash-flow-statement?symbol={ticker}&limit={years}&apikey={self.api_key}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    logger.debug(f"Fetched {len(data)} years of cash flow data for {ticker}")
                    return data
                else:
                    logger.warning(f"No cash flow data found for {ticker}")
                    return None

            elif response.status_code == 429:
                logger.error(f"FMP rate limit exceeded for {ticker}/cash-flow")
                return None
            else:
                logger.warning(
                    f"FMP API error for {ticker}/cash-flow: "
                    f"{response.status_code} - {response.text[:100]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {ticker}/cash-flow")
            return None
        except Exception as e:
            logger.error(f"Error fetching {ticker}/cash-flow: {e}")
            return None
