"""
Schwab API Market Data Fetching Module
Professional-grade replacement for yfinance using Schwab's official API
"""

import json
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import schwab
from schwab import auth
import logging

# Set up logging for Schwab API
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SchwabDataFetcher:
    """
    Professional market data fetcher using Schwab's official API
    Drop-in replacement for the yfinance-based DataFetcher
    """
    
    def __init__(self, config_path: str = None):
        """Initialize Schwab API client with authentication"""
        self.client = None
        self.price_data = pd.DataFrame()
        self.volume_data = pd.DataFrame()
        
        # Load configuration
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'schwab_credentials.json')
        
        self.config = self._load_config(config_path)
        
        # Initialize Schwab client
        self._initialize_client()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load Schwab API configuration from file"""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                logger.info(f"✅ Loaded Schwab API configuration from {config_path}")
                return config
            else:
                logger.warning(f"⚠️  Configuration file not found: {config_path}")
                logger.info("📝 Please create schwab_credentials.json with your API credentials")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"❌ Error loading Schwab configuration: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Return default configuration template"""
        return {
            "api_key": "YOUR_API_KEY_HERE",
            "app_secret": "YOUR_APP_SECRET_HERE",
            "callback_url": "https://127.0.0.1:8182",
            "token_path": "./schwab_token.json"
        }
    
    def _initialize_client(self):
        """Initialize authenticated Schwab API client"""
        try:
            # Check if we have valid credentials
            if (self.config['api_key'] == "YOUR_API_KEY_HERE" or 
                self.config['app_secret'] == "YOUR_APP_SECRET_HERE"):
                logger.warning("⚠️  Schwab API credentials not configured")
                logger.info("📝 Using fallback to yfinance functionality")
                self.client = None
                return
            
            # Initialize Schwab client with authentication
            self.client = auth.easy_client(
                api_key=self.config['api_key'],
                app_secret=self.config['app_secret'],
                callback_url=self.config['callback_url'],
                token_path=self.config['token_path']
            )
            
            logger.info("✅ Schwab API client initialized successfully")
            
            # Test the connection
            self._test_connection()
            
        except Exception as e:
            logger.error(f"❌ Error initializing Schwab client: {e}")
            logger.info("🔄 Falling back to yfinance functionality")
            self.client = None
    
    def _test_connection(self):
        """Test Schwab API connection with a simple quote request"""
        try:
            if self.client:
                # Test with a simple SPY quote
                response = self.client.get_quote('SPY')
                if response.status_code == 200:
                    logger.info("✅ Schwab API connection test successful")
                else:
                    logger.warning(f"⚠️  Schwab API test returned status: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Schwab API connection test failed: {e}")
    
    def fetch_current_data(self, holdings_tickers: List[str], benchmark_tickers: List[str] = None) -> Tuple[Optional[Dict], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """
        Fetch current price data using Schwab API
        Maintains same interface as original DataFetcher for compatibility
        """
        
        print("📡 Fetching current market data via Schwab API...")
        
        # Default benchmarks if not provided
        if benchmark_tickers is None:
            benchmark_tickers = ['SPY', 'IWM', '^VIX']
        
        all_tickers = holdings_tickers + benchmark_tickers
        print(f"🎯 Fetching data for tickers: {all_tickers}")
        
        if self.client is None:
            logger.warning("⚠️  Schwab API client not available, falling back to yfinance")
            return self._fallback_to_yfinance(all_tickers, holdings_tickers, benchmark_tickers)
        
        try:
            # Fetch current quotes using Schwab API
            current_prices = self._fetch_schwab_quotes(all_tickers)
            
            # Fetch historical data for analysis
            historical_data = self._fetch_schwab_historical(all_tickers)
            
            # Convert to expected format
            self.price_data = historical_data
            self.volume_data = pd.DataFrame()  # Volume data handled within price data
            
            if current_prices:
                print(f"✅ Successfully fetched Schwab data for {len(current_prices)} securities")
                if not historical_data.empty:
                    print(f"📅 Historical data range: {historical_data.index[0].date()} to {historical_data.index[-1].date()}")
                print(f"📊 Available tickers: {list(current_prices.keys())}")
                
                return current_prices, self.volume_data, self.price_data
            else:
                raise Exception("No current prices retrieved from Schwab API")
                
        except Exception as e:
            logger.error(f"❌ Error with Schwab API: {e}")
            logger.info("🔄 Falling back to yfinance")
            return self._fallback_to_yfinance(all_tickers, holdings_tickers, benchmark_tickers)
    
    def _fetch_schwab_quotes(self, tickers: List[str]) -> Optional[Dict[str, float]]:
        """Fetch current quotes from Schwab API"""
        try:
            current_prices = {}
            
            # Handle VIX separately (use $VIX.X for Schwab)
            processed_tickers = []
            for ticker in tickers:
                if ticker == '^VIX' or ticker == 'VIX':
                    processed_tickers.append('$VIX.X')  # Schwab VIX symbol
                else:
                    processed_tickers.append(ticker)
            
            # Fetch quotes in batches or individually
            if len(processed_tickers) == 1:
                # Single ticker
                response = self.client.get_quote(processed_tickers[0])
                if response.status_code == 200:
                    quote_data = response.json()
                    price = self._extract_price_from_quote(quote_data)
                    if price:
                        # Map back to original ticker name
                        original_ticker = tickers[0]
                        current_prices[original_ticker] = price
            else:
                # Multiple tickers - use get_quotes
                response = self.client.get_quotes(processed_tickers)
                if response.status_code == 200:
                    quotes_data = response.json()
                    
                    for i, ticker in enumerate(processed_tickers):
                        if ticker in quotes_data:
                            price = self._extract_price_from_quote(quotes_data[ticker])
                            if price:
                                # Map back to original ticker name
                                original_ticker = tickers[i]
                                current_prices[original_ticker] = price
            
            return current_prices if current_prices else None
            
        except Exception as e:
            logger.error(f"❌ Error fetching Schwab quotes: {e}")
            return None
    
    def _extract_price_from_quote(self, quote_data: Dict) -> Optional[float]:
        """Extract current price from Schwab quote response"""
        try:
            # Schwab quote response structure may vary, try multiple fields
            if isinstance(quote_data, dict):
                # Try different price fields in order of preference
                price_fields = ['lastPrice', 'mark', 'bidPrice', 'askPrice', 'closePrice']
                for field in price_fields:
                    if field in quote_data and quote_data[field] is not None:
                        return float(quote_data[field])
            return None
        except (ValueError, TypeError):
            return None
    
    def _fetch_schwab_historical(self, tickers: List[str], days: int = 5) -> pd.DataFrame:
        """Fetch historical price data from Schwab API"""
        try:
            historical_data = {}
            
            for ticker in tickers:
                # Handle VIX separately
                schwab_ticker = '$VIX.X' if ticker in ['^VIX', 'VIX'] else ticker
                
                try:
                    # Get daily price history for the last few days
                    response = self.client.get_price_history_every_day(
                        schwab_ticker, 
                        start_datetime=datetime.now() - timedelta(days=days),
                        end_datetime=datetime.now()
                    )
                    
                    if response.status_code == 200:
                        history_data = response.json()
                        
                        # Extract price series from Schwab response
                        price_series = self._parse_schwab_history(history_data)
                        if price_series is not None and len(price_series) > 0:
                            historical_data[ticker] = price_series
                            
                except Exception as e:
                    logger.warning(f"⚠️  Could not fetch history for {ticker}: {e}")
                    continue
            
            if historical_data:
                # Create DataFrame with common index
                df = pd.DataFrame(historical_data)
                df = df.ffill().bfill()  # Forward/backward fill missing data
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"❌ Error fetching Schwab historical data: {e}")
            return pd.DataFrame()
    
    def _parse_schwab_history(self, history_data: Dict) -> Optional[pd.Series]:
        """Parse Schwab price history response into pandas Series"""
        try:
            if 'candles' not in history_data:
                return None
            
            candles = history_data['candles']
            if not candles:
                return None
            
            # Extract dates and closing prices
            dates = []
            prices = []
            
            for candle in candles:
                # Schwab timestamp is in milliseconds
                timestamp = pd.to_datetime(candle['datetime'], unit='ms')
                close_price = candle['close']
                
                dates.append(timestamp)
                prices.append(close_price)
            
            if dates and prices:
                return pd.Series(prices, index=dates, name='Close')
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Error parsing Schwab history data: {e}")
            return None
    
    def _fallback_to_yfinance(self, all_tickers: List[str], holdings_tickers: List[str], benchmark_tickers: List[str]) -> Tuple[Optional[Dict], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Fallback to yfinance when Schwab API is unavailable"""
        try:
            # Import and use the original DataFetcher as fallback
            from data_fetcher import DataFetcher
            
            logger.info("🔄 Using yfinance fallback")
            fallback_fetcher = DataFetcher()
            return fallback_fetcher.fetch_current_data(holdings_tickers, benchmark_tickers)
            
        except Exception as e:
            logger.error(f"❌ Fallback to yfinance also failed: {e}")
            return None, None, None
    
    # Maintain compatibility with existing interface
    def get_current_prices(self, tickers: List[str]) -> Optional[Dict[str, float]]:
        """Get current prices for specific tickers - compatibility method"""
        current_prices, _, _ = self.fetch_current_data(tickers)
        return current_prices
    
    def calculate_benchmark_returns(self, current_prices: Dict[str, float], benchmarks: List[str] = None) -> Dict[str, float]:
        """Calculate benchmark returns - compatibility method"""
        if benchmarks is None:
            benchmarks = ['SPY', 'IWM', 'VIX']
        
        benchmark_returns = {}
        
        for benchmark in benchmarks:
            try:
                if benchmark in current_prices and benchmark in self.price_data.columns:
                    current_price = current_prices[benchmark]
                    
                    # Calculate various timeframe returns
                    prices = self.price_data[benchmark].dropna()
                    if len(prices) > 1:
                        # Daily return
                        if len(prices) >= 2:
                            daily_return = ((current_price - prices.iloc[-2]) / prices.iloc[-2]) * 100
                            benchmark_returns[f'{benchmark}_daily'] = daily_return
                        
                        # Weekly return (5 trading days)
                        if len(prices) >= 5:
                            week_ago_price = prices.iloc[-5]
                            weekly_return = ((current_price - week_ago_price) / week_ago_price) * 100
                            benchmark_returns[f'{benchmark}_weekly'] = weekly_return
                            
            except Exception as e:
                logger.error(f"❌ Error calculating {benchmark} returns: {e}")
        
        return benchmark_returns
    
    def get_volume_alerts(self, current_prices: Dict[str, float], volume_threshold_multiplier: float = 2.0) -> List[Dict[str, any]]:
        """Check for unusual volume activity - compatibility method"""
        # Volume alerts would need to be implemented with Schwab streaming API
        # For now, return empty list to maintain compatibility
        return []
    
    def data_quality_check(self) -> Dict[str, any]:
        """Perform data quality checks - compatibility method"""
        quality_report = {
            'has_price_data': not self.price_data.empty,
            'has_volume_data': not self.volume_data.empty,
            'tickers_with_data': list(self.price_data.columns) if not self.price_data.empty else [],
            'data_date_range': None,
            'missing_data_points': 0,
            'quality_score': 0,
            'api_source': 'Schwab API' if self.client else 'yfinance (fallback)'
        }
        
        if not self.price_data.empty:
            quality_report['data_date_range'] = {
                'start': str(self.price_data.index[0].date()),
                'end': str(self.price_data.index[-1].date()),
                'days': len(self.price_data)
            }
            
            # Count missing data points
            missing_count = self.price_data.isnull().sum().sum()
            total_points = self.price_data.size
            quality_report['missing_data_points'] = missing_count
            
            # Calculate quality score (0-100)
            if total_points > 0:
                quality_score = max(0, 100 - (missing_count / total_points * 100))
                quality_report['quality_score'] = round(quality_score, 2)
        
        return quality_report