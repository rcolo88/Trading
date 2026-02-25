"""
YFinance Data Fetcher - Fetches financial data with currency conversion

Designed for foreign companies that report in non-USD currencies.
Automatically converts all values to USD using live exchange rates.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
import requests
import logging

from .currency_converter import CurrencyConverter, CurrencyConversionError
from .company_detector import CompanyDetector, CompanyProfile

logger = logging.getLogger(__name__)


@dataclass
class YFinanceFinancialData:
    """Extended financial data with currency info"""
    ticker: str
    # Basic info
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    current_price: Optional[float] = None
    pe_ratio: Optional[float] = None
    company_name: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    
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
    
    # Calculated metrics
    nopat: Optional[float] = None
    
    # Additional fields for safety metrics
    retained_earnings: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    interest_expense: Optional[float] = None
    working_capital: Optional[float] = None
    
    # Metadata
    fetch_time: Optional[str] = None
    data_quality: str = "complete"
    source_currency: Optional[str] = None
    exchange_rate_used: Optional[float] = None
    
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
    
    def to_financial_data(self) -> 'FinancialData':
        """Convert to standard FinancialData format for quality analysis"""
        from .financial_data_fetcher import FinancialData
        return FinancialData(
            ticker=self.ticker,
            market_cap=self.market_cap,
            sector=self.sector,
            industry=self.industry,
            current_price=self.current_price,
            pe_ratio=self.pe_ratio,
            revenue=self.revenue,
            cogs=self.cogs,
            sga=self.sga,
            operating_income=self.operating_income,
            net_income=self.net_income,
            total_assets=self.total_assets,
            shareholder_equity=self.shareholder_equity,
            total_debt=self.total_debt,
            operating_cash_flow=self.operating_cash_flow,
            free_cash_flow=self.free_cash_flow,
            nopat=self.nopat,
            retained_earnings=self.retained_earnings,
            ebit=self.ebit,
            ebitda=self.ebitda,
            interest_expense=self.interest_expense,
            working_capital=self.working_capital,
            fetch_time=self.fetch_time,
            data_quality=self.data_quality
        )


class YFinanceDataFetcher:
    """
    Fetches financial data from yfinance with currency conversion.
    
    Designed for foreign companies that report in non-USD currencies.
    
    Features:
    - Automatic currency detection from company country of incorporation
    - Live exchange rate conversion to USD
    - Historical data with currency conversion
    - Comprehensive field mapping for different industries
    - Error handling with fallback
    """
    
    # Country to reporting currency mapping
    # Many foreign companies trade in USD but report financials in home currency
    COUNTRY_CURRENCY_MAP = {
        'Taiwan': 'TWD',
        'Japan': 'JPY',
        'South Korea': 'KRW',
        'China': 'CNY',
        'Hong Kong': 'HKD',
        'Singapore': 'SGD',
        'India': 'INR',
        'Denmark': 'DKK',
        'Switzerland': 'CHF',
        'Sweden': 'SEK',
        'Norway': 'NOK',
        'United Kingdom': 'GBP',
        'Germany': 'EUR',
        'France': 'EUR',
        'Netherlands': 'EUR',
        'Spain': 'EUR',
        'Italy': 'EUR',
        'Australia': 'AUD',
        'Canada': 'CAD',
        'Brazil': 'BRL',
        'Mexico': 'MXN',
    }
    
    def __init__(self, enable_cache: bool = True):
        """
        Initialize yfinance data fetcher.
        
        Args:
            enable_cache: Enable caching for exchange rates
        """
        self.currency_converter = CurrencyConverter()
        self.company_detector = CompanyDetector()
        logger.info("YFinanceDataFetcher initialized with currency conversion")
    
    def _get_reporting_currency(self, country: str, yfinance_currency: str) -> str:
        """
        Determine the reporting currency based on country of incorporation.
        
        Many foreign companies (TSM, SONY, etc.) trade in USD on US exchanges
        but report their financial statements in their home currency.
        
        Args:
            country: Country of incorporation
            yfinance_currency: Trading currency from yfinance
            
        Returns:
            Reporting currency code
        """
        if not country:
            return yfinance_currency
        
        # Check if country maps to a specific reporting currency
        reporting_currency = self.COUNTRY_CURRENCY_MAP.get(country)
        if reporting_currency:
            return reporting_currency
        
        return yfinance_currency
    
    def fetch_financial_data(self, ticker: str) -> Optional[YFinanceFinancialData]:
        """
        Fetch financial data for a ticker with currency conversion.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            YFinanceFinancialData with converted values, or None on error
        """
        ticker = ticker.upper().strip()
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            company_country = info.get('country', '')
            yfinance_currency = info.get('currency', 'USD')
            
            # Determine reporting currency based on country, not trading currency
            reporting_currency = self._get_reporting_currency(company_country, yfinance_currency)
            
            data = YFinanceFinancialData(
                ticker=ticker,
                company_name=info.get('longName') or info.get('shortName'),
                country=company_country,
                currency=reporting_currency,
                source_currency=reporting_currency,
                fetch_time=datetime.now().isoformat()
            )
            
            exchange_rate = self._get_exchange_rate(reporting_currency)
            data.exchange_rate_used = exchange_rate
            
            self._populate_basic_info(data, info, exchange_rate)
            self._populate_income_statement(data, stock.income_stmt, exchange_rate)
            self._populate_balance_sheet(data, stock.balance_sheet, exchange_rate)
            self._populate_cash_flow(data, stock.cashflow, exchange_rate)
            
            data.data_quality = self._assess_data_quality(data)
            
            if data.validate():
                if reporting_currency != 'USD':
                    logger.debug(f"Successfully fetched yfinance data for {ticker} ({reporting_currency} → USD at rate {exchange_rate:.4f})")
                else:
                    logger.debug(f"Successfully fetched yfinance data for {ticker} (USD)")
            else:
                logger.warning(f"Partial yfinance data for {ticker}")
            
            return data
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"Ticker not found or delisted: {ticker} (HTTP 404)")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch yfinance data for {ticker}: {e}")
            return None
    
    def _get_exchange_rate(self, currency: str) -> float:
        """Get exchange rate for currency to USD"""
        if currency.upper() == 'USD':
            return 1.0
        try:
            return self.currency_converter.get_rate(currency, 'USD')
        except CurrencyConversionError:
            logger.warning(f"Failed to get exchange rate for {currency}, using backup")
            return self.currency_converter._get_backup_rate(currency)
    
    def _populate_basic_info(self, data: YFinanceFinancialData, info: Dict, rate: float) -> None:
        """Populate basic company info"""
        if info.get('marketCap'):
            data.market_cap = info['marketCap'] * rate
        if info.get('currentPrice'):
            data.current_price = info['currentPrice']
        if info.get('trailingPE'):
            data.pe_ratio = info['trailingPE']
        data.sector = info.get('sector')
        data.industry = info.get('industry')
    
    def _populate_income_statement(self, data: YFinanceFinancialData, income_stmt: pd.DataFrame, rate: float) -> None:
        """Populate income statement data with currency conversion"""
        if income_stmt.empty:
            return
        
        latest = income_stmt.iloc[:, 0]
        
        data.revenue = self._get_value(latest, ['Total Revenue', 'Revenue'], rate)
        data.cogs = self._get_value(latest, ['Cost of Revenue', 'Cost Of Revenue'], rate)
        data.net_income = self._get_value(latest, ['Net Income', 'Net Income Common'], rate)
        data.operating_income = self._get_value(latest, ['Operating Income', 'Operating Income'], rate)
        data.ebit = data.operating_income
        
        if data.revenue is not None and data.cogs is not None:
            data.sga = data.revenue - data.cogs
        
        if data.operating_income is not None and data.net_income is not None:
            data.nopat = data.operating_income * 0.79
    
    def _populate_balance_sheet(self, data: YFinanceFinancialData, balance: pd.DataFrame, rate: float) -> None:
        """Populate balance sheet data with currency conversion"""
        if balance.empty:
            return
        
        latest = balance.iloc[:, 0]
        
        data.total_assets = self._get_value(latest, ['Total Assets'], rate)
        data.shareholder_equity = self._get_value(latest, ['Stockholders Equity', 'Shareholders Equity', 'Total Equity'], rate)
        data.total_debt = self._get_value(latest, ['Total Debt', 'Long Term Debt'], rate)
        data.retained_earnings = self._get_value(latest, ['Retained Earnings'], rate)
        
        current_assets = self._get_value(latest, ['Total Current Assets'], rate)
        current_liabilities = self._get_value(latest, ['Total Current Liabilities'], rate)
        
        if current_assets is not None and current_liabilities is not None:
            data.working_capital = current_assets - current_liabilities
    
    def _populate_cash_flow(self, data: YFinanceFinancialData, cashflow: pd.DataFrame, rate: float) -> None:
        """Populate cash flow data with currency conversion"""
        if cashflow.empty:
            return
        
        latest = cashflow.iloc[:, 0]
        
        data.operating_cash_flow = self._get_value(latest, ['Operating Cash Flow', 'Cash Flow From Operations'], rate)
        data.free_cash_flow = self._get_value(latest, ['Free Cash Flow'], rate)
        
        # Try multiple sources for interest expense:
        # 1. Interest Paid Supplemental Data (yfinance cashflow)
        # 2. Interest Expense (if available)
        interest_paid = self._get_value(latest, ['Interest Paid Supplemental Data'], rate)
        if interest_paid is not None:
            # Interest paid is typically positive in cashflow, convert to expense (positive number)
            data.interest_expense = abs(interest_paid)
        else:
            # Try standard interest expense field
            data.interest_expense = self._get_value(latest, ['Interest Expense'], rate)
        
        depreciation = self._get_value(latest, ['Depreciation'], rate)
        if data.ebit is not None and depreciation is not None:
            data.ebitda = data.ebit + depreciation
        elif data.ebit is not None:
            data.ebitda = data.ebit * 1.15
    
    def _get_value(self, row: pd.Series, field_names: List[str], rate: float) -> Optional[float]:
        """Get value from row with field name aliases and convert currency"""
        for field_name in field_names:
            if field_name in row.index:
                value = row[field_name]
                if pd.notna(value) and value != 0:
                    return value * rate
        return None
    
    def _assess_data_quality(self, data: YFinanceFinancialData) -> str:
        """Assess the quality of fetched data"""
        required = [
            data.revenue, data.total_assets,
            data.net_income, data.shareholder_equity
        ]
        if all(x is not None for x in required):
            return "complete"
        elif any(x is not None for x in required):
            return "partial"
        return "insufficient"
    
    def fetch_historical_financials(self, ticker: str, years: int = 5) -> Optional[Dict]:
        """
        Fetch historical financial data for ratio calculations.
        
        Args:
            ticker: Stock ticker symbol
            years: Number of years of history
            
        Returns:
            Dictionary with historical data or None on error
        """
        ticker = ticker.upper().strip()
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get reporting currency based on country, not trading currency
            company_country = info.get('country', '')
            yfinance_currency = info.get('currency', 'USD')
            source_currency = self._get_reporting_currency(company_country, yfinance_currency)
            rate = self._get_exchange_rate(source_currency)
            
            income_stmt = stock.income_stmt
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            
            if income_stmt.empty:
                return None
            
            historical_data = {
                'ticker': ticker,
                'source_currency': source_currency,
                'exchange_rate': rate,
                'years_available': min(len(income_stmt.columns), years),
                'income': [],
                'balance': [],
                'cash_flow': []
            }
            
            for i in range(min(len(income_stmt.columns), years)):
                row = income_stmt.iloc[:, i]
                historical_data['income'].append({
                    'fiscal_year': row.name.year if hasattr(row.name, 'year') else str(row.name)[:4],
                    'revenue': self._get_value(row, ['Total Revenue', 'Revenue'], rate),
                    'cogs': self._get_value(row, ['Cost of Revenue', 'Cost Of Revenue'], rate),
                    'operating_income': self._get_value(row, ['Operating Income'], rate),
                    'net_income': self._get_value(row, ['Net Income'], rate),
                    'ebit': self._get_value(row, ['Operating Income'], rate),
                })
            
            if not balance.empty:
                for i in range(min(len(balance.columns), years)):
                    row = balance.iloc[:, i]
                    historical_data['balance'].append({
                        'fiscal_year': row.name.year if hasattr(row.name, 'year') else str(row.name)[:4],
                        'total_assets': self._get_value(row, ['Total Assets'], rate),
                        'shareholder_equity': self._get_value(row, ['Stockholders Equity', 'Total Equity'], rate),
                        'total_debt': self._get_value(row, ['Total Debt'], rate),
                        'retained_earnings': self._get_value(row, ['Retained Earnings'], rate),
                        'working_capital': None
                    })
            
            if not cashflow.empty:
                for i in range(min(len(cashflow.columns), years)):
                    row = cashflow.iloc[:, i]
                    historical_data['cash_flow'].append({
                        'fiscal_year': row.name.year if hasattr(row.name, 'year') else str(row.name)[:4],
                        'operating_cash_flow': self._get_value(row, ['Operating Cash Flow'], rate),
                        'free_cash_flow': self._get_value(row, ['Free Cash Flow'], rate),
                        'interest_expense': self._get_value(row, ['Interest Expense'], rate),
                    })
            
            logger.debug(f"Fetched {historical_data['years_available']} years of historical data for {ticker}")
            return historical_data
            
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {ticker}: {e}")
            return None


def convert_yfinance_to_financial_data(yfinance_data: YFinanceFinancialData) -> 'FinancialData':
    """Convert YFinanceFinancialData to standard FinancialData format"""
    return yfinance_data.to_financial_data()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = YFinanceDataFetcher()
    
    print("YFinance Data Fetcher Test")
    print("=" * 80)
    
    test_tickers = ['TSM', 'SONY', 'AAPL']
    
    for ticker in test_tickers:
        print(f"\n--- Testing {ticker} ---")
        data = fetcher.fetch_financial_data(ticker)
        
        if data:
            print(f"  Company: {data.company_name}")
            print(f"  Country: {data.country}")
            print(f"  Currency: {data.source_currency} → USD")
            print(f"  Exchange Rate: {data.exchange_rate_used}")
            print(f"  Revenue: ${data.revenue/1e9:.1f}B" if data.revenue else "  Revenue: N/A")
            print(f"  Net Income: ${data.net_income/1e9:.1f}B" if data.net_income else "  Net Income: N/A")
            print(f"  Total Assets: ${data.total_assets/1e9:.1f}B" if data.total_assets else "  Total Assets: N/A")
            print(f"  Equity: ${data.shareholder_equity/1e9:.1f}B" if data.shareholder_equity else "  Equity: N/A")
            print(f"  OCF: ${data.operating_cash_flow/1e9:.1f}B" if data.operating_cash_flow else "  OCF: N/A")
            print(f"  Valid: {data.validate()}")
        else:
            print(f"  Failed to fetch data for {ticker}")
