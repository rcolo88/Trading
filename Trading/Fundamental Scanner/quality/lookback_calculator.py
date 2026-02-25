"""
Lookback Period Calculator for Quality Analysis

This module calculates market-cap-adjusted lookback periods for quality metrics
based on the framework defined in UPDATES.md.

Key Principle: Smaller caps require shorter lookbacks due to data availability
and higher volatility. Larger caps have more stable metrics, allowing longer
lookbacks.

Market Cap Tiers and Multipliers:
- Mega Cap (> $200B): 1.25x (extended lookback)
- Large Cap ($10B-$200B): 1.0x (baseline)
- Mid Cap ($2B-$10B): 0.75x (reduced lookback)
- Small Cap ($300M-$2B): 0.75x (moderate lookback - extended from 0.5x)
- Micro Cap (< $300M): 0.5x (conservative lookback - extended from 0.35x)

Formula:
    Adjusted Lookback = Base Lookback × Market Cap Multiplier × Sector Adjustment

Example:
    - Base lookback for ROE Persistence: 5 years
    - Large Cap multiplier: 1.0x
    - Adjusted lookback: 5 × 1.0 = 5 years

    - Base lookback for ROE Persistence: 5 years
    - Small Cap multiplier: 0.5x
    - Adjusted lookback: 5 × 0.5 = 2.5 years (rounded to 2-3 years)

Author: Quality Analysis System
Date: January 2026
"""

from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarketCapTier(Enum):
    """Market capitalization tier classification with lookback multipliers."""
    MEGA_CAP = "Mega Cap"      # > $200B
    LARGE_CAP = "Large Cap"    # $10B - $200B
    MID_CAP = "Mid Cap"        # $2B - $10B
    SMALL_CAP = "Small Cap"    # $300M - $2B
    MICRO_CAP = "Micro Cap"    # < $300M


# Market cap tier thresholds (in dollars)
MEGA_CAP_THRESHOLD = 200_000_000_000   # $200 billion
LARGE_CAP_THRESHOLD = 10_000_000_000   # $10 billion
MID_CAP_THRESHOLD = 2_000_000_000      # $2 billion
SMALL_CAP_THRESHOLD = 300_000_000      # $300 million

# Default lookback periods by quality dimension (in years)
DEFAULT_LOOKBACKS = {
    'profitability': 1,
    'earnings_quality': 1,
    'growth_quality': 3,
    'safety': 3,
    'roe_persistence': 5
}

# Sector-specific adjustments (multipliers applied after market cap)
SECTOR_ADJUSTMENTS = {
    'Technology': 0.8,     # Fast-changing; reduce lookback
    'Healthcare': 1.1,     # R&D-intensive; extend slightly
    'Utilities': 1.1,      # Slow-changing; extend slightly
    'Industrials': 1.1,    # Long cycles; extend slightly
    'Financials': 1.0,     # Regulated; standard lookback
    'Consumer Cyclicals': 1.0,  # Variable; standard lookback
    'Real Estate': 1.0,    # Stable; standard lookback
    'Communication Services': 0.9,  # Mixed; slight reduction
    'Materials': 1.0,      # Cyclical; standard lookback
    'Energy': 1.0,         # Volatile; standard lookback
}

# Quality dimension configurations
QUALITY_DIMENSIONS = {
    'profitability': {
        'metrics': ['gross_profitability', 'roe', 'roic', 'operating_margin', 'fcf_margin'],
        'default_lookback': 1,
        'min_lookback': 1,
        'max_lookback': 3
    },
    'earnings_quality': {
        'metrics': ['accrual_ratio', 'cash_conversion', 'f_score'],
        'default_lookback': 1,
        'min_lookback': 1,
        'max_lookback': 3
    },
    'growth_quality': {
        'metrics': ['asset_growth', 'revenue_cagr', 'margin_trend', 'revenue_quality'],
        'default_lookback': 3,
        'min_lookback': 1,
        'max_lookback': 5
    },
    'safety': {
        'metrics': ['beta', 'volatility', 'leverage', 'z_score', 'interest_coverage'],
        'default_lookback': 3,
        'min_lookback': 1,
        'max_lookback': 5
    },
    'roe_persistence': {
        'metrics': ['roe_mean', 'roe_persistence', 'roe_trend', 'incremental_roce'],
        'default_lookback': 5,
        'min_lookback': 2,
        'max_lookback': 5
    }
}


