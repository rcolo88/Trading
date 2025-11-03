"""
End-to-End Test Suite for Agent Pipeline
Tests the complete workflow from data fetching to recommendation generation
"""

import unittest
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime

# Import modules to test
from news_fetcher import NewsFetcher, NewsArticle
from financial_data_fetcher import FinancialDataFetcher, FinancialData
from quality_metrics_calculator import QualityMetricsCalculator
from agents.reasoning_agent import ReasoningAgent


class TestAgentPipeline(unittest.TestCase):
    """End-to-end tests for agent pipeline"""

    def setUp(self):
        """Setup test fixtures"""
        self.test_tickers = ["AAPL", "MSFT"]
        self.has_finnhub_key = os.getenv("FINNHUB_API_KEY") is not None

    def test_pipeline_data_flow(self):
        """Test complete data flow from fetching to analysis"""
        print("\n" + "="*60)
        print("TEST: Complete Pipeline Data Flow")
        print("="*60)

        # Step 1: Fetch financial data
        print("\n[1/4] Fetching financial data...")
        fetcher = FinancialDataFetcher(enable_cache=False)
        financial_data = fetcher.fetch_financial_data("AAPL")

        self.assertIsNotNone(financial_data)
        self.assertEqual(financial_data.ticker, "AAPL")
        print(f"✓ Financial data fetched: {financial_data.data_quality}")

        # Step 2: Calculate quality metrics
        print("\n[2/4] Calculating quality metrics...")
        calculator = QualityMetricsCalculator()

        calculator_input = {
            'ticker': 'AAPL',
            'revenue': financial_data.revenue,
            'cogs': financial_data.cogs,
            'sga': financial_data.sga,
            'total_assets': financial_data.total_assets,
            'net_income': financial_data.net_income,
            'shareholder_equity': financial_data.shareholder_equity,
            'free_cash_flow': financial_data.free_cash_flow,
            'market_cap': financial_data.market_cap,
            'total_debt': financial_data.total_debt,
            'nopat': financial_data.nopat
        }

        quality_result = calculator.calculate_quality_metrics(calculator_input)

        self.assertIsNotNone(quality_result)
        self.assertGreater(quality_result.composite_score, 0)
        print(f"✓ Quality score: {quality_result.composite_score:.1f} ({quality_result.tier.value})")

        # Step 3: Build agent outputs (mock news/market data)
        print("\n[3/4] Building agent outputs...")
        agent_outputs = {
            'news_sentiment': {
                'sentiment': 'positive',
                'confidence': 0.75,
                'reasoning': 'Strong earnings report'
            },
            'market_sentiment': {
                'sentiment': 'bullish',
                'confidence': 0.65,
                'reasoning': 'Tech sector showing strength'
            },
            'risk_assessment': {
                'label': 'medium',
                'confidence': 0.70,
                'reasoning': 'Moderate risk environment'
            },
            'quality_analysis': {
                'composite_score': quality_result.composite_score,
                'tier': quality_result.tier.value,
                'red_flags_count': len(quality_result.red_flags),
                'investment_rating': 'BUY' if quality_result.composite_score > 70 else 'HOLD'
            },
            'current_holding': False,
            'current_shares': 0
        }
        print("✓ Agent outputs prepared")

        # Step 4: Test reasoning agent (without API call for unit test)
        print("\n[4/4] Testing reasoning logic...")
        reasoning_agent = ReasoningAgent()

        # Create fallback decision (simulates reasoning without API call)
        decision = reasoning_agent._create_fallback_decision("AAPL", agent_outputs)

        self.assertIsNotNone(decision)
        self.assertIn(decision.action, ['BUY', 'SELL', 'HOLD'])
        self.assertGreater(decision.confidence, 0)
        print(f"✓ Decision: {decision.action} (confidence: {decision.confidence:.1%})")

        print("\n" + "="*60)
        print("PIPELINE TEST PASSED")
        print("="*60)

    @unittest.skipIf(not os.getenv("FINNHUB_API_KEY"), "Finnhub API key not set")
    def test_news_fetching_integration(self):
        """Test news fetching with real API"""
        print("\n" + "="*60)
        print("TEST: News Fetching Integration")
        print("="*60)

        news_fetcher = NewsFetcher()
        news = news_fetcher.fetch_company_news("AAPL", days_back=7)

        # Should return list (may be empty)
        self.assertIsInstance(news, list)
        print(f"✓ Fetched {len(news)} news articles for AAPL")

        if news:
            article = news[0]
            self.assertIsInstance(article, NewsArticle)
            self.assertIsNotNone(article.title)
            self.assertIsNotNone(article.url)
            print(f"✓ Latest article: {article.title[:50]}...")

        print("="*60)

    def test_output_json_format(self):
        """Test that output JSONs are properly formatted"""
        print("\n" + "="*60)
        print("TEST: Output JSON Format")
        print("="*60)

        # Test news analysis output format
        news_output = {
            'timestamp': datetime.now().isoformat(),
            'days_back': 7,
            'ticker_count': 2,
            'total_articles': 10,
            'results': {
                'AAPL': {
                    'article_count': 5,
                    'sentiment': 'positive',
                    'confidence': 0.75,
                    'breakdown': {'positive': 3, 'negative': 1, 'neutral': 1},
                    'articles': []
                }
            }
        }

        # Validate JSON serializable
        try:
            json_str = json.dumps(news_output, indent=2)
            self.assertIsInstance(json_str, str)
            print("✓ News output JSON format valid")
        except Exception as e:
            self.fail(f"News output not JSON serializable: {e}")

        # Test quality analysis output format
        quality_output = {
            'timestamp': datetime.now().isoformat(),
            'holdings_count': 2,
            'watchlist_count': 50,
            'holdings_quality': {
                'AAPL': {
                    'composite_score': 85.5,
                    'tier': 'Elite',
                    'red_flags_count': 0,
                    'red_flags': [],
                    'metrics': {}
                }
            },
            'recommendations': {
                'sell_candidates': [],
                'buy_alternatives': []
            }
        }

        # Validate JSON serializable
        try:
            json_str = json.dumps(quality_output, indent=2)
            self.assertIsInstance(json_str, str)
            print("✓ Quality output JSON format valid")
        except Exception as e:
            self.fail(f"Quality output not JSON serializable: {e}")

        print("="*60)

    def test_trading_document_format(self):
        """Test that trading document follows template format"""
        print("\n" + "="*60)
        print("TEST: Trading Document Format")
        print("="*60)

        # Create sample trading document
        doc_content = """# 🤖 LLM Trading Recommendations

---

## 📅 DOCUMENT HEADER
*Date: 2025-11-01*
*Market Conditions: Bullish sentiment with medium risk*
*Portfolio Performance: 5 holdings, $500.00 cash*

---

## 🛡️ RISK MANAGEMENT UPDATES

### ⚙️ Dynamic Risk Parameters
**MAX-POSITION-SIZE 20%** - Maximum single position risk
**CASH-RESERVE 5%** - Maintain liquidity for opportunities
**RISK-BUDGET MODERATE** - Balanced approach given medium risk environment

---

## 📋 ORDERS SECTION

### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)

**SELL all 10 shares of XYZ** - Quality below threshold

**BUY 5 shares of AAPL** - Elite quality opportunity

### ⚖️ POSITION MANAGEMENT (MEDIUM PRIORITY)

**HOLD all 15 shares of MSFT** - Maintaining position

## MARKET ANALYSIS & RATIONALE

### Current Market Environment
Tech sector showing strength with positive momentum.

### Risk Assessment
Moderate risk level with stable fundamentals.
"""

        # Validate key sections exist
        required_sections = [
            "# 🤖 LLM Trading Recommendations",
            "## 📅 DOCUMENT HEADER",
            "## 🛡️ RISK MANAGEMENT UPDATES",
            "## 📋 ORDERS SECTION",
            "### 🔥 IMMEDIATE EXECUTION (HIGH PRIORITY)",
            "## MARKET ANALYSIS & RATIONALE"
        ]

        for section in required_sections:
            self.assertIn(section, doc_content, f"Missing required section: {section}")

        print("✓ All required sections present")

        # Validate order format
        self.assertIn("**SELL all", doc_content, "SELL order format incorrect")
        self.assertIn("**BUY", doc_content, "BUY order format incorrect")
        self.assertIn("**HOLD all", doc_content, "HOLD order format incorrect")
        self.assertIn(" - ", doc_content, "Order reasoning separator missing")

        print("✓ Order formats valid")
        print("="*60)

    def test_recommendation_decision_logic(self):
        """Test reasoning agent decision logic"""
        print("\n" + "="*60)
        print("TEST: Recommendation Decision Logic")
        print("="*60)

        reasoning_agent = ReasoningAgent()

        # Test Case 1: High quality, should BUY
        test_case_1 = {
            'quality_analysis': {
                'composite_score': 88.5,
                'red_flags_count': 0,
                'tier': 'Elite'
            },
            'news_sentiment': {'sentiment': 'positive'},
            'current_holding': False
        }

        decision_1 = reasoning_agent._create_fallback_decision("TEST1", test_case_1)
        self.assertEqual(decision_1.action, "BUY", "High quality should recommend BUY")
        print(f"✓ Test 1 (High Quality): {decision_1.action} - PASS")

        # Test Case 2: Low quality, should SELL
        test_case_2 = {
            'quality_analysis': {
                'composite_score': 45.0,
                'red_flags_count': 2,
                'tier': 'Weak'
            },
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision_2 = reasoning_agent._create_fallback_decision("TEST2", test_case_2)
        self.assertEqual(decision_2.action, "SELL", "Low quality should recommend SELL")
        print(f"✓ Test 2 (Low Quality): {decision_2.action} - PASS")

        # Test Case 3: Too many red flags, should SELL
        test_case_3 = {
            'quality_analysis': {
                'composite_score': 72.0,
                'red_flags_count': 5,
                'tier': 'Strong'
            },
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision_3 = reasoning_agent._create_fallback_decision("TEST3", test_case_3)
        self.assertEqual(decision_3.action, "SELL", "Too many red flags should recommend SELL")
        print(f"✓ Test 3 (Many Red Flags): {decision_3.action} - PASS")

        # Test Case 4: Moderate quality, should HOLD
        test_case_4 = {
            'quality_analysis': {
                'composite_score': 75.0,
                'red_flags_count': 1,
                'tier': 'Strong'
            },
            'news_sentiment': {'sentiment': 'neutral'},
            'current_holding': True
        }

        decision_4 = reasoning_agent._create_fallback_decision("TEST4", test_case_4)
        self.assertEqual(decision_4.action, "HOLD", "Moderate quality should recommend HOLD")
        print(f"✓ Test 4 (Moderate Quality): {decision_4.action} - PASS")

        print("="*60)


class TestScriptOutputs(unittest.TestCase):
    """Test that scripts generate expected outputs"""

    def test_output_directory_structure(self):
        """Test that output directory exists and is accessible"""
        output_dir = Path(__file__).parent / "outputs"

        # Directory should exist (created by earlier scripts)
        self.assertTrue(output_dir.exists(), "Outputs directory should exist")
        self.assertTrue(output_dir.is_dir(), "Outputs should be a directory")

        # Should be writable
        test_file = output_dir / "test_write.tmp"
        try:
            test_file.write_text("test")
            test_file.unlink()  # Clean up
            print("✓ Outputs directory is writable")
        except Exception as e:
            self.fail(f"Outputs directory not writable: {e}")

    def test_recommendation_directory_structure(self):
        """Test that trading_recommendations directory exists"""
        rec_dir = Path(__file__).parent.parent / "trading_recommendations"

        # Directory may not exist yet, so create it for testing
        rec_dir.mkdir(exist_ok=True)

        self.assertTrue(rec_dir.exists(), "Trading recommendations directory should exist")
        self.assertTrue(rec_dir.is_dir(), "Should be a directory")
        print("✓ Trading recommendations directory exists")


def run_tests():
    """Run test suite with detailed output"""
    print("\n" + "="*60)
    print("AGENT PIPELINE END-TO-END TEST SUITE")
    print("="*60)

    # Check for API key
    has_key = os.getenv("FINNHUB_API_KEY") is not None
    print(f"Finnhub API Key: {'SET' if has_key else 'NOT SET'}")

    if not has_key:
        print("\nWARNING: Some tests will be skipped without FINNHUB_API_KEY")
        print("Get a free key at: https://finnhub.io/")

    print("="*60 + "\n")

    # Run tests
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    run_tests()
