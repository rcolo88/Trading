"""
Company Detector - Identifies US vs Foreign companies and determines data source

Uses SimFin's US companies list as the primary source of truth.
Foreign detection: If ticker is NOT in SimFin US companies, it's foreign.
"""

from dataclasses import dataclass
from typing import Optional, Dict
import simfin as sf
import pandas as pd
import logging

logger = logging.getLogger(__name__)


@dataclass
class CompanyProfile:
    """Profile of a company with origin and data source info"""
    ticker: str
    is_us_company: bool
    country: Optional[str]
    currency: Optional[str]
    exchange: Optional[str]
    company_name: Optional[str]
    recommended_source: str
    simfin_data_years: int
    
    @property
    def needs_currency_conversion(self) -> bool:
        """Returns True if currency conversion is needed"""
        return self.currency is not None and self.currency != 'USD'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'ticker': self.ticker,
            'is_us_company': self.is_us_company,
            'country': self.country,
            'currency': self.currency,
            'exchange': self.exchange,
            'company_name': self.company_name,
            'recommended_source': self.recommended_source,
            'simfin_data_years': self.simfin_data_years,
            'needs_currency_conversion': self.needs_currency_conversion
        }


class CompanyDetector:
    """
    Detects company origin and determines appropriate data source.
    
    Detection Strategy:
    1. Check if ticker exists in SimFin's US companies list
    2. If yes → US company, use SimFin
    3. If no → Foreign company, use yfinance with currency conversion
    
    Fallback:
    4. If SimFin lookup fails, use yfinance to verify
    """
    
    def __init__(self, us_market: str = 'us'):
        """
        Initialize company detector.
        
        Args:
            us_market: Market identifier for US companies (usually 'us')
        """
        self.us_market = us_market
        self._us_companies_cache: Optional[pd.Index] = None
    
    def _load_us_companies(self) -> pd.Index:
        """Load and cache US companies list from SimFin"""
        if self._us_companies_cache is None:
            try:
                import sys
                import io
                from contextlib import redirect_stdout, redirect_stderr
                
                suppressed_output = io.StringIO()
                with redirect_stdout(suppressed_output), redirect_stderr(suppressed_output):
                    companies_df = sf.load_companies(market=self.us_market)
                self._us_companies_cache = companies_df.index
                logger.debug(f"Loaded {len(self._us_companies_cache)} US companies from SimFin")
            except Exception as e:
                logger.error(f"Failed to load US companies: {e}")
                self._us_companies_cache = pd.Index([])
        return self._us_companies_cache
    
    def detect(self, ticker: str) -> CompanyProfile:
        """
        Detect company origin and determine appropriate data source.
        
        Detection Strategy:
        1. Check if ticker exists in SimFin's US companies list
        2. If yes → Check actual reporting currency via yfinance
           - If currency is USD → US company, use SimFin
           - If currency is not USD → Foreign company, use yfinance with conversion
        3. If no → Foreign company, use yfinance with currency conversion
        """
        ticker = ticker.upper().strip()
        
        us_companies = self._load_us_companies()
        in_simfin_us = ticker in us_companies
        
        # Get actual info from yfinance
        yfinance_currency = 'USD'
        info = {}
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            yfinance_currency = info.get('currency', 'USD')
        except Exception:
            yfinance_currency = 'USD'
        
        # Get country of incorporation from yfinance
        country = info.get('country', '')
        
        # Company is foreign if:
        # 1. Not in SimFin US list, OR
        # 2. Country of incorporation is not US
        is_foreign = not in_simfin_us or (country and country != 'United States')
        
        if is_foreign:
            logger.debug(f"{ticker}: Detected as foreign company (country: {country})")
            return self._create_foreign_profile_with_info(ticker, yfinance_currency, info)
        else:
            return self._create_us_profile(ticker, us_companies)
    
    def _create_foreign_profile_with_info(self, ticker: str, currency: str, info: dict) -> CompanyProfile:
        """Create profile for foreign company with known currency"""
        company_name = info.get('longName') or info.get('shortName')
        country = info.get('country')
        exchange = info.get('exchange')
        
        return CompanyProfile(
            ticker=ticker,
            is_us_company=False,
            country=country,
            currency=currency,
            exchange=exchange,
            company_name=company_name,
            recommended_source='yfinance',
            simfin_data_years=0
        )
    
    def _create_us_profile(self, ticker: str, us_companies: pd.Index) -> CompanyProfile:
        """Create profile for US company"""
        try:
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            suppressed_output = io.StringIO()
            with redirect_stdout(suppressed_output), redirect_stderr(suppressed_output):
                companies_df = sf.load_companies(market=self.us_market)
            row = companies_df.loc[ticker]
            
            company_name = row.get('Company Name') or row.get('Name')
            country = 'US'
            exchange = row.get('Exchange')
            currency = 'USD'
            
            simfin_data_years = self._count_simfin_data_years(ticker)
            
            return CompanyProfile(
                ticker=ticker,
                is_us_company=True,
                country=country,
                currency=currency,
                exchange=exchange,
                company_name=company_name,
                recommended_source='simfin',
                simfin_data_years=simfin_data_years
            )
        except Exception as e:
            logger.warning(f"Failed to get US company details for {ticker}: {e}")
            return CompanyProfile(
                ticker=ticker,
                is_us_company=True,
                country='US',
                currency='USD',
                exchange=None,
                company_name=None,
                recommended_source='simfin',
                simfin_data_years=0
            )
    
    def _create_foreign_profile(self, ticker: str) -> CompanyProfile:
        """Create profile for foreign company using yfinance"""
        try:
            import yfinance as yf
            
            stock = yf.Ticker(ticker)
            info = stock.info
            
            company_name = info.get('longName') or info.get('shortName')
            country = info.get('country')
            exchange = info.get('exchange')
            currency = info.get('currency', 'USD')
            
            logger.info(f"Foreign company detected: {ticker} ({country}, {currency})")
            
            return CompanyProfile(
                ticker=ticker,
                is_us_company=False,
                country=country,
                currency=currency,
                exchange=exchange,
                company_name=company_name,
                recommended_source='yfinance',
                simfin_data_years=0
            )
        except Exception as e:
            logger.warning(f"Failed to get foreign company details for {ticker}: {e}")
            return CompanyProfile(
                ticker=ticker,
                is_us_company=False,
                country=None,
                currency=None,
                exchange=None,
                company_name=None,
                recommended_source='yfinance',
                simfin_data_years=0
            )
    
    def _count_simfin_data_years(self, ticker: str) -> int:
        """Count how many years of data exist for ticker in SimFin"""
        try:
            import sys
            import io
            from contextlib import redirect_stdout, redirect_stderr
            
            suppressed_output = io.StringIO()
            with redirect_stdout(suppressed_output), redirect_stderr(suppressed_output):
                income_df = sf.load_income(variant='annual', market=self.us_market)
            if ticker in income_df.index:
                return len(income_df.columns)
            return 0
        except Exception:
            return 0
    
    def is_us_company(self, ticker: str) -> bool:
        """
        Quick check if ticker is a US company.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            True if US company, False if foreign
        """
        ticker = ticker.upper().strip()
        us_companies = self._load_us_companies()
        return ticker in us_companies
    
    def should_use_simfin(self, ticker: str, min_years: int = 3) -> bool:
        """
        Determine if SimFin should be used for this ticker.
        
        Args:
            ticker: Stock ticker symbol
            min_years: Minimum years of data required (default: 3)
            
        Returns:
            True if SimFin should be used, False otherwise
        """
        if not self.is_us_company(ticker):
            return False
        
        data_years = self._count_simfin_data_years(ticker)
        
        if data_years < min_years:
            logger.info(
                f"Ticker {ticker} has only {data_years} years of SimFin data "
                f"(minimum {min_years} required), will use yfinance instead"
            )
            return False
        
        return True
    
    def needs_currency_conversion(self, ticker: str) -> bool:
        """
        Determine if currency conversion is needed for this ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            True if conversion needed, False otherwise
        """
        profile = self.detect(ticker)
        return profile.needs_currency_conversion
    
    def get_currency(self, ticker: str) -> Optional[str]:
        """
        Get the reporting currency for this ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Currency code (e.g., 'USD', 'TWD', 'JPY')
        """
        profile = self.detect(ticker)
        return profile.currency
    
    def get_recommended_source(self, ticker: str) -> str:
        """
        Get the recommended data source for this ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            'simfin' or 'yfinance'
        """
        profile = self.detect(ticker)
        return profile.recommended_source
    
    def clear_cache(self) -> None:
        """Clear the US companies cache"""
        self._us_companies_cache = None
        logger.info("Company detector cache cleared")
    
    def detect_batch(self, tickers: list) -> Dict[str, CompanyProfile]:
        """
        Detect company info for multiple tickers.
        
        Args:
            tickers: List of stock ticker symbols
            
        Returns:
            Dictionary mapping ticker to CompanyProfile
        """
        results = {}
        for ticker in tickers:
            results[ticker] = self.detect(ticker)
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    detector = CompanyDetector()
    
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSM', 'SONY', 'NVDA', 'NVO', 'BABA']
    
    print("Company Detection Results")
    print("=" * 80)
    
    for ticker in test_tickers:
        profile = detector.detect(ticker)
        print(f"\n{ticker}:")
        print(f"  US Company: {profile.is_us_company}")
        print(f"  Country: {profile.country}")
        print(f"  Currency: {profile.currency}")
        print(f"  Exchange: {profile.exchange}")
        print(f"  Source: {profile.recommended_source}")
        print(f"  Data Years: {profile.simfin_data_years}")
    
    print("\n" + "=" * 80)
    print("\nQuick Detection:")
    for ticker in test_tickers:
        source = detector.get_recommended_source(ticker)
        print(f"  {ticker}: {source}")
