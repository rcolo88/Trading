#!/usr/bin/env python3
"""
LLM Managed Portfolio - Main Entry Point
Fully modular version that breaks down the original Daily_Portfolio_Script.py 
into focused, manageable modules.

This orchestrates all the modular components:
- PortfolioManager: Holdings and cash management
- SchwabDataFetcher: Schwab API market data retrieval
- TradeExecutor: Document parsing and order execution  
- ReportGenerator: Analysis and reporting

Usage:
    python main.py                    # Execute trades and generate report
    python main.py --report-only      # Generate report without executing trades
"""

import argparse
import pytz
from datetime import datetime
from market_hours import enforce_market_hours, is_market_open
from portfolio_manager import PortfolioManager
from schwab_data_fetcher import SchwabDataFetcher
from trade_executor import TradeExecutor
from report_generator import ReportGenerator


class LLMManagedPortfolio:
    """Main orchestrator for the modular portfolio system"""
    
    def __init__(self):
        """Initialize all modular components"""
        # Create core modules with Schwab API
        self.portfolio = PortfolioManager()
        self.data_fetcher = SchwabDataFetcher()
        self.trade_executor = TradeExecutor(self.portfolio, self.data_fetcher)
        self.report_generator = ReportGenerator(self.portfolio, self.data_fetcher)
        
        print("✅ Modular portfolio system initialized")
        print(f"   Portfolio: {len(self.portfolio.holdings)} positions")
        print(f"   Cash: ${self.portfolio.cash:.2f}")
        print(f"   Partial Fill Mode: {self.portfolio.partial_fill_mode.value}")
    
    def execute_automated_trading(self, document_path: str = None):
        """Execute automated trading workflow"""
        
        print(f"\n🤖 EXECUTING AUTOMATED TRADING WORKFLOW")
        print("=" * 50)
        
        # Execute trades using the trade executor
        results = self.trade_executor.execute_automated_trading(document_path)
        
        if results:
            successful_trades = len([r for r in results if r.executed])
            print(f"✅ Trading execution completed: {successful_trades}/{len(results)} trades successful")
        else:
            print("ℹ️  No trades were executed")
        
        return results
    
    def generate_report(self, prefer_close_prices: bool = False):
        """Generate comprehensive portfolio report"""
        
        print(f"\n📊 GENERATING PORTFOLIO REPORT")
        print("=" * 40)
        
        # Generate report using the report generator
        report_data = self.report_generator.generate_report(prefer_close_prices)
        
        if report_data:
            print("✅ Portfolio report generation completed")
        else:
            print("❌ Report generation failed")
        
        return report_data
    
    def get_portfolio_summary(self):
        """Get quick portfolio summary"""
        return self.report_generator.get_portfolio_summary()


