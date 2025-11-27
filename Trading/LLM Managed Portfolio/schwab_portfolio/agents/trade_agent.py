"""
Trade Decision Agent
Synthesizes all agent outputs to generate trade orders with no API calls
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.trading_models import TradeOrder, OrderType, OrderPriority
from .news_agent import NewsAnalysis
from .market_agent import MarketAnalysis
from .risk_agent import RiskAnalysis


@dataclass
class TradeDecision:
    """Consolidated trade decision from all agents"""
    action: str  # BUY, SELL, HOLD
    strength: str  # strong, moderate, weak
    confidence: float  # 0.0 to 1.0
    reasoning: str
    priority: OrderPriority
    suggested_allocation: Optional[float] = None  # % of portfolio


class TradeAgent:
    """
    Synthesizes outputs from sentiment agents to generate trade orders
    No API calls - pure logic based on other agents' results
    """

    # Trading parameters
    MAX_POSITION_SIZE = 0.20  # 20% max per position
    PROFIT_TAKE_THRESHOLD = 0.15  # Take profits at 15% gain
    STOP_LOSS_THRESHOLD = -0.08  # Stop loss at -8%
    HIGH_CONFIDENCE_THRESHOLD = 0.70  # High confidence for priority orders
    MEDIUM_CONFIDENCE_THRESHOLD = 0.55  # Medium confidence threshold

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate_orders(
        self,
        news_analysis: Optional[NewsAnalysis],
        market_analysis: Optional[MarketAnalysis],
        risk_analysis: Optional[RiskAnalysis],
        portfolio_data: Dict[str, Any],
        current_prices: Optional[Dict[str, float]] = None
    ) -> List[TradeOrder]:
        """
        Generate trade orders based on all agent analyses

        Args:
            news_analysis: Results from NewsAgent
            market_analysis: Results from MarketAgent
            risk_analysis: Results from RiskAgent
            portfolio_data: Current portfolio state (holdings, cash, returns)
            current_prices: Optional dict of {ticker: price}

        Returns:
            List of TradeOrder objects sorted by priority
        """
        self.logger.info("Generating trade orders from agent analyses")

        orders = []

        # Extract current holdings and calculate returns
        holdings = portfolio_data.get('holdings', {})
        cash = portfolio_data.get('cash', 0)
        total_value = portfolio_data.get('total_value', cash)

        # Get all tickers from analyses and holdings
        all_tickers = self._get_all_tickers(news_analysis, market_analysis, holdings)
        self.logger.info(f"Analyzing {len(all_tickers)} tickers: {all_tickers}")

        # Generate orders for each ticker
        for ticker in all_tickers:
            decision = self._make_trade_decision(
                ticker,
                news_analysis,
                market_analysis,
                risk_analysis,
                holdings,
                total_value,
                current_prices
            )

            if decision.action != "HOLD":
                order = self._create_trade_order(
                    ticker,
                    decision,
                    holdings,
                    total_value,
                    cash,
                    current_prices
                )
                if order:
                    orders.append(order)

        # Sort by priority
        orders = self._sort_by_priority(orders)

        self.logger.info(f"Generated {len(orders)} trade orders")
        for order in orders:
            self.logger.info(f"  {order.priority.value}: {order.action.value} {order.ticker} - {order.reason[:60]}")

        return orders

    def _get_all_tickers(
        self,
        news_analysis: Optional[NewsAnalysis],
        market_analysis: Optional[MarketAnalysis],
        holdings: Dict[str, Any]
    ) -> List[str]:
        """Get unique list of all tickers to analyze"""
        tickers = set()

        # Tickers from current holdings
        tickers.update(holdings.keys())

        # Tickers from news analysis
        if news_analysis:
            tickers.update(news_analysis.tickers)

        # Tickers from market analysis position sentiments
        if market_analysis:
            tickers.update(market_analysis.position_sentiments.keys())

        return sorted(list(tickers))

    def _make_trade_decision(
        self,
        ticker: str,
        news_analysis: Optional[NewsAnalysis],
        market_analysis: Optional[MarketAnalysis],
        risk_analysis: Optional[RiskAnalysis],
        holdings: Dict[str, Any],
        total_value: float,
        current_prices: Optional[Dict[str, float]]
    ) -> TradeDecision:
        """
        Make trading decision for a single ticker

        Args:
            ticker: Stock ticker
            news_analysis: News sentiment
            market_analysis: Market sentiment
            risk_analysis: Risk assessment
            holdings: Current holdings
            total_value: Total portfolio value
            current_prices: Current prices

        Returns:
            TradeDecision with action and reasoning
        """
        # Get current position
        position = holdings.get(ticker, {})
        current_shares = position.get('shares', 0)
        position_value = position.get('value', 0)
        position_return = position.get('return_pct', 0.0)

        # Initialize decision components
        signals = []
        confidence_sum = 0.0
        weight_sum = 0.0

        # Check for profit taking (highest priority)
        if current_shares > 0 and position_return >= self.PROFIT_TAKE_THRESHOLD:
            return TradeDecision(
                action="SELL",
                strength="strong",
                confidence=0.9,
                reasoning=f"Profit taking: {position_return:.1%} return exceeds {self.PROFIT_TAKE_THRESHOLD:.1%} threshold",
                priority=OrderPriority.HIGH,
                suggested_allocation=0.0
            )

        # Check for stop loss (highest priority)
        if current_shares > 0 and position_return <= self.STOP_LOSS_THRESHOLD:
            return TradeDecision(
                action="SELL",
                strength="strong",
                confidence=0.95,
                reasoning=f"Stop loss triggered: {position_return:.1%} return below {self.STOP_LOSS_THRESHOLD:.1%} threshold",
                priority=OrderPriority.HIGH,
                suggested_allocation=0.0
            )

        # Analyze news sentiment
        if news_analysis and ticker in news_analysis.tickers:
            news_sentiment = news_analysis.sentiment.lower()
            news_confidence = news_analysis.confidence

            if news_sentiment == "positive":
                signals.append(("BUY", news_confidence, 0.3, "positive news"))
            elif news_sentiment == "negative":
                signals.append(("SELL", news_confidence, 0.3, "negative news"))

            confidence_sum += news_confidence * 0.3
            weight_sum += 0.3

        # Analyze market sentiment
        if market_analysis:
            # Overall market sentiment
            market_sentiment = market_analysis.sentiment.lower()
            market_confidence = market_analysis.confidence

            if market_sentiment == "bullish":
                signals.append(("BUY", market_confidence, 0.25, "bullish market"))
            elif market_sentiment == "bearish":
                signals.append(("SELL", market_confidence, 0.25, "bearish market"))

            confidence_sum += market_confidence * 0.25
            weight_sum += 0.25

            # Position-specific sentiment if available
            if ticker in market_analysis.position_sentiments:
                position_sentiment = market_analysis.position_sentiments[ticker].lower()
                if position_sentiment == "bullish":
                    signals.append(("BUY", market_confidence, 0.2, f"{ticker} bullish outlook"))
                elif position_sentiment == "bearish":
                    signals.append(("SELL", market_confidence, 0.2, f"{ticker} bearish outlook"))

                confidence_sum += market_confidence * 0.2
                weight_sum += 0.2

        # Analyze risk
        if risk_analysis:
            risk_level = risk_analysis.risk_level.lower()
            risk_confidence = risk_analysis.confidence

            # High risk = sell signal
            if risk_level == "high":
                signals.append(("SELL", risk_confidence, 0.25, "high risk environment"))
                confidence_sum += risk_confidence * 0.25
                weight_sum += 0.25
            elif risk_level == "low" and current_shares == 0:
                signals.append(("BUY", risk_confidence * 0.5, 0.1, "low risk environment"))
                confidence_sum += risk_confidence * 0.5 * 0.1
                weight_sum += 0.1

        # Aggregate signals
        if not signals:
            return TradeDecision(
                action="HOLD",
                strength="weak",
                confidence=0.0,
                reasoning="Insufficient data for trade decision",
                priority=OrderPriority.LOW
            )

        # Count buy/sell signals
        buy_weight = sum(conf * weight for action, conf, weight, _ in signals if action == "BUY")
        sell_weight = sum(conf * weight for action, conf, weight, _ in signals if action == "SELL")

        # Normalize confidence
        overall_confidence = confidence_sum / weight_sum if weight_sum > 0 else 0.0

        # Determine action
        if buy_weight > sell_weight and (buy_weight - sell_weight) > 0.1:
            action = "BUY"
            strength_confidence = buy_weight
        elif sell_weight > buy_weight and (sell_weight - buy_weight) > 0.1:
            action = "SELL"
            strength_confidence = sell_weight
        else:
            action = "HOLD"
            strength_confidence = 0.0

        # Special rule: Bearish market + high risk = strong sell
        if market_analysis and risk_analysis:
            if market_analysis.sentiment.lower() == "bearish" and risk_analysis.risk_level.lower() == "high":
                if current_shares > 0:
                    action = "SELL"
                    strength_confidence = max(strength_confidence, 0.75)
                    signals.append(("SELL", 0.8, 0.3, "bearish market + high risk"))

        # Special rule: Positive news + bullish market + low risk = strong buy
        if news_analysis and market_analysis and risk_analysis:
            if (news_analysis.sentiment.lower() == "positive" and
                market_analysis.sentiment.lower() == "bullish" and
                risk_analysis.risk_level.lower() != "high"):
                if current_shares == 0 or position_value < total_value * self.MAX_POSITION_SIZE:
                    action = "BUY"
                    strength_confidence = max(strength_confidence, 0.75)
                    signals.append(("BUY", 0.85, 0.3, "positive news + bullish market"))

        # Determine strength
        if strength_confidence >= 0.7:
            strength = "strong"
        elif strength_confidence >= 0.5:
            strength = "moderate"
        else:
            strength = "weak"

        # Determine priority
        if strength_confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            priority = OrderPriority.HIGH
        elif strength_confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            priority = OrderPriority.MEDIUM
        else:
            priority = OrderPriority.LOW

        # Build reasoning
        signal_reasons = [reason for _, _, _, reason in signals if _ == action]
        reasoning = f"{strength.title()} {action.lower()} signal: " + ", ".join(signal_reasons[:3])

        # Calculate suggested allocation for buys
        suggested_allocation = None
        if action == "BUY":
            # Base allocation on strength
            if strength == "strong":
                suggested_allocation = 0.10  # 10% for strong signals
            elif strength == "moderate":
                suggested_allocation = 0.05  # 5% for moderate
            else:
                suggested_allocation = 0.03  # 3% for weak

            # Cap at max position size
            current_weight = position_value / total_value if total_value > 0 else 0
            remaining_capacity = self.MAX_POSITION_SIZE - current_weight
            suggested_allocation = min(suggested_allocation, remaining_capacity)

        return TradeDecision(
            action=action,
            strength=strength,
            confidence=overall_confidence,
            reasoning=reasoning,
            priority=priority,
            suggested_allocation=suggested_allocation
        )

    def _create_trade_order(
        self,
        ticker: str,
        decision: TradeDecision,
        holdings: Dict[str, Any],
        total_value: float,
        cash: float,
        current_prices: Optional[Dict[str, float]]
    ) -> Optional[TradeOrder]:
        """
        Create TradeOrder from decision

        Args:
            ticker: Stock ticker
            decision: TradeDecision
            holdings: Current holdings
            total_value: Total portfolio value
            cash: Available cash
            current_prices: Current prices

        Returns:
            TradeOrder or None if invalid
        """
        position = holdings.get(ticker, {})
        current_shares = position.get('shares', 0)
        position_return = position.get('return_pct', 0.0)

        # Convert action to OrderType
        if decision.action == "BUY":
            order_type = OrderType.BUY
        elif decision.action == "SELL":
            order_type = OrderType.SELL
        else:
            return None

        # Calculate shares
        shares = None
        target_value = None

        if order_type == OrderType.BUY:
            if decision.suggested_allocation and total_value > 0:
                target_value = total_value * decision.suggested_allocation
                # Don't buy if we don't have enough cash
                if target_value > cash * 0.95:  # Leave 5% buffer
                    target_value = cash * 0.95

                # Calculate shares if we have price
                if current_prices and ticker in current_prices:
                    shares = int(target_value / current_prices[ticker])
                    if shares == 0:
                        return None  # Not enough for even 1 share

        elif order_type == OrderType.SELL:
            if current_shares > 0:
                shares = current_shares
            else:
                return None  # Can't sell what we don't have

        # Set stop loss and profit target
        stop_loss = None
        profit_target = None

        if order_type == OrderType.BUY and current_prices and ticker in current_prices:
            current_price = current_prices[ticker]
            stop_loss = current_price * (1 + self.STOP_LOSS_THRESHOLD)
            profit_target = current_price * (1 + self.PROFIT_TAKE_THRESHOLD)

        # Create order
        order = TradeOrder(
            ticker=ticker,
            action=order_type,
            shares=shares,
            target_value=target_value,
            reason=decision.reasoning,
            priority=decision.priority,
            stop_loss=stop_loss,
            profit_target=profit_target
        )

        return order

    def _sort_by_priority(self, orders: List[TradeOrder]) -> List[TradeOrder]:
        """Sort orders by priority (HIGH > MEDIUM > LOW)"""
        priority_order = {
            OrderPriority.HIGH: 0,
            OrderPriority.MEDIUM: 1,
            OrderPriority.LOW: 2
        }

        return sorted(orders, key=lambda x: priority_order[x.priority])

    def generate_summary(
        self,
        orders: List[TradeOrder],
        news_analysis: Optional[NewsAnalysis],
        market_analysis: Optional[MarketAnalysis],
        risk_analysis: Optional[RiskAnalysis]
    ) -> str:
        """
        Generate human-readable summary of trade decisions

        Args:
            orders: Generated trade orders
            news_analysis: News analysis results
            market_analysis: Market analysis results
            risk_analysis: Risk analysis results

        Returns:
            Formatted summary string
        """
        summary = []
        summary.append("="*70)
        summary.append("TRADE DECISION SUMMARY")
        summary.append("="*70)

        # Overall market assessment
        summary.append("\nMarket Assessment:")
        if market_analysis:
            summary.append(f"  Sentiment: {market_analysis.sentiment} ({market_analysis.strength})")
            summary.append(f"  Confidence: {market_analysis.confidence:.1%}")

        if risk_analysis:
            summary.append(f"  Risk Level: {risk_analysis.risk_level.upper()}")
            summary.append(f"  Recommended Action: {risk_analysis.recommended_action}")

        if news_analysis:
            summary.append(f"\nNews Sentiment: {news_analysis.sentiment} ({news_analysis.confidence:.1%})")
            if news_analysis.tickers:
                summary.append(f"  Tickers: {', '.join(news_analysis.tickers[:5])}")

        # Trade orders
        summary.append(f"\n{'='*70}")
        summary.append(f"GENERATED ORDERS: {len(orders)}")
        summary.append(f"{'='*70}")

        if not orders:
            summary.append("\nNo trade orders generated. Market conditions suggest HOLD.")
        else:
            # Group by priority
            high_priority = [o for o in orders if o.priority == OrderPriority.HIGH]
            medium_priority = [o for o in orders if o.priority == OrderPriority.MEDIUM]
            low_priority = [o for o in orders if o.priority == OrderPriority.LOW]

            if high_priority:
                summary.append(f"\nHIGH PRIORITY ({len(high_priority)}):")
                for order in high_priority:
                    summary.append(f"  {order.action.value} {order.ticker}")
                    if order.shares:
                        summary.append(f"    Shares: {order.shares}")
                    summary.append(f"    Reason: {order.reason}")

            if medium_priority:
                summary.append(f"\nMEDIUM PRIORITY ({len(medium_priority)}):")
                for order in medium_priority:
                    summary.append(f"  {order.action.value} {order.ticker}")
                    if order.shares:
                        summary.append(f"    Shares: {order.shares}")
                    summary.append(f"    Reason: {order.reason}")

            if low_priority:
                summary.append(f"\nLOW PRIORITY ({len(low_priority)}):")
                for order in low_priority:
                    summary.append(f"  {order.action.value} {order.ticker}")
                    if order.shares:
                        summary.append(f"    Shares: {order.shares}")
                    summary.append(f"    Reason: {order.reason}")

        summary.append(f"\n{'='*70}\n")

        return "\n".join(summary)
