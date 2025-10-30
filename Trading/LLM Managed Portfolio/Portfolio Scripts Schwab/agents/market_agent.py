"""
Market Sentiment Agent
Analyzes market commentary and social sentiment using FinTwitBERT
"""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .base_agent import BaseAgent, AgentResult


@dataclass
class MarketAnalysis:
    """Structured market analysis result"""
    sentiment: str  # Bullish, Bearish, Neutral
    strength: str  # strong, moderate, weak
    confidence: float  # 0.0 to 1.0
    market_factors: List[str]  # Extracted market factors
    position_sentiments: Dict[str, str]  # {"AAPL": "Bullish", "NVDA": "Neutral"}
    sections_analyzed: int
    raw_results: List[AgentResult]

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "sentiment": self.sentiment,
            "strength": self.strength,
            "confidence": self.confidence,
            "market_factors": self.market_factors,
            "position_sentiments": self.position_sentiments,
            "sections_analyzed": self.sections_analyzed,
            "raw_results": [r.to_dict() for r in self.raw_results]
        }


class MarketAgent(BaseAgent):
    """Analyzes market commentary and social media for sentiment"""

    # Market-related keywords for factor extraction
    MARKET_FACTORS = {
        'interest rates', 'fed', 'federal reserve', 'rate cuts', 'rate hikes',
        'inflation', 'cpi', 'ppi', 'deflation',
        'earnings', 'earnings season', 'guidance', 'revenue', 'profit',
        'unemployment', 'jobs report', 'employment',
        'gdp', 'economic growth', 'recession', 'expansion',
        'volatility', 'vix', 'market volatility',
        'treasury', 'bonds', 'yield curve',
        'china', 'trade war', 'tariffs', 'geopolitics',
        'sector rotation', 'rebalancing',
        'technical analysis', 'support', 'resistance', 'breakout',
        'momentum', 'trend', 'oversold', 'overbought'
    }

    def __init__(self):
        super().__init__(model_key="market")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze market commentary for sentiment (single text analysis)

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

        # Make API call (returns None on error, never raises)
        response = self._make_api_call(payload)

        # Handle API failure
        if response is None:
            self.logger.error("API call failed, returning neutral result")
            return AgentResult(
                agent_name="MarketAgent",
                sentiment="neutral",
                confidence=0.0,
                score=0.0,
                label="ERROR",
                reasoning="API call failed after retries",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id
            )

        # Parse classification response
        parsed = self._parse_classification_response(response)
        if parsed is None:
            self.logger.error("Failed to parse response, returning neutral result")
            return AgentResult(
                agent_name="MarketAgent",
                sentiment="neutral",
                confidence=0.0,
                score=0.0,
                label="PARSE_ERROR",
                reasoning="Unable to parse model response",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id,
                raw_response=response
            )

        # Interpret results
        result = self._interpret_results(parsed, text, context)
        self.logger.info(f"Market sentiment: {result.sentiment} (confidence: {result.confidence:.2%})")

        return result

    def analyze_portfolio_document(self, document_text: str) -> MarketAnalysis:
        """
        Analyze portfolio document for market sentiment

        Args:
            document_text: Full text from daily_portfolio_analysis.md

        Returns:
            MarketAnalysis with aggregated results
        """
        self.logger.info("Analyzing portfolio document for market sentiment")

        # Extract market commentary sections
        market_sections = self._extract_market_sections(document_text)
        self.logger.info(f"Extracted {len(market_sections)} market commentary sections")

        # Extract position-specific commentary
        position_commentary = self._extract_position_commentary(document_text)
        self.logger.info(f"Extracted commentary for {len(position_commentary)} positions")

        # Analyze each market section
        results = []
        for idx, (section_name, section_text) in enumerate(market_sections.items(), 1):
            self.logger.debug(f"Analyzing section {idx}/{len(market_sections)}: {section_name}")
            result = self.analyze(section_text, context={"section": section_name})
            results.append(result)

        # Analyze position-specific commentary
        position_results = {}
        for ticker, commentary in position_commentary.items():
            self.logger.debug(f"Analyzing position commentary for {ticker}")
            result = self.analyze(commentary, context={"ticker": ticker})
            position_results[ticker] = result

        # Extract market factors
        market_factors = self._extract_market_factors(document_text)
        self.logger.info(f"Extracted {len(market_factors)} market factors: {market_factors}")

        # Aggregate results
        aggregated = self._aggregate_results(results, position_results, market_factors)

        return aggregated

    def _extract_market_sections(self, text: str) -> Dict[str, str]:
        """
        Extract market-related sections from document

        Args:
            text: Document text

        Returns:
            Dict of {section_name: section_text}
        """
        sections = {}

        # Section patterns to look for
        section_patterns = [
            (r'(?:^|\n)(?:#+\s*)?(?:Market Analysis|Market Overview)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)', 'Market Analysis'),
            (r'(?:^|\n)(?:#+\s*)?(?:Technical Overview|Technical Analysis)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)', 'Technical Analysis'),
            (r'(?:^|\n)(?:#+\s*)?(?:Market Conditions|Market Environment)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)', 'Market Conditions'),
            (r'(?:^|\n)(?:#+\s*)?(?:Economic Outlook|Economic Analysis)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)', 'Economic Outlook'),
            (r'(?:^|\n)(?:#+\s*)?(?:Sector Analysis|Sector Review)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)', 'Sector Analysis'),
        ]

        for pattern, section_name in section_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                section_text = match.group(1).strip()
                if section_text and len(section_text) > 50:  # Minimum length
                    sections[section_name] = section_text
                    self.logger.debug(f"Found section: {section_name} ({len(section_text)} chars)")

        return sections

    def _extract_position_commentary(self, text: str) -> Dict[str, str]:
        """
        Extract position-specific commentary from document

        Args:
            text: Document text

        Returns:
            Dict of {ticker: commentary_text}
        """
        position_commentary = {}

        # Look for patterns like "AAPL: ..." or "Apple (AAPL): ..."
        # Pattern 1: Ticker followed by colon and description
        pattern1 = r'\n([A-Z]{2,5}):\s*([^\n]+(?:\n(?!\n|[A-Z]{2,5}:)[^\n]+)*)'
        matches1 = re.finditer(pattern1, text)
        for match in matches1:
            ticker = match.group(1)
            commentary = match.group(2).strip()
            if len(commentary) > 20 and ticker not in ['CEO', 'CFO', 'CTO', 'IPO', 'USA', 'EUR']:
                position_commentary[ticker] = commentary

        # Pattern 2: Company Name (TICKER): description
        pattern2 = r'\n[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\(([A-Z]{2,5})\):\s*([^\n]+(?:\n(?!\n)[^\n]+)*)'
        matches2 = re.finditer(pattern2, text)
        for match in matches2:
            ticker = match.group(1)
            commentary = match.group(2).strip()
            if len(commentary) > 20:
                # Combine with existing if present
                if ticker in position_commentary:
                    position_commentary[ticker] += " " + commentary
                else:
                    position_commentary[ticker] = commentary

        # Pattern 3: Bullet points with ticker mentions
        bullet_pattern = r'[-*•▪]\s*(?:\$)?([A-Z]{2,5})\b[:\s]+([^\n]+)'
        matches3 = re.finditer(bullet_pattern, text)
        for match in matches3:
            ticker = match.group(1)
            commentary = match.group(2).strip()
            if len(commentary) > 20 and ticker not in ['FOR', 'THE', 'AND', 'ALL']:
                if ticker in position_commentary:
                    position_commentary[ticker] += " " + commentary
                else:
                    position_commentary[ticker] = commentary

        return position_commentary

    def _extract_market_factors(self, text: str) -> List[str]:
        """
        Extract market factors mentioned in text

        Args:
            text: Document text

        Returns:
            List of market factors found
        """
        text_lower = text.lower()
        found_factors = []

        for factor in self.MARKET_FACTORS:
            if factor in text_lower:
                found_factors.append(factor)

        return sorted(list(set(found_factors)))

    def _aggregate_results(
        self,
        section_results: List[AgentResult],
        position_results: Dict[str, AgentResult],
        market_factors: List[str]
    ) -> MarketAnalysis:
        """
        Aggregate market sentiment results

        Args:
            section_results: Results from market sections
            position_results: Results from position commentary
            market_factors: Extracted market factors

        Returns:
            MarketAnalysis with aggregated sentiment
        """
        if not section_results:
            return MarketAnalysis(
                sentiment="Neutral",
                strength="weak",
                confidence=0.0,
                market_factors=market_factors,
                position_sentiments={},
                sections_analyzed=0,
                raw_results=[]
            )

        # Weighted aggregation by confidence
        sentiment_scores = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        total_weight = 0.0

        for result in section_results:
            weight = result.confidence if result.confidence > 0 else 0.1
            sentiment_scores[result.sentiment] += weight
            total_weight += weight

        # Normalize
        if total_weight > 0:
            for sentiment in sentiment_scores:
                sentiment_scores[sentiment] /= total_weight

        # Determine overall sentiment
        dominant_sentiment = max(sentiment_scores, key=sentiment_scores.get)
        confidence = sentiment_scores[dominant_sentiment]

        # Map to FinTwitBERT labels (Bullish/Bearish/Neutral)
        if dominant_sentiment == "positive":
            market_sentiment = "Bullish"
        elif dominant_sentiment == "negative":
            market_sentiment = "Bearish"
        else:
            market_sentiment = "Neutral"

        # Determine strength based on confidence
        if confidence >= 0.75:
            strength = "strong"
        elif confidence >= 0.55:
            strength = "moderate"
        else:
            strength = "weak"

        # Convert position sentiments to Bullish/Bearish/Neutral format
        position_sentiments = {}
        for ticker, result in position_results.items():
            if result.sentiment == "positive":
                position_sentiments[ticker] = "Bullish"
            elif result.sentiment == "negative":
                position_sentiments[ticker] = "Bearish"
            else:
                position_sentiments[ticker] = "Neutral"

        self.logger.info(
            f"Aggregated {len(section_results)} sections: {market_sentiment} "
            f"({strength}, conf: {confidence:.2%})"
        )

        return MarketAnalysis(
            sentiment=market_sentiment,
            strength=strength,
            confidence=confidence,
            market_factors=market_factors,
            position_sentiments=position_sentiments,
            sections_analyzed=len(section_results),
            raw_results=section_results
        )

    def _interpret_results(self, parsed_result: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret parsed classification result for market sentiment

        Args:
            parsed_result: Parsed result with 'label' and 'score'
            text: Original market commentary
            context: Optional context

        Returns:
            AgentResult with interpretation
        """
        label = parsed_result.get("label", "neutral")
        score = parsed_result.get("score", 0.0)

        # FinTwitBERT uses Bullish/Bearish/Neutral labels
        # Normalize to our standard format
        label_lower = label.lower()
        if "bullish" in label_lower or "bull" in label_lower:
            sentiment = "positive"
        elif "bearish" in label_lower or "bear" in label_lower:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        confidence = max(0.0, min(1.0, score))

        # Generate reasoning
        ticker = context.get("ticker", "the market") if context else "the market"
        section = context.get("section", "market commentary") if context else "market commentary"
        reasoning = self._generate_reasoning(sentiment, confidence, ticker, section, context)

        return AgentResult(
            agent_name="MarketAgent",
            sentiment=sentiment,
            confidence=confidence,
            score=score,
            label=label,
            reasoning=reasoning,
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response=parsed_result
        )

    def _generate_reasoning(
        self,
        sentiment: str,
        confidence: float,
        ticker: str,
        section: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Generate human-readable reasoning for the sentiment"""
        if confidence > 0.8:
            strength = "Very strong"
        elif confidence > 0.65:
            strength = "Strong"
        elif confidence > 0.5:
            strength = "Moderate"
        else:
            strength = "Weak"

        # Map sentiment to market terms
        if sentiment == "positive":
            market_term = "bullish"
        elif sentiment == "negative":
            market_term = "bearish"
        else:
            market_term = "neutral"

        reasoning = f"{strength} {market_term} sentiment for {ticker} based on {section}. "

        if sentiment == "positive":
            reasoning += "Market commentary suggests optimistic outlook and positive momentum."
        elif sentiment == "negative":
            reasoning += "Market commentary indicates concerns and negative pressure."
        else:
            reasoning += "Market commentary appears balanced or uncertain."

        # Add price context if available
        if context and "price_change" in context:
            price_change = context["price_change"]
            if abs(price_change) > 0.02:  # >2% change
                if price_change > 0:
                    reasoning += f" Price momentum: +{price_change:.1%}."
                else:
                    reasoning += f" Price momentum: {price_change:.1%}."

        reasoning += f" (Confidence: {confidence:.1%})"

        return reasoning
