# Daily Portfolio Data Collection Script
# Run this daily and paste the output to Claude for analysis

import yfinance as yf
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import json
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging
import glob
import re

# Configure trade execution logger
trade_logger = logging.getLogger('trade_execution')
trade_logger.setLevel(logging.INFO)

# Create file handler - this ensures the log file gets written
if not trade_logger.handlers:  # Prevent duplicate handlers
    handler = logging.FileHandler('trade_execution.log')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    trade_logger.addHandler(handler)

# PDF support (add to your existing imports)
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    try:
        import PyPDF2
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# Configure logging for trade execution
trade_logger = logging.getLogger('trade_execution')
trade_logger.setLevel(logging.INFO)
handler = logging.FileHandler('trade_execution.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
trade_logger.addHandler(handler)

class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    REDUCE = "REDUCE"
    HOLD = "HOLD"

class OrderPriority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class PartialFillMode(Enum):
    """Configuration options for handling partial fills when insufficient cash"""
    AUTOMATIC = "AUTOMATIC"        # Always fill max affordable shares
    ASK_CONFIRMATION = "ASK"       # Ask user for each partial fill  
    REJECT = "REJECT"              # Reject orders that can't be filled completely
    SMART = "SMART"                # Auto-fill if >threshold% affordable, ask if below

    def __str__(self):
        """String representation for logging"""
        return self.value
    
    def __repr__(self):
        """Developer representation"""
        return f"PartialFillMode.{self.name}"
    
    @classmethod
    def from_string(cls, value: str):
        """Create enum from string value"""
        value = value.upper()
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"Invalid PartialFillMode: {value}")
    
    @property
    def description(self):
        """Human-readable description of the mode"""
        descriptions = {
            self.AUTOMATIC: "Automatically fills maximum affordable shares",
            self.ASK_CONFIRMATION: "Asks for confirmation before partial fills",
            self.REJECT: "Rejects any orders that cannot be filled completely", 
            self.SMART: "Auto-fills if >80% affordable, asks confirmation if <80%"
        }
        return descriptions[self]
    
    @property
    def requires_user_input(self):
        """Whether this mode may require user interaction"""
        return self in [self.ASK_CONFIRMATION, self.SMART]
@dataclass
class TradeOrder:
    """Represents a single trade order"""
    ticker: str
    action: OrderType
    shares: Optional[int] = None
    target_weight: Optional[float] = None
    target_value: Optional[float] = None
    reason: str = ""
    priority: OrderPriority = OrderPriority.MEDIUM
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    profit_target: Optional[float] = None

@dataclass
class TradeResult:
    """Represents the result of an executed trade"""
    order: TradeOrder
    executed: bool
    execution_price: Optional[float]
    executed_shares: Optional[int]
    execution_value: Optional[float]
    error_message: Optional[str]
    timestamp: datetime


