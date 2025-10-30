"""
HuggingFace Financial Agent System
Provides sentiment analysis and trading signal generation using HuggingFace models
"""

from .base_agent import BaseAgent, AgentResult
from .news_agent import NewsAgent, NewsAnalysis
from .market_agent import MarketAgent, MarketAnalysis
from .risk_agent import RiskAgent, RiskAnalysis
from .tone_agent import ToneAgent
from .trade_agent import TradeAgent, TradeDecision

__all__ = [
    "BaseAgent",
    "AgentResult",
    "NewsAgent",
    "NewsAnalysis",
    "MarketAgent",
    "MarketAnalysis",
    "RiskAgent",
    "RiskAnalysis",
    "ToneAgent",
    "TradeAgent",
    "TradeDecision"
]
