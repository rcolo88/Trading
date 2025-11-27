#!/usr/bin/env python3
"""
Valuation Analyzer - STEP 5: Valuation Analysis

Assesses whether stocks are reasonably valued given their quality scores.
Prevents overpaying even for high-quality companies.

Uses quality-adjusted P/E thresholds, PEG ratios, and FCF yields to determine
if a stock is CHEAP, FAIR, EXPENSIVE, or OVERVALUED.
"""

import json
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path

import yfinance as yf
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ValuationMetrics:
    """
    Raw valuation data for a stock

    Attributes:
        ticker: Stock ticker symbol
        price: Current stock price
        market_cap: Market capitalization
        pe_trailing: Trailing P/E ratio
        pe_forward: Forward P/E ratio
        peg_ratio: PEG ratio (P/E / growth rate)
        price_to_fcf: Price to Free Cash Flow ratio
        ev_to_ebitda: EV/EBITDA multiple
        fcf_yield: Free Cash Flow yield (FCF / market cap)
        revenue_growth: Year-over-year revenue growth
        earnings_growth: Year-over-year earnings growth
        sector: Company sector
        sector_median_pe: Median P/E for sector
        data_quality: COMPLETE, PARTIAL, or INSUFFICIENT
    """
    ticker: str
    price: float
    market_cap: float

    # Valuation multiples
    pe_trailing: Optional[float] = None
    pe_forward: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_fcf: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    fcf_yield: Optional[float] = None

    # Growth metrics
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None

    # Sector comparison
    sector: str = ""
    sector_median_pe: Optional[float] = None

    # Data quality
    data_quality: str = "INSUFFICIENT"


@dataclass
class ValuationRating:
    """
    Valuation rating and recommendation

    Attributes:
        ticker: Stock ticker symbol
        quality_score: Quality score (0-100)
        max_pe_allowed: Quality-adjusted maximum P/E threshold
        actual_pe: Actual trailing P/E ratio
        pe_rating: P/E rating (CHEAP, FAIR, EXPENSIVE, OVERVALUED)
        peg_rating: PEG rating (CHEAP, FAIR, EXPENSIVE)
        fcf_rating: FCF yield rating (EXCELLENT, GOOD, ACCEPTABLE, POOR)
        overall_rating: Overall valuation rating
        recommendation: BUY, HOLD, or AVOID
        reasoning: Explanation for the rating
    """
    ticker: str
    quality_score: float

    # Thresholds
    max_pe_allowed: float
    actual_pe: float

    # Ratings
    pe_rating: str
    peg_rating: str
    fcf_rating: str

    # Overall
    overall_rating: str
    recommendation: str
    reasoning: str


