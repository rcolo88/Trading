"""
SimFin Data Fetcher Module

Provides access to SimFin financial data for enhanced historical depth
and broader stock coverage as an alternative/complement to FMP.

Key Features:
- 5,000+ US stocks (vs FMP's limited free tier)
- 5 years historical data on free tier (vs FMP's call limits)
- Raw financial statements for custom ratio calculations
- No premium symbol restrictions (unlike FMP)
- Bulk download capabilities for efficiency
"""

import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

import simfin as sf
import pandas as pd
import numpy as np
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple
import pickle
import os
from dataclasses import dataclass, asdict
import json

warnings.filterwarnings('ignore', category=FutureWarning, module='simfin.load')

from .ticker_mapping import get_api_ticker, is_mapped_ticker
from .stock_logger import get_stock_logger

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class SimFinFinancialData:
    """Structured financial data from SimFin with source tagging"""
    ticker: str
    
    # Basic info
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[float] = None
    pe_ratio: Optional[float] = None
    
    # Income statement
    revenue: Optional[float] = None
    cogs: Optional[float] = None
    sga: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    
    # Balance sheet
    total_assets: Optional[float] = None
    shareholder_equity: Optional[float] = None
    total_debt: Optional[float] = None
    
    # Cash flow
    operating_cash_flow: Optional[float] = None
    free_cash_flow: Optional[float] = None
    
    # Additional fields for ratio calculations
    retained_earnings: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    interest_expense: Optional[float] = None
    working_capital: Optional[float] = None
    
    # Calculated ratios (will be computed)
    calculated_ratios: Dict[str, Any] = None
    
    # Metadata
    data_source: str = "SimFin"
    fiscal_year: Optional[int] = None
    fetch_time: Optional[str] = None
    data_quality: str = "complete"  # complete, partial, insufficient
    years_available: int = 0
    
    def to_dict(self) -> Dict:
        """Convert to dictionary with source tagging"""
        data = asdict(self)
        if self.calculated_ratios:
            data.update({f"simfin_{k}": v for k, v in self.calculated_ratios.items()})
        return data
    
    def validate(self) -> bool:
        """Check if data is sufficient for quality analysis"""
        required = [
            self.revenue, self.total_assets,
            self.net_income, self.shareholder_equity
        ]
        return all(x is not None for x in required)


