"""
FMP API Configuration

Standardized configuration for Financial Modeling Prep API rate limiting and usage.
This module centralizes all API tier definitions, market cap thresholds, and rate limits.

Author: API Rate Limiting System
Date: January 2026
"""

from typing import Dict
from dataclasses import dataclass
from enum import Enum


class MarketCapTier(Enum):
    """FMP API market cap tier classification"""
    MICRO_CAP = "micro_cap"    # <$2B - skip FMP entirely
    SMALL_CAP = "small_cap"     # $2B-$10B - 2 API calls
    LARGE_CAP = "large_cap"     # $10B-$500B - 4 API calls
    MEGA_CAP = "mega_cap"       # ≥$500B - 5 API calls


@dataclass
class FMPTierConfig:
    """Configuration for FMP API market cap tiers"""
    threshold: int           # Minimum market cap in dollars
    api_calls: int          # Number of API calls required
    years_of_data: int      # Years of historical data to fetch
    priority: int           # Analysis priority (lower = higher priority)
    description: str         # Human-readable description


# Standardized FMP API Tier Configuration
FMP_TIER_CONFIGS: Dict[MarketCapTier, FMPTierConfig] = {
    MarketCapTier.MICRO_CAP: FMPTierConfig(
        threshold=0,                    # <$2B
        api_calls=0,                    # Skip FMP entirely
        years_of_data=0,                # Use yfinance only
        priority=4,                     # Lowest priority
        description="Micro caps (<$2B) - Skip FMP, use yfinance only"
    ),
    
    MarketCapTier.SMALL_CAP: FMPTierConfig(
        threshold=2_000_000_000,        # $2B+
        api_calls=2,                    # ratios + score
        years_of_data=3,                # Moderate history
        priority=2,                     # Medium priority
        description="Small caps ($2B-$10B) - Basic analysis (2 API calls)"
    ),
    
    MarketCapTier.LARGE_CAP: FMPTierConfig(
        threshold=10_000_000_000,       # $10B+
        api_calls=4,                    # ratios + score + income + balance
        years_of_data=5,                # Full history
        priority=1,                     # High priority
        description="Large caps ($10B-$500B) - Growth analysis (4 API calls)"
    ),
    
    MarketCapTier.MEGA_CAP: FMPTierConfig(
        threshold=500_000_000_000,     # $500B+
        api_calls=5,                    # All 5 endpoints
        years_of_data=5,                # Full history
        priority=1,                     # Highest priority
        description="Mega caps (≥$500B) - Premium analysis (5 API calls)"
    )
}


# API Tier Configuration for different subscription levels
API_TIER_CONFIGS = {
    'FREE': {
        'daily_limit': 250,
        'hourly_limit': 50,
        'burst_limit': 10,
        'max_years': 5,
        'endpoints': ['ratios', 'score', 'income', 'balance', 'cash_flow'],
        'cache_expiry_days': 30
    },
    'PREMIUM': {
        'daily_limit': 1000,
        'hourly_limit': 200,
        'burst_limit': 25,
        'max_years': 10,
        'endpoints': ['all', 'premium'],
        'cache_expiry_days': 15
    },
    'ENTERPRISE': {
        'daily_limit': 5000,
        'hourly_limit': 1000,
        'burst_limit': 50,
        'max_years': 20,
        'endpoints': ['all', 'premium', 'institutional'],
        'cache_expiry_days': 7
    }
}


# Endpoint-specific cache expiry (days)
CACHE_EXPIRY_BY_ENDPOINT = {
    'ratios': 30,        # Fundamental metrics - very stable
    'score': 7,          # Piotroski/Z-Score - quarterly updates
    'income': 15,        # Revenue statements - moderate volatility
    'balance': 20,       # Balance sheet - relatively stable
    'cash_flow': 10      # Cash flow - quarterly volatility
}


def get_market_cap_tier(market_cap: float) -> MarketCapTier:
    """
    Determine FMP market cap tier based on market capitalization.
    
    Args:
        market_cap: Market capitalization in dollars
        
    Returns:
        MarketCapTier enum value
    """
    if market_cap >= 500_000_000_000:     # ≥$500B
        return MarketCapTier.MEGA_CAP
    elif market_cap >= 10_000_000_000:    # ≥$10B
        return MarketCapTier.LARGE_CAP
    elif market_cap >= 2_000_000_000:     # ≥$2B
        return MarketCapTier.SMALL_CAP
    else:                                 # <$2B
        return MarketCapTier.MICRO_CAP


def get_tier_config(tier: MarketCapTier) -> FMPTierConfig:
    """
    Get configuration for a specific market cap tier.
    
    Args:
        tier: MarketCapTier enum value
        
    Returns:
        FMPTierConfig object
    """
    return FMP_TIER_CONFIGS[tier]


def get_api_calls_needed(market_cap: float) -> int:
    """
    Calculate number of API calls needed for a given market cap.
    
    Args:
        market_cap: Market capitalization in dollars
        
    Returns:
        Number of API calls required
    """
    tier = get_market_cap_tier(market_cap)
    config = get_tier_config(tier)
    return config.api_calls


def get_years_of_data(market_cap: float) -> int:
    """
    Get recommended years of historical data for a market cap.
    
    Args:
        market_cap: Market capitalization in dollars
        
    Returns:
        Number of years of historical data to fetch
    """
    tier = get_market_cap_tier(market_cap)
    config = get_tier_config(tier)
    return config.years_of_data


def validate_api_tier(tier_name: str) -> bool:
    """
    Validate if API tier name is supported.
    
    Args:
        tier_name: Name of API tier (FREE, PREMIUM, ENTERPRISE)
        
    Returns:
        True if tier is supported, False otherwise
    """
    return tier_name.upper() in API_TIER_CONFIGS


def get_api_tier_config(tier_name: str = 'FREE') -> Dict:
    """
    Get configuration for a specific API tier.
    
    Args:
        tier_name: Name of API tier (defaults to FREE)
        
    Returns:
        Configuration dictionary for the tier
    """
    tier_name = tier_name.upper()
    if not validate_api_tier(tier_name):
        raise ValueError(f"Unsupported API tier: {tier_name}")
    
    return API_TIER_CONFIGS[tier_name]