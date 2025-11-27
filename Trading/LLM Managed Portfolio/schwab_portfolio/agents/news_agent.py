"""
News Sentiment Agent
Analyzes financial news sentiment using DistilRoBERTa model with advanced parsing
"""

import re
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from dataclasses import dataclass

from .base_agent import BaseAgent, AgentResult


@dataclass
class NewsAnalysis:
    """Structured news analysis result"""
    sentiment: str  # positive, negative, neutral
    confidence: float  # 0.0 to 1.0
    tickers: List[str]  # Extracted ticker symbols
    breakdown: Dict[str, float]  # Sentiment breakdown
    news_items_analyzed: int
    raw_results: List[AgentResult]

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "tickers": self.tickers,
            "breakdown": self.breakdown,
            "news_items": self.news_items_analyzed,
            "raw_results": [r.to_dict() for r in self.raw_results]
        }


class NewsAgent(BaseAgent):
    """Analyzes financial news articles for sentiment with advanced parsing"""

    # Common words that look like tickers but aren't
    TICKER_BLACKLIST = {
        'A', 'I', 'FOR', 'THE', 'AND', 'BUT', 'OR', 'TO', 'AT', 'IN', 'ON',
        'BY', 'AS', 'IT', 'AN', 'BE', 'ARE', 'WAS', 'CAN', 'SO', 'IF', 'NO',
        'ALL', 'OUT', 'NEW', 'NOW', 'UP', 'DOWN', 'HAS', 'GET', 'GO', 'SEE',
        'DAY', 'WAY', 'MAY', 'NEXT', 'LAST', 'OVER', 'NEAR', 'WELL', 'BIG',
        'US', 'UK', 'EU', 'ET', 'AM', 'PM', 'CEO', 'CFO', 'CTO', 'IPO',
        'AGO', 'INTO', 'ONE', 'TWO', 'TEN', 'FIVE', 'ADD', 'BUY', 'SELL'
    }

    def __init__(self):
        super().__init__(model_key="news")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze news text for sentiment (single text analysis)

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

        # Make API call (returns None on error, never raises)
        response = self._make_api_call(payload)

        # Handle API failure
        if response is None:
            self.logger.error("API call failed, returning neutral result")
            return AgentResult(
                agent_name="NewsAgent",
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
                agent_name="NewsAgent",
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
        self.logger.info(f"News sentiment: {result.sentiment} (confidence: {result.confidence:.2%})")

        return result

    def analyze_portfolio_document(self, document_text: str, max_items: int = 10) -> NewsAnalysis:
        """
        Analyze portfolio analysis document for news sentiment

        Args:
            document_text: Full text from daily_portfolio_analysis.md
            max_items: Maximum news items to analyze (default: 10)

        Returns:
            NewsAnalysis with aggregated results
        """
        self.logger.info("Analyzing portfolio document for news sentiment")

        # Extract news sections
        news_items = self._extract_news_items(document_text)
        self.logger.info(f"Extracted {len(news_items)} news items")

        # Limit to max_items
        if len(news_items) > max_items:
            self.logger.warning(f"Limiting analysis to {max_items} items (found {len(news_items)})")
            news_items = news_items[:max_items]

        # Analyze each news item
        results = []
        for idx, news_text in enumerate(news_items, 1):
            self.logger.debug(f"Analyzing news item {idx}/{len(news_items)}")
            result = self.analyze(news_text)
            results.append(result)

        # Extract all tickers
        all_tickers = self._extract_tickers(document_text)
        self.logger.info(f"Extracted {len(all_tickers)} unique tickers: {all_tickers}")

        # Aggregate results
        aggregated = self._aggregate_results(results, all_tickers)

        return aggregated

    def _extract_news_items(self, text: str) -> List[str]:
        """
        Extract news items from portfolio analysis document

        Args:
            text: Document text

        Returns:
            List of news item strings
        """
        news_items = []

        # Patterns to identify news sections
        section_patterns = [
            r'(?:^|\n)(?:#+\s*)?(?:News|Events|Market News|Headlines|Recent News)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)',
            r'(?:^|\n)(?:Breaking|Latest|Top Stories)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)',
        ]

        # Try to find news sections
        for pattern in section_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                section_text = match.group(1).strip()
                if section_text:
                    # Split into individual items
                    items = self._split_news_section(section_text)
                    news_items.extend(items)

        # If no structured sections found, look for bullet points or numbered lists
        if not news_items:
            news_items = self._extract_bullet_points(text)

        # Remove duplicates while preserving order
        seen = set()
        unique_items = []
        for item in news_items:
            item_clean = item.strip().lower()
            if item_clean and item_clean not in seen and len(item) > 20:
                seen.add(item_clean)
                unique_items.append(item)

        return unique_items

    def _split_news_section(self, section_text: str) -> List[str]:
        """
        Split news section into individual items

        Args:
            section_text: Text from news section

        Returns:
            List of individual news items
        """
        items = []

        # Try bullet points (-, *, •, ▪)
        bullet_pattern = r'^[\s]*[-*•▪]\s+(.+?)$'
        bullet_matches = re.finditer(bullet_pattern, section_text, re.MULTILINE)
        for match in bullet_matches:
            items.append(match.group(1).strip())

        # Try numbered lists (1., 2., etc.)
        if not items:
            numbered_pattern = r'^\s*\d+\.\s+(.+?)$'
            numbered_matches = re.finditer(numbered_pattern, section_text, re.MULTILINE)
            for match in numbered_matches:
                items.append(match.group(1).strip())

        # Try splitting by double newlines if no structured format
        if not items:
            paragraphs = section_text.split('\n\n')
            items = [p.strip() for p in paragraphs if len(p.strip()) > 20]

        return items

    def _extract_bullet_points(self, text: str) -> List[str]:
        """
        Extract all bullet points from text

        Args:
            text: Full document text

        Returns:
            List of bullet point items
        """
        items = []

        # Match bullet points
        bullet_pattern = r'^[\s]*[-*•▪]\s+(.+?)$'
        matches = re.finditer(bullet_pattern, text, re.MULTILINE)

        for match in matches:
            item = match.group(1).strip()
            # Filter for likely news items (contain company names or financial terms)
            if self._looks_like_news(item):
                items.append(item)

        return items

    def _looks_like_news(self, text: str) -> bool:
        """
        Heuristic to determine if text looks like a news item

        Args:
            text: Text to check

        Returns:
            True if likely news item
        """
        # Check for financial keywords
        financial_keywords = [
            'earnings', 'revenue', 'profit', 'loss', 'stock', 'share', 'market',
            'price', 'trading', 'investor', 'analyst', 'forecast', 'guidance',
            'quarter', 'Q1', 'Q2', 'Q3', 'Q4', 'announced', 'report', 'beats',
            'misses', 'expects', 'outlook', 'growth', 'decline', 'surge',
            'rally', 'drop', 'gain', 'fell', 'rose', 'up', 'down', 'percent', '%'
        ]

        text_lower = text.lower()
        keyword_count = sum(1 for keyword in financial_keywords if keyword in text_lower)

        # Require at least 2 financial keywords and reasonable length
        return keyword_count >= 2 and len(text) > 20

    def _extract_tickers(self, text: str) -> List[str]:
        """
        Extract stock tickers from text

        Handles formats:
        - $AAPL
        - AAPL (standalone)
        - (AAPL)
        - "Apple (AAPL)"

        Args:
            text: Text to extract tickers from

        Returns:
            List of unique ticker symbols
        """
        tickers: Set[str] = set()

        # Pattern 1: $TICKER
        pattern1 = r'\$([A-Z]{1,5})\b'
        matches1 = re.finditer(pattern1, text)
        for match in matches1:
            ticker = match.group(1)
            if ticker not in self.TICKER_BLACKLIST:
                tickers.add(ticker)

        # Pattern 2: (TICKER)
        pattern2 = r'\(([A-Z]{1,5})\)'
        matches2 = re.finditer(pattern2, text)
        for match in matches2:
            ticker = match.group(1)
            if ticker not in self.TICKER_BLACKLIST:
                tickers.add(ticker)

        # Pattern 3: Company Name (TICKER)
        pattern3 = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+\(([A-Z]{1,5})\)'
        matches3 = re.finditer(pattern3, text)
        for match in matches3:
            ticker = match.group(1)
            if ticker not in self.TICKER_BLACKLIST:
                tickers.add(ticker)

        # Pattern 4: Standalone tickers (careful with this one)
        # Only match if preceded by specific words to reduce false positives
        pattern4 = r'\b(?:stock|ticker|symbol|company|shares of|holdings in)\s+([A-Z]{2,5})\b'
        matches4 = re.finditer(pattern4, text, re.IGNORECASE)
        for match in matches4:
            ticker = match.group(1).upper()
            if ticker not in self.TICKER_BLACKLIST and len(ticker) >= 2:
                tickers.add(ticker)

        return sorted(list(tickers))

    def _aggregate_results(self, results: List[AgentResult], tickers: List[str]) -> NewsAnalysis:
        """
        Aggregate multiple news sentiment results

        Args:
            results: List of AgentResult from individual news items
            tickers: Extracted ticker symbols

        Returns:
            NewsAnalysis with aggregated sentiment
        """
        if not results:
            return NewsAnalysis(
                sentiment="neutral",
                confidence=0.0,
                tickers=tickers,
                breakdown={"positive": 0.0, "negative": 0.0, "neutral": 1.0},
                news_items_analyzed=0,
                raw_results=[]
            )

        # Weighted aggregation by confidence
        sentiment_scores = {"positive": 0.0, "negative": 0.0, "neutral": 0.0}
        total_weight = 0.0

        for result in results:
            weight = result.confidence if result.confidence > 0 else 0.1  # Minimum weight
            sentiment_scores[result.sentiment] += weight
            total_weight += weight

        # Normalize to percentages
        if total_weight > 0:
            breakdown = {
                sentiment: (score / total_weight)
                for sentiment, score in sentiment_scores.items()
            }
        else:
            breakdown = {"positive": 0.0, "negative": 0.0, "neutral": 1.0}

        # Determine overall sentiment (highest percentage)
        overall_sentiment = max(breakdown, key=breakdown.get)
        overall_confidence = breakdown[overall_sentiment]

        self.logger.info(
            f"Aggregated {len(results)} items: {overall_sentiment} "
            f"(conf: {overall_confidence:.2%})"
        )

        return NewsAnalysis(
            sentiment=overall_sentiment,
            confidence=overall_confidence,
            tickers=tickers,
            breakdown=breakdown,
            news_items_analyzed=len(results),
            raw_results=results
        )

    def _interpret_results(self, parsed_result: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret parsed classification result for news sentiment

        Args:
            parsed_result: Parsed result with 'label' and 'score'
            text: Original news text
            context: Optional context

        Returns:
            AgentResult with interpretation
        """
        label = parsed_result.get("label", "neutral")
        score = parsed_result.get("score", 0.0)

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
            raw_response=parsed_result
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
