"""
Reasoning Agent
Synthesizes all agent outputs to make final BUY/SELL/HOLD decisions using DeepSeek-R1 reasoning model
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

from .base_agent import BaseAgent, AgentResult


@dataclass
class ReasoningDecision:
    """Structured reasoning decision result"""
    ticker: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 to 1.0
    reasoning_steps: List[str]  # Step-by-step reasoning
    key_factors: Dict[str, Any]  # Factors considered
    recommended_shares: Optional[int] = None
    price_target: Optional[float] = None


class ReasoningAgent(BaseAgent):
    """
    Synthesizes all agent outputs to make final trading decisions

    Uses DeepSeek-R1-Distill-Qwen-14B for reasoning and decision synthesis.

    Decision Logic:
    - HOLD: Default when quality >70, no major red flags, neutral/positive news
    - SELL: Quality <60 OR >3 red flags OR major negative catalyst
    - BUY: Alternative quality >85 OR >15 points better than current holding
    """

    def __init__(self):
        super().__init__(model_key="reasoning")

    def synthesize_decision(
        self,
        ticker: str,
        agent_outputs: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ReasoningDecision:
        """
        Synthesize all agent outputs into a final trading decision

        Args:
            ticker: Stock ticker symbol
            agent_outputs: Dict with outputs from all agents:
                - news_sentiment: NewsAgent result
                - market_sentiment: MarketAgent result
                - risk_assessment: RiskAgent result
                - quality_analysis: QualityAgent result (optional)
                - current_holding: bool (whether currently held)
                - current_shares: int (shares held if applicable)
            context: Optional additional context

        Returns:
            ReasoningDecision with action, reasoning, and details
        """
        self.logger.info(f"Synthesizing decision for {ticker}")

        # Build prompt for reasoning model
        prompt = self._build_reasoning_prompt(ticker, agent_outputs, context)

        # Prepare payload for text generation
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 512,
                "temperature": self.model_config.temperature,
                "top_k": self.model_config.top_k,
                "return_full_text": False
            }
        }

        # Make API call
        response = self._make_api_call(payload)

        if response is None:
            self.logger.error("API call failed, returning HOLD with low confidence")
            return self._create_fallback_decision(ticker, agent_outputs)

        # Parse reasoning output
        decision = self._parse_reasoning_output(ticker, response, agent_outputs)

        self.logger.info(f"Decision for {ticker}: {decision.action} (confidence: {decision.confidence:.1%})")

        return decision

    def _build_reasoning_prompt(
        self,
        ticker: str,
        agent_outputs: Dict[str, Any],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build structured prompt for reasoning model

        Args:
            ticker: Stock ticker symbol
            agent_outputs: All agent outputs
            context: Additional context

        Returns:
            Formatted prompt string
        """
        # Extract agent outputs
        news_sentiment = agent_outputs.get('news_sentiment', {})
        market_sentiment = agent_outputs.get('market_sentiment', {})
        risk_assessment = agent_outputs.get('risk_assessment', {})
        quality_analysis = agent_outputs.get('quality_analysis', {})
        current_holding = agent_outputs.get('current_holding', False)
        current_shares = agent_outputs.get('current_shares', 0)

        prompt = f"""You are an expert portfolio manager making a trading decision for {ticker}.

CURRENT POSITION:
- Holding: {'YES (' + str(current_shares) + ' shares)' if current_holding else 'NO'}

AGENT ANALYSIS:

1. NEWS SENTIMENT:
- Sentiment: {news_sentiment.get('sentiment', 'N/A')}
- Confidence: {news_sentiment.get('confidence', 0):.1%}
- Key Points: {news_sentiment.get('reasoning', 'N/A')}

2. MARKET SENTIMENT:
- Outlook: {market_sentiment.get('sentiment', 'N/A')}
- Confidence: {market_sentiment.get('confidence', 0):.1%}
- Analysis: {market_sentiment.get('reasoning', 'N/A')}

3. RISK ASSESSMENT:
- Risk Level: {risk_assessment.get('label', 'N/A')}
- Confidence: {risk_assessment.get('confidence', 0):.1%}
- Concerns: {risk_assessment.get('reasoning', 'N/A')}

4. QUALITY ANALYSIS:
- Quality Score: {quality_analysis.get('composite_score', 'N/A')}/100
- Tier: {quality_analysis.get('tier', 'N/A')}
- Red Flags: {quality_analysis.get('red_flags_count', 0)}
- Investment Rating: {quality_analysis.get('investment_rating', 'N/A')}

DECISION FRAMEWORK:

HOLD if:
- Quality score >70
- No major red flags (<3)
- News neutral or positive
- No better alternative identified

SELL if:
- Quality score <60, OR
- Red flags >3, OR
- Major negative catalyst in news, OR
- Better alternative exists (>15 quality points higher)

BUY if (for alternatives):
- Quality score >85 (Elite), OR
- Quality score >70 AND 15+ points better than current holdings

Think step-by-step:
1. What is the overall quality of this company?
2. Is there positive or negative momentum (news + market)?
3. What are the key risks?
4. What is the best action: BUY, SELL, or HOLD?

Provide your reasoning in this exact format:

REASONING:
Step 1: [Quality assessment]
Step 2: [Momentum assessment]
Step 3: [Risk assessment]
Step 4: [Final decision logic]

DECISION: [BUY/SELL/HOLD]
CONFIDENCE: [0-100]%
KEY_FACTOR: [Single most important factor]
"""

        return prompt

    def _parse_reasoning_output(
        self,
        ticker: str,
        response: Any,
        agent_outputs: Dict[str, Any]
    ) -> ReasoningDecision:
        """
        Parse reasoning model output into structured decision

        Args:
            ticker: Stock ticker
            response: Raw API response
            agent_outputs: Original agent outputs for fallback

        Returns:
            ReasoningDecision object
        """
        try:
            # Extract generated text
            if isinstance(response, list) and len(response) > 0:
                generated_text = response[0].get('generated_text', '')
            elif isinstance(response, dict):
                generated_text = response.get('generated_text', '')
            else:
                generated_text = str(response)

            # Parse reasoning steps
            reasoning_steps = []
            if "Step 1:" in generated_text:
                for i in range(1, 5):
                    step_marker = f"Step {i}:"
                    if step_marker in generated_text:
                        # Extract step text
                        start = generated_text.find(step_marker)
                        end = generated_text.find(f"Step {i+1}:", start) if i < 4 else generated_text.find("DECISION:", start)
                        if end == -1:
                            end = len(generated_text)
                        step_text = generated_text[start:end].strip()
                        reasoning_steps.append(step_text)

            # Parse decision
            action = "HOLD"  # Default
            if "DECISION:" in generated_text:
                decision_line = generated_text.split("DECISION:")[1].split("\n")[0].strip().upper()
                if "BUY" in decision_line:
                    action = "BUY"
                elif "SELL" in decision_line:
                    action = "SELL"
                elif "HOLD" in decision_line:
                    action = "HOLD"

            # Parse confidence
            confidence = 0.5  # Default
            if "CONFIDENCE:" in generated_text:
                confidence_line = generated_text.split("CONFIDENCE:")[1].split("\n")[0].strip()
                # Extract percentage
                try:
                    confidence_str = ''.join(filter(str.isdigit, confidence_line))
                    confidence = int(confidence_str) / 100.0
                except ValueError:
                    confidence = 0.5

            # Parse key factor
            key_factor = "Multiple factors"
            if "KEY_FACTOR:" in generated_text:
                key_factor = generated_text.split("KEY_FACTOR:")[1].split("\n")[0].strip()

            # Build key factors dict
            key_factors = {
                'quality_score': agent_outputs.get('quality_analysis', {}).get('composite_score'),
                'news_sentiment': agent_outputs.get('news_sentiment', {}).get('sentiment'),
                'market_sentiment': agent_outputs.get('market_sentiment', {}).get('sentiment'),
                'risk_level': agent_outputs.get('risk_assessment', {}).get('label'),
                'key_factor': key_factor
            }

            return ReasoningDecision(
                ticker=ticker,
                action=action,
                confidence=confidence,
                reasoning_steps=reasoning_steps if reasoning_steps else ["Automated decision based on agent consensus"],
                key_factors=key_factors
            )

        except Exception as e:
            self.logger.error(f"Failed to parse reasoning output: {e}")
            return self._create_fallback_decision(ticker, agent_outputs)

    def _create_fallback_decision(
        self,
        ticker: str,
        agent_outputs: Dict[str, Any]
    ) -> ReasoningDecision:
        """
        Create fallback decision using simple rule-based logic

        Args:
            ticker: Stock ticker
            agent_outputs: All agent outputs

        Returns:
            ReasoningDecision with rule-based decision
        """
        quality_score = agent_outputs.get('quality_analysis', {}).get('composite_score', 50)
        red_flags = agent_outputs.get('quality_analysis', {}).get('red_flags_count', 0)
        news_sentiment = agent_outputs.get('news_sentiment', {}).get('sentiment', 'neutral')
        current_holding = agent_outputs.get('current_holding', False)

        # Simple rule-based logic
        action = "HOLD"
        reasoning = []

        if quality_score < 60:
            action = "SELL"
            reasoning.append(f"Quality score {quality_score:.1f} below threshold (60)")
        elif red_flags > 3:
            action = "SELL"
            reasoning.append(f"Too many red flags ({red_flags})")
        elif quality_score >= 85 and not current_holding:
            action = "BUY"
            reasoning.append(f"Elite quality score {quality_score:.1f}")
        elif news_sentiment == 'negative' and quality_score < 70:
            action = "SELL"
            reasoning.append("Negative news with moderate quality")
        else:
            action = "HOLD"
            reasoning.append(f"Quality {quality_score:.1f}, news {news_sentiment}, maintaining position")

        return ReasoningDecision(
            ticker=ticker,
            action=action,
            confidence=0.6,  # Lower confidence for fallback
            reasoning_steps=reasoning,
            key_factors={
                'quality_score': quality_score,
                'red_flags': red_flags,
                'news_sentiment': news_sentiment,
                'key_factor': 'Fallback rule-based decision'
            }
        )

    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Compatibility method for BaseAgent interface

        Args:
            text: Not used (reasoning agent uses structured inputs)
            context: Must contain 'ticker' and 'agent_outputs'

        Returns:
            AgentResult with decision
        """
        if not context or 'ticker' not in context or 'agent_outputs' not in context:
            raise ValueError("ReasoningAgent requires context with 'ticker' and 'agent_outputs'")

        ticker = context['ticker']
        agent_outputs = context['agent_outputs']

        # Synthesize decision
        decision = self.synthesize_decision(ticker, agent_outputs, context)

        # Convert to AgentResult for compatibility
        return AgentResult(
            agent_name="ReasoningAgent",
            sentiment=decision.action.lower(),  # BUY -> buy, SELL -> sell, HOLD -> hold
            confidence=decision.confidence,
            score=decision.confidence * 100,
            label=decision.action,
            reasoning="\n".join(decision.reasoning_steps),
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response={'decision': decision.__dict__}
        )


# Example usage
if __name__ == "__main__":
    # Initialize reasoning agent
    agent = ReasoningAgent()

    # Example agent outputs
    test_outputs = {
        'news_sentiment': {
            'sentiment': 'positive',
            'confidence': 0.78,
            'reasoning': 'Strong earnings beat announced'
        },
        'market_sentiment': {
            'sentiment': 'bullish',
            'confidence': 0.65,
            'reasoning': 'Tech sector showing strength'
        },
        'risk_assessment': {
            'label': 'medium',
            'confidence': 0.70,
            'reasoning': 'Some valuation concerns but fundamentals solid'
        },
        'quality_analysis': {
            'composite_score': 82.5,
            'tier': 'Strong',
            'red_flags_count': 1,
            'investment_rating': 'BUY'
        },
        'current_holding': False,
        'current_shares': 0
    }

    # Synthesize decision
    decision = agent.synthesize_decision("NVDA", test_outputs)

    print("\n" + "="*60)
    print("REASONING AGENT EXAMPLE")
    print("="*60)
    print(f"Ticker: {decision.ticker}")
    print(f"Action: {decision.action}")
    print(f"Confidence: {decision.confidence:.1%}")
    print(f"\nReasoning Steps:")
    for step in decision.reasoning_steps:
        print(f"  {step}")
    print(f"\nKey Factors: {decision.key_factors}")
    print("="*60 + "\n")
