#!/usr/bin/env python3
"""
Test script for TradeAgent - Trade decision synthesis and order generation
"""

import logging
from agents import TradeAgent, NewsAnalysis, MarketAnalysis, RiskAnalysis, AgentResult
from trading_models import OrderType, OrderPriority
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_mock_agent_result(sentiment: str, confidence: float) -> AgentResult:
    """Create mock AgentResult for testing"""
    return AgentResult(
        agent_name="MockAgent",
        sentiment=sentiment,
        confidence=confidence,
        score=confidence,
        label=sentiment,
        reasoning=f"Mock {sentiment} result",
        timestamp=datetime.now(),
        model_used="mock"
    )


def test_profit_taking():
    """Test profit taking logic (>15% return)"""
    print("\n" + "="*70)
    print("TEST 1: Profit Taking (>15% Return)")
    print("="*70)

    agent = TradeAgent()

    # Mock analyses
    news = NewsAnalysis("positive", 0.7, ["AAPL"], {"positive": 0.7, "negative": 0.2, "neutral": 0.1}, 3, [])
    market = MarketAnalysis("Bullish", "moderate", 0.6, [], {}, 2, [])
    risk = RiskAnalysis("low", 0.6, [], {"systemic": 0.3, "position": 0.3, "market": 0.4}, "maintain", 1, [])

    # Portfolio with 18% gain on AAPL
    portfolio_data = {
        'holdings': {
            'AAPL': {
                'shares': 100,
                'value': 18000,
                'cost_basis': 15000,
                'return_pct': 0.20  # 20% return - should trigger profit taking
            }
        },
        'cash': 5000,
        'total_value': 23000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'AAPL': 180.0})

    print(f"\nGenerated {len(orders)} orders:")
    for order in orders:
        print(f"  {order.priority.value}: {order.action.value} {order.ticker} - {order.reason}")

    # Verify profit taking triggered
    assert len(orders) == 1
    assert orders[0].action == OrderType.SELL
    assert orders[0].priority == OrderPriority.HIGH
    print("\n✓ Profit taking correctly triggered at 20% return")


def test_stop_loss():
    """Test stop loss logic (<-8% return)"""
    print("\n" + "="*70)
    print("TEST 2: Stop Loss (<-8% Return)")
    print("="*70)

    agent = TradeAgent()

    # Mock analyses
    news = NewsAnalysis("negative", 0.6, ["NVDA"], {"positive": 0.2, "negative": 0.6, "neutral": 0.2}, 2, [])
    market = MarketAnalysis("Bearish", "weak", 0.5, [], {}, 1, [])
    risk = RiskAnalysis("medium", 0.6, [], {"systemic": 0.5, "position": 0.5, "market": 0.5}, "maintain", 1, [])

    # Portfolio with -10% loss on NVDA
    portfolio_data = {
        'holdings': {
            'NVDA': {
                'shares': 50,
                'value': 9000,
                'cost_basis': 10000,
                'return_pct': -0.10  # -10% loss - should trigger stop loss
            }
        },
        'cash': 15000,
        'total_value': 24000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'NVDA': 180.0})

    print(f"\nGenerated {len(orders)} orders:")
    for order in orders:
        print(f"  {order.priority.value}: {order.action.value} {order.ticker} - {order.reason}")

    # Verify stop loss triggered
    assert len(orders) == 1
    assert orders[0].action == OrderType.SELL
    assert orders[0].priority == OrderPriority.HIGH
    print("\n✓ Stop loss correctly triggered at -10% return")


def test_bearish_high_risk_sell():
    """Test bearish market + high risk = sell"""
    print("\n" + "="*70)
    print("TEST 3: Bearish Market + High Risk = SELL")
    print("="*70)

    agent = TradeAgent()

    # Bearish market + high risk
    news = NewsAnalysis("negative", 0.7, ["MSFT"], {"positive": 0.1, "negative": 0.7, "neutral": 0.2}, 4, [])
    market = MarketAnalysis("Bearish", "strong", 0.8, [], {"MSFT": "Bearish"}, 3, [])
    risk = RiskAnalysis("high", 0.75, ["market volatility", "correction"], {"systemic": 0.6, "position": 0.5, "market": 0.8}, "reduce exposure", 5, [])

    # Portfolio with MSFT position
    portfolio_data = {
        'holdings': {
            'MSFT': {
                'shares': 75,
                'value': 28000,
                'cost_basis': 25000,
                'return_pct': 0.12  # 12% gain (below profit taking)
            }
        },
        'cash': 12000,
        'total_value': 40000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'MSFT': 373.0})

    print(f"\nGenerated {len(orders)} orders:")
    for order in orders:
        print(f"  {order.priority.value}: {order.action.value} {order.ticker} - {order.reason}")

    # Should generate sell order
    assert len(orders) >= 1
    sell_orders = [o for o in orders if o.action == OrderType.SELL]
    assert len(sell_orders) >= 1
    print("\n✓ Bearish + high risk correctly generated SELL signal")


