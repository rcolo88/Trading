#!/usr/bin/env python3
"""
Individual Stock Analysis
Provides detailed quality analysis for a single stock ticker

This module analyzes individual stocks with comprehensive quality metrics,
historical analysis, and investment recommendations.

Output:
    - outputs/stock_analysis_{TICKER}_{DATE}.txt: Detailed individual analysis

Author: Quality Scoring System
Date: 2025
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from data.financial_data_fetcher import FinancialDataFetcher, FinancialData
from data.enhanced_hybrid_fetcher import EnhancedHybridDataFetcher
from quality.quality_metrics_calculator import QualityMetricsCalculator, QualityAnalysisResult
from quality.lookback_calculator import LookbackCalculator, DEFAULT_LOOKBACKS, QUALITY_DIMENSIONS, SECTOR_ADJUSTMENTS
from quality.market_cap_classifier import MarketCapClassifier
from components.quality_persistence_analyzer import QualityPersistenceAnalyzer

# Setup logging - only show errors (progress bar handled by tqdm, warnings logged to file)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class IndividualStockAnalysis:
    """
    Comprehensive individual stock quality analysis

    Workflow:
    1. Fetch financial data for ticker
    2. Calculate quality metrics (5-metric framework)
    3. Classify market cap tier
    4. Analyze ROE persistence (if historical data available)
    5. Generate detailed report with investment recommendation
    """

    def __init__(self, ticker: str, use_enhanced: bool = True):
        """
        Initialize individual stock analysis

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            use_enhanced: Whether to use EnhancedHybridDataFetcher with FMP + SimFin (default True)
        """
        self.ticker = ticker.upper()
        self.use_enhanced = use_enhanced

        # Initialize enhanced hybrid data fetcher with FMP + SimFin support
        if use_enhanced:
            fmp_api_key = os.getenv('FMP_API_KEY', '2t0zX99cGTRZpm3NOBy0gKYZBNpVr247')
            simfin_api_key = '9916893d-f20d-45b7-b4ac-4449607d5128'
            self.fetcher = EnhancedHybridDataFetcher(
                fmp_api_key=fmp_api_key,
                simfin_api_key=simfin_api_key,
                enable_simfin=True
            )
            self.yf_fetcher = self.fetcher.yf_fetcher
            logger.info(f"Using EnhancedHybridDataFetcher (yfinance + FMP + SimFin)")
        else:
            self.fetcher = FinancialDataFetcher(enable_cache=True)
            self.yf_fetcher = self.fetcher
            logger.info(f"Using FinancialDataFetcher (yfinance only)")

        self.quality_calculator = QualityMetricsCalculator()
        self.market_cap_classifier = MarketCapClassifier()
        self.roe_analyzer = QualityPersistenceAnalyzer()

        # Results storage
        self.financial_data: Optional[Dict] = None  # Changed from FinancialData to Dict for hybrid
        self.quality_result: Optional[QualityAnalysisResult] = None
        self.market_cap_tier: Optional[str] = None
        self.roe_persistence: Optional[Dict] = None

    def fetch_data(self) -> bool:
        """
        Fetch financial data for the ticker

        Returns:
            True if data fetched successfully, False otherwise
        """
        logger.info(f"Fetching financial data for {self.ticker}")

        if self.use_enhanced:
            # Use EnhancedHybridDataFetcher (returns Dict with FMP + SimFin)
            try:
                self.financial_data = self.fetcher.fetch_complete_data(
                    ticker=self.ticker,
                    include_fmp=True,
                    include_simfin=True,
                    force_refresh_fmp=False
                )
            except AttributeError as e:
                logger.error(f"EnhancedHybridDataFetcher method not available: {e}")
                # Fallback to yfinance only
                financial_obj = self.yf_fetcher.fetch_financial_data(self.ticker)
                if financial_obj and hasattr(financial_obj, 'to_dict'):
                    self.financial_data = financial_obj.to_dict()
                else:
                    self.financial_data = None
        else:
            # Use yfinance-only fetcher (returns FinancialData object)
            financial_obj = self.fetcher.fetch_financial_data(self.ticker)
            if financial_obj and hasattr(financial_obj, 'to_dict'):
                self.financial_data = financial_obj.to_dict()
            else:
                self.financial_data = None

        if not self.financial_data:
            logger.error(f"Failed to fetch financial data for {self.ticker}")
            return False

        # Check data quality
        data_quality = self.financial_data.get('data_quality', 'unknown')
        if data_quality == "insufficient":
            logger.warning(f"Insufficient financial data for {self.ticker}")
            return False

        logger.info(f"Successfully fetched {data_quality} quality data for {self.ticker}")
        if self.use_enhanced:
            fmp_years = self.financial_data.get('fmp_years_fetched', 0)
            simfin_years = self.financial_data.get('simfin_years_available', 0)
            data_sources = self.financial_data.get('data_sources', [])
            if 'SimFin' in data_sources:
                logger.info(f"SimFin historical data: {simfin_years} years")
            elif fmp_years > 0:
                logger.info(f"FMP historical data: {fmp_years} years")
        return True

    def calculate_quality_metrics(self) -> bool:
        """
        Calculate quality metrics using the NEW_5FACTOR framework

        Returns:
            True if calculation successful, False otherwise
        """
        if not self.financial_data:
            return False

        logger.info(f"Calculating quality metrics for {self.ticker}")

        try:
            # financial_data is now a Dict (from HybridDataFetcher or converted FinancialData)
            # Pass it directly to calculator (which expects Dict)
            calculator_input = {
                'ticker': self.ticker,
            }
            
            # Safely unpack financial_data fields, handling None values
            if self.financial_data:
                for key, value in self.financial_data.items():
                    calculator_input[key] = value

            # Use NEW_5FACTOR framework for comprehensive multi-dimensional scoring
            self.quality_result = self.quality_calculator.calculate_quality_metrics(
                calculator_input,
                framework='NEW_5FACTOR'
            )

            if self.quality_result and self.quality_result.composite_score is not None:
                logger.info(f"Calculated quality metrics for {self.ticker}: score {self.quality_result.composite_score:.1f}")
            else:
                logger.warning(f"Could not calculate quality metrics for {self.ticker}")
            return True

        except Exception as e:
            logger.error(f"Failed to calculate quality metrics for {self.ticker}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            return False

    def classify_market_cap(self) -> bool:
        """
        Classify stock into market cap tier

        Returns:
            True if classification successful, False otherwise
        """
        if not self.financial_data or not self.financial_data.get('market_cap'):
            logger.warning(f"No market cap data available for {self.ticker}")
            self.market_cap_tier = "Unknown"
            return True

        try:
            # Create single-item batch for classification
            batch_result = self.market_cap_classifier.batch_classify_tickers([self.ticker])

            if self.ticker in batch_result.classifications:
                classification = batch_result.classifications[self.ticker]
                self.market_cap_tier = classification.tier.value if classification.tier else "Unknown"
                logger.info(f"Market cap tier for {self.ticker}: {self.market_cap_tier}")
                return True
            else:
                logger.warning(f"Market cap classification failed for {self.ticker}")
                self.market_cap_tier = "Unknown"
                return True

        except Exception as e:
            logger.error(f"Failed to classify market cap for {self.ticker}: {e}")
            self.market_cap_tier = "Unknown"
            return True

    def analyze_roe_persistence(self) -> bool:
        """
        Analyze ROE persistence using historical data

        Returns:
            True if analysis completed (may be None if insufficient data)
        """
        try:
            logger.info(f"Analyzing ROE persistence for {self.ticker}")

            # Check for ROE history from FMP first, then SimFin
            roe_history = self.financial_data.get('roe_history', [])

            # If no ROE history from FMP, try SimFin historical data
            if not roe_history and self.use_enhanced:
                simfin_historical = self.financial_data.get('simfin_historical', {})
                if simfin_historical:
                    roe_history = self._extract_simfin_roe(simfin_historical)

            # If still no ROE history, calculate from yfinance historical data
            if not roe_history:
                historical_data = self.yf_fetcher.fetch_historical_financials(self.ticker, years=10)
                if historical_data is not None and len(historical_data) >= 2:
                    # Calculate ROE from net_income / shareholder_equity
                    roe_history = []
                    for _, row in historical_data.iterrows():
                        equity = row.get('shareholder_equity', 0)
                        net_income = row.get('net_income', 0)
                        if equity and equity > 0 and net_income:
                            roe_history.append(net_income / equity)

            if len(roe_history) >= 3:
                persistence_result = self.roe_analyzer.analyze_roe_history(roe_history, ticker=self.ticker)
            else:
                logger.info(f"Insufficient historical ROE data for {self.ticker}")
                self.roe_persistence = None
                return True

            if persistence_result:
                incremental_roce = persistence_result.trend_analysis.get('incremental_roce_advantage', 0.0) if persistence_result.trend_analysis else 0.0

                self.roe_persistence = {
                    'years_analyzed': persistence_result.persistence_metrics.years_analyzed,
                    'roe_years_above_15pct': persistence_result.persistence_metrics.roe_years_above_15pct,
                    'roe_mean': persistence_result.persistence_metrics.roe_mean,
                    'incremental_roce_advantage': incremental_roce,
                    'classification': persistence_result.classification.value,
                    'compounder_confidence': persistence_result.compounder_confidence
                }

                logger.info(f"ROE persistence analysis complete for {self.ticker}: {persistence_result.classification.value}")
            else:
                self.roe_persistence = None
                logger.info(f"No ROE persistence result for {self.ticker}")

            return True

        except Exception as e:
            logger.error(f"Failed to analyze ROE persistence for {self.ticker}: {e}")
            self.roe_persistence = None
            return True

    def _extract_simfin_roe(self, simfin_data: Dict) -> list:
        """
        Extract ROE history from SimFin historical data

        Args:
            simfin_data: SimFin historical data dict with 'balance' and 'income' keys

        Returns:
            List of ROE values (net_income / shareholder_equity)
        """
        roe_history = []
        balance_data = simfin_data.get('balance', [])
        income_data = simfin_data.get('income', [])

        # Create a lookup for net income by fiscal year
        net_income_by_year = {}
        for year_data in income_data:
            fiscal_year = year_data.get('fiscal_year')
            net_income = year_data.get('net_income')
            if fiscal_year and net_income is not None:
                net_income_by_year[fiscal_year] = net_income

        # Calculate ROE for each year
        for year_data in balance_data:
            equity = year_data.get('shareholder_equity', 0)
            fiscal_year = year_data.get('fiscal_year')
            net_income = net_income_by_year.get(fiscal_year, 0) if fiscal_year else 0

            if equity and equity > 0 and net_income:
                roe_history.append(net_income / equity)

        return roe_history

    def generate_investment_recommendation(self) -> str:
        """
        Generate investment recommendation based on quality analysis

        Returns:
            Recommendation string
        """
        if not self.quality_result:
            return "Unable to generate recommendation - no quality data"

        score = self.quality_result.composite_score
        tier = self.quality_result.tier.value
        red_flags = len(self.quality_result.red_flags)

        # Base recommendation on quality score
        if score >= 85:
            base_rec = "STRONG BUY - Elite quality stock"
        elif score >= 70:
            base_rec = "BUY - Strong quality fundamentals"
        elif score >= 50:
            base_rec = "HOLD - Moderate quality, monitor closely"
        else:
            base_rec = "SELL/AVOID - Weak quality fundamentals"

        # Adjust for red flags
        if red_flags > 2:
            base_rec += f" (⚠️  {red_flags} red flags detected - exercise caution)"
        elif red_flags > 0:
            base_rec += f" ({red_flags} red flag(s) noted)"

        # Add persistence insight if available
        if self.roe_persistence:
            persistence_class = self.roe_persistence.get('classification', '')
            confidence = self.roe_persistence.get('compounder_confidence', 0)

            if persistence_class == 'Quality Compounder':
                base_rec += f" | ROE Persistence: Quality Compounder ({confidence:.1f}% confidence)"
            elif persistence_class == 'Quality Improver':
                base_rec += f" | ROE Persistence: Improving trends"
            elif persistence_class == 'Inconsistent':
                base_rec += " | ROE Persistence: Inconsistent performance"

        return base_rec

    def generate_report(self) -> str:
        """
        Generate comprehensive individual stock analysis report

        Returns:
            Formatted report string
        """
        if not self.financial_data or not self.quality_result:
            return f"Unable to generate report for {self.ticker} - insufficient data"

        report = []
        report.append("="*80)
        report.append(f"INDIVIDUAL STOCK QUALITY ANALYSIS: {self.ticker}")
        report.append("="*80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Company Overview
        report.append("🏢 COMPANY OVERVIEW")
        report.append("-"*40)
        report.append(f"Ticker: {self.ticker}")
        if self.financial_data.get('sector'):
            report.append(f"Sector: {self.financial_data.get('sector')}")
        if self.financial_data.get('industry'):
            report.append(f"Industry: {self.financial_data.get('industry')}")
        if self.financial_data.get('market_cap'):
            market_cap = self.financial_data.get('market_cap')
            market_cap_str = f"${market_cap / 1e9:.2f}B" if market_cap >= 1e9 else f"${market_cap / 1e6:.2f}M"
            report.append(f"Market Cap: {market_cap_str}")
        if self.market_cap_tier:
            report.append(f"Market Cap Tier: {self.market_cap_tier}")
        report.append("")

        # Quality Score Summary
        report.append("📊 QUALITY SCORE SUMMARY")
        report.append("-"*40)
        report.append(f"Quality Score: {self.quality_result.composite_score:.1f}/100")
        report.append(f"Tier: {self.quality_result.tier.value}")
        report.append(f"Red Flags: {len(self.quality_result.red_flags)}")
        report.append(f"Data Quality: {self.financial_data.get('data_quality', 'unknown')}")
        report.append("")

        # Investment Recommendation
        recommendation = self.generate_investment_recommendation()
        report.append("💡 INVESTMENT RECOMMENDATION")
        report.append("-"*40)
        report.append(recommendation)
        report.append("")

        # Detailed Metrics
        report.append("📈 DETAILED QUALITY METRICS")
        report.append("-"*40)
        for metric in self.quality_result.metric_scores:
            # DimensionScore has name, score, metrics dict
            if hasattr(metric, 'metrics') and metric.metrics:
                # Show key metric value if available
                key_metric = list(metric.metrics.keys())[0] if metric.metrics else None
                metric_value = metric.metrics.get(key_metric, 'N/A') if key_metric != 'N/A' else 'N/A'
                if isinstance(metric_value, (int, float)):
                    report.append(f"{metric.name}: {metric_value:.2f} (Score: {metric.score:.1f})")
                else:
                    report.append(f"{metric.name}: {metric_value} (Score: {metric.score:.1f})")
            else:
                # Fallback for MetricScore objects with .value attribute
                metric_value = getattr(metric, 'value', 'N/A')
                if isinstance(metric_value, (int, float)):
                    report.append(f"{metric.name}: {metric_value:.2f} (Score: {metric.score:.1f})")
                else:
                    report.append(f"{metric.name}: {metric_value} (Score: {metric.score:.1f})")
        report.append("")

        # Red Flags
        if self.quality_result.red_flags:
            report.append("🚩 RED FLAGS DETECTED")
            report.append("-"*40)
            for i, rf in enumerate(self.quality_result.red_flags, 1):
                report.append(f"{i}. [{rf.severity.upper()}] {rf.description}")
                if rf.category:
                    report.append(f"   Category: {rf.category}")
            report.append("")
        else:
            report.append("✅ NO RED FLAGS DETECTED")
            report.append("-"*40)
            report.append("This stock shows no major quality concerns.")
            report.append("")

        # Key Financials
        report.append("💰 KEY FINANCIAL METRICS")
        report.append("-"*40)
        data = self.financial_data

        if data.get('revenue'):
            report.append(f"Revenue: ${data.get('revenue') / 1e9:.2f}B")
        if data.get('net_income'):
            report.append(f"Net Income: ${data.get('net_income') / 1e9:.2f}B")
        if data.get('free_cash_flow'):
            report.append(f"Free Cash Flow: ${data.get('free_cash_flow') / 1e9:.2f}B")
        if data.get('total_assets'):
            report.append(f"Total Assets: ${data.get('total_assets') / 1e9:.2f}B")
        if data.get('shareholder_equity'):
            report.append(f"Shareholder Equity: ${data.get('shareholder_equity') / 1e9:.2f}B")
        if data.get('total_debt'):
            report.append(f"Total Debt: ${data.get('total_debt') / 1e9:.2f}B")

        # Profitability ratios
        if data.get('revenue') and data.get('cogs') and data.get('revenue') > 0:
            gross_margin = (data.get('revenue') - (data.get('cogs') or 0)) / data.get('revenue')
            report.append(f"Gross Margin: {gross_margin:.1%}")

        if data.get('net_income') and data.get('shareholder_equity') and data.get('shareholder_equity') > 0:
            roe = data.get('net_income') / data.get('shareholder_equity')
            report.append(f"Return on Equity: {roe:.1%}")
        report.append("")

        # ROE Persistence Analysis
        if self.roe_persistence:
            report.append("📊 ROE PERSISTENCE ANALYSIS")
            report.append("-"*40)
            rp = self.roe_persistence
            report.append(f"Years Analyzed: {rp['years_analyzed']}")
            report.append(f"ROE Years Above 15%: {rp['roe_years_above_15pct']}")
            report.append(f"ROE Mean: {rp['roe_mean']:.1%}")
            report.append(f"Incremental ROCE Advantage: {rp['incremental_roce_advantage']:.1%}")
            report.append(f"Classification: {rp['classification']}")
            report.append(f"Compounder Confidence: {rp['compounder_confidence']:.1f}%")
            report.append("")
        else:
            report.append("📊 ROE PERSISTENCE ANALYSIS")
            report.append("-"*40)
            report.append("Insufficient historical data for ROE persistence analysis.")
            report.append("Need at least 2 years of historical financials.")
            report.append("")

        # Lookback Periods Summary
        report.append("📐 LOOKBACK PERIODS SUMMARY")
        report.append("-"*40)

        market_cap = self.financial_data.get('market_cap', 0) if self.financial_data else 0
        sector = self.financial_data.get('sector', 'Unknown') if self.financial_data else 'Unknown'

        if market_cap > 0:
            tier = LookbackCalculator.classify_market_cap(market_cap)
            tier_name = tier.value if hasattr(tier, 'value') else str(tier)
            report.append(f"Market Cap Tier: {tier_name}")

            multiplier = LookbackCalculator.MARKET_CAP_MULTIPLIERS.get(tier, 1.0)
            sector_adj = SECTOR_ADJUSTMENTS.get(sector, 1.0)
            report.append(f"Market Cap Multiplier: {multiplier:.2f}x")
            report.append(f"Sector Adjustment: {sector_adj:.2f}x")
            report.append("")

            report.append("Quality Dimension Lookback Periods:")
            report.append("-"*40)

            for dimension, config in QUALITY_DIMENSIONS.items():
                base_lookback = config['default_lookback']
                adjusted = base_lookback * multiplier * sector_adj
                adjusted = max(config['min_lookback'], min(adjusted, config['max_lookback']))
                report.append(f"  {dimension.title().replace('_', ' ')}: {adjusted:.1f} years (base: {base_lookback})")

            report.append("")
            report.append("Formula: Adjusted Lookback = Base × Market Cap Multiplier × Sector Adjustment")
            report.append("")
        else:
            report.append("Market Cap data not available for lookback calculation.")
            report.append("")

        # Footer
        report.append("="*80)
        report.append("Quality Framework: Academic research-based metrics")
        report.append("Data Source: Yahoo Finance (yfinance)")
        report.append("Analysis Date: Real-time as of report generation")
        report.append("="*80)

        return "\n".join(report)

    def run(self) -> bool:
        """
        Run complete individual stock analysis

        Returns:
            True if analysis completed successfully, False otherwise
        """
        logger.info(f"Starting individual stock analysis for {self.ticker}")

        try:
            # Step 1: Fetch financial data
            if not self.fetch_data():
                logger.error(f"Analysis failed for {self.ticker} - could not fetch data")
                return False

            # Step 2: Calculate quality metrics
            if not self.calculate_quality_metrics():
                logger.error(f"Analysis failed for {self.ticker} - could not calculate metrics")
                return False

            # Step 3: Classify market cap
            self.classify_market_cap()

            # Step 4: Analyze ROE persistence
            self.analyze_roe_persistence()

            # Step 5: Generate and save report
            report = self.generate_report()

            # Create outputs directory if it doesn't exist
            output_dir = Path(__file__).parent.parent / "outputs"
            output_dir.mkdir(exist_ok=True)

            # Save report
            timestamp = datetime.now().strftime("%Y%m%d")
            filename = f"stock_analysis_{self.ticker}_{timestamp}.txt"
            output_path = output_dir / filename

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)

            print("="*60)
            print(f"INDIVIDUAL STOCK ANALYSIS COMPLETE")
            print("="*60)
            print(f"Ticker: {self.ticker}")
            print(f"Quality Score: {self.quality_result.composite_score:.1f}/100")
            print(f"Tier: {self.quality_result.tier.value}")
            print(f"Recommendation: {self.generate_investment_recommendation().split(' - ')[0]}")
            print()
            print(f"Full report saved to: outputs/{filename}")
            print("="*60)

            logger.info(f"Individual stock analysis complete for {self.ticker}")
            return True

        except Exception as e:
            logger.error(f"Analysis failed for {self.ticker}: {e}")
            return False


# Quick test function
if __name__ == "__main__":
    # Test with Apple
    analyzer = IndividualStockAnalysis("AAPL")
    analyzer.run()