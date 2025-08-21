#!/usr/bin/env python3
"""
LLM Managed Portfolio - Main Entry Point
Fully modular version that breaks down the original Daily_Portfolio_Script.py 
into focused, manageable modules.

This orchestrates all the modular components:
- PortfolioManager: Holdings and cash management
- DataFetcher: Market data retrieval
- TradeExecutor: Document parsing and order execution  
- ReportGenerator: Analysis and reporting

Usage:
    python main.py                # Execute trades and generate report
    python main.py --report-only  # Generate report without executing trades
"""

import argparse
from market_hours import enforce_market_hours
from portfolio_manager import PortfolioManager
from data_fetcher import DataFetcher
from trade_executor import TradeExecutor
from report_generator import ReportGenerator


class LLMManagedPortfolio:
    """Main orchestrator for the modular portfolio system"""
    
    def __init__(self):
        """Initialize all modular components"""
        # Create core modules
        self.portfolio = PortfolioManager()
        self.data_fetcher = DataFetcher()
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
    
    def generate_report(self):
        """Generate comprehensive portfolio report"""
        
        print(f"\n📊 GENERATING PORTFOLIO REPORT")
        print("=" * 40)
        
        # Generate report using the report generator
        report_data = self.report_generator.generate_report()
        
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
    args = parser.parse_args()
    
    # Market hours validation - must be first
    enforce_market_hours()
    
    print("\n" + "=" * 60)
    if args.report_only:
        print("📊 LLM MANAGED PORTFOLIO - REPORT MODE (READ-ONLY)")
    elif args.test_parser:
        print("🧪 LLM MANAGED PORTFOLIO - PARSER TEST MODE")
    else:
        print("🚀 LLM MANAGED PORTFOLIO - FULL EXECUTION MODE")
    print("=" * 60)
    
    # Create the orchestrated portfolio system
    try:
        portfolio_system = LLMManagedPortfolio()
        
        if args.test_parser:
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
            # Only generate the report without executing trades
            print("🔍 Running in read-only mode - no trades will be executed")
            portfolio_system.generate_report()
            
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