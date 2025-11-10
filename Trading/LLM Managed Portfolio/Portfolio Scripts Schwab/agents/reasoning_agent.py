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
            agent_outputs: All agent outputs (includes tier-specific data)
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

        # Extract tier-specific data
        market_cap_tier = agent_outputs.get('market_cap_tier', 'Unknown')
        roe_persistence_years = agent_outputs.get('roe_persistence_years')
        roe_trend_quarters = agent_outputs.get('roe_trend_quarters')
        incremental_roce = agent_outputs.get('incremental_roce')
        strict_filters_passed = agent_outputs.get('strict_filters_passed')
        thematic_score = agent_outputs.get('thematic_score')

        # Build tier-specific requirements section
        tier_requirements = ""
        if market_cap_tier == "LARGE_CAP":
            roe_met = "✓" if roe_persistence_years and roe_persistence_years >= 5 else "✗"
            tier_requirements = f"""
TIER CLASSIFICATION: Large Cap (65-70% of portfolio)
- ROE Persistence: {roe_persistence_years if roe_persistence_years else 'N/A'} years {roe_met} (requires 5+)
- Quality Threshold: ≥75
- Position Range: 8-15%
- Stop-Loss: -15%, Profit Target: +30%
"""
        elif market_cap_tier == "MID_CAP":
            roe_met = "✓" if roe_persistence_years and 2 <= roe_persistence_years <= 3 else "✗"
            roce_met = "✓" if incremental_roce and incremental_roce >= 5.0 else "✗"
            tier_requirements = f"""
TIER CLASSIFICATION: Mid Cap (15-20% of portfolio)
- ROE Persistence: {roe_persistence_years if roe_persistence_years else 'N/A'} years {roe_met} (requires 2-3)
- Incremental ROCE: {f"{incremental_roce:.1f}%" if incremental_roce else "N/A"} {roce_met} (requires +5%)
- Quality Threshold: ≥70
- Position Range: 5-10%
- Stop-Loss: -20%, Profit Target: +40%
"""
        elif market_cap_tier == "SMALL_CAP":
            trend_met = "✓" if roe_trend_quarters and 6 <= roe_trend_quarters <= 8 else "✗"
            filters_met = "✓" if strict_filters_passed else "✗"
            tier_requirements = f"""
TIER CLASSIFICATION: Small Cap (10-15% of portfolio)
- ROE Trend: {roe_trend_quarters if roe_trend_quarters else 'N/A'} quarters {trend_met} (requires 6-8)
- Strict Filters (FCF+, D/E<1.0, GP>30%): {filters_met}
- Quality Threshold: ≥65
- Position Range: 2-4%
- Stop-Loss: -25%, Profit Target: +50%
"""
        elif thematic_score is not None:
            tier_requirements = f"""
TIER CLASSIFICATION: Thematic (5-10% of portfolio)
- Thematic Score: {thematic_score:.1f}/40 (requires ≥28)
- Position Range: 1.5-2.5%
- Stop-Loss: -30%, Profit Target: +60%
"""
        else:
            tier_requirements = f"""
TIER CLASSIFICATION: {market_cap_tier}
- Tier-specific requirements not available
"""

        prompt = f"""You are an expert portfolio manager making a trading decision for {ticker} using the 4-tier market cap framework.

CURRENT POSITION:
- Holding: {'YES (' + str(current_shares) + ' shares)' if current_holding else 'NO'}
{tier_requirements}
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

DECISION FRAMEWORK (4-Tier Market Cap Framework):

TIER MISMATCH CHECK (Always check first):
- Large cap WITHOUT 5+ years ROE >15%: SELL (tier mismatch)
- Mid cap WITHOUT 2-3 years ROE >15% OR incremental ROCE +5%: SELL
- Small cap WITHOUT 6-8 qtrs ROE trend OR failing strict filters: SELL
- Thematic WITH score <28: SELL

SELL if (in priority order):
1. Tier mismatch detected (see above), OR
2. Red flags >3, OR
3. Quality below tier threshold (Large ≥75, Mid ≥70, Small ≥65), OR
4. Major negative catalyst in news AND borderline quality, OR
5. Better alternative exists within same tier

HOLD if:
- Meets tier requirements
- Quality score above tier threshold
- No major red flags (<3)
- News neutral or positive
- No better alternative identified

BUY if (for new positions):
- Large cap: Quality ≥75 AND ROE 5+ years, OR
- Mid cap: Quality ≥70 AND ROE 2-3 years AND ROCE +5%, OR
- Small cap: Quality ≥65 AND ROE trend 6-8 qtrs AND passes strict filters, OR
- Thematic: Score ≥28 (preferably ≥35 for leaders)

Think step-by-step:
1. Does this holding meet its tier requirements? (Check tier mismatch first!)
2. What is the overall quality and ROE persistence?
3. Is there positive or negative momentum (news + market)?
4. What are the key risks?
5. What is the best action: BUY, SELL, or HOLD?

Provide your reasoning in this exact format:

REASONING:
Step 1: [Tier requirement check - does it meet/fail?]
Step 2: [Quality and ROE persistence assessment]
Step 3: [Momentum assessment (news + market)]
Step 4: [Risk assessment]
Step 5: [Final decision logic]

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
        thematic_score: Optional[float],
        market_cap_tier: Optional[str] = None,
        roe_persistence_years: Optional[int] = None,
        roe_trend_quarters: Optional[int] = None,
        incremental_roce: Optional[float] = None,
        strict_filters_passed: Optional[bool] = None
    ) -> tuple:
        """
        Calculate position type, target %, stop-loss, profit target

        Position sizing follows 4-tier market cap framework (quality_investing_thresholds_research.md):

        Large Cap Holdings (65-70% of portfolio):
        - Requires: 5+ years ROE >15%, quality ≥75
        - Position: 8-15% (midpoint 11.5%), -15% stop, +30% target

        Mid Cap Holdings (15-20% of portfolio):
        - Requires: 2-3 years ROE >15%, incremental ROCE +5%, quality ≥70
        - Position: 5-10% (midpoint 7.5%), -20% stop, +40% target

        Small Cap Holdings (10-15% of portfolio):
        - Requires: 6-8 quarters positive ROE trend, passes strict filters (FCF+, D/E<1.0, GP>30%), quality ≥65
        - Position: 2-4% (midpoint 3%), -25% stop, +50% target

        Thematic Holdings (5-10% of portfolio):
        - Score 35-40: 1.5-2.5% position (midpoint 2%), -30% stop, +60% target (Leader)
        - Score 30-34: 1.5-2% position (midpoint 1.75%), -30% stop, +60% target (Strong Contender)
        - Score 28-29: 1.5% position, -30% stop, +60% target (Contender)
        - Score <28: 0% - EXIT

        Args:
            quality_score: Quality score (0-100 scale)
            thematic_score: Thematic score (0-40 scale)
            market_cap_tier: "LARGE_CAP", "MID_CAP", "SMALL_CAP", or "THEMATIC"
            roe_persistence_years: Years of ROE >15% (for large/mid cap)
            roe_trend_quarters: Quarters of positive ROE trend (for small cap)
            incremental_roce: Incremental ROCE improvement % (for mid cap)
            strict_filters_passed: Whether passes strict quality filters (for small cap)

        Returns:
            Tuple of (position_type, target_pct, stop_loss_pct, profit_target_pct)
        """
        # Priority 1: Thematic holdings (regardless of market cap)
        if thematic_score is not None and thematic_score >= 28:
            position_type = "THEMATIC"

            if thematic_score >= 35:
                # Leader: 1.5-2.5%
                target_pct = 2.0  # Midpoint
                stop_loss = -30.0
                profit_target = 60.0
            elif thematic_score >= 30:
                # Strong Contender: 1.5-2%
                target_pct = 1.75  # Midpoint
                stop_loss = -30.0
                profit_target = 60.0
            else:  # 28-29
                # Contender: 1.5%
                target_pct = 1.5
                stop_loss = -30.0
                profit_target = 60.0

            return position_type, target_pct, stop_loss, profit_target

        # Priority 2: Market cap tier-based quality holdings
        if market_cap_tier == "LARGE_CAP":
            # Large cap: Requires 5+ years ROE >15% AND quality ≥75
            if quality_score is not None and quality_score >= 75:
                if roe_persistence_years is not None and roe_persistence_years >= 5:
                    target_pct = 11.5  # Midpoint of 8-15%
                    stop_loss = -15.0
                    profit_target = 30.0
                    position_type = "LARGE_CAP"
                    return position_type, target_pct, stop_loss, profit_target
            # Doesn't meet large cap requirements → EXIT
            position_type = "NONE"
            target_pct = 0.0
            stop_loss = 0.0
            profit_target = 0.0
            return position_type, target_pct, stop_loss, profit_target

        elif market_cap_tier == "MID_CAP":
            # Mid cap: Requires 2-3 years ROE >15%, incremental ROCE +5%, quality ≥70
            if quality_score is not None and quality_score >= 70:
                roe_valid = roe_persistence_years is not None and 2 <= roe_persistence_years <= 3
                roce_valid = incremental_roce is not None and incremental_roce >= 5.0
                if roe_valid and roce_valid:
                    target_pct = 7.5  # Midpoint of 5-10%
                    stop_loss = -20.0
                    profit_target = 40.0
                    position_type = "MID_CAP"
                    return position_type, target_pct, stop_loss, profit_target
            # Doesn't meet mid cap requirements → EXIT
            position_type = "NONE"
            target_pct = 0.0
            stop_loss = 0.0
            profit_target = 0.0
            return position_type, target_pct, stop_loss, profit_target

        elif market_cap_tier == "SMALL_CAP":
            # Small cap: Requires 6-8 quarters positive ROE trend, passes strict filters, quality ≥65
            if quality_score is not None and quality_score >= 65:
                trend_valid = roe_trend_quarters is not None and 6 <= roe_trend_quarters <= 8
                filters_valid = strict_filters_passed is True
                if trend_valid and filters_valid:
                    target_pct = 3.0  # Midpoint of 2-4%
                    stop_loss = -25.0
                    profit_target = 50.0
                    position_type = "SMALL_CAP"
                    return position_type, target_pct, stop_loss, profit_target
            # Doesn't meet small cap requirements → EXIT
            position_type = "NONE"
            target_pct = 0.0
            stop_loss = 0.0
            profit_target = 0.0
            return position_type, target_pct, stop_loss, profit_target

        # No tier specified - fall back to legacy quality-only logic for backward compatibility
        if quality_score is not None and quality_score >= 70:
            position_type = "QUALITY"

            if quality_score >= 90:
                # Elite: 10-20%
                target_pct = 15.0  # Midpoint
                stop_loss = -15.0
                profit_target = 40.0
            elif quality_score >= 80:
                # Strong: 7-12%
                target_pct = 9.5  # Midpoint
                stop_loss = -15.0
                profit_target = 40.0
            else:  # 70-79
                # Moderate: 5-8%
                target_pct = 6.5  # Midpoint
                stop_loss = -20.0
                profit_target = 40.0

            return position_type, target_pct, stop_loss, profit_target

        # Below threshold or no valid data → EXIT
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

        Decision thresholds from 4-tier market cap framework (quality_investing_thresholds_research.md):

        Large Cap Holdings (65-70% of portfolio):
        - Requires: 5+ years ROE >15%, quality ≥75
        - BUY if meets requirements, SELL if fails

        Mid Cap Holdings (15-20% of portfolio):
        - Requires: 2-3 years ROE >15%, incremental ROCE +5%, quality ≥70
        - BUY if meets requirements, SELL if fails

        Small Cap Holdings (10-15% of portfolio):
        - Requires: 6-8 quarters positive ROE trend, passes strict filters, quality ≥65
        - BUY if meets requirements, SELL if fails

        Thematic Holdings (5-10% of portfolio):
        - Score <28: EXIT
        - Score 28-29: HOLD with 1.5% position
        - Score 30-34: BUY with 1.75% position
        - Score 35-40: STRONG BUY with 2% position

        Tier Mismatch Detection:
        - Large cap without 5+ years ROE >15%: EXIT or downgrade
        - Small cap failing strict filters: EXIT

        Args:
            ticker: Stock ticker
            agent_outputs: All agent outputs (includes market_cap_tier, roe_persistence, etc.)

        Returns:
            ReasoningDecision with rule-based decision
        """
        # Extract data from agent outputs
        quality_score = agent_outputs.get('quality_analysis', {}).get('composite_score', 50)
        thematic_score = agent_outputs.get('thematic_score')
        red_flags = agent_outputs.get('quality_analysis', {}).get('red_flags_count', 0)
        news_sentiment = agent_outputs.get('news_sentiment', {}).get('sentiment', 'neutral')
        current_holding = agent_outputs.get('current_holding', False)

        # Extract tier-specific data
        market_cap_tier = agent_outputs.get('market_cap_tier')
        roe_persistence_years = agent_outputs.get('roe_persistence_years')
        roe_trend_quarters = agent_outputs.get('roe_trend_quarters')
        incremental_roce = agent_outputs.get('incremental_roce')
        strict_filters_passed = agent_outputs.get('strict_filters_passed')

        # Calculate position sizing with tier-specific logic
        position_type, target_pct, stop_loss, profit_target = self._calculate_position_params(
            quality_score=quality_score,
            thematic_score=thematic_score,
            market_cap_tier=market_cap_tier,
            roe_persistence_years=roe_persistence_years,
            roe_trend_quarters=roe_trend_quarters,
            incremental_roce=incremental_roce,
            strict_filters_passed=strict_filters_passed
        )

        # Simple rule-based logic following 4-tier framework
        action = "HOLD"
        reasoning = []

        # Priority 1: Check thematic score (if applicable)
        if thematic_score is not None and thematic_score < 28:
            action = "SELL"
            reasoning.append(f"Thematic score {thematic_score:.1f}/40 below threshold (28)")
            reasoning.append("EXIT opportunistic position (4-tier framework)")
            reasoning.append("Free capital for higher-conviction thematic opportunities")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0

        # Priority 2: Tier mismatch detection
        elif market_cap_tier == "LARGE_CAP" and (roe_persistence_years is None or roe_persistence_years < 5):
            action = "SELL"
            years = roe_persistence_years if roe_persistence_years is not None else 0
            reasoning.append(f"Large cap tier mismatch: Only {years} years ROE >15% (requires 5+)")
            reasoning.append("EXIT or downgrade to lower tier (4-tier framework)")
            reasoning.append("Insufficient ROE persistence for large cap allocation")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0

        elif market_cap_tier == "MID_CAP" and (quality_score < 70 or roe_persistence_years is None or roe_persistence_years < 2):
            action = "SELL"
            reasoning.append(f"Mid cap tier mismatch: Quality {quality_score} or ROE {roe_persistence_years} years")
            reasoning.append("EXIT - fails mid cap requirements (quality ≥70, ROE 2-3 years)")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0

        elif market_cap_tier == "SMALL_CAP" and (strict_filters_passed is False or roe_trend_quarters is None or roe_trend_quarters < 6):
            action = "SELL"
            reasoning.append(f"Small cap tier mismatch: Fails strict filters or ROE trend {roe_trend_quarters} qtrs")
            reasoning.append("EXIT - fails small cap requirements (FCF+, D/E<1.0, GP>30%, 6-8 qtrs ROE trend)")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0

        # Priority 3: Check red flags
        elif red_flags > 3:
            action = "SELL"
            reasoning.append(f"Too many red flags ({red_flags}) - quality concerns")
            reasoning.append("EXIT regardless of score (4-tier risk management)")
            # Override position params for SELL
            target_pct = 0.0
            position_type = "NONE"
            stop_loss = 0.0
            profit_target = 0.0

        # Priority 4: Tier-specific BUY opportunities
        elif market_cap_tier == "LARGE_CAP" and quality_score >= 75 and roe_persistence_years >= 5 and not current_holding:
            action = "BUY"
            reasoning.append(f"Large cap opportunity: Quality {quality_score}, ROE {roe_persistence_years} years")
            reasoning.append(f"Target position: {target_pct:.1f}% (8-15% range)")
            reasoning.append("Meets large cap requirements (5+ years ROE >15%, quality ≥75)")

        elif market_cap_tier == "MID_CAP" and quality_score >= 70 and roe_persistence_years >= 2 and not current_holding:
            action = "BUY"
            reasoning.append(f"Mid cap opportunity: Quality {quality_score}, ROE {roe_persistence_years} years")
            reasoning.append(f"Target position: {target_pct:.1f}% (5-10% range)")
            reasoning.append("Meets mid cap requirements (2-3 years ROE >15%, quality ≥70)")

        elif market_cap_tier == "SMALL_CAP" and quality_score >= 65 and strict_filters_passed and not current_holding:
            action = "BUY"
            reasoning.append(f"Small cap opportunity: Quality {quality_score}, strict filters passed")
            reasoning.append(f"Target position: {target_pct:.1f}% (2-4% range)")
            reasoning.append("Meets small cap requirements (FCF+, D/E<1.0, GP>30%, ROE trend 6-8 qtrs)")

        # Priority 5: Negative news with borderline quality
        elif news_sentiment == 'negative':
            if (market_cap_tier == "LARGE_CAP" and quality_score < 80) or \
               (market_cap_tier == "MID_CAP" and quality_score < 75) or \
               (market_cap_tier == "SMALL_CAP" and quality_score < 70):
                action = "SELL"
                reasoning.append(f"Negative news with marginal quality for {market_cap_tier}")
                reasoning.append("EXIT - risk reduction for tier (4-tier framework)")
                # Override position params for SELL
                target_pct = 0.0
                position_type = "NONE"
                stop_loss = 0.0
                profit_target = 0.0

        # Default HOLD
        if action == "HOLD":
            tier_label = market_cap_tier if market_cap_tier else "Unknown"
            reasoning.append(f"Quality {quality_score} for {tier_label}, news {news_sentiment}")
            if target_pct > 0:
                reasoning.append(f"Maintain position at {target_pct:.1f}% ({position_type})")
            else:
                reasoning.append("Position sizing indicates EXIT - see tier requirements")

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
                'market_cap_tier': market_cap_tier,
                'roe_persistence_years': roe_persistence_years,
                'red_flags': red_flags,
                'news_sentiment': news_sentiment,
                'key_factor': 'Fallback rule-based decision (4-tier framework)'
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
