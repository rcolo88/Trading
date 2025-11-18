"""
Framework Compliance Validator - 4-Tier Market Cap Framework

This module implements framework compliance validation for the 4-tier market cap system
following quality_investing_thresholds_research.md:
- Core Holdings (65-70%): Large cap ($50B+) with 5+ years ROE >15%
- Growth Quality (15-20%): Mid cap ($2B-$50B) with 2-3 years ROE >15%
- Opportunistic Quality (10-15%): Small cap ($500M-$2B) with strict quality filters
- High Risk/Thematic (5-10%): Momentum plays and thematic investments

Author: Claude Code
Date: November 6, 2025
Reference: quality_investing_thresholds_research.md
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

# Import market cap tier enum
from quality.market_cap_classifier import MarketCapTier

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Violation:
    """
    Represents a single framework compliance violation
    """
    severity: str  # CRITICAL, WARNING, INFO
    category: str  # ALLOCATION, POSITION_SIZE, TIER_ELIGIBILITY, CONCENTRATION
    ticker: Optional[str]  # None for portfolio-level violations
    message: str
    current_value: float
    expected_value: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return asdict(self)


@dataclass
class TieredComplianceReport:
    """
    Comprehensive 4-tier framework compliance assessment
    """
    portfolio_value: float
    compliance_score: float  # 0-100
    violations: List[Violation]
    allocation_large_cap_pct: float
    allocation_mid_cap_pct: float
    allocation_small_cap_pct: float
    allocation_thematic_pct: float
    allocation_cash_pct: float
    tier_eligibility_issues: List[str]  # Holdings in wrong tiers
    framework_compliant: bool  # True if no CRITICAL violations
    validation_date: str  # ISO format

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export"""
        return {
            "portfolio_value": self.portfolio_value,
            "compliance_score": self.compliance_score,
            "violations": [v.to_dict() for v in self.violations],
            "allocation_large_cap_pct": self.allocation_large_cap_pct,
            "allocation_mid_cap_pct": self.allocation_mid_cap_pct,
            "allocation_small_cap_pct": self.allocation_small_cap_pct,
            "allocation_thematic_pct": self.allocation_thematic_pct,
            "allocation_cash_pct": self.allocation_cash_pct,
            "tier_eligibility_issues": self.tier_eligibility_issues,
            "framework_compliant": self.framework_compliant,
            "validation_date": self.validation_date
        }


