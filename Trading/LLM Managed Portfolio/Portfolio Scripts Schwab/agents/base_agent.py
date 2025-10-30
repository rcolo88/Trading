"""
Base Agent Class
Provides common functionality for all HuggingFace agents with advanced retry logic and caching
"""

import requests
import time
import logging
import hashlib
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hf_config import HFConfig, ModelConfig


class SimpleCache:
    """Simple in-memory cache with TTL support"""

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache

        Args:
            ttl_seconds: Time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: OrderedDict[str, Tuple[Any, datetime]] = OrderedDict()
        self.ttl_seconds = ttl_seconds
        self.max_size = 100  # Limit cache size
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]

        # Check if expired
        if datetime.now() - timestamp > timedelta(seconds=self.ttl_seconds):
            self.logger.debug(f"Cache expired for key: {key[:20]}...")
            del self._cache[key]
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        self.logger.debug(f"Cache hit for key: {key[:20]}...")
        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set value in cache with current timestamp

        Args:
            key: Cache key
            value: Value to cache
        """
        # Remove oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self.logger.debug(f"Cache full, removed oldest entry")

        self._cache[key] = (value, datetime.now())
        self.logger.debug(f"Cache set for key: {key[:20]}...")

    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self.logger.info("Cache cleared")

    def size(self) -> int:
        """Get current cache size"""
        return len(self._cache)


@dataclass
class AgentResult:
    """Result from an agent analysis"""
    agent_name: str
    sentiment: str  # positive, negative, neutral
    confidence: float  # 0.0 to 1.0
    score: float  # raw score from model
    label: str  # label from model
    reasoning: str
    timestamp: datetime
    model_used: str
    raw_response: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "agent_name": self.agent_name,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "score": self.score,
            "label": self.label,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
            "model_used": self.model_used,
            "raw_response": self.raw_response
        }


class BaseAgent(ABC):
    """Base class for all financial analysis agents with caching and smart retry logic"""

    # Shared cache across all agents
    _cache = SimpleCache(ttl_seconds=300)  # 5-minute TTL

    def __init__(self, model_key: str, config: HFConfig = HFConfig):
        """
        Initialize the agent

        Args:
            model_key: Key to lookup model in config (e.g., 'news', 'risk')
            config: Configuration object
        """
        self.config = config
        self.model_key = model_key
        self.model_config: ModelConfig = config.MODELS[model_key]
        self.api_url = config.get_model_url(model_key)
        self.headers = config.get_headers()
        self.logger = logging.getLogger(f"{self.__class__.__name__}")

    def _generate_cache_key(self, text: str) -> str:
        """
        Generate cache key from model and text

        Args:
            text: Input text

        Returns:
            Cache key (hash of model + text)
        """
        content = f"{self.model_config.model_id}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _parse_classification_response(self, response: Any) -> Optional[Dict[str, Any]]:
        """
        Parse HuggingFace classification response

        Handles format: [{"label": "positive", "score": 0.95}] or
                        [[{"label": "positive", "score": 0.95}]]

        Args:
            response: Raw API response

        Returns:
            Dict with 'label' and 'score' or None on error
        """
        try:
            # Handle nested list format
            if isinstance(response, list) and len(response) > 0:
                top_result = response[0]

                # If nested, unwrap
                if isinstance(top_result, list) and len(top_result) > 0:
                    top_result = top_result[0]

                # Validate structure
                if isinstance(top_result, dict) and "label" in top_result and "score" in top_result:
                    self.logger.debug(f"Parsed classification: {top_result['label']} ({top_result['score']:.3f})")
                    return top_result

            self.logger.warning(f"Unexpected response format: {type(response)}")
            return None

        except (IndexError, KeyError, TypeError) as e:
            self.logger.error(f"Error parsing classification response: {e}")
            return None

    def _make_api_call(self, payload: dict, bypass_cache: bool = False) -> Optional[Dict[str, Any]]:
        """
        Make API call to HuggingFace with smart retry logic and caching

        Args:
            payload: Request payload
            bypass_cache: If True, skip cache lookup and update

        Returns:
            API response as dictionary or None on error (never raises)
        """
        # Generate cache key
        cache_key = self._generate_cache_key(payload.get("inputs", ""))

        # Check cache first (unless bypassed)
        if not bypass_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self.logger.info(f"Using cached result for {self.model_config.name}")
                return cached_result

        # Attempt API call with retries
        for attempt in range(self.config.RETRY.max_retries):
            try:
                self.logger.debug(f"API call attempt {attempt + 1}/{self.config.RETRY.max_retries}")

                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )

                # Success
                if response.status_code == 200:
                    result = response.json()
                    # Cache successful result
                    if not bypass_cache:
                        self._cache.set(cache_key, result)
                    self.logger.info(f"API call successful for {self.model_config.name}")
                    return result

                # Model loading - wait 20-30 seconds
                elif response.status_code == 503:
                    if attempt < self.config.RETRY.max_retries - 1:
                        # Random wait between 20-30 seconds for 503
                        wait_time = random.uniform(20, 30)
                        self.logger.warning(
                            f"Model loading (503), waiting {wait_time:.1f}s "
                            f"(attempt {attempt + 1}/{self.config.RETRY.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Model still loading after {self.config.RETRY.max_retries} attempts")
                        return None

                # Rate limit - respect Retry-After header
                elif response.status_code == 429:
                    if attempt < self.config.RETRY.max_retries - 1:
                        # Check for Retry-After header
                        retry_after = response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                wait_time = int(retry_after)
                            except ValueError:
                                wait_time = 60  # Default if header is malformed
                        else:
                            wait_time = 60  # Default if no header

                        self.logger.warning(
                            f"Rate limited (429), waiting {wait_time}s "
                            f"(attempt {attempt + 1}/{self.config.RETRY.max_retries})"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Rate limit exceeded after {self.config.RETRY.max_retries} attempts")
                        return None

                # Other HTTP errors
                else:
                    self.logger.error(
                        f"HTTP {response.status_code} error: {response.text[:200]}"
                    )
                    return None

            except requests.exceptions.Timeout:
                self.logger.error(f"Request timeout (attempt {attempt + 1})")
                if attempt < self.config.RETRY.max_retries - 1:
                    delay = self.config.RETRY.get_delay(attempt)
                    self.logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached due to timeout")
                    return None

            except requests.exceptions.ConnectionError as e:
                self.logger.error(f"Connection error (attempt {attempt + 1}): {e}")
                if attempt < self.config.RETRY.max_retries - 1:
                    delay = self.config.RETRY.get_delay(attempt)
                    self.logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached due to connection errors")
                    return None

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt + 1}): {e}")
                if attempt < self.config.RETRY.max_retries - 1:
                    delay = self.config.RETRY.get_delay(attempt)
                    self.logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached due to request errors")
                    return None

            except Exception as e:
                self.logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                return None

        self.logger.error(f"Failed to get response after {self.config.RETRY.max_retries} attempts")
        return None

    def _normalize_sentiment(self, label: str, score: float) -> tuple[str, float]:
        """
        Normalize different model outputs to standard sentiment format

        Args:
            label: Model's label output
            score: Model's confidence score

        Returns:
            Tuple of (sentiment, confidence)
        """
        label_lower = label.lower()

        # Map various labels to standard sentiments
        if any(word in label_lower for word in ['positive', 'bullish', 'buy']):
            sentiment = 'positive'
        elif any(word in label_lower for word in ['negative', 'bearish', 'sell']):
            sentiment = 'negative'
        else:
            sentiment = 'neutral'

        # Ensure confidence is between 0 and 1
        confidence = max(0.0, min(1.0, score))

        return sentiment, confidence

    @abstractmethod
    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze text and return sentiment

        Args:
            text: Text to analyze
            context: Optional context (portfolio data, market data, etc.)

        Returns:
            AgentResult with analysis
        """
        pass

    @abstractmethod
    def _interpret_results(self, response: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret model response and create AgentResult

        Args:
            response: Raw API response
            text: Original input text
            context: Optional context

        Returns:
            AgentResult with interpretation
        """
        pass

    def get_model_info(self) -> dict:
        """Get information about this agent's model"""
        return {
            "agent_name": self.__class__.__name__,
            "model_name": self.model_config.name,
            "model_id": self.model_config.model_id,
            "task": self.model_config.task,
            "model_key": self.model_key
        }

    @classmethod
    def get_cache_stats(cls) -> dict:
        """
        Get cache statistics

        Returns:
            Dict with cache size and TTL info
        """
        return {
            "cache_size": cls._cache.size(),
            "max_size": cls._cache.max_size,
            "ttl_seconds": cls._cache.ttl_seconds
        }

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the shared cache"""
        cls._cache.clear()
