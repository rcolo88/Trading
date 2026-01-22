"""
Multi-Day Orchestration Manager for Large Dataset Analysis

Manages multi-day processing of large stock indices (Russell 3000) within API rate limits.
Intelligently allocates API calls across market cap tiers and provides resume capability.

Key Features:
- Daily API budget allocation (250 calls/day for FMP)
- Market cap tier prioritization (Mega → Large → Small → Micro)
- Resume capability from previous sessions
- Real-time progress tracking and ETA calculations
- Integration with existing quality analysis system

Author: Multi-Day Orchestration System
Date: January 2026
"""

import logging
import json
from typing import Dict, List, Tuple, Optional, NamedTuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from .fmp_config import get_market_cap_tier, get_api_calls_needed, MarketCapTier
from .fmp_cache_tracker import FMPCacheTracker
from .progress_tracker import ProgressTracker, ProgressState
from .quarterly_manager import QuarterlyManager

logger = logging.getLogger(__name__)


@dataclass
class DailyAllocation:
    """Daily API allocation configuration"""
    tier: str
    api_calls_per_stock: int
    daily_budget: int
    max_stocks_per_day: int
    priority: int


@dataclass
class QueueItem:
    """Item in the daily processing queue"""
    ticker: str
    market_cap_tier: MarketCapTier
    api_calls_needed: int
    priority: int
    last_updated: Optional[datetime] = None
    is_stale: bool = False


@dataclass
class DailyQueue:
    """Daily processing queue with prioritized stocks"""
    items: List[QueueItem]
    total_api_calls: int
    estimated_completion_time: timedelta
    session_date: datetime
    
    def get_tickers(self) -> List[str]:
        """Get list of tickers for today's processing"""
        return [item.ticker for item in self.items]
    
    def get_total_calls(self) -> int:
        """Get total API calls needed for today"""
        return sum(item.api_calls_needed for item in self.items)


