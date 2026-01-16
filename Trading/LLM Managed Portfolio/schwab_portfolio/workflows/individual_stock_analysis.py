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
from quality.quality_metrics_calculator import QualityMetricsCalculator, QualityAnalysisResult
from quality.market_cap_classifier import MarketCapClassifier
from components.quality_persistence_analyzer import QualityPersistenceAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO)
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

    def __init__(self, ticker: str):
        """
        Initialize individual stock analysis

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
        """
        self.ticker = ticker.upper()
        self.fetcher = FinancialDataFetcher(enable_cache=True)
        self.quality_calculator = QualityMetricsCalculator()
        self.market_cap_classifier = MarketCapClassifier()
        self.roe_analyzer = QualityPersistenceAnalyzer()

        # Results storage
        self.financial_data: Optional[FinancialData] = None
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

        self.financial_data = self.fetcher.fetch_financial_data(self.ticker)

        if not self.financial_data:
            logger.error(f"Failed to fetch financial data for {self.ticker}")
            return False

        if self.financial_data.data_quality == "insufficient":
            logger.warning(f"Insufficient financial data for {self.ticker}")
            return False

        logger.info(f"Successfully fetched {self.financial_data.data_quality} quality data for {self.ticker}")
        return True

    def calculate_quality_metrics(self) -> bool:
        """
        Calculate quality metrics using the 5-metric framework

        Returns:
            True if calculation successful, False otherwise
        """
        if not self.financial_data:
            return False

        logger.info(f"Calculating quality metrics for {self.ticker}")

        try:
            # Prepare data for calculator
            calculator_input = {
                'ticker': self.ticker,
                'revenue': self.financial_data.revenue,
                'cogs': self.financial_data.cogs,
                'sga': self.financial_data.sga,
                'total_assets': self.financial_data.total_assets,
                'net_income': self.financial_data.net_income,
                'shareholder_equity': self.financial_data.shareholder_equity,
                'free_cash_flow': self.financial_data.free_cash_flow,
                'market_cap': self.financial_data.market_cap,
                'total_debt': self.financial_data.total_debt,
                'nopat': self.financial_data.nopat
            }

            self.quality_result = self.quality_calculator.calculate_quality_metrics(calculator_input)

            logger.info(f"Calculated quality metrics for {self.ticker}: score {self.quality_result.composite_score:.1f}")
            return True

        except Exception as e:
            logger.error(f"Failed to calculate quality metrics for {self.ticker}: {e}")
            return False

    def classify_market_cap(self) -> bool:
        """
        Classify stock into market cap tier

        Returns:
            True if classification successful, False otherwise
        """
        if not self.financial_data or not self.financial_data.market_cap:
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

            # Fetch historical financial data
            historical_data = self.fetcher.fetch_historical_financials(self.ticker, years=10)

            if historical_data is None or len(historical_data) < 2:
                logger.info(f"Insufficient historical data for ROE persistence analysis of {self.ticker}")
                self.roe_persistence = None
                return True

            # Analyze persistence
            persistence_result = self.roe_analyzer.analyze_company(historical_data, ticker=self.ticker)

            if persistence_result:
                # Extract key metrics
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
        if self.financial_data.sector:
            report.append(f"Sector: {self.financial_data.sector}")
        if self.financial_data.industry:
            report.append(f"Industry: {self.financial_data.industry}")
        if self.financial_data.market_cap:
            market_cap_str = f"${self.financial_data.market_cap / 1e9:.2f}B" if self.financial_data.market_cap >= 1e9 else f"${self.financial_data.market_cap / 1e6:.2f}M"
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
        report.append(f"Data Quality: {self.financial_data.data_quality}")
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
            report.append(f"{metric.name}: {metric.value:.2f} (Score: {metric.score:.1f})")
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

        if data.revenue:
            report.append(f"Revenue: ${data.revenue / 1e9:.2f}B")
        if data.net_income:
            report.append(f"Net Income: ${data.net_income / 1e9:.2f}B")
        if data.free_cash_flow:
            report.append(f"Free Cash Flow: ${data.free_cash_flow / 1e9:.2f}B")
        if data.total_assets:
            report.append(f"Total Assets: ${data.total_assets / 1e9:.2f}B")
        if data.shareholder_equity:
            report.append(f"Shareholder Equity: ${data.shareholder_equity / 1e9:.2f}B")
        if data.total_debt:
            report.append(f"Total Debt: ${data.total_debt / 1e9:.2f}B")

        # Profitability ratios
        if data.revenue and data.cogs and data.revenue > 0:
            gross_margin = (data.revenue - (data.cogs or 0)) / data.revenue
            report.append(f"Gross Margin: {gross_margin:.1%}")

        if data.net_income and data.shareholder_equity and data.shareholder_equity > 0:
            roe = data.net_income / data.shareholder_equity
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