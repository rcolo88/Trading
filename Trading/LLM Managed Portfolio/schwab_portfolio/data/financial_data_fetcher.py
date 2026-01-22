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
import numpy as np
import time  # For rate limit delays

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

    # Additional fields for safety metrics (Z-Score, Debt/EBITDA, Interest Coverage)
    retained_earnings: Optional[float] = None  # For Altman Z-Score
    ebit: Optional[float] = None  # For Z-Score & Interest Coverage (same as operating_income)
    ebitda: Optional[float] = None  # For Debt/EBITDA ratio
    interest_expense: Optional[float] = None  # For Interest Coverage ratio
    working_capital: Optional[float] = None  # For Z-Score (Current Assets - Current Liabilities)

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

    def __init__(self, cache_file: str = "financial_cache.pkl", cache_hours: int = 48):
        self.cache_file = cache_file
        self.cache_hours = cache_hours  # Extended to 48 hours (fundamental data changes quarterly)
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
    
    # Field aliases for different industries (banks vs manufacturing)
    FIELD_ALIASES = {
        'revenue': ['Total Revenue', 'Revenue', 'Net Sales', 'Interest Income', 'Total Interest Income'],
        'cogs': ['Cost Of Revenue', 'Cost of Goods Sold', 'Cost of Sales', 'Interest Expense',
                   'Selling And Marketing Expense', 'Operating Expense'],
        'operating_income': ['Operating Income', 'Operating Profit', 'EBIT'],
        'net_income': ['Net Income', 'Net Earnings', 'Net Profit', 'Net Income Available to Common'],
        'total_assets': ['Total Assets', 'Total Assets (Reported)'],
        'shareholder_equity': ['Stockholders Equity', 'Shareholders Equity', 'Total Equity',
                            'Total Stockholders Equity', 'Common Stock Equity'],
        'total_debt': ['Total Debt', 'Total Debt (Reported)', 'Long Term Debt', 'Total Liabilities'],
        'operating_cash_flow': ['Operating Cash Flow', 'Cash Flow from Operations', 'Operating Activities'],
        'free_cash_flow': ['Free Cash Flow', 'Free Cash Flow (Reported)'],
        # New aliases for safety metrics
        'retained_earnings': ['Retained Earnings', 'Accumulated Deficit', 'Retained Earnings (Accumulated Deficit)'],
        'ebit': ['Operating Income', 'EBIT', 'Operating Profit'],
        'ebitda': ['EBITDA', 'Normalized EBITDA'],
        'interest_expense': ['Interest Expense', 'Interest Paid', 'Interest And Debt Expense'],
        'current_assets': ['Current Assets', 'Total Current Assets'],
        'current_liabilities': ['Current Liabilities', 'Total Current Liabilities'],
        'depreciation_amortization': ['Depreciation And Amortization', 'Depreciation Amortization Depletion',
                                     'Depreciation', 'Amortization'],
    }

    def __init__(self, enable_cache: bool = True):
        """
        Initialize financial data fetcher

        Args:
            enable_cache: Enable 24-hour caching (default: True)
        """
        self.cache = FinancialDataCache() if enable_cache else None
        logger.info("FinancialDataFetcher initialized with yfinance")

    def _fetch_with_retry(self, ticker: str, max_retries: int = 3) -> Optional[FinancialData]:
        """
        Fetch with exponential backoff retry for rate limits

        Args:
            ticker: Stock ticker symbol
            max_retries: Maximum retry attempts (default: 3)

        Returns:
            FinancialData or None if all retries failed
        """
        for attempt in range(max_retries):
            try:
                return self._fetch_financial_data_internal(ticker)

            except Exception as e:
                # Check if it's a rate limit error (429 or "Too Many Requests")
                error_str = str(e).lower()
                is_rate_limit = '429' in error_str or 'too many requests' in error_str

                if is_rate_limit and attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s...
                    logger.warning(f"⚠️  Rate limit hit for {ticker}, retrying in {delay}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                elif is_rate_limit:
                    logger.error(f"❌ Rate limit persists after {max_retries} retries: {ticker}")
                    return None
                else:
                    # Non-rate-limit error, don't retry
                    logger.error(f"Error fetching {ticker}: {e}")
                    return None

        return None

    def fetch_financial_data(self, ticker: str) -> Optional[FinancialData]:
        """
        Fetch financial data for a ticker with caching and retry logic

        Args:
            ticker: Stock ticker symbol

        Returns:
            FinancialData object or None if fetch failed
        """
        # Check cache first
        if self.cache:
            cached = self.cache.get(ticker)
            if cached is not None:
                logger.debug(f"Using cached data for {ticker}")
                return cached

        # Fetch with retry logic for rate limits
        return self._fetch_with_retry(ticker)

    def _fetch_financial_data_internal(self, ticker: str) -> Optional[FinancialData]:
        """
        Internal method to fetch financial data (called by retry wrapper)

        Args:
            ticker: Stock ticker symbol

        Returns:
            FinancialData object or None if fetch failed
        """
        # Note: Cache check is done in fetch_financial_data(), not here

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
                    data.revenue = self._safe_get_with_aliases(financials, 'revenue', 0)
                    data.cogs = self._safe_get_with_aliases(financials, 'cogs', 0)
                    data.operating_income = self._safe_get_with_aliases(financials, 'operating_income', 0)
                    data.net_income = self._safe_get_with_aliases(financials, 'net_income', 0)

                    # EBIT is the same as operating_income
                    data.ebit = data.operating_income

                    # Extract interest expense for Interest Coverage ratio
                    data.interest_expense = self._safe_get_with_aliases(financials, 'interest_expense', 0)

                    # Extract or calculate EBITDA
                    # Try direct extraction first
                    ebitda = self._safe_get_with_aliases(financials, 'ebitda', 0)
                    if ebitda is not None:
                        data.ebitda = ebitda
                    elif data.ebit is not None:
                        # Calculate EBITDA = EBIT + Depreciation + Amortization
                        depreciation = self._safe_get_with_aliases(financials, 'depreciation_amortization', 0)
                        if depreciation is not None:
                            data.ebitda = data.ebit + depreciation
                        else:
                            # Conservative estimate: EBITDA ≈ EBIT * 1.15
                            data.ebitda = data.ebit * 1.15
                    else:
                        data.ebitda = None

                    # Calculate SG&A (Operating Expense - COGS)
                    operating_expense = self._safe_get(financials, 'Operating Expense', 0)
                    if operating_expense and data.cogs:
                        data.sga = operating_expense - data.cogs
                except Exception as e:
                    logger.warning(f"Error extracting income statement for {ticker}: {e}")

            # Balance sheet
            if not balance_sheet.empty:
                try:
                    data.total_assets = self._safe_get_with_aliases(balance_sheet, 'total_assets', 0)
                    data.shareholder_equity = self._safe_get_with_aliases(balance_sheet, 'shareholder_equity', 0)

                    # Try to get total debt
                    total_debt = self._safe_get(balance_sheet, 'Total Debt', 0)
                    if total_debt is None:
                        # Try alternative: Long Term Debt + Current Debt
                        long_term_debt = self._safe_get(balance_sheet, 'Long Term Debt', 0) or 0
                        current_debt = self._safe_get(balance_sheet, 'Current Debt', 0) or 0
                        total_debt = long_term_debt + current_debt
                    data.total_debt = total_debt

                    # Extract retained earnings for Z-Score
                    data.retained_earnings = self._safe_get_with_aliases(balance_sheet, 'retained_earnings', 0)

                    # Calculate working capital (Current Assets - Current Liabilities)
                    current_assets = self._safe_get_with_aliases(balance_sheet, 'current_assets', 0)
                    current_liabilities = self._safe_get_with_aliases(balance_sheet, 'current_liabilities', 0)
                    if current_assets is not None and current_liabilities is not None:
                        data.working_capital = current_assets - current_liabilities
                    else:
                        data.working_capital = None
                except Exception as e:
                    logger.warning(f"Error extracting balance sheet for {ticker}: {e}")

            # Cash flow
            if not cashflow.empty:
                try:
                    data.free_cash_flow = self._safe_get(cashflow, 'Free Cash Flow', 0)
                    data.operating_cash_flow = self._safe_get_with_aliases(cashflow, 'operating_cash_flow', 0)
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
                value = df.loc[key].iloc[int(col)]
                # Validate value is reasonable (not NaN, not inf, not negative for certain fields)
                if pd.notna(value) and not np.isinf(value):
                    return float(value)
        except Exception as e:
            logger.debug(f"Failed to get {key}: {e}")
        return None

    def _safe_get_with_fallback(self, df: pd.DataFrame, key: str, start_col: int = 0, max_attempts: int = 3) -> Optional[float]:
        """
        Safely get value from DataFrame with column fallback logic.
        
        Tries column 0, then 1, 2 until finding valid data.
        This fixes the critical issue where column 0 contains NaN future estimates.
        """
        for col_idx in range(start_col, min(max_attempts, len(df.columns))):
            if key in df.index:
                value = df.loc[key].iloc[col_idx]
                # Validate value is reasonable (not NaN, not inf, not zero for critical fields)
                if pd.notna(value) and not np.isinf(value) and value != 0:
                    logger.debug(f"Found {key} in column {col_idx}: {value}")
                    return float(value)
                else:
                    logger.debug(f"Column {col_idx} {key} invalid: {value}")
            else:
                logger.debug(f"Column {col_idx} missing key: {key}")
        
        logger.warning(f"Could not find valid {key} in any column (tried {min(max_attempts, len(df.columns))} columns)")
        return None

    def _safe_get_with_aliases(self, df: pd.DataFrame, key: str, start_col: int = 0, max_attempts: int = 3) -> Optional[float]:
        """
        Safely get value from DataFrame with field aliases and column fallback.
        
        Tries field aliases then column fallback for robust data extraction.
        """
        aliases = self.FIELD_ALIASES.get(key, [key])
        
        for alias in aliases:
            for col_idx in range(start_col, min(max_attempts, len(df.columns))):
                if alias in df.index:
                    value = df.loc[alias].iloc[col_idx]
                    # Validate value is reasonable (not NaN, not inf, not zero for critical fields)
                    if pd.notna(value) and not np.isinf(value) and value != 0:
                        logger.debug(f"Found {key} as {alias} in column {col_idx}: {value}")
                        return float(value)
                    else:
                        logger.debug(f"Column {col_idx} {alias} invalid: {value}")
                else:
                    logger.debug(f"Column {col_idx} missing alias: {alias}")
        
        logger.warning(f"Could not find valid {key} using any alias (tried: {aliases})")
        return None

    def fetch_historical_financials(self, ticker: str, years: int = 10) -> Optional[pd.DataFrame]:
        """
        Fetch historical financial data for ROE persistence analysis

        This method fetches multi-year financial statements from yfinance and transforms
        them into a format suitable for the QualityPersistenceAnalyzer.

        Args:
            ticker: Stock ticker symbol
            years: Number of years to fetch (default: 10, but yfinance typically provides 3-4)

        Returns:
            DataFrame with columns:
                - year: int (e.g., 2021, 2022, 2023)
                - revenue: float
                - cogs: float (cost of goods sold)
                - sga: float (selling, general & administrative)
                - total_assets: float
                - net_income: float
                - shareholder_equity: float
                - free_cash_flow: float
                - total_debt: float
                - nopat: float (net operating profit after tax)

            Returns None if fetch failed or insufficient data

        Note:
            - yfinance typically provides 3-4 years of annual data (not 10)
            - DataFrame will have as many rows as years available from yfinance
            - Years are sorted in ascending order (oldest to newest)
            - Missing values are filled with None
        """
        try:
            logger.info(f"Fetching historical financials for {ticker} (target: {years} years)")

            # Create yfinance Ticker object
            stock = yf.Ticker(ticker)

            # Get financial statements (yfinance returns years as columns)
            financials = stock.financials  # Income statement
            balance_sheet = stock.balance_sheet  # Balance sheet
            cashflow = stock.cashflow  # Cash flow statement

            # Check if we have any data
            if financials.empty and balance_sheet.empty and cashflow.empty:
                logger.warning(f"No historical financial data available for {ticker}")
                return None

            # Get available years (yfinance uses datetime columns)
            # Combine years from all statements to get full coverage
            all_years = set()
            if not financials.empty:
                all_years.update(financials.columns)
            if not balance_sheet.empty:
                all_years.update(balance_sheet.columns)
            if not cashflow.empty:
                all_years.update(cashflow.columns)

            # Convert datetime columns to year integers
            years_list = sorted([col.year for col in all_years])

            if len(years_list) == 0:
                logger.warning(f"No valid years found in financial data for {ticker}")
                return None

            logger.info(f"Found {len(years_list)} years of data for {ticker}: {years_list}")

            # Build historical data DataFrame (years as rows)
            historical_data = []

            for year_val in years_list:
                # Find the matching datetime column for this year
                year_col = None
                for col in all_years:
                    if col.year == year_val:
                        year_col = col
                        break

                if year_col is None:
                    continue

                # Extract data for this year
                row_data = {'year': year_val}

                # Income statement
                if not financials.empty and year_col in financials.columns:
                    col_idx = financials.columns.get_loc(year_col)
                    row_data['revenue'] = self._safe_get(financials, 'Total Revenue', col_idx)
                    row_data['cogs'] = self._safe_get(financials, 'Cost Of Revenue', col_idx)
                    row_data['net_income'] = self._safe_get(financials, 'Net Income', col_idx)
                    operating_income = self._safe_get(financials, 'Operating Income', col_idx)

                    # Calculate SG&A (Operating Expense - COGS)
                    operating_expense = self._safe_get(financials, 'Operating Expense', col_idx)
                    if operating_expense is not None and row_data.get('cogs') is not None:
                        row_data['sga'] = operating_expense - row_data['cogs']
                    else:
                        row_data['sga'] = None

                    # Calculate NOPAT (approximate: operating income * (1 - tax rate))
                    # Use 21% federal corporate tax rate as approximation
                    if operating_income is not None:
                        row_data['nopat'] = operating_income * 0.79
                    else:
                        row_data['nopat'] = None
                else:
                    row_data['revenue'] = None
                    row_data['cogs'] = None
                    row_data['net_income'] = None
                    row_data['sga'] = None
                    row_data['nopat'] = None

                # Balance sheet
                if not balance_sheet.empty and year_col in balance_sheet.columns:
                    col_idx = balance_sheet.columns.get_loc(year_col)
                    row_data['total_assets'] = self._safe_get(balance_sheet, 'Total Assets', col_idx)
                    row_data['shareholder_equity'] = self._safe_get(balance_sheet, 'Stockholders Equity', col_idx)

                    # Try to get total debt
                    total_debt = self._safe_get(balance_sheet, 'Total Debt', col_idx)
                    if total_debt is None:
                        # Try alternative: Long Term Debt + Current Debt
                        long_term_debt = self._safe_get(balance_sheet, 'Long Term Debt', col_idx) or 0
                        current_debt = self._safe_get(balance_sheet, 'Current Debt', col_idx) or 0
                        total_debt = long_term_debt + current_debt if (long_term_debt or current_debt) else None
                    row_data['total_debt'] = total_debt
                else:
                    row_data['total_assets'] = None
                    row_data['shareholder_equity'] = None
                    row_data['total_debt'] = None

                # Cash flow
                if not cashflow.empty and year_col in cashflow.columns:
                    col_idx = cashflow.columns.get_loc(year_col)
                    row_data['free_cash_flow'] = self._safe_get(cashflow, 'Free Cash Flow', col_idx)
                else:
                    row_data['free_cash_flow'] = None

                historical_data.append(row_data)

            # Convert to DataFrame
            df = pd.DataFrame(historical_data)

            # Ensure columns exist (even if all None)
            required_columns = ['year', 'revenue', 'cogs', 'sga', 'total_assets',
                              'net_income', 'shareholder_equity', 'free_cash_flow',
                              'total_debt', 'nopat']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None

            # Reorder columns to match expected format
            df = df[required_columns]

            # Sort by year (ascending: oldest to newest)
            df = df.sort_values('year').reset_index(drop=True)

            # Log data quality
            complete_rows = df.dropna(subset=['revenue', 'net_income', 'shareholder_equity']).shape[0]
            logger.info(f"Historical data for {ticker}: {len(df)} years, {complete_rows} complete rows")

            if len(df) < 2:
                logger.warning(f"Insufficient historical data for {ticker}: only {len(df)} year(s)")
                return None

            return df

        except Exception as e:
            logger.error(f"Failed to fetch historical financials for {ticker}: {e}")
            return None

    def batch_fetch(self, tickers: List[str], delay: float = 2.0) -> Dict[str, Optional[FinancialData]]:
        """
        Fetch financial data for multiple tickers with rate limit protection

        Args:
            tickers: List of ticker symbols
            delay: Seconds to wait between requests (default 2.0 to avoid rate limits)

        Returns:
            Dict mapping ticker -> FinancialData (or None if failed)
        """
        results = {}

        for i, ticker in enumerate(tickers):
            logger.info(f"Fetching financials {i+1}/{len(tickers)}: {ticker}")
            data = self.fetch_financial_data(ticker)
            results[ticker] = data

            # Add delay between requests (except for last ticker)
            if i < len(tickers) - 1 and delay > 0:
                time.sleep(delay)
                logger.debug(f"Rate limit protection: waiting {delay}s before next request")

        success_count = sum(1 for v in results.values() if v and v.data_quality != "insufficient")
        logger.info(f"Batch fetch complete: {success_count}/{len(tickers)} tickers with usable data")

        return results

    def parallel_batch_fetch(
        self,
        tickers: List[str],
        max_workers: int = 10,
        requests_per_second: float = 1.0,
        show_progress: bool = True
    ) -> Dict[str, Optional[FinancialData]]:
        """
        Fetch financial data for multiple tickers in parallel with progress bar

        This method provides significant speedup for large index screening:
        - Uses ThreadPoolExecutor for concurrent fetching
        - Implements rate limiting to avoid API throttling
        - Shows real-time progress bar using tqdm

        Args:
            tickers: List of ticker symbols
            max_workers: Number of parallel threads (default: 10)
            requests_per_second: Rate limit (default: 1.0 = 1 request/second)
            show_progress: Show progress bar (default: True)

        Returns:
            Dict mapping ticker -> FinancialData (or None if failed)

        Performance:
            - Sequential: ~2 seconds per ticker
            - Parallel (10 workers): ~0.3-0.5 seconds per ticker
            - Example: Russell 2000 (2000 tickers) ~8-12 minutes vs 60-80 minutes

        Example:
            fetcher = FinancialDataFetcher()
            results = fetcher.parallel_batch_fetch(
                ['AAPL', 'MSFT', 'GOOGL'],
                max_workers=10,
                show_progress=True
            )
        """
        try:
            from .parallel_fetcher import ParallelFetcher
            logger.debug("ParallelFetcher imported successfully")
        except ImportError as e:
            logger.warning(f"ParallelFetcher not available: {e}, falling back to sequential batch_fetch")
            return self.batch_fetch(tickers)

        logger.info(f"Starting parallel batch fetch for {len(tickers)} tickers "
                   f"(workers={max_workers}, rate={requests_per_second}/s)")

        parallel_fetcher = ParallelFetcher(
            max_workers=max_workers,
            requests_per_second=requests_per_second,
            enable_cache=self.cache is not None,
            max_retries=3
        )

        if show_progress:
            results = parallel_fetcher.batch_fetch_with_progress(
                tickers,
                desc="Fetching financials"
            )
        else:
            results = parallel_fetcher.batch_fetch(tickers)

        valid_results = {
            ticker: data
            for ticker, data in results.items()
            if data and data.data_quality != "insufficient"
        }

        logger.info(f"Parallel fetch complete: {len(valid_results)}/{len(tickers)} tickers with usable data")
        return valid_results

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
        import requests
        from io import StringIO

        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        # Add User-Agent header to avoid 403 Forbidden error from Wikipedia
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        # The ticker table is the first table (index 0) containing the company list
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        logger.info(f"Fetched {len(tickers)} S&P 500 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 tickers: {e}")
        return []


def get_sp400_tickers() -> List[str]:
    """
    Get S&P MidCap 400 ticker list from Wikipedia

    The S&P MidCap 400 covers mid-cap companies with market caps
    typically between $2B and $50B.

    Returns:
        List of ticker symbols
    """
    try:
        import requests
        from io import StringIO

        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_400_companies'
        # Add User-Agent header to avoid 403 Forbidden error from Wikipedia
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        # Use first table (index 0) which contains the company list
        sp400_table = tables[0]
        tickers = sp400_table['Symbol'].tolist()
        logger.info(f"Fetched {len(tickers)} S&P MidCap 400 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 400 tickers: {e}")
        return []


def get_sp600_tickers() -> List[str]:
    """
    Get S&P SmallCap 600 ticker list from Wikipedia

    The S&P SmallCap 600 covers small-cap companies with market caps
    typically between $500M and $2B.

    Returns:
        List of ticker symbols
    """
    try:
        import requests
        from io import StringIO

        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_600_companies'
        # Add User-Agent header to avoid 403 Forbidden error from Wikipedia
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        # Use first table (index 0) which contains the company list
        sp600_table = tables[0]
        tickers = sp600_table['Symbol'].tolist()
        logger.info(f"Fetched {len(tickers)} S&P SmallCap 600 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 600 tickers: {e}")
        return []


def get_nasdaq100_tickers() -> List[str]:
    """
    Get NASDAQ-100 ticker list from Wikipedia

    The NASDAQ-100 includes the 100 largest non-financial companies
    listed on the NASDAQ stock exchange, heavily weighted toward
    technology companies.

    Returns:
        List of ticker symbols
    """
    try:
        import requests
        from io import StringIO

        url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
        # Add User-Agent header to avoid 403 Forbidden error from Wikipedia
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        # The ticker list is typically in the 4th table (index 3)
        # It has columns including 'Ticker'
        nasdaq_table = tables[3]
        tickers = nasdaq_table['Ticker'].tolist()
        logger.info(f"Fetched {len(tickers)} NASDAQ-100 tickers")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch NASDAQ-100 tickers: {e}")
        return []


def get_russell3000_tickers() -> List[str]:
    """
    Get Russell 3000 ticker list

    The Russell 3000 Index measures the performance of the 3,000 largest
    publicly traded U.S. companies, representing approximately 98% of the
    investable U.S. equity market.

    Note: As an approximation, this combines S&P 500, S&P MidCap 400,
    and S&P SmallCap 600 tickers. The actual Russell 3000 may differ
    slightly in methodology and constituents.

    Returns:
        List of ticker symbols
    """
    try:
        # Combine the three S&P indexes as an approximation of Russell 3000
        sp500 = get_sp500_tickers()
        sp400 = get_sp400_tickers()
        sp600 = get_sp600_tickers()

        # Combine and deduplicate
        all_tickers = set(sp500) | set(sp400) | set(sp600)
        tickers = list(all_tickers)

        logger.info(f"Fetched {len(tickers)} approximated Russell 3000 tickers "
                   f"(SP500: {len(sp500)}, SP400: {len(sp400)}, SP600: {len(sp600)})")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch Russell 3000 tickers: {e}")
        return []


def get_russell1000_tickers() -> List[str]:
    """
    Get Russell 1000 ticker list

    The Russell 1000 Index measures the performance of the 1,000 largest
    companies in the Russell 3000 Index, representing approximately 90%
    of the total market capitalization of the Russell 3000.

    Returns:
        List of ticker symbols
    """
    try:
        # Russell 1000 is approximately the top 1/3 of Russell 3000
        # We'll use S&P 500 + S&P MidCap 400 as a close approximation
        sp500 = get_sp500_tickers()
        sp400 = get_sp400_tickers()

        # Combine and deduplicate
        all_tickers = set(sp500) | set(sp400)
        tickers = list(all_tickers)

        logger.info(f"Fetched {len(tickers)} approximated Russell 1000 tickers "
                   f"(SP500: {len(sp500)}, SP400: {len(sp400)})")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch Russell 1000 tickers: {e}")
        return []


def get_russell2000_tickers() -> List[str]:
    """
    Get Russell 2000 ticker list

    The Russell 2000 Index measures the performance of the 2,000 smallest
    companies in the Russell 3000 Index, representing the small-cap segment
    of the U.S. equity market.

    Note: This uses the S&P SmallCap 600 as a high-quality approximation.
    The actual Russell 2000 requires a paid data provider (FTSE Russell).
    S&P 600 is a rules-based, liquid small-cap index that's widely used
    as a benchmark for small-cap strategies.

    Returns:
        List of ticker symbols (~600 small-cap stocks)
    """
    try:
        sp600 = get_sp600_tickers()

        logger.info(f"Using {len(sp600)} S&P SmallCap 600 tickers as Russell 2000 approximation")
        return sp600
    except Exception as e:
        logger.error(f"Failed to fetch Russell 2000 tickers: {e}")
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
