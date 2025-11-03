"""
Financial Data Fetcher Module
Fetches fundamental financial data from yfinance for quality analysis
"""

import yfinance as yf
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import pickle
import os
from dataclasses import dataclass, asdict
import json
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FinancialData:
    """Structured financial data for quality analysis"""
    ticker: str
    # Basic info
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[float] = None
    pe_ratio: Optional[float] = None

    # Income statement
    revenue: Optional[float] = None
    cogs: Optional[float] = None  # Cost of goods sold
    sga: Optional[float] = None  # Selling, general & administrative
    operating_income: Optional[float] = None
    net_income: Optional[float] = None

    # Balance sheet
    total_assets: Optional[float] = None
    shareholder_equity: Optional[float] = None
    total_debt: Optional[float] = None

    # Cash flow
    free_cash_flow: Optional[float] = None

    # Calculated metrics
    nopat: Optional[float] = None  # Net operating profit after tax

    # Metadata
    fetch_time: Optional[str] = None
    data_quality: str = "complete"  # complete, partial, insufficient

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)

    def validate(self) -> bool:
        """Check if data is sufficient for quality analysis"""
        required = [
            self.revenue, self.cogs, self.total_assets,
            self.net_income, self.shareholder_equity, self.free_cash_flow
        ]
        return all(x is not None for x in required)


