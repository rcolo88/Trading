"""
Quality Metrics Calculator for Stock Analysis

This module implements academically-validated quality metrics for evaluating company quality.
Metrics are based on research by Novy-Marx, Piotroski, and other academic studies on quality investing.

Ranked Metrics Calculated:
1. Gross Profitability = (Revenue - COGS) / Total Assets
2. Return on Equity (ROE) = Net Income / Shareholder Equity
3. Operating Profitability = (Revenue - COGS - SG&A) / Total Assets
4. Free Cash Flow Yield = Free Cash Flow / Market Cap
5. ROIC = NOPAT / (Total Debt + Total Equity)

"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logger = logging.getLogger(__name__)


class QualityTier(Enum):
    """Quality tier classifications based on composite score."""
    ELITE = "Elite"          # 85-100
    STRONG = "Strong"        # 70-84
    MODERATE = "Moderate"    # 50-69
    WEAK = "Weak"           # 0-49


@dataclass
class MetricScore:
    """Data class for individual metric scores."""
    name: str
    value: float
    score: float  # 0-10
    weight: float
    weighted_score: float
    percentile: Optional[float] = None


@dataclass
class RedFlag:
    """Data class for red flag warnings."""
    category: str
    severity: str  # "HIGH", "MEDIUM", "LOW"
    description: str
    metric_value: float


@dataclass
class QualityAnalysisResult:
    """Complete quality analysis result (supports both DEFAULT and STEPS frameworks)."""
    ticker: str
    metric_scores: List[MetricScore]
    composite_score: float
    tier: QualityTier
    red_flags: List[RedFlag]
    is_consistent_roe_performer: bool
    summary: str
    raw_metrics: Dict[str, float]
    framework: str = 'DEFAULT'  # 'DEFAULT' or 'STEPS'
    dimension_scores: Optional[Dict[str, float]] = None  # For STEPS mode transparency
    dimension_weights: Optional[Dict[str, float]] = None  # Document weights used


class QualityMetricsCalculator:
    """
    Calculates and analyzes quality metrics for stock evaluation.

    This class implements five academically-validated quality metrics and provides
    comprehensive scoring, tier classification, and red flag detection.

    Attributes:
        METRIC_WEIGHTS: Dictionary defining weights for each quality metric
        TIER_THRESHOLDS: Score thresholds for quality tier classification

    Example:
        >>> calculator = QualityMetricsCalculator()
        >>> financial_data = {
        ...     'ticker': 'AAPL',
        ...     'revenue': 394_328_000_000,
        ...     'cogs': 223_546_000_000,
        ...     'sga': 26_094_000_000,
        ...     'total_assets': 352_755_000_000,
        ...     'net_income': 99_803_000_000,
        ...     'shareholder_equity': 62_146_000_000,
        ...     'free_cash_flow': 111_443_000_000,
        ...     'market_cap': 3_000_000_000_000,
        ...     'total_debt': 111_088_000_000,
        ...     'nopat': 85_000_000_000,
        ... }
        >>> result = calculator.calculate_quality_metrics(financial_data)
        >>> print(f"Composite Score: {result.composite_score}")
        >>> print(f"Tier: {result.tier.value}")
    """

    # Metric weights (must sum to 1.0) - DEFAULT framework
    METRIC_WEIGHTS = {
        'gross_profitability': 0.25,
        'roe': 0.20,
        'operating_profitability': 0.20,
        'fcf_yield': 0.20,
        'roic': 0.15
    }

    # STEPS framework weights (4 dimensions, must sum to 1.0)
    STEPS_WEIGHTS = {
        'gross_profitability': 0.30,
        'roe_persistence': 0.25,
        'earnings_quality': 0.25,
        'conservative_growth': 0.20
    }

    # Tier classification thresholds
    TIER_THRESHOLDS = {
        QualityTier.ELITE: 85.0,
        QualityTier.STRONG: 70.0,
        QualityTier.MODERATE: 50.0,
        QualityTier.WEAK: 0.0
    }

    # Scoring thresholds for each metric (value ranges for 0-10 score)
    METRIC_THRESHOLDS = {
        'gross_profitability': {
            'excellent': 0.45,  # 10 points
            'good': 0.35,       # 7-9 points
            'average': 0.25,    # 4-6 points
            'poor': 0.15        # 1-3 points
            # Below 0.15 = 0 points
        },
        'roe': {
            'excellent': 0.25,  # 25%+ = 10 points
            'good': 0.18,       # 18%+ = 7-9 points
            'average': 0.12,    # 12%+ = 4-6 points
            'poor': 0.05        # 5%+ = 1-3 points
        },
        'operating_profitability': {
            'excellent': 0.30,
            'good': 0.20,
            'average': 0.10,
            'poor': 0.05
        },
        'fcf_yield': {
            'excellent': 0.08,  # 8%+ = 10 points
            'good': 0.05,       # 5%+ = 7-9 points
            'average': 0.03,    # 3%+ = 4-6 points
            'poor': 0.01        # 1%+ = 1-3 points
        },
        'roic': {
            'excellent': 0.20,  # 20%+ = 10 points
            'good': 0.15,       # 15%+ = 7-9 points
            'average': 0.10,    # 10%+ = 4-6 points
            'poor': 0.05        # 5%+ = 1-3 points
        }
    }

    # Red flag thresholds
    RED_FLAG_THRESHOLDS = {
        'high_accruals': 0.05,           # >5% of assets
        'excessive_asset_growth': 0.20,   # >20% YoY
        'high_leverage': 2.0,             # D/E > 2.0
        'margin_deterioration': -0.03     # -3% YoY
    }

    def __init__(self):
        """Initialize the Quality Metrics Calculator."""
        # Validate weights sum to 1.0
        total_weight = sum(self.METRIC_WEIGHTS.values())
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Metric weights must sum to 1.0, got {total_weight}")

        logger.info("QualityMetricsCalculator initialized")

    def calculate_quality_metrics(self, financial_data: Dict[str, Any], framework: str = 'DEFAULT') -> QualityAnalysisResult:
        """
        Calculate all quality metrics and generate comprehensive analysis.

        Supports two frameworks:
        - DEFAULT: 5-metric system (Gross Profitability, ROE, Operating Profitability, FCF Yield, ROIC)
        - STEPS: 4-dimension system (Gross Profitability, ROE Persistence, Earnings Quality, Conservative Growth)

        Args:
            financial_data: Dictionary containing financial metrics with keys:
                - ticker: Stock ticker symbol
                - revenue: Total revenue
                - cogs: Cost of goods sold
                - sga: Selling, general & administrative expenses
                - total_assets: Total assets
                - net_income: Net income
                - shareholder_equity: Shareholder equity
                - free_cash_flow: Free cash flow
                - market_cap: Market capitalization
                - total_debt: Total debt
                - nopat: Net operating profit after tax
                - roe_history: (Optional) List of historical ROE values (required for STEPS)
                - operating_cash_flow: (Optional) Operating cash flow (required for STEPS)
                - accruals: (Optional) Accruals as % of assets
                - asset_growth: (Optional) YoY asset growth rate
                - margin_change: (Optional) YoY margin change
                - prior_year_revenue: (Optional) Prior year revenue
                - prior_year_cogs: (Optional) Prior year COGS
                - ebitda: (Optional) EBITDA (required for STEPS Conservative Growth)
            framework: 'DEFAULT' or 'STEPS' (default: 'DEFAULT')

        Returns:
            QualityAnalysisResult: Complete analysis with scores, tier, and red flags

        Raises:
            ValueError: If required financial data is missing or invalid
        """
        ticker = financial_data.get('ticker', 'UNKNOWN')
        logger.info(f"Calculating quality metrics for {ticker} using {framework} framework")

        # Validate framework parameter
        if framework not in ['DEFAULT', 'STEPS']:
            raise ValueError(f"Invalid framework '{framework}'. Must be 'DEFAULT' or 'STEPS'")

        # Validate required fields
        self._validate_financial_data(financial_data, framework)

        # Branch based on framework
        if framework == 'STEPS':
            return self._calculate_steps_metrics(financial_data)
        else:
            return self._calculate_default_metrics(financial_data)

    def _calculate_default_metrics(self, financial_data: Dict[str, Any]) -> QualityAnalysisResult:
        """
        Calculate quality metrics using DEFAULT framework (5-metric system).
        This preserves the original calculation logic.

        Args:
            financial_data: Financial data dictionary

        Returns:
            QualityAnalysisResult with DEFAULT framework
        """
        ticker = financial_data.get('ticker', 'UNKNOWN')

        # Calculate individual metrics
        raw_metrics = self._calculate_raw_metrics(financial_data)

        # Score each metric
        metric_scores = self._score_metrics(raw_metrics)

        # Calculate composite score
        composite_score = self._calculate_composite_score(metric_scores)

        # Classify tier
        tier = self._classify_tier(composite_score)

        # Check for consistent ROE performance
        is_consistent_roe = self._check_consistent_roe(financial_data)

        # Detect red flags
        red_flags = self._detect_red_flags(financial_data, raw_metrics)

        # Generate summary
        summary = self._generate_summary(
            ticker=ticker,
            composite_score=composite_score,
            tier=tier,
            metric_scores=metric_scores,
            red_flags=red_flags,
            is_consistent_roe=is_consistent_roe
        )

        result = QualityAnalysisResult(
            ticker=ticker,
            metric_scores=metric_scores,
            composite_score=composite_score,
            tier=tier,
            red_flags=red_flags,
            is_consistent_roe_performer=is_consistent_roe,
            summary=summary,
            raw_metrics=raw_metrics,
            framework='DEFAULT'
        )

        logger.info(f"Quality analysis complete for {ticker}: {tier.value} tier, score {composite_score:.1f}")
        return result

    def _validate_financial_data(self, data: Dict[str, Any], framework: str = 'DEFAULT') -> None:
        """
        Validate that required financial data fields are present and valid.

        Args:
            data: Financial data dictionary
            framework: 'DEFAULT' or 'STEPS'

        Raises:
            ValueError: If required fields are missing or invalid
        """
        required_fields = [
            'revenue', 'cogs', 'sga', 'total_assets', 'net_income',
            'shareholder_equity', 'free_cash_flow', 'market_cap',
            'total_debt', 'nopat'
        ]

        # Additional fields required for STEPS framework
        if framework == 'STEPS':
            required_fields.extend(['operating_cash_flow'])  # For earnings quality

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields for {framework} framework: {', '.join(missing_fields)}")

        # Validate no negative values for key metrics
        for field in required_fields:
            if data[field] is None:
                raise ValueError(f"Field '{field}' cannot be None")

        # Validate denominators are not zero
        if data['total_assets'] == 0:
            raise ValueError("total_assets cannot be zero")
        if data['shareholder_equity'] == 0:
            raise ValueError("shareholder_equity cannot be zero")
        if data['market_cap'] == 0:
            raise ValueError("market_cap cannot be zero")
        if (data['total_debt'] + data['shareholder_equity']) == 0:
            raise ValueError("total_debt + shareholder_equity cannot be zero")

    def _calculate_raw_metrics(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate raw metric values from financial data.

        Args:
            data: Financial data dictionary

        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}

        # 1. Gross Profitability = (Revenue - COGS) / Total Assets
        metrics['gross_profitability'] = (
            (data['revenue'] - data['cogs']) / data['total_assets']
        )

        # 2. Return on Equity (ROE) = Net Income / Shareholder Equity
        metrics['roe'] = data['net_income'] / data['shareholder_equity']

        # 3. Operating Profitability = (Revenue - COGS - SG&A) / Total Assets
        metrics['operating_profitability'] = (
            (data['revenue'] - data['cogs'] - data['sga']) / data['total_assets']
        )

        # 4. Free Cash Flow Yield = Free Cash Flow / Market Cap
        metrics['fcf_yield'] = data['free_cash_flow'] / data['market_cap']

        # 5. ROIC = NOPAT / (Total Debt + Total Equity)
        invested_capital = data['total_debt'] + data['shareholder_equity']
        metrics['roic'] = data['nopat'] / invested_capital

        # Additional metrics for red flag detection
        metrics['debt_to_equity'] = (
            data['total_debt'] / data['shareholder_equity']
            if data['shareholder_equity'] != 0 else float('inf')
        )

        return metrics

    def _score_metric(self, metric_name: str, value: float) -> float:
        """
        Score a single metric on a 0-10 scale based on thresholds.

        Uses linear interpolation between threshold levels for smooth scoring.

        Args:
            metric_name: Name of the metric to score
            value: Raw metric value

        Returns:
            Score between 0.0 and 10.0
        """
        thresholds = self.METRIC_THRESHOLDS[metric_name]

        # Handle negative values
        if value < 0:
            return 0.0

        # Excellent tier (10 points)
        if value >= thresholds['excellent']:
            return 10.0

        # Good tier (7-9 points) - interpolate
        elif value >= thresholds['good']:
            ratio = (value - thresholds['good']) / (thresholds['excellent'] - thresholds['good'])
            return 7.0 + (ratio * 3.0)

        # Average tier (4-6 points) - interpolate
        elif value >= thresholds['average']:
            ratio = (value - thresholds['average']) / (thresholds['good'] - thresholds['average'])
            return 4.0 + (ratio * 3.0)

        # Poor tier (1-3 points) - interpolate
        elif value >= thresholds['poor']:
            ratio = (value - thresholds['poor']) / (thresholds['average'] - thresholds['poor'])
            return 1.0 + (ratio * 3.0)

        # Below poor threshold - interpolate from 0 to 1
        else:
            ratio = value / thresholds['poor']
            return min(ratio * 1.0, 1.0)

    def _score_metrics(self, raw_metrics: Dict[str, float]) -> List[MetricScore]:
        """
        Score all quality metrics.

        Args:
            raw_metrics: Dictionary of calculated raw metrics

        Returns:
            List of MetricScore objects
        """
        metric_scores = []

        for metric_name, weight in self.METRIC_WEIGHTS.items():
            value = raw_metrics[metric_name]
            score = self._score_metric(metric_name, value)
            weighted_score = score * weight * 10  # Convert to 0-100 scale with weight

            metric_scores.append(MetricScore(
                name=metric_name,
                value=value,
                score=score,
                weight=weight,
                weighted_score=weighted_score
            ))

        return metric_scores

    def _calculate_composite_score(self, metric_scores: List[MetricScore]) -> float:
        """
        Calculate weighted composite score.

        Args:
            metric_scores: List of individual metric scores

        Returns:
            Composite score (0-100)
        """
        composite = sum(ms.weighted_score for ms in metric_scores)
        return round(composite, 2)

    def _classify_tier(self, composite_score: float) -> QualityTier:
        """
        Classify quality tier based on composite score.

        Args:
            composite_score: Weighted composite score (0-100)

        Returns:
            QualityTier enum value
        """
        if composite_score >= self.TIER_THRESHOLDS[QualityTier.ELITE]:
            return QualityTier.ELITE
        elif composite_score >= self.TIER_THRESHOLDS[QualityTier.STRONG]:
            return QualityTier.STRONG
        elif composite_score >= self.TIER_THRESHOLDS[QualityTier.MODERATE]:
            return QualityTier.MODERATE
        else:
            return QualityTier.WEAK

    def _check_consistent_roe(self, data: Dict[str, Any]) -> bool:
        """
        Check if company maintains ROE >15% for 10+ years.

        Args:
            data: Financial data including optional 'roe_history' list

        Returns:
            True if ROE consistently >15% for 10+ years, False otherwise
        """
        roe_history = data.get('roe_history', [])

        if len(roe_history) < 10:
            return False

        # Check last 10 years
        last_10_years = roe_history[-10:]
        return all(roe > 0.15 for roe in last_10_years)

    def _detect_red_flags(
        self,
        data: Dict[str, Any],
        raw_metrics: Dict[str, float]
    ) -> List[RedFlag]:
        """
        Detect potential red flags in financial metrics.

        Args:
            data: Financial data dictionary
            raw_metrics: Calculated raw metrics

        Returns:
            List of RedFlag objects
        """
        red_flags = []

        # 1. High Accruals (>5% of assets)
        accruals = data.get('accruals')
        if accruals is not None and accruals > self.RED_FLAG_THRESHOLDS['high_accruals']:
            red_flags.append(RedFlag(
                category="High Accruals",
                severity="HIGH",
                description=f"Accruals at {accruals*100:.1f}% of assets (threshold: 5%). "
                           "High accruals may indicate aggressive accounting or unsustainable earnings.",
                metric_value=accruals
            ))

        # 2. Excessive Asset Growth (>20% YoY)
        asset_growth = data.get('asset_growth')
        if asset_growth is not None and asset_growth > self.RED_FLAG_THRESHOLDS['excessive_asset_growth']:
            red_flags.append(RedFlag(
                category="Excessive Asset Growth",
                severity="MEDIUM",
                description=f"Asset growth at {asset_growth*100:.1f}% YoY (threshold: 20%). "
                           "Rapid expansion may strain operations or indicate aggressive acquisitions.",
                metric_value=asset_growth
            ))

        # 3. Deteriorating Margins
        margin_change = data.get('margin_change')
        if margin_change is not None and margin_change < self.RED_FLAG_THRESHOLDS['margin_deterioration']:
            red_flags.append(RedFlag(
                category="Deteriorating Margins",
                severity="HIGH",
                description=f"Gross margin declined {abs(margin_change)*100:.1f}% YoY (threshold: -3%). "
                           "Margin compression may indicate competitive pressure or operational issues.",
                metric_value=margin_change
            ))

        # Calculate margin deterioration from revenue/COGS if prior year data available
        if 'prior_year_revenue' in data and 'prior_year_cogs' in data:
            current_margin = (data['revenue'] - data['cogs']) / data['revenue'] if data['revenue'] > 0 else 0
            prior_margin = (
                (data['prior_year_revenue'] - data['prior_year_cogs']) / data['prior_year_revenue']
                if data['prior_year_revenue'] > 0 else 0
            )
            calculated_margin_change = current_margin - prior_margin

            if calculated_margin_change < self.RED_FLAG_THRESHOLDS['margin_deterioration']:
                red_flags.append(RedFlag(
                    category="Deteriorating Gross Margin",
                    severity="HIGH",
                    description=f"Gross margin declined {abs(calculated_margin_change)*100:.1f}% YoY. "
                               "Current: {current_margin*100:.1f}%, Prior: {prior_margin*100:.1f}%",
                    metric_value=calculated_margin_change
                ))

        # 4. High Leverage (D/E > 2.0)
        debt_to_equity = raw_metrics.get('debt_to_equity', 0)
        if debt_to_equity > self.RED_FLAG_THRESHOLDS['high_leverage']:
            severity = "HIGH" if debt_to_equity > 3.0 else "MEDIUM"
            red_flags.append(RedFlag(
                category="High Leverage",
                severity=severity,
                description=f"Debt-to-Equity ratio at {debt_to_equity:.2f}x (threshold: 2.0x). "
                           "High leverage increases financial risk and interest burden.",
                metric_value=debt_to_equity
            ))

        # 5. Negative Free Cash Flow
        if data['free_cash_flow'] < 0:
            red_flags.append(RedFlag(
                category="Negative Free Cash Flow",
                severity="HIGH",
                description=f"Negative FCF of ${abs(data['free_cash_flow']):,.0f}. "
                           "Company is burning cash and may face liquidity issues.",
                metric_value=data['free_cash_flow']
            ))

        # 6. Negative ROE
        if raw_metrics['roe'] < 0:
            red_flags.append(RedFlag(
                category="Negative Return on Equity",
                severity="HIGH",
                description=f"ROE at {raw_metrics['roe']*100:.1f}%. "
                           "Company is destroying shareholder value.",
                metric_value=raw_metrics['roe']
            ))

        return red_flags

    def _generate_summary(
        self,
        ticker: str,
        composite_score: float,
        tier: QualityTier,
        metric_scores: List[MetricScore],
        red_flags: List[RedFlag],
        is_consistent_roe: bool
    ) -> str:
        """
        Generate human-readable summary of quality analysis.

        Args:
            ticker: Stock ticker symbol
            composite_score: Overall quality score
            tier: Quality tier classification
            metric_scores: Individual metric scores
            red_flags: Detected red flags
            is_consistent_roe: Whether company has consistent ROE >15%

        Returns:
            Formatted summary string
        """
        lines = []
        lines.append(f"=== Quality Analysis for {ticker} ===\n")

        # Overall score and tier
        lines.append(f"Composite Quality Score: {composite_score:.1f}/100")
        lines.append(f"Quality Tier: {tier.value}\n")

        # Tier interpretation
        tier_interpretation = {
            QualityTier.ELITE: "Exceptional quality with strong competitive advantages",
            QualityTier.STRONG: "High quality with sustainable business model",
            QualityTier.MODERATE: "Average quality with some competitive strengths",
            QualityTier.WEAK: "Below-average quality with concerning fundamentals"
        }
        lines.append(f"Interpretation: {tier_interpretation[tier]}\n")

        # Individual metrics
        lines.append("Individual Metric Scores:")
        lines.append("-" * 70)

        metric_names_readable = {
            'gross_profitability': 'Gross Profitability',
            'roe': 'Return on Equity (ROE)',
            'operating_profitability': 'Operating Profitability',
            'fcf_yield': 'Free Cash Flow Yield',
            'roic': 'Return on Invested Capital (ROIC)'
        }

        for ms in metric_scores:
            readable_name = metric_names_readable.get(ms.name, ms.name)
            lines.append(
                f"{readable_name:35} | Value: {ms.value:>7.1%} | "
                f"Score: {ms.score:>4.1f}/10 | Weight: {ms.weight:>4.0%} | "
                f"Contribution: {ms.weighted_score:>5.1f}"
            )

        # Consistent ROE performer badge
        if is_consistent_roe:
            lines.append("\n*** ELITE PERFORMER: ROE >15% for 10+ consecutive years ***")

        # Red flags
        if red_flags:
            lines.append("\n⚠️  RED FLAGS DETECTED:")
            lines.append("-" * 70)

            # Group by severity
            high_severity = [rf for rf in red_flags if rf.severity == "HIGH"]
            medium_severity = [rf for rf in red_flags if rf.severity == "MEDIUM"]
            low_severity = [rf for rf in red_flags if rf.severity == "LOW"]

            for severity_group, label in [
                (high_severity, "HIGH SEVERITY"),
                (medium_severity, "MEDIUM SEVERITY"),
                (low_severity, "LOW SEVERITY")
            ]:
                if severity_group:
                    lines.append(f"\n{label}:")
                    for rf in severity_group:
                        lines.append(f"  • {rf.category}: {rf.description}")
        else:
            lines.append("\n✓ No red flags detected")

        # Investment recommendation
        lines.append("\n" + "=" * 70)
        lines.append("INVESTMENT IMPLICATION:")

        if tier == QualityTier.ELITE and len([rf for rf in red_flags if rf.severity == "HIGH"]) == 0:
            recommendation = "STRONG BUY - Elite quality with no major red flags"
        elif tier == QualityTier.STRONG and len([rf for rf in red_flags if rf.severity == "HIGH"]) == 0:
            recommendation = "BUY - Strong quality fundamentals"
        elif tier == QualityTier.STRONG or tier == QualityTier.MODERATE:
            recommendation = "HOLD/CAUTIOUS BUY - Moderate quality, monitor red flags"
        elif len([rf for rf in red_flags if rf.severity == "HIGH"]) >= 2:
            recommendation = "AVOID - Multiple high-severity red flags"
        else:
            recommendation = "SELL/AVOID - Weak quality fundamentals"

        lines.append(recommendation)
        lines.append("=" * 70)

        return "\n".join(lines)

    def calculate_percentile_scores(
        self,
        ticker: str,
        financial_data: Dict[str, Any],
        peer_data: List[Dict[str, Any]]
    ) -> QualityAnalysisResult:
        """
        Calculate quality metrics with percentile ranking against peers.

        This method extends the basic quality calculation by adding percentile
        rankings for each metric relative to a peer group.

        Args:
            ticker: Stock ticker symbol
            financial_data: Financial data for the target company
            peer_data: List of financial data dictionaries for peer companies

        Returns:
            QualityAnalysisResult with percentile rankings included
        """
        # Calculate base metrics
        result = self.calculate_quality_metrics(financial_data)

        if not peer_data:
            logger.warning(f"No peer data provided for {ticker}, skipping percentile calculation")
            return result

        # Calculate raw metrics for all peers
        peer_metrics = []
        for peer in peer_data:
            try:
                peer_raw = self._calculate_raw_metrics(peer)
                peer_metrics.append(peer_raw)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid peer data: {e}")
                continue

        if not peer_metrics:
            logger.warning(f"No valid peer data for {ticker}, skipping percentile calculation")
            return result

        # Calculate percentiles for each metric
        for metric_score in result.metric_scores:
            metric_name = metric_score.name
            target_value = metric_score.value

            # Get all peer values for this metric
            peer_values = [pm[metric_name] for pm in peer_metrics]
            peer_values.append(target_value)  # Include target company
            peer_values.sort()

            # Calculate percentile rank
            rank = peer_values.index(target_value)
            percentile = (rank / (len(peer_values) - 1)) * 100 if len(peer_values) > 1 else 50.0

            metric_score.percentile = round(percentile, 1)

        logger.info(f"Percentile scores calculated for {ticker} against {len(peer_metrics)} peers")
        return result

    # ==================== STEPS FRAMEWORK METHODS ====================

    def _calculate_steps_metrics(self, financial_data: Dict[str, Any]) -> QualityAnalysisResult:
        """
        Calculate quality metrics using STEPS framework (4-dimension system).

        STEPS Framework:
        - Gross Profitability (30%)
        - ROE Persistence (25%)
        - Earnings Quality (25%)
        - Conservative Growth (20%)

        Args:
            financial_data: Financial data dictionary

        Returns:
            Quality AnalysisResult with STEPS framework
        """
        ticker = financial_data.get('ticker', 'UNKNOWN')
        logger.info(f"Calculating STEPS quality metrics for {ticker}")

        # Calculate STEPS dimensions
        gp_score = self._calculate_gross_profitability_score_steps(financial_data)
        roe_persistence_score = self._calculate_roe_persistence_score(financial_data)
        earnings_quality_score = self._calculate_earnings_quality_score(financial_data)
        conservative_growth_score = self._calculate_conservative_growth_score(financial_data)

        # Build dimension scores dict
        dimension_scores = {
            'gross_profitability': gp_score,
            'roe_persistence': roe_persistence_score,
            'earnings_quality': earnings_quality_score,
            'conservative_growth': conservative_growth_score
        }

        # Build dimension weights dict
        dimension_weights = dict(self.STEPS_WEIGHTS)

        # Calculate weighted composite score (convert to 0-100 scale)
        composite_score = (
            gp_score * self.STEPS_WEIGHTS['gross_profitability'] +
            roe_persistence_score * self.STEPS_WEIGHTS['roe_persistence'] +
            earnings_quality_score * self.STEPS_WEIGHTS['earnings_quality'] +
            conservative_growth_score * self.STEPS_WEIGHTS['conservative_growth']
        ) * 10  # Convert 0-10 scale to 0-100

        # Create MetricScore objects for display
        metric_scores = [
            MetricScore(
                name='Gross Profitability',
                value=financial_data.get('revenue', 0) - financial_data.get('cogs', 0) / financial_data.get('total_assets', 1),
                score=gp_score,
                weight=self.STEPS_WEIGHTS['gross_profitability'],
                weighted_score=gp_score * self.STEPS_WEIGHTS['gross_profitability']
            ),
            MetricScore(
                name='ROE Persistence',
                value=financial_data.get('net_income', 0) / financial_data.get('shareholder_equity', 1),
                score=roe_persistence_score,
                weight=self.STEPS_WEIGHTS['roe_persistence'],
                weighted_score=roe_persistence_score * self.STEPS_WEIGHTS['roe_persistence']
            ),
            MetricScore(
                name='Earnings Quality',
                value=0.0,  # Composite metric
                score=earnings_quality_score,
                weight=self.STEPS_WEIGHTS['earnings_quality'],
                weighted_score=earnings_quality_score * self.STEPS_WEIGHTS['earnings_quality']
            ),
            MetricScore(
                name='Conservative Growth',
                value=financial_data.get('asset_growth', 0),
                score=conservative_growth_score,
                weight=self.STEPS_WEIGHTS['conservative_growth'],
                weighted_score=conservative_growth_score * self.STEPS_WEIGHTS['conservative_growth']
            )
        ]

        # Classify tier
        tier = self._classify_tier(composite_score)

        # Check for consistent ROE performance
        is_consistent_roe = self._check_consistent_roe(financial_data)

        # Detect red flags (use raw metrics for compatibility)
        raw_metrics = self._calculate_raw_metrics(financial_data)
        red_flags = self._detect_red_flags(financial_data, raw_metrics)

        # Generate STEPS-specific summary
        summary = f"STEPS Quality Analysis: {ticker} - {tier.value} tier (Score: {composite_score:.1f}/100)\n"
        summary += f"Dimensions: GP {gp_score:.1f}/10, ROE Persistence {roe_persistence_score:.1f}/10, "
        summary += f"Earnings Quality {earnings_quality_score:.1f}/10, Conservative Growth {conservative_growth_score:.1f}/10"

        result = QualityAnalysisResult(
            ticker=ticker,
            metric_scores=metric_scores,
            composite_score=composite_score,
            tier=tier,
            red_flags=red_flags,
            is_consistent_roe_performer=is_consistent_roe,
            summary=summary,
            raw_metrics=raw_metrics,
            framework='STEPS',
            dimension_scores=dimension_scores,
            dimension_weights=dimension_weights
        )

        logger.info(f"STEPS analysis complete for {ticker}: {tier.value} tier, score {composite_score:.1f}")
        return result

    def _calculate_gross_profitability_score_steps(self, financial_data: Dict[str, Any]) -> float:
        """
        Calculate Gross Profitability score for STEPS framework (different thresholds).

        Scoring (1-10 scale):
        - <20% = 1-3
        - 20-40% = 4-6
        - 40-60% = 7-9
        - >60% = 10

        Args:
            financial_data: Financial data dictionary

        Returns:
            Score from 1-10
        """
        revenue = financial_data.get('revenue', 0)
        cogs = financial_data.get('cogs', 0)
        total_assets = financial_data.get('total_assets', 1)

        if total_assets == 0:
            return 0.0

        gp_ratio = (revenue - cogs) / total_assets

        if gp_ratio > 0.60:
            return 10.0
        elif gp_ratio > 0.40:
            # Linear interpolation 7-9
            return 7.0 + (gp_ratio - 0.40) / 0.20 * 2.0
        elif gp_ratio > 0.20:
            # Linear interpolation 4-6
            return 4.0 + (gp_ratio - 0.20) / 0.20 * 2.0
        elif gp_ratio > 0.0:
            # Linear interpolation 1-3
            return 1.0 + (gp_ratio / 0.20) * 2.0
        else:
            return 1.0

    def _calculate_roe_persistence_score(self, financial_data: Dict[str, Any]) -> float:
        """
        Calculate ROE Persistence score for STEPS framework.

        Components:
        - Base ROE score (1-10 scale)
        - Consistency bonus: +1 if 3-year std dev < 5 percentage points
        - Persistence bonus: +1 if 3-year average within 20% of current year

        Scoring (1-10 scale):
        - <5% = 0-2
        - 5-10% = 3-4
        - 10-15% = 5-6
        - 15-20% = 7-8
        - >20% = 9-10

        Args:
            financial_data: Financial data dictionary

        Returns:
            Score from 1-10
        """
        net_income = financial_data.get('net_income', 0)
        shareholder_equity = financial_data.get('shareholder_equity', 1)

        if shareholder_equity == 0:
            return 0.0

        current_roe = net_income / shareholder_equity

        # Base score
        if current_roe > 0.20:
            base_score = 9.0 + min(1.0, (current_roe - 0.20) / 0.10)
        elif current_roe > 0.15:
            base_score = 7.0 + (current_roe - 0.15) / 0.05 * 2.0
        elif current_roe > 0.10:
            base_score = 5.0 + (current_roe - 0.10) / 0.05 * 2.0
        elif current_roe > 0.05:
            base_score = 3.0 + (current_roe - 0.05) / 0.05 * 2.0
        elif current_roe > 0.0:
            base_score = (current_roe / 0.05) * 2.0
        else:
            base_score = 0.0

        # Check for ROE history (3-year consistency)
        roe_history = financial_data.get('roe_history', [])
        if len(roe_history) >= 3:
            import statistics
            avg_roe = statistics.mean(roe_history)
            std_dev = statistics.stdev(roe_history)

            # Consistency bonus
            if std_dev < 0.05:  # < 5 percentage points std dev
                base_score = min(10.0, base_score + 0.5)

            # Persistence bonus
            if abs(current_roe - avg_roe) / current_roe < 0.20:  # Within 20%
                base_score = min(10.0, base_score + 0.5)

        return base_score

    def _calculate_earnings_quality_score(self, financial_data: Dict[str, Any]) -> float:
        """
        Calculate Earnings Quality score for STEPS framework.

        Components:
        a) Accruals ratio: (Net Income - Operating Cash Flow) / Total Assets
           - Lower is better, <0.05 = good, >0.10 = bad
        b) OCF/Net Income ratio
           - >1.2 = excellent (9-10), 1.0-1.2 = good (7-8), 0.8-1.0 = acceptable (5-6), <0.8 = poor (1-4)
        c) Asset growth rate
           - <10% = conservative (9-10), 10-20% = moderate (7-8), >20% = aggressive (1-6)

        Returns average of 3 components (1-10 scale)

        Args:
            financial_data: Financial data dictionary

        Returns:
            Score from 1-10
        """
        net_income = financial_data.get('net_income', 0)
        operating_cash_flow = financial_data.get('operating_cash_flow', net_income)  # Fallback to NI
        total_assets = financial_data.get('total_assets', 1)
        asset_growth = financial_data.get('asset_growth', 0)

        scores = []

        # Component a) Accruals ratio
        if total_assets > 0:
            accruals_ratio = abs((net_income - operating_cash_flow) / total_assets)
            if accruals_ratio < 0.02:
                accruals_score = 10.0
            elif accruals_ratio < 0.05:
                accruals_score = 7.0 + (0.05 - accruals_ratio) / 0.03 * 3.0
            elif accruals_ratio < 0.10:
                accruals_score = 4.0 + (0.10 - accruals_ratio) / 0.05 * 3.0
            else:
                accruals_score = max(1.0, 4.0 - (accruals_ratio - 0.10) * 10)
            scores.append(accruals_score)

        # Component b) OCF/Net Income ratio
        if net_income > 0:
            ocf_ni_ratio = operating_cash_flow / net_income
            if ocf_ni_ratio > 1.2:
                ocf_score = 9.0 + min(1.0, (ocf_ni_ratio - 1.2) / 0.3)
            elif ocf_ni_ratio > 1.0:
                ocf_score = 7.0 + (ocf_ni_ratio - 1.0) / 0.2 * 2.0
            elif ocf_ni_ratio > 0.8:
                ocf_score = 5.0 + (ocf_ni_ratio - 0.8) / 0.2 * 2.0
            else:
                ocf_score = max(1.0, 5.0 * ocf_ni_ratio / 0.8)
            scores.append(ocf_score)

        # Component c) Asset growth rate
        if asset_growth < 0.10:
            asset_score = 9.0 + min(1.0, (0.10 - asset_growth) / 0.05)
        elif asset_growth < 0.20:
            asset_score = 7.0 + (0.20 - asset_growth) / 0.10 * 2.0
        else:
            asset_score = max(1.0, 7.0 - (asset_growth - 0.20) * 10)
        scores.append(asset_score)

        # Return average
        return sum(scores) / len(scores) if scores else 5.0

    def _calculate_conservative_growth_score(self, financial_data: Dict[str, Any]) -> float:
        """
        Calculate Conservative Growth score for STEPS framework.

        Components:
        a) Asset growth: <10% = 10, 10-15% = 8, 15-20% = 6, >20% = 2
        b) Debt/EBITDA: <1x = 10, 1-2x = 8, 2-3x = 6, >3x = 3
        c) Capital allocation quality:
           - If acquisitions > 50% of total CAPEX: -2 points
           - If organic CAPEX dominates: +2 points

        Returns weighted average of components (1-10 scale)

        Args:
            financial_data: Financial data dictionary

        Returns:
            Score from 1-10
        """
        asset_growth = financial_data.get('asset_growth', 0)
        total_debt = financial_data.get('total_debt', 0)
        ebitda = financial_data.get('ebitda', financial_data.get('net_income', 0) * 1.5)  # Rough estimate if missing

        scores = []
        weights = []

        # Component a) Asset growth
        if asset_growth < 0.10:
            asset_growth_score = 10.0
        elif asset_growth < 0.15:
            asset_growth_score = 8.0 + (0.15 - asset_growth) / 0.05 * 2.0
        elif asset_growth < 0.20:
            asset_growth_score = 6.0 + (0.20 - asset_growth) / 0.05 * 2.0
        else:
            asset_growth_score = max(2.0, 6.0 - (asset_growth - 0.20) * 10)
        scores.append(asset_growth_score)
        weights.append(0.4)

        # Component b) Debt/EBITDA
        if ebitda > 0:
            debt_ebitda = total_debt / ebitda
            if debt_ebitda < 1.0:
                debt_score = 10.0
            elif debt_ebitda < 2.0:
                debt_score = 8.0 + (2.0 - debt_ebitda) * 2.0
            elif debt_ebitda < 3.0:
                debt_score = 6.0 + (3.0 - debt_ebitda) * 2.0
            else:
                debt_score = max(3.0, 6.0 - (debt_ebitda - 3.0))
            scores.append(debt_score)
            weights.append(0.4)

        # Component c) Capital allocation (simplified - would need CAPEX breakdown data)
        # For now, use a neutral score if data not available
        capex_quality_score = 7.0  # Neutral default
        scores.append(capex_quality_score)
        weights.append(0.2)

        # Calculate weighted average
        total_weight = sum(weights)
        if total_weight > 0:
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        else:
            weighted_score = 5.0

        return weighted_score


def format_quality_report(result: QualityAnalysisResult, include_raw_data: bool = False) -> str:
    """
    Format quality analysis result as a detailed report.

    Args:
        result: QualityAnalysisResult object
        include_raw_data: Whether to include raw metric values in report

    Returns:
        Formatted report string
    """
    report = [result.summary]

    if include_raw_data:
        report.append("\n\nRAW METRIC VALUES:")
        report.append("-" * 70)
        for metric_name, value in result.raw_metrics.items():
            report.append(f"{metric_name:30} | {value:>15.4f}")

    return "\n".join(report)


# Example usage and testing
if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Example: Apple Inc. (AAPL) - Hypothetical FY2024 data
    apple_data = {
        'ticker': 'AAPL',
        'revenue': 394_328_000_000,
        'cogs': 223_546_000_000,
        'sga': 26_094_000_000,
        'total_assets': 352_755_000_000,
        'net_income': 99_803_000_000,
        'shareholder_equity': 62_146_000_000,
        'free_cash_flow': 111_443_000_000,
        'market_cap': 3_000_000_000_000,
        'total_debt': 111_088_000_000,
        'nopat': 85_000_000_000,
        'roe_history': [0.46, 0.49, 0.55, 0.61, 0.56, 0.50, 0.63, 0.83, 1.00, 1.60],  # 10 years
        'accruals': 0.03,
        'asset_growth': 0.08,
        'margin_change': -0.01,
        'prior_year_revenue': 383_285_000_000,
        'prior_year_cogs': 214_137_000_000
    }

    # Create calculator and run analysis
    calculator = QualityMetricsCalculator()
    result = calculator.calculate_quality_metrics(apple_data)

    # Print results
    print(result.summary)
    print("\n" + "=" * 70)
    print(f"\nRaw Metrics:")
    for metric, value in result.raw_metrics.items():
        print(f"  {metric}: {value:.4f}")
