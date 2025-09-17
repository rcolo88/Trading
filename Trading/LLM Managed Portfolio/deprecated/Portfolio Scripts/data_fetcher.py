"""
Market Data Fetching Module
Handles all yfinance integration and market data retrieval
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional


class DataFetcher:
    """Handles market data fetching and processing"""
    
    def __init__(self):
        self.price_data = pd.DataFrame()
        self.volume_data = pd.DataFrame()
    
    def fetch_current_data(self, holdings_tickers: List[str], benchmark_tickers: List[str] = None) -> Tuple[Optional[Dict], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Fetch current price data for all holdings and benchmarks"""
        
        print("📡 Fetching current market data...")
        
        # Default benchmarks if not provided
        if benchmark_tickers is None:
            benchmark_tickers = ['SPY', 'IWM']  # Remove VIX for now
        
        all_tickers = holdings_tickers + benchmark_tickers
        print(f"🎯 Fetching data for tickers: {all_tickers}")
        
        try:
            # Fetch data with more robust handling
            start_fetch_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            raw_data = yf.download(all_tickers, start=start_fetch_date, progress=False, auto_adjust=True)
            
            # Handle different data structures from yfinance
            if raw_data.empty:
                print("❌ No data returned from yfinance - falling back to individual fetching")
                raise Exception("Bulk download failed - triggering fallback")
            
            # Handle multi-ticker vs single ticker cases
            if len(all_tickers) == 1:
                if 'Adj Close' in raw_data.columns:
                    self.price_data = pd.DataFrame({all_tickers[0]: raw_data['Adj Close']})
                else:
                    self.price_data = pd.DataFrame({all_tickers[0]: raw_data['Close']})
            else:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if 'Adj Close' in raw_data.columns.get_level_values(0):
                        self.price_data = raw_data['Adj Close']
                    elif 'Close' in raw_data.columns.get_level_values(0):
                        self.price_data = raw_data['Close']
                    else:
                        print("❌ Could not find price data columns - falling back to individual fetching")
                        raise Exception("Column structure issue - triggering fallback")
                else:
                    self.price_data = raw_data
            
            # Verify we have holdings data (not just benchmarks)
            holdings_found = [ticker for ticker in holdings_tickers if ticker in self.price_data.columns]
            if len(holdings_found) == 0:
                print("❌ No holdings data found in bulk download - falling back to individual fetching")
                raise Exception("No holdings data - triggering fallback")
            
            # Get volume data separately (excluding VIX which doesn't have volume)
            try:
                volume_raw = yf.download(all_tickers, start=start_fetch_date, progress=False, auto_adjust=True)
                if isinstance(volume_raw.columns, pd.MultiIndex) and 'Volume' in volume_raw.columns.get_level_values(0):
                    volume_data = volume_raw['Volume']
                else:
                    volume_data = pd.DataFrame()  # Empty if volume data unavailable
            except:
                volume_data = pd.DataFrame()
            
            # Try to get VIX separately using alternative ticker
            try:
                if 'VIX' not in self.price_data.columns:
                    print("🔍 Attempting to fetch VIX data separately...")
                    vix_data = yf.download('^VIX', start=start_fetch_date, progress=False, auto_adjust=True)
                    if not vix_data.empty:
                        if 'Close' in vix_data.columns:
                            vix_prices = vix_data['Close']
                        else:
                            vix_prices = vix_data.iloc[:, 0]  # Take first column
                        
                        # Add VIX to price data
                        self.price_data.loc[:, 'VIX'] = vix_prices
                        print("✅ VIX data fetched successfully using ^VIX")
                    else:
                        print("⚠️  VIX data unavailable - continuing without VIX")
            except Exception as e:
                print(f"⚠️  VIX fetch failed: {e} - continuing without VIX")
            
            # Clean up data
            self.price_data = self.price_data.ffill().bfill()
            
            # Store volume data
            self.volume_data = volume_data
            
            # Verify we have some data
            if self.price_data.empty:
                print("❌ Price data is empty after processing - falling back to individual fetching")
                raise Exception("Empty price data - triggering fallback")
            
            print(f"✅ Successfully fetched data for {len(self.price_data.columns)} securities")
            print(f"📅 Data range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
            print(f"📊 Available tickers: {list(self.price_data.columns)}")
            
            # Extract current prices (most recent row)
            current_prices = self.price_data.iloc[-1].to_dict()
            
            # Verify we have prices for holdings
            holdings_with_prices = [ticker for ticker in holdings_tickers if ticker in current_prices]
            if len(holdings_with_prices) < len(holdings_tickers):
                print(f"⚠️  Missing prices for some holdings: {set(holdings_tickers) - set(holdings_with_prices)}")
            
            # Return the tuple that generate_report expects
            return current_prices, self.volume_data, self.price_data
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            print("🔄 Trying alternative approach...")
            
            # Alternative approach: fetch tickers individually
            success = self.fetch_data_individually(all_tickers + ['^VIX'])
            if success:
                # If successful, extract and return the data
                current_prices = self.price_data.iloc[-1].to_dict() if not self.price_data.empty else {}
                return current_prices, self.volume_data, self.price_data
            else:
                return None, None, None
    
    def fetch_data_individually(self, tickers: List[str]) -> bool:
        """Fallback method to fetch data for each ticker individually"""
        
        print("🔄 Fetching tickers individually...")
        
        price_data_dict = {}
        successful_tickers = []
        common_index = None
        
        for ticker in tickers:
            # Use ^VIX for VIX data
            fetch_ticker = '^VIX' if ticker == 'VIX' else ticker
            
            try:
                print(f"   Fetching {ticker}...")
                start_fetch_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                ticker_data = yf.download(fetch_ticker, start=start_fetch_date, progress=False, auto_adjust=True)
                
                if not ticker_data.empty and len(ticker_data) > 0:
                    # Extract price series - handle MultiIndex columns from yfinance
                    price_series = None
                    
                    # Check if columns are MultiIndex (like ('Close', 'IONS'))
                    if isinstance(ticker_data.columns, pd.MultiIndex):
                        # Look for Close or Adj Close in the first level
                        if ('Close', ticker) in ticker_data.columns:
                            price_series = ticker_data[('Close', ticker)]
                        elif ('Adj Close', ticker) in ticker_data.columns:
                            price_series = ticker_data[('Adj Close', ticker)]
                        else:
                            # Find any price column for this ticker
                            price_cols = [col for col in ticker_data.columns if col[1] == ticker and col[0] in ['Close', 'Adj Close', 'Open', 'High', 'Low']]
                            if price_cols:
                                price_series = ticker_data[price_cols[0]]
                    else:
                        # Simple column structure
                        if 'Close' in ticker_data.columns:
                            price_series = ticker_data['Close']
                        elif 'Adj Close' in ticker_data.columns:
                            price_series = ticker_data['Adj Close']
                        else:
                            numeric_cols = ticker_data.select_dtypes(include=[np.number]).columns
                            if len(numeric_cols) > 0:
                                price_series = ticker_data[numeric_cols[0]]
                    
                    # Ensure we have a proper time series (not just a scalar)
                    if price_series is not None and isinstance(price_series, pd.Series) and len(price_series) > 0:
                        # Remove any NaN values
                        price_series = price_series.dropna()
                        if len(price_series) > 0:
                            price_data_dict[ticker] = price_series
                            successful_tickers.append(ticker)
                            
                            # Store the index for alignment
                            if common_index is None:
                                common_index = price_series.index
                            else:
                                # Use intersection to ensure all series have common dates
                                common_index = common_index.intersection(price_series.index)
                        else:
                            print(f"   ⚠️  No valid price data after removing NaN for {ticker}")
                    else:
                        print(f"   ⚠️  Invalid price series for {ticker}")
                else:
                    print(f"   ⚠️  No data for {ticker}")
                    
            except Exception as e:
                print(f"   ❌ Failed to fetch {ticker}: {e}")
        
        if price_data_dict and common_index is not None and len(common_index) > 0:
            # Align all series to common index and create DataFrame
            aligned_data = {}
            for ticker, series in price_data_dict.items():
                # Reindex to common dates
                aligned_series = series.reindex(common_index)
                if not aligned_series.empty:
                    aligned_data[ticker] = aligned_series
            
            if aligned_data:
                self.price_data = pd.DataFrame(aligned_data, index=common_index)
                self.price_data = self.price_data.ffill().bfill()
                
                # Initialize empty volume data
                self.volume_data = pd.DataFrame()
                
                print(f"✅ Successfully fetched {len(aligned_data)} out of {len(tickers)} tickers")
                print(f"📊 Available data: {list(aligned_data.keys())}")
                
                if len(self.price_data) > 0:
                    print(f"📅 Data range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
                    return True
        
        print("❌ Could not fetch any valid data")
        self.price_data = pd.DataFrame()
        self.volume_data = pd.DataFrame()
        return False
    
    def get_current_prices(self, tickers: List[str]) -> Optional[Dict[str, float]]:
        """Get current prices for specific tickers"""
        if self.price_data.empty:
            return None
        
        current_prices = {}
        latest_row = self.price_data.iloc[-1]
        
        for ticker in tickers:
            if ticker in latest_row.index and pd.notna(latest_row[ticker]):
                current_prices[ticker] = float(latest_row[ticker])
        
        return current_prices if current_prices else None
    
    def get_historical_data(self, ticker: str, days: int = 30) -> Optional[pd.Series]:
        """Get historical price data for a specific ticker"""
        if self.price_data.empty or ticker not in self.price_data.columns:
            return None
        
        # Get last N days of data
        end_date = self.price_data.index[-1]
        start_date = end_date - timedelta(days=days)
        
        historical_data = self.price_data[ticker]
        return historical_data[historical_data.index >= start_date]
    
    def calculate_benchmark_returns(self, current_prices: Dict[str, float], benchmarks: List[str] = None) -> Dict[str, float]:
        """Calculate benchmark returns"""
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
                        
                        # Monthly return (20 trading days)
                        if len(prices) >= 20:
                            month_ago_price = prices.iloc[-20]
                            monthly_return = ((current_price - month_ago_price) / month_ago_price) * 100
                            benchmark_returns[f'{benchmark}_monthly'] = monthly_return
                            
            except Exception as e:
                print(f"❌ Error calculating {benchmark} returns: {e}")
        
        return benchmark_returns
    
    def get_volume_alerts(self, current_prices: Dict[str, float], volume_threshold_multiplier: float = 2.0) -> List[Dict[str, any]]:
        """Check for unusual volume activity"""
        volume_alerts = []
        
        if self.volume_data.empty:
            return volume_alerts
        
        try:
            # Get the most recent volume data
            latest_volume = self.volume_data.iloc[-1]
            
            for ticker in current_prices.keys():
                if ticker in latest_volume.index and ticker in self.volume_data.columns:
                    current_volume = latest_volume[ticker]
                    
                    # Calculate average volume over last 20 days
                    ticker_volume_history = self.volume_data[ticker].dropna()
                    if len(ticker_volume_history) >= 20:
                        avg_volume = ticker_volume_history.iloc[-20:].mean()
                        
                        if current_volume > (avg_volume * volume_threshold_multiplier):
                            volume_ratio = current_volume / avg_volume
                            volume_alerts.append({
                                'ticker': ticker,
                                'current_volume': current_volume,
                                'average_volume': avg_volume,
                                'volume_ratio': volume_ratio,
                                'alert_type': 'HIGH_VOLUME'
                            })
                            
        except Exception as e:
            print(f"❌ Error checking volume alerts: {e}")
        
        return volume_alerts
    
    def data_quality_check(self) -> Dict[str, any]:
        """Perform data quality checks on fetched data"""
        quality_report = {
            'has_price_data': not self.price_data.empty,
            'has_volume_data': not self.volume_data.empty,
            'tickers_with_data': list(self.price_data.columns) if not self.price_data.empty else [],
            'data_date_range': None,
            'missing_data_points': 0,
            'quality_score': 0
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