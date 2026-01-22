#!/usr/bin/env python3
"""
Quality Analysis Main Entry Point
Algorithmic quality scoring for stocks based on academic research

This script provides a simple command-line interface to the quality scoring system.
Choose between:
1. Index analysis: Analyze stocks from a market index (S&P 500, Russell 2000, etc.)
2. Multiple indices: Combine multiple indices for broader coverage
3. Individual stock analysis: Deep dive on specific ticker

Usage:
    # Single index analysis (batch) - Sequential (default)
    python main_quality_analysis.py --index sp500 --limit 50

    # Multiple indices combined (e.g., SP500 + SP400 + SP600)
    python main_quality_analysis.py --indices sp500,sp400,sp600 --limit 100

    # Index analysis with parallel fetching (10x speedup)
    python main_quality_analysis.py --index russell2000 --limit 0 --parallel --workers 10

    # Multi-day orchestration (NEW!)
    python main_quality_analysis.py --index russell3000  # Auto-activates when needed
    python main_quality_analysis.py --index russell3000 --multi-day  # Force multi-day
    python main_quality_analysis.py --index sp500 --multi-day  # Force for smaller index too

    # Individual stock analysis
    python main_quality_analysis.py --ticker AAPL
    python main_quality_analysis.py --ticker NVDA

Performance Options:
    --parallel: Enable parallel fetching (6-10x speedup)
    --workers: Number of parallel workers (default: 10)
    --timeout: Maximum runtime in seconds (default: 600 = 10 minutes)

Multi-Day Options:
    --multi-day: Enable automatic multi-day orchestration for large datasets
    --force-multi-day: Force multi-day mode regardless of index size

Output (Index):
    - outputs/quality_analysis.json: Complete quality analysis results
    - outputs/quality_analysis_summary.txt: Quality rankings and statistics

Output (Individual):
    - outputs/stock_analysis_AAPL_20250116.txt: Detailed individual analysis

Author: Quality Scoring System
Date: 2025
"""

import argparse
import sys
import signal
from pathlib import Path
from typing import List

# Global flag for graceful shutdown
_SHUTDOWN_REQUESTED = False


def _signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    print("\n\nShutdown signal received, stopping...")
    sys.stdout.flush()
    sys.exit(0)


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from workflows.quality_analysis_script import QualityAnalysisScript
from workflows.individual_stock_analysis import IndividualStockAnalysis
from data.watchlist_config import WatchlistConfig, WatchlistIndex


def should_use_multi_day(index_name: str, total_tickers: int, total_api_calls: int, force_multi_day: bool = False) -> bool:
    """
    Determine if multi-day mode should be used.
    
    NOTE: Multi-day mode is now DISABLED by default because we use SimFin
    which has no daily API limit (only rate-limited per second).
    
    Args:
        index_name: Name of the index
        total_tickers: Number of tickers in the index
        total_api_calls: Total API calls needed (not used anymore)
        force_multi_day: Force multi-day mode regardless
        
    Returns:
        Always False - SimFin eliminates need for multi-day processing
    """
    # Multi-day mode is disabled because SimFin has no daily call limit
    # SimFin is rate-limited per second (2 calls/sec), not per day
    return False


def parse_indices(indices_str: str) -> list:
    """Parse comma-separated index string into list of WatchlistIndex"""
    valid_indices = ['sp500', 'sp400', 'sp600', 'nasdaq100', 'russell1000', 'russell2000', 'russell3000', 'combined_sp']
    indices = []
    for idx in indices_str.split(','):
        idx = idx.strip().lower()
        if idx not in valid_indices:
            raise argparse.ArgumentTypeError(f"Invalid index '{idx}'. Valid options: {valid_indices}")
        indices.append(WatchlistIndex(idx))
    return indices


