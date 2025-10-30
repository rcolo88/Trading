"""
Risk Analysis Agent
Analyzes financial text for risk factors using FinBERT with conservative assessment
"""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .base_agent import BaseAgent, AgentResult


@dataclass
class RiskAnalysis:
    """Structured risk analysis result"""
    risk_level: str  # high, medium, low
    confidence: float  # 0.0 to 1.0
    concerns: List[str]  # Specific risk concerns
    risk_scores: Dict[str, float]  # {"systemic": 0.7, "position": 0.3, "market": 0.5}
    recommended_action: str  # reduce exposure, maintain, increase
    risk_factors_analyzed: int
    raw_results: List[AgentResult]

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "concerns": self.concerns,
            "risk_scores": self.risk_scores,
            "recommended_action": self.recommended_action,
            "risk_factors_analyzed": self.risk_factors_analyzed,
            "raw_results": [r.to_dict() for r in self.raw_results]
        }


class RiskAgent(BaseAgent):
    """Analyzes financial text for risk and sentiment with conservative bias"""

    # Risk-related keywords for concern identification
    RISK_KEYWORDS = {
        # High severity
        'high': {
            'warning', 'alert', 'caution', 'danger', 'critical', 'urgent',
            'severe', 'significant', 'major', 'concern', 'risk',
            'vulnerable', 'exposure', 'threat', 'crisis', 'downturn',
            'collapse', 'crash', 'plunge', 'tumble', 'decline'
        },
        # Concentration risks
        'concentration': {
            'concentration', 'overweight', 'overexposed', 'heavily weighted',
            'dominant position', 'large position', 'significant holding'
        },
        # Volatility risks
        'volatility': {
            'volatility', 'volatile', 'unstable', 'erratic', 'fluctuation',
            'swing', 'whipsaw', 'turbulent', 'choppy'
        },
        # Market risks
        'market': {
            'bear market', 'correction', 'selloff', 'sell-off', 'drawdown',
            'pullback', 'retreat', 'weakness', 'pressure'
        },
        # Systemic risks
        'systemic': {
            'systemic', 'contagion', 'spillover', 'financial crisis',
            'credit crunch', 'liquidity crisis', 'bank run'
        },
        # Stop-loss and protective
        'protective': {
            'stop-loss', 'stop loss', 'trailing stop', 'exit strategy',
            'risk management', 'hedge', 'protection', 'defensive'
        }
    }

    def __init__(self):
        super().__init__(model_key="risk")

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Analyze text for risk factors and sentiment (single text analysis)

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

        # Make API call (returns None on error, never raises)
        response = self._make_api_call(payload)

        # Handle API failure - conservative for risk
        if response is None:
            self.logger.error("API call failed, returning medium risk (conservative)")
            return AgentResult(
                agent_name="RiskAgent",
                sentiment="neutral",
                confidence=0.5,  # Medium confidence for default risk
                score=0.5,
                label="ERROR",
                reasoning="API call failed. Defaulting to medium risk (conservative approach).",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id
            )

        # Parse classification response
        parsed = self._parse_classification_response(response)
        if parsed is None:
            self.logger.error("Failed to parse response, returning medium risk (conservative)")
            return AgentResult(
                agent_name="RiskAgent",
                sentiment="neutral",
                confidence=0.5,
                score=0.5,
                label="PARSE_ERROR",
                reasoning="Unable to parse risk analysis. Defaulting to medium risk.",
                timestamp=datetime.now(),
                model_used=self.model_config.model_id,
                raw_response=response
            )

        # Interpret results
        result = self._interpret_results(parsed, text, context)
        self.logger.info(f"Risk assessment: {result.sentiment} (confidence: {result.confidence:.2%})")

        return result

    def analyze_portfolio_document(self, document_text: str, portfolio_data: Optional[Dict[str, Any]] = None) -> RiskAnalysis:
        """
        Analyze portfolio document for risk factors

        Args:
            document_text: Full text from daily_portfolio_analysis.md
            portfolio_data: Optional portfolio metrics (concentration, volatility, etc.)

        Returns:
            RiskAnalysis with comprehensive risk assessment
        """
        self.logger.info("Analyzing portfolio document for risk factors")

        # Extract risk-related sections
        risk_sections = self._extract_risk_sections(document_text)
        self.logger.info(f"Extracted {len(risk_sections)} risk-related sections")

        # Extract specific risk factors
        risk_factors = self._extract_risk_factors(document_text)
        self.logger.info(f"Identified {len(risk_factors)} risk factors")

        # Analyze each risk section
        results = []
        for section_text in risk_sections:
            self.logger.debug(f"Analyzing risk section ({len(section_text)} chars)")
            result = self.analyze(section_text, context=portfolio_data)
            results.append(result)

        # Analyze individual risk factors
        for factor_text in risk_factors:
            self.logger.debug(f"Analyzing risk factor: {factor_text[:50]}...")
            result = self.analyze(factor_text, context=portfolio_data)
            results.append(result)

        # Extract concerns
        concerns = self._identify_concerns(document_text, portfolio_data)
        self.logger.info(f"Identified {len(concerns)} specific concerns")

        # Aggregate results
        aggregated = self._aggregate_results(results, concerns, portfolio_data)

        return aggregated

    def _extract_risk_sections(self, text: str) -> List[str]:
        """
        Extract risk-related sections from document

        Args:
            text: Document text

        Returns:
            List of risk section texts
        """
        sections = []

        # Section patterns for risk content
        section_patterns = [
            r'(?:^|\n)(?:#+\s*)?(?:Risk|Risks|Risk Assessment|Risk Analysis)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)',
            r'(?:^|\n)(?:#+\s*)?(?:Warnings?|Alerts?|Cautions?)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)',
            r'(?:^|\n)(?:#+\s*)?(?:Concerns?|Issues?|Problems?)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)',
            r'(?:^|\n)(?:#+\s*)?(?:Volatility|Market Volatility)[:\s]*\n(.*?)(?=\n#{1,3}\s|\n\n\n|\Z)',
        ]

        for pattern in section_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
            for match in matches:
                section_text = match.group(1).strip()
                if section_text and len(section_text) > 30:
                    sections.append(section_text)

        return sections

    def _extract_risk_factors(self, text: str) -> List[str]:
        """
        Extract individual risk factors from text

        Args:
            text: Document text

        Returns:
            List of risk factor texts
        """
        factors = []

        # Look for sentences with risk keywords
        sentences = re.split(r'[.!?]+', text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue

            sentence_lower = sentence.lower()

            # Check if sentence contains risk keywords
            for category, keywords in self.RISK_KEYWORDS.items():
                if any(keyword in sentence_lower for keyword in keywords):
                    factors.append(sentence)
                    break  # Only add once per sentence

        # Remove duplicates
        unique_factors = list(dict.fromkeys(factors))

        return unique_factors[:20]  # Limit to 20 factors to avoid API overload

    def _identify_concerns(self, text: str, portfolio_data: Optional[Dict[str, Any]]) -> List[str]:
        """
        Identify specific risk concerns

        Args:
            text: Document text
            portfolio_data: Optional portfolio metrics

        Returns:
            List of concern descriptions
        """
        concerns = []
        text_lower = text.lower()

        # Check for high severity keywords
        for keyword in self.RISK_KEYWORDS['high']:
            if keyword in text_lower:
                concerns.append(f"{keyword.title()} mentioned")

        # Check for concentration risks
        for keyword in self.RISK_KEYWORDS['concentration']:
            if keyword in text_lower:
                concerns.append("Portfolio concentration risk")
                break

        # Check for volatility
        for keyword in self.RISK_KEYWORDS['volatility']:
            if keyword in text_lower:
                concerns.append("High market volatility")
                break

        # Check for market risks
        for keyword in self.RISK_KEYWORDS['market']:
            if keyword in text_lower:
                concerns.append("Adverse market conditions")
                break

        # Check for systemic risks
        for keyword in self.RISK_KEYWORDS['systemic']:
            if keyword in text_lower:
                concerns.append("Systemic risk factors")
                break

        # Check portfolio metrics if provided
        if portfolio_data:
            if portfolio_data.get('max_position_weight', 0) > 0.20:
                concerns.append(f"High concentration ({portfolio_data['max_position_weight']:.1%})")

            if portfolio_data.get('portfolio_volatility', 0) > 0.25:
                concerns.append(f"High volatility ({portfolio_data['portfolio_volatility']:.1%})")

            if portfolio_data.get('cash_percentage', 100) < 5:
                concerns.append("Low cash reserves")

        # Remove duplicates
        unique_concerns = list(dict.fromkeys(concerns))

        return unique_concerns[:10]  # Top 10 concerns

    def _aggregate_results(
        self,
        results: List[AgentResult],
        concerns: List[str],
        portfolio_data: Optional[Dict[str, Any]]
    ) -> RiskAnalysis:
        """
        Aggregate risk analysis results with conservative bias

        Args:
            results: List of AgentResult from risk factors
            concerns: Identified concerns
            portfolio_data: Optional portfolio metrics

        Returns:
            RiskAnalysis with overall assessment
        """
        if not results:
            # No results - default to medium risk (conservative)
            return RiskAnalysis(
                risk_level="medium",
                confidence=0.5,
                concerns=concerns if concerns else ["Insufficient data for assessment"],
                risk_scores={"systemic": 0.5, "position": 0.5, "market": 0.5},
                recommended_action="maintain",
                risk_factors_analyzed=0,
                raw_results=[]
            )

        # Calculate risk score (negative sentiment = higher risk)
        risk_score = 0.0
        total_weight = 0.0

        for result in results:
            weight = result.confidence if result.confidence > 0 else 0.1

            # Map sentiment to risk (inverted: negative sentiment = high risk)
            if result.sentiment == "negative":
                risk_contribution = weight * 1.0  # High risk
            elif result.sentiment == "neutral":
                risk_contribution = weight * 0.5  # Medium risk
            else:  # positive
                risk_contribution = weight * 0.0  # Low risk

            risk_score += risk_contribution
            total_weight += weight

        # Normalize risk score
        if total_weight > 0:
            normalized_risk = risk_score / total_weight
        else:
            normalized_risk = 0.5  # Default medium

        # Conservative bias: bump up risk if concerns present
        if len(concerns) > 5:
            normalized_risk = min(1.0, normalized_risk + 0.2)
        elif len(concerns) > 2:
            normalized_risk = min(1.0, normalized_risk + 0.1)

        # Classify risk level
        if normalized_risk >= 0.65:
            risk_level = "high"
        elif normalized_risk >= 0.35:
            risk_level = "medium"
        else:
            risk_level = "low"

        # Calculate confidence (higher when more results)
        confidence = min(0.9, 0.5 + (len(results) * 0.05))

        # Calculate risk scores by category
        risk_scores = self._calculate_risk_scores(results, concerns, portfolio_data)

        # Determine recommended action
        recommended_action = self._determine_action(risk_level, concerns, risk_scores)

        self.logger.info(
            f"Risk assessment: {risk_level.upper()} risk "
            f"(score: {normalized_risk:.2f}, confidence: {confidence:.1%})"
        )

        return RiskAnalysis(
            risk_level=risk_level,
            confidence=confidence,
            concerns=concerns,
            risk_scores=risk_scores,
            recommended_action=recommended_action,
            risk_factors_analyzed=len(results),
            raw_results=results
        )

    def _calculate_risk_scores(
        self,
        results: List[AgentResult],
        concerns: List[str],
        portfolio_data: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Calculate risk scores by category"""
        scores = {"systemic": 0.0, "position": 0.0, "market": 0.0}

        # Analyze concerns for categories
        concerns_text = " ".join(concerns).lower()

        if any(keyword in concerns_text for keyword in ['systemic', 'contagion', 'crisis']):
            scores['systemic'] = 0.7
        elif any(keyword in concerns_text for keyword in ['market', 'correction', 'volatility']):
            scores['systemic'] = 0.4

        if any(keyword in concerns_text for keyword in ['concentration', 'position', 'weight']):
            scores['position'] = 0.8
        elif any(keyword in concerns_text for keyword in ['holding', 'exposure']):
            scores['position'] = 0.5

        if any(keyword in concerns_text for keyword in ['market', 'volatility', 'turbulent']):
            scores['market'] = 0.7
        elif any(keyword in concerns_text for keyword in ['pressure', 'weakness']):
            scores['market'] = 0.5

        # Adjust based on portfolio data
        if portfolio_data:
            if portfolio_data.get('max_position_weight', 0) > 0.20:
                scores['position'] = max(scores['position'], 0.7)

            if portfolio_data.get('portfolio_volatility', 0) > 0.25:
                scores['market'] = max(scores['market'], 0.6)

        # Default to medium risk if no signals
        for category in scores:
            if scores[category] == 0.0:
                scores[category] = 0.5

        return scores

    def _determine_action(self, risk_level: str, concerns: List[str], risk_scores: Dict[str, float]) -> str:
        """Determine recommended action based on risk assessment"""
        if risk_level == "high":
            if any(score > 0.75 for score in risk_scores.values()):
                return "reduce exposure significantly"
            return "reduce exposure"

        elif risk_level == "medium":
            if len(concerns) > 3:
                return "maintain with caution"
            return "maintain"

        else:  # low risk
            if all(score < 0.3 for score in risk_scores.values()):
                return "consider increase"
            return "maintain"

    def _interpret_results(self, parsed_result: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret parsed classification result for risk analysis

        Args:
            parsed_result: Parsed result with 'label' and 'score'
            text: Original text
            context: Optional context

        Returns:
            AgentResult with risk interpretation
        """
        label = parsed_result.get("label", "neutral")
        score = parsed_result.get("score", 0.0)

        # Normalize sentiment (negative sentiment = higher risk)
        sentiment, confidence = self._normalize_sentiment(label, score)

        # Generate reasoning
        ticker = context.get("ticker", "portfolio") if context else "portfolio"
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
            raw_response=parsed_result
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
