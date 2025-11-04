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

    # Position sizing (from portfolio_constructor.py logic)
    target_position_pct: Optional[float] = None  # e.g., 15.0 for 15%
    position_type: Optional[str] = None  # QUALITY or THEMATIC
    stop_loss_pct: Optional[float] = None  # e.g., -15.0
    profit_target_pct: Optional[float] = None  # e.g., +40.0


class ReasoningAgent(BaseAgent):
    """
    Synthesizes all agent outputs to make final trading decisions

    Uses DeepSeek-R1-Distill-Qwen-14B for reasoning and decision synthesis.

    Decision Logic (STEPS Framework - PM_README_V3.md):
    - HOLD: Default when quality ≥70, no major red flags, neutral/positive news
    - SELL: Quality <70 (STEPS threshold) OR thematic <28 OR >3 red flags OR major negative catalyst
    - BUY: Alternative quality ≥85 (Elite) OR quality ≥70 and 15+ points better than current holding
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

DECISION FRAMEWORK (STEPS Methodology):

HOLD if:
- Quality score ≥70 (STEPS threshold for core holdings)
- No major red flags (<3)
- News neutral or positive
- No better alternative identified

SELL if:
- Quality score <70 (STEPS: exit from core holdings), OR
- Thematic score <28 (STEPS: exit opportunistic positions), OR
- Red flags >3, OR
- Major negative catalyst in news, OR
- Better alternative exists (>15 quality points higher)

BUY if (for alternatives):
- Quality score ≥85 (Elite tier - STEPS: 10-20% position), OR
- Quality score ≥70 AND 15+ points better than current holdings

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

            # Calculate position sizing
            quality_score = agent_outputs.get('quality_analysis', {}).get('composite_score')
            thematic_score = agent_outputs.get('thematic_score')
            position_type, target_pct, stop_loss, profit_target = self._calculate_position_params(
                quality_score, thematic_score
            )

            # Build key factors dict
            key_factors = {
                'quality_score': quality_score,
                'thematic_score': thematic_score,
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
                key_factors=key_factors,
                target_position_pct=target_pct,
                position_type=position_type,
                stop_loss_pct=stop_loss,
                profit_target_pct=profit_target
            )

        except Exception as e:
            self.logger.error(f"Failed to parse reasoning output: {e}")
            return self._create_fallback_decision(ticker, agent_outputs)

    def _calculate_position_params(
        self,
        quality_score: Optional[float],
        thematic_score: Optional[float]
    ) -> tuple:
        """
        Calculate position type, target %, stop-loss, profit target

        Position sizing follows PM_README_V3.md (80/20 Framework):

        Quality Holdings (Core 80%):
        - Score ≥9.0: 10-20% position, -15% stop, +40% target (Elite)
        - Score 8.0-8.99: 7-12% position, -15% stop, +40% target (Strong)
        - Score 7.0-7.99: 5-8% position, -20% stop, +40% target (Moderate)
        - Score <7.0: 0% - EXIT

        Thematic Holdings (Opportunistic 20%):
        - Score 35-40: 5-7% position, -27.5% stop, +50% target (Leader)
        - Score 30-34: 3-5% position, -27.5% stop, +50% target (Strong Contender)
        - Score 28-29: 2-3% position, -25% stop, +45% target (Contender)
        - Score <28: 0% - EXIT

        Args:
            quality_score: Quality score (0-100 scale)
            thematic_score: Thematic score (0-40 scale)

        Returns:
            Tuple of (position_type, target_pct, stop_loss_pct, profit_target_pct)
        """
        # Convert quality score from 0-100 scale to 0-10 scale
        quality_score_10 = quality_score / 10.0 if quality_score is not None else None

        # Quality holdings (score ≥ 7)
        if quality_score_10 is not None and quality_score_10 >= 7.0:
            position_type = "QUALITY"

            if quality_score_10 >= 9.0:
                # Elite: 10-20%
                target_pct = 15.0  # Midpoint
                stop_loss = -15.0
                profit_target = 40.0
            elif quality_score_10 >= 8.0:
                # Strong: 7-12%
                target_pct = 9.5  # Midpoint
                stop_loss = -15.0
                profit_target = 40.0
            else:  # 7.0-7.99
                # Moderate: 5-8%
                target_pct = 6.5  # Midpoint
                stop_loss = -20.0
                profit_target = 40.0

        # Thematic holdings (score ≥ 28)
        elif thematic_score is not None and thematic_score >= 28:
            position_type = "THEMATIC"

            if thematic_score >= 35:
                # Leader: 5-7%
                target_pct = 6.0  # Midpoint
                stop_loss = -27.5
                profit_target = 50.0
            elif thematic_score >= 30:
                # Strong Contender: 3-5%
                target_pct = 4.0  # Midpoint
                stop_loss = -27.5
                profit_target = 50.0
            else:  # 28-29
                # Contender: 2-3%
                target_pct = 2.5  # Midpoint
                stop_loss = -25.0
                profit_target = 45.0

        else:
            # No score or below thresholds → EXIT
            position_type = "NONE"
            target_pct = 0.0
            stop_loss = 0.0
            profit_target = 0.0

        return position_type, target_pct, stop_loss, profit_target

    def _create_fallback_decision(
        self,
        ticker: str,
        agent_outputs: Dict[str, Any]
    ) -> ReasoningDecision:
        """
        Create fallback decision using simple rule-based logic when LLM reasoning fails

        Decision thresholds from PM_README_V3.md (80/20 Framework):

        Quality Holdings (Core 80%):
        - Score <7.0 (70 on 0-100 scale): EXIT - below minimum threshold (line 594)
        - Score 7.0-7.9 (70-79): HOLD with 5-8% position (line 66)
        - Score 8.0-8.9 (80-89): BUY/SCALE with 7-12% position (line 65)
        - Score ≥9.0 (90-100): STRONG BUY with 10-20% position (line 64)

        Thematic Holdings (Opportunistic 20%):
        - Score <28: EXIT - below minimum threshold (line 117)
        - Score 28-29: HOLD with 2-3% position (line 122)
        - Score 30-34: BUY with 3-5% position (line 121)
        - Score 35-40: STRONG BUY with 5-7% position (line 120)

        Additional Exit Rules:
        - Red flags >3: EXIT regardless of score
        - Negative news + quality <70: EXIT
        - Better alternative exists (>15 points quality): SWAP/EXIT

        Args:
            ticker: Stock ticker
            agent_outputs: All agent outputs

        Returns:
            ReasoningDecision with rule-based decision
        """
        quality_score = agent_outputs.get('quality_analysis', {}).get('composite_score', 50)
        thematic_score = agent_outputs.get('thematic_score')
        red_flags = agent_outputs.get('quality_analysis', {}).get('red_flags_count', 0)
        news_sentiment = agent_outputs.get('news_sentiment', {}).get('sentiment', 'neutral')
        current_holding = agent_outputs.get('current_holding', False)

        # Calculate position sizing
        position_type, target_pct, stop_loss, profit_target = self._calculate_position_params(
            quality_score, thematic_score
        )

        # Simple rule-based logic following STEPS methodology
        action = "HOLD"
        reasoning = []

        # Check thematic score first (if applicable)
        if thematic_score is not None and thematic_score < 28:
            action = "SELL"
            reasoning.append(f"Thematic score {thematic_score:.1f}/40 below STEPS threshold (28)")
            reasoning.append("EXIT opportunistic position (STEPS requirement)")
            reasoning.append("Free capital for higher-conviction thematic opportunities")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0
        # Check quality score
        elif quality_score < 70:  # STEPS threshold (7.0 on 10-point scale)
            action = "SELL"
            quality_10 = quality_score / 10.0
            reasoning.append(f"Quality score {quality_10:.1f}/10 below STEPS threshold (7.0)")
            reasoning.append("EXIT from core holdings (STEPS requirement)")
            reasoning.append("Free capital for higher quality opportunities")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0
        # Check red flags
        elif red_flags > 3:
            action = "SELL"
            reasoning.append(f"Too many red flags ({red_flags}) - quality concerns")
            reasoning.append("EXIT regardless of score (STEPS risk management)")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0
        # Elite quality opportunity
        elif quality_score >= 85 and not current_holding:
            action = "BUY"
            quality_10 = quality_score / 10.0
            reasoning.append(f"Quality score {quality_10:.1f}/10 (STEPS: Elite tier)")
            reasoning.append(f"Target position: {target_pct:.1f}% ({position_type})")
            reasoning.append(f"STEPS framework: 10-20% range for Elite quality")
        # Negative news with borderline quality
        elif news_sentiment == 'negative' and quality_score < 75:
            action = "SELL"
            reasoning.append("Negative news with marginal quality (STEPS: risk reduction)")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0
        # Default HOLD
        else:
            action = "HOLD"
            quality_10 = quality_score / 10.0
            reasoning.append(f"Quality {quality_10:.1f}/10 (STEPS: threshold met), news {news_sentiment}")
            if target_pct > 0:
                reasoning.append(f"Maintain position at {target_pct:.1f}% ({position_type})")

        # Add position sizing to reasoning for BUY/HOLD
        if action in ["BUY", "HOLD"] and target_pct > 0:
            reasoning.append(f"Stop-loss: {stop_loss}%, Profit target: {profit_target}%")

        return ReasoningDecision(
            ticker=ticker,
            action=action,
            confidence=0.6,  # Lower confidence for fallback
            reasoning_steps=reasoning,
            key_factors={
                'quality_score': quality_score,
                'thematic_score': thematic_score,
                'red_flags': red_flags,
                'news_sentiment': news_sentiment,
                'key_factor': 'Fallback rule-based decision'
            },
            target_position_pct=target_pct,
            position_type=position_type,
            stop_loss_pct=stop_loss,
            profit_target_pct=profit_target
        )

    def _interpret_results(self, response: Dict[str, Any], text: str, context: Optional[Dict[str, Any]]) -> AgentResult:
        """
        Interpret reasoning model response into AgentResult

        This method satisfies the BaseAgent abstract method requirement.
        For ReasoningAgent, we parse the response and convert to AgentResult.

        Args:
            response: Raw API response from reasoning model
            text: Original prompt text (not used)
            context: Must contain 'ticker' and 'agent_outputs'

        Returns:
            AgentResult with decision
        """
        if not context or 'ticker' not in context or 'agent_outputs' not in context:
            raise ValueError("ReasoningAgent requires context with 'ticker' and 'agent_outputs'")

        ticker = context['ticker']
        agent_outputs = context['agent_outputs']

        # Parse the response into a decision
        decision = self._parse_reasoning_output(ticker, response, agent_outputs)

        # Convert to AgentResult
        return AgentResult(
            agent_name="ReasoningAgent",
            sentiment=decision.action.lower(),
            confidence=decision.confidence,
            score=decision.confidence * 100,
            label=decision.action,
            reasoning="\n".join(decision.reasoning_steps),
            timestamp=datetime.now(),
            model_used=self.model_config.model_id,
            raw_response={'decision': decision.__dict__}
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
