"""
Test suite for Reasoning Agent
Tests position sizing, threshold logic, and decision synthesis
"""

import unittest
from unittest.mock import Mock, patch
from agents.reasoning_agent import ReasoningAgent, ReasoningDecision


class TestPositionSizing(unittest.TestCase):
    """Test position sizing calculations"""

    def setUp(self):
        self.agent = ReasoningAgent()

    def test_quality_score_9_elite(self):
        """Test position sizing for quality score 9.0 (Elite)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=90.0,  # 9.0 on 10-point scale
            thematic_score=None
        )

        self.assertEqual(position_type, "QUALITY")
        self.assertEqual(target_pct, 15.0)  # Midpoint of 10-20%
        self.assertEqual(stop_loss, -15.0)
        self.assertEqual(profit_target, 40.0)

    def test_quality_score_8_strong(self):
        """Test position sizing for quality score 8.0 (Strong)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=80.0,  # 8.0 on 10-point scale
            thematic_score=None
        )

        self.assertEqual(position_type, "QUALITY")
        self.assertEqual(target_pct, 9.5)  # Midpoint of 7-12%
        self.assertEqual(stop_loss, -15.0)
        self.assertEqual(profit_target, 40.0)

    def test_quality_score_7_moderate(self):
        """Test position sizing for quality score 7.0 (Moderate)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=70.0,  # 7.0 on 10-point scale
            thematic_score=None
        )

        self.assertEqual(position_type, "QUALITY")
        self.assertEqual(target_pct, 6.5)  # Midpoint of 5-8%
        self.assertEqual(stop_loss, -20.0)
        self.assertEqual(profit_target, 40.0)

    def test_quality_score_below_threshold(self):
        """Test EXIT for quality score below 7.0"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=65.0,  # 6.5 on 10-point scale
            thematic_score=None
        )

        self.assertEqual(position_type, "NONE")
        self.assertEqual(target_pct, 0.0)
        self.assertEqual(stop_loss, 0.0)
        self.assertEqual(profit_target, 0.0)

    def test_thematic_score_35_leader(self):
        """Test position sizing for thematic score 35 (Leader)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=35.0
        )

        self.assertEqual(position_type, "THEMATIC")
        self.assertEqual(target_pct, 6.0)  # Midpoint of 5-7%
        self.assertEqual(stop_loss, -27.5)
        self.assertEqual(profit_target, 50.0)

    def test_thematic_score_30_strong_contender(self):
        """Test position sizing for thematic score 30 (Strong Contender)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=32.0
        )

        self.assertEqual(position_type, "THEMATIC")
        self.assertEqual(target_pct, 4.0)  # Midpoint of 3-5%
        self.assertEqual(stop_loss, -27.5)
        self.assertEqual(profit_target, 50.0)

    def test_thematic_score_28_contender(self):
        """Test position sizing for thematic score 28 (Contender)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=28.0
        )

        self.assertEqual(position_type, "THEMATIC")
        self.assertEqual(target_pct, 2.5)  # Midpoint of 2-3%
        self.assertEqual(stop_loss, -25.0)
        self.assertEqual(profit_target, 45.0)

    def test_thematic_score_below_threshold(self):
        """Test EXIT for thematic score below 28"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=25.0
        )

        self.assertEqual(position_type, "NONE")
        self.assertEqual(target_pct, 0.0)
        self.assertEqual(stop_loss, 0.0)
        self.assertEqual(profit_target, 0.0)

    def test_no_scores_provided(self):
        """Test EXIT when no scores provided"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=None
        )

        self.assertEqual(position_type, "NONE")
        self.assertEqual(target_pct, 0.0)
        self.assertEqual(stop_loss, 0.0)
        self.assertEqual(profit_target, 0.0)

    def test_quality_takes_precedence(self):
        """Test that quality score takes precedence over thematic"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=80.0,
            thematic_score=35.0
        )

        # Should use quality parameters, not thematic
        self.assertEqual(position_type, "QUALITY")
        self.assertEqual(target_pct, 9.5)  # Quality midpoint
        self.assertEqual(stop_loss, -15.0)  # Quality stop-loss
        self.assertEqual(profit_target, 40.0)  # Quality target


