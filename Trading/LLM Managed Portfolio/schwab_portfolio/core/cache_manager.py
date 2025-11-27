"""
Unified Cache Manager for Financial Data

Provides consistent caching across all modules with pluggable backends (pickle/JSON),
configurable TTL, and automatic expiration.
"""

import pickle
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, Union

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with metadata and expiration tracking"""

    def __init__(self, key: str, value: Any, ttl_hours: int):
        self.key = key
        self.value = value
        self.timestamp = datetime.now()
        self.ttl_hours = ttl_hours

    def is_expired(self) -> bool:
        """Check if cache entry has exceeded TTL"""
        age = datetime.now() - self.timestamp
        return age > timedelta(hours=self.ttl_hours)

    def to_dict(self) -> Dict:
        """Serialize for JSON storage"""
        return {
            'key': self.key,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'ttl_hours': self.ttl_hours
        }


class CacheManager:
    """
    Unified cache manager with pluggable backends

    Supports:
    - Pickle-based caching (binary, fast)
    - JSON-based caching (text, readable)
    - Configurable TTL per cache type
    - Automatic expiration

    Example:
        cache = CacheManager('data_cache.pkl', ttl_hours=48)
        cache.set('AAPL', financial_data)
        data = cache.get('AAPL')  # Returns data if fresh, None if expired
    """

    def __init__(
        self,
        cache_file: Union[str, Path],
        ttl_hours: int = 24,
        cache_format: str = 'pickle'
    ):
        """
        Initialize cache manager

        Args:
            cache_file: Path to cache file
            ttl_hours: Time-to-live in hours (default 24)
            cache_format: 'pickle' or 'json' (default 'pickle')
        """
        self.cache_file = Path(cache_file)
        self.ttl_hours = ttl_hours
        self.cache_format = cache_format
        self.cache: Dict[str, CacheEntry] = {}
        self._load()

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if exists and not expired

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        if key in self.cache:
            entry = self.cache[key]
            if not entry.is_expired():
                logger.debug(f"Cache HIT: {key}")
                return entry.value
            else:
                logger.debug(f"Cache EXPIRED: {key}")
                del self.cache[key]
        logger.debug(f"Cache MISS: {key}")
        return None

    def set(self, key: str, value: Any, ttl_hours: Optional[int] = None) -> None:
        """
        Set value in cache with optional custom TTL

        Args:
            key: Cache key
            value: Value to cache
            ttl_hours: Optional custom TTL (uses default if not specified)
        """
        ttl = ttl_hours if ttl_hours is not None else self.ttl_hours
        self.cache[key] = CacheEntry(key=key, value=value, ttl_hours=ttl)
        self._save()
        logger.debug(f"Cache SET: {key} (TTL: {ttl}h)")

    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache = {}
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info(f"Cache cleared: {self.cache_file}")

    def invalidate(self, key: str) -> None:
        """Invalidate specific cache entry"""
        if key in self.cache:
            del self.cache[key]
            self._save()
            logger.debug(f"Cache invalidated: {key}")

    def _load(self) -> None:
        """Load cache from disk"""
        if not self.cache_file.exists():
            return

        try:
            if self.cache_format == 'pickle':
                with open(self.cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
            else:  # json
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.cache = {
                        k: CacheEntry(
                            key=v['key'],
                            value=v['value'],
                            ttl_hours=v['ttl_hours']
                        )
                        for k, v in data.items()
                    }
                    # Restore original timestamps
                    for k, v in data.items():
                        self.cache[k].timestamp = datetime.fromisoformat(v['timestamp'])

            logger.debug(f"Loaded cache: {len(self.cache)} entries from {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to load cache from {self.cache_file}: {e}")
            self.cache = {}

    def _save(self) -> None:
        """Save cache to disk"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

            if self.cache_format == 'pickle':
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.cache, f)
            else:  # json
                with open(self.cache_file, 'w') as f:
                    data = {k: v.to_dict() for k, v in self.cache.items()}
                    json.dump(data, f, indent=2)

            logger.debug(f"Saved cache: {len(self.cache)} entries to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")


# Pre-configured cache instances for common use cases

def get_financial_cache() -> CacheManager:
    """Get cache for financial data (48h TTL)"""
    return CacheManager('outputs/cache/financial_cache.pkl', ttl_hours=48)


def get_market_cache() -> CacheManager:
    """Get cache for market data (4h TTL)"""
    return CacheManager('outputs/cache/market_cache.pkl', ttl_hours=4)


def get_news_cache() -> CacheManager:
    """Get cache for news data (12h TTL)"""
    return CacheManager('outputs/cache/news_cache.pkl', ttl_hours=12)
