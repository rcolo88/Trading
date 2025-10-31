"""
Example: Integrating Quality Metrics Calculator with Trading System

This example demonstrates how to integrate the Quality Metrics Calculator
with the existing LLM Managed Portfolio trading system.

Author: Trading System
Date: 2025-10-30
"""

import yfinance as yf
from typing import Dict, List, Optional, Any
from quality_metrics_calculator import (
    QualityMetricsCalculator,
    QualityAnalysisResult,
    QualityTier,
    format_quality_report
)
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QualityScreener:
    """
    Integrates quality metrics calculator with yfinance for live stock analysis.

    This class fetches real-time financial data and calculates quality metrics
    for portfolio holdings or potential investments.
    """

    def __init__(self):
        """Initialize the quality screener."""
        self.calculator = QualityMetricsCalculator()

    def fetch_financial_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch financial data from yfinance for quality analysis.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary of financial metrics, or None if data unavailable
        """
        try:
            stock = yf.Ticker(ticker)

            # Get financial statements
            income_stmt = stock.financials
            balance_sheet = stock.balance_sheet
            cash_flow = stock.cashflow

            # Get current stock info
            info = stock.info

            # Handle quarterly vs annual data
            if income_stmt.empty:
                income_stmt = stock.quarterly_financials
                balance_sheet = stock.quarterly_balance_sheet
                cash_flow = stock.quarterly_cashflow
                logger.warning(f"{ticker}: Using quarterly data (annual not available)")

            if income_stmt.empty or balance_sheet.empty:
                logger.error(f"{ticker}: Financial data not available")
                return None

            # Extract most recent column (latest data)
            latest_col = income_stmt.columns[0]

            # Build financial data dictionary
            # Note: yfinance uses different field names, we need to map them
            financial_data = {
                'ticker': ticker,

                # Income statement items
                'revenue': self._safe_get(income_stmt, 'Total Revenue', latest_col),
                'cogs': self._safe_get(income_stmt, 'Cost Of Revenue', latest_col),
                'sga': self._safe_get(income_stmt, 'Selling General Administrative', latest_col, default=0),
                'net_income': self._safe_get(income_stmt, 'Net Income', latest_col),

                # Balance sheet items
                'total_assets': self._safe_get(balance_sheet, 'Total Assets', latest_col),
                'shareholder_equity': self._safe_get(balance_sheet, 'Stockholders Equity', latest_col),
                'total_debt': self._calculate_total_debt(balance_sheet, latest_col),

                # Cash flow items
                'free_cash_flow': self._safe_get(cash_flow, 'Free Cash Flow', latest_col),

                # Market data
                'market_cap': info.get('marketCap', 0),

                # Calculate NOPAT (approximate)
                'nopat': self._estimate_nopat(income_stmt, latest_col),

                # Optional: Historical ROE
                'roe_history': self._calculate_roe_history(income_stmt, balance_sheet),

                # Optional: YoY changes
                'prior_year_revenue': self._safe_get(income_stmt, 'Total Revenue', income_stmt.columns[1]) if len(income_stmt.columns) > 1 else None,
                'prior_year_cogs': self._safe_get(income_stmt, 'Cost Of Revenue', income_stmt.columns[1]) if len(income_stmt.columns) > 1 else None,
            }

            # Calculate optional metrics if data available
            if len(income_stmt.columns) > 1:
                financial_data['asset_growth'] = self._calculate_asset_growth(balance_sheet)

            logger.info(f"{ticker}: Financial data fetched successfully")
            return financial_data

        except Exception as e:
            logger.error(f"{ticker}: Error fetching financial data: {str(e)}")
            return None

    def _safe_get(self, df, field_name: str, column, default=None):
        """Safely extract value from dataframe."""
        try:
            if field_name in df.index:
                value = df.loc[field_name, column]
                return float(value) if value is not None else default
            return default
        except Exception:
            return default

    def _calculate_total_debt(self, balance_sheet, column) -> float:
        """Calculate total debt from balance sheet."""
        # Try different debt field names
        debt_fields = [
            'Total Debt',
            'Long Term Debt',
            'Short Long Term Debt',
            'Current Debt'
        ]

        total_debt = 0
        for field in debt_fields:
            debt = self._safe_get(balance_sheet, field, column, default=0)
            if debt:
                total_debt += debt

        return total_debt

    def _estimate_nopat(self, income_stmt, column) -> float:
        """
        Estimate NOPAT (Net Operating Profit After Tax).

        NOPAT = Operating Income * (1 - Tax Rate)
        If tax rate unavailable, use effective rate from Net Income
        """
        operating_income = self._safe_get(income_stmt, 'Operating Income', column)
        if not operating_income:
            # Fallback: use EBIT
            operating_income = self._safe_get(income_stmt, 'EBIT', column, default=0)

        # Estimate tax rate
        pretax_income = self._safe_get(income_stmt, 'Pretax Income', column)
        net_income = self._safe_get(income_stmt, 'Net Income', column)

        if pretax_income and net_income and pretax_income != 0:
            tax_rate = 1 - (net_income / pretax_income)
        else:
            tax_rate = 0.21  # Default U.S. corporate tax rate

        nopat = operating_income * (1 - tax_rate)
        return nopat

    def _calculate_roe_history(self, income_stmt, balance_sheet) -> List[float]:
        """Calculate historical ROE for consistency analysis."""
        roe_history = []

        # Get up to 10 years/quarters of data
        num_periods = min(len(income_stmt.columns), 10)

        for i in range(num_periods):
            try:
                col = income_stmt.columns[i]
                net_income = self._safe_get(income_stmt, 'Net Income', col)
                equity = self._safe_get(balance_sheet, 'Stockholders Equity', col)

                if net_income is not None and equity and equity != 0:
                    roe = net_income / equity
                    roe_history.append(roe)
            except Exception:
                continue

        return roe_history

    def _calculate_asset_growth(self, balance_sheet) -> Optional[float]:
        """Calculate YoY asset growth rate."""
        if len(balance_sheet.columns) < 2:
            return None

        try:
            current_assets = self._safe_get(balance_sheet, 'Total Assets', balance_sheet.columns[0])
            prior_assets = self._safe_get(balance_sheet, 'Total Assets', balance_sheet.columns[1])

            if current_assets and prior_assets and prior_assets != 0:
                return (current_assets - prior_assets) / prior_assets

        except Exception:
            pass

        return None

    def analyze_stock(self, ticker: str) -> Optional[QualityAnalysisResult]:
        """
        Perform complete quality analysis on a stock.

        Args:
            ticker: Stock ticker symbol

        Returns:
            QualityAnalysisResult or None if analysis fails
        """
        logger.info(f"Analyzing quality metrics for {ticker}...")

        # Fetch financial data
        financial_data = self.fetch_financial_data(ticker)

        if not financial_data:
            logger.error(f"Could not fetch financial data for {ticker}")
            return None

        # Calculate quality metrics
        try:
            result = self.calculator.calculate_quality_metrics(financial_data)
            logger.info(f"{ticker} analysis complete: {result.tier.value} tier, "
                       f"score {result.composite_score:.1f}")
            return result
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {str(e)}")
            return None

    def screen_portfolio(self, tickers: List[str]) -> Dict[str, QualityAnalysisResult]:
        """
        Screen multiple stocks and return quality analysis for each.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping tickers to their quality analysis results
        """
        results = {}

        for ticker in tickers:
            result = self.analyze_stock(ticker)
            if result:
                results[ticker] = result

        return results

    def generate_portfolio_quality_report(self, tickers: List[str]) -> str:
        """
        Generate comprehensive quality report for entire portfolio.

        Args:
            tickers: List of ticker symbols in portfolio

        Returns:
            Formatted report string
        """
        results = self.screen_portfolio(tickers)

        if not results:
            return "No quality data available for portfolio."

        # Sort by quality score
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )

        # Build report
        lines = []
        lines.append("=" * 80)
        lines.append("PORTFOLIO QUALITY ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary table
        lines.append("QUALITY SUMMARY:")
        lines.append("-" * 80)
        lines.append(f"{'Ticker':<10} {'Score':<8} {'Tier':<12} {'Red Flags':<12} {'ROE Consist.':<15}")
        lines.append("-" * 80)

        for ticker, result in sorted_results:
            roe_badge = "✓" if result.is_consistent_roe_performer else " "
            high_severity = len([rf for rf in result.red_flags if rf.severity == "HIGH"])
            flag_str = f"{len(result.red_flags)} ({high_severity} HIGH)" if result.red_flags else "None"

            lines.append(f"{ticker:<10} {result.composite_score:<8.1f} {result.tier.value:<12} "
                        f"{flag_str:<12} {roe_badge:<15}")

        # Tier breakdown
        lines.append("")
        lines.append("TIER DISTRIBUTION:")
        tier_counts = {}
        for tier in QualityTier:
            count = sum(1 for r in results.values() if r.tier == tier)
            if count > 0:
                tier_counts[tier.value] = count
                lines.append(f"  {tier.value}: {count} stocks")

        # Stocks with concerns
        high_concern = [
            ticker for ticker, result in results.items()
            if len([rf for rf in result.red_flags if rf.severity == "HIGH"]) >= 2
        ]

        if high_concern:
            lines.append("")
            lines.append("⚠️  STOCKS WITH MULTIPLE HIGH-SEVERITY RED FLAGS:")
            for ticker in high_concern:
                lines.append(f"  • {ticker}")

        # Elite performers
        elite = [ticker for ticker, result in results.items() if result.tier == QualityTier.ELITE]
        if elite:
            lines.append("")
            lines.append("⭐ ELITE QUALITY STOCKS:")
            for ticker in elite:
                lines.append(f"  • {ticker}")

        # Detailed reports for each stock
        lines.append("")
        lines.append("=" * 80)
        lines.append("DETAILED STOCK ANALYSIS")
        lines.append("=" * 80)

        for ticker, result in sorted_results:
            lines.append("")
            lines.append(format_quality_report(result, include_raw_data=False))
            lines.append("")

        return "\n".join(lines)


def example_single_stock_analysis():
    """Example: Analyze a single stock."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Single Stock Analysis")
    print("=" * 80)

    screener = QualityScreener()

    # Analyze Apple
    result = screener.analyze_stock('AAPL')

    if result:
        print(format_quality_report(result, include_raw_data=True))
    else:
        print("Analysis failed")


