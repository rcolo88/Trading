"""
Market Tone Agent
Analyzes overall market tone using FinBERT-tone model
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentResult


class ToneAgent(BaseAgent):
    """Analyzes overall market tone and sentiment"""

    def __init__(self):
        super().__init__(model_key="tone")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze text for overall market tone

        Args:
            text: Market commentary or analysis text
            context: Optional context (market indices, VIX, etc.)

        Returns:
            AgentResult with tone analysis
        """
        self.logger.info(f"Analyzing market tone for {len(text)} characters")

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

            self.logger.info(f"Market tone: {result.sentiment} (confidence: {result.confidence:.2%})")

            return result

        except Exception as e:
            self.logger.error(f"Error analyzing market tone: {e}")
            # Return neutral result on error
            return AgentResult(
                agent_name="ToneAgent",
                sentiment="neutral",
                confidence=0.0,
                score=0.0,
                label="ERROR",
                reasoning=f"Error during tone analysis: {str(e)}",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id
            )

    def _interpret_results(self, response: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret model response for market tone

        Args:
            response: Raw API response
            text: Original text
            context: Optional context

        Returns:
            AgentResult with tone interpretation
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
            reasoning = self._generate_reasoning(sentiment, confidence, context)

            return AgentResult(
                agent_name="ToneAgent",
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
            agent_name="ToneAgent",
            sentiment="neutral",
            confidence=0.0,
            score=0.0,
            label="UNKNOWN",
            reasoning="Unable to parse tone analysis",
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response=response
        )

    def _generate_reasoning(self, sentiment: str, confidence: float, context: Optional[Dict[str, Any]]) -> str:
        """Generate human-readable reasoning for the tone assessment"""
        if confidence > 0.8:
            strength = "Very clear"
        elif confidence > 0.6:
            strength = "Clear"
        else:
            strength = "Somewhat"

        reasoning = f"{strength} {sentiment} market tone detected. "

        if sentiment == "positive":
            reasoning += "Overall market sentiment appears optimistic and constructive."
        elif sentiment == "negative":
            reasoning += "Overall market sentiment appears pessimistic and cautious."
        else:
            reasoning += "Overall market sentiment appears balanced or uncertain."

        # Add market context if available
        if context:
            if "vix" in context:
                vix = context["vix"]
                if vix > 25:
                    reasoning += f" VIX elevated at {vix:.1f} (fear)."
                elif vix < 15:
                    reasoning += f" VIX low at {vix:.1f} (complacency)."

            if "market_trend" in context:
                trend = context["market_trend"]
                if trend == "up":
                    reasoning += " Broad market trending upward."
                elif trend == "down":
                    reasoning += " Broad market trending downward."

            if "sector_rotation" in context:
                reasoning += f" {context['sector_rotation']}"

        reasoning += f" (Confidence: {confidence:.1%})"

        return reasoning
