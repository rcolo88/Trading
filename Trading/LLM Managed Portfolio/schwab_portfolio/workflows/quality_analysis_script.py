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
from config.hf_config import HFConfig
from data.watchlist_config import WatchlistConfig, WatchlistIndex

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QualityAnalysisScript:
    """
    Standalone quality analysis pipeline

    Workflow:
    1. Load current portfolio holdings
    2. Fetch watchlist tickers from configured index (SP500/SP400/SP600/etc.)
    3. Fetch financial data for holdings + watchlist
    4. Calculate quality metrics for all tickers
    5. Identify SELL candidates (holdings with quality <70)
    6. Identify BUY alternatives (watchlist with quality >85 OR >15 points better)
    7. Export results to JSON and summary text
    """

    def __init__(self, watchlist_config: Optional[WatchlistConfig] = None):
        """
        Initialize quality analysis script

        Args:
            watchlist_config: Watchlist configuration (defaults to HFConfig.WATCHLIST_CONFIG)
        """
        self.watchlist_config = watchlist_config or HFConfig.WATCHLIST_CONFIG
        self.financial_fetcher = FinancialDataFetcher(enable_cache=True)
        self.market_cap_classifier = MarketCapClassifier()
        self.roe_analyzer = QualityPersistenceAnalyzer()
        self.quality_calculator = QualityMetricsCalculator()
        self.results = {}

    def load_portfolio_holdings(self) -> List[str]:
        """
        Load current portfolio holdings from portfolio_state.json

        Returns:
            List of ticker symbols in portfolio
        """
        # Portfolio state is in parent directory
        portfolio_path = Path(__file__).parent.parent / "portfolio_state.json"

        if not portfolio_path.exists():
            logger.warning(f"Portfolio state not found at {portfolio_path}")
            return []

        try:
            with open(portfolio_path, 'r') as f:
                state = json.load(f)

            holdings = list(state.get('holdings', {}).keys())
            logger.info(f"Loaded {len(holdings)} holdings from portfolio: {holdings}")
            return holdings

        except Exception as e:
            logger.error(f"Failed to load portfolio holdings: {e}")
            return []

    def get_watchlist_tickers(self, limit: Optional[int] = None) -> List[str]:
        """
        Get watchlist tickers from configured index

        Args:
            limit: Optional limit (overrides watchlist_config.limit if provided)

        Returns:
            List of ticker symbols
        """
        # Legacy support: check deprecated WATCHLIST_TICKERS first
        if hasattr(HFConfig, 'WATCHLIST_TICKERS') and HFConfig.WATCHLIST_TICKERS:
            logger.warning("WATCHLIST_TICKERS is deprecated. Use WATCHLIST_CONFIG instead.")
            watchlist = HFConfig.WATCHLIST_TICKERS[:limit] if limit else HFConfig.WATCHLIST_TICKERS
            logger.info(f"Using legacy WATCHLIST_TICKERS: {len(watchlist)} tickers")
            return watchlist

        # Use new WatchlistConfig system
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

    def identify_recommendations(
        self,
        holdings: List[str],
        holdings_quality: Dict[str, QualityAnalysisResult],
        watchlist_quality: Dict[str, QualityAnalysisResult]
    ) -> Dict[str, List[Dict]]:
        """
        Identify SELL and BUY recommendations based on quality analysis

        Args:
            holdings: List of current holdings
            holdings_quality: Quality results for holdings
            watchlist_quality: Quality results for watchlist

        Returns:
            Dict with 'sell_candidates' and 'buy_alternatives' lists
        """
        sell_candidates = []
        buy_alternatives = []

        # Identify SELL candidates (holdings with quality <70)
        for ticker in holdings:
            if ticker not in holdings_quality:
                continue

            result = holdings_quality[ticker]

            if result.composite_score < HFConfig.QUALITY_MIN_SCORE:
                sell_candidates.append({
                    'ticker': ticker,
                    'quality_score': result.composite_score,
                    'tier': result.tier.value,
                    'red_flags': len(result.red_flags),
                    'reason': f"Quality score {result.composite_score:.1f} below minimum threshold {HFConfig.QUALITY_MIN_SCORE}"
                })

        # Identify BUY alternatives from watchlist
        for ticker, result in watchlist_quality.items():
            # Skip if already holding
            if ticker in holdings:
                continue

            # Alternative 1: Quality score >85 (ideal)
            if result.composite_score >= HFConfig.QUALITY_IDEAL_SCORE:
                buy_alternatives.append({
                    'ticker': ticker,
                    'quality_score': result.composite_score,
                    'tier': result.tier.value,
                    'red_flags': len(result.red_flags),
                    'reason': f"Elite quality score {result.composite_score:.1f} (>={HFConfig.QUALITY_IDEAL_SCORE})"
                })
                continue

            # Alternative 2: Score >70 AND >15 points better than weakest holding
            if result.composite_score >= HFConfig.QUALITY_MIN_SCORE:
                # Find weakest holding
                weakest_holding_score = min(
                    [r.composite_score for r in holdings_quality.values()],
                    default=100
                )

                if result.composite_score - weakest_holding_score >= HFConfig.QUALITY_SWAP_THRESHOLD:
                    buy_alternatives.append({
                        'ticker': ticker,
                        'quality_score': result.composite_score,
                        'tier': result.tier.value,
                        'red_flags': len(result.red_flags),
                        'reason': f"Quality score {result.composite_score:.1f} is {result.composite_score - weakest_holding_score:.1f} points better than weakest holding"
                    })

        # Sort by quality score (descending)
        sell_candidates.sort(key=lambda x: x['quality_score'])
        buy_alternatives.sort(key=lambda x: x['quality_score'], reverse=True)

        logger.info(f"Identified {len(sell_candidates)} SELL candidates and {len(buy_alternatives)} BUY alternatives")

        return {
            'sell_candidates': sell_candidates,
            'buy_alternatives': buy_alternatives
        }

    def export_results(
        self,
        holdings_quality: Dict[str, QualityAnalysisResult],
        watchlist_quality: Dict[str, QualityAnalysisResult],
        recommendations: Dict[str, List[Dict]],
        market_cap_tiers: Dict[str, str],
        roe_persistence: Dict[str, Dict],
        strict_filters: Dict[str, Dict]
    ):
        """
        Export analysis results to JSON and summary text (4-tier framework)

        Args:
            holdings_quality: Quality results for holdings
            watchlist_quality: Quality results for watchlist
            recommendations: SELL and BUY recommendations
            market_cap_tiers: Market cap tier classification (4-tier framework)
            roe_persistence: ROE persistence analysis results
            strict_filters: Small cap strict quality filters results
        """
        # Create outputs directory if it doesn't exist
        output_dir = Path(__file__).parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d")

        # Prepare JSON output (4-tier framework)
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'holdings_count': len(holdings_quality),
            'watchlist_count': len(watchlist_quality),
            'holdings_quality': {
                ticker: {
                    'composite_score': result.composite_score,
                    'tier': result.tier.value,
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
                for ticker, result in holdings_quality.items()
            },
            'watchlist_quality': {
                ticker: {
                    'composite_score': result.composite_score,
                    'tier': result.tier.value,
                    'market_cap': result.market_cap,
                    'red_flags_count': len(result.red_flags)
                }
                for ticker, result in watchlist_quality.items()
            },
            'recommendations': recommendations,
            'market_cap_tiers': market_cap_tiers,  # NEW: 4-tier framework
            'roe_persistence': roe_persistence,    # NEW: 4-tier framework
            'strict_filters': strict_filters        # NEW: 4-tier framework
        }

        # Export JSON (fixed filename - no timestamp)
        json_file = output_dir / "quality_analysis.json"
        with open(json_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Exported JSON results to {json_file}")

        # Export summary text (fixed filename - no timestamp)
        summary_file = output_dir / "quality_analysis_summary.txt"
        with open(summary_file, 'w') as f:
            f.write("="*60 + "\n")
            f.write("QUALITY METRICS ANALYSIS SUMMARY\n")
            f.write("="*60 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Holdings Analyzed: {len(holdings_quality)}\n")
            f.write(f"Watchlist Analyzed: {len(watchlist_quality)}\n")
            f.write("="*60 + "\n\n")

            # Current Holdings
            f.write("CURRENT HOLDINGS QUALITY:\n")
            f.write("-"*60 + "\n")
            for ticker, result in sorted(holdings_quality.items(), key=lambda x: x[1].composite_score, reverse=True):
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

                f.write(f"{ticker}:\n")
                f.write(f"  Market Cap: {market_cap_str}\n")
                f.write(f"  Quality Score: {result.composite_score:.1f}/100\n")
                f.write(f"  Tier: {result.tier.value}\n")
                f.write(f"  Red Flags: {len(result.red_flags)}\n")
                if result.red_flags:
                    for rf in result.red_flags:
                        f.write(f"    - [{rf.severity}] {rf.description}\n")
                f.write("\n")

            # SELL Candidates
            f.write("\n" + "="*60 + "\n")
            f.write("SELL CANDIDATES (Quality <70):\n")
            f.write("-"*60 + "\n")
            if recommendations['sell_candidates']:
                for candidate in recommendations['sell_candidates']:
                    f.write(f"{candidate['ticker']}:\n")
                    f.write(f"  Quality Score: {candidate['quality_score']:.1f}\n")
                    f.write(f"  Reason: {candidate['reason']}\n")
                    f.write(f"  Red Flags: {candidate['red_flags']}\n")
                    f.write("\n")
            else:
                f.write("No sell candidates identified.\n\n")

            # BUY Alternatives
            f.write("\n" + "="*60 + "\n")
            f.write("BUY ALTERNATIVES (Top 10):\n")
            f.write("-"*60 + "\n")
            if recommendations['buy_alternatives']:
                for alternative in recommendations['buy_alternatives'][:10]:
                    f.write(f"{alternative['ticker']}:\n")
                    f.write(f"  Quality Score: {alternative['quality_score']:.1f}\n")
                    f.write(f"  Tier: {alternative['tier']}\n")
                    f.write(f"  Reason: {alternative['reason']}\n")
                    f.write("\n")
            else:
                f.write("No buy alternatives identified.\n\n")

            # Top Watchlist Overall
            f.write("\n" + "="*80 + "\n")
            f.write("TOP 20 WATCHLIST STOCKS BY QUALITY:\n")
            f.write("-"*80 + "\n")
            f.write(f"{'Ticker':<8} {'Market Cap':<12} {'Score':<8} {'Tier':<12} {'Red Flags':<10}\n")
            f.write("-"*80 + "\n")
            sorted_watchlist = sorted(
                watchlist_quality.items(),
                key=lambda x: x[1].composite_score,
                reverse=True
            )
            for ticker, result in sorted_watchlist[:20]:
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

                f.write(f"{ticker:<8} {market_cap_str:<12} {result.composite_score:5.1f}    {result.tier.value:<12} {len(result.red_flags):<10}\n")

        logger.info(f"Exported summary to {summary_file}")

        # Print summary to console
        print("\n" + "="*60)
        print("QUALITY METRICS ANALYSIS COMPLETE")
        print("="*60)
        print(f"Holdings analyzed: {len(holdings_quality)}")
        print(f"Watchlist analyzed: {len(watchlist_quality)}")
        print(f"SELL candidates: {len(recommendations['sell_candidates'])}")
        print(f"BUY alternatives: {len(recommendations['buy_alternatives'])}")
        print(f"\nResults saved to:")
        print(f"  - {json_file}")
        print(f"  - {summary_file}")
        print("="*60 + "\n")

    def run(self, watchlist_limit: int = 50):
        """
        Run complete quality analysis pipeline

        Args:
            watchlist_limit: Maximum number of watchlist tickers to analyze (default: 50)
        """
        logger.info("Starting quality analysis pipeline")

        # Load holdings
        holdings = self.load_portfolio_holdings()
        if not holdings:
            logger.error("No holdings to analyze. Exiting.")
            return

        # Get watchlist
        watchlist = self.get_watchlist_tickers(limit=watchlist_limit)
        if not watchlist:
            logger.error("No watchlist tickers available. Exiting.")
            return

        # Combine holdings + watchlist for fetching
        all_tickers = list(set(holdings + watchlist))
        logger.info(f"Total tickers to analyze: {len(all_tickers)}")

        # Fetch financial data
        financial_data = self.fetch_financial_data(all_tickers)

        # Calculate quality metrics
        quality_results = self.calculate_quality_metrics(financial_data)

        # Split results into holdings vs watchlist
        holdings_quality = {ticker: result for ticker, result in quality_results.items() if ticker in holdings}
        watchlist_quality = {ticker: result for ticker, result in quality_results.items() if ticker in watchlist}

        # Classify market cap tiers (4-tier framework integration)
        logger.info("Classifying market cap tiers...")
        market_cap_results = self.market_cap_classifier.batch_classify_tickers(list(quality_results.keys()))
        market_cap_tiers = {
            ticker: tier_data.tier.value
            for ticker, tier_data in market_cap_results.classifications.items()
        }
        logger.info(f"Classified {len(market_cap_tiers)} tickers into market cap tiers")

        # Analyze ROE persistence (4-tier framework integration)
        # NOTE: ROE persistence requires historical data. yfinance typically provides 3-4 years
        # which is sufficient for mid-cap (2-3 years) and small-cap (2 years) requirements.
        # Large-cap requirement (5+ years) may not always be met, but we handle this gracefully.
        logger.info("Analyzing ROE persistence...")
        roe_persistence = {}
        for ticker in quality_results.keys():
            try:
                # Fetch historical financials (yfinance provides 3-4 years typically)
                hist_data = self.fetcher.fetch_historical_financials(ticker)

                if hist_data is not None and len(hist_data) >= 2:
                    # Minimum 2 years required for small cap analysis
                    persistence_result = self.roe_analyzer.analyze_company(hist_data, ticker=ticker)

                    if persistence_result:
                        # Extract incremental ROCE from trend_analysis if available
                        incremental_roce = persistence_result.trend_analysis.get('incremental_roce_advantage', 0.0)

                        roe_persistence[ticker] = {
                            'years_analyzed': persistence_result.persistence_metrics.years_analyzed,
                            'roe_years_above_15pct': persistence_result.persistence_metrics.roe_years_above_15pct,
                            'roe_mean': persistence_result.persistence_metrics.roe_mean,
                            'incremental_roce_advantage': incremental_roce,
                            'classification': persistence_result.classification.value,
                            'compounder_confidence': persistence_result.compounder_confidence
                        }
                        logger.debug(f"ROE persistence for {ticker}: {persistence_result.classification.value} ({persistence_result.compounder_confidence:.1f}% confidence)")
                else:
                    logger.debug(f"Insufficient historical data for {ticker} (need 2+ years)")

            except Exception as e:
                logger.warning(f"Failed to analyze ROE persistence for {ticker}: {e}")
                continue

        logger.info(f"Analyzed ROE persistence for {len(roe_persistence)} tickers")

        # Analyze small cap strict filters (4-tier framework integration)
        logger.info("Analyzing small cap strict filters...")
        strict_filters = {}
        for ticker, tier in market_cap_tiers.items():
            if tier == "Small Cap":  # Only check small caps
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

        # Generate recommendations
        recommendations = self.identify_recommendations(holdings, holdings_quality, watchlist_quality)

        # Export results (including market cap tiers, ROE persistence, and strict filters)
        self.export_results(
            holdings_quality,
            watchlist_quality,
            recommendations,
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
