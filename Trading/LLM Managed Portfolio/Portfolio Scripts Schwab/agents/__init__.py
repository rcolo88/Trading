"""
HuggingFace Financial Agent System
Provides sentiment analysis and trading signal generation using HuggingFace models
"""

from .base_agent import BaseAgent, AgentResult
from .news_agent import NewsAgent
from .market_agent import MarketAgent
from .risk_agent import RiskAgent
from .tone_agent import ToneAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "NewsAgent",
    "MarketAgent",
    "RiskAgent",
    "ToneAgent"
]
