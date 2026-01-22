"""
Parallel Fetcher Module
Concurrent financial data fetching with rate limiting and progress tracking

Features:
- ThreadPoolExecutor for concurrent fetching
- Semaphore-based rate limiting
- Progress bar with tqdm
- Graceful error handling
- Retry logic with exponential backoff

Author: Quality Analysis System
Date: January 2026
"""

import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures._base import Future
from threading import Semaphore
from typing import TYPE_CHECKING, Dict, List, Optional, Callable
from dataclasses import dataclass

import yfinance as yf
import pandas as pd
import numpy as np

if TYPE_CHECKING:
    from .financial_data_fetcher import FinancialData, FinancialDataCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ParallelFetchResult:
    """Result of parallel batch fetch operation"""
    success_count: int
    failed_count: int
    insufficient_count: int
    total_count: int
    duration_seconds: float
    results: Dict[str, 'FinancialData']


class RateLimiter:
    """Thread-safe rate limiter using semaphore"""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.semaphore = Semaphore(1)
        self.last_call_time = 0.0
    
    def acquire(self):
        """Wait if necessary to maintain rate limit"""
        with self.semaphore:
            now = time.time()
            elapsed = now - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_call_time = time.time()


class ParallelFetcher:
    """
    Parallel financial data fetcher with rate limiting and progress tracking
    
    Uses ThreadPoolExecutor to fetch multiple tickers concurrently,
    with semaphore-based rate limiting to avoid overwhelming the API.
    
    Usage:
        fetcher = ParallelFetcher(max_workers=10, requests_per_second=1.0)
        results = fetcher.batch_fetch(['AAPL', 'MSFT', 'GOOGL'])
        
        # With progress bar
        results = fetcher.batch_fetch_with_progress(
            ['AAPL', 'MSFT', 'GOOGL'],
            desc="Fetching financials"
        )
    """
    
    def __init__(
        self,
        max_workers: int = 10,
        requests_per_second: float = 1.0,
        enable_cache: bool = True,
        max_retries: int = 3
    ):
        """
        Initialize parallel fetcher
        
        Args:
            max_workers: Maximum concurrent threads (default: 10)
            requests_per_second: Rate limit (default: 1.0 = 1 request/second)
            enable_cache: Enable 24-hour caching (default: True)
            max_retries: Maximum retry attempts for rate limit errors (default: 3)
        """
        from .financial_data_fetcher import FinancialDataCache

        self.max_workers = max_workers
        self.requests_per_second = requests_per_second
        self.max_retries = max_retries
        self.cache = FinancialDataCache() if enable_cache else None
        self.rate_limiter = RateLimiter(requests_per_second)
        
        logger.info(f"ParallelFetcher initialized: workers={max_workers}, "
                   f"rate={requests_per_second}/s, cache={enable_cache}")
    
    def _fetch_single_ticker(
        self,
        ticker: str,
        retry_count: int = 0
    ) -> tuple:
        """
        Fetch financial data for a single ticker
        
        Args:
            ticker: Stock ticker symbol
            retry_count: Current retry attempt number
            
        Returns:
            Tuple of (ticker, FinancialData or None)
        """
        from .financial_data_fetcher import FinancialData

        try:
            self.rate_limiter.acquire()
            
            if self.cache:
                cached = self.cache.get(ticker)
                if cached is not None:
                    logger.debug(f"Cache HIT for {ticker}")
                    return (ticker, cached)
            
            stock = yf.Ticker(ticker)
            info = stock.info
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cashflow = stock.cashflow
            
            data = FinancialData(ticker=ticker)
            
            data.market_cap = info.get('marketCap')
            data.sector = info.get('sector')
            data.industry = info.get('industry')
            data.current_price = info.get('currentPrice')
            data.pe_ratio = info.get('trailingPE')
            
            if not financials.empty:
                data.revenue = self._safe_get(financials, 'Total Revenue', 0)
                data.cogs = self._safe_get(financials, 'Cost Of Revenue', 0)
                data.operating_income = self._safe_get(financials, 'Operating Income', 0)
                data.net_income = self._safe_get(financials, 'Net Income', 0)
                
                operating_expense = self._safe_get(financials, 'Operating Expense', 0)
                if operating_expense and data.cogs:
                    data.sga = operating_expense - data.cogs
            
            if not balance_sheet.empty:
                data.total_assets = self._safe_get(balance_sheet, 'Total Assets', 0)
                data.shareholder_equity = self._safe_get(balance_sheet, 'Stockholders Equity', 0)
                
                total_debt = self._safe_get(balance_sheet, 'Total Debt', 0)
                if total_debt is None:
                    long_term_debt = self._safe_get(balance_sheet, 'Long Term Debt', 0) or 0
                    current_debt = self._safe_get(balance_sheet, 'Current Debt', 0) or 0
                    total_debt = long_term_debt + current_debt
                data.total_debt = total_debt
            
            if not cashflow.empty:
                data.free_cash_flow = self._safe_get(cashflow, 'Free Cash Flow', 0)
            
            if data.operating_income:
                data.nopat = data.operating_income * 0.79
            
            from datetime import datetime
            data.fetch_time = datetime.now().isoformat()
            
            if data.validate():
                data.data_quality = "complete"
            elif any([data.revenue, data.total_assets, data.net_income]):
                data.data_quality = "partial"
            else:
                data.data_quality = "insufficient"
            
            if self.cache:
                self.cache.set(ticker, data)
            
            logger.debug(f"Fetched {ticker}: quality={data.data_quality}")
            return (ticker, data)
            
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = '429' in error_str or 'too many requests' in error_str
            
            if is_rate_limit and retry_count < self.max_retries:
                wait_time = 2 ** retry_count
                logger.warning(f"Rate limit for {ticker}, retrying in {wait_time}s "
                              f"(attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(wait_time)
                return self._fetch_single_ticker(ticker, retry_count + 1)
            else:
                logger.error(f"Failed to fetch {ticker}: {e}")
                return (ticker, None)
    
    def _safe_get(self, df: pd.DataFrame, key: str, col: int = 0) -> Optional[float]:
        """Safely get value from DataFrame"""
        try:
            if key in df.index:
                value = df.loc[key].iloc[col]
                if pd.notna(value) and not np.isinf(value):
                    return float(value)
        except Exception:
            pass
        return None
    
    def batch_fetch(self, tickers: List[str]) -> Dict[str, Optional['FinancialData']]:
        """
        Fetch financial data for multiple tickers in parallel
        
        Args:
            tickers: List of ticker symbols
            
        Returns:
            Dict mapping ticker -> FinancialData (or None if failed)
        """
        results = {}
        start_time = time.time()
        
        logger.info(f"Starting parallel fetch for {len(tickers)} tickers "
                   f"(workers={self.max_workers})")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_single_ticker, ticker): ticker
                for ticker in tickers
            }
            
            for i, future in enumerate(as_completed(futures)):
                ticker, data = future.result()
                results[ticker] = data
                
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i + 1}/{len(tickers)} completed")
        
        duration = time.time() - start_time
        
        success_count = sum(1 for v in results.values() 
                           if v and v.data_quality != "insufficient")
        failed_count = sum(1 for v in results.values() if v is None)
        insufficient_count = sum(1 for v in results.values() 
                                if v and v.data_quality == "insufficient")
        
        logger.info(f"Parallel fetch complete: {duration:.1f}s")
        logger.info(f"  Success: {success_count}, Failed: {failed_count}, "
                   f"Insufficient: {insufficient_count}")
        
        return results
    
    def batch_fetch_with_progress(
        self,
        tickers: List[str],
        desc: str = "Fetching financials",
        unit: str = "ticker",
        suppress_logging: bool = False
    ) -> Dict[str, Optional['FinancialData']]:
        """
        Fetch financial data with progress bar using tqdm

        Args:
            tickers: List of ticker symbols
            desc: Progress bar description
            unit: Unit label for progress bar
            suppress_logging: Suppress all logging during fetch (default: False)

        Returns:
            Dict mapping ticker -> FinancialData (or None if failed)
        """
        try:
            from tqdm import tqdm
            has_tqdm = True
        except ImportError:
            logger.warning("tqdm not installed, using batch_fetch without progress")
            has_tqdm = False
            return self.batch_fetch(tickers)

        results = {}
        start_time = time.time()

        logger.info(f"Starting parallel fetch with progress: {len(tickers)} tickers")

        def set_logger_level(level: int):
            """Temporarily set logger level for all handlers"""
            root_logger = logging.getLogger()
            original = root_logger.level
            root_logger.setLevel(level)
            for handler in root_logger.handlers:
                handler.setLevel(level)
            return original

        original_level = None
        if suppress_logging:
            original_level = set_logger_level(logging.WARNING)

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._fetch_single_ticker, ticker): ticker
                    for ticker in tickers
                }

                with tqdm(total=len(tickers), desc=desc, unit=unit, mininterval=0.1, miniters=1, dynamic_ncols=True, disable=False, file=sys.stdout) as pbar:
                    for future in as_completed(futures):
                        ticker, data = future.result()
                        results[ticker] = data
                        pbar.update(1)

            duration = time.time() - start_time

            success_count = sum(1 for v in results.values()
                               if v and v.data_quality != "insufficient")
            failed_count = sum(1 for v in results.values() if v is None)

            logger.info(f"Parallel fetch with progress complete: {duration:.1f}s")
            logger.info(f"  Success: {success_count}, Failed: {failed_count}")

            return results
        finally:
            if suppress_logging and original_level is not None:
                set_logger_level(original_level)
    
    def batch_fetch_with_callback(
        self,
        tickers: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Optional['FinancialData']]:
        """
        Fetch financial data with custom progress callback
        
        Args:
            tickers: List of ticker symbols
            progress_callback: Function called with (completed, total)
            
        Returns:
            Dict mapping ticker -> FinancialData (or None if failed)
        """
        results = {}
        start_time = time.time()
        total = len(tickers)

        logger.info(f"Starting parallel fetch with callback: {total} tickers")

        def _update_progress(completed, total):
            if progress_callback:
                progress_callback(completed, total)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_single_ticker, ticker): ticker
                for ticker in tickers
            }

            completed = 0
            for future in as_completed(futures):
                ticker, data = future.result()
                results[ticker] = data
                completed += 1
                _update_progress(completed, total)

        duration = time.time() - start_time

        success_count = sum(1 for v in results.values() 
                           if v and v.data_quality != "insufficient")
        failed_count = sum(1 for v in results.values() if v is None)

        logger.info(f"Parallel fetch with callback complete: {duration:.1f}s")
        logger.info(f"  Success: {success_count}, Failed: {failed_count}")

        return results
    
    def fetch_historical_financials(
        self,
        ticker: str,
        years: int = 10
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical financial data for a single ticker
        
        Args:
            ticker: Stock ticker symbol
            years: Number of years to fetch (default: 10)
            
        Returns:
            DataFrame with historical data or None if failed
        """
        try:
            self.rate_limiter.acquire()
            
            stock = yf.Ticker(ticker)
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cashflow = stock.cashflow
            
            if financials.empty and balance_sheet.empty and cashflow.empty:
                logger.warning(f"No historical data for {ticker}")
                return None
            
            all_years = set()
            if not financials.empty:
                all_years.update(financials.columns)
            if not balance_sheet.empty:
                all_years.update(balance_sheet.columns)
            if not cashflow.empty:
                all_years.update(cashflow.columns)
            
            years_list = sorted([col.year for col in all_years])
            
            if len(years_list) == 0:
                return None
            
            historical_data = []
            
            for year_val in years_list:
                year_col = None
                for col in all_years:
                    if col.year == year_val:
                        year_col = col
                        break
                
                if year_col is None:
                    continue
                
                row_data = {'year': year_val}
                
                if not financials.empty and year_col in financials.columns:
                    col_idx = financials.columns.get_loc(year_col)
                    row_data['revenue'] = self._safe_get(financials, 'Total Revenue', col_idx)
                    row_data['cogs'] = self._safe_get(financials, 'Cost Of Revenue', col_idx)
                    row_data['net_income'] = self._safe_get(financials, 'Net Income', col_idx)
                    operating_income = self._safe_get(financials, 'Operating Income', col_idx)
                    
                    operating_expense = self._safe_get(financials, 'Operating Expense', col_idx)
                    if operating_expense is not None and row_data.get('cogs') is not None:
                        row_data['sga'] = operating_expense - row_data['cogs']
                    else:
                        row_data['sga'] = None
                    
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
                
                if not balance_sheet.empty and year_col in balance_sheet.columns:
                    col_idx = balance_sheet.columns.get_loc(year_col)
                    row_data['total_assets'] = self._safe_get(balance_sheet, 'Total Assets', col_idx)
                    row_data['shareholder_equity'] = self._safe_get(balance_sheet, 'Stockholders Equity', col_idx)
                    
                    total_debt = self._safe_get(balance_sheet, 'Total Debt', col_idx)
                    if total_debt is None:
                        long_term_debt = self._safe_get(balance_sheet, 'Long Term Debt', col_idx) or 0
                        current_debt = self._safe_get(balance_sheet, 'Current Debt', col_idx) or 0
                        total_debt = long_term_debt + current_debt if (long_term_debt or current_debt) else None
                    row_data['total_debt'] = total_debt
                else:
                    row_data['total_assets'] = None
                    row_data['shareholder_equity'] = None
                    row_data['total_debt'] = None
                
                if not cashflow.empty and year_col in cashflow.columns:
                    col_idx = cashflow.columns.get_loc(year_col)
                    row_data['free_cash_flow'] = self._safe_get(cashflow, 'Free Cash Flow', col_idx)
                else:
                    row_data['free_cash_flow'] = None
                
                historical_data.append(row_data)
            
            df = pd.DataFrame(historical_data)
            
            required_columns = ['year', 'revenue', 'cogs', 'sga', 'total_assets',
                              'net_income', 'shareholder_equity', 'free_cash_flow',
                              'total_debt', 'nopat']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            df = df[required_columns]
            df = df.sort_values('year').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to fetch historical financials for {ticker}: {e}")
            return None
    
    def parallel_batch_historical_fetch(
        self,
        tickers: List[str],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Fetch historical financials for multiple tickers in parallel
        
        Args:
            tickers: List of ticker symbols
            progress_callback: Function called with (completed, total)
            
        Returns:
            Dict mapping ticker -> DataFrame (or None if failed)
        """
        results = {}
        total = len(tickers)
        
        logger.info(f"Fetching historical financials for {total} tickers")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.fetch_historical_financials, ticker): ticker
                for ticker in tickers
            }
            
            completed = 0
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    data = future.result()
                    results[ticker] = data
                except Exception as e:
                    logger.error(f"Error fetching historicals for {ticker}: {e}")
                    results[ticker] = None
                
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
        
        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(f"Historical fetch complete: {success_count}/{total} successful")
        
        return results


if __name__ == "__main__":
    print("=" * 60)
    print("Parallel Fetcher Test")
    print("=" * 60)
    
    fetcher = ParallelFetcher(max_workers=5, requests_per_second=1.0)
    
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "LLY", "V"]
    
    print(f"\nTesting parallel batch fetch for {len(tickers)} tickers")
    results = fetcher.batch_fetch_with_progress(tickers, desc="Fetching test tickers")
    
    print("\nResults:")
    for ticker, data in results.items():
        if data:
            quality = data.data_quality
            print(f"  {ticker}: {quality}")
        else:
            print(f"  {ticker}: FAILED")
    
    print(f"\nTest complete. {sum(1 for v in results.values() if v)}/{len(tickers)} successful")
