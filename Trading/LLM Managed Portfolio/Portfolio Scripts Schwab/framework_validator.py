"""
Framework Compliance Validator - STEP 10 Implementation

This module implements framework compliance validation for the STEPS portfolio analysis framework.
Ensures all recommendations comply with PM_README_V3.md framework rules (80/20, position sizing, quality thresholds).

Author: Claude Code
Date: 2025-11-03
Reference: STEPS_Research_Methodology_November_1_2025.md (STEP 10)
Reference: PM_README_V3.md (80/20 Framework)
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Violation:
    """
    Represents a single framework compliance violation
    """
    severity: str  # CRITICAL, WARNING, INFO
    category: str  # ALLOCATION, POSITION_SIZE, THRESHOLD, CONCENTRATION
    ticker: Optional[str]  # None for portfolio-level violations
    message: str
    current_value: float
    expected_value: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return asdict(self)


@dataclass
class ComplianceReport:
    """
    Comprehensive framework compliance assessment
    """
    portfolio_value: float
    compliance_score: float  # 0-100
    violations: List[Violation]
    allocation_quality_pct: float
    allocation_thematic_pct: float
    allocation_cash_pct: float
    framework_compliant: bool  # True if no CRITICAL violations
    validation_date: str  # ISO format

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            "portfolio_value": self.portfolio_value,
            "compliance_score": self.compliance_score,
            "violations": [v.to_dict() for v in self.violations],
            "allocation_quality_pct": self.allocation_quality_pct,
            "allocation_thematic_pct": self.allocation_thematic_pct,
            "allocation_cash_pct": self.allocation_cash_pct,
            "framework_compliant": self.framework_compliant,
            "validation_date": self.validation_date
        }


class FrameworkValidator:
    """
    Validates portfolio compliance with 80/20 framework

    Responsibilities:
    - Validate 80/20 allocation (75-85% quality, 15-25% thematic)
    - Validate position sizing (match quality/thematic score ranges)
    - Validate quality thresholds (≥7.0 for core holdings)
    - Validate thematic thresholds (≥28 for opportunistic holdings)
    - Calculate compliance score (0-100)
    - Generate compliance reports
    """

    # Framework thresholds from PM_README_V3.md
    QUALITY_MIN = 75.0  # Minimum % in quality holdings
    QUALITY_MAX = 85.0  # Maximum % in quality holdings
    QUALITY_TARGET = 80.0

    THEMATIC_MIN = 15.0  # Minimum % in thematic holdings
    THEMATIC_MAX = 25.0  # Maximum % in thematic holdings
    THEMATIC_TARGET = 20.0

    CASH_MIN = 3.0  # Minimum cash reserve
    CASH_RECOMMENDED = 5.0  # Recommended cash reserve

    MAX_POSITION = 20.0  # Maximum single position size
    MAX_THEMATIC_POSITION = 7.0  # Maximum thematic position size

    QUALITY_THRESHOLD = 7.0  # Minimum quality score (7.0 on 10-point scale = 70/100)
    THEMATIC_THRESHOLD = 28.0  # Minimum thematic score (28/40)

    def __init__(self):
        """Initialize FrameworkValidator"""
        self.validation_cache: Dict[str, ComplianceReport] = {}

    def validate_80_20_allocation(
        self,
        allocation_quality_pct: float,
        allocation_thematic_pct: float,
        allocation_cash_pct: float
    ) -> List[Violation]:
        """
        Validate 80/20 framework compliance

        Rules (from PM_README_V3.md):
        - Quality holdings: 75-85% (80% target ±5% tolerance)
        - Opportunistic holdings: 15-25% (20% target ±5% tolerance)
        - Cash reserve: ≥3% (5% recommended)

        Violations:
        - CRITICAL: Quality <70% or >90%, Opportunistic >30%, Cash <2%
        - WARNING: Quality 70-75% or 85-90%, Opportunistic 25-30%, Cash 2-3%
        - INFO: Minor deviations within tolerance

        Args:
            allocation_quality_pct: % allocated to quality holdings
            allocation_thematic_pct: % allocated to thematic holdings
            allocation_cash_pct: % in cash

        Returns:
            List of Violation objects
        """
        violations = []

        # Validate quality allocation
        if allocation_quality_pct < 70.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Quality allocation {allocation_quality_pct:.1f}% far below minimum 75% (critical underweight)",
                current_value=allocation_quality_pct,
                expected_value=self.QUALITY_MIN
            ))
        elif allocation_quality_pct < self.QUALITY_MIN:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Quality allocation {allocation_quality_pct:.1f}% below minimum 75% (rebalance needed)",
                current_value=allocation_quality_pct,
                expected_value=self.QUALITY_MIN
            ))
        elif allocation_quality_pct > 90.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Quality allocation {allocation_quality_pct:.1f}% far above maximum 85% (critical overweight)",
                current_value=allocation_quality_pct,
                expected_value=self.QUALITY_MAX
            ))
        elif allocation_quality_pct > self.QUALITY_MAX:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Quality allocation {allocation_quality_pct:.1f}% above maximum 85% (rebalance needed)",
                current_value=allocation_quality_pct,
                expected_value=self.QUALITY_MAX
            ))

        # Validate thematic allocation
        if allocation_thematic_pct > 30.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Opportunistic allocation {allocation_thematic_pct:.1f}% far above maximum 25% (critical overweight)",
                current_value=allocation_thematic_pct,
                expected_value=self.THEMATIC_MAX
            ))
        elif allocation_thematic_pct > self.THEMATIC_MAX:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Opportunistic allocation {allocation_thematic_pct:.1f}% above maximum 25% (rebalance needed)",
                current_value=allocation_thematic_pct,
                expected_value=self.THEMATIC_MAX
            ))
        elif allocation_thematic_pct < self.THEMATIC_MIN:
            violations.append(Violation(
                severity="INFO",
                category="ALLOCATION",
                ticker=None,
                message=f"Opportunistic allocation {allocation_thematic_pct:.1f}% below minimum 15% (consider increasing)",
                current_value=allocation_thematic_pct,
                expected_value=self.THEMATIC_MIN
            ))

        # Validate cash reserve
        if allocation_cash_pct < 2.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Cash reserve {allocation_cash_pct:.1f}% critically low (minimum 3% required)",
                current_value=allocation_cash_pct,
                expected_value=self.CASH_MIN
            ))
        elif allocation_cash_pct < self.CASH_MIN:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Cash reserve {allocation_cash_pct:.1f}% below minimum 3% (increase recommended)",
                current_value=allocation_cash_pct,
                expected_value=self.CASH_MIN
            ))
        elif allocation_cash_pct < self.CASH_RECOMMENDED:
            violations.append(Violation(
                severity="INFO",
                category="ALLOCATION",
                ticker=None,
                message=f"Cash reserve {allocation_cash_pct:.1f}% below recommended 5% (consider increasing)",
                current_value=allocation_cash_pct,
                expected_value=self.CASH_RECOMMENDED
            ))

        return violations

    def validate_position_sizing(
        self,
        holdings: Dict[str, float],  # ticker → current %
        quality_scores: Dict[str, float],  # ticker → quality score (0-100)
        thematic_scores: Dict[str, float]  # ticker → thematic score (0-40)
    ) -> List[Violation]:
        """
        Validate position sizes match framework rules

        Quality position rules (PM_README_V3.md):
        - Score 9-10 (90-100): Should be 10-20%
        - Score 8-8.9 (80-89): Should be 7-12%
        - Score 7-7.9 (70-79): Should be 5-8%

        Thematic position rules:
        - Score 35-40: Should be 5-7% (max)
        - Score 30-34: Should be 3-5%
        - Score 28-29: Should be 2-3%

        Violations:
        - CRITICAL: Position >20% (concentration risk), thematic position >7%
        - WARNING: Position outside recommended range by >2%
        - INFO: Position slightly outside range (<2%)

        Args:
            holdings: Dictionary mapping tickers to current position %
            quality_scores: Dictionary mapping tickers to quality scores
            thematic_scores: Dictionary mapping tickers to thematic scores

        Returns:
            List of Violation objects
        """
        violations = []

        for ticker, current_pct in holdings.items():
            # Check if this is a quality or thematic holding
            quality_score = quality_scores.get(ticker)
            thematic_score = thematic_scores.get(ticker)

            # Concentration risk check (applies to all holdings)
            if current_pct > self.MAX_POSITION:
                violations.append(Violation(
                    severity="CRITICAL",
                    category="CONCENTRATION",
                    ticker=ticker,
                    message=f"{ticker} position {current_pct:.1f}% exceeds maximum 20% (concentration risk)",
                    current_value=current_pct,
                    expected_value=self.MAX_POSITION
                ))

            # Quality holdings validation
            if quality_score is not None and quality_score >= 70:  # Quality holding
                # Determine expected range based on quality score
                if quality_score >= 90:
                    min_pct, max_pct = 10.0, 20.0
                    score_range = "9-10 (90-100)"
                elif quality_score >= 80:
                    min_pct, max_pct = 7.0, 12.0
                    score_range = "8-8.9 (80-89)"
                else:  # 70-79
                    min_pct, max_pct = 5.0, 8.0
                    score_range = "7-7.9 (70-79)"

                # Check if position is outside recommended range
                if current_pct < min_pct - 2.0:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} position {current_pct:.1f}% significantly below range {min_pct}-{max_pct}% for quality score {score_range}",
                        current_value=current_pct,
                        expected_value=min_pct
                    ))
                elif current_pct < min_pct:
                    violations.append(Violation(
                        severity="INFO",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} position {current_pct:.1f}% slightly below range {min_pct}-{max_pct}% for quality score {score_range}",
                        current_value=current_pct,
                        expected_value=min_pct
                    ))
                elif current_pct > max_pct + 2.0:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} position {current_pct:.1f}% significantly above range {min_pct}-{max_pct}% for quality score {score_range}",
                        current_value=current_pct,
                        expected_value=max_pct
                    ))
                elif current_pct > max_pct:
                    violations.append(Violation(
                        severity="INFO",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} position {current_pct:.1f}% slightly above range {min_pct}-{max_pct}% for quality score {score_range}",
                        current_value=current_pct,
                        expected_value=max_pct
                    ))

            # Thematic holdings validation
            elif thematic_score is not None and thematic_score >= 28:  # Thematic holding
                # Check maximum thematic position size
                if current_pct > self.MAX_THEMATIC_POSITION:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} thematic position {current_pct:.1f}% exceeds maximum 7% for opportunistic holdings",
                        current_value=current_pct,
                        expected_value=self.MAX_THEMATIC_POSITION
                    ))

                # Determine expected range based on thematic score
                if thematic_score >= 35:
                    min_pct, max_pct = 5.0, 7.0
                    score_range = "35-40"
                elif thematic_score >= 30:
                    min_pct, max_pct = 3.0, 5.0
                    score_range = "30-34"
                else:  # 28-29
                    min_pct, max_pct = 2.0, 3.0
                    score_range = "28-29"

                # Check if position is outside recommended range
                if current_pct < min_pct - 1.0:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} thematic position {current_pct:.1f}% below range {min_pct}-{max_pct}% for thematic score {score_range}",
                        current_value=current_pct,
                        expected_value=min_pct
                    ))
                elif current_pct > max_pct + 1.0:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} thematic position {current_pct:.1f}% above range {min_pct}-{max_pct}% for thematic score {score_range}",
                        current_value=current_pct,
                        expected_value=max_pct
                    ))

        return violations

    def validate_quality_thresholds(
        self,
        holdings: Dict[str, str],  # ticker → type (QUALITY or THEMATIC)
        quality_scores: Dict[str, float]  # ticker → quality score (0-100)
    ) -> List[Violation]:
        """
        Validate all quality holdings meet minimum threshold

        Rules:
        - Quality holdings must have score ≥70 (7.0 on 10-point scale)
        - Thematic holdings exempt from quality threshold

        Violations:
        - CRITICAL: Quality holding with score <70 (exit immediately)
        - WARNING: Quality holding with score 70-75 (monitor closely)

        Args:
            holdings: Dictionary mapping tickers to type (QUALITY or THEMATIC)
            quality_scores: Dictionary mapping tickers to quality scores

        Returns:
            List of Violation objects
        """
        violations = []

        for ticker, holding_type in holdings.items():
            if holding_type == "QUALITY":
                quality_score = quality_scores.get(ticker)

                if quality_score is None:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="THRESHOLD",
                        ticker=ticker,
                        message=f"{ticker} quality score unavailable (cannot validate threshold)",
                        current_value=0.0,
                        expected_value=self.QUALITY_THRESHOLD * 10  # Convert to 0-100 scale
                    ))
                elif quality_score < self.QUALITY_THRESHOLD * 10:  # 70 on 0-100 scale
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="THRESHOLD",
                        ticker=ticker,
                        message=f"{ticker} quality score {quality_score:.1f}/100 below threshold 70 (exit immediately)",
                        current_value=quality_score,
                        expected_value=self.QUALITY_THRESHOLD * 10
                    ))
                elif quality_score < 75:  # 7.5 on 10-point scale
                    violations.append(Violation(
                        severity="WARNING",
                        category="THRESHOLD",
                        ticker=ticker,
                        message=f"{ticker} quality score {quality_score:.1f}/100 near threshold (monitor closely)",
                        current_value=quality_score,
                        expected_value=75.0
                    ))

        return violations

    def validate_thematic_thresholds(
        self,
        thematic_holdings: List[str],  # List of thematic ticker symbols
        thematic_scores: Dict[str, float]  # ticker → thematic score (0-40)
    ) -> List[Violation]:
        """
        Validate all thematic holdings meet minimum threshold

        Rules:
        - Thematic holdings must have score ≥28/40

        Violations:
        - CRITICAL: Thematic holding with score <28 (exit immediately)
        - WARNING: Thematic holding with score 28-30 (risky, monitor)

        Args:
            thematic_holdings: List of thematic ticker symbols
            thematic_scores: Dictionary mapping tickers to thematic scores

        Returns:
            List of Violation objects
        """
        violations = []

        for ticker in thematic_holdings:
            thematic_score = thematic_scores.get(ticker)

            if thematic_score is None:
                violations.append(Violation(
                    severity="CRITICAL",
                    category="THRESHOLD",
                    ticker=ticker,
                    message=f"{ticker} thematic score unavailable (cannot validate threshold)",
                    current_value=0.0,
                    expected_value=self.THEMATIC_THRESHOLD
                ))
            elif thematic_score < self.THEMATIC_THRESHOLD:
                violations.append(Violation(
                    severity="CRITICAL",
                    category="THRESHOLD",
                    ticker=ticker,
                    message=f"{ticker} thematic score {thematic_score:.1f}/40 below threshold 28 (exit immediately)",
                    current_value=thematic_score,
                    expected_value=self.THEMATIC_THRESHOLD
                ))
            elif thematic_score < 30:
                violations.append(Violation(
                    severity="WARNING",
                    category="THRESHOLD",
                    ticker=ticker,
                    message=f"{ticker} thematic score {thematic_score:.1f}/40 near threshold (risky, monitor closely)",
                    current_value=thematic_score,
                    expected_value=30.0
                ))

        return violations

    def calculate_compliance_score(self, violations: List[Violation]) -> float:
        """
        Calculate overall compliance score (0-100%)

        Score calculation:
        - Start at 100
        - -20 for each CRITICAL violation
        - -5 for each WARNING violation
        - -1 for each INFO violation
        - Minimum 0

        Args:
            violations: List of Violation objects

        Returns:
            Score from 0-100
        """
        score = 100.0

        for violation in violations:
            if violation.severity == "CRITICAL":
                score -= 20.0
            elif violation.severity == "WARNING":
                score -= 5.0
            elif violation.severity == "INFO":
                score -= 1.0

        # Ensure score is non-negative
        score = max(0.0, score)

        return score

    def validate_portfolio(
        self,
        portfolio_state: Dict,  # Portfolio state dict
        quality_scores: Dict[str, float],  # ticker → quality score (0-100)
        thematic_scores: Dict[str, float],  # ticker → thematic score (0-40)
        holdings_types: Optional[Dict[str, str]] = None  # ticker → QUALITY or THEMATIC
    ) -> ComplianceReport:
        """
        Main method: Full framework validation

        Run all validation checks:
        1. 80/20 allocation
        2. Position sizing
        3. Quality thresholds
        4. Thematic thresholds
        5. Concentration risk (any position >20%)

        Combine all violations into ComplianceReport
        Calculate compliance score

        Args:
            portfolio_state: Portfolio state dictionary
            quality_scores: Dictionary of quality scores
            thematic_scores: Dictionary of thematic scores
            holdings_types: Optional dict mapping tickers to QUALITY or THEMATIC

        Returns:
            ComplianceReport object
        """
        logger.info("Validating framework compliance...")

        # Extract portfolio data
        holdings = portfolio_state.get('holdings', {})
        cash = portfolio_state.get('cash', 0.0)

        # Calculate portfolio value
        total_holdings_value = sum(holdings.values())
        portfolio_value = total_holdings_value + cash

        if portfolio_value == 0:
            logger.warning("Portfolio value is zero, cannot validate")
            return ComplianceReport(
                portfolio_value=0.0,
                compliance_score=0.0,
                violations=[],
                allocation_quality_pct=0.0,
                allocation_thematic_pct=0.0,
                allocation_cash_pct=0.0,
                framework_compliant=False,
                validation_date=datetime.now().strftime('%Y-%m-%d')
            )

        # Classify holdings as quality or thematic if not provided
        if holdings_types is None:
            holdings_types = {}
            for ticker in holdings.keys():
                quality_score = quality_scores.get(ticker, 0)
                thematic_score = thematic_scores.get(ticker, 0)

                # Quality holdings have score ≥70
                if quality_score >= 70:
                    holdings_types[ticker] = "QUALITY"
                # Thematic holdings have score ≥28
                elif thematic_score >= 28:
                    holdings_types[ticker] = "THEMATIC"
                else:
                    # Below both thresholds - classify as quality for validation purposes
                    holdings_types[ticker] = "QUALITY"

        # Calculate allocations
        quality_value = sum(
            value for ticker, value in holdings.items()
            if holdings_types.get(ticker) == "QUALITY"
        )
        thematic_value = sum(
            value for ticker, value in holdings.items()
            if holdings_types.get(ticker) == "THEMATIC"
        )

        allocation_quality_pct = (quality_value / portfolio_value) * 100
        allocation_thematic_pct = (thematic_value / portfolio_value) * 100
        allocation_cash_pct = (cash / portfolio_value) * 100

        # Calculate position percentages
        position_pcts = {
            ticker: (value / portfolio_value) * 100
            for ticker, value in holdings.items()
        }

        # Run all validations
        all_violations = []

        # 1. Validate 80/20 allocation
        all_violations.extend(self.validate_80_20_allocation(
            allocation_quality_pct, allocation_thematic_pct, allocation_cash_pct
        ))

        # 2. Validate position sizing
        all_violations.extend(self.validate_position_sizing(
            position_pcts, quality_scores, thematic_scores
        ))

        # 3. Validate quality thresholds
        all_violations.extend(self.validate_quality_thresholds(
            holdings_types, quality_scores
        ))

        # 4. Validate thematic thresholds
        thematic_holdings = [
            ticker for ticker, type_ in holdings_types.items()
            if type_ == "THEMATIC"
        ]
        all_violations.extend(self.validate_thematic_thresholds(
            thematic_holdings, thematic_scores
        ))

        # Calculate compliance score
        compliance_score = self.calculate_compliance_score(all_violations)

        # Check if framework compliant (no CRITICAL violations)
        critical_violations = [v for v in all_violations if v.severity == "CRITICAL"]
        framework_compliant = len(critical_violations) == 0

        report = ComplianceReport(
            portfolio_value=portfolio_value,
            compliance_score=compliance_score,
            violations=all_violations,
            allocation_quality_pct=allocation_quality_pct,
            allocation_thematic_pct=allocation_thematic_pct,
            allocation_cash_pct=allocation_cash_pct,
            framework_compliant=framework_compliant,
            validation_date=datetime.now().strftime('%Y-%m-%d')
        )

        logger.info(f"Framework compliance: {compliance_score:.1f}/100")
        logger.info(f"  - CRITICAL violations: {len(critical_violations)}")
        logger.info(f"  - WARNING violations: {len([v for v in all_violations if v.severity == 'WARNING'])}")
        logger.info(f"  - INFO violations: {len([v for v in all_violations if v.severity == 'INFO'])}")
        logger.info(f"  - Framework compliant: {framework_compliant}")

        return report

    def generate_compliance_report_markdown(self, report: ComplianceReport) -> str:
        """
        Generate markdown compliance report

        Args:
            report: ComplianceReport object

        Returns:
            Markdown formatted report
        """
        lines = []
        lines.append("# Framework Compliance Report")
        lines.append("")
        lines.append(f"**Validation Date**: {report.validation_date}")
        lines.append(f"**Portfolio Value**: ${report.portfolio_value:,.2f}")
        lines.append("")

        # Compliance Score Section
        lines.append(f"## Compliance Score: {report.compliance_score:.0f}/100")
        if report.framework_compliant:
            lines.append("**Status**: ✅ COMPLIANT (no critical violations)")
        else:
            lines.append("**Status**: ❌ NON-COMPLIANT (critical violations present)")
        lines.append("")

        # Allocation Summary
        lines.append("## Allocation Summary")
        lines.append(f"- **Quality Holdings**: {report.allocation_quality_pct:.1f}% (target 80%, range 75-85%) " +
                    ("✅" if 75 <= report.allocation_quality_pct <= 85 else "⚠️"))
        lines.append(f"- **Opportunistic Holdings**: {report.allocation_thematic_pct:.1f}% (target 20%, range 15-25%) " +
                    ("✅" if 15 <= report.allocation_thematic_pct <= 25 else "⚠️"))
        lines.append(f"- **Cash Reserve**: {report.allocation_cash_pct:.1f}% (minimum 3%, recommended 5%) " +
                    ("✅" if report.allocation_cash_pct >= 3 else "⚠️"))
        lines.append("")

        # Violations Section
        lines.append("## Violations")
        lines.append("")

        # Group violations by severity
        critical = [v for v in report.violations if v.severity == "CRITICAL"]
        warnings = [v for v in report.violations if v.severity == "WARNING"]
        info = [v for v in report.violations if v.severity == "INFO"]

        # CRITICAL violations
        lines.append(f"### CRITICAL ({len(critical)})")
        if critical:
            for v in critical:
                ticker_str = f"**{v.ticker}**: " if v.ticker else ""
                lines.append(f"- ❌ {ticker_str}{v.message}")
        else:
            lines.append("None")
        lines.append("")

        # WARNING violations
        lines.append(f"### WARNING ({len(warnings)})")
        if warnings:
            for v in warnings:
                ticker_str = f"**{v.ticker}**: " if v.ticker else ""
                lines.append(f"- ⚠️ {ticker_str}{v.message}")
        else:
            lines.append("None")
        lines.append("")

        # INFO violations
        lines.append(f"### INFO ({len(info)})")
        if info:
            for v in info:
                ticker_str = f"**{v.ticker}**: " if v.ticker else ""
                lines.append(f"- ℹ️ {ticker_str}{v.message}")
        else:
            lines.append("None")
        lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        if report.framework_compliant:
            lines.append("✅ Portfolio is in compliance with framework. Address warnings and info items as appropriate.")
        else:
            lines.append("❌ **Critical violations must be resolved immediately:**")
            for i, v in enumerate(critical, 1):
                ticker_str = f"{v.ticker}: " if v.ticker else ""
                lines.append(f"{i}. {ticker_str}{v.message}")

        lines.append("")

        return "\n".join(lines)

    def export_to_json(self, report: ComplianceReport, output_file: str):
        """
        Export compliance report to JSON

        Args:
            report: ComplianceReport object
            output_file: Output file path
        """
        with open(output_file, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(f"Compliance report exported to {output_file}")


def main():
    """
    Test FrameworkValidator with sample portfolio
    """
    validator = FrameworkValidator()

    # Sample portfolio state
    portfolio_state = {
        'holdings': {
            'NVDA': 15000,  # 15% if portfolio is 100k
            'GOOGL': 12000,  # 12%
            'MSFT': 10000,  # 10%
            'META': 8000,   # 8%
            'AMD': 3000,    # 3%
        },
        'cash': 5000  # 5%
    }

    # Sample quality scores (0-100 scale)
    quality_scores = {
        'NVDA': 90,
        'GOOGL': 85,
        'MSFT': 88,
        'META': 82,
        'AMD': 65  # Below threshold
    }

    # Sample thematic scores (0-40 scale)
    thematic_scores = {
        'NVDA': 0,
        'GOOGL': 0,
        'MSFT': 0,
        'META': 0,
        'AMD': 25  # Below threshold
    }

    print("Testing FrameworkValidator...")
    print(f"Portfolio value: ${sum(portfolio_state['holdings'].values()) + portfolio_state['cash']:,.2f}")
    print()

    # Run validation
    report = validator.validate_portfolio(
        portfolio_state,
        quality_scores,
        thematic_scores
    )

    # Print summary
    print("\nCompliance Results:")
    print("-" * 80)
    print(f"Compliance Score: {report.compliance_score:.0f}/100")
    print(f"Framework Compliant: {report.framework_compliant}")
    print(f"CRITICAL violations: {len([v for v in report.violations if v.severity == 'CRITICAL'])}")
    print(f"WARNING violations: {len([v for v in report.violations if v.severity == 'WARNING'])}")
    print(f"INFO violations: {len([v for v in report.violations if v.severity == 'INFO'])}")
    print()

    # Print violations
    if report.violations:
        print("Violations:")
        for v in report.violations:
            ticker_str = f"[{v.ticker}] " if v.ticker else ""
            print(f"  {v.severity}: {ticker_str}{v.message}")
    print()

    # Generate and save markdown report
    markdown = validator.generate_compliance_report_markdown(report)
    with open("outputs/compliance_test_report.md", 'w') as f:
        f.write(markdown)

    # Export to JSON
    validator.export_to_json(report, "outputs/compliance_test_report.json")

    print("Export complete!")
    print("  - Markdown: outputs/compliance_test_report.md")
    print("  - JSON: outputs/compliance_test_report.json")


if __name__ == "__main__":
    main()