class DailyPortfolioReport:
    # == 1. INITIALIZATION ==
    def __init__(self):
        # Updated portfolio holdings (from your corrected allocation)
        self.holdings = {
            'IONS': {'shares': 3, 'entry_price': 37.01, 'allocation': 111.03},  # Reduced from 4 shares
            'CRGY': {'shares': 26, 'entry_price': 9.10, 'allocation': 236.60},  # No change
            'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45}, # No change
            'CYTK': {'shares': 6, 'entry_price': 36.58, 'allocation': 219.48},  # No change
            'SOUN': {'shares': 19, 'entry_price': 11.01, 'allocation': 209.19}, # No change
            'QS': {'shares': 23, 'entry_price': 8.50, 'allocation': 138.00},    # No change
            'RIG': {'shares': 65, 'entry_price': 3.00, 'allocation': 195.00},   # No change
            'AMD': {'shares': 1, 'entry_price': 176.78, 'allocation': 176.78},  # No change
            'NVDA': {'shares': 1, 'entry_price': 175.00, 'allocation': 135.00}, # NEW POSITION
            'GOOGL': {'shares': 1, 'entry_price': 193.00, 'allocation': 193.00} # NEW POSITION
        }

        self.benchmarks = ['SPY', 'IWM', 'VIX']
        self.total_investment = 1964.58  # Unchanged - original investment
        self.cash = 2.34  # Minimal cash remaining
        self.load_portfolio_state()
    

    # == 2. CONFIGURATION METHODS ==
    def set_partial_fill_mode(self, mode: PartialFillMode, min_cash_reserve: float = None, 
                          threshold: float = None):
        """Configure partial fill behavior"""
        self.partial_fill_mode = mode
        if min_cash_reserve is not None:
            self.min_cash_reserve = min_cash_reserve
        if threshold is not None:
            self.partial_fill_threshold = threshold
        
        print(f"📊 Partial Fill Configuration Updated:")
        print(f"   Mode: {mode.value}")
        print(f"   Cash Reserve: ${self.min_cash_reserve:.2f}")
        if mode == PartialFillMode.SMART:
            print(f"   Auto-fill threshold: {self.partial_fill_threshold:.1%}")

        """Validate cash flow before executing trades"""
        print(f"\n💰 CASH FLOW ANALYSIS:")
        print("=" * 40)
        
        simulated_cash = self.cash
        validation_results = {
            'feasible': True,
            'total_sells': 0,
            'total_buys': 0,
            'final_cash': 0,
            'warnings': [],
            'phase_results': {}
        }
        
        execution_phases = self._prioritize_orders_for_cash_flow(orders)
        
        for phase_name, phase_orders in execution_phases.items():
            if not phase_orders or "HOLD" in phase_name:
                continue
                
            phase_sells = 0
            phase_buys = 0
            phase_warnings = []
            
            print(f"\n📋 {phase_name}:")
            
            for order in phase_orders:
                if order.ticker not in current_prices:
                    phase_warnings.append(f"No price data for {order.ticker}")
                    continue
                    
                current_price = current_prices[order.ticker]
                
                if order.action in [OrderType.SELL, OrderType.REDUCE]:
                    if order.ticker not in self.holdings:
                        phase_warnings.append(f"Cannot sell {order.ticker} - no position")
                        continue
                    
                    available_shares = self.holdings[order.ticker]['shares']
                    
                    if order.action == OrderType.REDUCE and order.target_weight:
                        shares_to_sell = available_shares - int(available_shares * order.target_weight / 100)
                    else:
                        shares_to_sell = min(order.shares or available_shares, available_shares)
                    
                    proceeds = shares_to_sell * current_price
                    simulated_cash += proceeds
                    phase_sells += proceeds
                    
                    print(f"   📤 Sell {shares_to_sell} {order.ticker}: +${proceeds:.2f} → ${simulated_cash:.2f}")
                    
                elif order.action == OrderType.BUY:
                    required_cash = order.shares * current_price
                    
                    if required_cash > simulated_cash:
                        # Check if partial fill is possible
                        if simulated_cash >= current_price:
                            max_shares = int(simulated_cash / current_price)
                            partial_cost = max_shares * current_price
                            phase_warnings.append(f"Partial fill for {order.ticker}: {max_shares}/{order.shares} shares")
                            simulated_cash -= partial_cost
                            phase_buys += partial_cost
                            print(f"   📥 Buy {max_shares} {order.ticker} (partial): -${partial_cost:.2f} → ${simulated_cash:.2f}")
                        else:
                            validation_results['feasible'] = False
                            phase_warnings.append(f"Cannot afford any {order.ticker} shares")
                            print(f"   ❌ Cannot buy {order.ticker}: Need ${required_cash:.2f}, have ${simulated_cash:.2f}")
                    else:
                        simulated_cash -= required_cash
                        phase_buys += required_cash
                        print(f"   📥 Buy {order.shares} {order.ticker}: -${required_cash:.2f} → ${simulated_cash:.2f}")
            
            validation_results['phase_results'][phase_name] = {
                'sells': phase_sells,
                'buys': phase_buys, 
                'warnings': phase_warnings
            }
            
            validation_results['total_sells'] += phase_sells
            validation_results['total_buys'] += phase_buys
            validation_results['warnings'].extend(phase_warnings)
        
        validation_results['final_cash'] = simulated_cash
        
        print(f"\n💰 CASH FLOW SUMMARY:")
        print(f"   Starting cash: ${self.cash:.2f}")
        print(f"   Total from sells: +${validation_results['total_sells']:.2f}")
        print(f"   Total for buys: -${validation_results['total_buys']:.2f}")
        print(f"   Final cash: ${validation_results['final_cash']:.2f}")
        print(f"   Net change: ${validation_results['final_cash'] - self.cash:+.2f}")
        
        if validation_results['warnings']:
            print(f"\n⚠️  WARNINGS ({len(validation_results['warnings'])}):")
            for warning in validation_results['warnings']:
                print(f"   • {warning}")
        
        if validation_results['feasible']:
            print(f"\n✅ All trades are feasible with current cash flow strategy")
        else:
            print(f"\n❌ Some trades cannot be executed due to insufficient cash")
        
        return validation_results


    # == 3. DATA FETCHING METHODS ==
    def save_portfolio_state(self):
        """Save current portfolio state to external JSON file"""
        state_data = {
            'timestamp': datetime.now().isoformat(),
            'cash': self.cash,
            'holdings': dict(self.holdings),
            'total_investment': getattr(self, 'total_investment', 2000.00),
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open('portfolio_state.json', 'w') as f:
            json.dump(state_data, f, indent=2)
        
        print(f"💾 Portfolio state saved to portfolio_state.json")

    def load_portfolio_state(self):
        """Load portfolio state from external file if it exists"""
        try:
            if os.path.exists('portfolio_state.json'):
                with open('portfolio_state.json', 'r') as f:
                    state_data = json.load(f)
                
                self.cash = state_data['cash']
                self.holdings = state_data['holdings']
                
                print(f"📂 Portfolio state loaded from portfolio_state.json")
                print(f"   Last updated: {state_data['last_update']}")
                return True
        except Exception as e:
            print(f"⚠️ Error loading portfolio state: {e}")
            print("📝 Using default holdings from __init__")
        
        return False
    
    def fetch_current_data(self):
        """Fetch current price data for all holdings and benchmarks"""
        
        print("📡 Fetching current market data...")
        
        # Get all tickers
        portfolio_tickers = list(self.holdings.keys())
        benchmark_tickers = ['SPY', 'IWM']  # Remove VIX for now
        all_tickers = portfolio_tickers + benchmark_tickers
        
        print(f"🎯 Fetching data for tickers: {all_tickers}")
        
        try:
            # Fetch data with more robust handling
            start_fetch_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            raw_data = yf.download(all_tickers, start=start_fetch_date, progress=False, auto_adjust=True)
            
            # Handle different data structures from yfinance
            if raw_data.empty:
                print("❌ No data returned from yfinance")
                return None, None, None  # Return tuple instead of False
            
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
                        print("❌ Could not find price data columns")
                        return None, None, None  # Return tuple instead of False
                else:
                    self.price_data = raw_data
            
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
                print("🔍 Attempting to fetch VIX data separately...")
                vix_data = yf.download('^VIX', start=start_fetch_date, progress=False, auto_adjust=True)
                if not vix_data.empty:
                    if 'Close' in vix_data.columns:
                        vix_prices = vix_data['Close']
                    else:
                        vix_prices = vix_data.iloc[:, 0]  # Take first column
                    
                    # Add VIX to price data
                    self.price_data['VIX'] = vix_prices
                    print("✅ VIX data fetched successfully using ^VIX")
                else:
                    print("⚠️  VIX data unavailable - continuing without VIX")
            except Exception as e:
                print(f"⚠️  VIX fetch failed: {e} - continuing without VIX")
            
            # Clean up data
            self.price_data = self.price_data.fillna(method='ffill').fillna(method='bfill')
            
            # Store volume data
            self.volume_data = volume_data
            
            # Verify we have some data
            if self.price_data.empty:
                print("❌ Price data is empty after processing")
                return None, None, None  # Return tuple instead of False
            
            print(f"✅ Successfully fetched data for {len(self.price_data.columns)} securities")
            print(f"📅 Data range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
            print(f"📊 Available tickers: {list(self.price_data.columns)}")
            
            # Extract current prices (most recent row)
            current_prices = self.price_data.iloc[-1].to_dict()
            
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
    
    def fetch_data_individually(self, tickers):
        """Fallback method to fetch data for each ticker individually"""
        
        print("🔄 Fetching tickers individually...")
        
        price_data_dict = {}
        successful_tickers = []
        
        for ticker in tickers:
            # Use ^VIX for VIX data
            fetch_ticker = '^VIX' if ticker == 'VIX' else ticker
            
            try:
                print(f"   Fetching {ticker}...")
                start_fetch_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                ticker_data = yf.download(fetch_ticker, start=start_fetch_date, progress=False, auto_adjust=True)
                
                if not ticker_data.empty:
                    if 'Close' in ticker_data.columns:
                        price_data_dict[ticker] = ticker_data['Close']
                    elif 'Adj Close' in ticker_data.columns:
                        price_data_dict[ticker] = ticker_data['Adj Close']
                    else:
                        numeric_cols = ticker_data.select_dtypes(include=[np.number]).columns
                        if len(numeric_cols) > 0:
                            price_data_dict[ticker] = ticker_data[numeric_cols[0]]
                    
                    successful_tickers.append(ticker)
                else:
                    print(f"   ⚠️  No data for {ticker}")
                    
            except Exception as e:
                print(f"   ❌ Failed to fetch {ticker}: {e}")
        
        if price_data_dict:
            self.price_data = pd.DataFrame(price_data_dict)
            self.price_data = self.price_data.fillna(method='ffill').fillna(method='bfill')
            
            # Initialize empty volume data
            self.volume_data = pd.DataFrame()
            
            print(f"✅ Successfully fetched {len(successful_tickers)} out of {len(tickers)} tickers")
            print(f"📊 Available data: {successful_tickers}")
            
            if len(self.price_data) > 0:
                print(f"📅 Data range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
                return True  # Keep returning True for success
        
        print("❌ Could not fetch any valid data")
        self.price_data = pd.DataFrame()  # Ensure empty DataFrame
        self.volume_data = pd.DataFrame()  # Ensure empty DataFrame
        return False


    # == 4. ANALYSIS & CALCULATION METHODS ==
    def calculate_position_metrics(self, current_prices):
        """Calculate key metrics for each position"""
        positions = []
        
        # STEP 1: Calculate the COMPLETE total portfolio value FIRST
        total_current_value = self.cash
        position_values = {}
        total_cost_basis = 0  # Track actual total investment
        
        # First pass: Calculate all position values and total
        for ticker, position in self.holdings.items():
            if ticker in current_prices:
                current_price = current_prices[ticker]
                current_value = position['shares'] * current_price
                cost_basis = position['shares'] * position['entry_price']
                position_values[ticker] = {
                    'current_price': current_price,
                    'current_value': current_value,
                    'cost_basis': cost_basis
                }
                total_current_value += current_value
                total_cost_basis += cost_basis
        
        # STEP 2: Now calculate metrics using the FINAL total for all positions
        for ticker, position in self.holdings.items():
            if ticker in position_values:
                pos_data = position_values[ticker]
                current_price = pos_data['current_price']
                current_value = pos_data['current_value']
                cost_basis = pos_data['cost_basis']
                
                # P&L calculations - FIXED to use actual cost basis
                pnl_dollar = current_value - cost_basis
                pnl_percent = (pnl_dollar / cost_basis) * 100
                daily_change = ((current_price - position['entry_price']) / position['entry_price']) * 100
                
                # ✅ FIXED: Use the complete total for weight calculations
                current_weight = (current_value / total_current_value) * 100 if total_current_value > 0 else 0
                target_weight = (cost_basis / total_cost_basis) * 100  # Fixed to use actual total cost basis
                weight_drift = current_weight - target_weight
                
                positions.append({
                    'ticker': ticker,
                    'shares': position['shares'],
                    'entry_price': position['entry_price'],
                    'current_price': current_price,
                    'current_value': current_value,
                    'cost_basis': cost_basis,
                    'pnl_dollar': pnl_dollar,
                    'pnl_percent': pnl_percent,
                    'daily_change': daily_change,
                    'current_weight': current_weight,
                    'target_weight': target_weight,
                    'weight_drift': weight_drift
                })
        
        return positions, total_current_value, total_cost_basis
    
    def check_alerts(self, positions):
        """Check for stop-loss and profit target alerts"""
        alerts = []
        
        stop_loss_targets = {
            'CYTK': -18, 'AMD': -13, 'IONS': -19, 'SOUN': -20,
            'QS': -25, 'RIG': -20, 'CRGY': -20, 'SERV': -20
        }
        
        profit_targets = {
            'CYTK': 40, 'AMD': 40, 'IONS': 40, 'SOUN': 50,
            'QS': 100, 'RIG': 40, 'CRGY': 30, 'SERV': 50
        }
        
        for pos in positions:
            ticker = pos['ticker']
            pnl_pct = pos['pnl_percent']
            
            if ticker in stop_loss_targets and pnl_pct <= stop_loss_targets[ticker]:
                alerts.append(f"🔴 STOP LOSS: {ticker} at {pnl_pct:.1f}% (target: {stop_loss_targets[ticker]}%)")
            
            if ticker in profit_targets and pnl_pct >= profit_targets[ticker]:
                alerts.append(f"🟢 PROFIT TARGET: {ticker} at {pnl_pct:.1f}% (target: {profit_targets[ticker]}%)")
        
        return alerts
    
    def get_volume_alerts(self, volume_data, price_data):
        """Check for unusual volume activity"""
        volume_alerts = []
        
        # Handle case where volume_data might be a Series instead of DataFrame
        if volume_data is None:
            return volume_alerts
        
        # Convert Series to DataFrame if needed
        if isinstance(volume_data, pd.Series):
            return volume_alerts  # Skip volume analysis if data structure is unexpected
        
        for ticker in self.holdings.keys():
            if ticker in volume_data.columns and len(volume_data[ticker]) >= 5:
                recent_volume = volume_data[ticker].dropna()
                if len(recent_volume) >= 5:
                    current_volume = recent_volume.iloc[-1]
                    avg_volume = recent_volume.iloc[-5:-1].mean()
                    
                    if current_volume > avg_volume * 2:  # 2x average volume
                        if ticker in price_data.columns and len(price_data[ticker]) >= 2:
                            price_change = ((price_data[ticker].iloc[-1] - price_data[ticker].iloc[-2]) / price_data[ticker].iloc[-2]) * 100
                            volume_alerts.append(f"📊 HIGH VOLUME: {ticker} - {current_volume/1000000:.1f}M vs {avg_volume/1000000:.1f}M avg (Price: {price_change:+.1f}%)")
        
        return volume_alerts
    


    # == 5. DOCUMENT PROCESSING METHODS ==
    def find_trading_document(self):
        """Auto-detect trading recommendation document"""
        
        # Search patterns for trading recommendation files
        search_patterns = [
            'trading_recommendation*.md',
            'trading_recommendation*.pdf', 
            'trading_recommendations*.md',
            'trading_recommendations*.pdf',
            'claude_recommendation*.md',
            'claude_recommendation*.pdf',
            'portfolio_analysis*.md',
            'portfolio_analysis*.pdf'
        ]
        
        found_files = []
        
        for pattern in search_patterns:
            matches = glob.glob(pattern)
            for match in matches:
                # Get file modification time to find most recent
                mod_time = os.path.getmtime(match)
                found_files.append((match, mod_time))
        
        if not found_files:
            print("❌ No trading recommendation files found!")
            print("🔍 Searched for patterns:")
            for pattern in search_patterns:
                print(f"   • {pattern}")
            return None
        
        # Sort by modification time (most recent first)
        found_files.sort(key=lambda x: x[1], reverse=True)
        
        if len(found_files) == 1:
            selected_file = found_files[0][0]
            print(f"📄 Found document: {selected_file}")
            return selected_file
        
        # Multiple files found - show options
        print(f"📄 Found {len(found_files)} trading documents:")
        for i, (filename, mod_time) in enumerate(found_files[:5], 1):  # Show top 5
            mod_date = datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M')
            print(f"   {i}. {filename} (modified: {mod_date})")
        
        # Auto-select most recent
        selected_file = found_files[0][0]
        print(f"✅ Auto-selecting most recent: {selected_file}")
        
        return selected_file
    
    def parse_document(self, file_path: str):
        """Parse trading orders from markdown or PDF document"""
        
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return []
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if file_ext == '.md':
                return self.parse_markdown_document(file_path)
            elif file_ext == '.pdf':
                return self.parse_pdf_document(file_path)
            else:
                # Try to parse as text anyway
                print(f"⚠️ Unknown file type {file_ext}, attempting text parsing...")
                return self.parse_markdown_document(file_path)
                
        except Exception as e:
            print(f"❌ Error parsing document: {e}")
            return []
    
    def parse_pdf_document(self, file_path: str):
        """Extract text from PDF and parse orders"""
        
        if not PDF_AVAILABLE:
            print("❌ PDF parsing not available. Please install PyPDF2 or pdfplumber:")
            print("   pip install pdfplumber")
            return []
        
        print(f"📖 Extracting text from PDF: {file_path}")
        
        try:
            # Try pdfplumber first (better text extraction)
            if 'pdfplumber' in globals():
                text_content = self._extract_with_pdfplumber(file_path)
            else:
                text_content = self._extract_with_pypdf2(file_path)
            
            if not text_content.strip():
                print("❌ No text extracted from PDF")
                return []
            
            print(f"✅ Extracted {len(text_content)} characters from PDF")
            print(f"📝 First 200 characters: {text_content[:200]}...")
            
            # Parse the extracted text as markdown
            return self.parse_text_content(text_content)
            
        except Exception as e:
            print(f"❌ Error extracting PDF text: {e}")
            return []
    
    def parse_markdown_document(self, file_path: str):
        """Parse trading orders from markdown document"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return self.parse_text_content(content)
            
        except FileNotFoundError:
            print(f"❌ Markdown file not found: {file_path}")
            return []
        except Exception as e:
            print(f"❌ Error reading markdown file: {e}")
            return []
    
    def parse_text_content(self, content: str):
        """Parse trading orders from text content (works for both MD and PDF)"""
        orders = []
        
        # Extract ORDERS section
        orders_section = self._extract_orders_section(content)
        if not orders_section:
            print("⚠️ No ORDERS section found, searching entire document...")
            orders_section = content  # Search entire document as fallback
        
        # Parse individual order lines
        lines = orders_section.split('\n')
        current_priority = OrderPriority.MEDIUM
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for priority headers
            if 'HIGH PRIORITY' in line.upper() or 'IMMEDIATE' in line.upper():
                current_priority = OrderPriority.HIGH
                continue
            elif 'MEDIUM PRIORITY' in line.upper() or 'POSITION MANAGEMENT' in line.upper():
                current_priority = OrderPriority.MEDIUM
                continue
            elif 'LOW PRIORITY' in line.upper():
                current_priority = OrderPriority.LOW
                continue
            
            # Parse order lines
            order = self._parse_order_line(line, current_priority)
            if order:
                orders.append(order)
        
        return orders
    
    def _extract_orders_section(self, content: str):
        """Extract the ORDERS section from markdown"""
        # Look for ## ORDERS section
        pattern = r'##\s+ORDERS\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        return match.group(1) if match else ""
    
    def _parse_order_line(self, line: str, priority: OrderPriority):
        """Parse a single order line"""
        line = line.strip('*- ')  # Remove markdown formatting
        
        # Pattern 1: "SELL all 19 shares of SOUN"
        sell_all_match = re.search(r'sell\s+all\s+(\d+)\s+shares?\s+of\s+([A-Z]+)', line, re.IGNORECASE)
        if sell_all_match:
            shares, ticker = sell_all_match.groups()
            reason = self._extract_reason(line)
            return TradeOrder(
                ticker=ticker,
                action=OrderType.SELL,
                shares=int(shares),
                reason=reason,
                priority=priority
            )
        
        # Pattern 2: "SELL 3 shares of CYTK"
        sell_match = re.search(r'sell\s+(\d+)\s+shares?\s+of\s+([A-Z]+)', line, re.IGNORECASE)
        if sell_match:
            shares, ticker = sell_match.groups()
            reason = self._extract_reason(line)
            return TradeOrder(
                ticker=ticker,
                action=OrderType.SELL,
                shares=int(shares),
                reason=reason,
                priority=priority
            )
        
        # Pattern 3: "BUY 15 shares of NVDA"
        buy_match = re.search(r'buy\s+(\d+)\s+shares?\s+of\s+([A-Z]+)', line, re.IGNORECASE)
        if buy_match:
            shares, ticker = buy_match.groups()
            reason = self._extract_reason(line)
            return TradeOrder(
                ticker=ticker,
                action=OrderType.BUY,
                shares=int(shares),
                reason=reason,
                priority=priority
            )
        
        # Pattern 4: "HOLD all 3 shares of IONS"
        hold_match = re.search(r'hold\s+(?:all\s+)?(\d+)?\s*shares?\s+of\s+([A-Z]+)', line, re.IGNORECASE)
        if hold_match:
            shares, ticker = hold_match.groups()
            return TradeOrder(
                ticker=ticker,
                action=OrderType.HOLD,
                shares=int(shares) if shares else None,
                reason="Hold position",
                priority=priority
            )
        
        return None
    
    def _extract_reason(self, line: str):
        """Extract reason from order line"""
        # Look for text after "Reason:" 
        reason_match = re.search(r'reason[:\s]+([^*\n]+)', line, re.IGNORECASE)
        if reason_match:
            return reason_match.group(1).strip()
        
        # Fallback: take everything after the ticker
        parts = line.split('-', 1)
        if len(parts) > 1:
            return parts[1].strip()
        
        return "No specific reason provided"
    
    def _extract_with_pdfplumber(self, file_path: str):
        """Extract text using pdfplumber (recommended)"""
        import pdfplumber
        
        text_content = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_content += page_text + "\n"
        
        return text_content
    
    def _extract_with_pypdf2(self, file_path: str):
        """Extract text using PyPDF2 (fallback)"""
        import PyPDF2
        
        text_content = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text_content += page.extract_text() + "\n"
        return text_content



    # == 6. CASH FLOW VALIDATION ==
    def validate_cash_flow(self, orders, current_prices):
        """Validate cash flow before executing trades"""
        print(f"\n💰 CASH FLOW ANALYSIS:")
        print("=" * 40)
        
        simulated_cash = self.cash
        validation_results = {
            'feasible': True,
            'total_sells': 0,
            'total_buys': 0,
            'final_cash': 0,
            'warnings': [],
            'phase_results': {}
        }
        
        execution_phases = self._prioritize_orders_for_cash_flow(orders)
        
        for phase_name, phase_orders in execution_phases.items():
            if not phase_orders or "HOLD" in phase_name:
                continue
                
            phase_sells = 0
            phase_buys = 0
            phase_warnings = []
            
            print(f"\n📋 {phase_name}:")
            
            for order in phase_orders:
                if order.ticker not in current_prices:
                    phase_warnings.append(f"No price data for {order.ticker}")
                    continue
                    
                current_price = current_prices[order.ticker]
                
                if order.action in [OrderType.SELL, OrderType.REDUCE]:
                    if order.ticker not in self.holdings:
                        phase_warnings.append(f"Cannot sell {order.ticker} - no position")
                        continue
                    
                    available_shares = self.holdings[order.ticker]['shares']
                    
                    if order.action == OrderType.REDUCE and order.target_weight:
                        shares_to_sell = available_shares - int(available_shares * order.target_weight / 100)
                    else:
                        shares_to_sell = min(order.shares or available_shares, available_shares)
                    
                    proceeds = shares_to_sell * current_price
                    simulated_cash += proceeds
                    phase_sells += proceeds
                    
                    print(f"   📤 Sell {shares_to_sell} {order.ticker}: +${proceeds:.2f} → ${simulated_cash:.2f}")
                    
                elif order.action == OrderType.BUY:
                    required_cash = order.shares * current_price
                    
                    if required_cash > simulated_cash:
                        # Check if partial fill is possible
                        if simulated_cash >= current_price:
                            max_shares = int(simulated_cash / current_price)
                            partial_cost = max_shares * current_price
                            phase_warnings.append(f"Partial fill for {order.ticker}: {max_shares}/{order.shares} shares")
                            simulated_cash -= partial_cost
                            phase_buys += partial_cost
                            print(f"   📥 Buy {max_shares} {order.ticker} (partial): -${partial_cost:.2f} → ${simulated_cash:.2f}")
                        else:
                            validation_results['feasible'] = False
                            phase_warnings.append(f"Cannot afford any {order.ticker} shares")
                            print(f"   ❌ Cannot buy {order.ticker}: Need ${required_cash:.2f}, have ${simulated_cash:.2f}")
                    else:
                        simulated_cash -= required_cash
                        phase_buys += required_cash
                        print(f"   📥 Buy {order.shares} {order.ticker}: -${required_cash:.2f} → ${simulated_cash:.2f}")
            
            validation_results['phase_results'][phase_name] = {
                'sells': phase_sells,
                'buys': phase_buys, 
                'warnings': phase_warnings
            }
            
            validation_results['total_sells'] += phase_sells
            validation_results['total_buys'] += phase_buys
            validation_results['warnings'].extend(phase_warnings)
        
        validation_results['final_cash'] = simulated_cash
        
        print(f"\n💰 CASH FLOW SUMMARY:")
        print(f"   Starting cash: ${self.cash:.2f}")
        print(f"   Total from sells: +${validation_results['total_sells']:.2f}")
        print(f"   Total for buys: -${validation_results['total_buys']:.2f}")
        print(f"   Final cash: ${validation_results['final_cash']:.2f}")
        print(f"   Net change: ${validation_results['final_cash'] - self.cash:+.2f}")
        
        if validation_results['warnings']:
            print(f"\n⚠️  WARNINGS ({len(validation_results['warnings'])}):")
            for warning in validation_results['warnings']:
                print(f"   • {warning}")
        
        if validation_results['feasible']:
            print(f"\n✅ All trades are feasible with current cash flow strategy")
        else:
            print(f"\n❌ Some trades cannot be executed due to insufficient cash")
        
        return validation_results
    
    def _prioritize_orders_for_cash_flow(self, orders):
        """Prioritize orders to ensure proper cash flow management"""
        
        # Separate orders by type and priority
        high_sells = []
        high_buys = []
        medium_sells = []
        medium_buys = []
        low_sells = []
        low_buys = []
        holds = []
        
        for order in orders:
            if order.action == OrderType.HOLD:
                holds.append(order)
            elif order.action in [OrderType.SELL, OrderType.REDUCE]:
                if order.priority == OrderPriority.HIGH:
                    high_sells.append(order)
                elif order.priority == OrderPriority.MEDIUM:
                    medium_sells.append(order)
                else:
                    low_sells.append(order)
            elif order.action == OrderType.BUY:
                if order.priority == OrderPriority.HIGH:
                    high_buys.append(order)
                elif order.priority == OrderPriority.MEDIUM:
                    medium_buys.append(order)
                else:
                    low_buys.append(order)
        
        # Return execution phases in proper cash-flow order
        return {
            "HIGH Priority SELLS (Generate Cash)": high_sells,
            "HIGH Priority BUYS (Use Generated Cash)": high_buys,
            "MEDIUM Priority SELLS": medium_sells,
            "MEDIUM Priority BUYS": medium_buys,
            "LOW Priority SELLS": low_sells,
            "LOW Priority BUYS": low_buys,
            "HOLD Orders": holds
        }
    

    # == 7. TRADE EXECUTION METHODS ==
    def execute_orders(self, orders):
        """Execute parsed trading orders with proper cash flow management"""
        results = []
        
        # Get current market data
        current_prices, _, _ = self.fetch_current_data()
        if not current_prices:
            print("❌ Failed to fetch current market data")
            return []
        
        print(f"💰 Starting cash balance: ${self.cash:.2f}")
        
        # Execute orders using cash-flow-aware prioritization
        execution_phases = self._prioritize_orders_for_cash_flow(orders)
        
        for phase_name, phase_orders in execution_phases.items():
            if not phase_orders:
                continue
                
            print(f"\n📋 Executing {phase_name}:")
            print("-" * 30)
            
            for order in phase_orders:
                if order.action == OrderType.HOLD:
                    print(f"👍 HOLD {order.ticker} - No execution needed")
                    continue
                
                # Show cash before each trade
                print(f"💵 Cash available: ${self.cash:.2f}")
                
                result = self._execute_single_order(order, current_prices)
                results.append(result)
                
                if result.executed:
                    old_cash = self.cash
                    self._update_portfolio_holdings(result)
                    cash_change = self.cash - old_cash
                    print(f"💰 Cash change: ${cash_change:+.2f} → New balance: ${self.cash:.2f}")
                else:
                    print(f"❌ Failed: {result.error_message}")
        
        return results

    def execute_automated_trading(self, document_path: Optional[str] = None):
        """Main method to execute automated trading from document"""
        print(f"\n{'='*60}")
        print(f"🤖 AUTOMATED TRADE EXECUTION")
        print(f"{'='*60}")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # LOG: Start of execution session
        trade_logger.info("=" * 60)
        trade_logger.info("AUTOMATED TRADE EXECUTION SESSION STARTED")
        trade_logger.info("=" * 60)
        
        # Auto-detect document if not provided
        if document_path is None:
            document_path = self.find_trading_document()
            if not document_path:
                trade_logger.warning("No trading document found - execution cancelled")
                return []
        
        # Validate file exists
        if not os.path.exists(document_path):
            error_msg = f"File not found: {document_path}"
            print(f"❌ {error_msg}")
            trade_logger.error(error_msg)
            return []
        
        print(f"📄 Document: {document_path}")
        file_ext = os.path.splitext(document_path)[1].lower()
        print(f"📋 File type: {file_ext.upper()}")
        
        # LOG: Document being processed
        trade_logger.info(f"Processing document: {document_path} (Type: {file_ext.upper()})")
        
        # Parse orders from document
        orders = self.parse_document(document_path)
        
        if not orders:
            error_msg = "No valid orders found in document"
            print(f"❌ {error_msg}")
            trade_logger.warning(error_msg)
            return []
        
        # LOG: Orders parsed
        trade_logger.info(f"Successfully parsed {len(orders)} orders from document")
        
        print(f"\n📋 PARSED ORDERS ({len(orders)}):")
        print("-" * 40)
        for i, order in enumerate(orders, 1):
            if order.action == OrderType.HOLD:
                order_desc = f"{order.action.value} {order.ticker} - {order.reason}"
                print(f"{i}. {order_desc}")
                trade_logger.info(f"Order {i}: {order_desc}")
            else:
                shares_text = f"{order.shares} shares of" if order.shares else "position in"
                order_desc = f"{order.action.value} {shares_text} {order.ticker} ({order.priority.value})"
                print(f"{i}. {order_desc}")
                print(f"   Reason: {order.reason}")
                trade_logger.info(f"Order {i}: {order_desc} - {order.reason}")
        
        # Get current market data for validation
        current_prices, _, _ = self.fetch_current_data()
        if not current_prices:
            error_msg = "Failed to fetch current market data"
            print(f"❌ {error_msg}")
            trade_logger.error(error_msg)
            return []
        
        # LOG: Market data status
        trade_logger.info(f"Market data fetched for {len(current_prices)} securities")
        
        # CASH FLOW VALIDATION
        validation = self.validate_cash_flow(orders, current_prices)
        
        # LOG: Validation results
        if validation['feasible']:
            trade_logger.info("Cash flow validation PASSED - all trades feasible")
        else:
            trade_logger.warning("Cash flow validation FAILED - some trades not feasible")
        
        if validation['warnings']:
            for warning in validation['warnings']:
                trade_logger.warning(f"Validation warning: {warning}")
        
        # Ask for confirmation if there are issues
        if not validation['feasible'] or validation['warnings']:
            print(f"\n⚠️  EXECUTION CONCERNS DETECTED!")
            response = input("Do you want to proceed anyway? (y/n): ").lower().strip()
            if response not in ['y', 'yes']:
                cancel_msg = "Execution cancelled by user"
                print(f"❌ {cancel_msg}")
                trade_logger.info(cancel_msg)
                return []
            else:
                trade_logger.info("User chose to proceed despite warnings")
        
        # Execute orders
        print(f"\n⚡ EXECUTING TRADES...")
        print("-" * 40)
        trade_logger.info("Beginning trade execution phase")
        
        results = self.execute_orders(orders)
        
        # Generate execution report
        executed_count = sum(1 for r in results if r.executed)
        failed_count = len(results) - executed_count
        
        print(f"\n📊 EXECUTION SUMMARY:")
        print("-" * 40)
        print(f"✅ Executed: {executed_count}")
        print(f"❌ Failed: {failed_count}")
        
        # LOG: Execution summary
        trade_logger.info(f"EXECUTION COMPLETE - {executed_count} executed, {failed_count} failed")
        
        total_proceeds = 0
        total_invested = 0
        
        for result in results:
            if result.executed:
                if result.order.action in [OrderType.SELL, OrderType.REDUCE]:
                    total_proceeds += result.execution_value
                    print(f"💰 Proceeds from {result.order.ticker}: ${result.execution_value:.2f}")
                elif result.order.action == OrderType.BUY:
                    total_invested += result.execution_value
                    print(f"💸 Invested in {result.order.ticker}: ${result.execution_value:.2f}")
            else:
                failure_msg = f"Failed {result.order.ticker}: {result.error_message}"
                print(f"⚠️  {failure_msg}")
                trade_logger.error(failure_msg)
        
        print(f"\n💰 ACTUAL CASH IMPACT:")
        print(f"   Proceeds from sales: +${total_proceeds:.2f}")
        print(f"   Invested in buys: -${total_invested:.2f}")
        print(f"   Net cash change: ${total_proceeds - total_invested:+.2f}")
        print(f"   Final cash balance: ${self.cash:.2f}")
        
        # LOG: Cash impact summary
        trade_logger.info(f"Cash impact: +${total_proceeds:.2f} proceeds, -${total_invested:.2f} invested, net: ${total_proceeds - total_invested:+.2f}")
        trade_logger.info(f"Final cash balance: ${self.cash:.2f}")
        
        # Compare with validation
        predicted_final = validation['final_cash']
        actual_final = self.cash
        variance = actual_final - predicted_final
        
        if abs(variance) > 0.01:  # More than 1 cent difference
            print(f"   Variance from prediction: ${variance:+.2f}")
            if abs(variance) > 1.00:  # More than $1 difference
                print(f"   ⚠️  Significant variance - may indicate execution issues")
                trade_logger.warning(f"Significant cash variance: ${variance:+.2f} from prediction")
            else:
                trade_logger.info(f"Minor cash variance: ${variance:+.2f} from prediction")
        else:
            print(f"   ✅ Matches cash flow prediction exactly")
            trade_logger.info("Cash flow matches prediction exactly")
        
        # Save execution log
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'trade_execution_{timestamp}.json'
        
        execution_log = {
            'timestamp': datetime.now().isoformat(),
            'document': document_path,
            'file_type': file_ext,
            'validation': validation,
            'orders_parsed': len(orders),
            'orders_executed': executed_count,
            'orders_failed': failed_count,
            'total_proceeds': total_proceeds,
            'total_invested': total_invested,
            'predicted_cash': predicted_final,
            'actual_cash': actual_final,
            'cash_variance': variance,
            'updated_holdings': dict(self.holdings)
        }
        
        with open(log_filename, 'w') as f:
            json.dump(execution_log, f, indent=2)
        
        print(f"\n📄 Execution log saved: {log_filename}")
        trade_logger.info(f"Detailed execution log saved to: {log_filename}")
        
        # Show updated portfolio summary
        print(f"\n📈 UPDATED PORTFOLIO SUMMARY:")
        print("-" * 40)
        print(f"   Cash: ${self.cash:.2f}")
        print(f"   Positions ({len(self.holdings)}):")
        for ticker, pos in self.holdings.items():
            print(f"     {ticker}: {pos['shares']} shares @ ${pos['entry_price']:.2f}")
            trade_logger.info(f"Final position - {ticker}: {pos['shares']} shares @ ${pos['entry_price']:.2f}")
        
        print(f"{'='*60}")
        
        # Save state after successful trades
        if executed_count > 0:
            self.save_portfolio_state()
            trade_logger.info("Portfolio state saved to portfolio_state.json")
        
        # LOG: End of session
        trade_logger.info("AUTOMATED TRADE EXECUTION SESSION COMPLETED")
        trade_logger.info("=" * 60)
        
        return results

    def _execute_single_order(self, order, current_prices):
        """Execute a single trading order with enhanced cash management"""
        timestamp = datetime.now()
        
        # LOG: Starting order execution
        trade_logger.info(f"Executing order: {order.action.value} {order.ticker}")
        
        # Validate ticker exists
        if order.ticker not in current_prices:
            error_msg = f"No market data for {order.ticker}"
            trade_logger.error(f"Order failed - {error_msg}")
            return TradeResult(
                order=order,
                executed=False,
                execution_price=None,
                executed_shares=None,
                execution_value=None,
                error_message=error_msg,
                timestamp=timestamp
            )
        
        current_price = current_prices[order.ticker]
        trade_logger.info(f"{order.ticker} current market price: ${current_price:.2f}")
        
        # Handle SELL/REDUCE orders
        if order.action in [OrderType.SELL, OrderType.REDUCE]:
            if order.ticker not in self.holdings:
                error_msg = f"No position in {order.ticker} to sell"
                trade_logger.error(f"Sell order failed - {error_msg}")
                return TradeResult(
                    order=order,
                    executed=False,
                    execution_price=current_price,
                    executed_shares=0,
                    execution_value=0,
                    error_message=error_msg,
                    timestamp=timestamp
                )
            
            available_shares = self.holdings[order.ticker]['shares']
            trade_logger.info(f"Available shares for {order.ticker}: {available_shares}")
            
            # For REDUCE orders, calculate shares to sell based on target weight
            if order.action == OrderType.REDUCE and order.target_weight is not None:
                target_percentage = order.target_weight / 100
                shares_to_keep = int(available_shares * target_percentage)
                shares_to_sell = available_shares - shares_to_keep
                trade_logger.info(f"REDUCE order: keeping {shares_to_keep} shares ({target_percentage:.1%}), selling {shares_to_sell}")
            else:
                # For SELL orders, use specified shares or all shares
                shares_to_sell = min(order.shares or available_shares, available_shares)
                trade_logger.info(f"SELL order: selling {shares_to_sell} shares")
            
            if shares_to_sell <= 0:
                error_msg = f"No shares to sell (calculated: {shares_to_sell})"
                trade_logger.error(f"Sell order failed - {error_msg}")
                return TradeResult(
                    order=order,
                    executed=False,
                    execution_price=current_price,
                    executed_shares=0,
                    execution_value=0,
                    error_message=error_msg,
                    timestamp=timestamp
                )
            
            execution_value = shares_to_sell * current_price
            log_message = f"SOLD {shares_to_sell} shares of {order.ticker} at ${current_price:.2f} = ${execution_value:.2f}"
            print(f"📤 PAPER TRADE: {log_message}")
            trade_logger.info(f"TRADE EXECUTED: {log_message}")
            
            return TradeResult(
                order=order,
                executed=True,
                execution_price=current_price,
                executed_shares=shares_to_sell,
                execution_value=execution_value,
                error_message=None,
                timestamp=timestamp
            )
        
        # Handle BUY orders with enhanced partial fill management
        elif order.action == OrderType.BUY:
            shares_to_buy = order.shares
            required_cash = shares_to_buy * current_price
            available_cash = max(0, self.cash - getattr(self, 'min_cash_reserve', 10.0))
            
            trade_logger.info(f"BUY order: {shares_to_buy} shares x ${current_price:.2f} = ${required_cash:.2f} required")
            trade_logger.info(f"Available cash: ${available_cash:.2f} (after ${getattr(self, 'min_cash_reserve', 10.0):.2f} reserve)")
            
            # Check if we have enough cash (considering cash reserve)
            if required_cash > available_cash:
                trade_logger.warning(f"Insufficient cash for full order - handling partial fill")
                return self._handle_insufficient_cash(order, current_price, available_cash, timestamp)
            
            execution_value = shares_to_buy * current_price
            log_message = f"BOUGHT {shares_to_buy} shares of {order.ticker} at ${current_price:.2f} = ${execution_value:.2f}"
            print(f"📥 PAPER TRADE: {log_message}")
            trade_logger.info(f"TRADE EXECUTED: {log_message}")
            
            return TradeResult(
                order=order,
                executed=True,
                execution_price=current_price,
                executed_shares=shares_to_buy,
                execution_value=execution_value,
                error_message=None,
                timestamp=timestamp
            )
        
        error_msg = f"Unknown order action: {order.action}"
        trade_logger.error(f"Order failed - {error_msg}")
        return TradeResult(
            order=order,
            executed=False,
            execution_price=current_price,
            executed_shares=0,
            execution_value=0,
            error_message=error_msg,
            timestamp=timestamp
        )

    def _handle_insufficient_cash(self, order, current_price, available_cash, timestamp):
        """Handle insufficient cash scenarios based on configuration"""
        
        required_cash = order.shares * current_price
        max_affordable_shares = int(available_cash / current_price) if available_cash >= current_price else 0
        affordability_ratio = (max_affordable_shares * current_price) / required_cash if required_cash > 0 else 0
        
        print(f"⚠️  INSUFFICIENT CASH for {order.ticker}:")
        print(f"   Requested: {order.shares} shares (${required_cash:.2f})")
        print(f"   Available: ${available_cash:.2f} (after ${getattr(self, 'min_cash_reserve', 10.0):.2f} reserve)")
        print(f"   Max affordable: {max_affordable_shares} shares ({affordability_ratio:.1%} of order)")
        
        # LOG: Insufficient cash details
        trade_logger.warning(f"Insufficient cash for {order.ticker}: need ${required_cash:.2f}, have ${available_cash:.2f}")
        trade_logger.info(f"Max affordable: {max_affordable_shares}/{order.shares} shares ({affordability_ratio:.1%})")
        
        # Handle based on partial fill mode
        if getattr(self, 'partial_fill_mode', PartialFillMode.AUTOMATIC) == PartialFillMode.AUTOMATIC:
            if max_affordable_shares > 0:
                print(f"✅ AUTO-FILLING: {max_affordable_shares} shares")
                trade_logger.info(f"AUTO-FILL: executing {max_affordable_shares} shares of {order.ticker}")
                return self._execute_partial_fill(order, max_affordable_shares, current_price, timestamp)
            else:
                error_msg = f"Cannot afford even 1 share. Need ${current_price:.2f}, have ${available_cash:.2f}"
                trade_logger.error(f"Partial fill failed - {error_msg}")
                return TradeResult(
                    order=order, executed=False, execution_price=current_price,
                    executed_shares=0, execution_value=0, timestamp=timestamp,
                    error_message=error_msg
                )
        
        # Fallback to reject
        error_msg = f"Insufficient cash: Need ${required_cash:.2f}, have ${available_cash:.2f}"
        trade_logger.info(f"Order rejected - {error_msg}")
        return TradeResult(
            order=order, executed=False, execution_price=current_price,
            executed_shares=0, execution_value=0, timestamp=timestamp,
            error_message=error_msg
        )

    # == 8. PARTIAL FILL HELPERS ==
    def _execute_partial_fill(self, order, shares, price, timestamp):
        """Execute a partial fill order"""
        if shares <= 0:
            return TradeResult(
                order=order, executed=False, execution_price=price,
                executed_shares=0, execution_value=0, timestamp=timestamp,
                error_message="No shares affordable for partial fill"
            )
        
        execution_value = shares * price
        print(f"📥 PAPER TRADE: BOUGHT {shares} shares of {order.ticker} at ${price:.2f} = ${execution_value:.2f} (PARTIAL FILL)")
        
        return TradeResult(
            order=order,
            executed=True,
            execution_price=price,
            executed_shares=shares,
            execution_value=execution_value,
            error_message=None,
            timestamp=timestamp
        )

    def _ask_partial_fill_confirmation(self, order, max_shares, price, available_cash, affordability_ratio, timestamp):
        """Ask user for confirmation on partial fill"""
        
        if max_shares <= 0:
            return TradeResult(
                order=order, executed=False, execution_price=price,
                executed_shares=0, execution_value=0, timestamp=timestamp,
                error_message=f"Cannot afford even 1 share: ${available_cash:.2f} available, ${price:.2f} needed"
            )
        
        print(f"🤔 PARTIAL FILL DECISION NEEDED:")
        print(f"   Can afford {max_shares}/{order.shares} shares ({affordability_ratio:.1%} of requested)")
        print(f"   Cost: ${max_shares * price:.2f} of ${available_cash:.2f} available")
        
        while True:
            response = input(f"   Execute partial fill of {max_shares} {order.ticker} shares? (y/n/s=skip): ").lower().strip()
            
            if response in ['y', 'yes']:
                return self._execute_partial_fill(order, max_shares, price, timestamp)
            elif response in ['n', 'no', 's', 'skip']:
                return TradeResult(
                    order=order, executed=False, execution_price=price,
                    executed_shares=0, execution_value=0, timestamp=timestamp,
                    error_message=f"Partial fill declined by user"
                )
            else:
                print("   Please enter 'y' for yes, 'n' for no, or 's' to skip")


    # == 9. PORTFOLIO UPDATE METHODS ==
    def _update_portfolio_holdings(self, result):
        """Update portfolio holdings after successful trade"""
        if not result.executed:
            return
        
        order = result.order
        ticker = order.ticker
        shares = result.executed_shares
        price = result.execution_price
        value = result.execution_value
        
        # LOG: Starting portfolio update
        trade_logger.info(f"Updating portfolio holdings for {ticker}")
        
        if order.action in [OrderType.SELL, OrderType.REDUCE]:
            if ticker in self.holdings:
                current_shares = self.holdings[ticker]['shares']
                remaining_shares = current_shares - shares
                
                trade_logger.info(f"Before: {ticker} had {current_shares} shares")
                
                if remaining_shares <= 0:
                    # Sold entire position
                    del self.holdings[ticker]
                    print(f"🗑️  Removed {ticker} position entirely")
                    trade_logger.info(f"POSITION CLOSED: Removed {ticker} position entirely")
                else:
                    # Reduce position
                    self.holdings[ticker]['shares'] = remaining_shares
                    # Adjust allocation proportionally
                    original_allocation = self.holdings[ticker]['allocation']
                    self.holdings[ticker]['allocation'] = original_allocation * (remaining_shares / current_shares)
                    print(f"📉 Reduced {ticker} to {remaining_shares} shares")
                    trade_logger.info(f"POSITION REDUCED: {ticker} now has {remaining_shares} shares (was {current_shares})")
                
                # Add cash from sale
                old_cash = self.cash
                self.cash += value
                trade_logger.info(f"Cash updated: ${old_cash:.2f} + ${value:.2f} = ${self.cash:.2f}")
                
        elif order.action == OrderType.BUY:
            old_cash = self.cash
            
            if ticker in self.holdings:
                # Add to existing position
                current_shares = self.holdings[ticker]['shares']
                current_basis = self.holdings[ticker]['shares'] * self.holdings[ticker]['entry_price']
                new_basis = current_basis + value
                new_shares = current_shares + shares
                new_avg_price = new_basis / new_shares
                
                trade_logger.info(f"Before: {ticker} had {current_shares} shares @ ${self.holdings[ticker]['entry_price']:.2f}")
                
                self.holdings[ticker].update({
                    'shares': new_shares,
                    'entry_price': new_avg_price,
                    'allocation': new_basis
                })
                print(f"📈 Increased {ticker} to {new_shares} shares")
                trade_logger.info(f"POSITION INCREASED: {ticker} now has {new_shares} shares @ ${new_avg_price:.2f} avg (was {current_shares} @ ${self.holdings[ticker]['entry_price']:.2f})")
            else:
                # New position
                self.holdings[ticker] = {
                    'shares': shares,
                    'entry_price': price,
                    'allocation': value
                }
                print(f"🆕 Added new {ticker} position: {shares} shares")
                trade_logger.info(f"NEW POSITION: Added {ticker} - {shares} shares @ ${price:.2f}")
            
            # Reduce cash
            self.cash -= value
            trade_logger.info(f"Cash updated: ${old_cash:.2f} - ${value:.2f} = ${self.cash:.2f}")
        
        trade_logger.info(f"Portfolio update complete for {ticker}")


    # == 10. REPORTING AND VISUALIZATION == 
    def generate_report(self):
        """Generate complete daily report"""
        print("=" * 60)
        print(f"📊 DAILY PORTFOLIO REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # Fetch data
        current_prices, volumes, price_history = self.fetch_current_data()
        if current_prices is None:
            print("❌ Failed to fetch market data")
            return
        
        # Calculate positions
        positions, total_value, total_cost_basis = self.calculate_position_metrics(current_prices)

        # FIXED: Use actual initial investment of $2000
        initial_investment = 2000.00  # Your real starting amount
        total_pnl = total_value - initial_investment  # Fixed calculation
        total_pnl_pct = (total_pnl / initial_investment) * 100  # Fixed percentage
        account_growth_percent = ((total_value / initial_investment) - 1) * 100  # Fixed growth

        print(f"\n💰 ACCOUNT VALUE SUMMARY:")
        print(f"   Total Account Value:    ${total_value:,.2f}")
        print(f"   Initial Investment:     ${initial_investment:,.2f}")
        print(f"   Cash Available:         ${self.cash:.2f}")
        print(f"   Total P&L:              ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
        print(f"   Account Growth:         {account_growth_percent:+.2f}%")
        
        # Benchmark performance
        print(f"\n📈 BENCHMARK PERFORMANCE:")
        if 'SPY' in current_prices:
            spy_change = ((current_prices['SPY'] - price_history['SPY'].iloc[-2]) / price_history['SPY'].iloc[-2]) * 100
            print(f"   S&P 500 (SPY):     ${current_prices['SPY']:.2f} ({spy_change:+.2f}%)")
        
        if 'IWM' in current_prices:
            iwm_change = ((current_prices['IWM'] - price_history['IWM'].iloc[-2]) / price_history['IWM'].iloc[-2]) * 100
            print(f"   Russell 2000 (IWM): ${current_prices['IWM']:.2f} ({iwm_change:+.2f}%)")
        
        if 'VIX' in current_prices:
            print(f"   VIX:               {current_prices['VIX']:.2f}")
        
        # Individual positions with weight analysis
        print(f"\n🏢 POSITION DETAILS:")
        print(f"{'Ticker':<6} {'Shares':<7} {'Entry':<8} {'Current':<8} {'Value':<10} {'P&L $':<10} {'P&L %':<8} {'Cur.Wt':<7} {'Tgt.Wt':<7} {'Drift':<6}")
        print("-" * 95)
        
        # Sort by P&L %
        positions.sort(key=lambda x: x['pnl_percent'], reverse=True)
        
        # Track positions that need rebalancing
        rebalance_alerts = []
        
        for pos in positions:
            drift_alert = ""
            if abs(pos['weight_drift']) > 5:  # >5% weight drift
                drift_alert = " ⚠️"
                rebalance_alerts.append(f"{pos['ticker']}: {pos['weight_drift']:+.1f}% drift")
            
            print(f"{pos['ticker']:<6} {pos['shares']:<7} ${pos['entry_price']:<7.2f} ${pos['current_price']:<7.2f} "
                f"${pos['current_value']:<9.2f} ${pos['pnl_dollar']:<9.2f} {pos['pnl_percent']:+.1f}%   "
                f"{pos['current_weight']:.1f}%   {pos['target_weight']:.1f}%   {pos['weight_drift']:+.1f}%{drift_alert}")
            
        alerts = self.check_alerts(positions)
        volume_alerts = self.get_volume_alerts(volumes, price_history)
        
        if alerts or volume_alerts or rebalance_alerts:
            print(f"\n⚠️  ALERTS:")
            for alert in alerts + volume_alerts:
                print(f"   {alert}")
            if rebalance_alerts:
                print(f"   📊 REBALANCING NEEDED:")
                for alert in rebalance_alerts:
                    print(f"      {alert}")
        else:
            print(f"\n✅ No alerts triggered")
        
        # Top movers
        print(f"\n📊 TOP MOVERS:")
        best_performer = max(positions, key=lambda x: x['pnl_percent'])
        worst_performer = min(positions, key=lambda x: x['pnl_percent'])
        print(f"   Best:  {best_performer['ticker']} ({best_performer['pnl_percent']:+.1f}%)")
        print(f"   Worst: {worst_performer['ticker']} ({worst_performer['pnl_percent']:+.1f}%)")
        
        # Generate JSON with total account context
        report_data = {
            'date': datetime.now().isoformat(),
            'account_value': total_value,
            'initial_investment': initial_investment,
            'cash_available': self.cash,
            'total_pnl_dollar': total_pnl,
            'total_pnl_percent': total_pnl_pct,
            'account_growth_percent': account_growth_percent,
            'positions': positions,
            'alerts': alerts,
            'volume_alerts': volume_alerts,
            'rebalancing_alerts': rebalance_alerts,
            'benchmarks': {
                'SPY': current_prices.get('SPY', 0),
                'IWM': current_prices.get('IWM', 0),
                'VIX': current_prices.get('VIX', 0)
            },
            'portfolio_metrics': {
                'total_positions': len(positions),
                'positions_profitable': len([p for p in positions if p['pnl_percent'] > 0]),
                'largest_position_weight': max([p['current_weight'] for p in positions]) if positions else 0,
                'concentration_risk': sum([p['current_weight'] for p in positions if p['current_weight'] > 15])
            }
        }
        
        # Generate formatted output file for AI analysis
        self.generate_analysis_file(report_data)

        # Generate performance chart
        self.plot_performance_chart(save_path='LLM Managed Portfolio Performance')

        # Generate position details chart
        self.plot_position_details(positions, total_value, save_path='LLM Position Details')
        
        # Export historical metrics
        self.export_historical_metrics(report_data)
        
        print(f"\n" + "=" * 60)
        print("📋 JSON DATA FOR CLAUDE ANALYSIS:")
        print("=" * 60)
        print(json.dumps(report_data, indent=2))
        
        return report_data
    
    def generate_analysis_file(self, report_data):
        """Generate formatted text file for AI analysis"""
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Create formatted content
        content = f"""Daily portfolio update for {current_date}. Here's the data:

{json.dumps(report_data, indent=2)}

Key questions:
- Any positions need rebalancing?
- Should I take profits/cut losses?
- Any new catalysts or news affecting holdings?
- Market outlook for tomorrow/this week?

Additional context:
- Portfolio total investment: ${self.total_investment:,.2f}
- Cash available: ${self.cash:.2f}
- Investment timeframe: August 5, 2025 to December 27, 2025
- Strategy: Catalyst-driven momentum with concentrated positions

Risk management parameters:
- Stop-loss triggers: CYTK (-18%), AMD (-13%), IONS (-19%), Others (-20%)
- Profit targets: High-growth (50%), Binary catalysts (40%), Speculative (100%), Value/Cyclical (30-40%)

Please provide analysis and trading recommendations based on this data."""

        # Write to file
        filename = 'portfolio_analysis_output.txt'
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n💾 Analysis file generated: {filename}")
            print("📋 Upload this file to Claude or copy/paste its contents for analysis")
        except Exception as e:
            print(f"❌ Error creating analysis file: {e}")
        
        return content
   
    def plot_performance_chart(self, save_path=None):
        """Create performance chart matching the reference style"""
        
        if not hasattr(self, 'price_data') or self.price_data is None:
            print("❌ No price data available for charting")
            return
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # FIXED: Use actual initial investment
        initial_investment = 2000.00  # Your real starting amount
        
        # Calculate portfolio performance over time
        portfolio_values = []
        spy_values = []
        iwm_values = []
        dates = self.price_data.index
        
        for date in dates:
            # Calculate daily portfolio value
            daily_portfolio_value = self.cash
            for ticker, position in self.holdings.items():
                if ticker in self.price_data.columns:
                    current_price = self.price_data.loc[date, ticker]
                    if not pd.isna(current_price):
                        daily_portfolio_value += position['shares'] * current_price
                    else:
                        daily_portfolio_value += position['allocation']
                else:
                    daily_portfolio_value += position['allocation']
            
            portfolio_values.append(daily_portfolio_value)
        
        # FIXED: Calculate benchmark values normalized to $2000 starting point
        if 'SPY' in self.price_data.columns:
            spy_start = self.price_data['SPY'].iloc[0]
            spy_values = (self.price_data['SPY'] / spy_start) * initial_investment
        
        if 'IWM' in self.price_data.columns:
            iwm_start = self.price_data['IWM'].iloc[0]
            iwm_values = (self.price_data['IWM'] / iwm_start) * initial_investment
        
        # Plot lines
        ax.plot(dates, portfolio_values, color='#1f77b4', linewidth=2.5, marker='o', markersize=3,
                label=f'Portfolio (${initial_investment:,.0f} Invested)', zorder=3)
        
        if len(spy_values) > 0:
            ax.plot(dates, spy_values, color='#ff7f0e', linewidth=2, linestyle='-',
                    label=f'S&P 500 (${initial_investment:,.0f} Invested)', zorder=2)
        
        if len(iwm_values) > 0:
            ax.plot(dates, iwm_values, color='#2ca02c', linewidth=2, linestyle='--',
                    label=f'Russell 2000 (${initial_investment:,.0f} Invested)', zorder=1)
        
        # Formatting
        ax.set_title('LLM Portfolio vs. S&P 500 vs. Russell 2000', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel(f'Value of ${initial_investment:,.0f} Investment', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.legend(loc='upper left', fontsize=11)
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Add performance annotations
        if len(portfolio_values) > 0:
            portfolio_return = ((portfolio_values[-1] - initial_investment) / initial_investment) * 100
            ax.annotate(f'{portfolio_return:+.1f}%', 
                    xy=(dates[-1], portfolio_values[-1]),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#1f77b4',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if len(spy_values) > 0:
            spy_return = ((spy_values.iloc[-1] - initial_investment) / initial_investment) * 100
            ax.annotate(f'{spy_return:+.1f}%', 
                    xy=(dates[-1], spy_values.iloc[-1]),
                    xytext=(10, -10), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#ff7f0e',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if len(iwm_values) > 0:
            iwm_return = ((iwm_values.iloc[-1] - initial_investment) / initial_investment) * 100
            ax.annotate(f'{iwm_return:+.1f}%', 
                    xy=(dates[-1], iwm_values.iloc[-1]),
                    xytext=(10, 0), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#2ca02c',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        # Format x-axis dates
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        num_days = len(dates)
        if num_days <= 7:
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        elif num_days <= 30:
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        else:
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Chart saved to {save_path}")
        
        plt.show()
        
    def plot_position_details(self, positions, total_value, save_path=None):
        """Create position details chart showing portfolio breakdown and performance"""
        
        if not positions:
            print("❌ No position data available for charting")
            return
        
        # Create figure with subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Position Details', fontsize=16, fontweight='bold')
        
        # Extract data for plotting
        tickers = [pos['ticker'] for pos in positions]
        current_values = [pos['current_value'] for pos in positions]
        pnl_dollars = [pos['pnl_dollar'] for pos in positions]
        pnl_percentages = [pos['pnl_percent'] for pos in positions]
        current_weights = [pos['current_weight'] for pos in positions]
        
        # Define colors for consistency
        colors = plt.cm.Set3(np.linspace(0, 1, len(positions)))
        profit_colors = ['#2E8B57' if pnl >= 0 else '#DC143C' for pnl in pnl_dollars]
        
        # 1. Portfolio Allocation (Pie Chart)
        ax1.pie(current_values, labels=tickers, autopct='%1.1f%%', startangle=90, colors=colors)
        ax1.set_title('Portfolio Allocation by Value', fontweight='bold', pad=20)
        
        # 2. Position Values (Horizontal Bar Chart)
        y_pos = np.arange(len(tickers))
        bars = ax2.barh(y_pos, current_values, color=colors, alpha=0.7)
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(tickers)
        ax2.set_xlabel('Current Value ($)')
        ax2.set_title('Position Values', fontweight='bold', pad=20)
        ax2.grid(axis='x', alpha=0.3)
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, current_values)):
            ax2.text(value + max(current_values) * 0.01, bar.get_y() + bar.get_height()/2, 
                    f'${value:.0f}', ha='left', va='center', fontsize=9)
        
        # 3. P&L Performance ($ and %)
        x_pos = np.arange(len(tickers))
        
        # Create twin axis for percentage
        ax3_twin = ax3.twinx()
        
        # Plot P&L dollars as bars
        bars3 = ax3.bar(x_pos, pnl_dollars, color=profit_colors, alpha=0.7, label='P&L ($)')
        ax3.set_xlabel('Positions')
        ax3.set_ylabel('P&L ($)', color='black')
        ax3.set_title('P&L Performance', fontweight='bold', pad=20)
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(tickers, rotation=45)
        ax3.grid(axis='y', alpha=0.3)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        # Plot P&L percentages as line
        line = ax3_twin.plot(x_pos, pnl_percentages, color='orange', marker='o', 
                            linewidth=2, markersize=6, label='P&L (%)')
        ax3_twin.set_ylabel('P&L (%)', color='orange')
        ax3_twin.tick_params(axis='y', labelcolor='orange')
        ax3_twin.axhline(y=0, color='orange', linestyle='--', alpha=0.5)
        
        # Add value labels on bars
        for bar, pnl_dollar, pnl_pct in zip(bars3, pnl_dollars, pnl_percentages):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + (max(pnl_dollars) * 0.02 if height >= 0 else min(pnl_dollars) * 0.02),
                    f'${pnl_dollar:.0f}', ha='center', va='bottom' if height >= 0 else 'top', fontsize=8)
        
        # 4. Weight Distribution vs Target
        ax4.barh(y_pos, current_weights, color=colors, alpha=0.7, label='Current Weight')
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(tickers)
        ax4.set_xlabel('Portfolio Weight (%)')
        ax4.set_title('Current Portfolio Weights', fontweight='bold', pad=20)
        ax4.grid(axis='x', alpha=0.3)
        
        # Add weight labels
        for i, weight in enumerate(current_weights):
            ax4.text(weight + max(current_weights) * 0.01, i, f'{weight:.1f}%', 
                    ha='left', va='center', fontsize=9)
        
        # Add portfolio summary text box
        total_pnl = sum(pnl_dollars)
        total_cost_basis = sum([pos['cost_basis'] for pos in positions])
        total_pnl_pct = (total_pnl / total_cost_basis) * 100 if total_cost_basis > 0 else 0
        profitable_positions = len([p for p in pnl_dollars if p >= 0])
        
        summary_text = f"""Portfolio Summary:
        Total Value: ${total_value:,.0f}
        Total P&L: ${total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)
        Profitable Positions: {profitable_positions}/{len(positions)}
        Largest Position: {max(current_weights):.1f}%
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        # Add text box to the figure
        fig.text(0.02, 0.02, summary_text, fontsize=10, 
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8),
                verticalalignment='bottom')
        
        # Adjust layout to prevent overlapping
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.15)  # Make room for summary text
        
        # Save the chart
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Position Details saved to {save_path}")
        
        plt.show()
        # plt.close()  # Clean up to prevent memory issues
    
    
        """Export daily metrics to CSV for historical tracking"""
        
        filename = 'portfolio_historical_metrics.csv'
        
        # Current metrics to track
        current_metrics = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'account_value': report_data['account_value'],
            'total_pnl_dollar': report_data['total_pnl_dollar'],
            'total_pnl_percent': report_data['total_pnl_percent'],
            'account_growth_percent': report_data['account_growth_percent'],
            'spy_price': report_data['benchmarks']['SPY'],
            'iwm_price': report_data['benchmarks']['IWM'],
            'vix_level': report_data['benchmarks']['VIX'],
            'positions_profitable': report_data['portfolio_metrics']['positions_profitable'],
            'largest_position_weight': report_data['portfolio_metrics']['largest_position_weight'],
            'concentration_risk': report_data['portfolio_metrics']['concentration_risk'],
            'total_alerts': len(report_data['alerts']) + len(report_data['volume_alerts']) + len(report_data['rebalancing_alerts'])
        }
        
        # Add individual position performance
        for pos in report_data['positions']:
            current_metrics[f"{pos['ticker']}_price"] = pos['current_price']
            current_metrics[f"{pos['ticker']}_pnl_pct"] = pos['pnl_percent']
            current_metrics[f"{pos['ticker']}_weight"] = pos['current_weight']
            current_metrics[f"{pos['ticker']}_drift"] = pos['weight_drift']
        
        # Create DataFrame
        df_new = pd.DataFrame([current_metrics])
        
        # Append to existing file or create new one
        try:
            if os.path.exists(filename):
                df_existing = pd.read_csv(filename)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined.to_csv(filename, index=False)
            print(f"📈 Historical metrics saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving historical metrics: {e}")

    def export_historical_metrics(self, report_data):
        """Export enhanced daily metrics to CSV for historical tracking"""
        
        filename = 'portfolio_historical_metrics.csv'
        
        # Enhanced metrics to track
        current_metrics = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'account_value': report_data['account_value'],
            'initial_investment': report_data['initial_investment'],
            'cash_available': report_data['cash_available'],
            'total_pnl_dollar': report_data['total_pnl_dollar'],
            'total_pnl_percent': report_data['total_pnl_percent'],
            'account_growth_percent': report_data['account_growth_percent'],
            'spy_price': report_data['benchmarks']['SPY'],
            'iwm_price': report_data['benchmarks']['IWM'],
            'vix_level': report_data['benchmarks']['VIX'],
            'positions_profitable': report_data['portfolio_metrics']['positions_profitable'],
            'total_positions': report_data['portfolio_metrics']['total_positions'],
            'largest_position_weight': report_data['portfolio_metrics']['largest_position_weight'],
            'concentration_risk': report_data['portfolio_metrics']['concentration_risk'],
            'total_alerts': len(report_data['alerts']) + len(report_data['volume_alerts']) + len(report_data['rebalancing_alerts'])
        }
        
        # Add individual position details (enhanced)
        for pos in report_data['positions']:
            ticker = pos['ticker']
            current_metrics[f"{ticker}_shares"] = pos['shares']
            current_metrics[f"{ticker}_entry_price"] = pos['entry_price']
            current_metrics[f"{ticker}_current_price"] = pos['current_price']
            current_metrics[f"{ticker}_current_value"] = pos['current_value']
            current_metrics[f"{ticker}_pnl_dollar"] = pos['pnl_dollar']
            current_metrics[f"{ticker}_pnl_pct"] = pos['pnl_percent']
            current_metrics[f"{ticker}_weight"] = pos['current_weight']
            current_metrics[f"{ticker}_weight_drift"] = pos['weight_drift']
        
        # Create DataFrame
        df_new = pd.DataFrame([current_metrics])
        
        # Append to existing file or create new one
        try:
            if os.path.exists(filename):
                df_existing = pd.read_csv(filename)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined.to_csv(filename, index=False)
            print(f"📈 Enhanced historical metrics saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving historical metrics: {e}")
# Usage
# if __name__ == "__main__":
#     reporter = DailyPortfolioReport()
#     reporter.generate_report()

# Usage 
if __name__ == "__main__":
    
    print("\n" + "=" * 60)
    print("INTEGRATION WITH YOUR PORTFOLIO SCRIPT:")
    print("=" * 60)
    
    # This would be integrated into your existing Daily_Portfolio_Script.py
    # from Daily_Portfolio_Script import DailyPortfolioReport
    
    # Create portfolio instance
    portfolio = DailyPortfolioReport()
    
    # Execute automated trading from document
    # Will automatically look for doc if doc is unspecified
    results = portfolio.execute_automated_trading()
    
    # Generate updated portfolio report
    portfolio.generate_report()
    

# STEPS:
# 1. Save Claude's response as 'claude_recommendations.txt'
# 2. Add the automated trading methods to your DailyPortfolioReport class
# 3. Run: python Daily_Portfolio_Script.py --execute-trades claude_recommendations.txt
# 4. Review execution report and update holdings in script
    