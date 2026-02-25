"""
Ticker Mapping Cache

Provides caching for ticker symbol mappings to avoid repeated lookups
and improve performance when processing large lists of tickers.

Features:
- File-based persistence (JSON format)
- TTL-based expiration (default 7 days)
- Thread-safe operations
- Automatic cleanup of expired entries

Usage:
    from .ticker_cache import TickerMappingCache

    cache = TickerMappingCache()
    cached = cache.get('FISV', 'simfin')
    if cached:
        print(f"Found cached mapping: FISV -> {cached}")
    else:
        # Perform lookup and cache result
        cache.set('FISV', 'simfin', 'FI')
"""

import json
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TickerMappingCache:
    """
    Thread-safe cache for ticker symbol mappings.

    Caches mappings between standard tickers and API-specific tickers
    to avoid repeated lookups and improve performance.

    Attributes:
        cache_file: Path to JSON cache file
        ttl_days: Time-to-live for cache entries in days
        _lock: Thread lock for thread-safe operations
        _cache: In-memory cache dictionary
    """

    def __init__(
        self,
        cache_file: str = "ticker_mapping_cache.json",
        ttl_days: int = 7
    ):
        """
        Initialize ticker mapping cache.

        Args:
            cache_file: Path to JSON cache file (default: ticker_mapping_cache.json)
            ttl_days: Time-to-live for cache entries in days (default: 7)
        """
        self.cache_file = cache_file
        self.ttl_days = ttl_days
        self._lock = threading.RLock()
        self._cache: Dict[str, dict] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from JSON file if it exists."""
        if not os.path.exists(self.cache_file):
            logger.debug(f"Ticker cache file not found: {self.cache_file}")
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate cache structure
            if not isinstance(data, dict):
                logger.warning(f"Invalid ticker cache format: expected dict")
                return

            # Load and validate entries
            now = datetime.now()
            loaded_count = 0
            expired_count = 0

            for key, value in data.items():
                if not isinstance(value, dict):
                    continue

                # Check TTL
                timestamp = value.get('timestamp')
                if timestamp:
                    try:
                        entry_time = datetime.fromisoformat(timestamp)
                        if now - entry_time > timedelta(days=self.ttl_days):
                            expired_count += 1
                            continue
                    except ValueError:
                        continue

                self._cache[key] = value
                loaded_count += 1

            logger.info(
                f"Loaded ticker cache: {loaded_count} entries, "
                f"{expired_count} expired entries discarded"
            )

        except Exception as e:
            logger.warning(f"Failed to load ticker cache: {e}")

    def _save_cache(self) -> None:
        """Save cache to JSON file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, default=str)
            logger.debug(f"Saved ticker cache: {len(self._cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save ticker cache: {e}")

    def _make_key(self, ticker: str, api_source: str) -> str:
        """Create cache key from ticker and API source."""
        return f"{api_source.lower()}:{ticker.upper()}"

    def get(self, ticker: str, api_source: str) -> Optional[str]:
        """
        Get cached API ticker for a standard ticker.

        Args:
            ticker: Standard ticker symbol (e.g., 'FISV')
            api_source: API source (e.g., 'simfin')

        Returns:
            Cached API-specific ticker (e.g., 'FI') or None if not cached/expired
        """
        with self._lock:
            key = self._make_key(ticker, api_source)

            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check TTL
            timestamp = entry.get('timestamp')
            if timestamp:
                try:
                    entry_time = datetime.fromisoformat(timestamp)
                    if datetime.now() - entry_time > timedelta(days=self.ttl_days):
                        del self._cache[key]
                        logger.debug(f"Ticker cache entry expired: {key}")
                        return None
                except ValueError:
                    return None

            return entry.get('mapped_ticker')

    def set(
        self,
        ticker: str,
        api_source: str,
        mapped_ticker: str,
        discovered: bool = False
    ) -> None:
        """
        Cache a ticker mapping.

        Args:
            ticker: Standard ticker symbol
            api_source: API source
            mapped_ticker: API-specific ticker
            discovered: Whether this was auto-discovered (for logging)
        """
        with self._lock:
            key = self._make_key(ticker, api_source)

            self._cache[key] = {
                'standard_ticker': ticker.upper(),
                'api_source': api_source.lower(),
                'mapped_ticker': mapped_ticker.upper(),
                'timestamp': datetime.now().isoformat(),
                'discovered': discovered
            }

            self._save_cache()

            if discovered:
                logger.info(
                    f"Discovered and cached ticker mapping: "
                    f"{ticker} -> {mapped_ticker} ({api_source})"
                )

    def delete(self, ticker: str, api_source: str) -> bool:
        """
        Delete a cached ticker mapping.

        Args:
            ticker: Standard ticker symbol
            api_source: API source

        Returns:
            True if entry was deleted, False if not found
        """
        with self._lock:
            key = self._make_key(ticker, api_source)

            if key in self._cache:
                del self._cache[key]
                self._save_cache()
                return True

            return False

    def clear(self) -> None:
        """Clear all cached ticker mappings."""
        with self._lock:
            self._cache.clear()
            self._save_cache()
            logger.info("Ticker mapping cache cleared")

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        with self._lock:
            total = len(self._cache)

            # Count discovered entries
            discovered = sum(
                1 for v in self._cache.values()
                if v.get('discovered', False)
            )

            # Count by API source
            by_source: Dict[str, int] = {}
            for v in self._cache.values():
                source = v.get('api_source', 'unknown')
                by_source[source] = by_source.get(source, 0) + 1

            return {
                'total_entries': total,
                'discovered_entries': discovered,
                'by_api_source': by_source,
                'ttl_days': self.ttl_days,
                'cache_file': self.cache_file
            }

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            now = datetime.now()
            expired_keys = []

            for key, entry in self._cache.items():
                timestamp = entry.get('timestamp')
                if timestamp:
                    try:
                        entry_time = datetime.fromisoformat(timestamp)
                        if now - entry_time > timedelta(days=self.ttl_days):
                            expired_keys.append(key)
                    except ValueError:
                        expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                self._save_cache()
                logger.info(f"Cleaned up {len(expired_keys)} expired ticker cache entries")

            return len(expired_keys)


def get_ticker_mapping_cache(
    cache_file: str = "ticker_mapping_cache.json",
    ttl_days: int = 7
) -> TickerMappingCache:
    """
    Factory function to get a TickerMappingCache instance.

    Args:
        cache_file: Path to cache file
        ttl_days: TTL in days

    Returns:
        TickerMappingCache instance
    """
    return TickerMappingCache(cache_file=cache_file, ttl_days=ttl_days)
