#!/usr/bin/env python3
"""
Test script for enhanced MarketAgent with document parsing and market factor extraction
"""

import logging
from agents import MarketAgent, MarketAnalysis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_market_section_extraction():
    """Test market section extraction"""
    print("\n" + "="*70)
    print("TEST 1: Market Section Extraction")
    print("="*70)

    agent = MarketAgent()

    sample_document = """
# Daily Portfolio Analysis

## Market Analysis

The S&P 500 continues to trend upward with strong momentum in technology stocks.
Interest rates remain a key concern as the Fed signals potential rate hikes.
Overall market sentiment is bullish with increasing trading volumes.

## Technical Analysis

Technical indicators show overbought conditions in several sectors.
Support levels are holding firm around 4400 on the S&P 500.
Momentum indicators suggest continued upward movement.

## Economic Outlook

GDP growth forecasts remain positive for the next quarter.
Unemployment figures continue to improve, supporting market confidence.

## Portfolio Performance

Portfolio is up 2.5% this week.
"""

    sections = agent._extract_market_sections(sample_document)

    print(f"\nExtracted {len(sections)} market sections:")
    for name, text in sections.items():
        print(f"\n{name}:")
        print(f"  Length: {len(text)} characters")
        print(f"  Preview: {text[:80]}...")


def test_position_commentary_extraction():
    """Test position-specific commentary extraction"""
    print("\n" + "="*70)
    print("TEST 2: Position Commentary Extraction")
    print("="*70)

    agent = MarketAgent()

    sample_document = """
# Portfolio Holdings

## Individual Positions

AAPL: Strong performance this week with 5% gains. Technical outlook remains bullish.

Microsoft (MSFT): Continued growth in cloud services. Analyst upgrades support positive outlook.

- NVDA: AI chip demand driving record revenues. Stock showing strong momentum.
- $TSLA: Electric vehicle sales beating expectations despite market challenges.

Apple (AAPL): Additional commentary about strong iPhone sales in Q4.
"""

    position_commentary = agent._extract_position_commentary(sample_document)

    print(f"\nExtracted commentary for {len(position_commentary)} positions:")
    for ticker, commentary in position_commentary.items():
        print(f"\n{ticker}:")
        print(f"  {commentary[:100]}...")


def test_market_factors_extraction():
    """Test market factor extraction"""
    print("\n" + "="*70)
    print("TEST 3: Market Factors Extraction")
    print("="*70)

    agent = MarketAgent()

    sample_texts = [
        # Text 1: Interest rates and inflation
        "The Federal Reserve is considering rate cuts to combat inflation concerns.",

        # Text 2: Earnings and technical analysis
        "Earnings season shows strong revenue growth. Technical analysis indicates support at current levels.",

        # Text 3: Geopolitics and volatility
        "Trade war tensions with China increase market volatility. VIX levels remain elevated.",

        # Text 4: Economic indicators
        "GDP growth and employment figures beat expectations. Treasury yields continue to rise.",
    ]

    for idx, text in enumerate(sample_texts, 1):
        factors = agent._extract_market_factors(text)
        print(f"\n{idx}. Text: {text[:60]}...")
        print(f"   Factors: {', '.join(factors)}")


def test_fintwitbert_label_handling():
    """Test FinTwitBERT-specific label handling"""
    print("\n" + "="*70)
    print("TEST 4: FinTwitBERT Label Handling")
    print("="*70)

    agent = MarketAgent()

    # Simulate FinTwitBERT responses
    test_labels = [
        {"label": "Bullish", "score": 0.85},
        {"label": "Bearish", "score": 0.72},
        {"label": "Neutral", "score": 0.65},
        {"label": "bullish", "score": 0.90},  # lowercase
        {"label": "BEARISH", "score": 0.88},  # uppercase
    ]

    print("\nTesting label normalization:")
    for parsed_result in test_labels:
        result = agent._interpret_results(parsed_result, "test", {})
        print(f"  {parsed_result['label']:10} -> {result.sentiment:8} (confidence: {result.confidence:.1%})")


def test_sentiment_strength_calculation():
    """Test sentiment strength calculation"""
    print("\n" + "="*70)
    print("TEST 5: Sentiment Strength Calculation")
    print("="*70)

    agent = MarketAgent()

    from agents.base_agent import AgentResult
    from datetime import datetime

    # Mock results with different confidence levels
    test_cases = [
        (0.85, "strong"),
        (0.75, "strong"),
        (0.65, "moderate"),
        (0.55, "moderate"),
        (0.45, "weak"),
        (0.30, "weak"),
    ]

    print("\nTesting strength classification:")
    print("Confidence  →  Expected Strength")
    print("-" * 35)

    for confidence, expected_strength in test_cases:
        mock_results = [
            AgentResult(
                agent_name="MarketAgent",
                sentiment="positive",
                confidence=confidence,
                score=confidence,
                label="Bullish",
                reasoning="Test",
                timestamp=datetime.now(),
                model_used="test"
            )
        ]

        analysis = agent._aggregate_results(mock_results, {}, [])
        status = "✓" if analysis.strength == expected_strength else "✗"
        print(f"{status}  {confidence:.2f}      →  {analysis.strength:8} (expected: {expected_strength})")


