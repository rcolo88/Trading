"""
Enhanced Hybrid Data Fetcher v4.0

Integrates yfinance + SimFin with automatic foreign company detection.

Strategy:
- US companies: SimFin (complete historical data, USD)
- Foreign companies: yfinance with currency conversion (TWD, JPY, etc.)
- FMP: REMOVED - SimFin provides all needed data without rate limits

Features:
- Automatic US vs Foreign company detection
- Live currency conversion for foreign companies
- Dual-source integration (yfinance + SimFin)
- No daily API limits (SimFin rate-limited per second, not per day)
- No premium symbol restrictions
"""

from .financial_data_fetcher import FinancialDataFetcher, FinancialData
from .simfin_fetcher import SimFinDataFetcher
from .ratio_calculator import FinancialRatioCalculator
from .company_detector import CompanyDetector, CompanyProfile
from .yfinance_fetcher import YFinanceDataFetcher, YFinanceFinancialData
from .currency_converter import CurrencyConversionError
from .stock_logger import get_stock_logger
from typing import Dict, Optional, List, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EnhancedHybridDataFetcher:
    """
    Enhanced hybrid data fetcher with automatic foreign company detection.
    
    Usage:
        fetcher = EnhancedHybridDataFetcher()
        data = fetcher.fetch_complete_data('GOOGL')  # US company → SimFin
        data = fetcher.fetch_complete_data('TSM')    # Foreign → yfinance + currency conversion
    
    Features:
    - Automatic US vs Foreign company detection
    - Live currency conversion for foreign companies
    - Dual-source integration (yfinance + SimFin)
    - No daily API limits (SimFin rate-limited per second, not per day)
    - No premium symbol restrictions
    """

    def __init__(
        self,
        simfin_api_key: Optional[str] = None,
        simfin_cache_file: str = "simfin_cache.pkl"
    ):
        """
        Initialize enhanced hybrid data fetcher with foreign detection.
        
        Args:
            simfin_api_key: SimFin API key (optional, for enhanced US company data)
            simfin_cache_file: Path to SimFin cache file
        """
        self.yf_fetcher = FinancialDataFetcher()
        self.yf_fetcher_foreign = YFinanceDataFetcher()
        self.company_detector = CompanyDetector()
        
        if simfin_api_key:
            self.simfin_fetcher = SimFinDataFetcher(
                api_key=simfin_api_key,
                cache_file=simfin_cache_file
            )
            self.ratio_calculator = FinancialRatioCalculator()
        else:
            self.simfin_fetcher = SimFinDataFetcher(cache_file=simfin_cache_file)
            self.ratio_calculator = FinancialRatioCalculator()
        
        logger.info("EnhancedHybridDataFetcher v4.0 initialized (SimFin-only, no FMP)")

    def fetch_complete_data(
        self,
        ticker: str,
        include_simfin: bool = True,
        force_refresh_simfin: bool = False
    ) -> Dict:
        """
        Fetch complete dataset with automatic foreign company detection and routing.
        
        Strategy:
        - US companies: yfinance (current) + SimFin (historical, USD)
        - Foreign companies: yfinance with currency conversion (TWD, JPY, etc.)
        - No FMP - SimFin provides all needed data without daily rate limits
        
        Args:
            ticker: Stock ticker symbol
            include_simfin: Whether to fetch SimFin data (default True)
            force_refresh_simfin: Force refresh SimFin cache
            
        Returns:
            Dict with merged data from all sources with source tagging
        """
        ticker = ticker.upper().strip()
        logger.debug(f"Fetching enhanced complete data for {ticker}")
        
        # Step 1: Detect company origin and determine routing
        company_profile = self.company_detector.detect(ticker)
        
        if company_profile.is_us_company:
            logger.debug(f"{ticker}: Detected as US company → Using SimFin for historical data")
            return self._fetch_us_company_data(
                ticker, company_profile, include_simfin, force_refresh_simfin
            )
        else:
            logger.debug(
                f"{ticker}: Detected as foreign company ({company_profile.country}) "
                f"→ Using yfinance with {company_profile.currency} → USD conversion"
            )
            return self._fetch_foreign_company_data(
                ticker, company_profile, include_simfin, force_refresh_simfin
            )
    
    def _fetch_us_company_data(
        self,
        ticker: str,
        company_profile: CompanyProfile,
        include_simfin: bool,
        force_refresh_simfin: bool
    ) -> Dict:
        """Fetch data for US company using SimFin with proper yfinance fallback"""
        
        # Step 1: Get current fundamentals from yfinance (always free)
        logger.debug(f"{ticker}: Fetching current data from yfinance...")
        current_data = self.yf_fetcher.fetch_financial_data(ticker)
        
        if not current_data or not hasattr(current_data, 'to_dict'):
            logger.error(f"Failed to fetch yfinance data for {ticker}")
            # Try foreign fetcher as last resort
            logger.debug(f"{ticker}: Attempting fallback with foreign yfinance fetcher...")
            current_data = self.yf_fetcher_foreign.fetch_financial_data(ticker)
            if not current_data or not hasattr(current_data, 'to_dict'):
                get_stock_logger().error(ticker, "All yfinance fetchers failed")
                return {}
        
        current_dict = current_data.to_dict()
        current_dict['company_profile'] = company_profile.to_dict()
        
        # Step 2: Get SimFin data (if enabled) - PRIMARY source for US companies
        simfin_data = {}
        simfin_ratios = {}
        if include_simfin:
            logger.debug(f"{ticker}: Fetching data from SimFin...")
            
            simfin_current = self.simfin_fetcher.fetch_financial_data(ticker)
            if simfin_current:
                simfin_dict = simfin_current.to_dict()
                simfin_data = simfin_dict
                
                # Calculate ratios from SimFin raw data
                simfin_ratios = self._calculate_simfin_ratios(simfin_current)
                
                # Get historical data for growth calculations
                simfin_historical = self.simfin_fetcher.fetch_historical_financials(ticker)
                if simfin_historical:
                    simfin_data['simfin_historical'] = simfin_historical
            else:
                get_stock_logger().warning(ticker, "SimFin data not available, using yfinance historical data")
        
        # Step 3: If SimFin historical data is missing, fall back to yfinance historical
        yfinance_historical = {}
        if not simfin_data.get('simfin_historical'):
            logger.debug(f"{ticker}: Fetching historical data from yfinance (SimFin fallback)...")
            yfinance_historical = self.yf_fetcher_foreign.fetch_historical_financials(ticker, years=5)
            if yfinance_historical:
                simfin_data['yfinance_historical'] = yfinance_historical
        
        # Step 4: Handle case where SimFin failed completely - enhance with yfinance data
        if not simfin_data and current_dict:
            logger.debug(f"{ticker}: SimFin failed completely, enhancing with yfinance data...")
            # Copy key yfinance fields to simfin_data structure for consistency
            for field in ['revenue', 'net_income', 'total_assets', 'shareholder_equity', 
                         'total_debt', 'free_cash_flow', 'ebit', 'ebitda', 'interest_expense',
                         'retained_earnings', 'working_capital', 'operating_income']:
                if current_dict.get(field) is not None:
                    simfin_data[field] = current_dict.get(field)
            
            # Mark that this is yfinance-only data
            simfin_data['data_quality'] = current_dict.get('data_quality', 'partial')
        
        # Step 5: Merge all datasets (no FMP)
        merged_data = self._merge_enhanced_data(
            current_dict, simfin_data, simfin_ratios, ticker
        )
        
        # Add company profile info
        merged_data['is_foreign_company'] = False
        merged_data['company_country'] = 'US'
        merged_data['data_source'] = 'yfinance + SimFin' if simfin_data else 'yfinance (SimFin unavailable)'
        
        return merged_data
    
    def _fetch_foreign_company_data(
        self,
        ticker: str,
        company_profile: CompanyProfile,
        include_simfin: bool,
        force_refresh_simfin: bool
    ) -> Dict:
        """Fetch data for foreign company using yfinance with currency conversion"""
        
        # Step 1: Get current fundamentals from yfinance (with currency conversion)
        logger.debug(f"{ticker}: Fetching data from yfinance with {company_profile.currency} → USD conversion...")
        yf_data = self.yf_fetcher_foreign.fetch_financial_data(ticker)
        
        if not yf_data or not hasattr(yf_data, 'to_dict'):
            logger.error(f"Failed to fetch yfinance data for {ticker}")
            return {}
        
        current_dict = yf_data.to_dict()
        current_dict['company_profile'] = company_profile.to_dict()
        
        # Add exchange rate info
        current_dict['exchange_rate'] = yf_data.exchange_rate_used
        current_dict['source_currency'] = yf_data.source_currency
        
        # Step 2: Get historical data from yfinance (with currency conversion)
        yf_historical = {}
        if include_simfin:
            logger.debug(f"{ticker}: Fetching historical data from yfinance...")
            yf_historical = self.yf_fetcher_foreign.fetch_historical_financials(ticker, years=5)
            if yf_historical:
                current_dict['yfinance_historical'] = yf_historical
        
        # Step 3: No SimFin for foreign companies
        simfin_data = {}
        simfin_ratios = {}
        
        # Step 4: Merge all datasets (no FMP)
        merged_data = self._merge_enhanced_data(
            current_dict, simfin_data, simfin_ratios, ticker
        )
        
        # Add company profile info
        merged_data['is_foreign_company'] = True
        merged_data['company_country'] = company_profile.country
        merged_data['data_source'] = f'yfinance ({company_profile.currency} → USD)'
        merged_data['currency'] = company_profile.currency
        merged_data['exchange_rate'] = yf_data.exchange_rate_used
        
        logger.debug(
            f"{ticker}: Foreign company data complete "
            f"({company_profile.currency} → USD at rate {yf_data.exchange_rate_used:.4f})"
        )
        
        return merged_data

    def _calculate_simfin_ratios(self, simfin_data) -> Dict[str, Any]:
        """
        Calculate ratios from SimFin raw data
        
        Args:
            simfin_data: SimFinFinancialData object
            
        Returns:
            Dict of calculated ratios with source tagging
        """
        if not simfin_data:
            return {}
        
        try:
            # Calculate all ratios using the ratio calculator
            calculated_ratios = self.ratio_calculator.calculate_all_ratios(
                revenue=simfin_data.revenue,
                cogs=simfin_data.cogs,
                operating_income=simfin_data.operating_income,
                net_income=simfin_data.net_income,
                total_assets=simfin_data.total_assets,
                shareholder_equity=simfin_data.shareholder_equity,
                total_debt=simfin_data.total_debt,
                retained_earnings=simfin_data.retained_earnings,
                working_capital=simfin_data.working_capital,
                ebit=simfin_data.ebit,
                ebitda=simfin_data.ebitda,
                interest_expense=simfin_data.interest_expense,
                operating_cash_flow=simfin_data.operating_cash_flow,
                free_cash_flow=simfin_data.free_cash_flow
            )
            
            # Convert to dict with source tagging
            ratios_dict = calculated_ratios.to_dict()
            
            logger.debug(f"Calculated {sum(1 for v in ratios_dict.values() if v is not None)} SimFin ratios")
            return ratios_dict
            
        except Exception as e:
            logger.error(f"Failed to calculate SimFin ratios: {e}")
            return {}

    def _merge_enhanced_data(
        self,
        current: Dict,
        simfin_data: Dict,
        simfin_ratios: Dict,
        ticker: str
    ) -> Dict:
        """
        Merge data from yfinance and SimFin with intelligent source tagging
        
        Priority and Strategy:
        1. yfinance: Current year fundamentals (always primary)
        2. SimFin: Raw data + calculated ratios (no FMP)
        3. Source tagging: All metrics tagged with source for comparison
        
        Args:
            current: yfinance current data dict
            simfin_data: SimFin current data dict
            simfin_ratios: SimFin calculated ratios dict
            ticker: Stock ticker for logging
            
        Returns:
            Enhanced merged dataset with source tagging
        """
        # Start with yfinance current data as base
        merged = current.copy()
        
        # Add metadata
        merged['data_sources'] = []
        merged['fetch_timestamp'] = datetime.now().isoformat()
        
        # Add yfinance to sources
        merged['data_sources'].append('yfinance')
        
        # Add SimFin data with source tagging
        if simfin_data:
            merged['data_sources'].append('SimFin')

            # Add SimFin-specific metadata
            merged['simfin_years_available'] = simfin_data.get('years_available', 0)
            merged['simfin_data_quality'] = simfin_data.get('data_quality', 'unknown')
            merged['simfin_fiscal_year'] = simfin_data.get('fiscal_year')

            # Add key SimFin financial metrics with source tagging
            simfin_metrics = [
                'revenue', 'net_income', 'total_assets', 'shareholder_equity',
                'total_debt', 'ebit', 'ebitda', 'interest_expense',
                'operating_cash_flow', 'free_cash_flow', 'retained_earnings',
                'working_capital', 'operating_income'
            ]
            for metric in simfin_metrics:
                if simfin_data.get(metric) is not None:
                    merged[f'simfin_{metric}'] = simfin_data.get(metric)

            # Add SimFin calculated ratios with source tagging
            if simfin_ratios:
                merged.update(simfin_ratios)

            # Extract SimFin historical trends for ROE persistence analysis
            if simfin_data and not merged.get('roe_history'):
                simfin_historical = simfin_data.get('simfin_historical', {})
                if simfin_historical:
                    simfin_trends = self._extract_simfin_historical_trends(simfin_historical)
                    merged.update(simfin_trends)
        
        # Add data quality and validation metadata
        merged['data_quality_score'] = self._calculate_data_quality_score(merged)
        merged['has_historical_data'] = bool(
            merged.get('roe_history') or merged.get('simfin_historical')
        )
        
        # No FMP, so SimFin is always used
        merged['simfin_used_as_fallback'] = False
        
        logger.debug(
            f"{ticker}: Enhanced merge complete with {len(merged['data_sources'])} sources, "
            f"quality score: {merged.get('data_quality_score', 'N/A')}"
        )
        
        return merged

    def _calculate_data_quality_score(self, merged: Dict) -> float:
        """Calculate overall data quality score (0-100)"""
        score = 0.0
        
        # Base score for having yfinance data
        if merged.get('ticker'):
            score += 30
        
        # Bonus for SimFin data
        if 'SimFin' in merged.get('data_sources', []):
            score += 35
            if merged.get('simfin_years_available', 0) >= 3:
                score += 10
        
        # Bonus for having historical data
        if merged.get('has_historical_data'):
            score += 15
        
        # Bonus for having both sources (validation capability)
        if len(merged.get('data_sources', [])) >= 2:
            score += 10
        
        return min(score, 100.0)

    def batch_fetch_enhanced(
        self,
        tickers: List[str],
        include_simfin: bool = True,
        max_workers: int = 5
    ) -> Dict[str, Dict]:
        """
        Batch fetch enhanced data for multiple tickers
        
        Args:
            tickers: List of ticker symbols
            include_simfin: Whether to include SimFin data
            max_workers: Number of parallel workers
            
        Returns:
            Dict mapping ticker -> enhanced merged data
        """
        results = {}
        
        logger.info(f"Starting enhanced batch fetch for {len(tickers)} tickers")
        
        for i, ticker in enumerate(tickers):
            logger.debug(f"Enhanced batch fetch {i+1}/{len(tickers)}: {ticker}")
            
            try:
                data = self.fetch_complete_data(
                    ticker=ticker,
                    include_simfin=include_simfin
                )
                results[ticker] = data
                
            except Exception as e:
                logger.error(f"Failed to fetch enhanced data for {ticker}: {e}")
                results[ticker] = {}
        
        # Calculate statistics
        successful = sum(1 for data in results.values() if data)
        simfin_available = sum(1 for data in results.values() if 'SimFin' in data.get('data_sources', []))
        
        logger.debug(
            f"Enhanced batch fetch complete: {successful}/{len(tickers)} successful, "
            f"SimFin: {simfin_available}"
        )
        
        return results

    def get_data_source_summary(self, tickers: List[str]) -> Dict[str, Any]:
        """
        Get summary of data sources for a list of tickers
        
        Args:
            tickers: List of ticker symbols to analyze
            
        Returns:
            Summary of data source coverage and quality
        """
        summary = {
            'total_tickers': len(tickers),
            'yfinance_coverage': 0,
            'simfin_coverage': 0,
            'dual_source_coverage': 0,
            'average_quality_score': 0.0,
            'blocked_symbols_simfin': []
        }
        
        # This would require actual fetching - for now return structure
        return summary

    def _extract_simfin_historical_trends(self, historical_data: Dict) -> Dict:
        """
        Extract historical trends from SimFin balance/income data.
        
        This is used when FMP data is not available (premium-only symbols like FISV)
        to provide ROE history for persistence analysis.
        
        Args:
            historical_data: SimFin historical data dict with 'balance' and 'income' keys
            
        Returns:
            Dict with 'roe_history' and other historical trends
        """
        trends = {}
        
        balance_data = historical_data.get('balance', [])
        income_data = historical_data.get('income', [])
        
        # Create lookup for net income by fiscal year
        net_income_by_year = {}
        for year_data in income_data:
            fiscal_year = year_data.get('fiscal_year')
            net_income = year_data.get('net_income')
            if fiscal_year and net_income is not None:
                net_income_by_year[fiscal_year] = net_income
        
        # Calculate ROE: net_income / shareholder_equity
        roe_history = []
        for year_data in balance_data:
            equity = year_data.get('shareholder_equity', 0)
            fiscal_year = year_data.get('fiscal_year')
            net_income = net_income_by_year.get(fiscal_year, 0) if fiscal_year else 0
            
            if equity and equity > 0 and net_income:
                roe_history.append(net_income / equity)
        
        trends['roe_history'] = roe_history
        
        # Extract revenue history from income statements
        revenue_history = [
            year.get('revenue', 0)
            for year in income_data
        ]
        trends['revenue_history'] = revenue_history
        
        logger.debug(f"Extracted {len(roe_history)} years of ROE from SimFin historical data")
        
        return trends


