#!/usr/bin/env python3
"""
Watchlist Generator Script
Weekly screening script to identify high-quality stocks from S&P 500

Outputs:
- outputs/quality_watchlist_YYYYMMDD.csv: Top quality stocks
- outputs/quality_watchlist_YYYYMMDD_summary.txt: Human-readable summary
- outputs/quality_watchlist_YYYYMMDD_full.json: Complete screening results
"""

import json
import logging
import os
import sys
import csv
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports (Portfolio Scripts Schwab/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.financial_data_fetcher import FinancialDataFetcher, FinancialData
from quality.quality_metrics_calculator import QualityMetricsCalculator, QualityAnalysisResult
from config.hf_config import HFConfig
from data.watchlist_config import WatchlistConfig, WatchlistIndex

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WatchlistGenerator:
    """
    Configurable quality screening across multiple indexes

    Workflow:
    1. Fetch ticker list from configured index (SP500/SP400/SP600/NASDAQ100/Combined)
    2. Fetch financial data for all tickers (parallel)
    3. Calculate quality metrics
    4. Filter by quality threshold (>70)
    5. Rank by composite score
    6. Export top stocks to watchlist
    """

    def __init__(
        self,
        watchlist_config: Optional[WatchlistConfig] = None,
        min_quality_score: float = 70.0,
        max_workers: int = 10
    ):
        """
        Initialize watchlist generator

        Args:
            watchlist_config: Watchlist configuration (defaults to HFConfig.WATCHLIST_CONFIG)
            min_quality_score: Minimum quality score for inclusion (default: 70)
            max_workers: Number of parallel workers for fetching (default: 10)
        """
        self.watchlist_config = watchlist_config or HFConfig.WATCHLIST_CONFIG
        self.min_quality_score = min_quality_score
        self.max_workers = max_workers
        self.financial_fetcher = FinancialDataFetcher(enable_cache=True)
        self.quality_calculator = QualityMetricsCalculator()

    def get_universe_tickers(self) -> List[str]:
        """
        Get universe of tickers to screen (configured index)

        Returns:
            List of ticker symbols
        """
        logger.info(f"Fetching ticker list from {self.watchlist_config}")
        tickers = self.watchlist_config.get_tickers()

        if not tickers:
            logger.error(f"Failed to fetch tickers from {self.watchlist_config.index.value}")
            return []

        logger.info(f"Fetched {len(tickers)} tickers from {self.watchlist_config.index.value}")
        return tickers

    def fetch_financial_data_parallel(self, tickers: List[str]) -> Dict[str, FinancialData]:
        """
        Fetch financial data for tickers in parallel

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> FinancialData
        """
        logger.info(f"Fetching financial data for {len(tickers)} tickers (parallel, {self.max_workers} workers)")

        results = {}

        def fetch_single(ticker: str) -> tuple:
            """Fetch single ticker"""
            try:
                data = self.financial_fetcher.fetch_financial_data(ticker)
                return ticker, data
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
                return ticker, None

        # Parallel execution
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(fetch_single, ticker): ticker for ticker in tickers}

            completed = 0
            for future in as_completed(futures):
                ticker, data = future.result()
                if data and data.data_quality != "insufficient":
                    results[ticker] = data

                completed += 1
                if completed % 50 == 0:
                    logger.info(f"Progress: {completed}/{len(tickers)} ({completed/len(tickers)*100:.1f}%)")

        logger.info(f"Successfully fetched {len(results)}/{len(tickers)} tickers ({len(results)/len(tickers)*100:.1f}%)")
        return results

    def calculate_quality_metrics(self, financial_data: Dict[str, FinancialData]) -> Dict[str, QualityAnalysisResult]:
        """
        Calculate quality metrics for all tickers

        Args:
            financial_data: Dict mapping ticker -> FinancialData

        Returns:
            Dict mapping ticker -> QualityAnalysisResult
        """
        logger.info(f"Calculating quality metrics for {len(financial_data)} tickers")

        quality_results = {}
        processed = 0

        for ticker, data in financial_data.items():
            try:
                # Convert FinancialData to format expected by quality calculator
                calculator_input = {
                    'ticker': ticker,
                    'revenue': data.revenue,
                    'cogs': data.cogs,
                    'sga': data.sga,
                    'total_assets': data.total_assets,
                    'net_income': data.net_income,
                    'shareholder_equity': data.shareholder_equity,
                    'free_cash_flow': data.free_cash_flow,
                    'market_cap': data.market_cap,
                    'total_debt': data.total_debt,
                    'nopat': data.nopat
                }

                # Calculate quality metrics
                result = self.quality_calculator.calculate_quality_metrics(calculator_input)
                quality_results[ticker] = result

                processed += 1
                if processed % 50 == 0:
                    logger.info(f"Quality calculation progress: {processed}/{len(financial_data)}")

            except Exception as e:
                logger.warning(f"Failed to calculate quality for {ticker}: {e}")
                continue

        logger.info(f"Calculated quality metrics for {len(quality_results)} tickers")
        return quality_results

    def filter_and_rank(self, quality_results: Dict[str, QualityAnalysisResult]) -> List[tuple]:
        """
        Filter by quality threshold and rank by score

        Args:
            quality_results: Dict mapping ticker -> QualityAnalysisResult

        Returns:
            List of (ticker, result) tuples, sorted by quality score (descending)
        """
        # Filter by minimum quality score
        filtered = [
            (ticker, result)
            for ticker, result in quality_results.items()
            if result.composite_score >= self.min_quality_score
        ]

        # Sort by composite score (descending)
        ranked = sorted(filtered, key=lambda x: x[1].composite_score, reverse=True)

        logger.info(f"Filtered to {len(ranked)} stocks with quality score >= {self.min_quality_score}")

        return ranked

    def export_results(self, ranked_stocks: List[tuple], all_quality_results: Dict[str, QualityAnalysisResult]):
        """
        Export watchlist to CSV, JSON, and summary text

        Args:
            ranked_stocks: List of (ticker, QualityAnalysisResult) tuples
            all_quality_results: All quality results (for full JSON export)
        """
        # Create outputs directory if it doesn't exist
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        # Generate timestamp for filenames (used in JSON metadata only)
        timestamp = datetime.now().strftime("%Y%m%d")

        # NOTE: CSV, full JSON, and summary exports have been removed to reduce file redundancy
        # All watchlist data is now in quality_analysis.json (generated by quality_analysis_script.py)
        # This consolidates 5 output files down to 2: quality_analysis.json + quality_analysis_summary.txt

        # Export CSV (primary watchlist) - COMMENTED OUT (redundant with quality_analysis.json)
        # csv_file = output_dir / "quality_watchlist.csv"
        # with open(csv_file, 'w', newline='') as f:
        #     writer = csv.writer(f)
        #     writer.writerow(['Ticker', 'Market_Cap', 'Quality_Score', 'Tier', 'Red_Flags', 'Gross_Profitability', 'ROE', 'ROIC', 'FCF_Yield', 'Operating_Profitability'])
        #
        #     for ticker, result in ranked_stocks:
        #         # Extract metric values
        #         metrics = {m.name: m.value for m in result.metric_scores}
        #
        #         # Format market cap (billions)
        #         market_cap_str = f"{result.market_cap / 1e9:.2f}B" if result.market_cap else "N/A"
        #
        #         writer.writerow([
        #             ticker,
        #             market_cap_str,
        #             f"{result.composite_score:.1f}",
        #             result.tier.value,
        #             len(result.red_flags),
        #             f"{metrics.get('Gross Profitability', 0):.3f}",
        #             f"{metrics.get('ROE', 0):.3f}",
        #             f"{metrics.get('ROIC', 0):.3f}",
        #             f"{metrics.get('FCF Yield', 0):.3f}",
        #             f"{metrics.get('Operating Profitability', 0):.3f}"
        #         ])
        #
        # logger.info(f"Exported CSV watchlist to {csv_file}")

        # Export full JSON - COMMENTED OUT (redundant with quality_analysis.json)
        # json_file = output_dir / "quality_watchlist_full.json"
        # json_data = {
        #     'timestamp': datetime.now().isoformat(),
        #     'total_screened': len(all_quality_results),
        #     'watchlist_count': len(ranked_stocks),
        #     'min_quality_score': self.min_quality_score,
        #     'watchlist': [
        #         {
        #             'ticker': ticker,
        #             'market_cap': result.market_cap,
        #             'quality_score': result.composite_score,
        #             'tier': result.tier.value,
        #             'red_flags_count': len(result.red_flags),
        #             'red_flags': [
        #                 {
        #                     'category': rf.category,
        #                     'severity': rf.severity,
        #                     'description': rf.description
        #                 }
        #                 for rf in result.red_flags
        #             ],
        #             'metrics': {
        #                 m.name: {
        #                     'value': m.value,
        #                     'score': m.score,
        #                     'weighted_score': m.weighted_score
        #                 }
        #                 for m in result.metric_scores
        #             }
        #         }
        #         for ticker, result in ranked_stocks
        #     ],
        #     'statistics': {
        #         'elite_count': sum(1 for _, r in ranked_stocks if r.tier.value == 'Elite'),
        #         'strong_count': sum(1 for _, r in ranked_stocks if r.tier.value == 'Strong'),
        #         'average_quality_score': sum(r.composite_score for _, r in ranked_stocks) / len(ranked_stocks) if ranked_stocks else 0,
        #         'top_quality_score': ranked_stocks[0][1].composite_score if ranked_stocks else 0
        #     }
        # }
        #
        # with open(json_file, 'w') as f:
        #     json.dump(json_data, f, indent=2)
        #
        # logger.info(f"Exported full JSON to {json_file}")

        # Export summary text - COMMENTED OUT (redundant with quality_analysis_summary.txt)
        # summary_file = output_dir / "quality_watchlist_summary.txt"
        # with open(summary_file, 'w') as f:
        #     f.write("="*60 + "\n")
        #     f.write("QUALITY WATCHLIST - WEEKLY SCREENING SUMMARY\n")
        #     f.write("="*60 + "\n")
        #     f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        #     f.write(f"Total Stocks Screened: {len(all_quality_results)}\n")
        #     f.write(f"Minimum Quality Score: {self.min_quality_score}\n")
        #     f.write(f"Stocks in Watchlist: {len(ranked_stocks)}\n")
        #     f.write("="*60 + "\n\n")
        #
        #     # Statistics
        #     f.write("QUALITY DISTRIBUTION:\n")
        #     f.write("-"*60 + "\n")
        #     elite_count = sum(1 for _, r in ranked_stocks if r.tier.value == 'Elite')
        #     strong_count = sum(1 for _, r in ranked_stocks if r.tier.value == 'Strong')
        #     moderate_count = sum(1 for _, r in ranked_stocks if r.tier.value == 'Moderate')
        #
        #     f.write(f"Elite (85-100):      {elite_count:4} stocks\n")
        #     f.write(f"Strong (70-84):      {strong_count:4} stocks\n")
        #     f.write(f"Moderate (50-69):    {moderate_count:4} stocks\n")
        #     f.write(f"\nAverage Quality Score: {sum(r.composite_score for _, r in ranked_stocks) / len(ranked_stocks):.1f}\n" if ranked_stocks else "")
        #     f.write(f"Highest Quality Score: {ranked_stocks[0][1].composite_score:.1f} ({ranked_stocks[0][0]})\n" if ranked_stocks else "")
        #     f.write("\n")
        #
        #     # Top 50 stocks
        #     f.write("="*80 + "\n")
        #     f.write("TOP 50 QUALITY STOCKS:\n")
        #     f.write("-"*80 + "\n")
        #     f.write(f"{'Rank':<6} {'Ticker':<8} {'Market Cap':<12} {'Score':<8} {'Tier':<12} {'Red Flags':<10}\n")
        #     f.write("-"*80 + "\n")
        #
        #     for rank, (ticker, result) in enumerate(ranked_stocks[:50], 1):
        #         # Format market cap
        #         if result.market_cap:
        #             if result.market_cap >= 1e9:
        #                 market_cap_str = f"${result.market_cap / 1e9:.2f}B"
        #             elif result.market_cap >= 1e6:
        #                 market_cap_str = f"${result.market_cap / 1e6:.2f}M"
        #             else:
        #                 market_cap_str = f"${result.market_cap:.0f}"
        #         else:
        #             market_cap_str = "N/A"
        #
        #         f.write(f"{rank:<6} {ticker:<8} {market_cap_str:<12} {result.composite_score:6.1f}   {result.tier.value:<12} {len(result.red_flags):<10}\n")
        #
        #     # Elite stocks breakdown
        #     f.write("\n" + "="*80 + "\n")
        #     f.write("ELITE QUALITY STOCKS (Score >= 85):\n")
        #     f.write("-"*80 + "\n")
        #     elite_stocks = [(ticker, result) for ticker, result in ranked_stocks if result.tier.value == 'Elite']
        #     if elite_stocks:
        #         for ticker, result in elite_stocks:
        #             # Format market cap
        #             if result.market_cap:
        #                 if result.market_cap >= 1e9:
        #                     market_cap_str = f"${result.market_cap / 1e9:.2f}B"
        #                 elif result.market_cap >= 1e6:
        #                     market_cap_str = f"${result.market_cap / 1e6:.2f}M"
        #                 else:
        #                     market_cap_str = f"${result.market_cap:.0f}"
        #             else:
        #                 market_cap_str = "N/A"
        #
        #             f.write(f"\n{ticker}: {result.composite_score:.1f} (Market Cap: {market_cap_str})\n")
        #             f.write(f"  Metrics:\n")
        #             for metric in result.metric_scores:
        #                 f.write(f"    {metric.name}: {metric.value:.3f} (score: {metric.score:.1f}/10)\n")
        #             if result.red_flags:
        #                 f.write(f"  Red Flags: {len(result.red_flags)}\n")
        #     else:
        #         f.write("No elite stocks found in this screening.\n")
        #
        # logger.info(f"Exported summary to {summary_file}")

        # Calculate elite/strong counts for console output
        elite_count = sum(1 for _, r in ranked_stocks if r.tier.value == 'Elite')
        strong_count = sum(1 for _, r in ranked_stocks if r.tier.value == 'Strong')

        # Print console summary
        print("\n" + "="*60)
        print("QUALITY WATCHLIST GENERATION COMPLETE")
        print("="*60)
        print(f"Total stocks screened: {len(all_quality_results)}")
        print(f"Watchlist stocks: {len(ranked_stocks)}")
        print(f"Elite stocks (>=85): {elite_count}")
        print(f"Strong stocks (70-84): {strong_count}")
        print(f"\nTop 10 Quality Stocks:")
        for rank, (ticker, result) in enumerate(ranked_stocks[:10], 1):
            print(f"  {rank:2}. {ticker:6} - Score: {result.composite_score:5.1f} ({result.tier.value})")
        print(f"\nNOTE: Watchlist data is now in quality_analysis.json (consolidated)")
        print(f"See quality_analysis_summary.txt for human-readable summary")
        print("="*60 + "\n")

    def run(self):
        """
        Run complete watchlist generation pipeline
        """
        logger.info("Starting weekly watchlist generation")

        # Get S&P 500 tickers
        tickers = self.get_universe_tickers()
        if not tickers:
            logger.error("No tickers to screen. Exiting.")
            return

        # Fetch financial data (parallel)
        financial_data = self.fetch_financial_data_parallel(tickers)
        if not financial_data:
            logger.error("Failed to fetch financial data. Exiting.")
            return

        # Calculate quality metrics
        quality_results = self.calculate_quality_metrics(financial_data)
        if not quality_results:
            logger.error("Failed to calculate quality metrics. Exiting.")
            return

        # Filter and rank
        ranked_stocks = self.filter_and_rank(quality_results)

        # Export results
        self.export_results(ranked_stocks, quality_results)

        logger.info("Watchlist generation complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate quality watchlist from configurable index screening"
    )
    parser.add_argument(
        '--index',
        type=str,
        default='sp500',
        choices=['sp500', 'sp400', 'sp600', 'nasdaq100', 'combined_sp'],
        help='Index to screen (default: sp500). Options: sp500 (large cap ~500), '
             'sp400 (mid cap ~400), sp600 (small cap ~600), nasdaq100 (tech ~100), '
             'combined_sp (S&P 1500 ~1500)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of tickers to screen (for performance)'
    )
    parser.add_argument(
        '--min-quality',
        type=float,
        default=70.0,
        help='Minimum quality score for inclusion (default: 70.0)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of parallel workers for fetching (default: 10)'
    )

    args = parser.parse_args()

    # Map CLI argument to WatchlistIndex enum
    index_map = {
        'sp500': WatchlistIndex.SP500,
        'sp400': WatchlistIndex.SP400,
        'sp600': WatchlistIndex.SP600,
        'nasdaq100': WatchlistIndex.NASDAQ100,
        'combined_sp': WatchlistIndex.COMBINED_SP
    }

    # Create watchlist config
    watchlist_config = WatchlistConfig(
        index=index_map[args.index],
        limit=args.limit
    )

    logger.info(f"Using watchlist configuration: {watchlist_config}")

    # Run watchlist generation
    generator = WatchlistGenerator(
        watchlist_config=watchlist_config,
        min_quality_score=args.min_quality,
        max_workers=args.workers
    )
    generator.run()


if __name__ == "__main__":
    main()
