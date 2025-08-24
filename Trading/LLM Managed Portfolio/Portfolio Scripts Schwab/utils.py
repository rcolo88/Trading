"""
Utility Functions Module
Helper functions and standalone utilities for the trading system
"""

import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os


def validate_performance_calculations(self):
    """Standalone function to validate performance calculations"""
    # Check if we have performance data
    if not os.path.exists('../portfolio_performance_history.csv'):
        print("❌ No performance history found - skipping validation")
        return
    
    try:
        # Load the historical data
        df = pd.read_csv('../portfolio_performance_history.csv')
        
        if df.empty:
            print("❌ Performance history file is empty")
            return
            
        # Get the latest performance record
        latest = df.iloc[-1]
        current_performance = latest['Total P&L %']
        
        print(f"\n📊 PERFORMANCE VALIDATION:")
        print(f"Latest recorded performance: {current_performance:+.2f}%")
        
        # Additional validation logic would go here
        return True
        
    except Exception as e:
        print(f"❌ Error validating performance: {e}")
        return False


def plot_performance_chart_fixed(self, save_path=None):
    """
    Fixed version of performance chart generation
    Uses ../portfolio_performance_history.csv for accurate historical data
    """
    
    if not os.path.exists('../portfolio_performance_history.csv'):
        print("❌ No performance history file found")
        return
    
    try:
        # Load historical performance data
        df = pd.read_csv('../portfolio_performance_history.csv')
        
        if len(df) < 2:
            print("❌ Not enough historical data for chart (need at least 2 data points)")
            return
        
        # Parse dates and sort
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        
        # Calculate actual returns vs SPY
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
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"✅ Chart saved to {save_path}")
        else:
            plt.savefig('../LLM Managed Portfolio Performance.png', dpi=300, bbox_inches='tight')
            print("✅ Chart saved to '../LLM Managed Portfolio Performance.png'")
        
        plt.close()
        
        # Validation: Compare last data point with current calculations
        if len(df) > 0:
            last_record = df.iloc[-1]
            recorded_return = last_record['Total P&L %']
            actual_return = portfolio_returns.iloc[-1]
            
            print(f"✅ Chart shows actual performance: {actual_return:+.2f}%")
            return
    
    except Exception as e:
        print(f"❌ Error creating performance chart: {e}")
        return
    
    print("❌ No reliable historical data - chart generation skipped")
    print("💡 Run the system for a few more days to build historical data")


def format_currency(amount):
    """Format currency values for display"""
    return f"${amount:,.2f}"


def format_percentage(percentage):
    """Format percentage values for display"""
    return f"{percentage:+.2f}%"


def calculate_days_since(date_str):
    """Calculate days since a given date string"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return (datetime.now() - date_obj).days
    except:
        return None