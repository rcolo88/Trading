#!/usr/bin/env python3
"""
Thematic Analysis Script
Standalone script to score holdings/candidates on thematic fit (opportunistic 20% allocation)

Outputs:
- outputs/thematic_analysis_YYYYMMDD.json: Complete thematic scoring results
- outputs/thematic_analysis_YYYYMMDD_summary.txt: Human-readable summary
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from thematic_prompt_builder import ThematicPromptBuilder, ThematicScore
from financial_data_fetcher import FinancialDataFetcher, FinancialData
import yfinance as yf

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ThematicAnalysisScript:
    """
    Standalone thematic analysis pipeline

    Workflow:
    1. Identify theme for each ticker (keyword matching)
    2. Score ticker on identified theme (heuristic or LLM)
    3. Export results to JSON and summary

    Themes:
    - AI Infrastructure
    - Nuclear Renaissance
    - Defense Modernization
    - Climate Technology
    - Longevity/Biotech
    - Generic (fallback)
    """

    # Theme keyword mappings
    THEME_KEYWORDS = {
        "AI Infrastructure": [
            "artificial intelligence", "AI", "data center", "cloud", "GPU",
            "accelerator", "networking", "power infrastructure", "cooling",
            "semiconductor", "chip", "nvidia", "compute", "inference"
        ],
        "Nuclear Renaissance": [
            "nuclear", "SMR", "small modular reactor", "uranium", "reactor",
            "nuclear power", "enrichment", "nuclear energy", "nuclear fuel"
        ],
        "Defense Modernization": [
            "defense", "military", "drone", "UAV", "cyber security", "cybersecurity",
            "space", "satellite", "hypersonic", "missile", "aerospace defense",
            "defense contractor", "weapons", "autonomous systems"
        ],
        "Climate Technology": [
            "climate", "carbon capture", "renewable", "solar", "wind",
            "energy storage", "battery", "electric vehicle", "EV",
            "emissions reduction", "sustainability", "green energy", "hydrogen"
        ],
        "Longevity/Biotech": [
            "GLP-1", "ozempic", "wegovy", "longevity", "aging", "biotech",
            "biopharmaceutical", "medical device", "drug development",
            "therapeutic", "clinical trial", "FDA approval"
        ]
    }

    def __init__(self, model_type: str = '7B'):
        """
        Initialize thematic analysis script

        Args:
            model_type: Model size for prompt generation (7B, 13B, 70B)
        """
        self.prompt_builder = ThematicPromptBuilder(model_type=model_type)
        self.financial_fetcher = FinancialDataFetcher(enable_cache=True)
        self.results = {}

    def load_portfolio_holdings(self) -> List[str]:
        """
        Load current portfolio holdings from portfolio_state.json

        Returns:
            List of ticker symbols in portfolio
        """
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

    def identify_theme_for_ticker(
        self,
        ticker: str,
        company_info: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Determine which theme (if any) applies to this ticker

        Uses keyword matching on business description and company name.

        Args:
            ticker: Stock ticker symbol
            company_info: Optional company information dict with 'description', 'name'

        Returns:
            Theme name or None if no match
        """
        # Fetch company info if not provided
        if company_info is None:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                company_info = {
                    'description': info.get('longBusinessSummary', ''),
                    'name': info.get('longName', ''),
                    'sector': info.get('sector', ''),
                    'industry': info.get('industry', '')
                }
            except Exception as e:
                logger.warning(f"Failed to fetch info for {ticker}: {e}")
                return None

        # Combine all text for matching
        search_text = " ".join([
            company_info.get('description', ''),
            company_info.get('name', ''),
            company_info.get('sector', ''),
            company_info.get('industry', '')
        ]).lower()

        if not search_text.strip():
            logger.warning(f"No text available for {ticker} theme identification")
            return None

        # Score each theme by keyword matches
        theme_scores = {}
        for theme, keywords in self.THEME_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in search_text)
            theme_scores[theme] = score

        # Return best matching theme (minimum 2 keyword matches)
        best_theme = max(theme_scores, key=theme_scores.get)
        best_score = theme_scores[best_theme]

        if best_score >= 2:
            logger.info(f"{ticker} identified as '{best_theme}' (score: {best_score})")
            return best_theme
        else:
            logger.info(f"{ticker} does not match any theme clearly (best: {best_theme} with {best_score} matches)")
            return None

    def score_ticker_on_theme_heuristic(
        self,
        ticker: str,
        theme: str,
        company_data: Dict
    ) -> Dict[str, any]:
        """
        Heuristic-based thematic scoring (fast, no LLM required)

        Uses simple heuristics based on keyword density, market cap,
        revenue growth, and other basic metrics.

        Args:
            ticker: Stock ticker
            theme: Identified theme
            company_data: Company financial and info data

        Returns:
            Scoring result dict with score, dimensions, classification
        """
        # Extract basic metrics
        description = company_data.get('description', '')
        market_cap = company_data.get('market_cap', 0)
        revenue_growth = company_data.get('revenue_growth', 0)

        # Count keyword matches for theme alignment
        keywords = self.THEME_KEYWORDS.get(theme, [])
        keyword_matches = sum(1 for kw in keywords if kw.lower() in description.lower())

        # Dimension scoring (1-10 scale, conservative)
        # Dimension 1: Theme Alignment (keyword density)
        theme_alignment = min(10, max(1, keyword_matches))

        # Dimension 2: Market Timing (based on market cap and growth)
        if market_cap > 100e9:  # Large cap
            market_timing = 7  # Established player
        elif market_cap > 10e9:  # Mid cap
            market_timing = 8  # Growth stage
        else:  # Small cap
            market_timing = 6  # Early stage risk

        # Adjust for revenue growth
        if revenue_growth > 0.3:  # >30% growth
            market_timing = min(10, market_timing + 2)
        elif revenue_growth < 0:  # Declining
            market_timing = max(1, market_timing - 2)

        # Dimension 3: Competitive Position (conservative default)
        competitive_position = 6

        # Dimension 4: Financial Strength (based on basic metrics)
        financial_strength = 6
        if company_data.get('gross_margin', 0) > 0.5:
            financial_strength += 1
        if company_data.get('fcf_margin', 0) > 0.1:
            financial_strength += 1
        financial_strength = min(10, financial_strength)

        # Dimension 5: Execution Capability (conservative default)
        execution_capability = 6

        # Calculate overall score (out of 50)
        dimension_scores = {
            "theme_alignment": theme_alignment,
            "market_timing": market_timing,
            "competitive_position": competitive_position,
            "financial_strength": financial_strength,
            "execution_capability": execution_capability
        }
        overall_score = sum(dimension_scores.values())

        # Classification
        if overall_score >= 40:
            classification = "Leader"
            position_range = "5-7%"
        elif overall_score >= 30:
            classification = "Strong Contender"
            position_range = "3-5%"
        elif overall_score >= 28:
            classification = "Contender"
            position_range = "2-3%"
        else:
            classification = "Laggard"
            position_range = "0% (EXIT)"

        # Investment stance
        if overall_score >= 35:
            investment_stance = "BUY"
        elif overall_score >= 28:
            investment_stance = "HOLD"
        else:
            investment_stance = "AVOID"

        return {
            "ticker": ticker,
            "theme": theme,
            "score": overall_score,
            "dimensions": dimension_scores,
            "classification": classification,
            "position_size_range": position_range,
            "investment_stance": investment_stance,
            "method": "heuristic",
            "confidence": 0.6  # Lower confidence for heuristic
        }

    def score_ticker_on_theme(
        self,
        ticker: str,
        theme: str,
        company_data: Dict,
        use_llm: bool = False
    ) -> Optional[Dict]:
        """
        Score ticker on theme (0-50 scale with 5 dimensions)

        Args:
            ticker: Stock ticker symbol
            theme: Theme name
            company_data: Company financial and info data
            use_llm: If True, use LLM (requires external API), else heuristic

        Returns:
            Scoring result dict or None if failed
        """
        if use_llm:
            # LLM-based scoring (requires external integration)
            logger.warning(f"LLM scoring not yet implemented, falling back to heuristic for {ticker}")
            return self.score_ticker_on_theme_heuristic(ticker, theme, company_data)
        else:
            # Heuristic-based scoring
            return self.score_ticker_on_theme_heuristic(ticker, theme, company_data)

    def analyze_opportunistic_holdings(
        self,
        tickers: Optional[List[str]] = None,
        use_llm: bool = False
    ) -> Dict[str, Dict]:
        """
        Main method: Score holdings/candidates on thematic fit

        Args:
            tickers: List of tickers to analyze (defaults to portfolio holdings)
            use_llm: Whether to use LLM for scoring (False = heuristic)

        Returns:
            Dict mapping tickers to thematic scoring results
        """
        # Load tickers if not provided
        if tickers is None:
            tickers = self.load_portfolio_holdings()

        if not tickers:
            logger.warning("No tickers to analyze")
            return {}

        logger.info(f"Analyzing {len(tickers)} tickers for thematic fit...")

        results = {}

        for ticker in tickers:
            logger.info(f"\nAnalyzing {ticker}...")

            try:
                # Fetch company data
                stock = yf.Ticker(ticker)
                info = stock.info

                company_data = {
                    'description': info.get('longBusinessSummary', ''),
                    'name': info.get('longName', ''),
                    'sector': info.get('sector', ''),
                    'industry': info.get('industry', ''),
                    'market_cap': info.get('marketCap', 0),
                    'revenue_growth': info.get('revenueGrowth', 0),
                    'gross_margin': info.get('grossMargins', 0),
                    'fcf_margin': info.get('freeCashflow', 0) / info.get('totalRevenue', 1) if info.get('totalRevenue', 0) > 0 else 0
                }

                # Identify theme
                theme = self.identify_theme_for_ticker(ticker, company_data)

                if theme is None:
                    logger.info(f"{ticker} - No clear theme identified, skipping")
                    continue

                # Score on identified theme
                score_result = self.score_ticker_on_theme(
                    ticker, theme, company_data, use_llm=use_llm
                )

                if score_result:
                    results[ticker] = score_result
                    logger.info(
                        f"{ticker} - Theme: {theme}, Score: {score_result['score']}/50, "
                        f"Classification: {score_result['classification']}"
                    )

            except Exception as e:
                logger.error(f"Failed to analyze {ticker}: {e}")
                continue

        logger.info(f"\nCompleted thematic analysis for {len(results)}/{len(tickers)} tickers")

        self.results = results
        return results

    def export_results(
        self,
        results: Dict[str, Dict],
        date_str: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Export results to JSON and summary text files

        Args:
            results: Thematic analysis results
            date_str: Date string (YYYYMMDD), defaults to today

        Returns:
            Tuple of (json_path, summary_path)
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y%m%d')

        # Create outputs directory if needed
        outputs_dir = Path(__file__).parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        # Export JSON
        json_path = outputs_dir / f"thematic_analysis_{date_str}.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Exported JSON results to {json_path}")

        # Export summary
        summary_path = outputs_dir / f"thematic_analysis_{date_str}_summary.txt"
        with open(summary_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"THEMATIC ANALYSIS SUMMARY - {date_str}\n")
            f.write("=" * 80 + "\n\n")

            if not results:
                f.write("No thematic holdings identified.\n")
            else:
                # Group by classification
                leaders = {k: v for k, v in results.items() if v['classification'] == 'Leader'}
                contenders = {k: v for k, v in results.items() if v['classification'] in ['Strong Contender', 'Contender']}
                laggards = {k: v for k, v in results.items() if v['classification'] == 'Laggard'}

                # Summary stats
                f.write(f"Total Analyzed: {len(results)}\n")
                f.write(f"Leaders (40-50): {len(leaders)}\n")
                f.write(f"Contenders (28-39): {len(contenders)}\n")
                f.write(f"Laggards (<28): {len(laggards)}\n\n")

                # Leaders section
                if leaders:
                    f.write("-" * 80 + "\n")
                    f.write("LEADERS (Score 40-50) - BUY Candidates\n")
                    f.write("-" * 80 + "\n\n")
                    for ticker, data in sorted(leaders.items(), key=lambda x: x[1]['score'], reverse=True):
                        f.write(f"{ticker} - {data['theme']}\n")
                        f.write(f"  Score: {data['score']}/50\n")
                        f.write(f"  Position Size: {data['position_size_range']}\n")
                        f.write(f"  Dimensions: {data['dimensions']}\n")
                        f.write(f"  Stance: {data['investment_stance']}\n\n")

                # Contenders section
                if contenders:
                    f.write("-" * 80 + "\n")
                    f.write("CONTENDERS (Score 28-39) - HOLD/Consider\n")
                    f.write("-" * 80 + "\n\n")
                    for ticker, data in sorted(contenders.items(), key=lambda x: x[1]['score'], reverse=True):
                        f.write(f"{ticker} - {data['theme']}\n")
                        f.write(f"  Score: {data['score']}/50\n")
                        f.write(f"  Position Size: {data['position_size_range']}\n")
                        f.write(f"  Classification: {data['classification']}\n")
                        f.write(f"  Stance: {data['investment_stance']}\n\n")

                # Laggards section
                if laggards:
                    f.write("-" * 80 + "\n")
                    f.write("LAGGARDS (Score <28) - AVOID/SELL\n")
                    f.write("-" * 80 + "\n\n")
                    for ticker, data in sorted(laggards.items(), key=lambda x: x[1]['score'], reverse=True):
                        f.write(f"{ticker} - {data['theme']}\n")
                        f.write(f"  Score: {data['score']}/50\n")
                        f.write(f"  Stance: {data['investment_stance']}\n\n")

        logger.info(f"Exported summary to {summary_path}")

        return str(json_path), str(summary_path)

    def run(
        self,
        tickers: Optional[List[str]] = None,
        use_llm: bool = False,
        export: bool = True
    ) -> Dict[str, Dict]:
        """
        Run complete thematic analysis workflow

        Args:
            tickers: Tickers to analyze (defaults to portfolio holdings)
            use_llm: Whether to use LLM for scoring
            export: Whether to export results to files

        Returns:
            Thematic analysis results dict
        """
        # Run analysis
        results = self.analyze_opportunistic_holdings(tickers=tickers, use_llm=use_llm)

        # Export if requested
        if export and results:
            self.export_results(results)

        return results


def main():
    """
    Main entry point for standalone execution

    Usage:
        python thematic_analysis_script.py
        python thematic_analysis_script.py --tickers NVDA IONQ PLTR
    """
    import argparse

    parser = argparse.ArgumentParser(description='Thematic Analysis Script')
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Tickers to analyze (defaults to portfolio holdings)'
    )
    parser.add_argument(
        '--use-llm',
        action='store_true',
        help='Use LLM for scoring (slower, requires API)'
    )
    parser.add_argument(
        '--no-export',
        action='store_true',
        help='Skip exporting results to files'
    )

    args = parser.parse_args()

    # Run analysis
    script = ThematicAnalysisScript()
    results = script.run(
        tickers=args.tickers,
        use_llm=args.use_llm,
        export=not args.no_export
    )

    # Print summary
    print("\n" + "=" * 80)
    print("THEMATIC ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Analyzed: {len(results)} tickers")

    if results:
        for ticker, data in sorted(results.items(), key=lambda x: x[1]['score'], reverse=True):
            print(f"{ticker:6s} - {data['theme']:25s} - Score: {data['score']:2d}/50 - {data['classification']}")


if __name__ == "__main__":
    main()
