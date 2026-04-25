#!/usr/bin/env python3
"""
Quality Analysis Main Entry Point
Cross-sectional quality scoring based on academic research

Uses profitability-anchored opportunity discovery framework from
quality_investing_academic_research.md (Novy-Marx, Fama-French,
AQR QMJ, Sloan, Piotroski, etc.)

Two-Phase Workflow (Recommended):
    # Phase 1: Fetch data (resumable with Ctrl-C)
    python main_quality_analysis.py --fetch-only

    # Phase 2: Score cached data (instant, re-runnable)
    python main_quality_analysis.py --score-only

Single-Step Workflow:
    # Fetch + score in one command (default: combined SP1500)
    python main_quality_analysis.py

    # Specific index
    python main_quality_analysis.py --index sp500

    # Multiple indices
    python main_quality_analysis.py --indices sp500,sp400,sp600

Other Options:
    --limit N: Process first N tickers only
    --workers N: Parallel workers (default: 10, max: 10 for yfinance)
    --rate R: Requests per second (default: 1.0, lower if hitting 429s)
    --top-n N: Number in shortlist (default: 25)
    --ticker AAPL: Single-stock analysis

Output:
    - outputs/opportunities_YYYYMMDD.json: Full ranked dataset with all signals
    - outputs/opportunities_YYYYMMDD_top.txt: Human-readable top-N shortlist
    - outputs/opportunities_YYYYMMDD_red.txt: Red-flagged tickers (failed hard gates)

Defaults:
    - Index: combined_sp (S&P 1500 = SP500 + SP400 + SP600)
    - Workers: 10 (yfinance limit)
    - Rate: 1.0 req/sec

Author: Quality Scoring System
Date: 2026
"""

import argparse
import logging
import sys
import signal
from pathlib import Path
from typing import List

# Configure logging to suppress all console output - only progress bar should show
# Remove any existing handlers
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Create a null handler to prevent "No handler found" warnings
null_handler = logging.NullHandler()
root_logger.addHandler(null_handler)

# Set root logger level to ERROR to suppress warnings/info
root_logger.setLevel(logging.ERROR)

# Suppress specific noisy loggers
logging.getLogger('schwab_portfolio').setLevel(logging.ERROR)
logging.getLogger('simfin').setLevel(logging.ERROR)
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('pandas').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

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

from workflows.opportunity_discovery import OpportunityDiscoveryWorkflow
from data.watchlist_config import WatchlistConfig, WatchlistIndex


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
        description='Cross-Sectional Quality Scoring (Academic Research-Based)',
        epilog='Examples:\n'
               '  # Two-step workflow (recommended for large indices):\n'
               '  python main_quality_analysis.py --fetch-only  # Fetch data (resumable)\n'
               '  python main_quality_analysis.py --score-only  # Score cached data\n'
               '\n'
               '  # One-step workflow (fetch + score):\n'
               '  python main_quality_analysis.py               # Default: combined SP1500\n'
               '  python main_quality_analysis.py --index sp500 # Specific index\n'
               '\n'
               '  # Multiple indices:\n'
               '  python main_quality_analysis.py --indices sp500,sp400,sp600\n'
               '\n'
               '  # Limit processing:\n'
               '  python main_quality_analysis.py --index sp500 --limit 100\n'
               '\n'
               '  # Single stock:\n'
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
        help='Single index to screen (default: combined_sp)'
    )
    group.add_argument(
        '--indices',
        type=str,
        help='Multiple indices to combine (comma-separated, e.g., sp500,sp400,sp600)'
    )
    group.add_argument(
        '--ticker',
        type=str,
        help='Individual stock ticker (e.g., AAPL, MSFT, NVDA)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Maximum tickers to process (0 = all)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Parallel workers (default: 10, max: 10 for yfinance)'
    )

    parser.add_argument(
        '--top-n',
        type=int,
        default=25,
        help='Number of top opportunities in shortlist (default: 25)'
    )

    parser.add_argument(
        '--rate',
        type=float,
        default=1.0,
        help='Requests per second (default: 1.0, lower if hitting 429s)'
    )

    parser.add_argument(
        '--fetch-only',
        action='store_true',
        help='Only fetch and cache data, do not score (resumable with Ctrl-C)'
    )

    parser.add_argument(
        '--score-only',
        action='store_true',
        help='Skip fetch phase, only score cached data'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.index and not args.indices and not args.ticker:
        # Default to composite SP1500 (all S&P indices combined)
        args.index = 'combined_sp'

    if args.ticker and args.limit != 0:
        parser.error("--limit is only used with --index or --indices, not --ticker")

    if args.workers < 1 or args.workers > 10:
        parser.error("--workers must be between 1 and 10 (yfinance limitation)")

    if args.fetch_only and args.score_only:
        parser.error("Cannot use --fetch-only and --score-only together. Choose one.")

    if args.ticker:
        # Individual stock analysis - use opportunity scorer on single ticker
        # Create a temporary index with just this ticker
        config = WatchlistConfig(
            index=WatchlistIndex.CUSTOM,
            custom_tickers=[args.ticker.upper()]
        )
        workflow = OpportunityDiscoveryWorkflow(
            watchlist_config=config,
            max_workers=1,
            requests_per_second=args.rate,
            top_n=1,
        )
        if args.score_only:
            workflow.score([args.ticker.upper()])
        else:
            workflow.run(limit=1)
        print(f"\nSingle-ticker analysis complete. Check outputs/opportunities_*.txt for {args.ticker.upper()}")
        return

    # Index analysis (single or multiple)
    # Create watchlist config
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
    print(f"Universe: {len(all_tickers)} tickers from {args.index or args.indices}")

    # Always use opportunity discovery workflow (academic research-based)
    workflow = OpportunityDiscoveryWorkflow(
        watchlist_config=config,
        max_workers=min(args.workers, 10),  # yfinance does not like >10 concurrent
        requests_per_second=args.rate,
        top_n=args.top_n,
    )
    tickers = config.get_tickers()
    if args.limit > 0:
        tickers = tickers[: args.limit]

    if args.fetch_only:
        # Phase 1 only: fetch and cache (resumable with Ctrl-C)
        workflow.gather(tickers)
        print(f"\n✅ Fetch complete. Data cached in merged_opportunity_cache.pkl")
        print(f"📊 Run scoring with: python main_quality_analysis.py --score-only")
    elif args.score_only:
        # Phase 2 only: score from cache
        workflow.score(tickers)
    else:
        # Both phases: fetch then score
        workflow.run(limit=args.limit if args.limit > 0 else None)


if __name__ == "__main__":
    main()