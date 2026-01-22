"""
Quality Analysis Package

Modules for comprehensive stock quality analysis based on academic research.

Modules:
- quality_metrics_calculator: Main quality calculation engine
- earnings_quality: Accrual Ratio, Cash Conversion, Piotroski F-Score
- growth_quality: Asset Growth, Revenue CAGR, Margin Trend, Revenue Quality
- safety_metrics: Beta, Idiosyncratic Volatility, Z-Score, Leverage
- lookback_calculator: Market-cap-adjusted lookback periods
- multipliers: Safety, Data Quality, and Market Cap multipliers
- config: Configuration settings and thresholds

Author: Quality Analysis System
Date: January 2026
"""

from .quality_metrics_calculator import (
    QualityMetricsCalculator,
    QualityAnalysisResult,
    QualityTier,
    MetricScore,
    RedFlag,
    format_quality_report
)

from .earnings_quality import (
    EarningsQualityAnalyzer,
    EarningsQualityResult,
    PiotroskiScoreBreakdown,
    get_earnings_quality_analyzer
)

from .growth_quality import (
    GrowthQualityAnalyzer,
    GrowthQualityResult,
    get_growth_quality_analyzer
)

from .safety_metrics import (
    SafetyAnalyzer,
    SafetyMetricsResult,
    get_safety_analyzer
)

from .lookback_calculator import (
    LookbackCalculator,
    LookbackResult,
    DimensionLookbackResult,
    MarketCapTier as LookbackMarketCapTier,
    get_lookback_calculator
)

from .multipliers import (
    MultiplierCalculator,
    MultiplierResult,
    get_multiplier_calculator
)

from .config import (
    QualityConfig,
    get_quality_config,
    MultiplierConfig,
    ScoringConfig,
    DataRequirements
)

__all__ = [
    'QualityMetricsCalculator',
    'QualityAnalysisResult',
    'QualityTier',
    'MetricScore',
    'RedFlag',
    'format_quality_report',
    'EarningsQualityAnalyzer',
    'EarningsQualityResult',
    'PiotroskiScoreBreakdown',
    'get_earnings_quality_analyzer',
    'GrowthQualityAnalyzer',
    'GrowthQualityResult',
    'get_growth_quality_analyzer',
    'SafetyAnalyzer',
    'SafetyMetricsResult',
    'get_safety_analyzer',
    'LookbackCalculator',
    'LookbackResult',
    'DimensionLookbackResult',
    'LookbackMarketCapTier',
    'get_lookback_calculator',
    'MultiplierCalculator',
    'MultiplierResult',
    'get_multiplier_calculator',
    'QualityConfig',
    'get_quality_config',
    'MultiplierConfig',
    'ScoringConfig',
    'DataRequirements'
]
