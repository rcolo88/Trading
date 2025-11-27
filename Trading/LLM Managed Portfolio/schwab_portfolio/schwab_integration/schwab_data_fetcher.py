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
                logger.error("❌ Schwab API credentials required for operation")
                raise Exception("Schwab API credentials not configured")
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
            
            # Provide specific guidance for common errors
            if "RedirectServerExitedError" in str(e) or "callback URL" in str(e).lower():
                logger.error("🔧 CALLBACK URL ISSUE DETECTED:")
                logger.error("   1. Ensure your callback URL in schwab_credentials.json includes a port: 'https://127.0.0.1:8182'")
                logger.error("   2. Verify this EXACT URL is configured in your Schwab developer app settings")
                logger.error("   3. The callback URL must match exactly between your app and credentials file")
                logger.error("   4. Visit https://developer.schwab.com/ to update your app's callback URL")
            elif "api_key" in str(e).lower() or "app_secret" in str(e).lower():
                logger.error("🔧 CREDENTIALS ISSUE DETECTED:")
                logger.error("   1. Verify your API key and app secret in schwab_credentials.json")
                logger.error("   2. Ensure your Schwab developer app is in 'Ready for Use' status")
            else:
                logger.error("🔧 AUTHENTICATION TROUBLESHOOTING:")
                logger.error("   1. Check if your Schwab developer app is approved and active")
                logger.error("   2. Verify all credentials are correct")
                logger.error("   3. Try deleting schwab_token.json to force re-authentication")
            
            logger.error("❌ Failed to initialize Schwab API client")
            self.client = None
            raise Exception(f"Schwab API initialization failed: {e}")
    
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
    
    def fetch_current_data(self, holdings_tickers: List[str], benchmark_tickers: List[str] = None, prefer_close_prices: bool = False) -> Tuple[Optional[Dict], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
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
            logger.error("❌ Schwab API client not available")
            raise Exception("Schwab API client is required for operation")
        
        try:
            # Fetch current quotes using Schwab API
            current_prices = self._fetch_schwab_quotes(all_tickers, prefer_close_prices)
            
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
            logger.error("❌ Schwab API error, cannot continue without proper API access")
            raise Exception(f"Schwab API error: {e}")
    
    def _fetch_schwab_quotes(self, tickers: List[str], prefer_close_prices: bool = False) -> Optional[Dict[str, float]]:
        """Fetch current quotes from Schwab API"""
        try:
            current_prices = {}
            
            # Handle VIX separately - try different formats for Schwab
            processed_tickers = []
            for ticker in tickers:
                if ticker == '^VIX' or ticker == 'VIX':
                    # Try VIX without special symbols first, then $VIX.X if needed
                    processed_tickers.append('VIX')
                else:
                    processed_tickers.append(ticker)
            
            # Fetch quotes in batches or individually
            if len(processed_tickers) == 1:
                # Single ticker
                ticker = processed_tickers[0]
                original_ticker = tickers[0]
                logger.debug(f"🔍 Fetching single quote for: {ticker} -> {original_ticker}")
                
                response = self.client.get_quote(ticker)
                if response.status_code == 200:
                    quote_data = response.json()
                    logger.debug(f"🔍 Single quote response: {quote_data}")
                    
                    price = self._extract_price_from_quote(quote_data, prefer_close_prices)
                    if price:
                        current_prices[original_ticker] = price
                        logger.debug(f"✅ Successfully extracted single price for {original_ticker}: {price}")
                    else:
                        logger.warning(f"⚠️  Could not extract price from single quote for {ticker}")
                else:
                    logger.error(f"❌ Single quote request failed with status {response.status_code} for {ticker}")
            else:
                # Multiple tickers - use get_quotes
                response = self.client.get_quotes(processed_tickers)
                if response.status_code == 200:
                    quotes_data = response.json()
                    logger.debug(f"🔍 Full quotes response: {quotes_data}")
                    
                    # Check if the response is nested (common pattern)
                    if isinstance(quotes_data, dict) and len(quotes_data) == 1:
                        # Sometimes responses are nested, try to unwrap
                        first_key = next(iter(quotes_data))
                        if isinstance(quotes_data[first_key], dict):
                            quotes_data = quotes_data[first_key]
                            logger.debug(f"🔍 Unwrapped nested response: {quotes_data}")
                    
                    for i, ticker in enumerate(processed_tickers):
                        original_ticker = tickers[i]
                        logger.debug(f"🔍 Processing ticker: {ticker} -> {original_ticker}")
                        
                        if ticker in quotes_data:
                            price = self._extract_price_from_quote(quotes_data[ticker], prefer_close_prices)
                            if price:
                                current_prices[original_ticker] = price
                                logger.debug(f"✅ Successfully extracted price for {original_ticker}: {price}")
                            else:
                                logger.warning(f"⚠️  Could not extract price for {ticker}")
                        else:
                            logger.warning(f"⚠️  Ticker {ticker} not found in quotes response")
                            # Try variations of the ticker symbol
                            for key in quotes_data.keys():
                                if key.upper() == ticker.upper():
                                    price = self._extract_price_from_quote(quotes_data[key], prefer_close_prices)
                                    if price:
                                        current_prices[original_ticker] = price
                                        logger.debug(f"✅ Found price for {original_ticker} using key variation {key}: {price}")
                                        break
            
            return current_prices if current_prices else None
            
        except Exception as e:
            logger.error(f"❌ Error fetching Schwab quotes: {e}")
            return None
    
    def _extract_price_from_quote(self, quote_data: Dict, prefer_close_prices: bool = False) -> Optional[float]:
        """Extract current price from Schwab quote response"""
        try:
            # Debug: Log the actual response structure (only first few keys to avoid spam)
            top_keys = list(quote_data.keys())[:5] if isinstance(quote_data, dict) else []
            logger.debug(f"🔍 Schwab quote top-level keys: {top_keys}")
            
            # Schwab quote response is nested - look in different sections
            if isinstance(quote_data, dict):
                # Priority 1: Look in the 'quote' section (most recent market data)
                if 'quote' in quote_data and isinstance(quote_data['quote'], dict):
                    quote_section = quote_data['quote']
                    logger.debug(f"🔍 Found quote section with keys: {list(quote_section.keys())}")
                    
                    # Try price fields in order of preference within quote section
                    if prefer_close_prices:
                        # Prioritize close prices for after-hours reporting
                        quote_price_fields = ['closePrice', 'lastPrice', 'mark', 'bidPrice', 'askPrice']
                    else:
                        # Normal priority for live trading
                        quote_price_fields = ['lastPrice', 'mark', 'bidPrice', 'askPrice', 'closePrice']
                    for field in quote_price_fields:
                        if field in quote_section and quote_section[field] is not None:
                            try:
                                price = float(quote_section[field])
                                if price > 0:  # Sanity check
                                    logger.debug(f"✅ Found price {price} in quote.{field}")
                                    return price
                            except (ValueError, TypeError):
                                continue
                
                # Priority 2: Look in the 'regular' section (regular market data)
                if 'regular' in quote_data and isinstance(quote_data['regular'], dict):
                    regular_section = quote_data['regular']
                    logger.debug(f"🔍 Found regular section with keys: {list(regular_section.keys())}")
                    
                    if prefer_close_prices:
                        regular_price_fields = ['regularMarketPreviousClose', 'regularMarketLastPrice', 'lastPrice', 'price']
                    else:
                        regular_price_fields = ['regularMarketLastPrice', 'lastPrice', 'price', 'regularMarketPreviousClose']
                    for field in regular_price_fields:
                        if field in regular_section and regular_section[field] is not None:
                            try:
                                price = float(regular_section[field])
                                if price > 0:
                                    logger.debug(f"✅ Found price {price} in regular.{field}")
                                    return price
                            except (ValueError, TypeError):
                                continue
                
                # Priority 3: Try top-level price fields (fallback)
                if prefer_close_prices:
                    top_level_price_fields = ['close', 'closePrice', 'lastPrice', 'mark', 'price']
                else:
                    top_level_price_fields = ['lastPrice', 'mark', 'price', 'close', 'closePrice']
                for field in top_level_price_fields:
                    if field in quote_data and quote_data[field] is not None:
                        try:
                            price = float(quote_data[field])
                            if price > 0:
                                logger.debug(f"✅ Found price {price} in top-level {field}")
                                return price
                        except (ValueError, TypeError):
                            continue
                
                # Final fallback: Look for any numeric field > 1 (avoid boolean values)
                for key, value in quote_data.items():
                    if isinstance(value, (int, float)) and value > 1 and value < 10000:  # Reasonable price range
                        logger.debug(f"🔍 Trying fallback price field '{key}': {value}")
                        return float(value)
                        
                logger.warning(f"⚠️  No valid price found in quote data")
                
            return None
        except (ValueError, TypeError) as e:
            logger.error(f"❌ Error extracting price from quote: {e}")
            return None
    
    def _fetch_schwab_historical(self, tickers: List[str], days: int = 5) -> pd.DataFrame:
        """Fetch historical price data from Schwab API"""
        try:
            historical_data = {}
            
            for ticker in tickers:
                # Handle VIX separately - try simple VIX first
                schwab_ticker = 'VIX' if ticker in ['^VIX', 'VIX'] else ticker
                
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
            'api_source': 'Schwab API'
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