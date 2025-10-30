"""
HuggingFace Agent Trading System
Orchestrates multiple sentiment analysis agents to generate trading recommendations
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import json

from agents import NewsAgent, MarketAgent, RiskAgent, ToneAgent, AgentResult
from trading_models import TradeOrder, OrderType, OrderPriority
from hf_config import HFConfig


@dataclass
class ConsensusResult:
    """Aggregated result from all agents"""
    overall_sentiment: str  # positive, negative, neutral
    confidence: float  # weighted confidence score
    recommendation: str  # BUY, SELL, HOLD
    reasoning: str
    agent_results: List[AgentResult]
    timestamp: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "overall_sentiment": self.overall_sentiment,
            "confidence": self.confidence,
            "recommendation": self.recommendation,
            "reasoning": self.reasoning,
            "agent_results": [r.to_dict() for r in self.agent_results],
            "timestamp": self.timestamp.isoformat()
        }


class HFAgentSystem:
    """Main system that coordinates all HuggingFace agents"""

    def __init__(self, config: HFConfig = HFConfig):
        """
        Initialize the agent system

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize all agents
        self.logger.info("Initializing HuggingFace Agent System...")
        self.news_agent = NewsAgent()
        self.market_agent = MarketAgent()
        self.risk_agent = RiskAgent()
        self.tone_agent = ToneAgent()

        self.logger.info("All agents initialized successfully")

    def analyze_portfolio_data(self, portfolio_analysis: str, context: Optional[Dict[str, Any]] = None) -> ConsensusResult:
        """
        Analyze portfolio data using all agents

        Args:
            portfolio_analysis: Text from daily_portfolio_analysis.md
            context: Optional context (current holdings, cash, etc.)

        Returns:
            ConsensusResult with aggregated analysis
        """
        self.logger.info("Starting multi-agent portfolio analysis...")

        agent_results = []

        # Run all agents in parallel conceptually (sequentially in practice due to API)
        try:
            # News sentiment
            news_result = self.news_agent.analyze(portfolio_analysis, context)
            agent_results.append(news_result)

            # Market sentiment
            market_result = self.market_agent.analyze(portfolio_analysis, context)
            agent_results.append(market_result)

            # Risk analysis
            risk_result = self.risk_agent.analyze(portfolio_analysis, context)
            agent_results.append(risk_result)

            # Market tone
            tone_result = self.tone_agent.analyze(portfolio_analysis, context)
            agent_results.append(tone_result)

        except Exception as e:
            self.logger.error(f"Error during agent analysis: {e}")
            raise

        # Aggregate results
        consensus = self._build_consensus(agent_results, context)

        self.logger.info(f"Analysis complete. Recommendation: {consensus.recommendation} (confidence: {consensus.confidence:.1%})")

        return consensus

    def _build_consensus(self, agent_results: List[AgentResult], context: Optional[Dict[str, Any]]) -> ConsensusResult:
        """
        Build consensus from all agent results

        Args:
            agent_results: Results from all agents
            context: Optional context

        Returns:
            ConsensusResult with aggregated decision
        """
        # Weighted voting system
        weights = {
            "NewsAgent": 0.25,
            "MarketAgent": 0.30,
            "RiskAgent": 0.30,  # Higher weight for risk
            "ToneAgent": 0.15
        }

        sentiment_scores = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        total_weight = 0.0

        for result in agent_results:
            weight = weights.get(result.agent_name, 0.25)
            weighted_confidence = result.confidence * weight

            sentiment_scores[result.sentiment] += weighted_confidence
            total_weight += weight

        # Normalize scores
        if total_weight > 0:
            for sentiment in sentiment_scores:
                sentiment_scores[sentiment] /= total_weight

        # Determine overall sentiment
        overall_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        confidence = sentiment_scores[overall_sentiment]

        # Generate recommendation based on sentiment and confidence
        recommendation = self._generate_recommendation(
            overall_sentiment,
            confidence,
            agent_results,
            context
        )

        # Build reasoning
        reasoning = self._build_reasoning(
            overall_sentiment,
            confidence,
            recommendation,
            agent_results,
            context
        )

        return ConsensusResult(
            overall_sentiment=overall_sentiment,
            confidence=confidence,
            recommendation=recommendation,
            reasoning=reasoning,
            agent_results=agent_results,
            timestamp=datetime.now()
        )

    def _generate_recommendation(
        self,
        sentiment: str,
        confidence: float,
        agent_results: List[AgentResult],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Generate trading recommendation based on consensus

        Args:
            sentiment: Overall sentiment
            confidence: Confidence score
            agent_results: All agent results
            context: Optional context

        Returns:
            Recommendation string (BUY, SELL, HOLD)
        """
        # Check confidence threshold
        if confidence < self.config.TRADING.confidence_threshold:
            return "HOLD"

        # Risk override - if risk agent is very negative, be cautious
        risk_result = next((r for r in agent_results if r.agent_name == "RiskAgent"), None)
        if risk_result and risk_result.sentiment == "negative" and risk_result.confidence > 0.75:
            if sentiment == "positive":
                return "HOLD"  # Override positive sentiment with high risk
            else:
                return "SELL"  # Reinforce negative sentiment

        # Generate recommendation based on sentiment
        if sentiment == "positive" and confidence >= self.config.TRADING.confidence_threshold:
            return "BUY"
        elif sentiment == "negative" and confidence >= self.config.TRADING.confidence_threshold:
            return "SELL"
        else:
            return "HOLD"

    def _build_reasoning(
        self,
        sentiment: str,
        confidence: float,
        recommendation: str,
        agent_results: List[AgentResult],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build detailed reasoning for the recommendation"""
        reasoning = f"Multi-Agent Analysis Summary:\n\n"
        reasoning += f"Overall Sentiment: {sentiment.upper()} (Confidence: {confidence:.1%})\n"
        reasoning += f"Recommendation: {recommendation}\n\n"

        reasoning += "Agent Breakdowns:\n"
        for result in agent_results:
            reasoning += f"- {result.agent_name}: {result.sentiment} ({result.confidence:.1%})\n"
            reasoning += f"  {result.reasoning}\n\n"

        # Add consensus logic
        reasoning += "Consensus Logic:\n"
        if confidence < self.config.TRADING.confidence_threshold:
            reasoning += f"- Confidence {confidence:.1%} below threshold {self.config.TRADING.confidence_threshold:.1%}\n"
            reasoning += "- Insufficient consensus for action\n"

        if recommendation == "BUY":
            reasoning += "- Strong positive signals across multiple agents\n"
            reasoning += "- Risk profile acceptable for entry\n"
        elif recommendation == "SELL":
            reasoning += "- Negative signals or elevated risk detected\n"
            reasoning += "- Recommend reducing exposure\n"
        else:
            reasoning += "- Mixed signals or elevated uncertainty\n"
            reasoning += "- Maintain current positions\n"

        return reasoning

    def generate_trade_orders(
        self,
        consensus: ConsensusResult,
        current_holdings: Dict[str, Any],
        available_cash: float
    ) -> List[TradeOrder]:
        """
        Generate specific trade orders based on consensus

        Args:
            consensus: ConsensusResult from analysis
            current_holdings: Current portfolio holdings
            available_cash: Available cash for trading

        Returns:
            List of TradeOrder objects
        """
        orders = []

        if consensus.recommendation == "HOLD":
            self.logger.info("Recommendation is HOLD - no orders generated")
            return orders

        # This is a simplified example - in practice, you'd analyze individual tickers
        # from the portfolio analysis and generate specific orders

        # Example: Generate orders based on overall market sentiment
        # In real implementation, this would parse portfolio_analysis for specific tickers

        self.logger.info(f"Generated {len(orders)} trade orders")
        return orders

    def export_analysis(self, consensus: ConsensusResult, filepath: str):
        """
        Export analysis to file

        Args:
            consensus: ConsensusResult to export
            filepath: Path to save file
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(consensus.to_dict(), f, indent=2)
            self.logger.info(f"Analysis exported to {filepath}")
        except Exception as e:
            self.logger.error(f"Error exporting analysis: {e}")

    def print_analysis(self, consensus: ConsensusResult):
        """Print formatted analysis to console"""
        print("\n" + "="*70)
        print("HUGGINGFACE AGENT SYSTEM ANALYSIS")
        print("="*70)
        print(f"\nOverall Sentiment: {consensus.overall_sentiment.upper()}")
        print(f"Confidence: {consensus.confidence:.1%}")
        print(f"Recommendation: {consensus.recommendation}")
        print(f"\nTimestamp: {consensus.timestamp}")
        print("\n" + "-"*70)
        print("DETAILED REASONING:")
        print("-"*70)
        print(consensus.reasoning)
        print("="*70 + "\n")


def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


if __name__ == "__main__":
    # Example usage
    setup_logging()

    print("\n" + "="*70)
    print("HuggingFace Agent Trading System - Test Mode")
    print("="*70 + "\n")

    # Initialize system
    system = HFAgentSystem()

    # Example portfolio analysis text
    test_analysis = """
    Market Analysis: The S&P 500 has shown strong momentum with tech stocks leading gains.
    Portfolio Performance: Up 5.2% this month with NVDA and AAPL as top performers.
    Risk Assessment: Volatility remains elevated but within acceptable ranges.
    Economic Outlook: Fed policy remains accommodative with rate cuts expected.
    """

    # Example context
    test_context = {
        "ticker": "SPY",
        "price_change": 0.025,
        "vix": 18.5,
        "market_trend": "up"
    }

    try:
        # Run analysis
        print("Running multi-agent analysis...\n")
        consensus = system.analyze_portfolio_data(test_analysis, test_context)

        # Print results
        system.print_analysis(consensus)

        # Export results
        system.export_analysis(consensus, "hf_agent_analysis.json")
        print("Analysis exported to hf_agent_analysis.json")

    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()
