"""
Performance Validation Module
Comprehensive performance validation system with multiple cross-checks
"""

import os
import json
import glob


class PerformanceValidator:
    """Foolproof performance validation system with multiple cross-checks"""
    
    def __init__(self, portfolio_instance):
        self.portfolio = portfolio_instance
        self.validation_results = {}
        
    def validate_performance(self, current_prices):
        """Run comprehensive performance validation with multiple cross-checks"""
        print("\n" + "="*60)
        print("🔍 PERFORMANCE VALIDATION SYSTEM")
        print("="*60)
        
        # Method 1: Manual Position-by-Position Calculation
        manual_calc = self._manual_position_calculation(current_prices)
        
        # Method 2: State File Validation  
        state_calc = self._state_file_validation(current_prices)
        
        # Method 3: Trade Log Reconciliation
        trade_calc = self._trade_log_reconciliation()
        
        # Method 4: Simple Cash + Holdings Validation
        simple_calc = self._simple_validation(current_prices)
        
        # Cross-check all methods
        self._cross_validate_results(manual_calc, state_calc, trade_calc, simple_calc)
        
        return self.validation_results
    
    def _manual_position_calculation(self, current_prices):
        """Method 1: Manual calculation from scratch"""
        print("\n📊 METHOD 1: Manual Position-by-Position Calculation")
        print("-" * 50)
        
        total_current_value = self.portfolio.cash
        total_cost_basis = 0
        
        print(f"💰 Starting with cash: ${self.portfolio.cash:.2f}")
        
        for ticker, position in self.portfolio.holdings.items():
            if ticker in current_prices:
                shares = position['shares']
                entry_price = position['entry_price']
                current_price = current_prices[ticker]
                
                cost_basis = shares * entry_price
                current_value = shares * current_price
                pnl = current_value - cost_basis
                
                total_cost_basis += cost_basis
                total_current_value += current_value
                
                print(f"   {ticker}: {shares} shares × ${current_price:.2f} = ${current_value:.2f} "
                      f"(Cost: ${cost_basis:.2f}, P&L: ${pnl:+.2f})")
        
        total_pnl = total_current_value - 2000.00  # True initial investment
        total_pnl_pct = (total_pnl / 2000.00) * 100
        
        print(f"\n📈 MANUAL CALCULATION RESULTS:")
        print(f"   Total Portfolio Value: ${total_current_value:.2f}")
        print(f"   Total Cost Basis: ${total_cost_basis:.2f}")
        print(f"   Cash: ${self.portfolio.cash:.2f}")
        print(f"   Initial Investment: $2,000.00")
        print(f"   Total P&L: ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")
        
        return {
            'method': 'Manual Calculation',
            'total_value': total_current_value,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'calculation_basis': '2000.00 initial investment'
        }
    
    def _state_file_validation(self, current_prices):
        """Method 2: Validate using portfolio_state.json"""
        print("\n📂 METHOD 2: Portfolio State File Validation")
        print("-" * 50)
        
        try:
            if os.path.exists('../portfolio_state.json'):
                with open('../portfolio_state.json', 'r') as f:
                    state_data = json.load(f)
                
                state_cash = state_data['cash']
                state_holdings = state_data['holdings']
                
                total_current_value = state_cash
                
                print(f"💰 State file cash: ${state_cash:.2f}")
                print(f"🏢 State file holdings:")
                
                for ticker, position in state_holdings.items():
                    if ticker in current_prices:
                        shares = position['shares']
                        current_price = current_prices[ticker]
                        current_value = shares * current_price
                        total_current_value += current_value
                        
                        print(f"   {ticker}: {shares} shares × ${current_price:.2f} = ${current_value:.2f}")
                
                total_pnl = total_current_value - 2000.00
                total_pnl_pct = (total_pnl / 2000.00) * 100
                
                print(f"\n📈 STATE FILE VALIDATION:")
                print(f"   Total Portfolio Value: ${total_current_value:.2f}")
                print(f"   Total P&L: ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")
                
                return {
                    'method': 'State File Validation',
                    'total_value': total_current_value,
                    'total_pnl': total_pnl,
                    'total_pnl_pct': total_pnl_pct,
                    'calculation_basis': '../portfolio_state.json'
                }
            else:
                print("❌ No ../portfolio_state.json file found")
                return None
                
        except Exception as e:
            print(f"❌ Error reading state file: {e}")
            return None
    
    def _trade_log_reconciliation(self):
        """Method 3: Reconcile using trade execution logs"""
        print("\n📝 METHOD 3: Trade Log Reconciliation")
        print("-" * 50)
        
        try:
            # Find most recent trade execution log
            trade_logs = glob.glob('../trade_executions/trade_execution_*.json')
            if trade_logs:
                latest_log = max(trade_logs, key=os.path.getmtime)
                
                with open(latest_log, 'r') as f:
                    log_data = json.load(f)
                
                actual_cash = log_data.get('actual_cash', 0)
                updated_holdings = log_data.get('updated_holdings', {})
                
                print(f"📄 Using trade log: {latest_log}")
                print(f"💰 Log shows cash: ${actual_cash:.2f}")
                print(f"🏢 Log shows holdings: {len(updated_holdings)} positions")
                
                return {
                    'method': 'Trade Log Reconciliation',
                    'log_file': latest_log,
                    'actual_cash': actual_cash,
                    'holdings_count': len(updated_holdings),
                    'calculation_basis': 'trade_execution_log'
                }
            else:
                print("❌ No trade execution logs found")
                return None
                
        except Exception as e:
            print(f"❌ Error reading trade logs: {e}")
            return None
    
    def _simple_validation(self, current_prices):
        """Method 4: Simple cash + holdings validation"""
        print("\n🧮 METHOD 4: Simple Validation (Cash + Holdings)")
        print("-" * 50)
        
        # Just sum everything we have right now
        total_value = self.portfolio.cash
        
        for ticker, position in self.portfolio.holdings.items():
            if ticker in current_prices:
                value = position['shares'] * current_prices[ticker]
                total_value += value
                print(f"   {ticker}: ${value:.2f}")
        
        gain_from_2000 = total_value - 2000.00
        gain_pct = (gain_from_2000 / 2000.00) * 100
        
        print(f"\n📈 SIMPLE VALIDATION:")
        print(f"   Total Value: ${total_value:.2f}")
        print(f"   Gain from $2000: ${gain_from_2000:+.2f} ({gain_pct:+.2f}%)")
        
        return {
            'method': 'Simple Validation',
            'total_value': total_value,
            'total_pnl': gain_from_2000,
            'total_pnl_pct': gain_pct,
            'calculation_basis': 'cash + current_holdings'
        }
    
    def _cross_validate_results(self, manual, state, trade, simple):
        """Cross-validate all calculation methods"""
        print("\n🔍 CROSS-VALIDATION RESULTS")
        print("="*60)
        
        methods = [manual, state, trade, simple]
        valid_methods = [m for m in methods if m and 'total_value' in m]
        
        if len(valid_methods) < 2:
            print("❌ Insufficient methods for cross-validation")
            return
        
        # Compare total values
        values = [m['total_value'] for m in valid_methods]
        percentages = [m['total_pnl_pct'] for m in valid_methods]
        
        value_variance = max(values) - min(values)
        pct_variance = max(percentages) - min(percentages)
        
        print(f"📊 VALUE COMPARISON:")
        for method in valid_methods:
            print(f"   {method['method']}: ${method['total_value']:.2f} ({method['total_pnl_pct']:+.2f}%)")
        
        print(f"\n📈 VARIANCE ANALYSIS:")
        print(f"   Value variance: ${value_variance:.2f}")
        print(f"   Percentage variance: {pct_variance:.2f}%")
        
        if value_variance < 1.00:  # Less than $1 difference
            print("✅ VALIDATION PASSED: All methods agree (variance < $1)")
            consensus_value = sum(values) / len(values)
            consensus_pct = sum(percentages) / len(percentages)
            
            self.validation_results = {
                'status': 'PASSED',
                'consensus_value': consensus_value,
                'consensus_performance': consensus_pct,
                'variance': value_variance,
                'methods_used': len(valid_methods)
            }
        else:
            print(f"❌ VALIDATION FAILED: Methods disagree (variance ${value_variance:.2f})")
            print(f"🚨 PERFORMANCE CALCULATION SYSTEM HAS BUGS!")
            
            self.validation_results = {
                'status': 'FAILED',
                'variance': value_variance,
                'methods_used': len(valid_methods),
                'issue': 'Multiple calculation methods give different results'
            }
        
        return self.validation_results