class FrameworkValidator:
    """
    Validates portfolio compliance with 4-tier market cap framework

    Responsibilities:
    - Validate 4-tier allocation (65-70/15-20/10-15/5-10)
    - Validate tier-specific position sizing
    - Validate tier eligibility (ROE persistence, strict filters)
    - Calculate compliance score (0-100)
    - Generate compliance reports
    """

    # 4-Tier allocation targets and ranges (from research)
    LARGE_CAP_MIN = 62.5  # 67.5% ± 2.5%
    LARGE_CAP_MAX = 72.5
    LARGE_CAP_TARGET = 67.5

    MID_CAP_MIN = 12.5  # 17.5% ± 2.5%
    MID_CAP_MAX = 22.5
    MID_CAP_TARGET = 17.5

    SMALL_CAP_MIN = 7.5  # 12.5% ± 2.5%
    SMALL_CAP_MAX = 17.5
    SMALL_CAP_TARGET = 12.5

    THEMATIC_MIN = 2.5  # 7.5% ± 2.5%
    THEMATIC_MAX = 12.5
    THEMATIC_TARGET = 7.5

    CASH_MIN = 3.0  # Minimum cash reserve
    CASH_RECOMMENDED = 5.0  # Recommended cash reserve

    # Tier-specific position limits (from research)
    MAX_LARGE_CAP_POSITION = 15.0  # 15% max for large cap
    MAX_MID_CAP_POSITION = 10.0    # 10% max for mid cap
    MAX_SMALL_CAP_POSITION = 4.0   # 4% max for small cap (2% typical, 4% absolute max)
    MAX_THEMATIC_POSITION = 2.5    # 2.5% max for thematic

    # ROE persistence requirements by tier
    LARGE_CAP_ROE_YEARS = 5  # 5+ consecutive years ROE >15%
    MID_CAP_ROE_YEARS = 2    # 2-3 consecutive years ROE >15%
    SMALL_CAP_ROE_QUARTERS = 6  # 6-8 quarters positive ROE trend

    def __init__(self):
        """Initialize FrameworkValidator"""
        self.validation_cache: Dict[str, TieredComplianceReport] = {}
        logger.info("FrameworkValidator initialized (4-Tier Market Cap Framework)")

    def validate_4_tier_allocation(
        self,
        allocation_large_cap_pct: float,
        allocation_mid_cap_pct: float,
        allocation_small_cap_pct: float,
        allocation_thematic_pct: float,
        allocation_cash_pct: float
    ) -> List[Violation]:
        """
        Validate 4-tier market cap framework compliance

        Rules (from research):
        - Large cap (Core): 65-70% (67.5% ± 2.5%)
        - Mid cap (Growth): 15-20% (17.5% ± 2.5%)
        - Small cap (Opportunistic): 10-15% (12.5% ± 2.5%)
        - Thematic (High Risk): 5-10% (7.5% ± 2.5%)
        - Cash reserve: ≥3% (5% recommended)

        Violations:
        - CRITICAL: Tier <min-5% or >max+5%, Cash <2%
        - WARNING: Tier outside ±2.5% range, Cash 2-3%
        - INFO: Minor deviations

        Args:
            allocation_large_cap_pct: % allocated to large cap holdings
            allocation_mid_cap_pct: % allocated to mid cap holdings
            allocation_small_cap_pct: % allocated to small cap holdings
            allocation_thematic_pct: % allocated to thematic holdings
            allocation_cash_pct: % in cash

        Returns:
            List of Violation objects
        """
        violations = []

        # Validate large cap allocation
        if allocation_large_cap_pct < self.LARGE_CAP_MIN - 5.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Large cap allocation {allocation_large_cap_pct:.1f}% far below minimum {self.LARGE_CAP_MIN:.1f}% (critical underweight)",
                current_value=allocation_large_cap_pct,
                expected_value=self.LARGE_CAP_MIN
            ))
        elif allocation_large_cap_pct < self.LARGE_CAP_MIN:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Large cap allocation {allocation_large_cap_pct:.1f}% below minimum {self.LARGE_CAP_MIN:.1f}% (rebalance needed)",
                current_value=allocation_large_cap_pct,
                expected_value=self.LARGE_CAP_MIN
            ))
        elif allocation_large_cap_pct > self.LARGE_CAP_MAX + 5.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Large cap allocation {allocation_large_cap_pct:.1f}% far above maximum {self.LARGE_CAP_MAX:.1f}% (critical overweight)",
                current_value=allocation_large_cap_pct,
                expected_value=self.LARGE_CAP_MAX
            ))
        elif allocation_large_cap_pct > self.LARGE_CAP_MAX:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Large cap allocation {allocation_large_cap_pct:.1f}% above maximum {self.LARGE_CAP_MAX:.1f}% (rebalance needed)",
                current_value=allocation_large_cap_pct,
                expected_value=self.LARGE_CAP_MAX
            ))

        # Validate mid cap allocation
        if allocation_mid_cap_pct < self.MID_CAP_MIN - 5.0:
            violations.append(Violation(
                severity="CRITICAL",
                category="ALLOCATION",
                ticker=None,
                message=f"Mid cap allocation {allocation_mid_cap_pct:.1f}% far below minimum {self.MID_CAP_MIN:.1f}%",
                current_value=allocation_mid_cap_pct,
                expected_value=self.MID_CAP_MIN
            ))
        elif allocation_mid_cap_pct < self.MID_CAP_MIN:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Mid cap allocation {allocation_mid_cap_pct:.1f}% below minimum {self.MID_CAP_MIN:.1f}%",
                current_value=allocation_mid_cap_pct,
                expected_value=self.MID_CAP_MIN
            ))
        elif allocation_mid_cap_pct > self.MID_CAP_MAX:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Mid cap allocation {allocation_mid_cap_pct:.1f}% above maximum {self.MID_CAP_MAX:.1f}%",
                current_value=allocation_mid_cap_pct,
                expected_value=self.MID_CAP_MAX
            ))

        # Validate small cap allocation
        if allocation_small_cap_pct < self.SMALL_CAP_MIN:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Small cap allocation {allocation_small_cap_pct:.1f}% below minimum {self.SMALL_CAP_MIN:.1f}%",
                current_value=allocation_small_cap_pct,
                expected_value=self.SMALL_CAP_MIN
            ))
        elif allocation_small_cap_pct > self.SMALL_CAP_MAX:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Small cap allocation {allocation_small_cap_pct:.1f}% above maximum {self.SMALL_CAP_MAX:.1f}%",
                current_value=allocation_small_cap_pct,
                expected_value=self.SMALL_CAP_MAX
            ))

        # Validate thematic allocation
        if allocation_thematic_pct < self.THEMATIC_MIN:
            violations.append(Violation(
                severity="INFO",
                category="ALLOCATION",
                ticker=None,
                message=f"Thematic allocation {allocation_thematic_pct:.1f}% below minimum {self.THEMATIC_MIN:.1f}% (consider increasing)",
                current_value=allocation_thematic_pct,
                expected_value=self.THEMATIC_MIN
            ))
        elif allocation_thematic_pct > self.THEMATIC_MAX:
            violations.append(Violation(
                severity="WARNING",
                category="ALLOCATION",
                ticker=None,
                message=f"Thematic allocation {allocation_thematic_pct:.1f}% above maximum {self.THEMATIC_MAX:.1f}%",
                current_value=allocation_thematic_pct,
                expected_value=self.THEMATIC_MAX
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
                message=f"Cash reserve {allocation_cash_pct:.1f}% below minimum 3%",
                current_value=allocation_cash_pct,
                expected_value=self.CASH_MIN
            ))
        elif allocation_cash_pct < self.CASH_RECOMMENDED:
            violations.append(Violation(
                severity="INFO",
                category="ALLOCATION",
                ticker=None,
                message=f"Cash reserve {allocation_cash_pct:.1f}% below recommended 5%",
                current_value=allocation_cash_pct,
                expected_value=self.CASH_RECOMMENDED
            ))

        return violations

    def validate_tier_position_sizing(
        self,
        holdings: Dict[str, float],  # ticker → current %
        holdings_tiers: Dict[str, str]  # ticker → tier (LARGE_CAP, MID_CAP, SMALL_CAP, THEMATIC)
    ) -> List[Violation]:
        """
        Validate position sizes match tier-specific limits

        Position limits by tier (from research):
        - Large cap: Max 15%
        - Mid cap: Max 10%
        - Small cap: Max 4% (2% typical, 4% absolute max)
        - Thematic: Max 2.5%

        Violations:
        - CRITICAL: Position exceeds tier limit
        - WARNING: Position near limit (within 0.5%)

        Args:
            holdings: Dictionary mapping tickers to current position %
            holdings_tiers: Dictionary mapping tickers to tier

        Returns:
            List of Violation objects
        """
        violations = []

        for ticker, current_pct in holdings.items():
            tier = holdings_tiers.get(ticker)

            if tier == 'LARGE_CAP':
                if current_pct > self.MAX_LARGE_CAP_POSITION:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} large cap position {current_pct:.1f}% exceeds maximum {self.MAX_LARGE_CAP_POSITION:.0f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_LARGE_CAP_POSITION
                    ))
                elif current_pct > self.MAX_LARGE_CAP_POSITION - 0.5:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} large cap position {current_pct:.1f}% near maximum {self.MAX_LARGE_CAP_POSITION:.0f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_LARGE_CAP_POSITION
                    ))

            elif tier == 'MID_CAP':
                if current_pct > self.MAX_MID_CAP_POSITION:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} mid cap position {current_pct:.1f}% exceeds maximum {self.MAX_MID_CAP_POSITION:.0f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_MID_CAP_POSITION
                    ))
                elif current_pct > self.MAX_MID_CAP_POSITION - 0.5:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} mid cap position {current_pct:.1f}% near maximum {self.MAX_MID_CAP_POSITION:.0f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_MID_CAP_POSITION
                    ))

            elif tier == 'SMALL_CAP':
                if current_pct > self.MAX_SMALL_CAP_POSITION:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} small cap position {current_pct:.1f}% exceeds maximum {self.MAX_SMALL_CAP_POSITION:.0f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_SMALL_CAP_POSITION
                    ))
                elif current_pct > self.MAX_SMALL_CAP_POSITION - 0.5:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} small cap position {current_pct:.1f}% near maximum {self.MAX_SMALL_CAP_POSITION:.0f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_SMALL_CAP_POSITION
                    ))

            elif tier == 'THEMATIC':
                if current_pct > self.MAX_THEMATIC_POSITION:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} thematic position {current_pct:.1f}% exceeds maximum {self.MAX_THEMATIC_POSITION:.1f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_THEMATIC_POSITION
                    ))
                elif current_pct > self.MAX_THEMATIC_POSITION - 0.5:
                    violations.append(Violation(
                        severity="WARNING",
                        category="POSITION_SIZE",
                        ticker=ticker,
                        message=f"{ticker} thematic position {current_pct:.1f}% near maximum {self.MAX_THEMATIC_POSITION:.1f}%",
                        current_value=current_pct,
                        expected_value=self.MAX_THEMATIC_POSITION
                    ))

        return violations

    def validate_tier_eligibility(
        self,
        holdings_tiers: Dict[str, str],  # ticker → tier
        roe_persistence: Dict[str, Dict],  # ticker → {years: float, meets_requirement: bool}
        small_cap_filters: Dict[str, Dict]  # ticker → {passes: bool, failed_filters: List[str]}
    ) -> Tuple[List[Violation], List[str]]:
        """
        Validate holdings meet tier eligibility requirements

        Rules (from research):
        - Large cap: 5+ consecutive years ROE >15%
        - Mid cap: 2-3 consecutive years ROE >15%
        - Small cap: 6-8 quarters positive ROE trend + strict quality filters (FCF+, D/E<1.0, GP>30%)
        - Thematic: No specific ROE requirements

        Violations:
        - CRITICAL: Holding in tier but fails requirements
        - WARNING: Holding marginally meets requirements

        Args:
            holdings_tiers: Dictionary mapping tickers to tier
            roe_persistence: Dictionary mapping tickers to ROE persistence data
            small_cap_filters: Dictionary mapping tickers to small cap filter results

        Returns:
            Tuple of (violations list, tier_eligibility_issues list)
        """
        violations = []
        tier_eligibility_issues = []

        for ticker, tier in holdings_tiers.items():
            if tier == 'LARGE_CAP':
                roe_data = roe_persistence.get(ticker, {})
                meets_requirement = roe_data.get('meets_requirement', False)
                years = roe_data.get('years', 0)

                if not meets_requirement:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="TIER_ELIGIBILITY",
                        ticker=ticker,
                        message=f"{ticker} large cap fails 5+ year ROE >15% requirement ({years:.1f} years)",
                        current_value=years,
                        expected_value=self.LARGE_CAP_ROE_YEARS
                    ))
                    tier_eligibility_issues.append(f"{ticker}: Large cap without 5yr ROE persistence")
                elif years < self.LARGE_CAP_ROE_YEARS + 1:
                    violations.append(Violation(
                        severity="WARNING",
                        category="TIER_ELIGIBILITY",
                        ticker=ticker,
                        message=f"{ticker} large cap marginally meets requirement ({years:.1f} years, prefer 6+)",
                        current_value=years,
                        expected_value=self.LARGE_CAP_ROE_YEARS + 1
                    ))

            elif tier == 'MID_CAP':
                roe_data = roe_persistence.get(ticker, {})
                meets_requirement = roe_data.get('meets_requirement', False)
                years = roe_data.get('years', 0)

                if not meets_requirement:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="TIER_ELIGIBILITY",
                        ticker=ticker,
                        message=f"{ticker} mid cap fails 2-3 year ROE >15% requirement ({years:.1f} years)",
                        current_value=years,
                        expected_value=self.MID_CAP_ROE_YEARS
                    ))
                    tier_eligibility_issues.append(f"{ticker}: Mid cap without 2-3yr ROE persistence")

            elif tier == 'SMALL_CAP':
                # Check ROE trend
                roe_data = roe_persistence.get(ticker, {})
                meets_roe = roe_data.get('meets_requirement', False)
                quarters = roe_data.get('quarters', 0)

                if not meets_roe:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="TIER_ELIGIBILITY",
                        ticker=ticker,
                        message=f"{ticker} small cap fails 6-8 quarter positive ROE trend ({quarters:.0f} quarters)",
                        current_value=quarters,
                        expected_value=self.SMALL_CAP_ROE_QUARTERS
                    ))
                    tier_eligibility_issues.append(f"{ticker}: Small cap without positive ROE trend")

                # Check strict quality filters
                filter_data = small_cap_filters.get(ticker, {})
                passes_filters = filter_data.get('passes', False)
                failed_filters = filter_data.get('failed_filters', [])

                if not passes_filters:
                    violations.append(Violation(
                        severity="CRITICAL",
                        category="TIER_ELIGIBILITY",
                        ticker=ticker,
                        message=f"{ticker} small cap fails strict quality filters: {', '.join(failed_filters)}",
                        current_value=0.0,
                        expected_value=1.0
                    ))
                    tier_eligibility_issues.append(f"{ticker}: Small cap fails filters ({', '.join(failed_filters)})")

        return violations, tier_eligibility_issues

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
        holdings_tiers: Dict[str, str],  # ticker → tier (LARGE_CAP, MID_CAP, SMALL_CAP, THEMATIC)
        roe_persistence: Optional[Dict[str, Dict]] = None,  # ticker → ROE persistence data
        small_cap_filters: Optional[Dict[str, Dict]] = None  # ticker → small cap filter results
    ) -> TieredComplianceReport:
        """
        Main method: Full 4-tier framework validation

        Run all validation checks:
        1. 4-tier allocation
        2. Tier-specific position sizing
        3. Tier eligibility (ROE persistence, strict filters)
        4. Concentration risk

        Combine all violations into TieredComplianceReport
        Calculate compliance score

        Args:
            portfolio_state: Portfolio state dictionary
            holdings_tiers: Dictionary mapping tickers to tiers
            roe_persistence: Optional ROE persistence data
            small_cap_filters: Optional small cap filter results

        Returns:
            TieredComplianceReport object
        """
        logger.info("Validating 4-tier framework compliance...")

        # Extract portfolio data
        holdings = portfolio_state.get('holdings', {})
        cash = portfolio_state.get('cash', 0.0)

        # Handle two portfolio_state formats:
        # 1. New format: {ticker: {shares, entry_price, allocation}}
        # 2. Old format: {ticker: dollar_value}
        holdings_values = {}
        for ticker, value in holdings.items():
            if isinstance(value, dict):
                # New format - extract allocation (dollar value)
                holdings_values[ticker] = value.get('allocation', 0.0)
            else:
                # Old format - value is already a float
                holdings_values[ticker] = float(value)

        # Calculate portfolio value
        total_holdings_value = sum(holdings_values.values())
        portfolio_value = total_holdings_value + cash

        if portfolio_value == 0:
            logger.warning("Portfolio value is zero, cannot validate")
            return TieredComplianceReport(
                portfolio_value=0.0,
                compliance_score=0.0,
                violations=[],
                allocation_large_cap_pct=0.0,
                allocation_mid_cap_pct=0.0,
                allocation_small_cap_pct=0.0,
                allocation_thematic_pct=0.0,
                allocation_cash_pct=0.0,
                tier_eligibility_issues=[],
                framework_compliant=False,
                validation_date=datetime.now().strftime('%Y-%m-%d')
            )

        # Calculate tier allocations
        large_cap_value = sum(
            value for ticker, value in holdings_values.items()
            if holdings_tiers.get(ticker) == "LARGE_CAP"
        )
        mid_cap_value = sum(
            value for ticker, value in holdings_values.items()
            if holdings_tiers.get(ticker) == "MID_CAP"
        )
        small_cap_value = sum(
            value for ticker, value in holdings_values.items()
            if holdings_tiers.get(ticker) == "SMALL_CAP"
        )
        thematic_value = sum(
            value for ticker, value in holdings_values.items()
            if holdings_tiers.get(ticker) == "THEMATIC"
        )

        allocation_large_cap_pct = (large_cap_value / portfolio_value) * 100
        allocation_mid_cap_pct = (mid_cap_value / portfolio_value) * 100
        allocation_small_cap_pct = (small_cap_value / portfolio_value) * 100
        allocation_thematic_pct = (thematic_value / portfolio_value) * 100
        allocation_cash_pct = (cash / portfolio_value) * 100

        # Calculate position percentages
        position_pcts = {
            ticker: (value / portfolio_value) * 100
            for ticker, value in holdings_values.items()
        }

        # Run all validations
        all_violations = []

        # 1. Validate 4-tier allocation
        all_violations.extend(self.validate_4_tier_allocation(
            allocation_large_cap_pct, allocation_mid_cap_pct,
            allocation_small_cap_pct, allocation_thematic_pct, allocation_cash_pct
        ))

        # 2. Validate tier-specific position sizing
        all_violations.extend(self.validate_tier_position_sizing(
            position_pcts, holdings_tiers
        ))

        # 3. Validate tier eligibility (if data provided)
        tier_eligibility_issues = []
        if roe_persistence is not None and small_cap_filters is not None:
            eligibility_violations, issues = self.validate_tier_eligibility(
                holdings_tiers, roe_persistence, small_cap_filters
            )
            all_violations.extend(eligibility_violations)
            tier_eligibility_issues = issues

        # Calculate compliance score
        compliance_score = self.calculate_compliance_score(all_violations)

        # Check if framework compliant (no CRITICAL violations)
        critical_violations = [v for v in all_violations if v.severity == "CRITICAL"]
        framework_compliant = len(critical_violations) == 0

        report = TieredComplianceReport(
            portfolio_value=portfolio_value,
            compliance_score=compliance_score,
            violations=all_violations,
            allocation_large_cap_pct=allocation_large_cap_pct,
            allocation_mid_cap_pct=allocation_mid_cap_pct,
            allocation_small_cap_pct=allocation_small_cap_pct,
            allocation_thematic_pct=allocation_thematic_pct,
            allocation_cash_pct=allocation_cash_pct,
            tier_eligibility_issues=tier_eligibility_issues,
            framework_compliant=framework_compliant,
            validation_date=datetime.now().strftime('%Y-%m-%d')
        )

        logger.info(f"4-Tier framework compliance: {compliance_score:.1f}/100")
        logger.info(f"  - CRITICAL violations: {len(critical_violations)}")
        logger.info(f"  - WARNING violations: {len([v for v in all_violations if v.severity == 'WARNING'])}")
        logger.info(f"  - INFO violations: {len([v for v in all_violations if v.severity == 'INFO'])}")
        logger.info(f"  - Framework compliant: {framework_compliant}")

        return report

    def generate_compliance_report_markdown(self, report: TieredComplianceReport) -> str:
        """
        Generate markdown compliance report for 4-tier framework

        Args:
            report: TieredComplianceReport object

        Returns:
            Markdown formatted report
        """
        lines = []
        lines.append("# 4-Tier Framework Compliance Report")
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
        lines.append("## Tier Allocation Summary")
        lines.append(f"- **Large Cap (Core)**: {report.allocation_large_cap_pct:.1f}% (target 67.5%, range 62.5-72.5%) " +
                    ("✅" if self.LARGE_CAP_MIN <= report.allocation_large_cap_pct <= self.LARGE_CAP_MAX else "⚠️"))
        lines.append(f"- **Mid Cap (Growth)**: {report.allocation_mid_cap_pct:.1f}% (target 17.5%, range 12.5-22.5%) " +
                    ("✅" if self.MID_CAP_MIN <= report.allocation_mid_cap_pct <= self.MID_CAP_MAX else "⚠️"))
        lines.append(f"- **Small Cap (Opportunistic)**: {report.allocation_small_cap_pct:.1f}% (target 12.5%, range 7.5-17.5%) " +
                    ("✅" if self.SMALL_CAP_MIN <= report.allocation_small_cap_pct <= self.SMALL_CAP_MAX else "⚠️"))
        lines.append(f"- **Thematic (High Risk)**: {report.allocation_thematic_pct:.1f}% (target 7.5%, range 2.5-12.5%) " +
                    ("✅" if self.THEMATIC_MIN <= report.allocation_thematic_pct <= self.THEMATIC_MAX else "⚠️"))
        lines.append(f"- **Cash Reserve**: {report.allocation_cash_pct:.1f}% (minimum 3%, recommended 5%) " +
                    ("✅" if report.allocation_cash_pct >= 3 else "⚠️"))
        lines.append("")

        # Tier Eligibility Issues
        if report.tier_eligibility_issues:
            lines.append("## Tier Eligibility Issues")
            for issue in report.tier_eligibility_issues:
                lines.append(f"- ⚠️ {issue}")
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
            lines.append("✅ Portfolio is in compliance with 4-tier framework. Address warnings and info items as appropriate.")
        else:
            lines.append("❌ **Critical violations must be resolved immediately:**")
            for i, v in enumerate(critical, 1):
                ticker_str = f"{v.ticker}: " if v.ticker else ""
                lines.append(f"{i}. {ticker_str}{v.message}")

        lines.append("")

        return "\n".join(lines)

    def export_to_json(self, report: TieredComplianceReport, output_file: str):
        """
        Export compliance report to JSON

        Args:
            report: TieredComplianceReport object
            output_file: Output file path
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(f"4-tier compliance report exported to {output_file}")


def main():
    """
    Test FrameworkValidator with sample 4-tier portfolio
    """
    validator = FrameworkValidator()

    # Sample portfolio state
    portfolio_state = {
        'holdings': {
            'AAPL': 12000,   # 12% large cap
            'MSFT': 10000,   # 10% large cap
            'GOOGL': 8000,   # 8% large cap
            'NVDA': 5000,    # 5% mid cap
            'ARM': 3000,     # 3% mid cap
            'QS': 2000,      # 2% small cap
            'IONQ': 1500,    # 1.5% thematic
        },
        'cash': 5000  # 5%
    }

    # Holdings tier classification
    holdings_tiers = {
        'AAPL': 'LARGE_CAP',
        'MSFT': 'LARGE_CAP',
        'GOOGL': 'LARGE_CAP',
        'NVDA': 'MID_CAP',
        'ARM': 'MID_CAP',
        'QS': 'SMALL_CAP',
        'IONQ': 'THEMATIC'
    }

    # ROE persistence data (optional)
    roe_persistence = {
        'AAPL': {'meets_requirement': True, 'years': 10},
        'MSFT': {'meets_requirement': True, 'years': 8},
        'GOOGL': {'meets_requirement': True, 'years': 6},
        'NVDA': {'meets_requirement': True, 'years': 3},
        'ARM': {'meets_requirement': True, 'years': 2.5},
        'QS': {'meets_requirement': True, 'quarters': 7}
    }

    # Small cap filters (optional)
    small_cap_filters = {
        'QS': {'passes': True, 'failed_filters': []}
    }

    print("Testing 4-Tier FrameworkValidator...")
    print(f"Portfolio value: ${sum(portfolio_state['holdings'].values()) + portfolio_state['cash']:,.2f}")
    print()

    # Run validation
    report = validator.validate_portfolio(
        portfolio_state,
        holdings_tiers,
        roe_persistence,
        small_cap_filters
    )

    # Print summary
    print("\n4-Tier Compliance Results:")
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
    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/compliance_4tier_test.md", 'w') as f:
        f.write(markdown)

    # Export to JSON
    validator.export_to_json(report, "outputs/compliance_4tier_test.json")

    print("Export complete!")
    print("  - Markdown: outputs/compliance_4tier_test.md")
    print("  - JSON: outputs/compliance_4tier_test.json")


if __name__ == "__main__":
    main()
