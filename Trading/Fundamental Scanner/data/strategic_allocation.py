"""
Strategic Allocation Manager for Optimal API Usage

Intelligently allocates API calls across stocks based on market cap tiers,
portfolio priorities, and analysis goals. Maximizes coverage while staying within
API limits.

Author: API Rate Limiting System  
Date: January 2026
"""

import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .fmp_config import get_market_cap_tier, get_api_calls_needed, MarketCapTier
from .fmp_cache_tracker import FMPCacheTracker

logger = logging.getLogger(__name__)


class AllocationStrategy(Enum):
    """Allocation strategy types"""
    COVERAGE_FOCUS = "coverage_focus"      # Maximize number of stocks analyzed
    QUALITY_FOCUS = "quality_focus"        # Prioritize high-value stocks  
    BALANCED = "balanced"                   # Balance coverage and quality
    PORTFOLIO_PRIORITY = "portfolio_priority"  # Prioritize current holdings


class PriorityCategory(Enum):
    """Priority categories for allocation"""
    CRITICAL = "critical"     # Portfolio holdings, mega-caps
    HIGH = "high"            # Large-caps, key watchlist
    MEDIUM = "medium"         # Mid-caps for breadth
    LOW = "low"              # Small-caps, experimental


@dataclass
class AllocationResult:
    """Result of strategic allocation"""
    allocated_tickers: Dict[str, List[str]]  # Priority category -> tickers
    total_stocks: int
    estimated_calls: int
    allocation_efficiency: float  # Calls used / calls available
    strategy_used: str
    remaining_calls: int


@dataclass 
class StockPriority:
    """Stock priority information"""
    ticker: str
    market_cap: float
    tier: MarketCapTier
    api_calls: int
    priority_score: float  # Higher = more important
    category: PriorityCategory