def test_position_sentiment_mapping():
    """Test position sentiment mapping to Bullish/Bearish/Neutral"""
    print("\n" + "="*70)
    print("TEST 6: Position Sentiment Mapping")
    print("="*70)

    agent = MarketAgent()

    from agents.base_agent import AgentResult
    from datetime import datetime

    # Create mock position results
    mock_positions = {
        "AAPL": AgentResult("MarketAgent", "positive", 0.8, 0.8, "Bullish", "test", datetime.now(), "test"),
        "MSFT": AgentResult("MarketAgent", "negative", 0.7, 0.7, "Bearish", "test", datetime.now(), "test"),
        "NVDA": AgentResult("MarketAgent", "neutral", 0.6, 0.6, "Neutral", "test", datetime.now(), "test"),
    }

    mock_section_results = [
        AgentResult("MarketAgent", "positive", 0.7, 0.7, "Bullish", "test", datetime.now(), "test")
    ]

    analysis = agent._aggregate_results(mock_section_results, mock_positions, [])

    print("\nPosition sentiment mapping:")
    for ticker, sentiment in analysis.position_sentiments.items():
        print(f"  {ticker}: {sentiment}")


def test_full_document_analysis():
    """Test full document analysis pipeline"""
    print("\n" + "="*70)
    print("TEST 7: Full Document Analysis (API Call)")
    print("="*70)
    print("NOTE: This will make actual API calls to HuggingFace")

    agent = MarketAgent()

    sample_document = """
# Portfolio Analysis - January 15, 2025

## Market Analysis

The market shows strong bullish momentum with the S&P 500 reaching new highs.
Technology sector leads with impressive gains driven by AI innovations.
Interest rates remain supportive of risk assets as the Fed signals patience.

## Technical Analysis

Technical indicators are showing overbought conditions but momentum remains strong.
Support levels are well-established and resistance has been cleanly broken.
Volume trends confirm the upward movement with healthy market breadth.

## Individual Positions

AAPL: Strong upward momentum with new product launches driving revenue.
Technical breakout confirms bullish trend continuation.

Microsoft (MSFT): Cloud business exceeding expectations with accelerating growth.
Analyst upgrades support continued optimism.

- NVDA: AI chip demand creating supply constraints. Stock price reflects strong fundamentals.

## Economic Outlook

GDP growth and employment figures support continued market strength.
Inflation pressures moderating, reducing need for aggressive Fed action.
"""

    print("\nAnalyzing document...")

    analysis = agent.analyze_portfolio_document(sample_document)

    print("\n" + "-"*70)
    print("MARKET ANALYSIS RESULTS")
    print("-"*70)
    print(f"Overall Sentiment: {analysis.sentiment}")
    print(f"Strength: {analysis.strength}")
    print(f"Confidence: {analysis.confidence:.1%}")

    print(f"\nMarket Factors Detected ({len(analysis.market_factors)}):")
    for factor in analysis.market_factors[:10]:  # Show first 10
        print(f"  - {factor}")

    if analysis.position_sentiments:
        print(f"\nPosition Sentiments:")
        for ticker, sentiment in analysis.position_sentiments.items():
            print(f"  {ticker}: {sentiment}")

    print(f"\nSections Analyzed: {analysis.sections_analyzed}")

    print("\nSection Results:")
    for idx, result in enumerate(analysis.raw_results, 1):
        print(f"  {idx}. {result.sentiment} ({result.confidence:.1%})")
        print(f"     {result.reasoning[:70]}...")


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "="*70)
    print("TEST 8: Edge Cases")
    print("="*70)

    agent = MarketAgent()

    # Empty document
    print("\n1. Empty document:")
    analysis1 = agent.analyze_portfolio_document("")
    print(f"   Sentiment: {analysis1.sentiment}, Strength: {analysis1.strength}, Sections: {analysis1.sections_analyzed}")

    # Document with no market sections
    print("\n2. Document with no market sections:")
    doc2 = "This is just regular text without any market analysis sections."
    analysis2 = agent.analyze_portfolio_document(doc2)
    print(f"   Sentiment: {analysis2.sentiment}, Strength: {analysis2.strength}, Sections: {analysis2.sections_analyzed}")

    # Document with market factors but no sections
    print("\n3. Document with factors but no sections:")
    doc3 = "Interest rates and inflation are concerns. Earnings and GDP growth look positive."
    analysis3 = agent.analyze_portfolio_document(doc3)
    print(f"   Sentiment: {analysis3.sentiment}, Factors: {len(analysis3.market_factors)}, Sections: {analysis3.sections_analyzed}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("ENHANCED MARKET AGENT - TEST SUITE")
    print("="*70)
    print("\nFeatures being tested:")
    print("- Market section extraction (Market Analysis, Technical Overview, etc.)")
    print("- Position-specific commentary extraction")
    print("- Market factor identification (50+ factors)")
    print("- FinTwitBERT label handling (Bullish/Bearish/Neutral)")
    print("- Sentiment strength calculation (strong/moderate/weak)")
    print("- Full document analysis pipeline")

    try:
        # Fast tests (no API calls)
        test_market_section_extraction()
        test_position_commentary_extraction()
        test_market_factors_extraction()
        test_fintwitbert_label_handling()
        test_sentiment_strength_calculation()
        test_position_sentiment_mapping()
        test_edge_cases()

        # API test (optional - comment out to skip)
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
