# Daily Portfolio Data Collection Script
# Run this daily and paste the output to Claude for analysis

import yfinance as yf
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class DailyPortfolioReport:
    def __init__(self):
        # Updated portfolio holdings (from your corrected allocation)
        self.holdings = {
            'IONS': {'shares': 3, 'entry_price': 37.01, 'allocation': 111.03},  # Reduced from 4 shares
            'CRGY': {'shares': 26, 'entry_price': 9.10, 'allocation': 236.60},  # No change
            'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45}, # No change
            'CYTK': {'shares': 6, 'entry_price': 36.58, 'allocation': 219.48},  # No change
            'SOUN': {'shares': 19, 'entry_price': 11.01, 'allocation': 209.19}, # No change
            'QS': {'shares': 23, 'entry_price': 6.00, 'allocation': 138.00},    # No change
            'RIG': {'shares': 65, 'entry_price': 3.00, 'allocation': 195.00},   # No change
            'AMD': {'shares': 1, 'entry_price': 176.78, 'allocation': 176.78},  # No change
            'NVDA': {'shares': 1, 'entry_price': 175.00, 'allocation': 135.00}, # NEW POSITION
            'GOOGL': {'shares': 1, 'entry_price': 193.00, 'allocation': 193.00} # NEW POSITION
        }

        self.benchmarks = ['SPY', 'IWM', 'VIX']
        self.total_investment = 1964.58  # Unchanged - original investment
        self.cash = 2.34  # Minimal cash remaining
    
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

        # Generate performance chart
        self.plot_performance_chart()
        
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
        
        # Calculate portfolio performance over time
        portfolio_values = []
        spy_values = []
        iwm_values = []
        dates = self.price_data.index
        
        initial_portfolio_value = self.total_investment + self.cash
        
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
        
        # Calculate benchmark values (normalized to start at same dollar amount)
        if 'SPY' in self.price_data.columns:
            spy_start = self.price_data['SPY'].iloc[0]
            spy_values = (self.price_data['SPY'] / spy_start) * initial_portfolio_value
        
        if 'IWM' in self.price_data.columns:
            iwm_start = self.price_data['IWM'].iloc[0]
            iwm_values = (self.price_data['IWM'] / iwm_start) * initial_portfolio_value
        
        # Plot lines
        ax.plot(dates, portfolio_values, color='#1f77b4', linewidth=2.5, marker='o', markersize=3,
                label=f'Portfolio (${initial_portfolio_value:,.0f} Invested)', zorder=3)
        
        if len(spy_values) > 0:
            ax.plot(dates, spy_values, color='#ff7f0e', linewidth=2, linestyle='-',
                    label=f'S&P 500 (${initial_portfolio_value:,.0f} Invested)', zorder=2)
        
        if len(iwm_values) > 0:
            ax.plot(dates, iwm_values, color='#2ca02c', linewidth=2, linestyle='--',
                    label=f'Russell 2000 (${initial_portfolio_value:,.0f} Invested)', zorder=1)
        
        # Formatting
        ax.set_title('LLM Portfolio vs. S&P 500 vs. Russell 2000', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel(f'Value of ${initial_portfolio_value:,.0f} Investment', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.legend(loc='upper left', fontsize=11)
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Add performance annotations
        if len(portfolio_values) > 0:
            portfolio_return = ((portfolio_values[-1] - initial_portfolio_value) / initial_portfolio_value) * 100
            ax.annotate(f'{portfolio_return:+.1f}%', 
                    xy=(dates[-1], portfolio_values[-1]),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#1f77b4',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if len(spy_values) > 0:
            spy_return = ((spy_values.iloc[-1] - initial_portfolio_value) / initial_portfolio_value) * 100
            ax.annotate(f'{spy_return:+.1f}%', 
                    xy=(dates[-1], spy_values.iloc[-1]),
                    xytext=(10, -10), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#ff7f0e',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if len(iwm_values) > 0:
            iwm_return = ((iwm_values.iloc[-1] - initial_portfolio_value) / initial_portfolio_value) * 100
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
        plt.savefig('output.png')
    def export_historical_metrics(self, report_data):
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

# Usage
if __name__ == "__main__":
    reporter = DailyPortfolioReport()
    reporter.generate_report()
    