def main():
    """Main entry point with market hours validation"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LLM Managed Portfolio - Fully Modular Version')
    parser.add_argument('--report-only', action='store_true', 
                      help='Generate portfolio report without executing any trades')
    parser.add_argument('--test-parser', action='store_true',
                      help='Test document parsing without executing trades')
    parser.add_argument('--load-previous-day', action='store_true',
                      help='Load portfolio positions from previous day performance history')
    parser.add_argument('--test-schwab-api', action='store_true',
                      help='Test Schwab API connection and functionality')
    parser.add_argument('--sync-schwab-account', action='store_true',
                      help='Sync portfolio with actual Schwab account positions')
    args = parser.parse_args()
    
    # Conditional market hours validation
    market_is_open = is_market_open()
    
    if args.report_only:
        # --report-only mode: Only allow when market is CLOSED
        if market_is_open:
            et_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            print("🚫 REPORT-ONLY MODE RESTRICTED DURING MARKET HOURS")
            print(f"Current time: {current_time}")
            print("The --report-only flag can only be used when the market is CLOSED:")
            print("• After 4:00 PM Eastern Time on trading days")
            print("• On weekends and holidays")
            print("• Before 9:30 AM Eastern Time on trading days")
            print("\nThis ensures report prices reflect the most recent close prices.")
            print("During market hours, use the full trading mode or wait until market close.")
            exit(1)
        else:
            et_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            print(f"✅ Market is closed - Report-only mode enabled - {current_time}")
    else:
        # All other modes: Require market to be OPEN
        if not market_is_open:
            et_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            print("🚫 TRADING MODES REQUIRE MARKET TO BE OPEN")
            print(f"Current time: {current_time}")
            print("Trading operations can only run during US market hours:")
            print("• Monday-Friday, 9:30 AM - 4:00 PM Eastern Time")
            print("• On days when NYSE/NASDAQ are open (no holidays)")
            print("\nTo generate reports when market is closed, use: --report-only")
            exit(1)
        else:
            et_tz = pytz.timezone('US/Eastern')
            current_time = datetime.now(et_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            print(f"✅ Market is open - Trading mode enabled - {current_time}")
    
    print("\n" + "=" * 60)
    if args.load_previous_day:
        print("🔄 LLM MANAGED PORTFOLIO - POSITION RECOVERY MODE")
    elif args.report_only:
        print("📊 LLM MANAGED PORTFOLIO - REPORT MODE (READ-ONLY)")
    elif args.test_parser:
        print("🧪 LLM MANAGED PORTFOLIO - PARSER TEST MODE")
    elif args.test_schwab_api:
        print("🔬 LLM MANAGED PORTFOLIO - SCHWAB API TEST MODE")
    elif args.sync_schwab_account:
        print("🔄 LLM MANAGED PORTFOLIO - SCHWAB ACCOUNT SYNC MODE")
    else:
        print("🚀 LLM MANAGED PORTFOLIO - FULL EXECUTION MODE (SCHWAB API)")
    print("=" * 60)
    
    # Create the orchestrated portfolio system
    try:
        portfolio_system = LLMManagedPortfolio()
        
        if args.load_previous_day:
            # Load positions from saved portfolio state
            print("🔄 Loading positions from saved portfolio state...")
            previous_positions = portfolio_system.portfolio.load_positions_from_previous_day()
            
            if previous_positions != portfolio_system.portfolio.holdings:
                portfolio_system.portfolio.holdings = previous_positions
                portfolio_system.portfolio.save_portfolio_state()
                print(f"✅ Portfolio positions restored from saved state")
                print(f"   Loaded {len(previous_positions)} positions")
                print(f"   Current cash: ${portfolio_system.portfolio.cash:.2f}")
                
                # Show summary of loaded positions
                for ticker, position in previous_positions.items():
                    shares = position.get('shares', 0)
                    entry_price = position.get('entry_price', 0)
                    allocation = position.get('allocation', shares * entry_price)
                    print(f"   {ticker}: {shares} shares @ ${entry_price:.2f} (${allocation:.2f})")
                
                # Generate report to update daily_portfolio_analysis.md and performance history
                print("\n📊 Generating updated portfolio report...")
                portfolio_system.generate_report()
                print("✅ Portfolio analysis files updated with restored positions")
            else:
                print("ℹ️  No changes needed - positions already current")
                # Still generate report to ensure files are current
                print("\n📊 Generating current portfolio report...")
                portfolio_system.generate_report()
                
        elif args.test_schwab_api:
            # Test Schwab API connection and functionality
            print("🔬 Testing Schwab API connection...")
            
            # Test basic API connection
            if portfolio_system.data_fetcher.client:
                print("✅ Schwab API client initialized")
                
                # Test quote fetching
                test_tickers = ['SPY', 'AAPL']
                print(f"🎯 Testing quotes for: {test_tickers}")
                current_prices, _, _ = portfolio_system.data_fetcher.fetch_current_data(test_tickers)
                
                if current_prices:
                    print("✅ Quote fetching successful:")
                    for ticker, price in current_prices.items():
                        print(f"   {ticker}: ${price:.2f}")
                else:
                    print("❌ Quote fetching failed")
                    
                # Test data quality
                quality = portfolio_system.data_fetcher.data_quality_check()
                print(f"📊 Data quality score: {quality['quality_score']}%")
                print(f"📡 Data source: {quality['api_source']}")
                
            else:
                print("❌ Schwab API client not available")
                print("📝 Please configure schwab_credentials.json with your API credentials")
                
        elif args.sync_schwab_account:
            # Sync with actual Schwab account positions
            print("🔄 Syncing with Schwab account positions...")
            print("⚠️  Account sync functionality requires additional API permissions")
            print("📝 This feature will be implemented in Phase 2")
            
        elif args.test_parser:
            # Test document parsing functionality
            print("🔍 Testing document parsing...")
            document = portfolio_system.trade_executor.find_trading_document()
            if document:
                orders = portfolio_system.trade_executor.parse_document(document)
                print(f"📋 Found {len(orders)} orders in document")
                for order in orders:
                    print(f"   {order.action.value} {order.ticker} - {order.reason}")
            else:
                print("❌ No trading document found")
                
        elif args.report_only:
            # Only generate the report without executing trades - use close prices when market is closed
            print("🔍 Running in read-only mode - no trades will be executed")
            print("💰 Using most recent close prices for accurate after-hours valuation")
            portfolio_system.generate_report(prefer_close_prices=True)
            
        else:
            # Full execution mode: Execute trades then generate report
            print("🚀 Running full execution mode")
            
            # Step 1: Execute automated trading
            trade_results = portfolio_system.execute_automated_trading()
            
            # Step 2: Generate updated portfolio report
            portfolio_system.generate_report()
            
            print(f"\n✅ Portfolio management cycle completed")
            
    except Exception as e:
        print(f"❌ Error in portfolio system: {e}")
        raise


if __name__ == "__main__":
    main()