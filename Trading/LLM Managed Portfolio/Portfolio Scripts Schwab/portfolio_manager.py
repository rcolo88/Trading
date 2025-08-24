"""
Portfolio State Management Module
Handles portfolio holdings, cash, state persistence, and basic portfolio operations
"""

import json
import os
import pandas as pd
from typing import Dict, Any
from trading_models import PartialFillMode


class PortfolioManager:
    """Manages portfolio state, holdings, and cash operations"""
    
    def __init__(self):
        """Initialize portfolio with default holdings and load state if available"""
        # Updated portfolio holdings (from corrected allocation)
        self.holdings = {
            'IONS': {'shares': 3, 'entry_price': 37.01, 'allocation': 111.03},
            'CRGY': {'shares': 26, 'entry_price': 9.10, 'allocation': 236.60},
            'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45},
            'CYTK': {'shares': 6, 'entry_price': 36.58, 'allocation': 219.48},
            'SOUN': {'shares': 19, 'entry_price': 11.01, 'allocation': 209.19},
            'QS': {'shares': 23, 'entry_price': 8.50, 'allocation': 138.00},
            'RIG': {'shares': 65, 'entry_price': 3.00, 'allocation': 195.00},
            'AMD': {'shares': 1, 'entry_price': 176.78, 'allocation': 176.78},
            'NVDA': {'shares': 1, 'entry_price': 175.00, 'allocation': 135.00},
            'GOOGL': {'shares': 1, 'entry_price': 193.00, 'allocation': 193.00}
        }
        
        self.benchmarks = ['SPY', 'IWM', 'VIX']
        
        # Portfolio configuration
        self.partial_fill_mode = PartialFillMode.AUTOMATIC
        self.min_cash_reserve = 0.00
        self.partial_fill_threshold = 0.8  # 80% threshold for SMART mode
        
        # Load existing state or set defaults
        if not self.load_portfolio_state():
            self.cash = 0.00
    
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
    
    def cleanup_sold_positions(self):
        """Remove positions with 0 shares from holdings"""
        positions_to_remove = []
        for ticker, position in self.holdings.items():
            if position.get('shares', 0) == 0:
                positions_to_remove.append(ticker)
        
        for ticker in positions_to_remove:
            print(f"🧹 Removing sold position: {ticker}")
            del self.holdings[ticker]
        
        if positions_to_remove:
            self.save_portfolio_state()
        
        return len(positions_to_remove)
    
    def save_portfolio_state(self):
        """Save current portfolio state to JSON file and create dated backup"""
        try:
            from datetime import datetime
            
            # Get the parent directory (one level up from Portfolio Scripts)
            parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            
            # Create state data
            current_time = pd.Timestamp.now()
            state = {
                'timestamp': current_time.isoformat(),
                'cash': self.cash,
                'holdings': self.holdings,
                'benchmarks': self.benchmarks,
                'partial_fill_mode': self.partial_fill_mode.value,
                'min_cash_reserve': self.min_cash_reserve,
                'partial_fill_threshold': self.partial_fill_threshold,
                'last_updated': str(current_time)
            }
            
            # Save current state file (main portfolio_state.json)
            state_file = os.path.join(parent_dir, 'portfolio_state.json')
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=4, default=str)
            
            # Save dated backup to Portfolio States folder
            stats_dir = os.path.join(parent_dir, 'Portfolio States')
            os.makedirs(stats_dir, exist_ok=True)
            
            # Format date as mmddyy (e.g., 082225 for Aug 22, 2025)
            date_str = current_time.strftime('%m%d%y')
            dated_file = os.path.join(stats_dir, f'portfolio_state_{date_str}.json')
            
            with open(dated_file, 'w') as f:
                json.dump(state, f, indent=4, default=str)
            
            print(f"💾 Portfolio state saved to {state_file}")
            print(f"📊 Dated backup saved to Portfolio States/portfolio_state_{date_str}.json")
            return True
            
        except Exception as e:
            print(f"❌ Error saving portfolio state: {e}")
            return False
    
    def load_portfolio_state(self):
        """Load portfolio state from JSON file if it exists"""
        try:
            # Get the parent directory (one level up from Pieced Portfolio Scripts)  
            parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            state_file = os.path.join(parent_dir, 'portfolio_state.json')
            
            if not os.path.exists(state_file):
                print("💡 No existing portfolio state found - using defaults")
                return False
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            # Load state values
            self.cash = float(state.get('cash', 0.00))
            self.holdings = state.get('holdings', self.holdings)
            self.benchmarks = state.get('benchmarks', self.benchmarks)
            
            # Load configuration
            if 'partial_fill_mode' in state:
                self.partial_fill_mode = PartialFillMode.from_string(state['partial_fill_mode'])
            self.min_cash_reserve = float(state.get('min_cash_reserve', 0.00))
            self.partial_fill_threshold = float(state.get('partial_fill_threshold', 0.8))
            
            print(f"✅ Portfolio state loaded from {state_file}")
            print(f"   Cash: ${self.cash:.2f}")
            print(f"   Holdings: {len(self.holdings)} positions")
            print(f"   Partial Fill Mode: {self.partial_fill_mode.value}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading portfolio state: {e}")
            return False
    
    def load_positions_from_previous_day(self):
        """Load positions from the most recent dated portfolio state file in Portfolio States/"""
        try:
            import glob
            from datetime import datetime
            
            # Get the parent directory (one level up from Portfolio Scripts)
            parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            stats_dir = os.path.join(parent_dir, 'Portfolio States')
            
            if not os.path.exists(stats_dir):
                print("📊 No Portfolio States folder found - using current holdings")
                return self.holdings
            
            # Find all dated portfolio state files
            pattern = os.path.join(stats_dir, 'portfolio_state_*.json')
            state_files = glob.glob(pattern)
            
            if not state_files:
                print("📊 No dated portfolio state files found - using current holdings")
                return self.holdings
            
            # Parse dates and find most recent file
            dated_files = []
            for file_path in state_files:
                filename = os.path.basename(file_path)
                # Extract date from filename like "portfolio_state_082225.json"
                if filename.startswith('portfolio_state_') and filename.endswith('.json'):
                    date_part = filename[16:-5]  # Remove "portfolio_state_" and ".json"
                    if len(date_part) == 6:  # mmddyy format
                        try:
                            month = int(date_part[:2])
                            day = int(date_part[2:4])
                            year_2digit = int(date_part[4:6])
                            
                            # Convert 2-digit year to 4-digit (assume 20xx for years 00-99)
                            if year_2digit >= 0:
                                full_year = 2000 + year_2digit
                            
                            file_date = datetime(full_year, month, day)
                            dated_files.append((file_date, file_path))
                        except ValueError:
                            continue  # Skip files with invalid date formats
            
            if not dated_files:
                print("📊 No valid dated portfolio state files found - using current holdings")
                return self.holdings
            
            # Sort by date (most recent first) and get the latest file
            dated_files.sort(key=lambda x: x[0], reverse=True)
            latest_date, latest_file = dated_files[0]
            
            # Load the most recent state file
            with open(latest_file, 'r') as f:
                saved_state = json.load(f)
            
            saved_holdings = saved_state.get('holdings', {})
            saved_cash = float(saved_state.get('cash', 0.0))
            
            if saved_holdings:
                print(f"📈 Loading {len(saved_holdings)} positions from most recent state")
                print(f"   File: {os.path.basename(latest_file)}")
                print(f"   Date: {latest_date.strftime('%m/%d/%Y')}")
                print(f"   Timestamp: {saved_state.get('timestamp', 'Unknown')}")
                
                # Also update cash from saved state
                if saved_cash != self.cash:
                    print(f"💰 Updating cash: ${self.cash:.2f} → ${saved_cash:.2f}")
                    self.cash = saved_cash
                
                return saved_holdings
            else:
                print("📊 No positions in most recent state file - using current holdings")
                return self.holdings
                
        except Exception as e:
            print(f"❌ Error loading dated portfolio state: {e}")
            print("📊 Using current holdings as fallback")
            return self.holdings
    
    def get_total_investment(self):
        """Calculate total investment across all positions"""
        total = 0
        for ticker, position in self.holdings.items():
            if 'allocation' in position:
                total += position['allocation']
            else:
                # Calculate from shares * entry_price if allocation not stored
                shares = position.get('shares', 0)
                entry_price = position.get('entry_price', 0)
                total += shares * entry_price
        return total
    
    def get_portfolio_tickers(self):
        """Get list of all tickers in portfolio plus benchmarks"""
        return list(self.holdings.keys()) + self.benchmarks
    
    def update_position(self, ticker: str, shares: int, entry_price: float = None):
        """Update or create a position in the portfolio"""
        if ticker not in self.holdings:
            self.holdings[ticker] = {
                'shares': 0,
                'entry_price': entry_price or 0.0,
                'allocation': 0
            }
        
        old_shares = self.holdings[ticker]['shares']
        self.holdings[ticker]['shares'] = shares
        
        if entry_price is not None:
            self.holdings[ticker]['entry_price'] = entry_price
        
        # Update allocation
        self.holdings[ticker]['allocation'] = shares * self.holdings[ticker]['entry_price']
        
        print(f"📊 Updated position: {ticker} {old_shares} → {shares} shares")
        
        # Save state after update
        self.save_portfolio_state()
    
    def add_cash(self, amount: float, description: str = ""):
        """Add cash to portfolio"""
        self.cash += amount
        print(f"💰 Added ${amount:.2f} to cash{' - ' + description if description else ''}")
        print(f"   New cash balance: ${self.cash:.2f}")
        self.save_portfolio_state()
    
    def subtract_cash(self, amount: float, description: str = ""):
        """Subtract cash from portfolio"""
        if amount > self.cash:
            print(f"❌ Insufficient cash: Need ${amount:.2f}, have ${self.cash:.2f}")
            return False
        
        self.cash -= amount
        print(f"💸 Subtracted ${amount:.2f} from cash{' - ' + description if description else ''}")
        print(f"   New cash balance: ${self.cash:.2f}")
        self.save_portfolio_state()
        return True
    
    def get_position_info(self, ticker: str):
        """Get detailed information about a specific position"""
        return self.holdings.get(ticker, None)
    
    def get_portfolio_summary(self):
        """Get a summary of the entire portfolio"""
        return {
            'cash': self.cash,
            'holdings': self.holdings.copy(),
            'total_positions': len(self.holdings),
            'total_investment': self.get_total_investment(),
            'benchmarks': self.benchmarks,
            'partial_fill_mode': self.partial_fill_mode.value
        }