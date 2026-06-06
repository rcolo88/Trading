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
        # Individual stock analysis
        ticker = args.ticker.upper()

        # For single-ticker, we want to score against the full cached universe (if available)
        # to get meaningful cross-sectional z-scores. Otherwise z-scores are all 0.0 (N=1).
        from pathlib import Path
        import pickle

        cache_file = Path(__file__).parent / "merged_opportunity_cache.pkl"
        cached_universe = []

        if cache_file.exists() and args.score_only:
            # Load all cached tickers to use as universe
            try:
                with cache_file.open("rb") as f:
                    cache_data = pickle.load(f)
                    cached_universe = list(cache_data.keys())
                if len(cached_universe) > 1:
                    print(f"[single-ticker] Scoring {ticker} against cached universe of {len(cached_universe)} tickers")
                    print(f"[single-ticker] This provides meaningful cross-sectional z-scores")
            except Exception as e:
                print(f"[single-ticker] Could not load cache: {e}")

        # Create workflow
        if cached_universe and args.score_only:
            # Score against full universe, then filter to target ticker
            config = WatchlistConfig(
                index=WatchlistIndex.CUSTOM,
                custom_tickers=cached_universe
            )
            workflow = OpportunityDiscoveryWorkflow(
                watchlist_config=config,
                max_workers=1,
                requests_per_second=args.rate,
                top_n=len(cached_universe),  # Get all reports
                write_outputs=False,  # We'll write custom filtered output
            )
            reports = workflow.score(cached_universe)

            # Filter to target ticker and write custom output
            target_report = next((r for r in reports if r.ticker == ticker), None)
            if target_report:
                # Write single-ticker output files
                from datetime import datetime
                import json
                from pathlib import Path

                outputs_dir = Path(__file__).parent / "outputs"
                outputs_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d")

                # JSON output (single ticker)
                json_path = outputs_dir / f"opportunities_{stamp}_single_{ticker}.json"
                with json_path.open("w") as f:
                    json.dump(target_report.to_dict(), f, indent=2, default=str)

                # Human-readable output
                txt_path = outputs_dir / f"opportunities_{stamp}_single_{ticker}.txt"
                with txt_path.open("w") as f:
                    f.write(f"Single Ticker Analysis: {ticker}\n")
                    f.write(f"Universe: {len(cached_universe)} tickers from cache\n")
                    f.write("=" * 80 + "\n\n")
                    f.write(f"Rank:              {reports.index(target_report) + 1} of {len(reports)}\n")
                    f.write(f"Opportunity Score: {target_report.opportunity_score:.1f} / 100\n")
                    if target_report.qarp_score:
                        f.write(f"QARP Score:        {target_report.qarp_score:.1f} / 100\n")
                    f.write(f"Tier:              {target_report.tier}\n")
                    f.write(f"Gates Passed:      {'✅ Yes' if target_report.gates_passed else '❌ No'}\n")
                    if target_report.gate_failures:
                        f.write(f"Gate Failures:     {', '.join(target_report.gate_failures)}\n")
                    f.write(f"Sector:            {target_report.sector or 'N/A'}\n")
                    f.write(f"Market Cap:        ${target_report.market_cap:,.0f}\n" if target_report.market_cap else "")
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("SIGNALS (Raw Values)\n")
                    f.write("=" * 80 + "\n")
                    for k, v in target_report.signals.items():
                        if v is not None:
                            if isinstance(v, float):
                                if abs(v) < 0.01:
                                    f.write(f"{k:25s} {v:.4f}\n")
                                elif abs(v) < 1:
                                    f.write(f"{k:25s} {v:.3f}\n")
                                else:
                                    f.write(f"{k:25s} {v:.2f}\n")
                            else:
                                f.write(f"{k:25s} {v}\n")
                    f.write("\n" + "=" * 80 + "\n")
                    f.write("Z-SCORES (Cross-Sectional Rankings)\n")
                    f.write("=" * 80 + "\n")
                    for k, v in target_report.z_scores.items():
                        percentile = 50 + (v / 3) * 50  # Rough percentile estimate
                        percentile = max(0, min(100, percentile))
                        f.write(f"{k:25s} {v:6.2f}  (~{percentile:.0f}th percentile)\n")

                print(f"\n✅ Single-ticker analysis complete:")
                print(f"   Rank: {reports.index(target_report) + 1} / {len(reports)}")
                print(f"   Opp Score: {target_report.opportunity_score:.1f}")
                print(f"   QARP Score: {target_report.qarp_score:.1f}" if target_report.qarp_score else "")
                print(f"   Tier: {target_report.tier}")
                print(f"\n📄 Details: {txt_path}")
                print(f"📊 JSON: {json_path}")
            else:
                print(f"❌ {ticker} not found in cached universe")
        else:
            # Fallback: analyze in isolation (z-scores will be 0.0)
            if not args.score_only:
                print(f"[single-ticker] Fetching data for {ticker} (isolated analysis)")
                print(f"[single-ticker] ⚠️  Z-scores will be 0.0 (N=1). Run --fetch-only on an index first, then --ticker {ticker} --score-only for cross-sectional rankings.")

            config = WatchlistConfig(
                index=WatchlistIndex.CUSTOM,
                custom_tickers=[ticker]
            )
            workflow = OpportunityDiscoveryWorkflow(
                watchlist_config=config,
                max_workers=1,
                requests_per_second=args.rate,
                top_n=1,
            )
            if args.score_only:
                workflow.score([ticker])
            else:
                workflow.run(limit=1)
            print(f"\nSingle-ticker analysis complete. Check outputs/opportunities_*.txt for {ticker}")
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