"""
Quality Multipliers Module for Quality Analysis

This module implements adjustment multipliers for quality scores:
1. Safety Multiplier: Adjusts score based on financial safety metrics
2. Data Quality Multiplier: Adjusts score based on data availability
3. Market Cap Multiplier: Adjusts lookback periods based on market cap tier

Multipliers are applied as final adjustments to quality scores to account for:
- Financial risk factors (leverage, volatility)
- Data reliability and availability
- Market structure considerations

Author: Quality Analysis System
Date: January 2026
"""

from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MultiplierResult:
    """Complete multiplier analysis result."""
    safety_multiplier: float
    data_quality_multiplier: float
    market_cap_multiplier: float
    combined_multiplier: float
    adjustment_factors: Dict[str, float]
    quality_adjustment_notes: Dict[str, str]

    def to_dict(self) -> dict:
        return {
            'safety_multiplier': self.safety_multiplier,
            'data_quality_multiplier': self.data_quality_multiplier,
            'market_cap_multiplier': self.market_cap_multiplier,
            'combined_multiplier': self.combined_multiplier,
            'adjustment_factors': self.adjustment_factors,
            'quality_adjustment_notes': self.quality_adjustment_notes
        }


class MultiplierCalculator:
    """
    Calculate quality score adjustment multipliers.

    Multipliers provide final adjustments to base quality scores based on:
    1. Safety Profile: Financial health and risk factors
    2. Data Quality: Reliability of available financial data
    3. Market Cap: Size-based considerations

    Multiplier Ranges:
    - Safety Multiplier: 0.70 to 1.00
    - Data Quality Multiplier: 0.80 to 1.00
    - Market Cap Multiplier: 0.35 to 1.25 (for lookback adjustments)

    Example:
        >>> calculator = MultiplierCalculator()
        >>> result = calculator.calculate_multipliers(
        ...     safety_metrics={'z_score': 4.5, 'debt_ebitda': 1.5},
        ...     data_years=5,
        ...     required_years=5,
        ...     market_cap=50_000_000_000
        ... )
        >>> print(f"Combined Multiplier: {result.combined_multiplier:.3f}")
    """

    # Safety Multiplier Thresholds
    SAFETY_EXCELLENT_Z_SCORE = 3.0
    SAFETY_GOOD_Z_SCORE = 2.0
    SAFETY_CONCERN_Z_SCORE = 1.5

    SAFETY_EXCELLENT_DEBT_EBITDA = 1.5
    SAFETY_GOOD_DEBT_EBITDA = 2.5
    SAFETY_CONCERN_DEBT_EBITDA = 3.5

    # Data Quality Thresholds
    DATA_QUALITY_EXCELLENT = 0.95  # 5+ years, all required fields
    DATA_QUALITY_GOOD = 0.90       # 4+ years, minor gaps
    DATA_QUALITY_AVERAGE = 0.85    # 3+ years, some gaps
    DATA_QUALITY_POOR = 0.80       # <3 years or significant gaps

    # Market Cap Multipliers (for lookback adjustments)
    MARKET_CAP_MULTIPLIERS = {
        'mega': 1.25,    # > $200B
        'large': 1.00,   # $10B - $200B
        'mid': 0.75,     # $2B - $10B
        'small': 0.50,   # $300M - $2B
        'micro': 0.35    # < $300M
    }

    def __init__(self):
        """Initialize the Multiplier Calculator."""
        logger.info("MultiplierCalculator initialized")

    def calculate_safety_multiplier(
        self,
        z_score: Optional[float] = None,
        debt_to_ebitda: Optional[float] = None,
        interest_coverage: Optional[float] = None,
        beta: Optional[float] = None
    ) -> float:
        """
        Calculate safety multiplier based on financial risk metrics.

        Safety Multiplier = Base × Z-Score Factor × Leverage Factor × Volatility Factor

        Ranges:
        - 0.70-0.85: High risk (distressed, highly leveraged)
        - 0.85-0.95: Moderate risk (some concerns)
        - 0.95-1.00: Low risk (financially sound)

        Args:
            z_score: Altman Z-Score (higher is better)
            debt_to_ebitda: Debt/EBITDA ratio (lower is better)
            interest_coverage: Interest coverage ratio (higher is better)
            beta: Stock beta (lower is better)

        Returns:
            Safety multiplier from 0.70 to 1.00
        """
        base_multiplier = 1.0
        z_score_factor = 1.0
        leverage_factor = 1.0
        volatility_factor = 1.0

        # Z-Score Factor
        if z_score is not None:
            if z_score >= self.SAFETY_EXCELLENT_Z_SCORE:
                z_score_factor = 1.0  # No adjustment
            elif z_score >= self.SAFETY_GOOD_Z_SCORE:
                z_score_factor = 0.98  # Slight concern
            elif z_score >= self.SAFETY_CONCERN_Z_SCORE:
                z_score_factor = 0.95  # Moderate concern
            else:
                z_score_factor = 0.85  # High concern

        # Leverage Factor
        if debt_to_ebitda is not None:
            if debt_to_ebitda <= self.SAFETY_EXCELLENT_DEBT_EBITDA:
                leverage_factor = 1.0
            elif debt_to_ebitda <= self.SAFETY_GOOD_DEBT_EBITDA:
                leverage_factor = 0.98
            elif debt_to_ebitda <= self.SAFETY_CONCERN_DEBT_EBITDA:
                leverage_factor = 0.93
            else:
                leverage_factor = 0.80  # Highly leveraged

        # Volatility Factor (Beta)
        if beta is not None:
            if beta <= 0.8:
                volatility_factor = 1.0  # Low volatility - good
            elif beta <= 1.2:
                volatility_factor = 0.98  # Average
            elif beta <= 1.5:
                volatility_factor = 0.95  # Elevated
            else:
                volatility_factor = 0.85  # High volatility

        # Interest Coverage Factor
        interest_factor = 1.0
        if interest_coverage is not None:
            if interest_coverage >= 10.0:
                interest_factor = 1.0
            elif interest_coverage >= 5.0:
                interest_factor = 0.98
            elif interest_coverage >= 3.0:
                interest_factor = 0.95
            elif interest_coverage >= 1.0:
                interest_factor = 0.90
            else:
                interest_factor = 0.80  # Cannot cover interest

        # Calculate combined safety multiplier
        safety_multiplier = (
            base_multiplier *
            z_score_factor *
            leverage_factor *
            volatility_factor *
            interest_factor
        )

        # Enforce bounds
        safety_multiplier = max(0.70, min(1.00, safety_multiplier))

        logger.info(
            f"Safety Multiplier: {safety_multiplier:.3f} "
            f"(Z={z_score_factor:.2f}, L={leverage_factor:.2f}, "
            f"V={volatility_factor:.2f}, I={interest_factor:.2f})"
        )

        return round(safety_multiplier, 3)

    def calculate_data_quality_multiplier(
        self,
        available_years: int,
        required_years: int,
        data_completeness: float = 1.0,
        has_audited_statements: bool = True
    ) -> float:
        """
        Calculate data quality multiplier based on data availability and reliability.

        Data Quality Multiplier = Base × Completeness × Recency × Audit Factor

        Ranges:
        - 0.95-1.00: Excellent (5+ years, complete, audited)
        - 0.90-0.95: Good (4+ years, minor gaps)
        - 0.85-0.90: Average (3+ years, some gaps)
        - 0.80-0.85: Poor (<3 years or significant gaps)

        Args:
            available_years: Years of historical data available
            required_years: Years required for full analysis
            data_completeness: Percentage of required fields available (0.0-1.0)
            has_audited_statements: Whether financial statements are audited

        Returns:
            Data quality multiplier from 0.80 to 1.00
        """
        # Base multiplier starts at 1.0
        base_multiplier = 1.0

        # Recency factor: Penalty for insufficient history
        if available_years >= required_years:
            recency_factor = 1.0
        elif available_years >= required_years - 1:
            recency_factor = 0.98  # Slight penalty
        elif available_years >= required_years - 2:
            recency_factor = 0.95  # Moderate penalty
        else:
            recency_factor = 0.90  # Significant penalty

        # Completeness factor: Penalty for missing data
        completeness_factor = 0.80 + (0.20 * data_completeness)

        # Audit factor: Bonus for audited statements
        audit_factor = 1.02 if has_audited_statements else 1.0

        # Calculate combined data quality multiplier
        data_multiplier = (
            base_multiplier *
            recency_factor *
            completeness_factor *
            audit_factor
        )

        # Enforce bounds
        data_multiplier = max(0.80, min(1.00, data_multiplier))

        logger.debug(
            f"Data Quality Multiplier: {data_multiplier:.3f} "
            f"(Recency={recency_factor:.2f}, Completeness={completeness_factor:.2f}, "
            f"Audit={audit_factor:.2f})"
        )

        return round(data_multiplier, 3)

    def get_market_cap_multiplier(self, market_cap: float) -> float:
        """
        Get market cap multiplier for lookback adjustments.

        Market Cap Multipliers:
        - Mega Cap (> $200B): 1.25x (extended lookback justified)
        - Large Cap ($10B-$200B): 1.0x (baseline)
        - Mid Cap ($2B-$10B): 0.75x (reduced lookback)
        - Small Cap ($300M-$2B): 0.50x (minimum lookback)
        - Micro Cap (< $300M): 0.35x (very minimum)

        Args:
            market_cap: Company market capitalization in dollars

        Returns:
            Market cap multiplier
        """
        if market_cap >= 200_000_000_000:  # $200B
            return self.MARKET_CAP_MULTIPLIERS['mega']
        elif market_cap >= 10_000_000_000:  # $10B
            return self.MARKET_CAP_MULTIPLIERS['large']
        elif market_cap >= 2_000_000_000:  # $2B
            return self.MARKET_CAP_MULTIPLIERS['mid']
        elif market_cap >= 300_000_000:  # $300M
            return self.MARKET_CAP_MULTIPLIERS['small']
        else:
            return self.MARKET_CAP_MULTIPLIERS['micro']

    def get_market_cap_tier(self, market_cap: float) -> str:
        """
        Get market cap tier name.

        Args:
            market_cap: Company market capitalization in dollars

        Returns:
            Market cap tier name
        """
        if market_cap >= 200_000_000_000:
            return 'Mega Cap'
        elif market_cap >= 10_000_000_000:
            return 'Large Cap'
        elif market_cap >= 2_000_000_000:
            return 'Mid Cap'
        elif market_cap >= 300_000_000:
            return 'Small Cap'
        else:
            return 'Micro Cap'

    def calculate_multipliers(
        self,
        safety_metrics: Optional[Dict[str, Optional[float]]] = None,
        data_years: int = 5,
        required_years: int = 5,
        data_completeness: float = 1.0,
        has_audited_statements: bool = True,
        market_cap: Optional[float] = None
    ) -> MultiplierResult:
        """
        Calculate all quality score multipliers.

        Args:
            safety_metrics: Dictionary of safety metrics (z_score, debt_to_ebitda, etc.)
            data_years: Years of historical data available
            required_years: Years required for full analysis
            data_completeness: Percentage of required fields available
            has_audited_statements: Whether statements are audited
            market_cap: Company market cap for tier-based adjustments

        Returns:
            MultiplierResult with all multipliers and factors
        """
        # Calculate Safety Multiplier
        if safety_metrics:
            safety_multiplier = self.calculate_safety_multiplier(
                z_score=safety_metrics.get('z_score'),
                debt_to_ebitda=safety_metrics.get('debt_to_ebitda'),
                interest_coverage=safety_metrics.get('interest_coverage'),
                beta=safety_metrics.get('beta')
            )
        else:
            safety_multiplier = 1.0  # No adjustment if no data

        # Calculate Data Quality Multiplier
        data_quality_multiplier = self.calculate_data_quality_multiplier(
            available_years=data_years,
            required_years=required_years,
            data_completeness=data_completeness,
            has_audited_statements=has_audited_statements
        )

        # Get Market Cap Multiplier
        if market_cap is not None:
            market_cap_multiplier = self.get_market_cap_multiplier(market_cap)
            market_cap_tier = self.get_market_cap_tier(market_cap)
        else:
            market_cap_multiplier = 1.0
            market_cap_tier = 'Unknown'

        # Calculate Combined Multiplier
        # Combined = Safety × Data Quality (Market Cap affects lookbacks separately)
        combined_multiplier = safety_multiplier * data_quality_multiplier

        # Build adjustment factors and notes
        adjustment_factors = {
            'safety': safety_multiplier,
            'data_quality': data_quality_multiplier,
            'market_cap': market_cap_multiplier,
            'combined': combined_multiplier
        }

        quality_adjustment_notes = {}

        if safety_multiplier < 0.95:
            quality_adjustment_notes['safety'] = (
                f"Safety multiplier {safety_multiplier:.2f}: "
                "Lower due to elevated financial risk factors"
            )

        if data_quality_multiplier < 0.95:
            quality_adjustment_notes['data_quality'] = (
                f"Data quality multiplier {data_quality_multiplier:.2f}: "
                "Reduced due to limited or incomplete historical data"
            )

        if market_cap is not None:
            quality_adjustment_notes['market_cap'] = (
                f"Market cap multiplier {market_cap_multiplier:.2f} ({market_cap_tier}): "
                "Adjusts lookback periods based on company size"
            )

        logger.info(
            f"Multipliers calculated: Safety={safety_multiplier:.3f}, "
            f"Data={data_quality_multiplier:.3f}, "
            f"MCap={market_cap_multiplier:.2f}, "
            f"Combined={combined_multiplier:.3f}"
        )

        return MultiplierResult(
            safety_multiplier=safety_multiplier,
            data_quality_multiplier=data_quality_multiplier,
            market_cap_multiplier=market_cap_multiplier,
            combined_multiplier=combined_multiplier,
            adjustment_factors=adjustment_factors,
            quality_adjustment_notes=quality_adjustment_notes
        )

    def apply_multipliers(
        self,
        base_quality_score: float,
        safety_metrics: Optional[Dict[str, float]] = None,
        data_years: int = 5,
        required_years: int = 5,
        data_completeness: float = 1.0,
        has_audited_statements: bool = True
    ) -> Dict:
        """
        Apply multipliers to a base quality score.

        Args:
            base_quality_score: Unadjusted quality score (0-10 or 0-100 scale)
            safety_metrics: Safety metrics for multiplier calculation
            data_years: Years of historical data available
            required_years: Years required for full analysis
            data_completeness: Percentage of required fields available
            has_audited_statements: Whether statements are audited

        Returns:
            Dictionary with adjusted score and multiplier details
        """
        # Calculate multipliers
        multiplier_result = self.calculate_multipliers(
            safety_metrics=safety_metrics,
            data_years=data_years,
            required_years=required_years,
            data_completeness=data_completeness,
            has_audited_statements=has_audited_statements
        )

        # Determine scale
        if base_quality_score > 20:
            # Assume 0-100 scale
            adjusted_score = base_quality_score * multiplier_result.combined_multiplier
            scale_note = "0-100 scale"
        else:
            # Assume 0-10 scale
            adjusted_score = base_quality_score * multiplier_result.combined_multiplier
            scale_note = "0-10 scale"

        return {
            'base_score': base_quality_score,
            'adjusted_score': round(adjusted_score, 2),
            'multiplier_result': multiplier_result,
            'scale_note': scale_note
        }

    def get_multiplier_summary(self, market_cap: float) -> str:
        """
        Generate human-readable summary of market cap multipliers.

        Args:
            market_cap: Company market capitalization

        Returns:
            Formatted summary string
        """
        tier = self.get_market_cap_tier(market_cap)
        multiplier = self.get_market_cap_multiplier(market_cap)

        lines = [
            "=" * 60,
            "QUALITY MULTIPLIERS SUMMARY",
            "=" * 60,
            f"Market Cap: ${market_cap/1e9:.2f}B",
            f"Tier: {tier}",
            f"Market Cap Multiplier: {multiplier:.2f}x",
            "-" * 60,
            "Multiplier Ranges:",
            "-" * 60,
            "Safety Multiplier:    0.70 - 1.00 (based on leverage, Z-score, volatility)",
            "Data Quality Multiplier: 0.80 - 1.00 (based on data availability)",
            "Market Cap Multiplier: 0.35 - 1.25 (for lookback periods)",
            "-" * 60,
            "Combined Effect:",
            "-" * 60,
            f"  Low Risk + Good Data:   {0.95 * 0.95:.2f}x (Score ~90% of base)",
            f"  High Risk + Poor Data:  {0.70 * 0.80:.2f}x (Score ~56% of base)",
            "=" * 60
        ]

        return "\n".join(lines)