class ValuationAnalyzer:
    """
    Analyzes stock valuations with quality-adjusted thresholds

    Workflow:
    1. Fetch valuation metrics from yfinance
    2. Calculate quality-adjusted P/E threshold
    3. Rate P/E, PEG, and FCF yield
    4. Combine into overall valuation rating
    5. Generate BUY/HOLD/AVOID recommendation
    6. Export results to JSON and markdown

    Quality-Adjusted P/E Thresholds (from PM_README_V3.md):
    - Quality <7: Max 15x P/E (shouldn't own anyway)
    - Quality 7-8: Max 20x P/E
    - Quality 8-9: Max 30x P/E
    - Quality >9: Max 40x P/E (premium for exceptional quality)
    """

    def __init__(self):
        """Initialize valuation analyzer"""
        self.results = {}

    def fetch_valuation_metrics(self, ticker: str) -> ValuationMetrics:
        """
        Fetch valuation data using yfinance

        Args:
            ticker: Stock ticker symbol

        Returns:
            ValuationMetrics object
        """
        logger.info(f"Fetching valuation metrics for {ticker}...")

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Basic data
            price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            market_cap = info.get('marketCap', 0)

            # Valuation multiples
            pe_trailing = info.get('trailingPE')
            pe_forward = info.get('forwardPE')
            peg_ratio = info.get('pegRatio')
            ev_to_ebitda = info.get('enterpriseToEbitda')

            # Calculate FCF metrics
            fcf = info.get('freeCashflow', 0)
            fcf_yield = (fcf / market_cap * 100) if market_cap > 0 and fcf else None

            # Calculate Price/FCF
            shares = info.get('sharesOutstanding', 0)
            fcf_per_share = (fcf / shares) if shares > 0 and fcf else None
            price_to_fcf = (price / fcf_per_share) if fcf_per_share and fcf_per_share > 0 else None

            # Growth metrics
            revenue_growth = info.get('revenueGrowth')  # Quarterly YoY
            earnings_growth = info.get('earningsGrowth')  # Quarterly YoY

            # Sector
            sector = info.get('sector', 'Unknown')

            # Sector median P/E (would need external data, placeholder for now)
            sector_median_pe = None

            # Assess data quality
            data_quality = self._assess_data_quality(
                pe_trailing, peg_ratio, fcf_yield, revenue_growth
            )

            metrics = ValuationMetrics(
                ticker=ticker,
                price=price,
                market_cap=market_cap,
                pe_trailing=pe_trailing,
                pe_forward=pe_forward,
                peg_ratio=peg_ratio,
                price_to_fcf=price_to_fcf,
                ev_to_ebitda=ev_to_ebitda,
                fcf_yield=fcf_yield,
                revenue_growth=revenue_growth,
                earnings_growth=earnings_growth,
                sector=sector,
                sector_median_pe=sector_median_pe,
                data_quality=data_quality
            )

            logger.info(f"{ticker} - Price: ${price:.2f}, P/E: {pe_trailing}, Data: {data_quality}")
            return metrics

        except Exception as e:
            logger.error(f"Failed to fetch valuation metrics for {ticker}: {e}")
            return ValuationMetrics(
                ticker=ticker,
                price=0,
                market_cap=0,
                data_quality="INSUFFICIENT"
            )

    def _assess_data_quality(
        self,
        pe: Optional[float],
        peg: Optional[float],
        fcf_yield: Optional[float],
        revenue_growth: Optional[float]
    ) -> str:
        """
        Assess data quality based on availability of key metrics

        Args:
            pe: P/E ratio
            peg: PEG ratio
            fcf_yield: FCF yield
            revenue_growth: Revenue growth

        Returns:
            COMPLETE, PARTIAL, or INSUFFICIENT
        """
        available_count = sum([
            pe is not None,
            peg is not None,
            fcf_yield is not None,
            revenue_growth is not None
        ])

        if available_count >= 3:
            return "COMPLETE"
        elif available_count >= 2:
            return "PARTIAL"
        else:
            return "INSUFFICIENT"

    def calculate_quality_adjusted_threshold(self, quality_score: float) -> float:
        """
        Calculate maximum acceptable P/E based on quality score

        From PM_README_V3.md:
        - Quality score <7: Max 15x P/E (shouldn't own anyway)
        - Quality score 7-8: Max 20x P/E
        - Quality score 8-9: Max 30x P/E
        - Quality score >9: Max 40x P/E (premium for exceptional quality)

        Args:
            quality_score: Quality score (0-100 scale)

        Returns:
            Maximum P/E threshold
        """
        # Convert to 0-10 scale
        quality_10 = quality_score / 10.0

        if quality_10 < 7:
            return 15.0
        elif quality_10 < 8:
            return 20.0
        elif quality_10 < 9:
            return 30.0
        else:
            return 40.0

    def rate_pe_valuation(
        self,
        actual_pe: float,
        max_pe: float
    ) -> str:
        """
        Rate P/E valuation relative to quality-adjusted threshold

        Args:
            actual_pe: Actual trailing P/E ratio
            max_pe: Quality-adjusted maximum P/E threshold

        Returns:
            CHEAP, FAIR, EXPENSIVE, or OVERVALUED
        """
        if actual_pe <= 0:
            return "N/A (Negative Earnings)"

        ratio = actual_pe / max_pe

        if ratio < 0.7:
            return "CHEAP"
        elif ratio < 1.0:
            return "FAIR"
        elif ratio < 1.2:
            return "EXPENSIVE"
        else:
            return "OVERVALUED"

    def rate_peg_ratio(self, peg: Optional[float]) -> str:
        """
        Rate PEG ratio

        Args:
            peg: PEG ratio (P/E / growth rate)

        Returns:
            CHEAP, FAIR, EXPENSIVE, or N/A
        """
        if peg is None or peg <= 0:
            return "N/A"

        if peg < 1.0:
            return "CHEAP"
        elif peg <= 2.0:
            return "FAIR"
        else:
            return "EXPENSIVE"

    def rate_fcf_yield(self, fcf_yield: Optional[float]) -> str:
        """
        Rate FCF yield

        Args:
            fcf_yield: Free Cash Flow yield (%)

        Returns:
            EXCELLENT, GOOD, ACCEPTABLE, POOR, or N/A
        """
        if fcf_yield is None:
            return "N/A"

        if fcf_yield > 5.0:
            return "EXCELLENT"
        elif fcf_yield >= 3.0:
            return "GOOD"
        elif fcf_yield >= 1.0:
            return "ACCEPTABLE"
        else:
            return "POOR"

    def assess_valuation(
        self,
        ticker: str,
        quality_score: float,
        metrics: Optional[ValuationMetrics] = None
    ) -> ValuationRating:
        """
        Main method: Comprehensive valuation assessment

        Workflow:
        1. Calculate quality-adjusted P/E threshold
        2. Rate P/E (vs threshold)
        3. Rate PEG
        4. Rate FCF yield
        5. Combine into overall rating
        6. Generate recommendation

        Args:
            ticker: Stock ticker symbol
            quality_score: Quality score (0-100)
            metrics: Optional pre-fetched ValuationMetrics

        Returns:
            ValuationRating object
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Assessing valuation for {ticker} (Quality: {quality_score:.1f})")
        logger.info(f"{'='*60}")

        # Fetch metrics if not provided
        if metrics is None:
            metrics = self.fetch_valuation_metrics(ticker)

        # Check data quality
        if metrics.data_quality == "INSUFFICIENT":
            logger.warning(f"{ticker} - Insufficient data for valuation analysis")
            return self._create_insufficient_data_rating(ticker, quality_score)

        # Calculate threshold
        max_pe = self.calculate_quality_adjusted_threshold(quality_score)

        # Use trailing P/E, fallback to forward P/E
        actual_pe = metrics.pe_trailing if metrics.pe_trailing else metrics.pe_forward
        if actual_pe is None:
            actual_pe = 0.0

        # Rate individual metrics
        pe_rating = self.rate_pe_valuation(actual_pe, max_pe)
        peg_rating = self.rate_peg_ratio(metrics.peg_ratio)
        fcf_rating = self.rate_fcf_yield(metrics.fcf_yield)

        # Combine into overall rating
        overall_rating, recommendation, reasoning = self._combine_ratings(
            ticker, quality_score, max_pe, actual_pe,
            pe_rating, peg_rating, fcf_rating, metrics
        )

        rating = ValuationRating(
            ticker=ticker,
            quality_score=quality_score,
            max_pe_allowed=max_pe,
            actual_pe=actual_pe,
            pe_rating=pe_rating,
            peg_rating=peg_rating,
            fcf_rating=fcf_rating,
            overall_rating=overall_rating,
            recommendation=recommendation,
            reasoning=reasoning
        )

        logger.info(f"{ticker} - Overall: {overall_rating}, Recommendation: {recommendation}")
        return rating

    def _combine_ratings(
        self,
        ticker: str,
        quality_score: float,
        max_pe: float,
        actual_pe: float,
        pe_rating: str,
        peg_rating: str,
        fcf_rating: str,
        metrics: ValuationMetrics
    ) -> tuple:
        """
        Combine individual ratings into overall rating and recommendation

        Overall rating logic:
        - If P/E is OVERVALUED: overall = OVERVALUED (red flag)
        - If 2+ metrics are EXPENSIVE: overall = EXPENSIVE
        - If 2+ metrics are CHEAP: overall = CHEAP
        - Otherwise: overall = FAIR

        Recommendation logic:
        - OVERVALUED: AVOID (don't buy at any price)
        - EXPENSIVE: HOLD (wait for better entry)
        - FAIR: BUY if quality ≥80, otherwise HOLD
        - CHEAP: BUY (good value)

        Args:
            ticker, quality_score, max_pe, actual_pe: Basic info
            pe_rating, peg_rating, fcf_rating: Individual ratings
            metrics: ValuationMetrics object

        Returns:
            Tuple of (overall_rating, recommendation, reasoning)
        """
        # Count ratings
        expensive_count = sum([
            pe_rating in ["EXPENSIVE", "OVERVALUED"],
            peg_rating == "EXPENSIVE",
            fcf_rating in ["POOR", "ACCEPTABLE"]
        ])

        cheap_count = sum([
            pe_rating == "CHEAP",
            peg_rating == "CHEAP",
            fcf_rating in ["EXCELLENT", "GOOD"]
        ])

        # Determine overall rating
        if pe_rating == "OVERVALUED":
            overall_rating = "OVERVALUED"
        elif expensive_count >= 2:
            overall_rating = "EXPENSIVE"
        elif cheap_count >= 2:
            overall_rating = "CHEAP"
        else:
            overall_rating = "FAIR"

        # Determine recommendation
        if overall_rating == "OVERVALUED":
            recommendation = "AVOID"
        elif overall_rating == "EXPENSIVE":
            recommendation = "HOLD"
        elif overall_rating == "CHEAP":
            recommendation = "BUY"
        else:  # FAIR
            recommendation = "BUY" if quality_score >= 80 else "HOLD"

        # Generate reasoning
        reasoning = self._generate_reasoning(
            ticker, quality_score, max_pe, actual_pe,
            pe_rating, peg_rating, fcf_rating, metrics, overall_rating
        )

        return overall_rating, recommendation, reasoning

    def _generate_reasoning(
        self,
        ticker: str,
        quality_score: float,
        max_pe: float,
        actual_pe: float,
        pe_rating: str,
        peg_rating: str,
        fcf_rating: str,
        metrics: ValuationMetrics,
        overall_rating: str
    ) -> str:
        """Generate reasoning explanation for the rating"""
        parts = []

        # P/E analysis
        if actual_pe > 0:
            parts.append(f"P/E {actual_pe:.1f}x vs max {max_pe:.1f}x ({pe_rating})")
        else:
            parts.append("P/E not available or negative")

        # PEG analysis
        if metrics.peg_ratio:
            parts.append(f"PEG {metrics.peg_ratio:.2f} ({peg_rating})")

        # FCF analysis
        if metrics.fcf_yield:
            parts.append(f"FCF yield {metrics.fcf_yield:.1f}% ({fcf_rating})")

        # Quality context
        parts.append(f"Quality {quality_score:.1f}/100")

        return "; ".join(parts)

    def _create_insufficient_data_rating(
        self,
        ticker: str,
        quality_score: float
    ) -> ValuationRating:
        """Create rating for stocks with insufficient data"""
        max_pe = self.calculate_quality_adjusted_threshold(quality_score)

        return ValuationRating(
            ticker=ticker,
            quality_score=quality_score,
            max_pe_allowed=max_pe,
            actual_pe=0.0,
            pe_rating="N/A",
            peg_rating="N/A",
            fcf_rating="N/A",
            overall_rating="N/A",
            recommendation="HOLD",
            reasoning="Insufficient valuation data available"
        )

    def batch_analyze_portfolio(
        self,
        tickers: List[str],
        quality_scores: Dict[str, float]
    ) -> Dict[str, ValuationRating]:
        """
        Analyze valuation for multiple tickers

        Args:
            tickers: List of ticker symbols
            quality_scores: Dict mapping tickers to quality scores

        Returns:
            Dict mapping tickers to ValuationRating objects
        """
        results = {}

        for ticker in tickers:
            quality_score = quality_scores.get(ticker, 70.0)  # Default to 70 if not found
            rating = self.assess_valuation(ticker, quality_score)
            results[ticker] = rating

        logger.info(f"\nCompleted valuation analysis for {len(results)} tickers")
        return results

    def export_to_json(
        self,
        results: Dict[str, ValuationRating],
        date_str: Optional[str] = None
    ) -> str:
        """
        Export valuation analysis results to JSON

        Args:
            results: Dict of valuation ratings
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
        json_data = {ticker: asdict(rating) for ticker, rating in results.items()}

        # Export JSON
        json_path = outputs_dir / f"valuation_analysis_{date_str}.json"
        with open(json_path, 'w') as f:
            json.dump(json_data, f, indent=2)

        logger.info(f"Exported valuation analysis to {json_path}")
        return str(json_path)

    def generate_markdown_report(
        self,
        results: Dict[str, ValuationRating],
        date_str: Optional[str] = None
    ) -> str:
        """
        Generate markdown report for valuation analysis

        Args:
            results: Dict of valuation ratings
            date_str: Date string (YYYYMMDD), defaults to today

        Returns:
            Path to markdown report
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')

        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        report_path = outputs_dir / f"valuation_analysis_{date_str}.md"

        with open(report_path, 'w') as f:
            f.write("# VALUATION ANALYSIS REPORT\n\n")
            f.write(f"**Date**: {date_str}\n\n")
            f.write(f"**Holdings Analyzed**: {len(results)}\n\n")

            # Summary stats
            buy_count = sum(1 for r in results.values() if r.recommendation == "BUY")
            hold_count = sum(1 for r in results.values() if r.recommendation == "HOLD")
            avoid_count = sum(1 for r in results.values() if r.recommendation == "AVOID")

            cheap_count = sum(1 for r in results.values() if r.overall_rating == "CHEAP")
            fair_count = sum(1 for r in results.values() if r.overall_rating == "FAIR")
            expensive_count = sum(1 for r in results.values() if r.overall_rating == "EXPENSIVE")
            overvalued_count = sum(1 for r in results.values() if r.overall_rating == "OVERVALUED")

            f.write("## SUMMARY\n\n")
            f.write(f"**Recommendations**:\n")
            f.write(f"- BUY: {buy_count}\n")
            f.write(f"- HOLD: {hold_count}\n")
            f.write(f"- AVOID: {avoid_count}\n\n")

            f.write(f"**Valuation Ratings**:\n")
            f.write(f"- CHEAP: {cheap_count}\n")
            f.write(f"- FAIR: {fair_count}\n")
            f.write(f"- EXPENSIVE: {expensive_count}\n")
            f.write(f"- OVERVALUED: {overvalued_count}\n\n")

            # Detail table
            f.write("---\n\n")
            f.write("## DETAILED ANALYSIS\n\n")
            f.write("| Ticker | Quality | Max P/E | Actual P/E | P/E Rating | PEG Rating | FCF Rating | Overall | Rec |\n")
            f.write("|--------|---------|---------|-----------|------------|-----------|-----------|---------|-----|\n")

            for ticker, rating in sorted(results.items()):
                f.write(f"| {rating.ticker} | {rating.quality_score:.0f} | "
                       f"{rating.max_pe_allowed:.0f}x | {rating.actual_pe:.1f}x | "
                       f"{rating.pe_rating} | {rating.peg_rating} | {rating.fcf_rating} | "
                       f"**{rating.overall_rating}** | **{rating.recommendation}** |\n")

            # Detailed reasoning section
            f.write("\n---\n\n")
            f.write("## REASONING\n\n")

            for ticker, rating in sorted(results.items()):
                f.write(f"### {ticker} - {rating.overall_rating}\n\n")
                f.write(f"{rating.reasoning}\n\n")

        logger.info(f"Generated markdown report: {report_path}")
        return str(report_path)


def main():
    """
    Main entry point for standalone execution

    Usage:
        python valuation_analyzer.py
        python valuation_analyzer.py --tickers NVDA GOOGL AAPL
    """
    import argparse

    parser = argparse.ArgumentParser(description='Valuation Analysis (STEP 5)')
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

    # For demo, use placeholder quality scores
    # In production, would load from quality_analysis output
    quality_scores = {ticker: 75.0 for ticker in args.tickers}

    # Run analysis
    analyzer = ValuationAnalyzer()
    results = analyzer.batch_analyze_portfolio(args.tickers, quality_scores)

    # Export results
    if results:
        analyzer.export_to_json(results)
        analyzer.generate_markdown_report(results)

        # Print summary
        print("\n" + "="*60)
        print("VALUATION ANALYSIS COMPLETE")
        print("="*60)
        print(f"Analyzed: {len(results)} tickers\n")

        for ticker, rating in sorted(results.items()):
            status = "✅" if rating.recommendation == "BUY" else "⚠️" if rating.recommendation == "HOLD" else "❌"
            print(f"{status} {ticker:6s} - {rating.overall_rating:10s} - {rating.recommendation:4s} - P/E {rating.actual_pe:.1f}x (max {rating.max_pe_allowed:.0f}x)")


if __name__ == "__main__":
    main()
