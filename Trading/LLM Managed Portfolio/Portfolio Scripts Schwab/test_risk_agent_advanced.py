#!/usr/bin/env python3
"""
Test script for enhanced RiskAgent with conservative risk assessment
"""

import logging
from agents import RiskAgent, RiskAnalysis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_risk_section_extraction():
    """Test risk section extraction"""
    print("\n" + "="*70)
    print("TEST 1: Risk Section Extraction")
    print("="*70)

    agent = RiskAgent()

    sample_document = """
# Daily Portfolio Analysis

## Risk Assessment

Portfolio concentration is elevated with largest position at 22% of total value.
Market volatility remains high with VIX above 25.
Recommend implementing stop-loss orders on overweight positions.

## Warnings

CAUTION: Tech sector exposure exceeds recommended limits.
Alert: Low cash reserves may limit ability to capitalize on opportunities.

## Market Conditions

Current market shows signs of correction with increasing downside pressure.
"""

    sections = agent._extract_risk_sections(sample_document)

    print(f"\nExtracted {len(sections)} risk sections:")
    for idx, text in enumerate(sections, 1):
        print(f"\n{idx}. Length: {len(text)} characters")
        print(f"   Preview: {text[:80]}...")


def test_risk_factor_extraction():
    """Test risk factor extraction from text"""
    print("\n" + "="*70)
    print("TEST 2: Risk Factor Extraction")
    print("="*70)

    agent = RiskAgent()

    sample_document = """
Portfolio Analysis:

Market volatility has increased significantly this week. There is caution
about the tech sector concentration risk. Stop-loss orders should be considered
for protection against downside. The portfolio shows exposure to systemic risks
through financial sector holdings. Warning signs include declining momentum
and increasing bearish sentiment.
"""

    factors = agent._extract_risk_factors(sample_document)

    print(f"\nExtracted {len(factors)} risk factors:")
    for idx, factor in enumerate(factors, 1):
        print(f"{idx}. {factor}")


def test_concern_identification():
    """Test concern identification"""
    print("\n" + "="*70)
    print("TEST 3: Concern Identification")
    print("="*70)

    agent = RiskAgent()

    sample_documents = [
        # High severity keywords
        ("Warning: significant market correction expected", "High severity"),

        # Concentration risk
        ("Portfolio shows overweight position in technology stocks", "Concentration"),

        # Volatility
        ("Market conditions remain volatile and unstable", "Volatility"),

        # Systemic risk
        ("Systemic risks from banking sector contagion", "Systemic"),
    ]

    print("\nTesting concern detection:")
    for text, category in sample_documents:
        concerns = agent._identify_concerns(text, None)
        print(f"\n{category}: {text[:50]}...")
        print(f"  Concerns: {concerns}")


def test_risk_keyword_categories():
    """Test risk keyword categorization"""
    print("\n" + "="*70)
    print("TEST 4: Risk Keyword Categories")
    print("="*70)

    agent = RiskAgent()

    print(f"\nRisk keyword categories ({len(agent.RISK_KEYWORDS)}):")
    for category, keywords in agent.RISK_KEYWORDS.items():
        print(f"\n{category.title()} ({len(keywords)} keywords):")
        sample_keywords = list(keywords)[:5]
        print(f"  Sample: {', '.join(sample_keywords)}")


def test_risk_level_classification():
    """Test risk level classification"""
    print("\n" + "="*70)
    print("TEST 5: Risk Level Classification")
    print("="*70)

    agent = RiskAgent()

    from agents.base_agent import AgentResult
    from datetime import datetime

    # Test cases: (normalized_risk_score, expected_level)
    test_cases = [
        (0.85, "high"),
        (0.65, "high"),
        (0.50, "medium"),
        (0.35, "medium"),
        (0.20, "low"),
    ]

    print("\nRisk Score → Risk Level")
    print("-" * 30)

    for risk_score, expected in test_cases:
        # Create mock results to produce desired risk score
        if risk_score >= 0.65:
            sentiment = "negative"
        elif risk_score >= 0.35:
            sentiment = "neutral"
        else:
            sentiment = "positive"

        mock_results = [
            AgentResult(
                "RiskAgent", sentiment, 0.8, 0.8, "test",
                "test", datetime.now(), "test"
            )
        ]

        analysis = agent._aggregate_results(mock_results, [], None)
        status = "✓" if analysis.risk_level == expected else "✗"
        print(f"{status}  {risk_score:.2f}       → {analysis.risk_level:6} (expected: {expected})")