# Example usage
if __name__ == "__main__":
    # Initialize enhanced fetcher (SimFin-only, no FMP)
    fetcher = EnhancedHybridDataFetcher(
        simfin_api_key='YOUR_SIMFIN_KEY'  # Optional, uses free tier if not provided
    )
    
    # Example 1: Fetch enhanced data for a single ticker
    print("\n" + "="*60)
    print("Example: Enhanced data fetch for AAPL")
    print("="*60)
    
    data = fetcher.fetch_complete_data('AAPL')
    print(f"Data Sources: {data.get('data_sources', [])}")
    print(f"Quality Score: {data.get('data_quality_score', 'N/A')}")
    print(f"SimFin Years: {data.get('simfin_years_available', 'N/A')}")
    print(f"ROE History: {len(data.get('roe_history', []))} years")
    print(f"SimFin ROE: {data.get('simfin_roe', 'N/A')}")
    
    # Example 2: Batch fetch with enhanced data
    print("\n" + "="*60)
    print("Example: Enhanced batch fetch")
    print("="*60)
    
    tickers = ['AAPL', 'MSFT', 'GOOGL']
    results = fetcher.batch_fetch_enhanced(tickers)
    
    for ticker, data in results.items():
        sources = data.get('data_sources', [])
        quality = data.get('data_quality_score', 0)
        print(f"  {ticker}: {' + '.join(sources)} (Quality: {quality:.0f})")