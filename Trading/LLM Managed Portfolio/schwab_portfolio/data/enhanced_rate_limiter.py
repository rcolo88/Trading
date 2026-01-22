"""
Enhanced Rate Limiter for Multi-Tier API Management

Handles daily, hourly, and burst rate limiting for FMP API with
intelligent throttling and adaptive backoff.

Author: API Rate Limiting System
Date: January 2026
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum
import logging

from .fmp_config import get_api_tier_config

logger = logging.getLogger(__name__)


class RateLimitStatus(Enum):
    """Rate limiting status codes"""
    ALLOWED = "allowed"
    DAILY_LIMITED = "daily_limit_exceeded"
    HOURLY_LIMITED = "hourly_limit_exceeded"
    BURST_LIMITED = "burst_limit_exceeded"
    RATE_LIMITED = "rate_limited"


@dataclass
class RateLimitResult:
    """Result of rate limit check"""
    status: RateLimitStatus
    message: str
    retry_after: Optional[float] = None  # Seconds to wait
    available_calls: Optional[Dict[str, int]] = None


class EnhancedRateLimiter:
    """
    Enhanced rate limiting with multiple constraint types.
    
    Features:
    - Daily, hourly, and burst rate limiting
    - Thread-safe operations
    - Automatic resets
    - Adaptive backoff
    - Usage tracking
    """
    
    def __init__(self, api_tier: str = 'FREE'):
        """
        Initialize enhanced rate limiter.
        
        Args:
            api_tier: API tier name (FREE, PREMIUM, ENTERPRISE)
        """
        # Load tier configuration
        self.config = get_api_tier_config(api_tier)
        self.api_tier = api_tier
        
        # Rate limits
        self.daily_limit = self.config['daily_limit']
        self.hourly_limit = self.config['hourly_limit'] 
        self.burst_limit = self.config['burst_limit']
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Usage tracking
        self._daily_calls = 0
        self._hourly_calls = 0
        self._burst_calls = 0
        self._last_daily_reset = datetime.now()
        self._last_hourly_reset = datetime.now()
        self._last_burst_reset = datetime.now()
        
        # Burst window (1 minute)
        self._burst_window_seconds = 60
        
        # Call history for backoff calculation
        self._recent_calls = []
        
        logger.info(
            f"EnhancedRateLimiter initialized: "
            f"{self.daily_limit}/day, {self.hourly_limit}/hour, {self.burst_limit}/burst ({api_tier})"
        )
    
    def can_make_calls(self, calls_needed: int) -> RateLimitResult:
        """
        Check if calls can be made across all limit types.
        
        Args:
            calls_needed: Number of API calls needed
            
        Returns:
            RateLimitResult with status and guidance
        """
        with self._lock:
            self._reset_counters_if_needed()
            
            # Check all limits
            checks = [
                self._check_daily_limit(calls_needed),
                self._check_hourly_limit(calls_needed),
                self._check_burst_limit(calls_needed)
            ]
            
            # Find most restrictive limit
            restrictive_check = max(checks, key=lambda x: x[1])  # (status, priority)
            
            status, message, retry_after = restrictive_check[0], restrictive_check[2], restrictive_check[3]
            
            if status == RateLimitStatus.ALLOWED:
                self._record_calls(calls_needed)
                
                return RateLimitResult(
                    status=status,
                    message=message,
                    available_calls=self._get_available_counts()
                )
            else:
                logger.warning(f"Rate limited: {message}")
                
                return RateLimitResult(
                    status=status,
                    message=message,
                    retry_after=retry_after,
                    available_calls=self._get_available_counts()
                )
    
    def _check_daily_limit(self, calls_needed: int) -> Tuple[RateLimitStatus, int, str, Optional[float]]:
        """
        Check daily rate limit.
        
        Args:
            calls_needed: Number of calls needed
            
        Returns:
            Tuple of (status, priority, message, retry_after)
        """
        if self._daily_calls + calls_needed <= self.daily_limit:
            return RateLimitStatus.ALLOWED, 0, "Daily limit OK", None
        else:
            # Calculate when daily limit resets
            now = datetime.now()
            reset_time = datetime(now.year, now.month, now.day + 1, 0, 0, 0)
            retry_after = (reset_time - now).total_seconds()
            
            return RateLimitStatus.DAILY_LIMITED, 3, \
                   f"Daily limit exceeded ({self._daily_calls}/{self.daily_limit})", retry_after
    
    def _check_hourly_limit(self, calls_needed: int) -> Tuple[RateLimitStatus, int, str, Optional[float]]:
        """
        Check hourly rate limit.
        
        Args:
            calls_needed: Number of calls needed
            
        Returns:
            Tuple of (status, priority, message, retry_after)
        """
        if self._hourly_calls + calls_needed <= self.hourly_limit:
            return RateLimitStatus.ALLOWED, 0, "Hourly limit OK", None
        else:
            # Calculate when hourly limit resets
            now = datetime.now()
            reset_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            retry_after = (reset_time - now).total_seconds()
            
            return RateLimitStatus.HOURLY_LIMITED, 2, \
                   f"Hourly limit exceeded ({self._hourly_calls}/{self.hourly_limit})", retry_after
    
    def _check_burst_limit(self, calls_needed: int) -> Tuple[RateLimitStatus, int, str, Optional[float]]:
        """
        Check burst rate limit (within 1 minute window).
        
        Args:
            calls_needed: Number of calls needed
            
        Returns:
            Tuple of (status, priority, message, retry_after)
        """
        if self._burst_calls + calls_needed <= self.burst_limit:
            return RateLimitStatus.ALLOWED, 0, "Burst limit OK", None
        else:
            # Calculate when burst window resets
            now = datetime.now()
            reset_time = self._last_burst_reset + timedelta(seconds=self._burst_window_seconds)
            retry_after = (reset_time - now).total_seconds()
            
            return RateLimitStatus.BURST_LIMITED, 1, \
                   f"Burst limit exceeded ({self._burst_calls}/{self.burst_limit})", retry_after
    
    def _reset_counters_if_needed(self):
        """Reset counters if time windows have passed."""
        now = datetime.now()
        
        # Daily reset
        if now.date() > self._last_daily_reset.date():
            logger.debug(f"Daily reset: {self._daily_calls} -> 0")
            self._daily_calls = 0
            self._last_daily_reset = now
        
        # Hourly reset
        if now >= self._last_hourly_reset + timedelta(hours=1):
            logger.debug(f"Hourly reset: {self._hourly_calls} -> 0")
            self._hourly_calls = 0
            self._last_hourly_reset = now
        
        # Burst reset
        if now >= self._last_burst_reset + timedelta(seconds=self._burst_window_seconds):
            logger.debug(f"Burst reset: {self._burst_calls} -> 0")
            self._burst_calls = 0
            self._last_burst_reset = now
    
    def _record_calls(self, calls_needed: int):
        """
        Record API calls for rate limiting.
        
        Args:
            calls_needed: Number of calls made
        """
        self._daily_calls += calls_needed
        self._hourly_calls += calls_needed
        self._burst_calls += calls_needed
        
        # Record call timestamp for backoff calculation
        self._recent_calls.append({
            'timestamp': datetime.now(),
            'calls': calls_needed
        })
        
        # Keep only recent history (last 100 calls)
        if len(self._recent_calls) > 100:
            self._recent_calls = self._recent_calls[-100:]
        
        logger.debug(f"Recorded {calls_needed} calls: daily={self._daily_calls}, "
                    f"hourly={self._hourly_calls}, burst={self._burst_calls}")
    
    def _get_available_counts(self) -> Dict[str, int]:
        """
        Get available calls for each limit type.
        
        Returns:
            Dict with available calls by type
        """
        return {
            'daily': max(0, self.daily_limit - self._daily_calls),
            'hourly': max(0, self.hourly_limit - self._hourly_calls),
            'burst': max(0, self.burst_limit - self._burst_calls)
        }
    
    def wait_if_needed(self, calls_needed: int) -> bool:
        """
        Wait if rate limits would be exceeded.
        
        Args:
            calls_needed: Number of calls needed
            
        Returns:
            True if had to wait, False if allowed immediately
        """
        result = self.can_make_calls(calls_needed)
        
        if result.status != RateLimitStatus.ALLOWED:
            if result.retry_after:
                logger.info(f"Rate limited, waiting {result.retry_after:.1f} seconds...")
                time.sleep(result.retry_after)
                return True
            else:
                # Immediate retry possible (short delay)
                time.sleep(1)
                return True
        
        return False
    
    def get_usage_stats(self) -> Dict:
        """
        Get current usage statistics.
        
        Returns:
            Dict with usage metrics
        """
        with self._lock:
            self._reset_counters_if_needed()
            
            return {
                'api_tier': self.api_tier,
                'daily': {
                    'used': self._daily_calls,
                    'limit': self.daily_limit,
                    'remaining': max(0, self.daily_limit - self._daily_calls),
                    'utilization': self._daily_calls / self.daily_limit if self.daily_limit > 0 else 0
                },
                'hourly': {
                    'used': self._hourly_calls,
                    'limit': self.hourly_limit,
                    'remaining': max(0, self.hourly_limit - self._hourly_calls),
                    'utilization': self._hourly_calls / self.hourly_limit if self.hourly_limit > 0 else 0
                },
                'burst': {
                    'used': self._burst_calls,
                    'limit': self.burst_limit,
                    'remaining': max(0, self.burst_limit - self._burst_calls),
                    'utilization': self._burst_calls / self.burst_limit if self.burst_limit > 0 else 0
                },
                'last_resets': {
                    'daily': self._last_daily_reset.isoformat(),
                    'hourly': self._last_hourly_reset.isoformat(),
                    'burst': self._last_burst_reset.isoformat()
                }
            }
    
    def get_optimal_call_timing(self) -> Dict:
        """
        Analyze usage patterns to suggest optimal call timing.
        
        Returns:
            Dict with timing recommendations
        """
        with self._lock:
            if len(self._recent_calls) < 10:
                return {'message': 'Insufficient data for timing analysis'}
            
            # Analyze recent call patterns
            recent_hourly = {}
            for call in self._recent_calls[-50:]:  # Last 50 calls
                hour = call['timestamp'].hour
                if hour not in recent_hourly:
                    recent_hourly[hour] = {'calls': 0, 'delays': 0}
                recent_hourly[hour]['calls'] += 1
            
            # Find best hours (lowest utilization)
            best_hours = sorted(recent_hourly.items(), 
                            key=lambda x: x[1]['calls'], 
                            reverse=False)[:3]
            
            # Current utilization
            current_hour = datetime.now().hour
            current_util = self._hourly_calls / self.hourly_limit if self.hourly_limit > 0 else 0
            
            return {
                'current_hour': current_hour,
                'current_utilization': current_util,
                'best_hours': best_hours,
                'recommendation': (
                    f"Consider calling during hours: "
                    f"{[h for h, _ in best_hours]} for lower latency"
                ) if best_hours else "No clear pattern detected"
            }
    
    def reset_all_limits(self):
        """Reset all rate limit counters (for testing)."""
        with self._lock:
            now = datetime.now()
            self._daily_calls = 0
            self._hourly_calls = 0
            self._burst_calls = 0
            self._last_daily_reset = now
            self._last_hourly_reset = now
            self._last_burst_reset = now
            self._recent_calls = []
            
            logger.info("All rate limits reset")


class RateLimiterManager:
    """
    Manages multiple rate limiters for different API tiers.
    
    Useful for systems that need to manage multiple API keys or tiers.
    """
    
    def __init__(self):
        """Initialize rate limiter manager."""
        self.limiters: Dict[str, EnhancedRateLimiter] = {}
    
    def get_limiter(self, api_tier: str) -> EnhancedRateLimiter:
        """
        Get or create rate limiter for specified tier.
        
        Args:
            api_tier: API tier name
            
        Returns:
            EnhancedRateLimiter instance
        """
        if api_tier not in self.limiters:
            self.limiters[api_tier] = EnhancedRateLimiter(api_tier)
        
        return self.limiters[api_tier]
    
    def get_all_stats(self) -> Dict:
        """
        Get statistics for all managed limiters.
        
        Returns:
            Dict with all limiter stats
        """
        return {tier: limiter.get_usage_stats() 
                for tier, limiter in self.limiters.items()}