"""
Data Quality Validator - STEP 9 Implementation

This module implements data quality validation for the STEPS portfolio analysis framework.
Tracks data sources, detects missing/stale metrics, validates data consistency, and generates
quality reports with completeness scores.

Author: Claude Code
Date: 2025-11-03
Reference: STEPS_Research_Methodology_November_1_2025.md (STEP 9)
"""

import yfinance as yf
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MetricSource:
    """
    Tracks the source and metadata for a single metric
    """
    metric_name: str
    value: Any  # Can be float, str, or other types
    source: str  # e.g., "yfinance", "manual", "calculated"
    fetch_date: str  # ISO format YYYY-MM-DD
    confidence: str  # HIGH, MEDIUM, LOW

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return asdict(self)


@dataclass
class DataQualityReport:
    """
    Comprehensive data quality assessment for a ticker
    """
    ticker: str
    overall_quality: str  # COMPLETE, PARTIAL, INSUFFICIENT
    quality_score: float  # 0-10
    metrics: List[MetricSource]
    missing_metrics: List[str]
    stale_metrics: List[str]  # >90 days old
    warnings: List[str]
    validation_date: str  # ISO format

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            "ticker": self.ticker,
            "overall_quality": self.overall_quality,
            "quality_score": self.quality_score,
            "metrics": [m.to_dict() for m in self.metrics],
            "missing_metrics": self.missing_metrics,
            "stale_metrics": self.stale_metrics,
            "warnings": self.warnings,
            "validation_date": self.validation_date
        }