def test_conservative_bias():
    """Test conservative bias in risk assessment"""
    print("\n" + "="*70)
    print("TEST 6: Conservative Bias")
    print("="*70)

    agent = RiskAgent()

    from agents.base_agent import AgentResult
    from datetime import datetime

    # Base scenario: medium risk
    base_results = [
        AgentResult("RiskAgent", "neutral", 0.6, 0.6, "test", "test", datetime.now(), "test")
    ]

    # Scenario 1: No concerns
    analysis1 = agent._aggregate_results(base_results, [], None)

    # Scenario 2: Few concerns (2-5)
    analysis2 = agent._aggregate_results(base_results, ["concern1", "concern2", "concern3"], None)

    # Scenario 3: Many concerns (>5)
    analysis3 = agent._aggregate_results(
        base_results,
        ["c1", "c2", "c3", "c4", "c5", "c6"],
        None
    )

    print("\nConservative bias effect:")
    print(f"  No concerns (0):    {analysis1.risk_level}")
    print(f"  Few concerns (3):   {analysis2.risk_level}")
    print(f"  Many concerns (6):  {analysis3.risk_level}")
    print(f"\nNote: More concerns → higher risk level (conservative)")


def test_risk_score_categories():
    """Test risk score calculation by category"""
    print("\n" + "="*70)
    print("TEST 7: Risk Score Categories")
    print("="*70)

    agent = RiskAgent()

    test_scenarios = [
        (["systemic risk detected", "crisis imminent"], "Systemic"),
        (["high concentration", "overweight position"], "Position"),
        (["market volatility", "turbulent conditions"], "Market"),
        (["warning", "caution", "concern"], "Multiple"),
    ]

    print("\nRisk score categorization:")
    for concerns, scenario in test_scenarios:
        scores = agent._calculate_risk_scores([], concerns, None)
        print(f"\n{scenario}:")
        for category, score in scores.items():
            print(f"  {category:10} {score:.2f}")


def test_recommended_actions():
    """Test recommended action generation"""
    print("\n" + "="*70)
    print("TEST 8: Recommended Actions")
    print("="*70)

    agent = RiskAgent()

    test_cases = [
        ("high", ["critical risk"], {"systemic": 0.8, "position": 0.7, "market": 0.6}, "reduce exposure significantly"),
        ("high", ["moderate risk"], {"systemic": 0.6, "position": 0.5, "market": 0.5}, "reduce exposure"),
        ("medium", ["c1", "c2", "c3", "c4"], {"systemic": 0.5, "position": 0.5, "market": 0.5}, "maintain with caution"),
        ("medium", ["c1"], {"systemic": 0.5, "position": 0.5, "market": 0.5}, "maintain"),
        ("low", [], {"systemic": 0.2, "position": 0.2, "market": 0.2}, "consider increase"),
    ]

    print("\nRisk Level → Recommended Action")
    print("-" * 50)

    for risk_level, concerns, risk_scores, expected in test_cases:
        action = agent._determine_action(risk_level, concerns, risk_scores)
        status = "✓" if action == expected else "✗"
        print(f"{status} {risk_level:6} → {action:30} (expected: {expected})")


def test_portfolio_data_integration():
    """Test integration with portfolio metrics"""
    print("\n" + "="*70)
    print("TEST 9: Portfolio Data Integration")
    print("="*70)

    agent = RiskAgent()

    portfolio_scenarios = [
        # Scenario 1: High concentration
        {
            "max_position_weight": 0.25,
            "portfolio_volatility": 0.15,
            "cash_percentage": 10
        },
        # Scenario 2: High volatility
        {
            "max_position_weight": 0.15,
            "portfolio_volatility": 0.30,
            "cash_percentage": 8
        },
        # Scenario 3: Low cash
        {
            "max_position_weight": 0.12,
            "portfolio_volatility": 0.18,
            "cash_percentage": 3
        },
    ]

    print("\nPortfolio metrics impact on concerns:")
    for idx, portfolio_data in enumerate(portfolio_scenarios, 1):
        concerns = agent._identify_concerns("", portfolio_data)
        print(f"\nScenario {idx}:")
        print(f"  Max Position: {portfolio_data['max_position_weight']:.1%}")
        print(f"  Volatility: {portfolio_data['portfolio_volatility']:.1%}")
        print(f"  Cash: {portfolio_data['cash_percentage']:.0f}%")
        print(f"  Concerns: {concerns}")


