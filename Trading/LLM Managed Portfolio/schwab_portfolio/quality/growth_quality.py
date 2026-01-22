"""
Growth Quality Module for Quality Analysis

This module implements growth quality metrics based on academic research:
- Cooper, Gulen, Schill (2008): Asset Growth Anomaly - low asset growth predicts higher returns
- Lakonishok, Shleifer, Vishny (1994): Contrarian investment strategy

Metrics:
1. Asset Growth (1-year, inverse): Lower is better; penalizes rapid expansion
2. Revenue CAGR (3-5 years): Sustainable revenue growth rate
3. Margin Trend (3-5 years): Improving margins indicate quality growth
4. Revenue Quality: Consistency and sustainability of revenue

Weight in Quality Score: 15% (UPDATES.md)

Author: Quality Analysis System
Date: January 2026
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import logging
import statistics

logger = logging.getLogger(__name__)


@dataclass
class GrowthQualityResult:
    """Complete growth quality analysis result."""
    asset_growth_rate: Optional[float]
    asset_growth_score: float
    revenue_cagr: Optional[float]
    revenue_cagr_score: float
    margin_trend: Optional[float]
    margin_trend_score: float
    revenue_quality_score: float
    growth_quality_score: float
    red_flags: List[Dict]
    is_high_quality: bool

    def to_dict(self) -> dict:
        return {
            'asset_growth_rate': self.asset_growth_rate,
            'asset_growth_score': self.asset_growth_score,
            'revenue_cagr': self.revenue_cagr,
            'revenue_cagr_score': self.revenue_cagr_score,
            'margin_trend': self.margin_trend,
            'margin_trend_score': self.margin_trend_score,
            'revenue_quality_score': self.revenue_quality_score,
            'growth_quality_score': self.growth_quality_score,
            'red_flags': self.red_flags,
            'is_high_quality': self.is_high_quality
        }


class GrowthQualityAnalyzer:
    """
    Analyze growth quality metrics for stock evaluation.

    Implements academically-validated metrics for assessing growth quality:
    - Asset Growth (inverse relationship with returns per Cooper et al., 2008)
    - Revenue CAGR (sustainable growth measurement)
    - Margin Trend (improving margins indicate quality)
    - Revenue Quality (consistency and sustainability)

    Scoring (0-10 scale):
    - Asset Growth: <5% = 10, 5-15% = 7-9, 15-25% = 4-6, >25% = 1-3
    - Revenue CAGR: >20% = 10, 10-20% = 7-9, 5-10% = 4-6, <5% = 1-3
    - Margin Trend: >5% improvement = 10, 2-5% = 7-9, 0-2% = 4-6, <0% = 1-3
    - Revenue Quality: Based on consistency and predictability

    Example:
        >>> analyzer = GrowthQualityAnalyzer()
        >>> result = analyzer.analyze({
        ...     'total_assets': 1000,
        ...     'prior_total_assets': 900,
        ...     'revenues': [800, 850, 900, 950, 1000],
        ...     'margins': [0.20, 0.21, 0.22, 0.21, 0.23]
        ... })
        >>> print(f"Growth Quality Score: {result.growth_quality_score}/10")
    """

    # Asset growth thresholds (inverse scoring - lower is better)
    ASSET_GROWTH_EXCELLENT = 0.05  # <5% = 10 points
    ASSET_GROWTH_GOOD = 0.15       # 5-15% = 7-9 points
    ASSET_GROWTH_AVERAGE = 0.25    # 15-25% = 4-6 points
    ASSET_GROWTH_POOR = 0.40       # >25% = 1-3 points

    # Revenue CAGR thresholds
    REVENUE_CAGR_EXCELLENT = 0.20  # >20% = 10 points
    REVENUE_CAGR_GOOD = 0.10       # 10-20% = 7-9 points
    REVENUE_CAGR_AVERAGE = 0.05    # 5-10% = 4-6 points
    REVENUE_CAGR_POOR = 0.02       # 2-5% = 1-3 points

    # Margin trend thresholds
    MARGIN_TREND_EXCELLENT = 0.05  # >5% improvement = 10 points
    MARGIN_TREND_GOOD = 0.02       # 2-5% improvement = 7-9 points
    MARGIN_TREND_AVERAGE = 0.00    # 0-2% improvement = 4-6 points
    MARGIN_TREND_POOR = -0.02      # <0% = 1-3 points

    def __init__(self):
        """Initialize the Growth Quality Analyzer."""
        logger.info("GrowthQualityAnalyzer initialized")

    def calculate_asset_growth_rate(
        self,
        total_assets: float,
        prior_total_assets: float
    ) -> Optional[float]:
        """
        Calculate 1-year asset growth rate.

        Asset Growth = (Total Assets_t - Total Assets_t-1) / Total Assets_t-1

        Interpretation (inverse relationship with returns):
        - <5%: EXCELLENT (low asset growth predicts higher returns)
        - 5-15%: GOOD
        - 15-25%: AVERAGE
        - >25%: POOR (rapid expansion often destroys value)

        Args:
            total_assets: Current period total assets
            prior_total_assets: Prior period total assets

        Returns:
            Asset growth rate as decimal (e.g., 0.10 = 10%)
            None if calculation not possible
        """
        try:
            if prior_total_assets <= 0:
                logger.warning("Cannot calculate asset growth: prior assets <= 0")
                return None

            asset_growth = (total_assets - prior_total_assets) / prior_total_assets

            logger.debug(f"Asset growth rate: {asset_growth:.4f} ({asset_growth*100:.2f}%)")

            return asset_growth

        except Exception as e:
            logger.error(f"Error calculating asset growth rate: {e}")
            return None

    def calculate_asset_growth_score(self, asset_growth: Optional[float]) -> float:
        """
        Calculate asset growth score (0-10 scale, inverse relationship).

        Lower asset growth = Higher score (per Cooper, Gulen, Schill 2008)

        Args:
            asset_growth: Calculated asset growth rate

        Returns:
            Score from 0-10
        """
        if asset_growth is None:
            return 5.0  # Neutral score if data unavailable

        # Excellent: <5%
        if asset_growth <= self.ASSET_GROWTH_EXCELLENT:
            return 10.0

        # Good: 5-15% - interpolate 7-9
        elif asset_growth <= self.ASSET_GROWTH_GOOD:
            ratio = (asset_growth - self.ASSET_GROWTH_EXCELLENT) / (
                self.ASSET_GROWTH_GOOD - self.ASSET_GROWTH_EXCELLENT
            )
            return 7.0 + (ratio * 2.0)

        # Average: 15-25% - interpolate 4-6
        elif asset_growth <= self.ASSET_GROWTH_AVERAGE:
            ratio = (asset_growth - self.ASSET_GROWTH_GOOD) / (
                self.ASSET_GROWTH_AVERAGE - self.ASSET_GROWTH_GOOD
            )
            return 4.0 + (ratio * 2.0)

        # Poor: >25% - interpolate 1-3, then decay
        elif asset_growth <= self.ASSET_GROWTH_POOR:
            ratio = (asset_growth - self.ASSET_GROWTH_AVERAGE) / (
                self.ASSET_GROWTH_POOR - self.ASSET_GROWTH_AVERAGE
            )
            return 1.0 + (ratio * 2.0)

        # Very high growth - score decays further
        else:
            decay_factor = max(0, 1.0 - (asset_growth - self.ASSET_GROWTH_POOR) * 0.5)
            return max(1.0, 3.0 * decay_factor)

    def calculate_revenue_cagr(
        self,
        revenues: List[float],
        periods: Optional[int] = None
    ) -> Optional[float]:
        """
        Calculate Compound Annual Growth Rate for revenue.

        CAGR = (Ending Value / Beginning Value)^(1/n) - 1

        Args:
            revenues: List of revenue values (most recent first)
            periods: Number of periods (years). If None, uses len(revenues) - 1

        Returns:
            CAGR as decimal (e.g., 0.10 = 10%)
            None if calculation not possible
        """
        try:
            if len(revenues) < 2:
                logger.warning("Cannot calculate revenue CAGR: need at least 2 periods")
                return None

            # Remove None values from end if present
            valid_revenues = [r for r in revenues if r is not None]
            if len(valid_revenues) < 2:
                logger.warning("Cannot calculate revenue CAGR: insufficient valid data")
                return None

            beginning_value = valid_revenues[-1]  # Oldest value
            ending_value = valid_revenues[0]      # Most recent value

            if beginning_value <= 0:
                logger.warning("Cannot calculate revenue CAGR: beginning value <= 0")
                return None

            n = periods if periods is not None else (len(valid_revenues) - 1)
            if n <= 0:
                n = 1

            cagr = (ending_value / beginning_value) ** (1.0 / n) - 1

            logger.debug(f"Revenue CAGR: {cagr:.4f} ({cagr*100:.2f}%) over {n} years")

            return cagr

        except Exception as e:
            logger.error(f"Error calculating revenue CAGR: {e}")
            return None

    def calculate_revenue_cagr_score(self, cagr: Optional[float]) -> float:
        """
        Calculate revenue CAGR score (0-10 scale).

        Higher CAGR = Higher score (within reasonable bounds)

        Args:
            cagr: Calculated revenue CAGR

        Returns:
            Score from 0-10
        """
        if cagr is None:
            return 5.0  # Neutral score if data unavailable

        # Excellent: >20%
        if cagr >= self.REVENUE_CAGR_EXCELLENT:
            return 10.0

        # Good: 10-20% - interpolate 7-9
        elif cagr >= self.REVENUE_CAGR_GOOD:
            ratio = (cagr - self.REVENUE_CAGR_GOOD) / (
                self.REVENUE_CAGR_EXCELLENT - self.REVENUE_CAGR_GOOD
            )
            return 7.0 + (ratio * 2.0)

        # Average: 5-10% - interpolate 4-6
        elif cagr >= self.REVENUE_CAGR_AVERAGE:
            ratio = (cagr - self.REVENUE_CAGR_AVERAGE) / (
                self.REVENUE_CAGR_GOOD - self.REVENUE_CAGR_AVERAGE
            )
            return 4.0 + (ratio * 2.0)

        # Poor: 2-5% - interpolate 1-3
        elif cagr >= self.REVENUE_CAGR_POOR:
            ratio = (cagr - self.REVENUE_CAGR_POOR) / (
                self.REVENUE_CAGR_AVERAGE - self.REVENUE_CAGR_POOR
            )
            return 1.0 + (ratio * 2.0)

        # Negative or very low growth
        else:
            return max(1.0, 3.0 + cagr * 10)

    def calculate_margin_trend(
        self,
        margins: List[float],
        lookback_periods: int = 3
    ) -> Optional[float]:
        """
        Calculate margin trend (improvement rate over time).

        Margin Trend = (Recent Margin - Old Margin) / Old Margin

        Args:
            margins: List of margin values (most recent first)
            lookback_periods: Number of periods to compare (default 3)

        Returns:
            Margin change as decimal (e.g., 0.05 = 5% improvement)
            None if calculation not possible
        """
        try:
            if len(margins) < lookback_periods + 1:
                logger.warning(
                    f"Cannot calculate margin trend: need at least {lookback_periods + 1} periods"
                )
                return None

            # Remove None values
            valid_margins = [m for m in margins if m is not None]
            if len(valid_margins) < lookback_periods + 1:
                logger.warning("Cannot calculate margin trend: insufficient valid data")
                return None

            recent_margins = valid_margins[:lookback_periods]
            old_margins = valid_margins[lookback_periods:]

            if not recent_margins or not old_margins:
                return None

            recent_avg = sum(recent_margins) / len(recent_margins)
            old_avg = sum(old_margins) / len(old_margins)

            if old_avg <= 0:
                logger.warning("Cannot calculate margin trend: old margin average <= 0")
                return None

            margin_trend = (recent_margins[0] - old_margins[0]) / old_margins[0]

            logger.debug(f"Margin trend: {margin_trend:.4f} ({margin_trend*100:.2f}%)")

            return margin_trend

        except Exception as e:
            logger.error(f"Error calculating margin trend: {e}")
            return None

    def calculate_margin_trend_score(self, margin_trend: Optional[float]) -> float:
        """
        Calculate margin trend score (0-10 scale).

        Improving margins = Higher score (indicates quality growth)

        Args:
            margin_trend: Calculated margin change

        Returns:
            Score from 0-10
        """
        if margin_trend is None:
            return 5.0  # Neutral score if data unavailable

        # Excellent: >5% improvement
        if margin_trend >= self.MARGIN_TREND_EXCELLENT:
            return 10.0

        # Good: 2-5% improvement - interpolate 7-9
        elif margin_trend >= self.MARGIN_TREND_GOOD:
            ratio = (margin_trend - self.MARGIN_TREND_GOOD) / (
                self.MARGIN_TREND_EXCELLENT - self.MARGIN_TREND_GOOD
            )
            return 7.0 + (ratio * 2.0)

        # Average: 0-2% improvement - interpolate 4-6
        elif margin_trend >= self.MARGIN_TREND_AVERAGE:
            ratio = (margin_trend - self.MARGIN_TREND_AVERAGE) / (
                self.MARGIN_TREND_GOOD - self.MARGIN_TREND_AVERAGE
            )
            return 4.0 + (ratio * 2.0)

        # Poor: 0 to -2% - interpolate 1-3
        elif margin_trend >= self.MARGIN_TREND_POOR:
            ratio = (margin_trend - self.MARGIN_TREND_POOR) / (
                self.MARGIN_TREND_AVERAGE - self.MARGIN_TREND_POOR
            )
            return 1.0 + (ratio * 2.0)

        # Very negative trend - score decays
        else:
            return max(1.0, 3.0 + margin_trend * 10)

    def calculate_revenue_quality_score(
        self,
        revenues: List[float],
        base_score: float = 5.0
    ) -> float:
        """
        Calculate revenue quality score based on consistency and predictability.

        Revenue Quality Factors:
        1. Consistency: Low variance in growth rates
        2. Stability: No negative growth periods
        3. Predictability: Smooth growth trajectory

        Args:
            revenues: List of revenue values (most recent first)
            base_score: Base score to adjust (default 5.0)

        Returns:
            Revenue quality score from 0-10
        """
        try:
            if len(revenues) < 3:
                return base_score

            # Remove None values
            valid_revenues = [r for r in revenues if r is not None]
            if len(valid_revenues) < 3:
                return base_score

            # Calculate year-over-year growth rates
            growth_rates = []
            for i in range(1, len(valid_revenues)):
                if valid_revenues[i-1] > 0:
                    growth = (valid_revenues[i-2] - valid_revenues[i-1]) / valid_revenues[i-1]
                    growth_rates.append(growth)

            if len(growth_rates) < 2:
                return base_score

            # Calculate metrics
            mean_growth = statistics.mean(growth_rates)
            std_growth = statistics.stdev(growth_rates) if len(growth_rates) > 1 else 0

            # Consistency score: Low variance is good
            # Coefficient of variation
            if abs(mean_growth) > 0:
                cv = abs(std_growth / mean_growth)
            else:
                cv = std_growth

            # Adjust base score based on consistency
            adjustment = 0.0

            # Penalty for high variance (inconsistent growth)
            if cv > 1.0:
                adjustment -= 2.0
            elif cv > 0.5:
                adjustment -= 1.0
            elif cv < 0.3:
                adjustment += 1.0

            # Bonus for positive growth
            if mean_growth > 0.10:
                adjustment += 1.0
            elif mean_growth > 0.05:
                adjustment += 0.5

            # Penalty for negative periods
            negative_periods = sum(1 for g in growth_rates if g < 0)
            if negative_periods > len(growth_rates) / 2:
                adjustment -= 1.5

            final_score = max(1.0, min(10.0, base_score + adjustment))

            logger.debug(f"Revenue quality score: {final_score:.2f} (cv={cv:.2f}, neg={negative_periods})")

            return round(final_score, 1)

        except Exception as e:
            logger.error(f"Error calculating revenue quality score: {e}")
            return base_score

    def detect_growth_red_flags(
        self,
        asset_growth: Optional[float],
        revenue_cagr: Optional[float],
        margin_trend: Optional[float]
    ) -> List[Dict]:
        """
        Detect growth quality red flags.

        Args:
            asset_growth: Calculated asset growth rate
            revenue_cagr: Calculated revenue CAGR
            margin_trend: Calculated margin trend

        Returns:
            List of red flag dictionaries
        """
        red_flags = []

        # Excessive Asset Growth (MEDIUM severity)
        if asset_growth is not None and asset_growth > 0.40:
            red_flags.append({
                'category': 'EXCESSIVE ASSET GROWTH',
                'severity': 'HIGH',
                'description': f"Asset growth at {asset_growth*100:.1f}% (threshold: 40%). "
                             "Rapid expansion often destroys shareholder value.",
                'metric_value': asset_growth
            })
        elif asset_growth is not None and asset_growth > 0.25:
            red_flags.append({
                'category': 'HIGH ASSET GROWTH',
                'severity': 'MEDIUM',
                'description': f"Asset growth at {asset_growth*100:.1f}% (threshold: 25%). "
                             "Monitor for capital allocation issues.",
                'metric_value': asset_growth
            })

        # Declining Revenue (MEDIUM severity)
        if revenue_cagr is not None and revenue_cagr < 0:
            severity = 'HIGH' if revenue_cagr < -0.10 else 'MEDIUM'
            red_flags.append({
                'category': 'DECLINING REVENUE',
                'severity': severity,
                'description': f"Revenue CAGR at {revenue_cagr*100:.1f}% (negative). "
                             "Company is losing top-line growth.",
                'metric_value': revenue_cagr
            })

        # Margin Compression (MEDIUM severity)
        if margin_trend is not None and margin_trend < -0.05:
            red_flags.append({
                'category': 'MARGIN COMPRESSION',
                'severity': 'HIGH',
                'description': f"Margins declined {abs(margin_trend)*100:.1f}% YoY (threshold: -5%). "
                             "Competitive pressure or cost issues.",
                'metric_value': margin_trend
            })
        elif margin_trend is not None and margin_trend < 0:
            red_flags.append({
                'category': 'MARGIN DECLINE',
                'severity': 'LOW',
                'description': f"Margins declined {abs(margin_trend)*100:.1f}% YoY. "
                             "Monitor for continued pressure.",
                'metric_value': margin_trend
            })

        # Stagnant Growth (LOW severity)
        if revenue_cagr is not None and revenue_cagr < 0.02:
            red_flags.append({
                'category': 'STAGNANT GROWTH',
                'severity': 'LOW',
                'description': f"Revenue CAGR at {revenue_cagr*100:.1f}% (threshold: 2%). "
                             "Minimal top-line growth.",
                'metric_value': revenue_cagr
            })

        return red_flags

    def analyze(self, financial_data: Dict[str, any]) -> GrowthQualityResult:
        """
        Complete growth quality analysis.

        Args:
            financial_data: Dictionary with financial metrics:
                - total_assets, prior_total_assets: For asset growth
                - revenues: List of revenue values (most recent first)
                - margins: List of margin values (most recent first)
                - revenue_history: Alternative to revenues (dict with year keys)
                - margin_history: Alternative to margins (dict with year keys)

        Returns:
            GrowthQualityResult with all metrics and red flags
        """
        # Calculate Asset Growth
        asset_growth = self.calculate_asset_growth_rate(
            total_assets=financial_data.get('total_assets', 0),
            prior_total_assets=financial_data.get('prior_total_assets', 0)
        )
        asset_growth_score = self.calculate_asset_growth_score(asset_growth)
        
        # Fallback: if no prior data, estimate moderate growth (average score)
        if asset_growth is None:
            asset_growth = 0.10  # Assume 10% growth as fallback
            logger.info(f"Using fallback asset growth rate: {asset_growth:.1%}")

        # Calculate Revenue CAGR
        revenues = financial_data.get('revenues', [])
        if not revenues and 'revenue_history' in financial_data:
            revenues = financial_data['revenue_history']  # Already a list
        if not revenues:
            revenues = [
                financial_data.get('revenue', 0),
                financial_data.get('prior_revenue', 0)
            ]

        # ADD: Log revenue data for debugging
        if revenues:
            logger.info(f"Revenue data for CAGR: {revenues}")
            if len(revenues) >= 2 and revenues[0] < revenues[-1]:
                logger.warning("Revenue data appears oldest-first, reversing to newest-first")
                revenues = list(reversed(revenues))
                logger.info(f"Reversed revenue data: {revenues}")
        else:
            logger.warning("No revenue data available for CAGR calculation")

        revenue_cagr = self.calculate_revenue_cagr(revenues)
        revenue_cagr_score = self.calculate_revenue_cagr_score(revenue_cagr)
        
        # Fallback: if no historical revenue data, estimate moderate growth
        if revenue_cagr is None:
            revenue_cagr = 0.08  # Assume 8% CAGR as fallback
            logger.info(f"Using fallback revenue CAGR: {revenue_cagr:.1%}")

        # Calculate Margin Trend
        margins = financial_data.get('margins', [])
        if not margins and 'gross_margin_history' in financial_data:
            margins = financial_data['gross_margin_history']  # Use correct key from FMP
        elif not margins and 'margin_history' in financial_data:
            margins = financial_data['margin_history']  # Fallback to old key
        
        # Check available margin data
        valid_margins = [m for m in margins if m is not None and m > 0]
        logger.info(f"Available margin periods: {len(valid_margins)} from {len(margins)} total")
        
        # Use full 5-year margin trend if available (optimal scoring)
        if len(valid_margins) >= 5:
            margin_trend = self.calculate_margin_trend(margins)
            margin_trend_score = self.calculate_margin_trend_score(margin_trend)
            logger.info(f"Using optimal 5-year margin trend: {margin_trend:.3f} ({margin_trend*100:.1f}%)")
        elif len(valid_margins) >= 3:
            # Adaptive 3-year scoring: give 75% credit for 3-year trend
            margin_trend = self.calculate_margin_trend(margins, lookback_periods=2)
            margin_trend_score = self.calculate_margin_trend_score(margin_trend) * 0.75
            logger.info(f"Using adaptive 3-year margin trend scoring (75% credit)")
        else:
            logger.warning(f"Insufficient margin data: {len(valid_margins)} valid periods (need at least 3)")
            margin_trend = 0.02  # Assume 2% margin improvement as fallback
            margin_trend_score = 5.0  # Give average score for fallback
        if not margins:
            # Try to calculate from revenue/gross profit data
            current_gp = financial_data.get('revenue', 0) - financial_data.get('cogs', 0)
            prior_gp = financial_data.get('prior_revenue', 0) - financial_data.get('prior_cogs', 0)
            current_margin = current_gp / financial_data.get('revenue', 1) if financial_data.get('revenue', 0) > 0 else 0
            prior_margin = prior_gp / financial_data.get('prior_revenue', 1) if financial_data.get('prior_revenue', 0) > 0 else 0
            margins = [current_margin, prior_margin]

        # Check available margin data first
        valid_margins = [m for m in margins if m is not None and m > 0]
        margin_trend = None
        margin_trend_score = 0.0
        
        if len(valid_margins) >= 4:
            # Standard 4-period calculation
            margin_trend = self.calculate_margin_trend(margins)
            margin_trend_score = self.calculate_margin_trend_score(margin_trend)
        elif len(valid_margins) >= 3:
            # Adaptive 3-year scoring: give 75% credit for 3-year trend
            margin_trend = self.calculate_margin_trend(margins, lookback_periods=2)
            margin_trend_score = self.calculate_margin_trend_score(margin_trend) * 0.75
            logger.info(f"Using adaptive 3-year margin trend scoring (75% credit): {len(valid_margins)} periods available")
        else:
            logger.warning(f"Insufficient margin data: {len(valid_margins)} valid periods (need at least 3)")
            margin_trend = 0.02  # Assume 2% margin improvement as fallback
            margin_trend_score = 5.0  # Give average score for fallback

        # Calculate Revenue Quality
        revenue_quality_score = self.calculate_revenue_quality_score(revenues)

        # Calculate overall Growth Quality Score
        # Weighting: Asset Growth 25%, Revenue CAGR 30%, Margin Trend 25%, Revenue Quality 20%
        growth_quality_score = (
            asset_growth_score * 0.25 +
            revenue_cagr_score * 0.30 +
            margin_trend_score * 0.25 +
            revenue_quality_score * 0.20
        )

        # Detect red flags
        red_flags = self.detect_growth_red_flags(
            asset_growth=asset_growth,
            revenue_cagr=revenue_cagr,
            margin_trend=margin_trend
        )

        # Determine if high quality (score >= 7)
        is_high_quality = growth_quality_score >= 7.0

        logger.info(
            "Growth quality analysis: CAGR=%s, Asset Growth=%s, Score=%.1f/10, Red Flags=%d",
            f"{revenue_cagr:.1%}" if revenue_cagr else "N/A",
            f"{asset_growth:.1%}" if asset_growth else "N/A",
            growth_quality_score,
            len(red_flags)
        )

        return GrowthQualityResult(
            asset_growth_rate=asset_growth,
            asset_growth_score=asset_growth_score,
            revenue_cagr=revenue_cagr,
            revenue_cagr_score=revenue_cagr_score,
            margin_trend=margin_trend,
            margin_trend_score=margin_trend_score,
            revenue_quality_score=revenue_quality_score,
            growth_quality_score=round(growth_quality_score, 1),
            red_flags=red_flags,
            is_high_quality=is_high_quality
        )


def get_growth_quality_analyzer() -> GrowthQualityAnalyzer:
    """Factory function to get a GrowthQualityAnalyzer instance."""
    return GrowthQualityAnalyzer()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example: High-quality growth company
    data = {
        'total_assets': 1_100_000_000,
        'prior_total_assets': 1_000_000_000,
        'revenues': [1_200_000_000, 1_100_000_000, 1_000_000_000, 900_000_000, 800_000_000],
        'margins': [0.25, 0.24, 0.23, 0.22, 0.21],
        'revenue': 1_200_000_000,
        'prior_revenue': 1_100_000_000,
        'cogs': 900_000_000,
        'prior_cogs': 836_000_000
    }

    analyzer = GrowthQualityAnalyzer()
    result = analyzer.analyze(data)

    print("=" * 60)
    print("GROWTH QUALITY ANALYSIS")
    print("=" * 60)
    print(f"Asset Growth: {result.asset_growth_rate:.2%}" if result.asset_growth_rate else "N/A")
    print(f"Asset Growth Score: {result.asset_growth_score:.1f}/10")
    print(f"Revenue CAGR: {result.revenue_cagr:.2%}" if result.revenue_cagr else "N/A")
    print(f"Revenue CAGR Score: {result.revenue_cagr_score:.1f}/10")
    print(f"Margin Trend: {result.margin_trend:.2%}" if result.margin_trend else "N/A")
    print(f"Margin Trend Score: {result.margin_trend_score:.1f}/10")
    print(f"Revenue Quality Score: {result.revenue_quality_score:.1f}/10")
    print(f"Growth Quality Score: {result.growth_quality_score}/10")
    print(f"High Quality: {result.is_high_quality}")

    if result.red_flags:
        print("\nRED FLAGS:")
        for rf in result.red_flags:
            print(f"  [{rf['severity']}] {rf['category']}: {rf['description'][:60]}...")

    print("=" * 60)

    # Example: Low-quality growth (high asset growth)
    bad_data = {
        'total_assets': 2_000_000_000,
        'prior_total_assets': 1_000_000_000,  # 100% growth
        'revenues': [1_500_000_000, 1_200_000_000, 1_000_000_000],
        'margins': [0.15, 0.20, 0.22]  # Declining margins
    }

    result2 = analyzer.analyze(bad_data)

    print("\n" + "=" * 60)
    print("LOW-QUALITY GROWTH EXAMPLE")
    print("=" * 60)
    print(f"Growth Quality Score: {result2.growth_quality_score}/10")

    if result2.red_flags:
        print("\nRED FLAGS:")
        for rf in result2.red_flags:
            print(f"  [{rf['severity']}] {rf['category']}: {rf['description']}")
