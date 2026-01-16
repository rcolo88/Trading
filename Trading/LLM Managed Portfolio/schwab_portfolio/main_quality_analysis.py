#!/usr/bin/env python3
"""
Quality Analysis Main Entry Point
Algorithmic quality scoring for stocks based on academic research

This script provides a simple command-line interface to the quality scoring system.
Choose between:
1. Index analysis: Analyze portfolio vs watchlist (multiple stocks)
2. Individual stock analysis: Deep dive on specific ticker

Usage:
    # Index analysis (batch)
    python main_quality_analysis.py --index sp500 --limit 50
    python main_quality_analysis.py --index combined_sp  # Screen all 1500 stocks

    # Individual stock analysis
    python main_quality_analysis.py --ticker AAPL
    python main_quality_analysis.py --ticker NVDA

Output (Index):
    - outputs/quality_analysis.json: Complete analysis results
    - outputs/quality_analysis_summary.txt: Human-readable summary with recommendations

Output (Individual):
    - outputs/stock_analysis_AAPL_20250116.txt: Detailed individual analysis

Author: Quality Scoring System
Date: 2025
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from workflows.quality_analysis_script import QualityAnalysisScript
from workflows.individual_stock_analysis import IndividualStockAnalysis
from data.watchlist_config import WatchlistConfig, WatchlistIndex


def main():
    parser = argparse.ArgumentParser(
        description='Algorithmic Quality Scoring System',
        epilog='Examples:\n'
               '  Index analysis: python main_quality_analysis.py --index sp500 --limit 50\n'
               '  Individual stock: python main_quality_analysis.py --ticker AAPL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='%(prog)s [options]'
    )

    # Create mutually exclusive group for index vs ticker
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '--index',
        type=str,
        choices=['sp500', 'sp400', 'sp600', 'nasdaq100', 'combined_sp'],
        help='Index to screen. Options:\n'
             '  sp500: S&P 500 (large cap ~500, 12-17 min)\n'
             '  sp400: S&P MidCap 400 (mid cap ~400, 10-14 min)\n'
             '  sp600: S&P SmallCap 600 (small cap ~600, 15-20 min)\n'
             '  nasdaq100: NASDAQ-100 (tech ~100, 3-5 min)\n'
             '  combined_sp: S&P 1500 (~1500, 45-60 min)'
    )
    group.add_argument(
        '--ticker',
        type=str,
        help='Analyze individual stock ticker (e.g., AAPL, MSFT, NVDA)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Maximum tickers to analyze for index screening (default: 50). Ignored for --ticker.'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.index and not args.ticker:
        # Default to index analysis if nothing specified
        args.index = 'sp500'

    if args.ticker and args.limit != 50:
        parser.error("--limit is only used with --index, not --ticker")

    print(f"{'='*60}")
    print(f"QUALITY ANALYSIS SYSTEM")
    print(f"{'='*60}")

    if args.ticker:
        # Individual stock analysis
        print(f"Mode: Individual Stock Analysis")
        print(f"Ticker: {args.ticker.upper()}")
        print()

        # Run individual stock analysis
        analyzer = IndividualStockAnalysis(ticker=args.ticker.upper())
        analyzer.run()

    else:
        # Index analysis (batch)
        print(f"Mode: Index Analysis")
        print(f"Index: {args.index}")
        print(f"Limit: {args.limit if args.limit > 0 else 'All'}")
        print()

        # Map string to enum
        index_map = {
            'sp500': WatchlistIndex.SP500,
            'sp400': WatchlistIndex.SP400,
            'sp600': WatchlistIndex.SP600,
            'nasdaq100': WatchlistIndex.NASDAQ100,
            'combined_sp': WatchlistIndex.COMBINED_SP
        }

        # Create watchlist config
        config = WatchlistConfig(
            index=index_map[args.index],
            limit=args.limit if args.limit > 0 else None
        )

        # Run analysis
        script = QualityAnalysisScript(watchlist_config=config)
        script.run(watchlist_limit=args.limit if args.limit > 0 else None)


if __name__ == "__main__":
    main()