@dataclass
class LookbackResult:
    """Result of lookback calculation for a single metric."""
    metric_name: str
    base_lookback: float
    adjusted_lookback: float
    market_cap_tier: MarketCapTier
    market_cap_multiplier: float
    sector_adjustment: float
    data_availability_adjustment: float
    
    def to_dict(self) -> dict:
        return {
            'metric_name': self.metric_name,
            'base_lookback': self.base_lookback,
            'adjusted_lookback': self.adjusted_lookback,
            'market_cap_tier': self.market_cap_tier.value,
            'market_cap_multiplier': self.market_cap_multiplier,
            'sector_adjustment': self.sector_adjustment,
            'data_availability_adjustment': self.data_availability_adjustment
        }


@dataclass  
class DimensionLookbackResult:
    """Lookback calculation result for an entire quality dimension."""
    dimension: str
    metrics: Dict[str, LookbackResult]
    average_lookback: float
    primary_lookback: float  # For display purposes


class LookbackCalculator:
    """
    Calculate market-cap-adjusted lookback periods for quality metrics.
    
    This calculator implements the framework from UPDATES.md where smaller
    companies use shorter lookbacks due to data availability and higher
    volatility, while larger companies can use longer lookbacks for more
    stable measurements.
    
    Example:
        >>> calculator = LookbackCalculator()
        >>> result = calculator.calculate_lookback(
        ...     base_lookback=5,
        ...     market_cap=50_000_000_000,  # $50B
        ...     sector='Technology',
        ...     data_years=4
        ... )
        >>> print(f"Adjusted lookback: {result.adjusted_lookback} years")
    """
    
    # Market cap tier multipliers (smaller cap = smaller multiplier)
    # Updated: Extended lookbacks for small and micro caps (conservative approach)
    MARKET_CAP_MULTIPLIERS = {
        MarketCapTier.MEGA_CAP: 1.25,
        MarketCapTier.LARGE_CAP: 1.0,
        MarketCapTier.MID_CAP: 0.75,
        MarketCapTier.SMALL_CAP: 0.75,  # Extended from 0.5x
        MarketCapTier.MICRO_CAP: 0.5   # Extended from 0.35x
    }
    
    def __init__(self):
        """Initialize the Lookback Calculator."""
        logger.info("LookbackCalculator initialized")
    
    @staticmethod
    def classify_market_cap(market_cap: float) -> MarketCapTier:
        """
        Classify market cap value into tier.
        
        Args:
            market_cap: Market capitalization in dollars
            
        Returns:
            MarketCapTier enum value
            
        Raises:
            ValueError: If market_cap is not positive
        """
        if market_cap <= 0:
            raise ValueError(f"Market cap must be positive, got {market_cap}")
        
        if market_cap >= MEGA_CAP_THRESHOLD:
            return MarketCapTier.MEGA_CAP
        elif market_cap >= LARGE_CAP_THRESHOLD:
            return MarketCapTier.LARGE_CAP
        elif market_cap >= MID_CAP_THRESHOLD:
            return MarketCapTier.MID_CAP
        elif market_cap >= SMALL_CAP_THRESHOLD:
            return MarketCapTier.SMALL_CAP
        else:
            return MarketCapTier.MICRO_CAP
    
    def get_multiplier(self, market_cap_tier: MarketCapTier) -> float:
        """
        Get the lookback multiplier for a market cap tier.
        
        Args:
            market_cap_tier: The company's market cap tier
            
        Returns:
            Multiplier value (0.35 to 1.25)
        """
        return self.MARKET_CAP_MULTIPLIERS.get(market_cap_tier, 1.0)
    
    def get_sector_adjustment(self, sector: Optional[str] = None) -> float:
        """
        Get the sector-specific adjustment multiplier.
        
        Args:
            sector: GICS sector name (e.g., 'Technology', 'Healthcare')
            
        Returns:
            Adjustment multiplier (0.8 to 1.1)
        """
        if sector is None:
            return 1.0
        return SECTOR_ADJUSTMENTS.get(sector, 1.0)
    
    def get_data_availability_adjustment(self, available_years: Optional[int] = None,
                                          required_years: int = 1) -> float:
        """
        Get adjustment based on data availability.
        
        Args:
            available_years: Years of historical data available
            required_years: Years required for the calculation
            
        Returns:
            Adjustment multiplier (0.5 to 1.0)
        """
        if available_years is None:
            return 1.0
        
        if available_years >= required_years:
            return 1.0
        elif available_years >= 2:
            # Penalty for limited data
            return 0.8
        else:
            # Severe penalty for very limited data
            return 0.5
    
    def validate_minimum_data_requirements(self, market_cap_tier: MarketCapTier, 
                                          available_years: Optional[int] = None) -> Tuple[bool, str]:
        """
        Validate minimum data requirements for extended lookback periods.
        
        Args:
            market_cap_tier: The company's market cap tier
            available_years: Years of historical data available
            
        Returns:
            Tuple of (is_valid, message)
        """
        # Define minimum data requirements by tier (in years)
        MIN_DATA_REQUIREMENTS = {
            MarketCapTier.MEGA_CAP: 5,    # Need at least 5 years for mega caps
            MarketCapTier.LARGE_CAP: 3,    # Need at least 3 years for large caps
            MarketCapTier.MID_CAP: 3,     # Need at least 3 years for mid caps
            MarketCapTier.SMALL_CAP: 2,   # Need at least 2 years for small caps
            MarketCapTier.MICRO_CAP: 2    # Need at least 2 years for micro caps
        }
        
        if available_years is None:
            return True, "Data availability unknown - proceeding with caution"
        
        min_required = MIN_DATA_REQUIREMENTS.get(market_cap_tier, 2)
        
        if available_years >= min_required:
            return True, f"Sufficient data: {available_years} years available (minimum {min_required})"
        else:
            return False, (f"Insufficient data: {available_years} years available, "
                          f"minimum {min_required} required for {market_cap_tier.value} lookback analysis")
    
    def calculate_lookback(
        self,
        base_lookback: float,
        market_cap: float,
        sector: Optional[str] = None,
        data_years: Optional[int] = None,
        metric_name: str = "unknown"
    ) -> LookbackResult:
        """
        Calculate adjusted lookback period for a single metric.
        
        Formula:
            Adjusted Lookback = Base × Market Cap Multiplier × Sector Adjustment × Data Adjustment
            
        Args:
            base_lookback: Default lookback period from quality dimension
            market_cap: Company market capitalization in dollars
            sector: GICS sector name (optional)
            data_years: Years of historical data available (optional)
            metric_name: Name of the metric being calculated
            
        Returns:
            LookbackResult with adjusted lookback and breakdown
        """
        # Step 1: Classify market cap tier
        market_cap_tier = self.classify_market_cap(market_cap)
        
        # Step 2: Validate minimum data requirements
        if data_years is not None:
            is_valid, validation_msg = self.validate_minimum_data_requirements(market_cap_tier, data_years)
            if not is_valid:
                logger.warning(f"Data validation failed for {metric_name}: {validation_msg}")
                # Reduce lookback to available data years if insufficient
                adjusted = min(base_lookback, max(1, data_years))
                data_adj = 0.5  # Penalty for insufficient data
            else:
                logger.debug(f"Data validation passed for {metric_name}: {validation_msg}")
        
        # Step 3: Get market cap multiplier
        market_cap_multiplier = self.get_multiplier(market_cap_tier)
        
        # Step 4: Get sector adjustment
        sector_adjustment = self.get_sector_adjustment(sector)
        
        # Step 5: Calculate adjusted lookback
        adjusted = base_lookback * market_cap_multiplier * sector_adjustment
        
        # Step 6: Apply data availability constraint
        if data_years is not None:
            adjusted = min(adjusted, max(1, data_years))
        
        # Enforce minimum of 1 year
        adjusted = max(1, adjusted)
        
        # Step 7: Get data availability adjustment
        data_adj = self.get_data_availability_adjustment(data_years, int(base_lookback))
        
        logger.debug(
            f"Lookback for {metric_name}: base={base_lookback}, "
            f"tier={market_cap_tier.value}, adj={adjusted:.2f}"
        )
        
        return LookbackResult(
            metric_name=metric_name,
            base_lookback=base_lookback,
            adjusted_lookback=round(adjusted, 1),
            market_cap_tier=market_cap_tier,
            market_cap_multiplier=market_cap_multiplier,
            sector_adjustment=sector_adjustment,
            data_availability_adjustment=data_adj
        )
    
    def calculate_dimension_lookback(
        self,
        dimension: str,
        market_cap: float,
        sector: Optional[str] = None,
        data_years: Optional[int] = None
    ) -> DimensionLookbackResult:
        """
        Calculate lookbacks for all metrics in a quality dimension.
        
        Args:
            dimension: Quality dimension name (e.g., 'profitability', 'safety')
            market_cap: Company market capitalization
            sector: GICS sector name
            data_years: Years of historical data available
            
        Returns:
            DimensionLookbackResult with all metric calculations
        """
        if dimension not in QUALITY_DIMENSIONS:
            raise ValueError(f"Unknown dimension: {dimension}")
        
        config = QUALITY_DIMENSIONS[dimension]
        base_lookback = config['default_lookback']
        
        results = {}
        lookbacks = []
        
        for metric in config['metrics']:
            result = self.calculate_lookback(
                base_lookback=base_lookback,
                market_cap=market_cap,
                sector=sector,
                data_years=data_years,
                metric_name=metric
            )
            results[metric] = result
            lookbacks.append(result.adjusted_lookback)
        
        # Calculate averages
        avg_lookback = sum(lookbacks) / len(lookbacks) if lookbacks else base_lookback
        
        return DimensionLookbackResult(
            dimension=dimension,
            metrics=results,
            average_lookback=round(avg_lookback, 1),
            primary_lookback=base_lookback
        )
    
    def calculate_all_dimensions(
        self,
        market_cap: float,
        sector: Optional[str] = None,
        data_years: Optional[int] = None
    ) -> Dict[str, DimensionLookbackResult]:
        """
        Calculate lookbacks for all quality dimensions.
        
        Args:
            market_cap: Company market capitalization
            sector: GICS sector name
            data_years: Years of historical data available
            
        Returns:
            Dictionary mapping dimension names to lookback results
        """
        results = {}
        
        for dimension in QUALITY_DIMENSIONS.keys():
            results[dimension] = self.calculate_dimension_lookback(
                dimension=dimension,
                market_cap=market_cap,
                sector=sector,
                data_years=data_years
            )
        
        return results
    
    def get_lookback_summary(
        self,
        market_cap: float,
        sector: Optional[str] = None
    ) -> str:
        """
        Generate human-readable summary of lookback periods.
        
        Args:
            market_cap: Company market capitalization
            sector: GICS sector name
            
        Returns:
            Formatted summary string
        """
        tier = self.classify_market_cap(market_cap)
        multiplier = self.get_multiplier(tier)
        
        lines = [
            "=" * 60,
            "LOOKBACK PERIOD SUMMARY",
            "=" * 60,
            f"Market Cap: ${market_cap/1e9:.1f}B",
            f"Tier: {tier.value}",
            f"Market Cap Multiplier: {multiplier:.2f}x",
            f"Sector Adjustment: {self.get_sector_adjustment(sector):.2f}x",
            "-" * 60,
            "Dimension Lookbacks:",
            "-" * 60
        ]
        
        for dimension in QUALITY_DIMENSIONS.keys():
            result = self.calculate_dimension_lookback(
                dimension=dimension,
                market_cap=market_cap,
                sector=sector
            )
            lines.append(f"  {dimension:20} | Avg: {result.average_lookback:.1f} years | "
                        f"Base: {result.primary_lookback} years")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def get_recommended_lookback(self, metric_name: str, market_cap: float,
                                  sector: Optional[str] = None,
                                  data_years: Optional[int] = None) -> float:
        """
        Get recommended lookback for a specific metric.
        
        Args:
            metric_name: Name of the metric
            market_cap: Company market capitalization
            sector: GICS sector name
            data_years: Years of historical data available
            
        Returns:
            Recommended lookback period in years
        """
        # Find which dimension this metric belongs to
        for dimension, config in QUALITY_DIMENSIONS.items():
            if metric_name in config['metrics']:
                base_lookback = config['default_lookback']
                result = self.calculate_lookback(
                    base_lookback=base_lookback,
                    market_cap=market_cap,
                    sector=sector,
                    data_years=data_years,
                    metric_name=metric_name
                )
                return result.adjusted_lookback
        
        # If metric not found in any dimension, use default of 1 year
        logger.warning(f"Metric {metric_name} not found in any dimension, using default 1 year")
        return 1.0


def get_lookback_calculator() -> LookbackCalculator:
    """Factory function to get a LookbackCalculator instance."""
    return LookbackCalculator()


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example: Large cap tech company
    calculator = LookbackCalculator()
    
    # Apple example
    apple_market_cap = 3_000_000_000_000  # $3T
    apple_sector = "Technology"
    
    print(calculator.get_lookback_summary(apple_market_cap, apple_sector))
    print()
    
    # Small cap example
    small_market_cap = 500_000_000  # $500M
    small_sector = "Healthcare"
    
    print(calculator.get_lookback_summary(small_market_cap, small_sector))