class StrategicAllocationManager:
    """
    Manages strategic allocation of API calls for optimal coverage.
    
    Features:
    - Market cap-aware allocation
    - Priority-based stock selection  
    - Strategy optimization
    - Efficiency tracking
    """
    
    def __init__(self, cache_tracker: FMPCacheTracker):
        """
        Initialize strategic allocation manager.
        
        Args:
            cache_tracker: FMP cache tracker instance
        """
        self.cache_tracker = cache_tracker
        self.allocation_history: List[AllocationResult] = []
        
    def allocate_daily_calls(
        self,
        tickers: List[str],
        strategy: AllocationStrategy = AllocationStrategy.BALANCED,
        portfolio_holdings: Optional[List[str]] = None,
        available_calls: Optional[int] = None
    ) -> AllocationResult:
        """
        Allocate API calls for optimal daily usage.
        
        Args:
            tickers: List of tickers to consider
            strategy: Allocation strategy to use
            portfolio_holdings: Current portfolio holdings (highest priority)
            available_calls: Available API calls (calculated if None)
            
        Returns:
            AllocationResult with optimal allocation
        """
        if available_calls is None:
            available_calls = self.cache_tracker.max_daily_calls - self.cache_tracker.cache_data['daily_calls']
            
        logger.info(f"Allocating {available_calls} API calls for {len(tickers)} tickers using {strategy.value} strategy")
        
        # Step 1: Calculate priorities for all tickers
        stock_priorities = self._calculate_stock_priorities(
            tickers, portfolio_holdings, strategy
        )
        
        # Step 2: Sort by priority (highest first)
        stock_priorities.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Step 3: Greedy allocation by priority
        allocated_tickers = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        calls_used = 0
        allocated_count = 0
        
        for stock in stock_priorities:
            if calls_used + stock.api_calls <= available_calls:
                allocated_tickers[stock.category.value].append(stock.ticker)
                calls_used += stock.api_calls
                allocated_count += 1
            else:
                continue  # Skip if not enough calls remaining
        
        efficiency = calls_used / available_calls if available_calls > 0 else 0
        
        result = AllocationResult(
            allocated_tickers=allocated_tickers,
            total_stocks=allocated_count,
            estimated_calls=calls_used,
            allocation_efficiency=efficiency,
            strategy_used=strategy.value,
            remaining_calls=available_calls - calls_used
        )
        
        self.allocation_history.append(result)
        
        logger.info(
            f"Allocated {allocated_count} stocks using {calls_used}/{available_calls} calls "
            f"(efficiency: {efficiency:.1%}, remaining: {result.remaining_calls})"
        )
        
        return result
    
    def _calculate_stock_priorities(
        self,
        tickers: List[str],
        portfolio_holdings: Optional[List[str]],
        strategy: AllocationStrategy
    ) -> List[StockPriority]:
        """
        Calculate priority scores for all tickers.
        
        Args:
            tickers: List of ticker symbols
            portfolio_holdings: Current portfolio holdings
            strategy: Allocation strategy
            
        Returns:
            List of StockPriority objects sorted by priority
        """
        priorities = []
        
        for ticker in tickers:
            market_cap = self.cache_tracker.get_market_cap_for_ticker(ticker)
            tier = get_market_cap_tier(market_cap)
            api_calls = get_api_calls_needed(market_cap)
            category = self._determine_category(tier, portfolio_holdings, ticker)
            
            priority_score = self._calculate_priority_score(
                tier, category, market_cap, strategy, ticker
            )
            
            priorities.append(StockPriority(
                ticker=ticker,
                market_cap=market_cap,
                tier=tier,
                api_calls=api_calls,
                priority_score=priority_score,
                category=category
            ))
        
        return priorities
    
    def _determine_category(
        self,
        tier: MarketCapTier,
        portfolio_holdings: Optional[List[str]],
        ticker: str
    ) -> PriorityCategory:
        """
        Determine priority category for a stock.
        
        Args:
            tier: Market cap tier
            portfolio_holdings: Current portfolio holdings
            ticker: Stock ticker
            
        Returns:
            PriorityCategory enum value
        """
        # Portfolio holdings are highest priority
        if portfolio_holdings and ticker in portfolio_holdings:
            return PriorityCategory.CRITICAL
        
        # Mega caps are critical for quality analysis
        if tier == MarketCapTier.MEGA_CAP:
            return PriorityCategory.CRITICAL
        
        # Large caps are high priority
        if tier == MarketCapTier.LARGE_CAP:
            return PriorityCategory.HIGH
        
        # Mid caps are medium priority
        if tier == MarketCapTier.SMALL_CAP:
            return PriorityCategory.MEDIUM
        
        # Micro caps are low priority (no API calls needed)
        return PriorityCategory.LOW
    
    def _calculate_priority_score(
        self,
        tier: MarketCapTier,
        category: PriorityCategory,
        market_cap: float,
        strategy: AllocationStrategy,
        ticker: str
    ) -> float:
        """
        Calculate priority score based on strategy and stock characteristics.
        
        Args:
            tier: Market cap tier
            category: Priority category
            market_cap: Market capitalization
            strategy: Allocation strategy
            ticker: Stock ticker
            
        Returns:
            Priority score (higher = more important)
        """
        # Base score by category
        category_scores = {
            PriorityCategory.CRITICAL: 1000,
            PriorityCategory.HIGH: 750,
            PriorityCategory.MEDIUM: 500,
            PriorityCategory.LOW: 100
        }
        base_score = category_scores[category]
        
        # Strategy adjustments
        if strategy == AllocationStrategy.COVERAGE_FOCUS:
            # Favor small caps (fewer calls) for maximum coverage
            tier_multiplier = {
                MarketCapTier.MICRO_CAP: 2.0,  # Skip FMP entirely
                MarketCapTier.SMALL_CAP: 1.8,   # 2 calls
                MarketCapTier.LARGE_CAP: 1.0,   # 4 calls
                MarketCapTier.MEGA_CAP: 0.8      # 5 calls
            }
        elif strategy == AllocationStrategy.QUALITY_FOCUS:
            # Favor large/mega caps for deep analysis
            tier_multiplier = {
                MarketCapTier.MICRO_CAP: 0.5,
                MarketCapTier.SMALL_CAP: 0.7,
                MarketCapTier.LARGE_CAP: 1.2,
                MarketCapTier.MEGA_CAP: 1.5
            }
        elif strategy == AllocationStrategy.BALANCED:
            # Balanced approach
            tier_multiplier = {
                MarketCapTier.MICRO_CAP: 1.5,
                MarketCapTier.SMALL_CAP: 1.3,
                MarketCapTier.LARGE_CAP: 1.1,
                MarketCapTier.MEGA_CAP: 1.0
            }
        elif strategy == AllocationStrategy.PORTFOLIO_PRIORITY:
            # Strongly favor portfolio holdings
            tier_multiplier = {
                MarketCapTier.MICRO_CAP: 1.0,
                MarketCapTier.SMALL_CAP: 1.2,
                MarketCapTier.LARGE_CAP: 1.4,
                MarketCapTier.MEGA_CAP: 1.3
            }
        else:
            tier_multiplier = {tier: 1.0 for tier in MarketCapTier}
        
        # Market cap size adjustment (log scale for diminishing returns)
        if market_cap > 0:
            size_adjustment = 1 + (min(market_cap, 1e12) / 1e12) ** 0.5 * 0.2
        else:
            size_adjustment = 1.0
        
        final_score = base_score * tier_multiplier.get(tier, 1.0) * size_adjustment
        
        return final_score
    
    def get_allocation_summary(self) -> Dict:
        """
        Get summary of allocation history and performance.
        
        Returns:
            Dict with allocation statistics
        """
        if not self.allocation_history:
            return {'message': 'No allocation history available'}
        
        recent_allocations = self.allocation_history[-10:]  # Last 10 allocations
        
        avg_efficiency = sum(a.allocation_efficiency for a in recent_allocations) / len(recent_allocations)
        avg_stocks = sum(a.total_stocks for a in recent_allocations) / len(recent_allocations)
        avg_calls = sum(a.estimated_calls for a in recent_allocations) / len(recent_allocations)
        
        strategy_usage = {}
        for allocation in recent_allocations:
            strategy = allocation.strategy_used
            strategy_usage[strategy] = strategy_usage.get(strategy, 0) + 1
        
        return {
            'recent_allocations': len(recent_allocations),
            'average_efficiency': avg_efficiency,
            'average_stocks_per_day': avg_stocks,
            'average_calls_per_day': avg_calls,
            'strategy_usage': strategy_usage,
            'total_allocation_history': len(self.allocation_history)
        }
    
    def recommend_strategy(
        self,
        tickers: List[str],
        available_calls: Optional[int] = None
    ) -> Dict[str, AllocationStrategy]:
        """
        Recommend optimal strategy based on current conditions.
        
        Args:
            tickers: Available tickers to analyze
            available_calls: Available API calls
            
        Returns:
            Dict with strategy recommendations and expected outcomes
        """
        if available_calls is None:
            available_calls = self.cache_tracker.max_daily_calls - self.cache_tracker.cache_data['daily_calls']
        
        recommendations = {}
        
        # Simulate each strategy
        for strategy in AllocationStrategy:
            result = self.allocate_daily_calls(tickers, strategy, None, available_calls)
            recommendations[strategy.value] = {
                'strategy': strategy,
                'expected_stocks': result.total_stocks,
                'expected_calls': result.estimated_calls,
                'efficiency': result.allocation_efficiency,
                'coverage_rate': result.total_stocks / len(tickers) if tickers else 0
            }
        
        # Find best strategy by different metrics
        best_coverage = max(recommendations.values(), key=lambda x: x['coverage_rate'])
        best_efficiency = max(recommendations.values(), key=lambda x: x['efficiency'])
        
        return {
            'recommendations': recommendations,
            'best_for_coverage': best_coverage['strategy'].value,
            'best_for_efficiency': best_efficiency['strategy'].value,
            'current_calls_available': available_calls,
            'total_candidates': len(tickers)
        }