class TestFallbackDecision(unittest.TestCase):
    """Test fallback decision logic"""

    def setUp(self):
        self.agent = ReasoningAgent()

    def test_sell_below_steps_threshold(self):
        """Test SELL decision for quality score below 70 (STEPS threshold)"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 65.0, 'red_flags_count': 1},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.ticker, "TEST")
        self.assertIn("STEPS threshold", decision.reasoning_steps[0])
        self.assertEqual(decision.target_position_pct, 0.0)
        self.assertEqual(decision.position_type, "NONE")

    def test_sell_too_many_red_flags(self):
        """Test SELL decision for >3 red flags"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 75.0, 'red_flags_count': 4},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "SELL")
        self.assertIn("red flags", decision.reasoning_steps[0].lower())

    def test_buy_elite_quality(self):
        """Test BUY decision for elite quality (>85)"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 90.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'positive'},
            'current_holding': False
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "BUY")
        self.assertIn("Elite", decision.reasoning_steps[0])
        self.assertEqual(decision.target_position_pct, 15.0)  # Elite position size
        self.assertEqual(decision.position_type, "QUALITY")
        self.assertEqual(decision.stop_loss_pct, -15.0)
        self.assertEqual(decision.profit_target_pct, 40.0)

    def test_hold_moderate_quality(self):
        """Test HOLD decision for moderate quality"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 75.0, 'red_flags_count': 1},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.target_position_pct, 6.5)  # Moderate position size
        self.assertEqual(decision.position_type, "QUALITY")

    def test_position_sizing_in_reasoning(self):
        """Test that position sizing appears in reasoning text"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 85.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'positive'},
            'current_holding': False
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        # Check that reasoning includes position sizing
        reasoning_text = " ".join(decision.reasoning_steps)
        self.assertIn("Target position", reasoning_text)
        self.assertIn("Stop-loss", reasoning_text)
        self.assertIn("Profit target", reasoning_text)

    def test_thematic_score_in_fallback(self):
        """Test thematic score handling in fallback"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 50.0, 'red_flags_count': 0},
            'thematic_score': 35.0,
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        # Quality below 70, should SELL
        self.assertEqual(decision.action, "SELL")

    def test_thematic_below_threshold_triggers_sell(self):
        """Test thematic score <28 triggers SELL even with acceptable quality"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 75.0, 'red_flags_count': 0},
            'thematic_score': 25.0,  # Below threshold
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "SELL")
        self.assertIn("Thematic score", decision.reasoning_steps[0])
        self.assertIn("STEPS", decision.reasoning_steps[0])
        self.assertIn("threshold", decision.reasoning_steps[0].lower())
        self.assertEqual(decision.target_position_pct, 0.0)
        self.assertEqual(decision.position_type, "NONE")


class TestParseReasoningOutput(unittest.TestCase):
    """Test parsing of reasoning model output"""

    def setUp(self):
        self.agent = ReasoningAgent()

    def test_parse_buy_decision(self):
        """Test parsing BUY decision from model output"""
        response = [{
            'generated_text': """
            REASONING:
            Step 1: Quality assessment - High quality company with score 85
            Step 2: Momentum assessment - Positive news and market sentiment
            Step 3: Risk assessment - Moderate risk, well managed
            Step 4: Final decision - BUY recommended given quality and momentum

            DECISION: BUY
            CONFIDENCE: 85%
            KEY_FACTOR: Strong quality metrics
            """
        }]

        agent_outputs = {
            'quality_analysis': {'composite_score': 85.0},
            'thematic_score': None
        }

        decision = self.agent._parse_reasoning_output("TEST", response, agent_outputs)

        self.assertEqual(decision.action, "BUY")
        self.assertEqual(decision.confidence, 0.85)
        self.assertEqual(len(decision.reasoning_steps), 4)
        self.assertEqual(decision.target_position_pct, 9.5)  # Score 8.5 → Strong quality
        self.assertEqual(decision.position_type, "QUALITY")

    def test_parse_sell_decision(self):
        """Test parsing SELL decision from model output"""
        response = [{
            'generated_text': """
            REASONING:
            Step 1: Quality below threshold
            Step 2: Negative momentum
            Step 3: High risk
            Step 4: SELL recommended

            DECISION: SELL
            CONFIDENCE: 90%
            KEY_FACTOR: Quality deterioration
            """
        }]

        agent_outputs = {
            'quality_analysis': {'composite_score': 60.0},
            'thematic_score': None
        }

        decision = self.agent._parse_reasoning_output("TEST", response, agent_outputs)

        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.confidence, 0.90)
        self.assertEqual(decision.target_position_pct, 0.0)  # Below threshold
        self.assertEqual(decision.position_type, "NONE")

    def test_parse_hold_decision(self):
        """Test parsing HOLD decision from model output"""
        response = [{
            'generated_text': """
            REASONING:
            Step 1: Moderate quality
            Step 2: Neutral sentiment
            Step 3: Acceptable risk
            Step 4: HOLD current position

            DECISION: HOLD
            CONFIDENCE: 70%
            KEY_FACTOR: Stable fundamentals
            """
        }]

        agent_outputs = {
            'quality_analysis': {'composite_score': 75.0},
            'thematic_score': None
        }

        decision = self.agent._parse_reasoning_output("TEST", response, agent_outputs)

        self.assertEqual(decision.action, "HOLD")
        self.assertEqual(decision.confidence, 0.70)
        self.assertEqual(decision.target_position_pct, 6.5)  # Moderate quality
        self.assertEqual(decision.position_type, "QUALITY")

    def test_parse_with_thematic_score(self):
        """Test parsing with thematic score"""
        response = [{
            'generated_text': """
            DECISION: BUY
            CONFIDENCE: 80%
            KEY_FACTOR: Strong thematic alignment
            """
        }]

        agent_outputs = {
            'quality_analysis': {'composite_score': 50.0},
            'thematic_score': 35.0
        }

        decision = self.agent._parse_reasoning_output("TEST", response, agent_outputs)

        self.assertEqual(decision.action, "BUY")
        # Quality below threshold but thematic above threshold
        self.assertEqual(decision.position_type, "THEMATIC")
        self.assertEqual(decision.target_position_pct, 6.0)  # Leader thematic
        self.assertEqual(decision.stop_loss_pct, -27.5)
        self.assertEqual(decision.profit_target_pct, 50.0)

    def test_parse_malformed_response(self):
        """Test parsing handles malformed response gracefully"""
        response = [{'generated_text': 'malformed output with no structure'}]

        agent_outputs = {
            'quality_analysis': {'composite_score': 75.0},
            'thematic_score': None
        }

        decision = self.agent._parse_reasoning_output("TEST", response, agent_outputs)

        # Should default to HOLD with moderate confidence
        self.assertEqual(decision.action, "HOLD")
        self.assertIsInstance(decision.confidence, float)
        self.assertGreater(decision.confidence, 0.0)


class TestSTEPSThresholds(unittest.TestCase):
    """Test STEPS framework threshold compliance"""

    def setUp(self):
        self.agent = ReasoningAgent()

    def test_quality_threshold_70_not_60(self):
        """Verify STEPS threshold is 70, not legacy 60"""
        # Quality score 65 (6.5 on 10-point) should SELL
        agent_outputs = {
            'quality_analysis': {'composite_score': 65.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "SELL")
        self.assertIn("STEPS", decision.reasoning_steps[0])

    def test_quality_71_should_hold(self):
        """Quality score 71 should HOLD (above STEPS threshold)"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 71.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "HOLD")
        self.assertGreater(decision.target_position_pct, 0.0)

    def test_thematic_threshold_28(self):
        """Verify thematic threshold is 28"""
        # Score 27 should EXIT
        position_type, target_pct, _, _ = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=27.0
        )

        self.assertEqual(position_type, "NONE")
        self.assertEqual(target_pct, 0.0)

        # Score 28 should hold position
        position_type, target_pct, _, _ = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=28.0
        )

        self.assertEqual(position_type, "THEMATIC")
        self.assertGreater(target_pct, 0.0)