def example_portfolio_screening():
    """Example: Screen entire portfolio."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Portfolio Quality Screening")
    print("=" * 80)

    screener = QualityScreener()

    # Sample portfolio
    portfolio = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'JPM']

    # Generate report
    report = screener.generate_portfolio_quality_report(portfolio)
    print(report)


def example_investment_decision():
    """Example: Use quality metrics for investment decision."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Investment Decision Framework")
    print("=" * 80)

    screener = QualityScreener()

    # Analyze stock
    ticker = 'MSFT'
    result = screener.analyze_stock(ticker)

    if not result:
        print(f"Could not analyze {ticker}")
        return

    # Decision logic
    print(f"\nInvestment Analysis for {ticker}:")
    print(f"Quality Score: {result.composite_score:.1f}/100")
    print(f"Quality Tier: {result.tier.value}")

    high_severity_flags = [rf for rf in result.red_flags if rf.severity == "HIGH"]

    if result.tier == QualityTier.ELITE and len(high_severity_flags) == 0:
        decision = "STRONG BUY"
        rationale = "Elite quality with no major red flags"
    elif result.tier == QualityTier.STRONG and len(high_severity_flags) == 0:
        decision = "BUY"
        rationale = "Strong quality fundamentals"
    elif result.tier in [QualityTier.STRONG, QualityTier.MODERATE]:
        decision = "HOLD"
        rationale = "Moderate quality, monitor red flags"
    elif len(high_severity_flags) >= 2:
        decision = "AVOID"
        rationale = "Multiple high-severity red flags"
    else:
        decision = "SELL"
        rationale = "Weak quality fundamentals"

    print(f"\nRECOMMENDATION: {decision}")
    print(f"RATIONALE: {rationale}")

    if result.red_flags:
        print(f"\nConcerns to Monitor:")
        for rf in result.red_flags[:3]:  # Top 3
            print(f"  • [{rf.severity}] {rf.category}")


if __name__ == "__main__":
    # Run examples
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "QUALITY METRICS INTEGRATION EXAMPLES" + " " * 27 + "║")
    print("╚" + "=" * 78 + "╝")

    # Note: These examples require internet connection to fetch live data
    try:
        # Example 1: Single stock
        example_single_stock_analysis()

        # Example 2: Portfolio screening
        example_portfolio_screening()

        # Example 3: Investment decision
        example_investment_decision()

    except Exception as e:
        print(f"\nError running examples: {str(e)}")
        print("\nNote: Examples require internet connection and valid yfinance data")
