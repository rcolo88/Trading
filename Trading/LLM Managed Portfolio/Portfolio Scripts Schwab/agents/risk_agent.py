"""
Risk Analysis Agent
Analyzes financial text for risk factors using FinBERT
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentResult


class RiskAgent(BaseAgent):
    """Analyzes financial text for risk and sentiment"""

    def __init__(self):
        super().__init__(model_key="risk")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze text for risk factors and sentiment

        Args:
            text: Financial text to analyze for risk
            context: Optional context (portfolio data, position size, etc.)

        Returns:
            AgentResult with risk analysis
        """
        self.logger.info(f"Analyzing risk factors for {len(text)} characters")

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

            self.logger.info(f"Risk assessment: {result.sentiment} (confidence: {result.confidence:.2%})")

            return result

        except Exception as e:
            self.logger.error(f"Error analyzing risk: {e}")
            # Return neutral result on error - conservative for risk
            return AgentResult(
                agent_name="RiskAgent",
                sentiment="neutral",
                confidence=0.0,
                score=0.0,
                label="ERROR",
                reasoning=f"Error during risk analysis: {str(e)}. Recommend caution.",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id
            )

    def _interpret_results(self, response: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret model response for risk analysis

        Args:
            response: Raw API response
            text: Original text
            context: Optional context

        Returns:
            AgentResult with risk interpretation
        """
        # HF returns list of results
        if isinstance(response, list) and len(response) > 0:
            # Get top prediction
            top_result = response[0]
            if isinstance(top_result, list) and len(top_result) > 0:
                top_result = top_result[0]

            label = top_result.get("label", "neutral")
            score = top_result.get("score", 0.0)

            # Normalize sentiment (negative sentiment = higher risk)
            sentiment, confidence = self._normalize_sentiment(label, score)

            # Generate reasoning
            ticker = context.get("ticker", "position") if context else "position"
            reasoning = self._generate_reasoning(sentiment, confidence, ticker, context)

            return AgentResult(
                agent_name="RiskAgent",
                sentiment=sentiment,
                confidence=confidence,
                score=score,
                label=label,
                reasoning=reasoning,
                timestamp=datetime.now(),
                model_used=self.model_config.model_id,
                raw_response=response
            )

        # Fallback for unexpected response format - default to caution
        return AgentResult(
            agent_name="RiskAgent",
            sentiment="neutral",
            confidence=0.0,
            score=0.0,
            label="UNKNOWN",
            reasoning="Unable to parse risk analysis. Recommend caution.",
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response=response
        )

    def _generate_reasoning(self, sentiment: str, confidence: float, ticker: str, context: Optional[Dict[str, Any]]) -> str:
        """Generate human-readable reasoning for the risk assessment"""
        reasoning = ""

        if sentiment == "positive":
            if confidence > 0.7:
                reasoning = f"Low risk profile for {ticker}. "
                reasoning += "Financial indicators suggest stable or improving conditions. "
            else:
                reasoning = f"Generally favorable risk profile for {ticker}. "
        elif sentiment == "negative":
            if confidence > 0.7:
                reasoning = f"HIGH RISK WARNING for {ticker}. "
                reasoning += "Financial indicators suggest significant risk factors. "
            else:
                reasoning = f"Elevated risk detected for {ticker}. "
        else:
            reasoning = f"Neutral risk profile for {ticker}. "

        # Add position size context if available
        if context:
            if "position_size" in context:
                pos_size = context["position_size"]
                if pos_size > 0.15:  # >15% of portfolio
                    reasoning += f"CONCENTRATION RISK: Position is {pos_size:.1%} of portfolio. "
                elif pos_size > 0.10:
                    reasoning += f"Notable position at {pos_size:.1%} of portfolio. "

            if "volatility" in context:
                vol = context["volatility"]
                if vol > 0.30:  # >30% annualized volatility
                    reasoning += f"HIGH VOLATILITY: {vol:.1%} annualized. "

        reasoning += f"Risk confidence: {confidence:.1%}."

        return reasoning
