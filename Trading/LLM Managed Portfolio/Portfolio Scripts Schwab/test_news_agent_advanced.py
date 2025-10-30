#!/usr/bin/env python3
"""
Test script for enhanced NewsAgent with document parsing and ticker extraction
"""

import logging
from agents import NewsAgent, NewsAnalysis

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_ticker_extraction():
    """Test ticker extraction with various formats"""
    print("\n" + "="*70)
    print("TEST 1: Ticker Extraction")
    print("="*70)

    agent = NewsAgent()

    test_texts = [
        # Format 1: $TICKER
        "Market update: $AAPL is up 3% while $NVDA gained 2%.",

        # Format 2: (TICKER)
        "Apple (AAPL) and Microsoft (MSFT) reported earnings.",

        # Format 3: Company Name (TICKER)
        "Tesla (TSLA) stock surged after Elon Musk announced new products.",

        # Format 4: Standalone with context
        "I bought shares of GOOGL and stock AMZN today.",

        # Mixed formats
        "Portfolio holds $SPY, Microsoft (MSFT), and shares of TSLA.",

        # Should filter out common words
        "I went TO the store FOR A NEW item.",
    ]

    for idx, text in enumerate(test_texts, 1):
        tickers = agent._extract_tickers(text)
        print(f"\n{idx}. Text: {text[:60]}...")
        print(f"   Extracted: {tickers}")


def test_news_extraction():
    """Test news item extraction from document"""
    print("\n" + "="*70)
    print("TEST 2: News Item Extraction")
    print("="*70)

    agent = NewsAgent()

    sample_document = """
# Daily Portfolio Analysis

## News and Events

Recent market developments:

- Apple Inc. (AAPL) reported strong quarterly earnings, beating expectations
- Federal Reserve signals potential rate cuts in 2024
- Tech sector shows resilience amid market volatility
- $NVDA announces new AI chip lineup at CES
- Energy stocks rally on oil price increases

## Performance

Portfolio is up 2.5% this week.

## Other News

- Amazon (AMZN) expands AWS services
- Tesla (TSLA) delivers record number of vehicles
"""

    news_items = agent._extract_news_items(sample_document)

    print(f"\nExtracted {len(news_items)} news items:")
    for idx, item in enumerate(news_items, 1):
        print(f"\n{idx}. {item[:80]}...")


def test_news_filtering():
    """Test news item detection heuristic"""
    print("\n" + "="*70)
    print("TEST 3: News Item Filtering")
    print("="*70)

    agent = NewsAgent()

    test_items = [
        ("Apple reported strong earnings with revenue up 10%", True),
        ("The weather was nice today", False),
        ("Stock market fell 2% on inflation concerns", True),
        ("I like pizza", False),
        ("Q3 earnings beat analyst forecasts by 15%", True),
        ("Meeting scheduled for tomorrow", False),
        ("$SPY gained 1.5% as investors bought the dip", True),
    ]

    print("\nTesting news detection:")
    for text, expected in test_items:
        is_news = agent._looks_like_news(text)
        status = "✓" if is_news == expected else "✗"
        print(f"{status} '{text[:50]}...' -> {is_news} (expected: {expected})")


def test_sentiment_aggregation():
    """Test weighted sentiment aggregation"""
    print("\n" + "="*70)
    print("TEST 4: Sentiment Aggregation")
    print("="*70)

    agent = NewsAgent()

    # Simulate results with different sentiments and confidences
    from agents.base_agent import AgentResult
    from datetime import datetime

    mock_results = [
        AgentResult(
            agent_name="NewsAgent",
            sentiment="positive",
            confidence=0.9,
            score=0.9,
            label="positive",
            reasoning="Strong positive",
            timestamp=datetime.now(),
            model_used="test"
        ),
        AgentResult(
            agent_name="NewsAgent",
            sentiment="positive",
            confidence=0.7,
            score=0.7,
            label="positive",
            reasoning="Moderate positive",
            timestamp=datetime.now(),
            model_used="test"
        ),
        AgentResult(
            agent_name="NewsAgent",
            sentiment="negative",
            confidence=0.6,
            score=0.6,
            label="negative",
            reasoning="Moderate negative",
            timestamp=datetime.now(),
            model_used="test"
        ),
    ]

    aggregated = agent._aggregate_results(mock_results, ["AAPL", "MSFT"])

    print(f"\nAggregated Results:")
    print(f"  Overall Sentiment: {aggregated.sentiment}")
    print(f"  Confidence: {aggregated.confidence:.2%}")
    print(f"  Tickers: {aggregated.tickers}")
    print(f"  Breakdown:")
    for sentiment, pct in aggregated.breakdown.items():
        print(f"    {sentiment}: {pct:.1%}")
    print(f"  Items Analyzed: {aggregated.news_items_analyzed}")