def get_multiplier_calculator() -> MultiplierCalculator:
    """Factory function to get a MultiplierCalculator instance."""
    return MultiplierCalculator()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    calculator = MultiplierCalculator()

    # Example 1: High-quality company
    result1 = calculator.calculate_multipliers(
        safety_metrics={
            'z_score': 4.5,  # Very safe
            'debt_to_ebitda': 1.2,  # Low leverage
            'interest_coverage': 12.0,  # Excellent coverage
            'beta': 0.9  # Moderate volatility
        },
        data_years=5,
        required_years=5,
        data_completeness=1.0,
        has_audited_statements=True,
        market_cap=50_000_000_000  # $50B
    )

    print("=" * 60)
    print("HIGH-QUALITY COMPANY MULTIPLIERS")
    print("=" * 60)
    print(f"Safety Multiplier: {result1.safety_multiplier:.3f}")
    print(f"Data Quality Multiplier: {result1.data_quality_multiplier:.3f}")
    print(f"Market Cap Multiplier: {result1.market_cap_multiplier:.2f}")
    print(f"Combined Multiplier: {result1.combined_multiplier:.3f}")

    if result1.quality_adjustment_notes:
        print("\nAdjustment Notes:")
        for key, note in result1.quality_adjustment_notes.items():
            print(f"  {key}: {note}")

    # Example 2: Distressed company
    result2 = calculator.calculate_multipliers(
        safety_metrics={
            'z_score': 1.2,  # Distress zone
            'debt_to_ebitda': 4.5,  # High leverage
            'interest_coverage': 1.5,  # Weak coverage
            'beta': 1.6  # High volatility
        },
        data_years=3,
        required_years=5,
        data_completeness=0.75,
        has_audited_statements=False,
        market_cap=500_000_000  # $500M
    )

    print("\n" + "=" * 60)
    print("DISTRESSED COMPANY MULTIPLIERS")
    print("=" * 60)
    print(f"Combined Multiplier: {result2.combined_multiplier:.3f}")

    if result2.quality_adjustment_notes:
        print("\nAdjustment Notes:")
        for key, note in result2.quality_adjustment_notes.items():
            print(f"  {key}: {note}")

    # Example 3: Apply to base score
    print("\n" + "=" * 60)
    print("APPLYING MULTIPLIERS TO BASE SCORE")
    print("=" * 60)

    base_score = 8.5  # 0-10 scale
    adjusted = calculator.apply_multipliers(
        base_quality_score=base_score,
        safety_metrics=result1.adjustment_factors,
        data_years=5,
        required_years=5
    )

    print(f"Base Score: {adjusted['base_score']}/10")
    print(f"Adjusted Score: {adjusted['adjusted_score']}/10")
    print(f"Multiplier Applied: {adjusted['multiplier_result'].combined_multiplier:.3f}")
