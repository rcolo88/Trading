"""
Quality Analysis Configuration

This module contains all configuration settings, thresholds, and constants
for the quality analysis framework. All settings are centralized here for
easy modification and maintenance.

Author: Quality Analysis System
Date: January 2026
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QualityDimension(Enum):
    """Quality dimension classification."""
    PROFITABILITY = "Profitability"
    EARNINGS_QUALITY = "Earnings Quality"
    GROWTH_QUALITY = "Growth Quality"
    SAFETY = "Safety"
    ROE_PERSISTENCE = "ROE Persistence"


@dataclass
class MarketCapTierInfo:
    """Market cap tier information."""
    tier_name: str
    threshold: int
    multiplier: float


# Market Cap Tier Definitions
# Updated: Extended multipliers for small and micro caps
MARKET_CAP_TIERS = [
    MarketCapTierInfo("Mega Cap", 200_000_000_000, 1.25),
    MarketCapTierInfo("Large Cap", 10_000_000_000, 1.00),
    MarketCapTierInfo("Mid Cap", 2_000_000_000, 0.75),
    MarketCapTierInfo("Small Cap", 300_000_000, 0.75),  # Extended from 0.50
    MarketCapTierInfo("Micro Cap", 0, 0.50),          # Extended from 0.35
]


@dataclass
class QualityConfig:
    """Main configuration class for quality analysis."""

    # NEW_5FACTOR Dimension Weights (sum to 1.0)
    DIMENSION_WEIGHTS: Dict[str, float] = None

    # Market Cap Multipliers
    MARKET_CAP_MULTIPLIERS: Dict[str, float] = None

    # Tier Thresholds
    TIER_THRESHOLDS: Dict[str, float] = None

    # Scoring Thresholds
    SCORING_THRESHOLOLDS: Dict = None

    # Red Flag Thresholds
    RED_FLAG_THRESHOLDS: Dict = None

    # Sector Adjustments
    SECTOR_ADJUSTMENTS: Dict[str, float] = None

    # Default Lookback Periods
    DEFAULT_LOOKBACKS: Dict[str, int] = None

    def __post_init__(self):
        self.DIMENSION_WEIGHTS = {
            'profitability': 0.35,
            'earnings_quality': 0.20,
            'growth_quality': 0.15,
            'safety': 0.15,
            'roe_persistence': 0.15
        }

        self.MARKET_CAP_MULTIPLIERS = {
            'mega': 1.25,
            'large': 1.00,
            'mid': 0.75,
            'small': 0.75,  # Extended from 0.50
            'micro': 0.50   # Extended from 0.35
        }

        self.TIER_THRESHOLDS = {
            'ELITE': 85.0,
            'STRONG': 70.0,
            'MODERATE': 50.0,
            'WEAK': 0.0
        }

        self.SCORING_THRESHOLOLDS = {
            'profitability': {
                'gross_profitability': {
                    'excellent': 0.45,
                    'good': 0.35,
                    'average': 0.25,
                    'poor': 0.15
                },
                'roe': {
                    'excellent': 0.25,
                    'good': 0.18,
                    'average': 0.12,
                    'poor': 0.05
                },
                'roic': {
                    'excellent': 0.20,
                    'good': 0.15,
                    'average': 0.10,
                    'poor': 0.05
                }
            },
            'earnings_quality': {
                'accrual_ratio': {
                    'high': 0.10,
                    'low': -0.10
                },
                'cash_conversion': {
                    'low': 0.80
                },
                'f_score': {
                    'critical': 3,
                    'excellent': 8,
                    'good': 6,
                    'moderate': 4
                }
            },
            'growth_quality': {
                'asset_growth': {
                    'excellent': 0.05,
                    'good': 0.15,
                    'average': 0.25,
                    'poor': 0.40
                },
                'revenue_cagr': {
                    'excellent': 0.20,
                    'good': 0.10,
                    'average': 0.05,
                    'poor': 0.02
                },
                'margin_trend': {
                    'excellent': 0.05,
                    'good': 0.02,
                    'average': 0.00,
                    'poor': -0.02
                }
            },
            'safety': {
                'beta': {
                    'excellent': 0.50,
                    'good': 0.80,
                    'average': 1.20,
                    'poor': 1.50
                },
                'z_score': {
                    'excellent': 3.0,
                    'good': 2.0,
                    'average': 1.0,
                    'poor': 0.5
                },
                'debt_to_ebitda': {
                    'excellent': 1.0,
                    'good': 2.0,
                    'average': 3.0,
                    'poor': 4.0
                },
                'interest_coverage': {
                    'excellent': 10.0,
                    'good': 6.0,
                    'average': 3.0,
                    'poor': 1.0
                }
            },
            'roe_persistence': {
                'high_roe_threshold': 0.15,
                'min_years': 5,
                'max_years': 10
            }
        }

        self.RED_FLAG_THRESHOLDS = {
            'earnings_quality': {
                'high_accruals': 0.10,
                'very_negative_accruals': -0.10,
                'low_cash_conversion': 0.80,
                'critical_f_score': 3
            },
            'growth_quality': {
                'excessive_asset_growth': 0.40,
                'high_asset_growth': 0.25,
                'negative_revenue_cagr': 0.0,
                'margin_compression': -0.05,
                'margin_decline': 0.0,
                'stagnant_growth': 0.02
            },
            'safety': {
                'high_beta': 2.0,
                'elevated_beta': 1.5,
                'bankruptcy_risk': 1.0,
                'financial_distress': 2.0,
                'excessive_leverage': 5.0,
                'high_leverage': 4.0,
                'interest_coverage_risk': 1.0,
                'weak_interest_coverage': 3.0
            }
        }

        self.SECTOR_ADJUSTMENTS = {
            'Technology': 0.80,
            'Healthcare': 1.10,
            'Utilities': 1.10,
            'Industrials': 1.10,
            'Financials': 1.00,
            'Consumer Cyclicals': 1.00,
            'Real Estate': 1.00,
            'Communication Services': 0.90,
            'Materials': 1.00,
            'Energy': 1.00
        }

        self.DEFAULT_LOOKBACKS = {
            'profitability': 1,
            'earnings_quality': 1,
            'growth_quality': 3,
            'safety': 3,
            'roe_persistence': 5
        }


# Global configuration instance
_quality_config: Optional[QualityConfig] = None


def get_quality_config() -> QualityConfig:
    """Get the global quality configuration instance."""
    global _quality_config
    if _quality_config is None:
        _quality_config = QualityConfig()
    return _quality_config


def reset_quality_config() -> QualityConfig:
    """Reset and get the global quality configuration instance."""
    global _quality_config
    _quality_config = QualityConfig()
    return _quality_config


class MultiplierConfig:
    """Configuration for quality multipliers."""

    # Safety Multiplier Bounds
    SAFETY_MULTIPLIER_MIN = 0.70
    SAFETY_MULTIPLIER_MAX = 1.00

    # Data Quality Multiplier Bounds
    DATA_QUALITY_MULTIPLIER_MIN = 0.80
    DATA_QUALITY_MULTIPLIER_MAX = 1.00

    # Safety Threshold Definitions
    SAFETY_Z_SCORE_EXCELLENT = 3.0
    SAFETY_Z_SCORE_GOOD = 2.0
    SAFETY_Z_SCORE_CONCERN = 1.5

    SAFETY_DEBT_EBITDA_EXCELLENT = 1.5
    SAFETY_DEBT_EBITDA_GOOD = 2.5
    SAFETY_DEBT_EBITDA_CONCERN = 3.5

    # Data Quality Thresholds
    DATA_QUALITY_EXCELLENT_YEARS = 5
    DATA_QUALITY_GOOD_YEARS = 4
    DATA_QUALITY_AVERAGE_YEARS = 3
    DATA_QUALITY_POOR_YEARS = 2


class ScoringConfig:
    """Configuration for scoring algorithms."""

    # Score Scale
    SCORE_MIN = 0.0
    SCORE_MAX = 10.0
    COMPOSITE_SCORE_MIN = 0.0
    COMPOSITE_SCORE_MAX = 100.0

    # Score Tiers
    ELITE_THRESHOLD = 85.0
    STRONG_THRESHOLD = 70.0
    MODERATE_THRESHOLD = 50.0

    # High Quality Threshold
    HIGH_QUALITY_THRESHOLD = 7.0

    # Consistent ROE Threshold
    CONSISTENT_ROE_THRESHOLD = 0.15
    CONSISTENT_ROE_YEARS = 10


class DataRequirements:
    """Data requirements for quality analysis."""

    REQUIRED_FIELDS = [
        'ticker',
        'revenue',
        'cogs',
        'total_assets',
        'net_income',
        'shareholder_equity',
        'free_cash_flow',
        'market_cap',
        'total_debt',
        'nopat'
    ]

    OPTIONAL_FIELDS = [
        'operating_cash_flow',
        'prior_year_data',
        'roe_history',
        'revenue_history',
        'margin_history',
        'stock_returns',
        'market_returns',
        'sga',
        'ebitda',
        'ebit',
        'interest_expense',
        'retained_earnings',
        'sales',
        'working_capital',
        'shares_outstanding'
    ]

    MINIMUM_LOOKBACK_YEARS = {
        'profitability': 1,
        'earnings_quality': 1,
        'growth_quality': 3,
        'safety': 3,
        'roe_persistence': 5
    }

    RECOMMENDED_LOOKBACK_YEARS = {
        'profitability': 3,
        'earnings_quality': 5,
        'growth_quality': 5,
        'safety': 5,
        'roe_persistence': 10
    }


def validate_config() -> Tuple[bool, List[str]]:
    """
    Validate the quality configuration.

    Returns:
        Tuple of (is_valid, list of validation errors)
    """
    config = get_quality_config()
    errors = []

    # Validate dimension weights sum to 1.0
    weight_sum = sum(config.DIMENSION_WEIGHTS.values())
    if abs(weight_sum - 1.0) > 0.001:
        errors.append(
            f"Dimension weights sum to {weight_sum}, expected 1.0"
        )

    # Validate tier thresholds are in order
    thresholds = config.TIER_THRESHOLDS
    if thresholds['ELITE'] <= thresholds['STRONG']:
        errors.append("ELITE threshold must be > STRONG threshold")
    if thresholds['STRONG'] <= thresholds['MODERATE']:
        errors.append("STRONG threshold must be > MODERATE threshold")
    if thresholds['MODERATE'] <= thresholds['WEAK']:
        errors.append("MODERATE threshold must be > WEAK threshold")

    return len(errors) == 0, errors


# Run validation on import
is_valid, validation_errors = validate_config()
if not is_valid:
    import logging
    logger = logging.getLogger(__name__)
    for error in validation_errors:
        logger.warning(f"Configuration validation error: {error}")
