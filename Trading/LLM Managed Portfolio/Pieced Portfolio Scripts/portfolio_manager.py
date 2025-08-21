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
        """Save current portfolio state to JSON file"""
        try:
            # Get the parent directory (one level up from Pieced Portfolio Scripts)
            parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            state_file = os.path.join(parent_dir, 'portfolio_state.json')
            
            state = {
                'cash': self.cash,
                'holdings': self.holdings,
                'benchmarks': self.benchmarks,
                'partial_fill_mode': self.partial_fill_mode.value,
                'min_cash_reserve': self.min_cash_reserve,
                'partial_fill_threshold': self.partial_fill_threshold,
                'last_updated': json.dumps(str(pd.Timestamp.now()))
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=4, default=str)
            
            print(f"💾 Portfolio state saved to {state_file}")
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
        """Load positions from the most recent portfolio performance history"""
        try:
            # Get the parent directory (one level up from Pieced Portfolio Scripts)
            parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
            history_file = os.path.join(parent_dir, 'portfolio_performance_history.csv')
            
            if not os.path.exists(history_file):
                print("📊 No portfolio history found - using current holdings")
                return self.holdings
            
            import pandas as pd
            df = pd.read_csv(history_file)
            
            if df.empty:
                print("📊 Portfolio history is empty - using current holdings") 
                return self.holdings
            
            # Get the most recent entry
            latest = df.iloc[-1]
            
            # Parse positions from the latest entry
            previous_positions = {}
            position_columns = [col for col in df.columns if col.endswith('_shares')]
            
            for col in position_columns:
                ticker = col.replace('_shares', '').upper()
                shares = int(latest[col]) if pd.notna(latest[col]) and latest[col] != 0 else 0
                
                if shares > 0:
                    # Try to get entry price from current holdings or use a default
                    entry_price = self.holdings.get(ticker, {}).get('entry_price', 0.0)
                    previous_positions[ticker] = {
                        'shares': shares,
                        'entry_price': entry_price,
                        'allocation': shares * entry_price
                    }
            
            if previous_positions:
                print(f"📈 Loaded {len(previous_positions)} positions from previous day")
                return previous_positions
            else:
                print("📊 No previous positions found - using current holdings")
                return self.holdings
                
        except Exception as e:
            print(f"❌ Error loading previous positions: {e}")
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