class FinancialDataCache:
    """Simple file-based cache for financial data"""

    def __init__(self, cache_file: str = "financial_cache.pkl", cache_hours: int = 24):
        self.cache_file = cache_file
        self.cache_hours = cache_hours
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    logger.debug(f"Loaded financial cache with {len(cache)} entries")
                    return cache
            except Exception as e:
                logger.warning(f"Failed to load financial cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            logger.debug(f"Saved financial cache with {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save financial cache: {e}")

    def get(self, ticker: str) -> Optional[FinancialData]:
        """Get cached financial data if available and fresh"""
        if ticker in self.cache:
            data, timestamp = self.cache[ticker]
            # Financial data changes slowly - 24 hour cache
            if datetime.now() - timestamp < timedelta(hours=self.cache_hours):
                logger.debug(f"Financial cache HIT for {ticker}")
                return data
            else:
                logger.debug(f"Financial cache EXPIRED for {ticker}")
                del self.cache[ticker]
        return None

    def set(self, ticker: str, data: FinancialData):
        """Cache financial data"""
        self.cache[ticker] = (data, datetime.now())
        self._save_cache()
        logger.debug(f"Cached financial data for {ticker}")

    def clear(self):
        """Clear entire cache"""
        self.cache = {}
        self._save_cache()
        logger.info("Financial cache cleared")


class FinancialDataFetcher:
    """
    Fetch fundamental financial data from yfinance

    Features:
    - Comprehensive fundamental data (income, balance sheet, cash flow)
    - 24-hour caching (financials don't change daily)
    - Data validation and quality checks
    - Graceful error handling
    - Free and unlimited (yfinance)
    """

    def __init__(self, enable_cache: bool = True):
        """
        Initialize financial data fetcher

        Args:
            enable_cache: Enable 24-hour caching (default: True)
        """
        self.cache = FinancialDataCache() if enable_cache else None
        logger.info("FinancialDataFetcher initialized with yfinance")

    def fetch_financial_data(self, ticker: str) -> Optional[FinancialData]:
        """
        Fetch financial data for a ticker

        Args:
            ticker: Stock ticker symbol

        Returns:
            FinancialData object or None if fetch failed
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(ticker)
            if cached is not None:
                return cached

        try:
            logger.info(f"Fetching financial data for {ticker}")

            # Create yfinance Ticker object
            stock = yf.Ticker(ticker)

            # Get basic info
            info = stock.info

            # Get financial statements
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cashflow = stock.cashflow

            # Extract data (most recent period is first column)
            data = FinancialData(ticker=ticker)

            # Basic info
            data.market_cap = info.get('marketCap')
            data.sector = info.get('sector')
            data.industry = info.get('industry')
            data.current_price = info.get('currentPrice')
            data.pe_ratio = info.get('trailingPE')

            # Income statement
            if not financials.empty:
                try:
                    data.revenue = self._safe_get(financials, 'Total Revenue', 0)
                    data.cogs = self._safe_get(financials, 'Cost Of Revenue', 0)
                    data.operating_income = self._safe_get(financials, 'Operating Income', 0)
                    data.net_income = self._safe_get(financials, 'Net Income', 0)

                    # Calculate SG&A (Operating Expense - COGS)
                    operating_expense = self._safe_get(financials, 'Operating Expense', 0)
                    if operating_expense and data.cogs:
                        data.sga = operating_expense - data.cogs
                except Exception as e:
                    logger.warning(f"Error extracting income statement for {ticker}: {e}")

            # Balance sheet
            if not balance_sheet.empty:
                try:
                    data.total_assets = self._safe_get(balance_sheet, 'Total Assets', 0)
                    data.shareholder_equity = self._safe_get(balance_sheet, 'Stockholders Equity', 0)

                    # Try to get total debt
                    total_debt = self._safe_get(balance_sheet, 'Total Debt', 0)
                    if total_debt is None:
                        # Try alternative: Long Term Debt + Current Debt
                        long_term_debt = self._safe_get(balance_sheet, 'Long Term Debt', 0) or 0
                        current_debt = self._safe_get(balance_sheet, 'Current Debt', 0) or 0
                        total_debt = long_term_debt + current_debt
                    data.total_debt = total_debt
                except Exception as e:
                    logger.warning(f"Error extracting balance sheet for {ticker}: {e}")

            # Cash flow
            if not cashflow.empty:
                try:
                    data.free_cash_flow = self._safe_get(cashflow, 'Free Cash Flow', 0)
                except Exception as e:
                    logger.warning(f"Error extracting cash flow for {ticker}: {e}")

            # Calculate NOPAT (approximate: operating income * (1 - tax rate))
            # Use 21% federal corporate tax rate as approximation
            if data.operating_income:
                data.nopat = data.operating_income * 0.79

            # Metadata
            data.fetch_time = datetime.now().isoformat()

            # Data quality assessment
            if data.validate():
                data.data_quality = "complete"
                logger.info(f"Successfully fetched complete financial data for {ticker}")
            elif any([data.revenue, data.total_assets, data.net_income]):
                data.data_quality = "partial"
                logger.warning(f"Partial financial data for {ticker}")
            else:
                data.data_quality = "insufficient"
                logger.warning(f"Insufficient financial data for {ticker}")

            # Cache results
            if self.cache:
                self.cache.set(ticker, data)

            return data

        except Exception as e:
            logger.error(f"Failed to fetch financial data for {ticker}: {e}")
            return None

    def _safe_get(self, df: pd.DataFrame, key: str, col: int = 0) -> Optional[float]:
        """Safely get value from DataFrame"""
        try:
            if key in df.index:
                value = df.loc[key].iloc[col]
                # Validate value is reasonable (not NaN, not inf, not negative for certain fields)
                if pd.notna(value) and not pd.isinf(value):
                    return float(value)
        except Exception as e:
            logger.debug(f"Failed to get {key}: {e}")
        return None

    def batch_fetch(self, tickers: List[str]) -> Dict[str, Optional[FinancialData]]:
        """
        Fetch financial data for multiple tickers

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> FinancialData (or None if failed)
        """
        results = {}

        for i, ticker in enumerate(tickers):
            logger.info(f"Fetching financials {i+1}/{len(tickers)}: {ticker}")
            data = self.fetch_financial_data(ticker)
            results[ticker] = data

        success_count = sum(1 for v in results.values() if v and v.data_quality != "insufficient")
        logger.info(f"Batch fetch complete: {success_count}/{len(tickers)} tickers with usable data")

        return results

    def export_to_json(self, ticker: str, output_file: str):
        """
        Fetch financial data and export to JSON

        Args:
            ticker: Stock ticker symbol
            output_file: Output JSON file path
        """
        data = self.fetch_financial_data(ticker)

        if data:
            with open(output_file, 'w') as f:
                json.dump(data.to_dict(), f, indent=2)
            logger.info(f"Exported financial data for {ticker} to {output_file}")
        else:
            logger.error(f"No data to export for {ticker}")

    def get_earnings_dates(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        Get upcoming and historical earnings dates

        Args:
            ticker: Stock ticker symbol

        Returns:
            DataFrame with earnings dates or None
        """
        try:
            stock = yf.Ticker(ticker)
            earnings_dates = stock.earnings_dates
            logger.info(f"Fetched earnings dates for {ticker}")
            return earnings_dates
        except Exception as e:
            logger.error(f"Failed to fetch earnings dates for {ticker}: {e}")
            return None

    def get_analyst_info(self, ticker: str) -> Optional[Dict]:
        """
        Get analyst recommendations and target prices

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with analyst info or None
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            analyst_info = {
                'target_mean_price': info.get('targetMeanPrice'),
                'target_high_price': info.get('targetHighPrice'),
                'target_low_price': info.get('targetLowPrice'),
                'recommendation_mean': info.get('recommendationMean'),  # 1=Strong Buy, 5=Sell
                'recommendation_key': info.get('recommendationKey'),
                'number_of_analyst_opinions': info.get('numberOfAnalystOpinions')
            }

            logger.info(f"Fetched analyst info for {ticker}")
            return analyst_info

        except Exception as e:
            logger.error(f"Failed to fetch analyst info for {ticker}: {e}")
            return None


def get_sp500_tickers() -> List[str]:
    """
    Get S&P 500 ticker list from Wikipedia

    Returns:
        List of ticker symbols
    """
    try:
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
    # Initialize fetcher
    fetcher = FinancialDataFetcher()

    # Example 1: Fetch data for a single ticker
    print("\n" + "="*60)
    print("Example 1: Fetch financial data for NVDA")
    print("="*60)
    nvda_data = fetcher.fetch_financial_data("NVDA")
    if nvda_data:
        print(f"Ticker: {nvda_data.ticker}")
        print(f"Market Cap: ${nvda_data.market_cap:,.0f}" if nvda_data.market_cap else "N/A")
        print(f"Sector: {nvda_data.sector}")
        print(f"Revenue: ${nvda_data.revenue:,.0f}" if nvda_data.revenue else "N/A")
        print(f"Net Income: ${nvda_data.net_income:,.0f}" if nvda_data.net_income else "N/A")
        print(f"Total Assets: ${nvda_data.total_assets:,.0f}" if nvda_data.total_assets else "N/A")
        print(f"FCF: ${nvda_data.free_cash_flow:,.0f}" if nvda_data.free_cash_flow else "N/A")
        print(f"Data Quality: {nvda_data.data_quality}")

    # Example 2: Batch fetch
    print("\n" + "="*60)
    print("Example 2: Batch fetch for multiple tickers")
    print("="*60)
    tickers = ["AAPL", "MSFT", "GOOGL"]
    batch_results = fetcher.batch_fetch(tickers)
    for ticker, data in batch_results.items():
        if data:
            print(f"  {ticker}: {data.data_quality} data (Market Cap: ${data.market_cap:,.0f})" if data.market_cap else f"  {ticker}: {data.data_quality}")
        else:
            print(f"  {ticker}: FAILED")

    # Example 3: Get earnings dates
    print("\n" + "="*60)
    print("Example 3: Get earnings dates for AAPL")
    print("="*60)
    earnings = fetcher.get_earnings_dates("AAPL")
    if earnings is not None and not earnings.empty:
        print(earnings.head())

    # Example 4: Get analyst info
    print("\n" + "="*60)
    print("Example 4: Get analyst info for AAPL")
    print("="*60)
    analyst_info = fetcher.get_analyst_info("AAPL")
    if analyst_info:
        print(f"Target Mean Price: ${analyst_info.get('target_mean_price')}")
        print(f"Recommendation: {analyst_info.get('recommendation_key')}")
        print(f"Number of Analysts: {analyst_info.get('number_of_analyst_opinions')}")

    # Example 5: Export to JSON
    print("\n" + "="*60)
    print("Example 5: Export to JSON")
    print("="*60)
    fetcher.export_to_json("AAPL", "financials_aapl.json")
    print("Exported to financials_aapl.json")