def test_full_document_analysis():
    """Test full document analysis pipeline"""
    print("\n" + "="*70)
    print("TEST 5: Full Document Analysis (API Call)")
    print("="*70)
    print("NOTE: This will make actual API calls to HuggingFace")

    agent = NewsAgent()

    sample_document = """
# Portfolio Analysis - January 15, 2025

## Market News

- Apple (AAPL) stock rises 5% after strong iPhone sales report
- Microsoft (MSFT) announces major AI partnership expansion
- Federal Reserve hints at potential rate cuts this year
- Tech sector leads market gains with $NVDA up 8%
- Amazon (AMZN) faces increased competition in cloud services

## Portfolio Performance

Current holdings show 3.2% gains this week.

## Economic Outlook

Analysts expect continued market volatility but remain optimistic about tech stocks.
"""

    print("\nAnalyzing document...")
    print("(Limiting to 3 items to minimize API calls)")

    analysis = agent.analyze_portfolio_document(sample_document, max_items=3)

    print("\n" + "-"*70)
    print("ANALYSIS RESULTS")
    print("-"*70)
    print(f"Overall Sentiment: {analysis.sentiment.upper()}")
    print(f"Confidence: {analysis.confidence:.1%}")
    print(f"\nExtracted Tickers: {', '.join(analysis.tickers)}")
    print(f"\nSentiment Breakdown:")
    for sentiment, pct in analysis.breakdown.items():
        bar = "█" * int(pct * 30)
        print(f"  {sentiment:8} {pct:5.1%} {bar}")
    print(f"\nNews Items Analyzed: {analysis.news_items_analyzed}")

    print("\nIndividual Item Results:")
    for idx, result in enumerate(analysis.raw_results, 1):
        print(f"  {idx}. {result.sentiment} ({result.confidence:.1%}) - {result.reasoning[:60]}...")


def test_ticker_blacklist():
    """Test that common words are filtered out"""
    print("\n" + "="*70)
    print("TEST 6: Ticker Blacklist Filtering")
    print("="*70)

    agent = NewsAgent()

    # Text with common words that look like tickers
    text = "I went TO the store FOR A NEW item. It was ALL good. The US economy is strong."

    tickers = agent._extract_tickers(text)

    print(f"\nText: {text}")
    print(f"Extracted tickers: {tickers}")
    print(f"Expected: [] (empty, all filtered out)")

    if not tickers:
        print("✓ PASS: All common words correctly filtered")
    else:
        print(f"✗ FAIL: Found tickers that should be filtered: {tickers}")


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "="*70)
    print("TEST 7: Edge Cases")
    print("="*70)

    agent = NewsAgent()

    # Empty document
    print("\n1. Empty document:")
    analysis1 = agent.analyze_portfolio_document("", max_items=5)
    print(f"   Sentiment: {analysis1.sentiment}, Items: {analysis1.news_items_analyzed}")

    # Document with no news
    print("\n2. Document with no news:")
    doc2 = "This is just regular text without any financial news or tickers."
    analysis2 = agent.analyze_portfolio_document(doc2, max_items=5)
    print(f"   Sentiment: {analysis2.sentiment}, Items: {analysis2.news_items_analyzed}")

    # Document with only tickers, no news
    print("\n3. Document with tickers but no news:")
    doc3 = "$AAPL $MSFT $GOOGL"
    analysis3 = agent.analyze_portfolio_document(doc3, max_items=5)
    print(f"   Sentiment: {analysis3.sentiment}, Tickers: {analysis3.tickers}, Items: {analysis3.news_items_analyzed}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("ENHANCED NEWS AGENT - TEST SUITE")
    print("="*70)
    print("\nFeatures being tested:")
    print("- Ticker extraction ($AAPL, (AAPL), Company (TICKER))")
    print("- Ticker blacklist filtering")
    print("- News item extraction from documents")
    print("- News detection heuristics")
    print("- Weighted sentiment aggregation")
    print("- Full document analysis pipeline")

    try:
        # Fast tests (no API calls)
        test_ticker_extraction()
        test_ticker_blacklist()
        test_news_extraction()
        test_news_filtering()
        test_sentiment_aggregation()
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
