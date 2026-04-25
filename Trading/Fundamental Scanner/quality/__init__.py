"""
Quality Analysis Package

Academic research-based cross-sectional quality scoring.

Modules:
- opportunity_scorer: Profitability-anchored cross-sectional ranking (Novy-Marx, Fama-French, AQR QMJ)
- earnings_quality: Piotroski F-Score, Accrual Ratio, Cash Conversion (Sloan 1996, Piotroski 2000)

Author: Quality Analysis System
Date: April 2026
"""

from .earnings_quality import (
    EarningsQualityAnalyzer,
    EarningsQualityResult,
    PiotroskiScoreBreakdown,
    get_earnings_quality_analyzer
)

from .opportunity_scorer import (
    OpportunityScorer,
    OpportunityReport,
    OpportunitySignals,
    COMPOSITE_WEIGHTS,
    HARD_GATES,
    VALUE_WEIGHTS,
)

__all__ = [
    'EarningsQualityAnalyzer',
    'EarningsQualityResult',
    'PiotroskiScoreBreakdown',
    'get_earnings_quality_analyzer',
    'OpportunityScorer',
    'OpportunityReport',
    'OpportunitySignals',
    'COMPOSITE_WEIGHTS',
    'HARD_GATES',
    'VALUE_WEIGHTS',
]
