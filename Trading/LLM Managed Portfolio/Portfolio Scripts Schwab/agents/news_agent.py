"""
News Sentiment Agent
Analyzes financial news sentiment using DistilRoBERTa model
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentResult


class NewsAgent(BaseAgent):
    """Analyzes financial news articles for sentiment"""

    def __init__(self):
        super().__init__(model_key="news")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze news text for sentiment

        Args:
            text: News article or headline text
            context: Optional context (ticker, date, etc.)

        Returns:
            AgentResult with news sentiment analysis
        """
        self.logger.info(f"Analyzing news sentiment for {len(text)} characters")

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

            self.logger.info(f"News sentiment: {result.sentiment} (confidence: {result.confidence:.2%})")

            return result

        except Exception as e:
            self.logger.error(f"Error analyzing news: {e}")
            # Return neutral result on error
            return AgentResult(
                agent_name="NewsAgent",
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
        Interpret model response for news sentiment

        Args:
            response: Raw API response
            text: Original news text
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
            ticker = context.get("ticker", "market") if context else "market"
            reasoning = self._generate_reasoning(sentiment, confidence, ticker, text[:100])

            return AgentResult(
                agent_name="NewsAgent",
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
            agent_name="NewsAgent",
            sentiment="neutral",
            confidence=0.0,
            score=0.0,
            label="UNKNOWN",
            reasoning="Unable to parse model response",
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response=response
        )

    def _generate_reasoning(self, sentiment: str, confidence: float, ticker: str, text_preview: str) -> str:
        """Generate human-readable reasoning for the sentiment"""
        if confidence > 0.8:
            strength = "Strong"
        elif confidence > 0.6:
            strength = "Moderate"
        else:
            strength = "Weak"

        reasoning = f"{strength} {sentiment} sentiment detected in news about {ticker}. "

        if sentiment == "positive":
            reasoning += "News suggests favorable developments or positive market perception."
        elif sentiment == "negative":
            reasoning += "News indicates concerning developments or negative market perception."
        else:
            reasoning += "News appears neutral or mixed in tone."

        reasoning += f" (Confidence: {confidence:.1%})"

        return reasoning
