#!/usr/bin/env python3
"""
Quality Analysis Script
Standalone script to analyze quality metrics for portfolio holdings vs watchlist alternatives

Outputs:
- outputs/quality_analysis_YYYYMMDD.json: Complete quality analysis results
- outputs/quality_analysis_YYYYMMDD_summary.txt: Human-readable summary with recommendations
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports (Portfolio Scripts Schwab/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.financial_data_fetcher import FinancialDataFetcher, FinancialData
from quality.quality_metrics_calculator import QualityMetricsCalculator, QualityAnalysisResult
from quality.market_cap_classifier import MarketCapClassifier
from components.quality_persistence_analyzer import QualityPersistenceAnalyzer
from data.watchlist_config import WatchlistConfig, WatchlistIndex

# Quality thresholds (formerly from HFConfig)
QUALITY_MIN_SCORE = 70      # Minimum quality score for holdings
QUALITY_IDEAL_SCORE = 85    # Ideal quality score for new buys
QUALITY_SWAP_THRESHOLD = 15 # Minimum score improvement to swap holdings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QualityAnalysisScript:
    """
    Standalone quality analysis pipeline for stock indices

    Workflow:
    1. Fetch watchlist tickers from configured index (SP500/SP400/SP600/etc.)
    2. Fetch financial data for all tickers in the index
    3. Calculate quality metrics for all tickers
    4. Classify market cap tiers
    5. Analyze ROE persistence
    6. Rank stocks by quality score
    7. Export results to JSON and summary text
    """

    def __init__(self, watchlist_config: Optional[WatchlistConfig] = None):
        """
        Initialize quality analysis script

        Args:
            watchlist_config: Watchlist configuration (defaults to S&P 500)
        """
        self.watchlist_config = watchlist_config or WatchlistConfig(index=WatchlistIndex.SP500)
        self.financial_fetcher = FinancialDataFetcher(enable_cache=True)
        self.fetcher = self.financial_fetcher  # Alias for compatibility
        self.market_cap_classifier = MarketCapClassifier()
        self.roe_analyzer = QualityPersistenceAnalyzer()
        self.quality_calculator = QualityMetricsCalculator()
        self.results = {}



    def get_watchlist_tickers(self, limit: Optional[int] = None) -> List[str]:
        """
        Get watchlist tickers from configured index

        Args:
            limit: Optional limit (overrides watchlist_config.limit if provided)

        Returns:
            List of ticker symbols
        """
        # Use WatchlistConfig system
        # Apply limit override if provided
        if limit:
            config_with_limit = WatchlistConfig(
                index=self.watchlist_config.index,
                custom_tickers=self.watchlist_config.custom_tickers,
                limit=limit
            )
            watchlist = config_with_limit.get_tickers()
        else:
            watchlist = self.watchlist_config.get_tickers()

        if not watchlist:
            logger.error(f"Failed to fetch tickers from {self.watchlist_config.index.value}")
            return []

        logger.info(f"Using {self.watchlist_config.index.value} watchlist: {len(watchlist)} tickers")
        return watchlist

    def fetch_financial_data(self, tickers: List[str]) -> Dict[str, FinancialData]:
        """
        Fetch financial data for list of tickers

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker -> FinancialData
        """
        logger.info(f"Fetching financial data for {len(tickers)} tickers")

        results = self.financial_fetcher.batch_fetch(tickers)

        # Filter out failed fetches
        valid_results = {
            ticker: data
            for ticker, data in results.items()
            if data and data.data_quality != "insufficient"
        }

        logger.info(f"Successfully fetched {len(valid_results)}/{len(tickers)} tickers")
        return valid_results

    def calculate_quality_metrics(self, financial_data: Dict[str, FinancialData]) -> Dict[str, QualityAnalysisResult]:
        """
        Calculate quality metrics for all tickers

        Args:
            financial_data: Dict mapping ticker -> FinancialData

        Returns:
            Dict mapping ticker -> QualityAnalysisResult
        """
        quality_results = {}

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

                logger.info(f"{ticker}: Quality score {result.composite_score:.1f} ({result.tier.value})")

            except Exception as e:
                logger.warning(f"Failed to calculate quality for {ticker}: {e}")
                continue

        return quality_results



    def export_results(
        self,
        quality_results: Dict[str, QualityAnalysisResult],
        market_cap_tiers: Dict[str, str],
        roe_persistence: Dict[str, Dict],
        strict_filters: Dict[str, Dict]
    ):
        """
        Export quality analysis results to JSON and summary text

        Args:
            quality_results: Quality analysis results for all tickers
            market_cap_tiers: Market cap tier classification
            roe_persistence: ROE persistence analysis results
            strict_filters: Small cap strict quality filters results
        """
        # Create outputs directory if it doesn't exist
        output_dir = Path(__file__).parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d")

        # Sort quality results by composite score (descending) for consistent ordering
        sorted_results = sorted(
            quality_results.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )

        # Prepare JSON output
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'index': self.watchlist_config.index.value,
            'tickers_analyzed': len(quality_results),
            'quality_results': {
                ticker: {
                    'composite_score': result.composite_score,
                    'tier': result.tier.value if result.tier else "Unknown",
                    'market_cap': result.market_cap,
                    'red_flags_count': len(result.red_flags),
                    'red_flags': [
                        {
                            'category': rf.category,
                            'severity': rf.severity,
                            'description': rf.description
                        }
                        for rf in result.red_flags
                    ],
                    'metrics': {
                        m.name: {
                            'value': m.value,
                            'score': m.score,
                            'weighted_score': m.weighted_score
                        }
                        for m in result.metric_scores
                    }
                }
                for ticker, result in sorted_results  # Use sorted results
            },
            'market_cap_tiers': market_cap_tiers,
            'roe_persistence': roe_persistence,
            'strict_filters': strict_filters
        }

        # Export JSON (handle numpy types)
        json_file = output_dir / "quality_analysis.json"
        with open(json_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)

        logger.info(f"Exported JSON results to {json_file}")

        # Export summary text
        summary_file = output_dir / "quality_analysis_summary.txt"
        with open(summary_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("QUALITY ANALYSIS SUMMARY\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Index: {self.watchlist_config.index.value}\n")
            f.write(f"Stocks Analyzed: {len(quality_results)}\n")
            f.write("="*60 + "\n\n")

            # Quality Score Distribution
            f.write("QUALITY SCORE DISTRIBUTION:\n")
            f.write("-"*60 + "\n")
            elite = sum(1 for r in quality_results.values() if r.composite_score >= 85)
            strong = sum(1 for r in quality_results.values() if 70 <= r.composite_score < 85)
            moderate = sum(1 for r in quality_results.values() if 50 <= r.composite_score < 70)
            weak = sum(1 for r in quality_results.values() if r.composite_score < 50)

            f.write(f"Elite (85-100): {elite} stocks\n")
            f.write(f"Strong (70-84): {strong} stocks\n")
            f.write(f"Moderate (50-69): {moderate} stocks\n")
            f.write(f"Weak (0-49): {weak} stocks\n")
            f.write("\n")

            # Top 20 Stocks by Quality
            f.write("="*80 + "\n")
            f.write("TOP 20 STOCKS BY QUALITY SCORE:\n")
            f.write("-"*80 + "\n")
            f.write(f"{'Rank':<4} {'Ticker':<8} {'Market Cap':<12} {'Score':<8} {'Tier':<12} {'Red Flags':<10}\n")
            f.write("-"*80 + "\n")

            for rank, (ticker, result) in enumerate(sorted_results[:20], 1):
                # Format market cap
                if result.market_cap:
                    if result.market_cap >= 1e9:
                        market_cap_str = f"${result.market_cap / 1e9:.2f}B"
                    elif result.market_cap >= 1e6:
                        market_cap_str = f"${result.market_cap / 1e6:.2f}M"
                    else:
                        market_cap_str = f"${result.market_cap:.0f}"
                else:
                    market_cap_str = "N/A"

                tier = result.tier.value if result.tier else "Unknown"
                f.write(f"{rank:<4} {ticker:<8} {market_cap_str:<12} {result.composite_score:5.1f}    {tier:<12} {len(result.red_flags):<10}\n")

            # Market Cap Distribution
            f.write(f"\n{'='*60}\n")
            f.write("MARKET CAP DISTRIBUTION:\n")
            f.write("-"*60 + "\n")

            large_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Large Cap")
            mid_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Mid Cap")
            small_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Small Cap")
            micro_cap = sum(1 for tier in market_cap_tiers.values() if tier == "Micro Cap")

            f.write(f"Large Cap (≥$50B): {large_cap} stocks\n")
            f.write(f"Mid Cap ($2B-$50B): {mid_cap} stocks\n")
            f.write(f"Small Cap ($500M-$2B): {small_cap} stocks\n")
            f.write(f"Micro Cap (<$500M): {micro_cap} stocks\n")

            # ROE Persistence Summary
            if roe_persistence:
                f.write(f"\n{'='*60}\n")
                f.write("ROE PERSISTENCE SUMMARY:\n")
                f.write("-"*60 + "\n")

                compounders = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Quality Compounder')
                improvers = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Quality Improver')
                deteriorators = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Quality Deteriorator')
                inconsistent = sum(1 for r in roe_persistence.values() if r.get('classification') == 'Inconsistent')

                f.write(f"Quality Compounders: {compounders} stocks\n")
                f.write(f"Quality Improvers: {improvers} stocks\n")
                f.write(f"Quality Deteriorators: {deteriorators} stocks\n")
                f.write(f"Inconsistent: {inconsistent} stocks\n")

        logger.info(f"Exported summary to {summary_file}")

        # Print summary to console
        print("\n" + "="*60)
        print("QUALITY ANALYSIS COMPLETE")
        print("="*60)
        print(f"Index: {self.watchlist_config.index.value}")
        print(f"Stocks analyzed: {len(quality_results)}")
        print(f"Elite quality: {elite} stocks (≥85)")
        print(f"Strong quality: {strong} stocks (70-84)")
        print(f"\nResults saved to:")
        print(f"  - {json_file}")
        print(f"  - {summary_file}")
        print("="*60 + "\n")

    def run(self, watchlist_limit: Optional[int] = None):
        """
        Run complete quality analysis pipeline for stock index

        Args:
            watchlist_limit: Maximum number of watchlist tickers to analyze (default: None for full index)
        """
        logger.info("Starting quality analysis pipeline")

        # Get watchlist tickers from configured index
        watchlist = self.get_watchlist_tickers(limit=watchlist_limit)
        if not watchlist:
            logger.error("No watchlist tickers available. Exiting.")
            return

        logger.info(f"Analyzing {len(watchlist)} tickers from {self.watchlist_config.index.value}")

        # Fetch financial data
        financial_data = self.fetch_financial_data(watchlist)

        # Calculate quality metrics
        quality_results = self.calculate_quality_metrics(financial_data)

        # Classify market cap tiers (4-tier framework integration)
        logger.info("Classifying market cap tiers...")
        market_cap_results = self.market_cap_classifier.batch_classify_tickers(list(quality_results.keys()))
        market_cap_tiers = {
            ticker: tier_data.tier.value if tier_data.tier else "Unknown"
            for ticker, tier_data in market_cap_results.classifications.items()
        }
        logger.info(f"Classified {len(market_cap_tiers)} tickers into market cap tiers")

        # Analyze ROE persistence (4-tier framework integration)
        logger.info("Analyzing ROE persistence...")
        roe_persistence = {}
        for ticker in quality_results.keys():
            try:
                # Fetch historical financials (yfinance provides 3-4 years typically)
                hist_data = self.fetcher.fetch_historical_financials(ticker)

                if hist_data is not None and len(hist_data) >= 2:
                    # Minimum 2 years required for analysis
                    persistence_result = self.roe_analyzer.analyze_company(hist_data, ticker=ticker)

                    if persistence_result:
                        # Extract incremental ROCE from trend_analysis if available
                        incremental_roce = persistence_result.trend_analysis.get('incremental_roce_advantage', 0.0) if persistence_result.trend_analysis else 0.0

                        roe_persistence[ticker] = {
                            'years_analyzed': persistence_result.persistence_metrics.years_analyzed,
                            'roe_years_above_15pct': persistence_result.persistence_metrics.roe_years_above_15pct,
                            'roe_mean': persistence_result.persistence_metrics.roe_mean,
                            'incremental_roce_advantage': incremental_roce,
                            'classification': persistence_result.classification.value,
                            'compounder_confidence': persistence_result.compounder_confidence
                        }
                        logger.debug(f"ROE persistence for {ticker}: {persistence_result.classification.value}")
            except Exception as e:
                logger.warning(f"Failed to analyze ROE persistence for {ticker}: {e}")
                continue

        logger.info(f"Analyzed ROE persistence for {len(roe_persistence)} tickers")

        # Analyze small cap strict filters
        logger.info("Analyzing small cap strict filters...")
        strict_filters = {}
        for ticker, tier in market_cap_tiers.items():
            if tier == "Small Cap":
                data = financial_data.get(ticker)
                if data:
                    try:
                        # FCF+ check
                        fcf_positive = data.free_cash_flow and data.free_cash_flow > 0

                        # D/E < 1.0 check
                        if data.total_debt and data.shareholder_equity and data.shareholder_equity > 0:
                            debt_to_equity = data.total_debt / data.shareholder_equity
                            de_pass = debt_to_equity < 1.0
                        else:
                            de_pass = False

                        # GP > 30% check
                        if data.revenue and data.cogs and data.revenue > 0:
                            gross_margin = (data.revenue - data.cogs) / data.revenue
                            gm_pass = gross_margin > 0.30
                        else:
                            gm_pass = False

                        passed = fcf_positive and de_pass and gm_pass

                        strict_filters[ticker] = {
                            'passed': passed,
                            'fcf_positive': fcf_positive,
                            'debt_to_equity_ok': de_pass,
                            'gross_margin_ok': gm_pass
                        }
                    except Exception as e:
                        logger.warning(f"Failed to check strict filters for {ticker}: {e}")
                        continue
        logger.info(f"Analyzed strict filters for {len(strict_filters)} small cap tickers")

        # Export results (quality rankings only)
        self.export_results(
            quality_results,
            market_cap_tiers,
            roe_persistence,
            strict_filters
        )

        logger.info("Quality analysis pipeline complete")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze quality metrics for portfolio holdings vs watchlist alternatives"
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
        default=50,
        help='Maximum number of watchlist tickers to analyze (default: 50). '
             'Use 0 for no limit (screen entire index)'
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
        limit=args.limit if args.limit > 0 else None
    )

    logger.info(f"Using watchlist configuration: {watchlist_config}")

    # Run analysis
    script = QualityAnalysisScript(watchlist_config=watchlist_config)
    script.run(watchlist_limit=args.limit if args.limit > 0 else None)


if __name__ == "__main__":
    main()