class TestReasoningText(unittest.TestCase):
    """Test reasoning text includes position sizing information"""

    def setUp(self):
        self.agent = ReasoningAgent()

    def test_buy_includes_position_size(self):
        """BUY decisions should mention position size"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 90.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'positive'},
            'current_holding': False
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "BUY")

        reasoning_text = " ".join(decision.reasoning_steps)
        self.assertIn("Target position", reasoning_text)
        self.assertIn("15.0%", reasoning_text)  # Elite position size

    def test_steps_framework_references_in_reasoning(self):
        """Test that reasoning text includes STEPS framework references"""
        # Test SELL with quality below threshold
        agent_outputs_sell = {
            'quality_analysis': {'composite_score': 65.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision_sell = self.agent._create_fallback_decision("TEST", agent_outputs_sell)
        reasoning_text = " ".join(decision_sell.reasoning_steps)
        self.assertIn("STEPS", reasoning_text)

        # Test BUY with elite quality
        agent_outputs_buy = {
            'quality_analysis': {'composite_score': 90.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'positive'},
            'current_holding': False
        }

        decision_buy = self.agent._create_fallback_decision("TEST", agent_outputs_buy)
        reasoning_text = " ".join(decision_buy.reasoning_steps)
        self.assertIn("STEPS", reasoning_text)
        self.assertIn("Elite", reasoning_text)

    def test_hold_includes_risk_parameters(self):
        """HOLD decisions should mention stop-loss and profit targets"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 75.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "HOLD")

        reasoning_text = " ".join(decision.reasoning_steps)
        self.assertIn("Stop-loss", reasoning_text)
        self.assertIn("Profit target", reasoning_text)

    def test_sell_no_position_parameters(self):
        """SELL decisions should not include position sizing (going to 0%)"""
        agent_outputs = {
            'quality_analysis': {'composite_score': 65.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        self.assertEqual(decision.action, "SELL")
        self.assertEqual(decision.target_position_pct, 0.0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        self.agent = ReasoningAgent()

    def test_missing_quality_score(self):
        """Handle missing quality score gracefully"""
        agent_outputs = {
            'quality_analysis': {},  # No composite_score
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        # Should default to 50 (see line 388 in reasoning_agent.py)
        self.assertIsInstance(decision, ReasoningDecision)
        self.assertIn(decision.action, ["BUY", "SELL", "HOLD"])

    def test_boundary_quality_score_70(self):
        """Test exact boundary at quality score 70"""
        # 70.0 should be acceptable (>=70 threshold is relaxed to >70 in code)
        agent_outputs = {
            'quality_analysis': {'composite_score': 70.0, 'red_flags_count': 0},
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision = self.agent._create_fallback_decision("TEST", agent_outputs)

        # At exactly 70, should HOLD (7.0 on 10-point scale meets minimum)
        self.assertEqual(decision.action, "HOLD")
        self.assertGreater(decision.target_position_pct, 0.0)

    def test_boundary_thematic_score_28(self):
        """Test exact boundary at thematic score 28"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=None,
            thematic_score=28.0
        )

        self.assertEqual(position_type, "THEMATIC")
        self.assertEqual(target_pct, 2.5)  # Minimum thematic position
        self.assertEqual(stop_loss, -25.0)
        self.assertEqual(profit_target, 45.0)

    def test_very_high_quality_score(self):
        """Test quality score >100 (edge case)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=105.0,  # 10.5 on 10-point scale
            thematic_score=None
        )

        # Should treat as Elite (≥9.0)
        self.assertEqual(position_type, "QUALITY")
        self.assertEqual(target_pct, 15.0)

    def test_negative_quality_score(self):
        """Test negative quality score (edge case)"""
        position_type, target_pct, stop_loss, profit_target = self.agent._calculate_position_params(
            quality_score=-10.0,
            thematic_score=None
        )

        # Should EXIT (below threshold)
        self.assertEqual(position_type, "NONE")
        self.assertEqual(target_pct, 0.0)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