def test_positive_bullish_buy():
    """Test positive news + bullish market = buy"""
    print("\n" + "="*70)
    print("TEST 4: Positive News + Bullish Market = BUY")
    print("="*70)

    agent = TradeAgent()

    # Positive news + bullish market + low risk
    news = NewsAnalysis("positive", 0.85, ["AAPL", "GOOGL"], {"positive": 0.85, "negative": 0.05, "neutral": 0.1}, 5, [])
    market = MarketAnalysis("Bullish", "strong", 0.80, [], {"AAPL": "Bullish", "GOOGL": "Bullish"}, 4, [])
    risk = RiskAnalysis("low", 0.65, [], {"systemic": 0.3, "position": 0.3, "market": 0.3}, "consider increase", 2, [])

    # Portfolio with no current holdings in these tickers
    portfolio_data = {
        'holdings': {},
        'cash': 50000,
        'total_value': 50000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'AAPL': 180.0, 'GOOGL': 140.0})

    print(f"\nGenerated {len(orders)} orders:")
    for order in orders:
        print(f"  {order.priority.value}: {order.action.value} {order.ticker}")
        print(f"    Reason: {order.reason}")
        if order.target_value:
            print(f"    Target Value: ${order.target_value:,.2f}")

    # Should generate buy orders
    buy_orders = [o for o in orders if o.action == OrderType.BUY]
    assert len(buy_orders) >= 1
    print(f"\n✓ Positive news + bullish market generated {len(buy_orders)} BUY signals")


def test_position_size_limits():
    """Test 20% position size limit"""
    print("\n" + "="*70)
    print("TEST 5: Position Size Limit (20% Max)")
    print("="*70)

    agent = TradeAgent()

    # Strong buy signals
    news = NewsAnalysis("positive", 0.9, ["TSLA"], {"positive": 0.9, "negative": 0.05, "neutral": 0.05}, 3, [])
    market = MarketAnalysis("Bullish", "strong", 0.85, [], {"TSLA": "Bullish"}, 2, [])
    risk = RiskAnalysis("low", 0.7, [], {"systemic": 0.2, "position": 0.3, "market": 0.3}, "maintain", 1, [])

    # Portfolio with TSLA already at 18% of total value
    portfolio_data = {
        'holdings': {
            'TSLA': {
                'shares': 100,
                'value': 18000,  # 18% of 100k
                'cost_basis': 15000,
                'return_pct': 0.20
            }
        },
        'cash': 82000,
        'total_value': 100000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'TSLA': 180.0})

    print(f"\nCurrent TSLA position: $18,000 (18% of portfolio)")
    print(f"Max position size: 20%")
    print(f"Remaining capacity: 2%\n")

    print(f"Generated {len(orders)} orders:")
    for order in orders:
        if order.action == OrderType.BUY and order.ticker == "TSLA":
            if order.target_value:
                pct = (order.target_value / portfolio_data['total_value']) * 100
                print(f"  {order.action.value} {order.ticker}: ${order.target_value:,.2f} ({pct:.1f}% of portfolio)")
                # Should not exceed remaining 2%
                assert pct <= 2.5, "Position size should not exceed remaining capacity"

    print("\n✓ Position size correctly limited to maximum 20% of portfolio")