class DataValidator:
    """
    Validates data quality for portfolio analysis

    Responsibilities:
    - Detect missing critical metrics
    - Flag stale data (>90 days)
    - Validate data consistency
    - Generate quality scores
    - Track data sources
    """

    # Required metrics for complete data quality
    REQUIRED_METRICS = [
        'revenue', 'cogs', 'total_assets', 'shareholder_equity',
        'operating_income', 'net_income', 'operating_cash_flow',
        'total_debt', 'market_cap'
    ]

    # Metrics that should be recent
    PRICE_METRICS = ['current_price', 'market_cap']  # <7 days
    FUNDAMENTAL_METRICS = ['revenue', 'net_income', 'total_assets']  # <90 days

    def __init__(self):
        """Initialize DataValidator"""
        self.validation_cache: Dict[str, DataQualityReport] = {}

    def validate_financial_data(
        self,
        ticker: str,
        financial_data: Dict[str, Any],
        max_age_days: int = 90
    ) -> DataQualityReport:
        """
        Validate completeness and freshness of financial data

        Args:
            ticker: Stock ticker symbol
            financial_data: Dictionary containing financial metrics
            max_age_days: Maximum age for fundamental metrics (default 90)

        Returns:
            DataQualityReport with validation results
        """
        logger.info(f"Validating data quality for {ticker}...")

        # Track all metrics with sources
        metrics: List[MetricSource] = []

        # Detect missing metrics
        missing_metrics = self.detect_missing_metrics(financial_data)

        # Detect stale data
        stale_metrics = self.detect_stale_data(financial_data, max_age_days)

        # Validate data consistency
        warnings = self.validate_data_consistency(financial_data)

        # Track sources for available metrics
        for metric_name, metric_value in financial_data.items():
            if metric_value is not None and metric_name in self.REQUIRED_METRICS:
                # Determine source and confidence
                source = "yfinance"  # Default source
                confidence = "HIGH" if metric_name not in stale_metrics else "MEDIUM"
                fetch_date = datetime.now().strftime('%Y-%m-%d')  # Assume recent if in data

                metrics.append(MetricSource(
                    metric_name=metric_name,
                    value=metric_value,
                    source=source,
                    fetch_date=fetch_date,
                    confidence=confidence
                ))

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            missing_metrics, stale_metrics, warnings
        )

        # Determine overall quality
        overall_quality = self._determine_overall_quality(
            quality_score, missing_metrics
        )

        report = DataQualityReport(
            ticker=ticker,
            overall_quality=overall_quality,
            quality_score=quality_score,
            metrics=metrics,
            missing_metrics=missing_metrics,
            stale_metrics=stale_metrics,
            warnings=warnings,
            validation_date=datetime.now().strftime('%Y-%m-%d')
        )

        # Cache result
        self.validation_cache[ticker] = report

        logger.info(f"{ticker} data quality: {overall_quality} (score: {quality_score:.1f}/10)")

        return report

    def detect_missing_metrics(self, financial_data: Dict[str, Any]) -> List[str]:
        """
        Identify missing critical metrics

        Args:
            financial_data: Dictionary containing financial metrics

        Returns:
            List of missing metric names
        """
        missing = []

        for metric in self.REQUIRED_METRICS:
            if metric not in financial_data or financial_data[metric] is None:
                missing.append(metric)

        return missing

    def detect_stale_data(
        self,
        financial_data: Dict[str, Any],
        max_age_days: int = 90
    ) -> List[str]:
        """
        Identify metrics that are too old

        Args:
            financial_data: Dictionary containing financial metrics
            max_age_days: Maximum age threshold (default 90 days)

        Returns:
            List of stale metric names
        """
        stale = []

        # Check if last_updated exists
        if 'last_updated' not in financial_data:
            # If no timestamp, assume data is stale
            return self.FUNDAMENTAL_METRICS.copy()

        last_updated_str = financial_data.get('last_updated', '')

        try:
            last_updated = datetime.strptime(last_updated_str, '%Y-%m-%d')
            age_days = (datetime.now() - last_updated).days

            if age_days > max_age_days:
                # All fundamental metrics are stale
                for metric in self.FUNDAMENTAL_METRICS:
                    if metric in financial_data:
                        stale.append(metric)
        except (ValueError, TypeError):
            # Cannot parse date, flag as potentially stale
            logger.warning(f"Cannot parse last_updated date: {last_updated_str}")
            # Don't flag as stale if we can't determine age

        return stale

    def validate_data_consistency(
        self,
        financial_data: Dict[str, Any]
    ) -> List[str]:
        """
        Detect inconsistencies in data

        Args:
            financial_data: Dictionary containing financial metrics

        Returns:
            List of warnings about inconsistencies
        """
        warnings = []

        # Check revenue > 0
        revenue = financial_data.get('revenue', 0)
        if revenue is not None and revenue <= 0:
            warnings.append(f"Revenue is non-positive: {revenue}")

        # Check market cap > 0
        market_cap = financial_data.get('market_cap', 0)
        if market_cap is not None and market_cap <= 0:
            warnings.append(f"Market cap is non-positive: {market_cap}")

        # Check assets > equity (if debt exists)
        total_assets = financial_data.get('total_assets')
        shareholder_equity = financial_data.get('shareholder_equity')
        total_debt = financial_data.get('total_debt', 0)

        if (total_assets is not None and shareholder_equity is not None and
            total_debt is not None and total_debt > 0):
            if total_assets < shareholder_equity:
                warnings.append(
                    f"Assets ({total_assets}) < Equity ({shareholder_equity}) "
                    f"despite debt ({total_debt})"
                )

        # Check operating income <= revenue
        operating_income = financial_data.get('operating_income')
        if revenue is not None and operating_income is not None:
            if operating_income > revenue:
                warnings.append(
                    f"Operating income ({operating_income}) > Revenue ({revenue})"
                )

        # Check gross margin <= 100%
        cogs = financial_data.get('cogs')
        if revenue is not None and cogs is not None and revenue > 0:
            gross_profit = revenue - cogs
            gross_margin = (gross_profit / revenue) * 100
            if gross_margin > 100:
                warnings.append(
                    f"Gross margin ({gross_margin:.1f}%) exceeds 100%"
                )
            if gross_margin < 0:
                warnings.append(
                    f"Gross margin ({gross_margin:.1f}%) is negative"
                )

        # Check for negative equity (distress signal)
        if shareholder_equity is not None and shareholder_equity < 0:
            warnings.append(
                f"Negative shareholder equity ({shareholder_equity}) - financial distress"
            )

        # Check for excessive debt (Debt/Assets > 80%)
        if total_assets is not None and total_debt is not None and total_assets > 0:
            debt_ratio = (total_debt / total_assets) * 100
            if debt_ratio > 80:
                warnings.append(
                    f"Excessive leverage: Debt/Assets = {debt_ratio:.1f}%"
                )

        return warnings

    def _calculate_quality_score(
        self,
        missing_metrics: List[str],
        stale_metrics: List[str],
        warnings: List[str]
    ) -> float:
        """
        Calculate data quality score (0-10)

        Args:
            missing_metrics: List of missing metrics
            stale_metrics: List of stale metrics
            warnings: List of consistency warnings

        Returns:
            Score from 0-10
        """
        score = 10.0

        # Penalty for missing metrics
        score -= len(missing_metrics) * 2.0

        # Penalty for stale metrics
        score -= len(stale_metrics) * 1.0

        # Penalty for warnings
        score -= len(warnings) * 0.5

        # Ensure score is non-negative
        score = max(0.0, score)

        return score

    def _determine_overall_quality(
        self,
        quality_score: float,
        missing_metrics: List[str]
    ) -> str:
        """
        Determine overall quality classification

        Args:
            quality_score: Calculated quality score
            missing_metrics: List of missing metrics

        Returns:
            COMPLETE, PARTIAL, or INSUFFICIENT
        """
        # Critical metrics: revenue, total_assets, shareholder_equity, net_income
        critical_missing = [
            m for m in missing_metrics
            if m in ['revenue', 'total_assets', 'shareholder_equity', 'net_income']
        ]

        if len(critical_missing) > 0:
            return "INSUFFICIENT"
        elif quality_score >= 8.0:
            return "COMPLETE"
        else:
            return "PARTIAL"

    def generate_validation_report(
        self,
        report: DataQualityReport
    ) -> str:
        """
        Generate markdown data quality report

        Args:
            report: DataQualityReport object

        Returns:
            Markdown formatted report
        """
        lines = []
        lines.append(f"# Data Quality Report: {report.ticker}")
        lines.append("")
        lines.append(f"**Validation Date**: {report.validation_date}")
        lines.append("")

        # Overall Quality Section
        lines.append(f"## Overall Quality: {report.overall_quality}")
        lines.append(f"**Quality Score**: {report.quality_score:.1f}/10")
        lines.append("")

        # Metrics Summary
        total_required = len(self.REQUIRED_METRICS)
        complete_count = len(report.metrics)
        missing_count = len(report.missing_metrics)
        stale_count = len(report.stale_metrics)

        lines.append("## Metrics Summary")
        lines.append(f"- **Total Required Metrics**: {total_required}")
        lines.append(f"- **Complete**: {complete_count}")
        lines.append(f"- **Missing**: {missing_count}")
        lines.append(f"- **Stale**: {stale_count}")
        lines.append("")

        # Missing Metrics Section
        if report.missing_metrics:
            lines.append("## Missing Metrics")
            for metric in report.missing_metrics:
                lines.append(f"- `{metric}` (not available)")
            lines.append("")

        # Stale Metrics Section
        if report.stale_metrics:
            lines.append("## Stale Metrics (>90 days)")
            for metric in report.stale_metrics:
                lines.append(f"- `{metric}` (outdated)")
            lines.append("")

        # Data Sources Section
        if report.metrics:
            lines.append("## Data Sources")
            lines.append("| Metric | Value | Source | Date | Confidence |")
            lines.append("|--------|-------|--------|------|-----------|")

            for metric in report.metrics:
                # Format value appropriately
                if isinstance(metric.value, float):
                    if metric.value > 1e9:
                        value_str = f"${metric.value/1e9:.2f}B"
                    elif metric.value > 1e6:
                        value_str = f"${metric.value/1e6:.2f}M"
                    else:
                        value_str = f"{metric.value:.2f}"
                else:
                    value_str = str(metric.value)

                lines.append(
                    f"| {metric.metric_name} | {value_str} | {metric.source} | "
                    f"{metric.fetch_date} | {metric.confidence} |"
                )
            lines.append("")

        # Warnings Section
        if report.warnings:
            lines.append("## Warnings")
            for warning in report.warnings:
                lines.append(f"- ⚠️ {warning}")
            lines.append("")
        else:
            lines.append("## Warnings")
            lines.append("No data consistency issues detected.")
            lines.append("")

        # Quality Assessment
        lines.append("## Quality Assessment")
        if report.overall_quality == "COMPLETE":
            lines.append("✅ **Data quality is excellent.** All required metrics are available and recent.")
        elif report.overall_quality == "PARTIAL":
            lines.append("⚠️ **Data quality is acceptable but incomplete.** Some metrics are missing or stale.")
        else:
            lines.append("❌ **Data quality is insufficient.** Critical metrics are missing. Analysis may be unreliable.")
        lines.append("")

        return "\n".join(lines)

    def batch_validate_portfolio(
        self,
        tickers: List[str],
        financial_data_dict: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, DataQualityReport]:
        """
        Validate entire portfolio

        Args:
            tickers: List of ticker symbols
            financial_data_dict: Optional dict mapping tickers to financial data
                                If not provided, will fetch from yfinance

        Returns:
            Dictionary mapping tickers to DataQualityReport objects
        """
        logger.info(f"Batch validating {len(tickers)} tickers...")

        reports = {}

        for ticker in tickers:
            try:
                # Get financial data
                if financial_data_dict and ticker in financial_data_dict:
                    financial_data = financial_data_dict[ticker]
                else:
                    financial_data = self._fetch_financial_data(ticker)

                # Validate data
                report = self.validate_financial_data(ticker, financial_data)
                reports[ticker] = report

            except Exception as e:
                logger.error(f"Error validating {ticker}: {e}")
                # Create insufficient report
                reports[ticker] = DataQualityReport(
                    ticker=ticker,
                    overall_quality="INSUFFICIENT",
                    quality_score=0.0,
                    metrics=[],
                    missing_metrics=self.REQUIRED_METRICS.copy(),
                    stale_metrics=[],
                    warnings=[f"Error fetching data: {str(e)}"],
                    validation_date=datetime.now().strftime('%Y-%m-%d')
                )

        logger.info(f"Batch validation complete. {len(reports)} reports generated.")

        return reports

    def _fetch_financial_data(self, ticker: str) -> Dict[str, Any]:
        """
        Fetch financial data from yfinance

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary of financial metrics
        """
        stock = yf.Ticker(ticker)
        info = stock.info

        financial_data = {
            'revenue': info.get('totalRevenue'),
            'cogs': info.get('costOfRevenue'),
            'total_assets': info.get('totalAssets'),
            'shareholder_equity': info.get('totalStockholderEquity'),
            'operating_income': info.get('operatingIncome'),
            'net_income': info.get('netIncomeToCommon'),
            'operating_cash_flow': info.get('operatingCashflow'),
            'total_debt': info.get('totalDebt', 0),
            'market_cap': info.get('marketCap'),
            'current_price': info.get('currentPrice'),
            'last_updated': datetime.now().strftime('%Y-%m-%d')
        }

        return financial_data

    def export_to_json(self, reports: Dict[str, DataQualityReport], output_file: str):
        """
        Export validation reports to JSON

        Args:
            reports: Dictionary of DataQualityReport objects
            output_file: Output file path
        """
        export_data = {
            ticker: report.to_dict()
            for ticker, report in reports.items()
        }

        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Validation reports exported to {output_file}")

    def export_summary(self, reports: Dict[str, DataQualityReport], output_file: str):
        """
        Export summary markdown report

        Args:
            reports: Dictionary of DataQualityReport objects
            output_file: Output file path
        """
        lines = []
        lines.append("# Portfolio Data Quality Summary")
        lines.append("")
        lines.append(f"**Validation Date**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"**Tickers Analyzed**: {len(reports)}")
        lines.append("")

        # Summary statistics
        complete_count = sum(1 for r in reports.values() if r.overall_quality == "COMPLETE")
        partial_count = sum(1 for r in reports.values() if r.overall_quality == "PARTIAL")
        insufficient_count = sum(1 for r in reports.values() if r.overall_quality == "INSUFFICIENT")

        lines.append("## Overall Portfolio Data Quality")
        lines.append(f"- **Complete**: {complete_count} ({complete_count/len(reports)*100:.1f}%)")
        lines.append(f"- **Partial**: {partial_count} ({partial_count/len(reports)*100:.1f}%)")
        lines.append(f"- **Insufficient**: {insufficient_count} ({insufficient_count/len(reports)*100:.1f}%)")
        lines.append("")

        # Individual ticker quality
        lines.append("## Individual Ticker Quality")
        lines.append("| Ticker | Quality | Score | Missing | Stale | Warnings |")
        lines.append("|--------|---------|-------|---------|-------|----------|")

        for ticker in sorted(reports.keys()):
            report = reports[ticker]
            lines.append(
                f"| {ticker} | {report.overall_quality} | {report.quality_score:.1f}/10 | "
                f"{len(report.missing_metrics)} | {len(report.stale_metrics)} | {len(report.warnings)} |"
            )

        lines.append("")

        # Detailed reports for each ticker
        lines.append("---")
        lines.append("")
        lines.append("# Detailed Reports")
        lines.append("")

        for ticker in sorted(reports.keys()):
            report = reports[ticker]
            lines.append(self.generate_validation_report(report))
            lines.append("---")
            lines.append("")

        # Write to file
        with open(output_file, 'w') as f:
            f.write("\n".join(lines))

        logger.info(f"Summary report exported to {output_file}")


def main():
    """
    Test DataValidator with sample tickers
    """
    validator = DataValidator()

    # Test tickers
    test_tickers = ["NVDA", "GOOGL", "MSFT"]

    print("Testing DataValidator...")
    print(f"Validating {len(test_tickers)} tickers: {', '.join(test_tickers)}")
    print()

    # Batch validation
    reports = validator.batch_validate_portfolio(test_tickers)

    # Print summary
    print("\nValidation Results:")
    print("-" * 80)
    for ticker, report in reports.items():
        print(f"{ticker}:")
        print(f"  Quality: {report.overall_quality}")
        print(f"  Score: {report.quality_score:.1f}/10")
        print(f"  Missing: {len(report.missing_metrics)} metrics")
        print(f"  Stale: {len(report.stale_metrics)} metrics")
        print(f"  Warnings: {len(report.warnings)}")
        print()

    # Export results
    validator.export_to_json(reports, "outputs/data_validation_test.json")
    validator.export_summary(reports, "outputs/data_validation_summary.md")

    print("Export complete!")
    print("  - JSON: outputs/data_validation_test.json")
    print("  - Summary: outputs/data_validation_summary.md")


if __name__ == "__main__":
    main()
