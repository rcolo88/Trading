#!/usr/bin/env python3
"""
Competitive Analyzer - STEP 4: Competitive Landscape Analysis

Identifies 3-5 competitors for each holding, compares quality scores,
selects best-in-class, and generates KEEP/SWAP/EXIT recommendations.

This module helps answer: "Am I holding the best company in this space?"
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

import yfinance as yf

# Import quality metrics calculator
from quality_metrics_calculator import QualityMetricsCalculator, QualityAnalysisResult
from financial_data_fetcher import FinancialDataFetcher

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CompetitorComparison:
    """
    Comparison data for a single competitor

    Attributes:
        ticker: Stock ticker symbol
        company_name: Company name
        quality_score: Composite quality score (0-100)
        roe: Return on Equity
        gross_margin: Gross profit margin
        market_cap: Market capitalization
        rank: Competitive rank (1 = best)
    """
    ticker: str
    company_name: str
    quality_score: float
    roe: float
    gross_margin: float
    market_cap: float
    rank: int


@dataclass
class CompetitiveLandscape:
    """
    Complete competitive analysis for a ticker

    Attributes:
        focal_ticker: The ticker being analyzed
        competitors: List of competitor comparisons (sorted by rank)
        best_in_class: Ticker symbol of the winner
        competitive_advantage: Why focal_ticker wins (or doesn't)
        recommendation: KEEP, SWAP, or EXIT
        swap_candidate: If SWAP, which ticker to swap to
    """
    focal_ticker: str
    competitors: List[CompetitorComparison]
    best_in_class: str
    competitive_advantage: str
    recommendation: str
    swap_candidate: Optional[str] = None


class CompetitiveAnalyzer:
    """
    Analyzes competitive landscape for portfolio holdings

    Workflow:
    1. Identify 3-5 competitors for each ticker
    2. Calculate quality scores for all competitors
    3. Rank companies by quality
    4. Generate KEEP/SWAP/EXIT recommendations
    5. Export results to JSON and markdown

    Decision Logic:
    - KEEP: Focal ticker is #1 or #2 within 5 points of #1
    - SWAP: Focal ticker is #2+ and >5 points behind #1
    - EXIT: Focal ticker is last place with quality <70
    """

    # Manual competitor sets for common tickers
    COMPETITOR_SETS = {
        # Technology - AI Infrastructure
        "NVDA": ["AMD", "INTC", "GOOGL", "MSFT", "AMZN"],  # GPUs + Cloud AI
        "AMD": ["NVDA", "INTC", "QCOM", "AVGO"],  # Semiconductors
        "INTC": ["AMD", "NVDA", "QCOM", "TSM"],  # Semiconductors

        # Technology - Cloud/Platform
        "GOOGL": ["MSFT", "AMZN", "META", "AAPL"],  # Big Tech platforms
        "MSFT": ["GOOGL", "AMZN", "AAPL", "ORCL"],  # Cloud + Enterprise
        "AMZN": ["MSFT", "GOOGL", "AAPL", "WMT"],  # Cloud + Retail
        "META": ["GOOGL", "SNAP", "PINS", "TTD"],  # Social + Digital Ads

        # Technology - Semiconductors
        "TSM": ["INTC", "SSNLF", "UMC"],  # Foundries
        "AVGO": ["QCOM", "AMD", "NVDA", "MRVL"],  # Semiconductor design
        "QCOM": ["AVGO", "AMD", "MRVL"],  # Mobile chips

        # Healthcare
        "JNJ": ["PFE", "ABT", "MRK", "LLY"],  # Pharma giants
        "UNH": ["CVS", "CI", "HUM", "ELV"],  # Health insurance
        "ABBV": ["BMY", "GILD", "AMGN", "LLY"],  # Biotech/pharma

        # Financials
        "JPM": ["BAC", "WFC", "C", "GS"],  # Banks
        "V": ["MA", "AXP", "PYPL"],  # Payments
        "BRK.B": ["JPM", "BAC", "WFC"],  # Diversified financials

        # Consumer
        "AAPL": ["MSFT", "GOOGL", "AMZN", "META"],  # Consumer tech
        "TSLA": ["F", "GM", "RIVN", "LCID"],  # EVs
        "NKE": ["ADDYY", "LULU", "UAA"],  # Athletic apparel

        # Energy
        "XOM": ["CVX", "COP", "SLB", "BP"],  # Oil & gas
        "NEE": ["DUK", "SO", "D", "AEP"],  # Utilities

        # Industrials
        "BA": ["LMT", "NOC", "GD", "RTX"],  # Aerospace & defense
        "CAT": ["DE", "CMI", "ITW"],  # Industrial machinery
    }

    def __init__(self):
        """Initialize competitive analyzer"""
        self.quality_calculator = QualityMetricsCalculator()
        self.financial_fetcher = FinancialDataFetcher(enable_cache=True)
        self.results = {}

    def identify_competitors(self, ticker: str) -> List[str]:
        """
        Identify 3-5 direct competitors for a ticker

        Method:
        1. Check manual competitor sets first
        2. Fallback to sector-based identification
        3. Return 3-5 tickers (excluding focal ticker)

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of 3-5 competitor ticker symbols
        """
        # Check manual competitor sets
        if ticker in self.COMPETITOR_SETS:
            competitors = self.COMPETITOR_SETS[ticker]
            logger.info(f"{ticker} - Using manual competitor set: {competitors}")
            return competitors

        # Fallback: Sector-based identification
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            sector = info.get('sector', '')
            industry = info.get('industry', '')

            logger.info(f"{ticker} - No manual set, using sector: {sector}, industry: {industry}")

            # Simple fallback: Return empty list for now
            # In production, could query S&P 500 for same sector/industry
            logger.warning(f"{ticker} - Sector-based competitor identification not yet implemented")
            return []

        except Exception as e:
            logger.error(f"Failed to identify competitors for {ticker}: {e}")
            return []

    def compare_quality_metrics(
        self,
        tickers: List[str]
    ) -> List[CompetitorComparison]:
        """
        Fetch financial data and calculate quality scores for all competitors

        Args:
            tickers: List of ticker symbols to compare

        Returns:
            List of CompetitorComparison objects sorted by rank (1 = best)
        """
        comparisons = []

        for ticker in tickers:
            try:
                logger.info(f"Fetching quality data for {ticker}...")

                # Fetch financial data
                financial_data = self.financial_fetcher.fetch_ticker_data(ticker)

                if not financial_data or not financial_data.is_valid():
                    logger.warning(f"{ticker} - Invalid financial data, skipping")
                    continue

                # Calculate quality score
                quality_result = self.quality_calculator.calculate_quality_score(financial_data)

                # Get company info
                stock = yf.Ticker(ticker)
                info = stock.info
                company_name = info.get('longName', ticker)
                market_cap = info.get('marketCap', 0)

                # Create comparison object
                comparison = CompetitorComparison(
                    ticker=ticker,
                    company_name=company_name,
                    quality_score=quality_result.composite_score,
                    roe=financial_data.roe or 0.0,
                    gross_margin=financial_data.gross_margin or 0.0,
                    market_cap=market_cap,
                    rank=0  # Will be assigned after sorting
                )

                comparisons.append(comparison)

            except Exception as e:
                logger.error(f"Failed to compare {ticker}: {e}")
                continue

        # Sort by quality score (highest first)
        comparisons.sort(key=lambda x: x.quality_score, reverse=True)

        # Assign ranks
        for i, comp in enumerate(comparisons):
            comp.rank = i + 1

        logger.info(f"Compared {len(comparisons)} competitors")
        return comparisons

    def identify_best_in_class(
        self,
        comparisons: List[CompetitorComparison]
    ) -> str:
        """
        Select best-in-class competitor

        Winner = highest quality score
        If tie, use highest market cap (liquidity preference)

        Args:
            comparisons: List of competitor comparisons (sorted by rank)

        Returns:
            Ticker symbol of the winner
        """
        if not comparisons:
            return ""

        # Already sorted by quality score, so rank 1 is the winner
        best = comparisons[0]

        # Check for ties (within 0.5 points)
        ties = [c for c in comparisons if abs(c.quality_score - best.quality_score) < 0.5]

        if len(ties) > 1:
            # Break tie by market cap
            best = max(ties, key=lambda x: x.market_cap)
            logger.info(f"Tie broken by market cap: {best.ticker}")

        return best.ticker

    def generate_recommendation(
        self,
        focal_ticker: str,
        comparisons: List[CompetitorComparison]
    ) -> Tuple[str, Optional[str], str]:
        """
        Generate KEEP/SWAP/EXIT recommendation

        Decision Logic:
        - KEEP: Focal ticker is #1, OR #2 within 5 points of #1
        - SWAP: Focal ticker is #2+ and >5 points behind #1 (swap to #1)
        - EXIT: Focal ticker is last place AND quality <70

        Args:
            focal_ticker: The ticker being analyzed
            comparisons: List of competitor comparisons

        Returns:
            Tuple of (recommendation, swap_candidate, reasoning)
        """
        # Find focal ticker in comparisons
        focal = next((c for c in comparisons if c.ticker == focal_ticker), None)

        if not focal:
            return ("EXIT", None, "Ticker not found in comparison set")

        # Get best competitor
        best = comparisons[0]

        # Decision logic
        if focal.rank == 1:
            return ("KEEP", None, f"Best-in-class with quality score {focal.quality_score:.1f}")

        elif focal.rank == 2 and (focal.quality_score >= best.quality_score - 5):
            return ("KEEP", None, f"Strong #2 position, within 5 points of leader {best.ticker}")

        elif focal.quality_score < 70 and focal.rank == len(comparisons):
            return ("EXIT", None, f"Last place with quality {focal.quality_score:.1f} below STEPS threshold (70)")

        else:
            # SWAP to #1
            gap = best.quality_score - focal.quality_score
            return ("SWAP", best.ticker, f"Rank #{focal.rank}, {gap:.1f} points behind leader {best.ticker}")

    def analyze_competitive_position(
        self,
        ticker: str
    ) -> Optional[CompetitiveLandscape]:
        """
        Main method: Full competitive analysis for a single ticker

        Workflow:
        1. Identify competitors
        2. Compare quality metrics
        3. Identify best-in-class
        4. Generate recommendation

        Args:
            ticker: Stock ticker symbol to analyze

        Returns:
            CompetitiveLandscape object or None if failed
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Analyzing competitive position for {ticker}")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Identify competitors
            competitors = self.identify_competitors(ticker)

            if not competitors:
                logger.warning(f"{ticker} - No competitors identified")
                return None

            # Add focal ticker to comparison set
            all_tickers = [ticker] + [c for c in competitors if c != ticker]

            # Step 2: Compare quality metrics
            comparisons = self.compare_quality_metrics(all_tickers)

            if not comparisons:
                logger.warning(f"{ticker} - Failed to compare competitors")
                return None

            # Step 3: Identify best-in-class
            best_in_class = self.identify_best_in_class(comparisons)

            # Step 4: Generate recommendation
            recommendation, swap_candidate, advantage = self.generate_recommendation(
                ticker, comparisons
            )

            # Create result
            result = CompetitiveLandscape(
                focal_ticker=ticker,
                competitors=comparisons,
                best_in_class=best_in_class,
                competitive_advantage=advantage,
                recommendation=recommendation,
                swap_candidate=swap_candidate
            )

            logger.info(f"{ticker} - Recommendation: {recommendation}")
            if swap_candidate:
                logger.info(f"{ticker} - Swap candidate: {swap_candidate}")

            return result

        except Exception as e:
            logger.error(f"Failed to analyze {ticker}: {e}")
            return None

    def batch_analyze_portfolio(
        self,
        tickers: List[str]
    ) -> Dict[str, CompetitiveLandscape]:
        """
        Analyze competitive position for multiple tickers

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping tickers to CompetitiveLandscape objects
        """
        results = {}

        for ticker in tickers:
            landscape = self.analyze_competitive_position(ticker)
            if landscape:
                results[ticker] = landscape

        logger.info(f"\nCompleted competitive analysis for {len(results)}/{len(tickers)} tickers")
        return results

    def export_to_json(
        self,
        results: Dict[str, CompetitiveLandscape],
        date_str: Optional[str] = None
    ) -> str:
        """
        Export competitive analysis results to JSON

        Args:
            results: Dict of competitive landscapes
            date_str: Date string (YYYYMMDD), defaults to today

        Returns:
            Path to exported JSON file
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')

        # Create outputs directory
        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        # Convert to JSON-serializable format
        json_data = {}
        for ticker, landscape in results.items():
            json_data[ticker] = {
                'focal_ticker': landscape.focal_ticker,
                'best_in_class': landscape.best_in_class,
                'recommendation': landscape.recommendation,
                'swap_candidate': landscape.swap_candidate,
                'competitive_advantage': landscape.competitive_advantage,
                'competitors': [asdict(c) for c in landscape.competitors]
            }

        # Export JSON
        json_path = outputs_dir / f"competitive_analysis_{date_str}.json"
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)

        logger.info(f"Exported competitive analysis to {json_path}")
        return str(json_path)

    def generate_markdown_report(
        self,
        results: Dict[str, CompetitiveLandscape],
        date_str: Optional[str] = None
    ) -> str:
        """
        Generate markdown report for competitive analysis

        Args:
            results: Dict of competitive landscapes
            date_str: Date string (YYYYMMDD), defaults to today

        Returns:
            Path to markdown report
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')

        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        report_path = outputs_dir / f"competitive_analysis_{date_str}.md"

        with open(report_path, 'w') as f:
            f.write("# COMPETITIVE ANALYSIS REPORT\n\n")
            f.write(f"**Date**: {date_str}\n\n")
            f.write(f"**Holdings Analyzed**: {len(results)}\n\n")

            # Summary stats
            keep_count = sum(1 for r in results.values() if r.recommendation == "KEEP")
            swap_count = sum(1 for r in results.values() if r.recommendation == "SWAP")
            exit_count = sum(1 for r in results.values() if r.recommendation == "EXIT")

            f.write("## SUMMARY\n\n")
            f.write(f"- **KEEP**: {keep_count} holdings (best-in-class or strong #2)\n")
            f.write(f"- **SWAP**: {swap_count} holdings (upgrade opportunity available)\n")
            f.write(f"- **EXIT**: {exit_count} holdings (weak competitive position)\n\n")

            # Detail sections
            f.write("---\n\n")
            f.write("## DETAILED ANALYSIS\n\n")

            for ticker, landscape in sorted(results.items()):
                f.write(f"### {ticker} - {landscape.recommendation}\n\n")
                f.write(f"**Best-in-Class**: {landscape.best_in_class}\n\n")
                f.write(f"**Reasoning**: {landscape.competitive_advantage}\n\n")

                if landscape.swap_candidate:
                    f.write(f"**Swap To**: {landscape.swap_candidate}\n\n")

                # Competitor table
                f.write("**Competitive Ranking**:\n\n")
                f.write("| Rank | Ticker | Company | Quality Score | ROE | Gross Margin | Market Cap |\n")
                f.write("|------|--------|---------|--------------|-----|--------------|------------|\n")

                for comp in landscape.competitors:
                    market_cap_str = f"${comp.market_cap / 1e9:.1f}B" if comp.market_cap > 0 else "N/A"
                    highlight = "**" if comp.ticker == ticker else ""
                    f.write(f"| {comp.rank} | {highlight}{comp.ticker}{highlight} | "
                           f"{comp.company_name[:30]} | {comp.quality_score:.1f} | "
                           f"{comp.roe:.1%} | {comp.gross_margin:.1%} | {market_cap_str} |\n")

                f.write("\n---\n\n")

        logger.info(f"Generated markdown report: {report_path}")
        return str(report_path)


def main():
    """
    Main entry point for standalone execution

    Usage:
        python competitive_analyzer.py
        python competitive_analyzer.py --tickers NVDA GOOGL AAPL
    """
    import argparse

    parser = argparse.ArgumentParser(description='Competitive Analysis (STEP 4)')
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Tickers to analyze (defaults to portfolio holdings)'
    )

    args = parser.parse_args()

    # Load portfolio holdings if no tickers specified
    if not args.tickers:
        portfolio_path = Path(__file__).parent.parent / "portfolio_state.json"
        if portfolio_path.exists():
            with open(portfolio_path, 'r') as f:
                state = json.load(f)
            args.tickers = list(state.get('holdings', {}).keys())
            logger.info(f"Loaded {len(args.tickers)} holdings from portfolio")
        else:
            logger.error("No portfolio state found and no tickers specified")
            return

    # Run analysis
    analyzer = CompetitiveAnalyzer()
    results = analyzer.batch_analyze_portfolio(args.tickers)

    # Export results
    if results:
        analyzer.export_to_json(results)
        analyzer.generate_markdown_report(results)

        # Print summary
        print("\n" + "="*60)
        print("COMPETITIVE ANALYSIS COMPLETE")
        print("="*60)
        print(f"Analyzed: {len(results)} tickers\n")

        for ticker, landscape in sorted(results.items()):
            status = "✅" if landscape.recommendation == "KEEP" else "⚠️" if landscape.recommendation == "SWAP" else "❌"
            print(f"{status} {ticker:6s} - {landscape.recommendation:4s} - {landscape.competitive_advantage}")


if __name__ == "__main__":
    main()