def main():
    parser = argparse.ArgumentParser(
        description='Algorithmic Quality Scoring System',
        epilog='Examples:\n'
               '  # Single index analysis (sequential - default)\n'
               '  python main_quality_analysis.py --index sp500 --limit 50\n'
               '\n'
               '  # Multiple indices combined\n'
               '  python main_quality_analysis.py --indices sp500,sp400,sp600 --limit 100\n'
               '\n'
               '  # Parallel fetching (10x speedup for large indices)\n'
               '  python main_quality_analysis.py --index combined_sp --limit 0 --parallel\n'
               '\n'
               '  # Individual stock analysis\n'
               '  python main_quality_analysis.py --ticker AAPL',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='%(prog)s [options]'
    )

    # Create mutually exclusive group for index vs indices vs ticker
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '--index',
        type=str,
        choices=['sp500', 'sp400', 'sp600', 'nasdaq100', 'russell1000', 'russell2000', 'russell3000', 'combined_sp'],
        help='Single index to screen. Options: sp500, sp400, sp600, nasdaq100, combined_sp, etc.'
    )
    group.add_argument(
        '--indices',
        type=str,
        help='Multiple indices to combine (comma-separated). Example: sp500,sp400,sp600'
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
        help='Maximum tickers to analyze (default: 50). Use 0 for all tickers. Ignored for --ticker.'
    )

    parser.add_argument(
        '--parallel',
        action='store_true',
        help='Enable parallel fetching for faster analysis (6-10x speedup). Recommended for indices >100 tickers.'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of parallel workers for fetching (default: 10). Range: 5-20. Higher values = faster but may hit rate limits.'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Maximum runtime in seconds (default: 600 = 10 minutes). Increase for large indices with parallel mode.'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.index and not args.indices and not args.ticker:
        # Default to index analysis if nothing specified
        args.index = 'sp500'

    if args.ticker and args.limit != 50:
        parser.error("--limit is only used with --index or --indices, not --ticker")

    if args.parallel and args.workers < 1:
        parser.error("--workers must be at least 1")

    if args.timeout < 0:
        parser.error("--timeout must be a positive number (use 0 for no timeout)")

    print(f"{'='*60}")
    print(f"QUALITY ANALYSIS SYSTEM")
    print(f"{'='*60}")

    if args.ticker:
        # Individual stock analysis
        print(f"Mode: Individual Stock Analysis")
        print(f"Ticker: {args.ticker.upper()}")
        print()

        analyzer = IndividualStockAnalysis(ticker=args.ticker.upper())
        analyzer.run()

    else:
        # Index analysis (single or multiple)
        # Create watchlist config first
        if args.index:
            index_map = {
                'sp500': WatchlistIndex.SP500,
                'sp400': WatchlistIndex.SP400,
                'sp600': WatchlistIndex.SP600,
                'nasdaq100': WatchlistIndex.NASDAQ100,
                'russell1000': WatchlistIndex.RUSSELL1000,
                'russell2000': WatchlistIndex.RUSSELL2000,
                'russell3000': WatchlistIndex.RUSSELL3000,
                'combined_sp': WatchlistIndex.COMBINED_SP
            }
            config = WatchlistConfig(
                index=index_map[args.index],
                limit=args.limit if args.limit > 0 else None
            )
        else:
            # Multiple indices
            multi_indices = parse_indices(args.indices)
            config = WatchlistConfig(
                index=WatchlistIndex.MULTI,
                multi_indices=multi_indices,
                limit=args.limit if args.limit > 0 else None
            )
        
        # Get tickers
        all_tickers = config.get_tickers()
        
        # Multi-day mode is disabled - SimFin has no daily call limit
        # Processing always happens in single session now
        
        # Regular index analysis
        print(f"Mode: Index Analysis")

        if args.index:
            index_display = args.index
            print(f"Index: {args.index}")
        else:
            indices_list = args.indices.split(',')
            index_display = f"[{args.indices}]"
            print(f"Indices: {args.indices}")

        print(f"Total tickers: {len(all_tickers)}")
        print(f"Limit: {args.limit if args.limit > 0 else 'All'}")
        print(f"Parallel: {'Enabled' if args.parallel else 'Disabled'}")
        if args.parallel:
            print(f"Workers: {args.workers}")
        print(f"Timeout: {args.timeout}s")
        print(f"Data Source: SimFin (no daily rate limit)")
        print()

        # Run analysis with parallel options
        script = QualityAnalysisScript(watchlist_config=config)
        script.run(
            watchlist_limit=args.limit if args.limit > 0 else None,
            parallel=args.parallel,
            max_workers=args.workers,
            timeout_seconds=args.timeout
        )


if __name__ == "__main__":
    main()