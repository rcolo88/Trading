"""
Report Generation Module
Handles portfolio analysis, performance metrics, chart generation, and reporting
"""

import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from performance_validator import PerformanceValidator


class ReportGenerator:
    """Handles all reporting, analysis, and chart generation for the portfolio"""
    
    def __init__(self, portfolio_manager, data_fetcher):
        self.portfolio = portfolio_manager
        self.data_fetcher = data_fetcher
        
        # Get the parent directory (one level up from Pieced Portfolio Scripts)
        self.parent_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    
    def calculate_position_metrics(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Calculate key metrics for each position"""
        positions = []
        
        # STEP 1: Calculate the COMPLETE total portfolio value FIRST
        total_current_value = self.portfolio.cash
        position_values = {}
        total_cost_basis = 0  # Track actual total investment
        
        # First pass: Calculate all position values and total
        for ticker, position in self.portfolio.holdings.items():
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
        for ticker, position in self.portfolio.holdings.items():
            if ticker in position_values:
                pos_data = position_values[ticker]
                current_price = pos_data['current_price']
                current_value = pos_data['current_value']
                cost_basis = pos_data['cost_basis']
                
                # P&L calculations - Fixed to use actual cost basis
                pnl_dollar = current_value - cost_basis
                pnl_percent = (pnl_dollar / cost_basis) * 100
                daily_change = ((current_price - position['entry_price']) / position['entry_price']) * 100
                
                # Fixed: Use the complete total for weight calculations
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
        
        return positions
    
    def check_alerts(self, positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check for various portfolio alerts"""
        alerts = []
        
        for pos in positions:
            # Price alerts
            if pos['pnl_percent'] > 50:
                alerts.append({
                    'type': 'BIG_WIN',
                    'ticker': pos['ticker'],
                    'message': f"{pos['ticker']} up {pos['pnl_percent']:+.1f}% - consider taking profits",
                    'severity': 'HIGH'
                })
            elif pos['pnl_percent'] < -20:
                alerts.append({
                    'type': 'BIG_LOSS',
                    'ticker': pos['ticker'],
                    'message': f"{pos['ticker']} down {pos['pnl_percent']:+.1f}% - consider stop loss",
                    'severity': 'HIGH'
                })
            
            # Weight drift alerts
            if abs(pos['weight_drift']) > 5:
                drift_direction = "overweight" if pos['weight_drift'] > 0 else "underweight"
                alerts.append({
                    'type': 'WEIGHT_DRIFT',
                    'ticker': pos['ticker'],
                    'message': f"{pos['ticker']} {drift_direction} by {abs(pos['weight_drift']):.1f}% - consider rebalancing",
                    'severity': 'MEDIUM'
                })
        
        # Cash level alerts
        cash_ratio = (self.portfolio.cash / (self.portfolio.get_total_investment() + self.portfolio.cash)) * 100
        if cash_ratio > 20:
            alerts.append({
                'type': 'HIGH_CASH',
                'ticker': 'CASH',
                'message': f"High cash level ({cash_ratio:.1f}%) - consider deploying capital",
                'severity': 'MEDIUM'
            })
        elif cash_ratio < 2:
            alerts.append({
                'type': 'LOW_CASH',
                'ticker': 'CASH',
                'message': f"Low cash reserves ({cash_ratio:.1f}%) - consider building buffer",
                'severity': 'MEDIUM'
            })
        
        return alerts
    
    def generate_analysis_file(self, report_data: Dict[str, Any]):
        """Generate a comprehensive analysis file for Claude"""
        
        analysis_file = os.path.join(self.parent_dir, 'daily_portfolio_analysis.md')
        
        try:
            with open(analysis_file, 'w') as f:
                f.write(f"# Daily Portfolio Analysis - {datetime.now().strftime('%Y-%m-%d')}\n\n")
                
                # Executive Summary
                f.write("## Executive Summary\n")
                f.write(f"- **Total Portfolio Value**: ${report_data['total_value']:,.2f}\n")
                f.write(f"- **Total P&L**: ${report_data['total_pnl']:+,.2f} ({report_data['total_pnl_pct']:+.2f}%)\n")
                f.write(f"- **Cash Position**: ${report_data['cash']:,.2f}\n")
                f.write(f"- **Active Positions**: {len(report_data['positions'])}\n\n")
                
                # Performance vs Benchmarks
                f.write("## Benchmark Comparison\n")
                if 'benchmarks' in report_data:
                    for benchmark, returns in report_data['benchmarks'].items():
                        f.write(f"- **{benchmark}**: {returns:+.2f}%\n")
                f.write("\n")
                
                # Position Details
                f.write("## Position Analysis\n")
                for pos in report_data['positions']:
                    f.write(f"### {pos['ticker']}\n")
                    f.write(f"- Shares: {pos['shares']}\n")
                    f.write(f"- Current Price: ${pos['current_price']:.2f}\n")
                    f.write(f"- P&L: ${pos['pnl_dollar']:+,.2f} ({pos['pnl_percent']:+.2f}%)\n")
                    f.write(f"- Portfolio Weight: {pos['current_weight']:.1f}%\n")
                    f.write(f"- Weight Drift: {pos['weight_drift']:+.1f}%\n\n")
                
                # Alerts
                if report_data.get('alerts'):
                    f.write("## Alerts & Recommendations\n")
                    for alert in report_data['alerts']:
                        f.write(f"- **{alert['severity']}**: {alert['message']}\n")
                    f.write("\n")
                
                # Historical Performance
                f.write("## Recent Performance Trend\n")
                f.write("*Historical performance data will be populated as data accumulates*\n\n")
                
                # Footer
                f.write("---\n")
                f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
            
            print(f"📄 Analysis file generated: {analysis_file}")
            
        except Exception as e:
            print(f"❌ Error generating analysis file: {e}")
    
    def export_historical_performance(self, report_data: Dict[str, Any], current_prices: Dict[str, float]):
        """Export current performance to CSV for historical tracking"""
        
        history_file = os.path.join(self.parent_dir, 'portfolio_performance_history.csv')
        
        try:
            # Prepare current data row
            current_row = {
                'Date': datetime.now().strftime('%Y-%m-%d'),
                'Time': datetime.now().strftime('%H:%M:%S'),
                'Total Value': report_data['total_value'],
                'Cash': report_data['cash'],
                'Total P&L $': report_data['total_pnl'],
                'Total P&L %': report_data['total_pnl_pct']
            }
            
            # Add individual position data
            for pos in report_data['positions']:
                ticker = pos['ticker']
                current_row[f'{ticker}_shares'] = pos['shares']
                current_row[f'{ticker}_price'] = pos['current_price']
                current_row[f'{ticker}_value'] = pos['current_value']
                current_row[f'{ticker}_pnl_pct'] = pos['pnl_percent']
            
            # Add benchmark data
            if 'benchmarks' in report_data:
                for benchmark, returns in report_data['benchmarks'].items():
                    current_row[f'{benchmark} Return %'] = returns
            
            # Load existing data or create new DataFrame
            if os.path.exists(history_file):
                df = pd.read_csv(history_file)
                
                # Check if today's data already exists
                today = datetime.now().strftime('%Y-%m-%d')
                existing_today = df[df['Date'] == today]
                
                if not existing_today.empty:
                    # Update today's row
                    df.loc[df['Date'] == today] = pd.Series(current_row)
                    print("📊 Updated today's performance data")
                else:
                    # Append new row
                    df = pd.concat([df, pd.DataFrame([current_row])], ignore_index=True)
                    print("📊 Added new daily performance record")
            else:
                # Create new file
                df = pd.DataFrame([current_row])
                print("📊 Created new performance history file")
            
            # Save to CSV
            df.to_csv(history_file, index=False)
            print(f"✅ Performance data exported to {history_file}")
            
        except Exception as e:
            print(f"❌ Error exporting historical performance: {e}")
    
    def plot_performance_chart(self, save_path: Optional[str] = None):
        """Generate portfolio performance chart"""
        
        history_file = os.path.join(self.parent_dir, 'portfolio_performance_history.csv')
        
        if not os.path.exists(history_file):
            print("❌ No performance history file found - skipping chart")
            return
        
        try:
            # Load historical data
            df = pd.read_csv(history_file)
            
            if len(df) < 2:
                print("❌ Not enough historical data for chart (need at least 2 data points)")
                return
            
            # Parse dates and sort
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            
            # Create chart
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
            
            # Plot 1: Portfolio value over time
            ax1.plot(df['Date'], df['Total Value'], 'b-', linewidth=2, label='Portfolio Value')
            ax1.axhline(y=2000, color='r', linestyle='--', alpha=0.7, label='Initial Investment ($2,000)')
            ax1.set_title('Portfolio Value Over Time', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Portfolio Value ($)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Calculate percentage returns from $2000 baseline
            portfolio_returns = ((df['Total Value'] - 2000) / 2000) * 100
            
            # Plot 2: Returns comparison
            ax2.plot(df['Date'], portfolio_returns, 'g-', linewidth=2, label='Portfolio Return')
            
            # Add SPY comparison if available
            if 'SPY Return %' in df.columns:
                ax2.plot(df['Date'], df['SPY Return %'], 'orange', linewidth=2, label='SPY Benchmark', alpha=0.7)
            
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            ax2.set_title('Portfolio Performance vs Benchmark', fontsize=14, fontweight='bold')
            ax2.set_xlabel('Date')
            ax2.set_ylabel('Return (%)')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Save chart
            if save_path:
                chart_path = save_path
            else:
                chart_path = os.path.join(self.parent_dir, 'LLM Managed Portfolio Performance.png')
            
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            print(f"✅ Chart saved to {chart_path}")
            plt.close()
            
        except Exception as e:
            print(f"❌ Error creating performance chart: {e}")
    
    def plot_position_details(self, positions: List[Dict[str, Any]], total_value: float, save_path: Optional[str] = None):
        """Create detailed position charts"""
        
        if not positions:
            print("❌ No positions to chart")
            return
        
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
            
            # Chart 1: Position Values (Pie Chart)
            tickers = [pos['ticker'] for pos in positions]
            values = [pos['current_value'] for pos in positions]
            
            # Add cash as a segment if significant
            if self.portfolio.cash > total_value * 0.05:  # Show cash if >5% of total
                tickers.append('CASH')
                values.append(self.portfolio.cash)
            
            ax1.pie(values, labels=tickers, autopct='%1.1f%%', startangle=90)
            ax1.set_title('Portfolio Allocation by Value')
            
            # Chart 2: P&L by Position (Bar Chart)
            pnl_values = [pos['pnl_dollar'] for pos in positions]
            colors = ['green' if pnl >= 0 else 'red' for pnl in pnl_values]
            
            bars = ax2.bar(tickers, pnl_values, color=colors, alpha=0.7)
            ax2.set_title('Profit & Loss by Position')
            ax2.set_ylabel('P&L ($)')
            ax2.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            plt.setp(ax2.get_xticklabels(), rotation=45)
            
            # Chart 3: Weight Drift (Bar Chart)
            weight_drifts = [pos['weight_drift'] for pos in positions]
            colors_drift = ['blue' if drift >= 0 else 'orange' for drift in weight_drifts]
            
            ax3.bar(tickers, weight_drifts, color=colors_drift, alpha=0.7)
            ax3.set_title('Weight Drift from Target')
            ax3.set_ylabel('Drift (%)')
            ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            plt.setp(ax3.get_xticklabels(), rotation=45)
            
            # Chart 4: Performance Percentages
            pnl_pcts = [pos['pnl_percent'] for pos in positions]
            colors_pct = ['green' if pnl >= 0 else 'red' for pnl in pnl_pcts]
            
            ax4.bar(tickers, pnl_pcts, color=colors_pct, alpha=0.7)
            ax4.set_title('Performance by Position (%)')
            ax4.set_ylabel('Return (%)')
            ax4.axhline(y=0, color='black', linestyle='-', alpha=0.3)
            plt.setp(ax4.get_xticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # Save chart
            if save_path:
                chart_path = save_path
            else:
                chart_path = os.path.join(self.parent_dir, 'Portfolio Position Details.png')
            
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            print(f"✅ Position details chart saved to {chart_path}")
            plt.close()
            
        except Exception as e:
            print(f"❌ Error creating position details chart: {e}")
    
    def generate_report(self):
        """Generate comprehensive portfolio report"""
        
        print(f"\n{'='*60}")
        print(f"📊 DAILY PORTFOLIO REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        
        # Get current market data
        current_prices, volume_data, price_data = self.data_fetcher.fetch_current_data(
            list(self.portfolio.holdings.keys()),
            self.portfolio.benchmarks
        )
        
        if not current_prices:
            print("❌ Failed to fetch market data - cannot generate report")
            return None
        
        # Calculate position metrics
        positions = self.calculate_position_metrics(current_prices)
        
        # Calculate portfolio totals
        total_current_value = self.portfolio.cash + sum(pos['current_value'] for pos in positions)
        total_cost_basis = sum(pos['cost_basis'] for pos in positions)
        total_pnl = total_current_value - 2000.00  # From initial $2000 investment
        total_pnl_pct = (total_pnl / 2000.00) * 100
        
        # Performance validation
        validator = PerformanceValidator(self.portfolio)
        validation_results = validator.validate_performance(current_prices)
        
        # Calculate benchmarks
        benchmark_returns = self.data_fetcher.calculate_benchmark_returns(current_prices, self.portfolio.benchmarks)
        
        # Check for alerts
        alerts = self.check_alerts(positions)
        
        # Volume alerts
        volume_alerts = self.data_fetcher.get_volume_alerts(current_prices)
        alerts.extend(volume_alerts)
        
        # Compile report data
        report_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'total_value': total_current_value,
            'cash': self.portfolio.cash,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'positions': positions,
            'benchmarks': benchmark_returns,
            'alerts': alerts,
            'validation': validation_results
        }
        
        # Display report
        self._display_report(report_data)
        
        # Export data and generate files
        self.export_historical_performance(report_data, current_prices)
        self.generate_analysis_file(report_data)
        self.plot_performance_chart()
        self.plot_position_details(positions, total_current_value)
        
        return report_data
    
    def _display_report(self, report_data: Dict[str, Any]):
        """Display the portfolio report to console"""
        
        print(f"\n💰 PORTFOLIO SUMMARY:")
        print(f"   Total Value: ${report_data['total_value']:,.2f}")
        print(f"   Cash: ${report_data['cash']:,.2f}")
        print(f"   Total P&L: ${report_data['total_pnl']:+,.2f} ({report_data['total_pnl_pct']:+.2f}%)")
        
        if report_data['validation']['status'] == 'PASSED':
            print(f"✅ Performance validation: PASSED")
        else:
            print(f"❌ Performance validation: FAILED")
        
        print(f"\n📊 POSITIONS ({len(report_data['positions'])}):")
        print("-" * 80)
        print(f"{'Ticker':<8} {'Shares':<8} {'Price':<10} {'Value':<12} {'P&L $':<12} {'P&L %':<10} {'Weight':<8}")
        print("-" * 80)
        
        for pos in report_data['positions']:
            print(f"{pos['ticker']:<8} "
                  f"{pos['shares']:<8} "
                  f"${pos['current_price']:<9.2f} "
                  f"${pos['current_value']:<11,.2f} "
                  f"${pos['pnl_dollar']:<11,+.2f} "
                  f"{pos['pnl_percent']:<9,+.2f}% "
                  f"{pos['current_weight']:<7.1f}%")
        
        # Benchmarks
        if report_data['benchmarks']:
            print(f"\n📈 BENCHMARKS:")
            for benchmark, returns in report_data['benchmarks'].items():
                print(f"   {benchmark}: {returns:+.2f}%")
        
        # Alerts
        if report_data['alerts']:
            print(f"\n🚨 ALERTS ({len(report_data['alerts'])}):")
            for alert in report_data['alerts']:
                severity_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(alert['severity'], "ℹ️")
                print(f"   {severity_emoji} {alert['message']}")
        
        print(f"\n{'='*60}")
        print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get a quick portfolio summary without generating full report"""
        
        # Get current prices for holdings only
        holdings_tickers = list(self.portfolio.holdings.keys())
        current_prices, _, _ = self.data_fetcher.fetch_current_data(holdings_tickers, [])
        
        if not current_prices:
            return {'error': 'Unable to fetch current market data'}
        
        # Calculate basic metrics
        total_value = self.portfolio.cash
        total_pnl = 0
        
        for ticker, position in self.portfolio.holdings.items():
            if ticker in current_prices:
                current_value = position['shares'] * current_prices[ticker]
                cost_basis = position['shares'] * position['entry_price']
                total_value += current_value
                total_pnl += (current_value - cost_basis)
        
        total_pnl_pct = (total_pnl / 2000.00) * 100  # From initial $2000
        
        return {
            'total_value': total_value,
            'cash': self.portfolio.cash,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'positions_count': len(self.portfolio.holdings),
            'last_updated': datetime.now().isoformat()
        }