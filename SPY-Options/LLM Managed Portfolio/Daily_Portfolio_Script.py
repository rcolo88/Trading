# Daily Portfolio Data Collection Script
# Run this daily and paste the output to Claude for analysis

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class DailyPortfolioReport:
    def __init__(self):
        # Updated portfolio holdings (from your corrected allocation)
        self.holdings = {
            'IONS': {'shares': 8, 'entry_price': 37.01, 'allocation': 296.08},
            'CRGY': {'shares': 26, 'entry_price': 9.10, 'allocation': 236.60},
            'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45},
            'CYTK': {'shares': 6, 'entry_price': 36.58, 'allocation': 219.48},
            'SOUN': {'shares': 19, 'entry_price': 11.01, 'allocation': 209.19},
            'QS': {'shares': 33, 'entry_price': 6.00, 'allocation': 198.00},
            'RIG': {'shares': 65, 'entry_price': 3.00, 'allocation': 195.00},
            'AMD': {'shares': 1, 'entry_price': 176.78, 'allocation': 176.78}
        }
        
        self.benchmarks = ['SPY', 'IWM', 'VIX']
        self.total_investment = 1964.58
        self.cash = 35.42
        
    def fetch_current_data(self):
        """Fetch current market data for all positions"""
        tickers = list(self.holdings.keys()) + self.benchmarks
        
        try:
            # Get current prices
            current_data = yf.download(tickers, period='5d', progress=False)['Close']
            if len(tickers) == 1:
                current_data = pd.DataFrame({tickers[0]: current_data})
            
            # Get volume data
            volume_data = yf.download(tickers, period='5d', progress=False)['Volume']
            if len(tickers) == 1:
                volume_data = pd.DataFrame({tickers[0]: volume_data})
                
            return current_data.iloc[-1], volume_data.iloc[-1], current_data
            
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None, None, None
    
    def calculate_position_metrics(self, current_prices):
        """Calculate key metrics for each position"""
        positions = []
        total_current_value = self.cash
        
        for ticker, position in self.holdings.items():
            if ticker in current_prices:
                current_price = current_prices[ticker]
                current_value = position['shares'] * current_price
                total_current_value += current_value
                
                pnl_dollar = current_value - position['allocation']
                pnl_percent = (pnl_dollar / position['allocation']) * 100
                daily_change = ((current_price - position['entry_price']) / position['entry_price']) * 100
                
                # Calculate multiple weight metrics
                current_weight = (current_value / total_current_value) * 100 if total_current_value > 0 else 0
                target_weight = (position['allocation'] / self.total_investment) * 100
                weight_drift = current_weight - target_weight
                
                positions.append({
                    'ticker': ticker,
                    'shares': position['shares'],
                    'entry_price': position['entry_price'],
                    'current_price': current_price,
                    'current_value': current_value,
                    'pnl_dollar': pnl_dollar,
                    'pnl_percent': pnl_percent,
                    'daily_change': daily_change,
                    'current_weight': current_weight,
                    'target_weight': target_weight,
                    'weight_drift': weight_drift,
                    'initial_allocation': position['allocation']
                })
        
        return positions, total_current_value
    
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
        positions, total_value = self.calculate_position_metrics(current_prices)
        
        # Portfolio summary with account value context
        total_pnl = total_value - (self.total_investment + self.cash)
        total_pnl_pct = (total_pnl / self.total_investment) * 100
        account_value = total_value  # This is your total account value
        
        print(f"\n💰 ACCOUNT VALUE SUMMARY:")
        print(f"   Total Account Value:    ${account_value:,.2f}")
        print(f"   Initial Investment:     ${self.total_investment:,.2f}")
        print(f"   Cash Available:         ${self.cash:.2f}")
        print(f"   Total P&L:              ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
        print(f"   Account Growth:         {((account_value / (self.total_investment + self.cash)) - 1) * 100:+.2f}%")
        
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
            'initial_investment': self.total_investment,
            'cash_available': self.cash,
            'total_pnl_dollar': total_pnl,
            'total_pnl_percent': total_pnl_pct,
            'account_growth_percent': ((total_value / (self.total_investment + self.cash)) - 1) * 100,
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

# Usage
if __name__ == "__main__":
    reporter = DailyPortfolioReport()
    reporter.generate_report()
    