def test_full_document_analysis():
    """Test full document analysis pipeline"""
    print("\n" + "="*70)
    print("TEST 10: Full Document Analysis (API Call)")
    print("="*70)
    print("NOTE: This will make actual API calls to HuggingFace")

    agent = RiskAgent()

    sample_document = """
# Portfolio Risk Analysis - January 15, 2025

## Risk Assessment

WARNING: Portfolio concentration exceeds recommended limits with largest position at 28%.
Market volatility has increased significantly with VIX above 30.
Stop-loss orders recommended for protection against further downside.

## Concerns

- High exposure to technology sector creates concentration risk
- Declining cash reserves limit defensive capabilities
- Systemic risks from banking sector showing signs of stress
- Technical indicators suggest potential market correction

## Portfolio Metrics

Current portfolio shows elevated risk profile with multiple concerns.
Risk management protocols should be implemented immediately.
Consider rebalancing to reduce exposure to overweight positions.
"""

    portfolio_data = {
        "max_position_weight": 0.28,
        "portfolio_volatility": 0.32,
        "cash_percentage": 4
    }

    print("\nAnalyzing document with portfolio data...")

    analysis = agent.analyze_portfolio_document(sample_document, portfolio_data)

    print("\n" + "-"*70)
    print("RISK ANALYSIS RESULTS")
    print("-"*70)
    print(f"Risk Level: {analysis.risk_level.upper()}")
    print(f"Confidence: {analysis.confidence:.1%}")
    print(f"Recommended Action: {analysis.recommended_action}")

    print(f"\nConcerns ({len(analysis.concerns)}):")
    for concern in analysis.concerns:
        print(f"  - {concern}")

    print(f"\nRisk Scores:")
    for category, score in analysis.risk_scores.items():
        bar = "█" * int(score * 30)
        print(f"  {category.title():10} {score:.2f} {bar}")

    print(f"\nRisk Factors Analyzed: {analysis.risk_factors_analyzed}")


def test_error_handling():
    """Test error handling and conservative defaults"""
    print("\n" + "="*70)
    print("TEST 11: Error Handling (Conservative Defaults)")
    print("="*70)

    agent = RiskAgent()

    # Test 1: Empty document
    print("\n1. Empty document:")
    analysis1 = agent.analyze_portfolio_document("", None)
    print(f"   Risk Level: {analysis1.risk_level} (should default to 'medium')")
    print(f"   Action: {analysis1.recommended_action}")

    # Test 2: No risk content
    print("\n2. Document with no risk content:")
    doc2 = "Portfolio is performing well with steady growth."
    analysis2 = agent.analyze_portfolio_document(doc2, None)
    print(f"   Risk Level: {analysis2.risk_level}")
    print(f"   Factors Analyzed: {analysis2.risk_factors_analyzed}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("ENHANCED RISK AGENT - TEST SUITE")
    print("="*70)
    print("\nFeatures being tested:")
    print("- Risk section extraction (Risk, Warnings, Cautions, etc.)")
    print("- Risk factor identification (60+ keywords across 6 categories)")
    print("- Concern identification with portfolio metrics")
    print("- Conservative risk assessment with upward bias")
    print("- Risk level classification (high/medium/low)")
    print("- Risk score categorization (systemic/position/market)")
    print("- Recommended action generation")

    try:
        # Fast tests (no API calls)
        test_risk_section_extraction()
        test_risk_factor_extraction()
        test_concern_identification()
        test_risk_keyword_categories()
        test_risk_level_classification()
        test_conservative_bias()
        test_risk_score_categories()
        test_recommended_actions()
        test_portfolio_data_integration()
        test_error_handling()

        # API test (optional)
        print("\n" + "="*70)
        response = input("\nRun full document analysis test (requires API calls)? [y/N]: ")
        if response.lower() == 'y':
            test_full_document_analysis()
        else:
            print("Skipping API test")

        print("\n" + "="*70)
        print("ALL TESTS COMPLETED")
        print("="*70 + "\n")

    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
