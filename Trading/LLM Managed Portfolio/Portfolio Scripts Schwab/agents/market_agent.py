"""
Market Sentiment Agent
Analyzes market commentary and social sentiment using FinTwitBERT
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentResult


class MarketAgent(BaseAgent):
    """Analyzes market commentary and social media for sentiment"""

    def __init__(self):
        super().__init__(model_key="market")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze market commentary for sentiment

        Args:
            text: Market commentary, social media text, or analyst opinion
            context: Optional context (ticker, market data, etc.)

        Returns:
            AgentResult with market sentiment analysis
        """
        self.logger.info(f"Analyzing market sentiment for {len(text)} characters")

        # Prepare payload
        payload = {
            "inputs": text[:self.model_config.max_length],
            "parameters": {
                "top_k": self.model_config.top_k
            }
        }

        try:
            # Make API call
            response = self._make_api_call(payload)

            # Interpret results
            result = self._interpret_results(response, text, context)

            self.logger.info(f"Market sentiment: {result.sentiment} (confidence: {result.confidence:.2%})")

            return result

        except Exception as e:
            self.logger.error(f"Error analyzing market sentiment: {e}")
            # Return neutral result on error
            return AgentResult(
                agent_name="MarketAgent",
                sentiment="neutral",
                confidence=0.0,
                score=0.0,
                label="ERROR",
                reasoning=f"Error during analysis: {str(e)}",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id
            )

    def _interpret_results(self, response: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret model response for market sentiment

        Args:
            response: Raw API response
            text: Original market commentary
            context: Optional context

        Returns:
            AgentResult with interpretation
        """
        # HF returns list of results
        if isinstance(response, list) and len(response) > 0:
            # Get top prediction
            top_result = response[0]
            if isinstance(top_result, list) and len(top_result) > 0:
                top_result = top_result[0]

            label = top_result.get("label", "neutral")
            score = top_result.get("score", 0.0)

            # Normalize sentiment
            sentiment, confidence = self._normalize_sentiment(label, score)

            # Generate reasoning
            ticker = context.get("ticker", "the market") if context else "the market"
            reasoning = self._generate_reasoning(sentiment, confidence, ticker, context)

            return AgentResult(
                agent_name="MarketAgent",
                sentiment=sentiment,
                confidence=confidence,
                score=score,
                label=label,
                reasoning=reasoning,
                timestamp=datetime.now(),
                model_used=self.model_config.model_id,
                raw_response=response
            )

        # Fallback for unexpected response format
        return AgentResult(
            agent_name="MarketAgent",
            sentiment="neutral",
            confidence=0.0,
            score=0.0,
            label="UNKNOWN",
            reasoning="Unable to parse model response",
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response=response
        )

    def _generate_reasoning(self, sentiment: str, confidence: float, ticker: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate human-readable reasoning for the sentiment"""
        if confidence > 0.8:
            strength = "Strong"
        elif confidence > 0.6:
            strength = "Moderate"
        else:
            strength = "Weak"

        reasoning = f"{strength} {sentiment} market sentiment for {ticker}. "

        if sentiment == "positive":
            reasoning += "Market commentary suggests bullish sentiment and positive momentum."
        elif sentiment == "negative":
            reasoning += "Market commentary suggests bearish sentiment and negative pressure."
        else:
            reasoning += "Market commentary appears neutral or mixed."

        # Add price context if available
        if context and "price_change" in context:
            price_change = context["price_change"]
            if price_change > 0:
                reasoning += f" Price is up {price_change:.1%}."
            elif price_change < 0:
                reasoning += f" Price is down {abs(price_change):.1%}."

        reasoning += f" (Confidence: {confidence:.1%})"

        return reasoning