class SimFinDataCache:
    """File-based cache for SimFin data with longer expiry (fundamental data changes quarterly)"""
    
    def __init__(self, cache_file: str = "simfin_cache.pkl", cache_days: int = 30):
        self.cache_file = cache_file
        self.cache_days = cache_days
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                    logger.debug(f"Loaded SimFin cache with {len(cache)} entries")
                    return cache
            except Exception as e:
                logger.warning(f"Failed to load SimFin cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            logger.debug(f"Saved SimFin cache with {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save SimFin cache: {e}")
    
    def get(self, ticker: str) -> Optional[SimFinFinancialData]:
        """Get cached SimFin data if available and fresh"""
        if ticker in self.cache:
            data, timestamp = self.cache[ticker]
            if datetime.now() - timestamp < timedelta(days=self.cache_days):
                logger.debug(f"SimFin cache HIT for {ticker}")
                return data
            else:
                logger.debug(f"SimFin cache EXPIRED for {ticker}")
                del self.cache[ticker]
        return None
    
    def set(self, ticker: str, data: SimFinFinancialData):
        """Cache SimFin data"""
        self.cache[ticker] = (data, datetime.now())
        self._save_cache()
        logger.debug(f"Cached SimFin data for {ticker}")
    
    def clear(self):
        """Clear entire cache"""
        self.cache = {}
        self._save_cache()
        logger.info("SimFin cache cleared")


class SimFinDataFetcher:
    """
    Fetch fundamental financial data from SimFin
    
    Features:
    - 5,000+ US stocks on free tier
    - 5 years historical data (free tier)
    - Raw financial statements for custom calculations
    - No premium symbol restrictions
    - Bulk download capabilities
    - 30-day caching (fundamental data changes quarterly)
    """
    
    def __init__(self, api_key: str = None, enable_cache: bool = True, 
                 cache_file: str = "simfin_cache.pkl"):
        """
        Initialize SimFin data fetcher
        
        Args:
            api_key: SimFin API key (get free at simfin.com)
            enable_cache: Enable 30-day caching (default: True)
            cache_file: Path to cache file
        """
        # Set API key if provided
        if api_key:
            sf.set_api_key(api_key)
            logger.info("SimFin API key set")
        
        # Set data directory (default: ~/simfin_data/)
        sf.set_data_dir('~/simfin_data/')
        
        self.cache = SimFinDataCache(cache_file) if enable_cache else None
        logger.info("SimFinDataFetcher initialized")

    def _resolve_ticker(self, ticker: str) -> str:
        """
        Resolve standard ticker to SimFin-specific ticker.

        Args:
            ticker: Standard ticker symbol (e.g., 'FISV', 'GOOGL')

        Returns:
            SimFin-specific ticker (e.g., 'FI', 'GOOG')
        """
        original_ticker = ticker
        resolved_ticker = get_api_ticker(ticker, 'simfin')

        if resolved_ticker != original_ticker:
            logger.warning(
                f"Ticker mapping applied: '{original_ticker}' -> '{resolved_ticker}' (SimFin)"
            )

        return resolved_ticker

    def fetch_financial_data(self, ticker: str, variant: str = 'annual',
                          market: str = 'us') -> Optional[SimFinFinancialData]:
        """
        Fetch current financial data from SimFin

        Args:
            ticker: Stock ticker symbol
            variant: 'annual' or 'quarterly' (default: 'annual')
            market: 'us', 'de', or other markets (default: 'us')

        Returns:
            SimFinFinancialData object or None if fetch failed
        """
        # Resolve ticker for SimFin (handles FISV -> FI, GOOGL -> GOOG, etc.)
        simfin_ticker = self._resolve_ticker(ticker)

        # Check cache first (using original ticker as key for consistency)
        if self.cache:
            cached = self.cache.get(ticker)
            if cached is not None:
                logger.debug(f"Using cached SimFin data for {ticker}")
                return cached

        try:
            logger.debug(f"Fetching SimFin data for {ticker} (resolved: {simfin_ticker})")
            
            # Suppress SimFin library output during data loading
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            suppressed_output = io.StringIO()
            with redirect_stdout(suppressed_output), redirect_stderr(suppressed_output):
                # Load financial statements from SimFin
                income_df = sf.load_income(variant=variant, market=market)
                balance_df = sf.load_balance(variant=variant, market=market)
                cashflow_df = sf.load_cashflow(variant=variant, market=market)
                companies_df = sf.load_companies(market=market)
            
            # Check if ticker exists in data (use resolved ticker for SimFin lookup)
            if simfin_ticker not in income_df.index:
                get_stock_logger().warning(
                    ticker,
                    f"Ticker {ticker} (resolved: {simfin_ticker}) not found in SimFin data. "
                    f"Note: SimFin uses internal tickers (e.g., FISV -> FI, GOOGL -> GOOG)"
                )
                return None

            # Extract most recent data (last column is most recent)
            data = SimFinFinancialData(ticker=ticker)

            # Get company info (use resolved ticker)
            if simfin_ticker in companies_df.index:
                company_info = companies_df.loc[simfin_ticker]
                data.sector = company_info.get('Sector')
                data.industry = company_info.get('Industry')

            # Income Statement (most recent fiscal year) - use resolved ticker
            income_data = income_df.loc[simfin_ticker]
            if not income_data.empty:
                # Get most recent year (last column)
                recent_income = income_data.iloc[-1]
                data.fiscal_year = recent_income.get('Fiscal Year')
                
                data.revenue = recent_income.get('Revenue')
                data.cogs = recent_income.get('Cost of Revenue')
                # SimFin uses "Operating Income (Loss)" not "Operating Income"
                data.operating_income = recent_income.get('Operating Income (Loss)')
                data.net_income = recent_income.get('Net Income')
                
                # EBIT is same as Operating Income
                data.ebit = data.operating_income
                
                # Calculate SG&A
                operating_expense = recent_income.get('Operating Expense')
                if operating_expense and data.cogs:
                    data.sga = operating_expense - data.cogs
                
                # Get Interest Expense from income statement (SimFin uses "Interest Expense, Net")
                interest_exp_raw = recent_income.get('Interest Expense, Net')
                if interest_exp_raw is not None and not (isinstance(interest_exp_raw, float) and str(interest_exp_raw) == 'nan'):
                    data.interest_expense = abs(float(interest_exp_raw))
                
                # Calculate EBITDA if not directly available
                # EBITDA = Operating Income + Depreciation & Amortization
                if data.ebit is not None:
                    depreciation = recent_income.get('Depreciation & Amortization')
                    if depreciation is not None and not (isinstance(depreciation, float) and str(depreciation) == 'nan'):
                        data.ebitda = data.ebit + float(depreciation)
                    else:
                        data.ebitda = data.ebit * 1.15  # Estimate
            
            # Balance Sheet - use resolved ticker
            balance_data = balance_df.loc[simfin_ticker]
            if not balance_data.empty:
                recent_balance = balance_data.iloc[-1]
                
                data.total_assets = recent_balance.get('Total Assets')
                data.shareholder_equity = recent_balance.get('Total Equity')
                data.total_debt = recent_balance.get('Total Debt')
                
                # Working capital = Current Assets - Current Liabilities
                current_assets = recent_balance.get('Total Current Assets')
                current_liabilities = recent_balance.get('Total Current Liabilities')
                if current_assets is not None and current_liabilities is not None:
                    data.working_capital = current_assets - current_liabilities
                
                # Retained earnings for Altman Z-Score
                data.retained_earnings = recent_balance.get('Retained Earnings')
            
            # Cash Flow Statement - use resolved ticker
            cashflow_data = cashflow_df.loc[simfin_ticker]
            if not cashflow_data.empty:
                recent_cashflow = cashflow_data.iloc[-1]
                
                data.operating_cash_flow = recent_cashflow.get('Net Cash from Operating Activities')
                data.free_cash_flow = recent_cashflow.get('Free Cash Flow')
                
                # Note: Interest expense is extracted from income statement, not cash flow
                # See above section where we extract from recent_income.get('Interest Expense, Net')
                
                # Interest expense for coverage ratio
                data.interest_expense = recent_cashflow.get('Interest Expense (Income)')
                
                # Calculate EBITDA if not available
                if data.ebit is not None:
                    depreciation = recent_cashflow.get('Depreciation & Amortization')
                    if depreciation is not None:
                        data.ebitda = data.ebit + depreciation
                    else:
                        # Conservative estimate: EBITDA ≈ EBIT * 1.15
                        data.ebitda = data.ebit * 1.15
            
            # Metadata
            data.fetch_time = datetime.now().isoformat()
            data.years_available = len(income_df.columns) if not income_df.empty else 0
            
            # Data quality assessment
            if data.validate():
                data.data_quality = "complete"
                logger.debug(f"Successfully fetched complete SimFin data for {ticker}")
            elif any([data.revenue, data.total_assets, data.net_income]):
                data.data_quality = "partial"
                get_stock_logger().warning(ticker, "Partial SimFin data")
            else:
                data.data_quality = "insufficient"
                get_stock_logger().warning(ticker, "Insufficient SimFin data")
            
            # Cache results
            if self.cache:
                self.cache.set(ticker, data)
            
            return data
            
        except Exception as e:
            get_stock_logger().error(ticker, f"Failed to fetch SimFin data: {e}")
            return None
    
    def fetch_historical_financials(self, ticker: str, years: int = 5,
                                  variant: str = 'annual', market: str = 'us') -> Optional[Dict]:
        """
        Fetch historical financial data for ratio calculations

        Args:
            ticker: Stock ticker symbol
            years: Number of years to fetch (default: 5)
            variant: 'annual' or 'quarterly'
            market: Market identifier

        Returns:
            Dict with historical data for ratios calculation
        """
        # Resolve ticker for SimFin
        simfin_ticker = self._resolve_ticker(ticker)

        try:
            logger.debug(f"Fetching historical SimFin data for {ticker} (resolved: {simfin_ticker}, {years} years)")

            # Suppress SimFin library output during data loading
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            suppressed_output = io.StringIO()
            with redirect_stdout(suppressed_output), redirect_stderr(suppressed_output):
                # Load financial statements
                income_df = sf.load_income(variant=variant, market=market)
                balance_df = sf.load_balance(variant=variant, market=market)
                cashflow_df = sf.load_cashflow(variant=variant, market=market)

            # Use resolved ticker for lookup
            if simfin_ticker not in income_df.index:
                get_stock_logger().warning(
                    ticker,
                    f"Ticker {ticker} (resolved: {simfin_ticker}) not found in SimFin historical data"
                )
                return None

            # Extract historical data
            historical_data = {
                'ticker': ticker,
                'simfin_ticker': simfin_ticker,
                'years_available': len(income_df.columns),
                'income': [],
                'balance': [],
                'cash_flow': []
            }

            # Income statement history - use resolved ticker
            income_history = income_df.loc[simfin_ticker]
            if not income_history.empty:
                for idx in range(len(income_history)):
                    row = income_history.iloc[idx]
                    historical_data['income'].append({
                        'fiscal_year': row.get('Fiscal Year'),
                        'revenue': row.get('Revenue'),
                        'cogs': row.get('Cost of Revenue'),
                        'operating_income': row.get('Operating Income'),
                        'net_income': row.get('Net Income'),
                        'ebit': row.get('Operating Income'),
                        'operating_expense': row.get('Operating Expense')
                    })
            
            # Balance sheet history - use resolved ticker
            balance_history = balance_df.loc[simfin_ticker]
            if not balance_history.empty:
                for idx in range(len(balance_history)):
                    row = balance_history.iloc[idx]
                    historical_data['balance'].append({
                        'fiscal_year': row.get('Fiscal Year'),
                        'total_assets': row.get('Total Assets'),
                        'shareholder_equity': row.get('Total Equity'),
                        'total_debt': row.get('Total Debt'),
                        'current_assets': row.get('Total Current Assets'),
                        'current_liabilities': row.get('Total Current Liabilities'),
                        'retained_earnings': row.get('Retained Earnings'),
                        'working_capital': None  # Will be calculated
                    })
            
            # Cash flow history - use resolved ticker
            cashflow_history = cashflow_df.loc[simfin_ticker]
            if not cashflow_history.empty:
                for idx in range(len(cashflow_history)):
                    row = cashflow_history.iloc[idx]
                    historical_data['cash_flow'].append({
                        'fiscal_year': row.get('Fiscal Year'),
                        'operating_cash_flow': row.get('Net Cash from Operating Activities'),
                        'free_cash_flow': row.get('Free Cash Flow'),
                        'interest_expense': None,  # From income statement below
                        'depreciation_amortization': row.get('Depreciation & Amortization')
                    })
            
            # Income statement history - use resolved ticker with correct field names
            income_history = income_df.loc[simfin_ticker]
            if not income_history.empty:
                for idx in range(len(income_history)):
                    income_row = income_history.iloc[idx]
                    
                    # Update the income entry with correct field names
                    if idx < len(historical_data['income']):
                        historical_data['income'][idx]['revenue'] = income_row.get('Revenue')
                        historical_data['income'][idx]['cogs'] = income_row.get('Cost of Revenue')
                        historical_data['income'][idx]['operating_income'] = income_row.get('Operating Income (Loss)')
                        historical_data['income'][idx]['net_income'] = income_row.get('Net Income')
                        historical_data['income'][idx]['ebit'] = income_row.get('Operating Income (Loss)')
                    
                    # Get interest expense from income statement
                    ie_raw = income_row.get('Interest Expense, Net')
                    if ie_raw is not None and not (isinstance(ie_raw, float) and str(ie_raw) == 'nan'):
                        interest_expense = abs(float(ie_raw))
                    else:
                        interest_expense = None
                    
                    # Update the cash flow entry with interest expense from income statement
                    if idx < len(historical_data['cash_flow']):
                        historical_data['cash_flow'][idx]['interest_expense'] = interest_expense
            
            # Calculate working capital for balance sheet history
            for i, balance_year in enumerate(historical_data['balance']):
                if balance_year['current_assets'] is not None and balance_year['current_liabilities'] is not None:
                    balance_year['working_capital'] = (
                        balance_year['current_assets'] - balance_year['current_liabilities']
                    )
            
            logger.debug(f"Successfully fetched {len(historical_data['income'])} years of historical data for {ticker}")
            return historical_data
            
        except Exception as e:
            get_stock_logger().error(ticker, f"Failed to fetch historical SimFin data: {e}")
            return None
    
    def get_available_tickers(self, market: str = 'us') -> List[str]:
        """
        Get list of available tickers for a market
        
        Args:
            market: Market identifier (default: 'us')
            
        Returns:
            List of ticker symbols available in SimFin
        """
        try:
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            suppressed_output = io.StringIO()
            with redirect_stdout(suppressed_output), redirect_stderr(suppressed_output):
                companies_df = sf.load_companies(market=market)
            tickers = companies_df.index.tolist()
            logger.debug(f"Found {len(tickers)} tickers available in SimFin for {market} market")
            return tickers
        except Exception as e:
            logger.error(f"Failed to get available tickers from SimFin: {e}")
            return []
    
    def batch_fetch(self, tickers: List[str], delay: float = 1.0) -> Dict[str, Optional[SimFinFinancialData]]:
        """
        Fetch financial data for multiple tickers
        
        Args:
            tickers: List of ticker symbols
            delay: Seconds to wait between requests (SimFin rate limit: 2 calls/sec free tier)
            
        Returns:
            Dict mapping ticker -> SimFinFinancialData (or None if failed)
        """
        results = {}
        
        for i, ticker in enumerate(tickers):
            logger.debug(f"Fetching SimFin data {i+1}/{len(tickers)}: {ticker}")
            data = self.fetch_financial_data(ticker)
            results[ticker] = data
            
            # Rate limiting: 2 calls/sec for free tier = 0.5s between calls
            # Use 1.0s for safety margin
            if i < len(tickers) - 1 and delay > 0:
                time.sleep(delay)
        
        success_count = sum(1 for v in results.values() if v and v.data_quality != "insufficient")
        logger.debug(f"SimFin batch fetch complete: {success_count}/{len(tickers)} tickers with usable data")
        
        return results


# Example usage
if __name__ == "__main__":
    # Initialize fetcher (you'll need to set your API key)
    # fetcher = SimFinDataFetcher(api_key='YOUR_SIMFIN_API_KEY')
    fetcher = SimFinDataFetcher()  # Will use default free tier
    
    # Example 1: Fetch data for a single ticker
    print("\n" + "="*60)
    print("Example 1: Fetch SimFin data for AAPL")
    print("="*60)
    aapl_data = fetcher.fetch_financial_data("AAPL")
    if aapl_data:
        print(f"Ticker: {aapl_data.ticker}")
        print(f"Years Available: {aapl_data.years_available}")
        print(f"Revenue: ${aapl_data.revenue:,.0f}" if aapl_data.revenue else "N/A")
        print(f"Net Income: ${aapl_data.net_income:,.0f}" if aapl_data.net_income else "N/A")
        print(f"Total Assets: ${aapl_data.total_assets:,.0f}" if aapl_data.total_assets else "N/A")
        print(f"Data Quality: {aapl_data.data_quality}")
        print(f"Data Source: {aapl_data.data_source}")
    
    # Example 2: Get available tickers
    print("\n" + "="*60)
    print("Example 2: Get available tickers (first 10)")
    print("="*60)
    available_tickers = fetcher.get_available_tickers()
    print(f"Total tickers available: {len(available_tickers)}")
    print(f"First 10 tickers: {available_tickers[:10]}")
    
    # Example 3: Batch fetch
    print("\n" + "="*60)
    print("Example 3: Batch fetch for multiple tickers")
    print("="*60)
    tickers = ["AAPL", "MSFT", "GOOGL"][:3]  # Limit for example
    batch_results = fetcher.batch_fetch(tickers)
    for ticker, data in batch_results.items():
        if data:
            print(f"  {ticker}: {data.data_quality} data ({data.years_available} years)")
        else:
            print(f"  {ticker}: FAILED")