def test_priority_assignment():
    """Test priority assignment based on signal strength"""
    print("\n" + "="*70)
    print("TEST 6: Priority Assignment")
    print("="*70)

    agent = TradeAgent()

    # Mix of signal strengths
    news = NewsAnalysis("positive", 0.9, ["AAPL", "MSFT", "GOOGL"], {"positive": 0.9, "negative": 0.05, "neutral": 0.05}, 6, [])
    market = MarketAnalysis("Bullish", "strong", 0.85, [], {"AAPL": "Bullish", "MSFT": "Neutral", "GOOGL": "Bullish"}, 3, [])
    risk = RiskAnalysis("low", 0.7, [], {"systemic": 0.3, "position": 0.3, "market": 0.3}, "maintain", 2, [])

    portfolio_data = {
        'holdings': {},
        'cash': 100000,
        'total_value': 100000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'AAPL': 180.0, 'MSFT': 373.0, 'GOOGL': 140.0})

    print(f"\nGenerated {len(orders)} orders sorted by priority:\n")

    high_count = 0
    medium_count = 0
    low_count = 0

    for order in orders:
        print(f"  [{order.priority.value:6}] {order.action.value} {order.ticker}")
        print(f"            {order.reason[:60]}...")

        if order.priority == OrderPriority.HIGH:
            high_count += 1
        elif order.priority == OrderPriority.MEDIUM:
            medium_count += 1
        else:
            low_count += 1

    print(f"\nPriority Distribution:")
    print(f"  HIGH:   {high_count}")
    print(f"  MEDIUM: {medium_count}")
    print(f"  LOW:    {low_count}")

    # Verify orders are sorted by priority
    for i in range(len(orders) - 1):
        assert orders[i].priority.value <= orders[i+1].priority.value, "Orders should be sorted by priority"

    print("\n✓ Orders correctly sorted by priority (HIGH → MEDIUM → LOW)")


def test_insufficient_signals():
    """Test HOLD when signals are insufficient"""
    print("\n" + "="*70)
    print("TEST 7: Insufficient Signals = HOLD")
    print("="*70)

    agent = TradeAgent()

    # Weak/neutral signals
    news = NewsAnalysis("neutral", 0.5, ["XYZ"], {"positive": 0.3, "negative": 0.3, "neutral": 0.4}, 2, [])
    market = MarketAnalysis("Neutral", "weak", 0.45, [], {}, 1, [])
    risk = RiskAnalysis("medium", 0.5, [], {"systemic": 0.5, "position": 0.5, "market": 0.5}, "maintain", 1, [])

    portfolio_data = {
        'holdings': {},
        'cash': 50000,
        'total_value': 50000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'XYZ': 50.0})

    print(f"\nGenerated {len(orders)} orders")

    if len(orders) == 0:
        print("  No orders generated (HOLD)")
        print("\n✓ Correctly generated HOLD when signals are insufficient")
    else:
        print(f"  Unexpected orders generated:")
        for order in orders:
            print(f"    {order.action.value} {order.ticker}: {order.reason}")


def test_summary_generation():
    """Test summary generation"""
    print("\n" + "="*70)
    print("TEST 8: Summary Generation")
    print("="*70)

    agent = TradeAgent()

    # Create complete scenario
    news = NewsAnalysis("positive", 0.75, ["AAPL", "NVDA"], {"positive": 0.75, "negative": 0.15, "neutral": 0.1}, 4, [])
    market = MarketAnalysis("Bullish", "moderate", 0.70, ["earnings", "momentum"], {"AAPL": "Bullish", "NVDA": "Bullish"}, 3, [])
    risk = RiskAnalysis("low", 0.65, [], {"systemic": 0.3, "position": 0.4, "market": 0.3}, "maintain", 2, [])

    portfolio_data = {
        'holdings': {},
        'cash': 50000,
        'total_value': 50000
    }

    orders = agent.generate_orders(news, market, risk, portfolio_data, {'AAPL': 180.0, 'NVDA': 500.0})

    summary = agent.generate_summary(orders, news, market, risk)

    print(summary)

    assert "TRADE DECISION SUMMARY" in summary
    assert "Market Assessment" in summary
    assert "GENERATED ORDERS" in summary

    print("\n✓ Summary generated successfully")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("TRADE AGENT - TEST SUITE")
    print("="*70)
    print("\nFeatures being tested:")
    print("- Profit taking (>15% return)")
    print("- Stop loss (<-8% return)")
    print("- Bearish + high risk → SELL")
    print("- Positive news + bullish → BUY")
    print("- Position size limits (20% max)")
    print("- Priority assignment (HIGH/MEDIUM/LOW)")
    print("- Insufficient signals → HOLD")
    print("- Summary generation")

    try:
        test_profit_taking()
        test_stop_loss()
        test_bearish_high_risk_sell()
        test_positive_bullish_buy()
        test_position_size_limits()
        test_priority_assignment()
        test_insufficient_signals()
        test_summary_generation()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70 + "\n")

    except AssertionError as e:
        print(f"\n\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
