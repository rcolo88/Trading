#!/usr/bin/env python3
"""
LLM Managed Portfolio - Main Entry Point
Modular version of the original Daily_Portfolio_Script.py

This is the new entry point that imports the market hours validation
and other modules. The original Daily_Portfolio_Script.py remains unchanged.

Usage:
    python main.py                # Execute trades and generate report
    python main.py --report-only  # Generate report without executing trades
"""

# Import market hours validation first
from market_hours import enforce_market_hours

# Import the original portfolio report class
# Note: We import from the original file to maintain compatibility
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from Daily_Portfolio_Script import DailyPortfolioReport


def main():
    """Main entry point with market hours validation"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LLM Managed Portfolio - Modular Version')
    parser.add_argument('--report-only', action='store_true', 
                      help='Generate portfolio report without executing any trades')
    args = parser.parse_args()
    
    # Market hours validation - must be first
    enforce_market_hours()
    
    print("\n" + "=" * 60)
    if args.report_only:
        print("📊 LLM MANAGED PORTFOLIO - REPORT MODE (READ-ONLY)")
    else:
        print("LLM MANAGED PORTFOLIO - MARKET HOURS VALIDATED")
    print("=" * 60)
    
    # Create portfolio instance
    portfolio = DailyPortfolioReport()
    
    if args.report_only:
        # Only generate the report without executing trades
        print("🔍 Running in read-only mode - no trades will be executed")
        portfolio.generate_report()
    else:
        # Execute automated trading from document
        # Will automatically look for doc if doc is unspecified
        results = portfolio.execute_automated_trading()
        
        # Generate updated portfolio report
        portfolio.generate_report()


if __name__ == "__main__":
    main()