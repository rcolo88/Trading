"""
Base Agent Class
Provides common functionality for all HuggingFace agents
"""

import requests
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hf_config import HFConfig, ModelConfig


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
    """Base class for all financial analysis agents"""

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

    def _make_api_call(self, payload: dict) -> Dict[str, Any]:
        """
        Make API call to HuggingFace with retry logic

        Args:
            payload: Request payload

        Returns:
            API response as dictionary

        Raises:
            Exception: If all retries fail
        """
        for attempt in range(self.config.RETRY.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    self.logger.warning(f"Model loading, attempt {attempt + 1}/{self.config.RETRY.max_retries}")
                    if attempt < self.config.RETRY.max_retries - 1:
                        delay = self.config.RETRY.get_delay(attempt)
                        self.logger.info(f"Waiting {delay:.1f}s before retry...")
                        time.sleep(delay)
                        continue

                else:
                    response.raise_for_status()

            except requests.exceptions.RequestException as e:
                self.logger.error(f"API call failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.RETRY.max_retries - 1:
                    delay = self.config.RETRY.get_delay(attempt)
                    self.logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    raise

        raise Exception(f"Failed to get response after {self.config.RETRY.max_retries} attempts")

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