class MultiDayOrchestrator:
    """
    Manages multi-day processing of large stock indices within API constraints.
    
    Coordinates between:
    - API rate limiting and budget management
    - Progress tracking across sessions
    - Quarterly data freshness management
    - Quality analysis execution
    """
    
    # Daily API allocation strategy (250 calls total)
    DAILY_ALLOCATIONS = [
        DailyAllocation('mega_cap', 5, 50, 10, 1),    # 10 mega caps/day
        DailyAllocation('large_cap', 4, 100, 25, 2),  # 25 large caps/day
        DailyAllocation('small_cap', 2, 80, 40, 3),   # 40 small caps/day
        DailyAllocation('micro_cap', 0, 20, 200, 4),  # Unlimited micro caps (yfinance only)
    ]
    
    def __init__(self, 
                 index_name: str = "russell3000",
                 data_dir: str = "data",
                 outputs_dir: str = "outputs",
                 max_daily_calls: int = 250):
        """
        Initialize the multi-day orchestrator.
        
        Args:
            index_name: Name of the index being processed
            data_dir: Directory for data files and databases
            outputs_dir: Directory for output files
            max_daily_calls: Maximum API calls per day
        """
        self.index_name = index_name
        self.data_dir = Path(data_dir)
        self.outputs_dir = Path(outputs_dir)
        self.max_daily_calls = max_daily_calls
        
        # Ensure directories exist
        self.data_dir.mkdir(exist_ok=True)
        self.outputs_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.cache_tracker = FMPCacheTracker()
        self.progress_tracker = ProgressTracker(str(self.data_dir / "progress.db"))
        self.quarterly_manager = QuarterlyManager(self.outputs_dir)
        
        # Load current state
        self.current_session = datetime.now()
        self.progress_state = self.progress_tracker.load_progress()
        self._all_tickers_cache: List[str] = []  # Will be set when run_session is called
        
        logger.info(f"MultiDayOrchestrator initialized for {index_name}")
        logger.info(f"Session date: {self.current_session.strftime('%Y-%m-%d')}")
    
    def get_market_cap_for_ticker(self, ticker: str) -> float:
        """
        Get market capitalization for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Market capitalization in dollars
        """
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            market_cap = stock.info.get('marketCap', 0)
            return market_cap or 0
        except Exception as e:
            logger.warning(f"Could not fetch market cap for {ticker}: {e}")
            return 0
    
    def classify_ticker_tier(self, ticker: str) -> Tuple[MarketCapTier, int]:
        """
        Classify ticker into market cap tier and determine API calls needed.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Tuple of (market_cap_tier, api_calls_needed)
        """
        market_cap = self.get_market_cap_for_ticker(ticker)
        tier = get_market_cap_tier(market_cap)
        api_calls = get_api_calls_needed(market_cap)
        
        return tier, api_calls
    
    def generate_queue_items(self, tickers: List[str]) -> List[QueueItem]:
        """
        Generate queue items with classification and prioritization.
        
        Args:
            tickers: List of ticker symbols to process
            
        Returns:
            List of QueueItem objects sorted by priority
        """
        items = []
        current_quarter = self.quarterly_manager.get_current_quarter()
        
        for ticker in tickers:
            tier, api_calls = self.classify_ticker_tier(ticker)
            
            # Get priority from allocation configuration
            priority = next(
                (alloc.priority for alloc in self.DAILY_ALLOCATIONS if alloc.tier == tier.value),
                4
            )
            
            # Check if data is stale (from previous quarter)
            last_updated = self.progress_tracker.get_last_updated(ticker)
            is_stale = self.quarterly_manager.is_data_stale(last_updated, current_quarter)
            
            item = QueueItem(
                ticker=ticker,
                market_cap_tier=tier,
                api_calls_needed=api_calls,
                priority=priority,
                last_updated=last_updated,
                is_stale=is_stale
            )
            
            items.append(item)
        
        # Sort by priority (1=highest) and then by staleness
        items.sort(key=lambda x: (x.priority, x.is_stale, x.ticker))
        
        return items
    
    def generate_daily_queue(self, all_tickers: List[str]) -> DailyQueue:
        """
        Generate today's processing queue based on API budget and priorities.
        
        Args:
            all_tickers: Complete list of tickers for the index
            
        Returns:
            DailyQueue with prioritized items for today
        """
        # Get all queue items with classification
        all_items = self.generate_queue_items(all_tickers)
        
        # Filter out already completed or fresh items
        remaining_items = [
            item for item in all_items 
            if not self.progress_tracker.is_completed(item.ticker) or item.is_stale
        ]
        
        # Generate today's queue within API budget
        daily_items = []
        calls_used = 0
        
        for item in remaining_items:
            # Check if we have API budget for this item
            if calls_used + item.api_calls_needed <= self.max_daily_calls:
                daily_items.append(item)
                calls_used += item.api_calls_needed
            else:
                # If we can't afford this item, skip to next priority level
                continue
        
        # Estimate completion time (rough estimate: 2 minutes per API call)
        estimated_time = timedelta(minutes=calls_used * 2)
        
        queue = DailyQueue(
            items=daily_items,
            total_api_calls=calls_used,
            estimated_completion_time=estimated_time,
            session_date=self.current_session
        )
        
        logger.info(f"Generated daily queue: {len(daily_items)} stocks, {calls_used} API calls")
        logger.info(f"Estimated completion time: {estimated_time}")
        
        return queue
    
    def save_daily_queue(self, queue: DailyQueue) -> None:
        """Save today's queue to file for reference"""
        queue_file = self.data_dir / f"daily_queue_{self.current_session.strftime('%Y%m%d')}.json"
        
        queue_data = {
            'session_date': queue.session_date.isoformat(),
            'total_api_calls': queue.total_api_calls,
            'estimated_completion_minutes': queue.estimated_completion_time.total_seconds() / 60,
            'items': [
                {
                    'ticker': item.ticker,
                    'tier': item.market_cap_tier.value,
                    'api_calls_needed': item.api_calls_needed,
                    'priority': item.priority,
                    'is_stale': item.is_stale
                }
                for item in queue.items
            ]
        }
        
        with open(queue_file, 'w') as f:
            json.dump(queue_data, f, indent=2)
        
        logger.info(f"Daily queue saved to {queue_file}")
    
    def calculate_eta(self, remaining_tickers: List[str]) -> Dict[str, int]:
        """
        Calculate ETA for completing remaining stocks.
        
        Args:
            remaining_tickers: List of remaining tickers to process
            
        Returns:
            Dictionary with ETA estimates in days
        """
        remaining_items = self.generate_queue_items(remaining_tickers)
        
        # Group by market cap tier
        tier_counts = {}
        for item in remaining_items:
            tier = item.market_cap_tier.value
            if tier not in tier_counts:
                tier_counts[tier] = {'count': 0, 'api_calls': 0}
            tier_counts[tier]['count'] += 1
            tier_counts[tier]['api_calls'] += item.api_calls_needed
        
        # Calculate days needed per tier
        eta_days = {}
        for allocation in self.DAILY_ALLOCATIONS:
            tier = allocation.tier
            if tier in tier_counts:
                daily_capacity = allocation.daily_budget // allocation.api_calls_per_stock if allocation.api_calls_per_stock > 0 else allocation.max_stocks_per_day
                days_needed = (tier_counts[tier]['count'] + daily_capacity - 1) // daily_capacity
                eta_days[tier] = days_needed
        
        # Total ETA is the maximum (since we process tiers sequentially)
        total_days = max(eta_days.values()) if eta_days else 0
        eta_days['total'] = total_days
        
        return eta_days
    
    def run_session(self, all_tickers: List[str]) -> None:
        """
        Run a single multi-day session.
        
        Args:
            all_tickers: Complete list of tickers for the index
        """
        # Cache all tickers for later use
        self._all_tickers_cache = all_tickers
        
        logger.info(f"Starting multi-day session for {self.index_name}")
        logger.info(f"Total tickers: {len(all_tickers)}")
        
        # Load previous progress
        completed_tickers = self.progress_tracker.get_completed_tickers()
        remaining_count = len(all_tickers) - len(completed_tickers)
        
        logger.info(f"Previously completed: {len(completed_tickers)}")
        logger.info(f"Remaining: {remaining_count}")
        
        # Calculate ETA for remaining work
        remaining_tickers = [t for t in all_tickers if t not in completed_tickers]
        eta = self.calculate_eta(remaining_tickers)
        
        logger.info(f"ETA: {eta['total']} days remaining")
        for tier, days in eta.items():
            if tier != 'total':
                logger.info(f"  {tier}: {days} days")
        
        # Generate today's processing queue
        daily_queue = self.generate_daily_queue(all_tickers)
        
        if not daily_queue.items:
            logger.info("No stocks to process today - all caught up!")
            return
        
        # Save today's queue
        self.save_daily_queue(daily_queue)
        
        # Update progress for today's session
        self.progress_tracker.save_session_start(daily_queue)
        
        logger.info(f"Daily session ready: {len(daily_queue.items)} stocks to process")
        logger.info(f"Total API calls needed: {daily_queue.total_api_calls}")
        
        # Return queue items for processing by the quality analysis system
        return daily_queue
    
    def get_processing_summary(self) -> Dict:
        """Get summary of current processing state"""
        completed = self.progress_tracker.get_completed_tickers()
        all_tickers_list = self._all_tickers_cache if hasattr(self, '_all_tickers_cache') and self._all_tickers_cache else []
        eta = self.calculate_eta(self.progress_tracker.get_remaining_tickers(all_tickers_list))
        
        return {
            'index': self.index_name,
            'session_date': self.current_session.strftime('%Y-%m-%d'),
            'total_completed': len(completed),
            'eta_days': eta,
            'api_calls_today': self.progress_tracker.get_session_calls_used(),
            'api_calls_remaining': self.max_daily_calls - self.progress_tracker.get_session_calls_used()
        }