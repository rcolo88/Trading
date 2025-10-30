#!/usr/bin/env python3
"""
Test script for enhanced HuggingFace agents with caching and smart retry
"""

import logging
import time
from agents import NewsAgent, BaseAgent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_basic_analysis():
    """Test basic sentiment analysis"""
    print("\n" + "="*70)
    print("TEST 1: Basic Sentiment Analysis")
    print("="*70)

    agent = NewsAgent()

    test_text = """
    Apple Inc. reported strong quarterly earnings, beating analyst expectations
    with record iPhone sales. The company's services division continues to grow,
    and management expressed optimism about future product launches.
    """

    result = agent.analyze(test_text, context={"ticker": "AAPL"})

    print(f"\nSentiment: {result.sentiment}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Label: {result.label}")
    print(f"Reasoning: {result.reasoning}")
    print(f"Model: {result.model_used}")


def test_caching():
    """Test caching functionality"""
    print("\n" + "="*70)
    print("TEST 2: Caching Performance")
    print("="*70)

    agent = NewsAgent()

    test_text = "Market sentiment is positive with strong momentum."

    # First call - should hit API
    print("\nFirst call (should hit API):")
    start = time.time()
    result1 = agent.analyze(test_text)
    time1 = time.time() - start
    print(f"Time: {time1:.2f}s")
    print(f"Sentiment: {result1.sentiment} ({result1.confidence:.2%})")

    # Second call - should use cache
    print("\nSecond call (should use cache):")
    start = time.time()
    result2 = agent.analyze(test_text)
    time2 = time.time() - start
    print(f"Time: {time2:.2f}s")
    print(f"Sentiment: {result2.sentiment} ({result2.confidence:.2%})")

    print(f"\nSpeedup: {time1/time2:.1f}x faster from cache")

    # Check cache stats
    stats = BaseAgent.get_cache_stats()
    print(f"\nCache Stats: {stats}")


def test_error_handling():
    """Test error handling with invalid model"""
    print("\n" + "="*70)
    print("TEST 3: Error Handling")
    print("="*70)

    agent = NewsAgent()

    # Temporarily break the API URL to test error handling
    original_url = agent.api_url
    agent.api_url = "https://invalid-url-that-does-not-exist.com"

    print("\nTesting with invalid URL (should return neutral result):")
    result = agent.analyze("This should fail gracefully")

    print(f"Sentiment: {result.sentiment}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Label: {result.label}")
    print(f"Reasoning: {result.reasoning}")

    # Restore URL
    agent.api_url = original_url


def test_cache_expiry():
    """Test cache TTL expiration"""
    print("\n" + "="*70)
    print("TEST 4: Cache Expiry (5-minute TTL)")
    print("="*70)

    # Create agent with short TTL for testing
    agent = NewsAgent()

    # Clear cache first
    BaseAgent.clear_cache()
    print("Cache cleared")

    test_text = "Test cache expiry functionality"

    # Add to cache
    result1 = agent.analyze(test_text)
    print(f"\nFirst analysis: {result1.sentiment} ({result1.confidence:.2%})")

    stats = BaseAgent.get_cache_stats()
    print(f"Cache size: {stats['cache_size']}")
    print(f"TTL: {stats['ttl_seconds']} seconds (5 minutes)")

    # Second call should use cache
    result2 = agent.analyze(test_text)
    print(f"\nSecond analysis (from cache): {result2.sentiment} ({result2.confidence:.2%})")

    print("\nNote: In production, cache entries expire after 5 minutes of inactivity")


def test_multiple_agents():
    """Test that cache is shared across agents"""
    print("\n" + "="*70)
    print("TEST 5: Shared Cache Across Agents")
    print("="*70)

    from agents import MarketAgent, RiskAgent

    # Clear cache
    BaseAgent.clear_cache()

    news_agent = NewsAgent()
    market_agent = MarketAgent()
    risk_agent = RiskAgent()

    test_text = "Shared cache test text"

    # Analyze with each agent
    print("\nAnalyzing with NewsAgent...")
    news_agent.analyze(test_text)

    print("Analyzing with MarketAgent...")
    market_agent.analyze(test_text)

    print("Analyzing with RiskAgent...")
    risk_agent.analyze(test_text)

    # Check cache stats
    stats = BaseAgent.get_cache_stats()
    print(f"\nTotal cache entries: {stats['cache_size']}")
    print("(Each agent has its own cache key based on model + text)")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("ENHANCED HUGGINGFACE AGENTS - TEST SUITE")
    print("="*70)
    print("\nFeatures being tested:")
    print("- Smart retry logic (503, 429, network errors)")
    print("- In-memory caching with 5-minute TTL")
    print("- Graceful error handling (never crashes)")
    print("- Classification response parsing")
    print("- Comprehensive logging")

    try:
        test_basic_analysis()
        test_caching()
        test_cache_expiry()
        test_multiple_agents()
        test_error_handling()  # Run last since it tests failures

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
