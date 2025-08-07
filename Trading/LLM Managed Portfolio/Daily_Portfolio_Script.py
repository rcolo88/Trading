# Daily Portfolio Data Collection Script
# Run this daily and paste the output to Claude for analysis

import yfinance as yf
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import re
import json
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict
import logging


# Configure logging for trade execution
trade_logger = logging.getLogger('trade_execution')
trade_logger.setLevel(logging.INFO)
handler = logging.FileHandler('trade_execution.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
trade_logger.addHandler(handler)

class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    REDUCE = "REDUCE"
    INCREASE = "INCREASE"

class OrderPriority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

@dataclass
class TradeOrder:
    """Represents a single trade order"""
    ticker: str
    action: OrderType
    shares: Optional[int] = None
    target_weight: Optional[float] = None
    target_value: Optional[float] = None
    reason: str = ""
    priority: OrderPriority = OrderPriority.MEDIUM
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    profit_target: Optional[float] = None

@dataclass
class TradeResult:
    """Represents the result of an executed trade"""
    order: TradeOrder
    executed: bool
    execution_price: Optional[float]
    executed_shares: Optional[int]
    execution_value: Optional[float]
    error_message: Optional[str]
    timestamp: datetime

class DocumentParser:
    """Parse trading recommendations from various document formats"""
    
    def __init__(self):
        # Enhanced patterns to match Claude's analytical language
        self.order_patterns = {
            # Direct action patterns
            'exit_completely': r'(?i)exit\s+([A-Z]+)\s+completely|sell\s+all\s+([A-Z]+)',
            'reduce_position': r'(?i)(?:reduce|trim)\s+([A-Z]+)\s+(?:by\s+)?(\d+)%|([A-Z]+)\s+requires?\s+(?:a\s+)?(\d+)%\s+(?:position\s+)?reduction',
            'hold_position': r'(?i)hold\s+(?:your\s+)?(?:full\s+)?position\s+(?:in\s+)?([A-Z]+)|maintain\s+(?:your\s+)?position\s+(?:in\s+)?([A-Z]+)',
            'take_profits': r'(?i)(?:consider\s+)?taking?\s+(?:partial\s+)?profits?\s+(?:at\s+\d+%\s+gains?\s+)?(?:on\s+|in\s+)?([A-Z]+)|trimming?\s+(\d+)%\s+of\s+(?:this\s+position|([A-Z]+))',
            
            # Traditional patterns
            'buy_pattern': r'(?i)buy\s+(\d+)\s+shares?\s+of\s+([A-Z]+)|buy\s+([A-Z]+)\s+(\d+)\s+shares?',
            'sell_pattern': r'(?i)sell\s+(\d+)\s+shares?\s+of\s+([A-Z]+)|sell\s+([A-Z]+)\s+(\d+)\s+shares?',
            'weight_pattern': r'(?i)(?:set|adjust|rebalance)\s+([A-Z]+)\s+to\s+(\d+(?:\.\d+)?)%',
            
            # Priority actions (Claude often uses this structure)
            'priority_actions': r'(?i)(?:priority\s+)?(?:rebalancing\s+)?actions?[:\s]*\n(?:.*\n)*?(?:\d+\.?\s*)?([A-Z]+)[^a-z]*?(\d+)%',
        }
    
    def parse_text_document(self, text: str) -> List[TradeOrder]:
        """Parse trading orders from analytical text (Claude format)"""
        orders = []
        
        # Claude's analytical format - search entire document
        full_text = text.lower()
        
        # 1. Parse "Exit completely" orders
        exit_matches = re.findall(self.order_patterns['exit_completely'], full_text, re.IGNORECASE)
        for match in exit_matches:
            ticker = match[0] or match[1]  # Handle either pattern match
            if ticker:
                orders.append(TradeOrder(
                    ticker=ticker.upper(),
                    action=OrderType.SELL,
                    shares=None,  # Will sell all shares
                    reason=f"Exit {ticker.upper()} completely - risk management",
                    priority=OrderPriority.HIGH
                ))
        
        # 2. Parse percentage reduction orders
        reduce_matches = re.findall(self.order_patterns['reduce_position'], full_text, re.IGNORECASE)
        for match in reduce_matches:
            if match[0] and match[1]:  # "reduce TICKER by X%"
                ticker, percentage = match[0], match[1]
            elif match[2] and match[3]:  # "TICKER requires X% reduction"
                ticker, percentage = match[2], match[3]
            else:
                continue
                
            orders.append(TradeOrder(
                ticker=ticker.upper(),
                action=OrderType.REDUCE,
                target_weight=100 - float(percentage),  # Reduce by X% means keep (100-X)%
                reason=f"Reduce {ticker.upper()} by {percentage}% - position sizing",
                priority=OrderPriority.HIGH
            ))
        
        # 3. Parse profit-taking orders
        profit_matches = re.findall(self.order_patterns['take_profits'], full_text, re.IGNORECASE)
        for match in profit_matches:
            ticker = match[0] or match[2]  # Handle different match groups
            percentage = match[1] if match[1] else "50"  # Default to 50% if not specified
            
            if ticker:
                orders.append(TradeOrder(
                    ticker=ticker.upper(),
                    action=OrderType.REDUCE,
                    target_weight=100 - float(percentage),
                    reason=f"Take partial profits on {ticker.upper()}",
                    priority=OrderPriority.MEDIUM
                ))
        
        # 4. Traditional buy/sell patterns
        buy_matches = re.findall(self.order_patterns['buy_pattern'], full_text, re.IGNORECASE)
        for match in buy_matches:
            if match[0] and match[1]:
                shares, ticker = int(match[0]), match[1]
            elif match[2] and match[3]:
                ticker, shares = match[2], int(match[3])
            else:
                continue
            
            orders.append(TradeOrder(
                ticker=ticker.upper(),
                action=OrderType.BUY,
                shares=shares,
                reason="Buy recommendation from document",
                priority=OrderPriority.MEDIUM
            ))
        
        # 5. Extract priority actions section if it exists
        priority_section = self._extract_priority_actions(text)
        if priority_section:
            priority_orders = self._parse_priority_section(priority_section)
            orders.extend(priority_orders)
        
        return orders
    
    def parse_json_document(self, json_text: str) -> List[TradeOrder]:
        """Parse trading orders from JSON format"""
        try:
            data = json.loads(json_text)
            orders = []
            
            # Expected JSON structure
            for order_data in data.get('orders', []):
                order = TradeOrder(
                    ticker=order_data['ticker'],
                    action=OrderType(order_data['action'].upper()),
                    shares=order_data.get('shares'),
                    target_weight=order_data.get('target_weight'),
                    target_value=order_data.get('target_value'),
                    reason=order_data.get('reason', ''),
                    priority=OrderPriority(order_data.get('priority', 'MEDIUM').upper()),
                    limit_price=order_data.get('limit_price'),
                    stop_loss=order_data.get('stop_loss'),
                    profit_target=order_data.get('profit_target')
                )
                orders.append(order)
            
            return orders
        except json.JSONDecodeError as e:
            trade_logger.error(f"Failed to parse JSON document: {e}")
            return []
    
    def _extract_priority_actions(self, text: str) -> str:
        """Extract the priority actions section from Claude's analysis"""
        # Look for sections like "Priority rebalancing actions:"
        patterns = [
            r'priority\s+(?:rebalancing\s+)?actions?[:\s]*\n(.*?)(?=\n\n|\n###|\nTarget|\Z)',
            r'immediate\s+action\s+required[:\s]*\n(.*?)(?=\n\n|\n###|\Z)',
            r'rebalancing\s+recommendations[:\s]*\n(.*?)(?=\n\n|\n###|\Z)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1)
        return ""
    
    def _parse_priority_section(self, section_text: str) -> List[TradeOrder]:
        """Parse the priority actions section for specific orders"""
        orders = []
        lines = section_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Parse lines like "1. Exit SOUN completely (+$202 in proceeds)"
            exit_match = re.search(r'(?:\d+\.\s*)?exit\s+([A-Z]+)\s+completely', line, re.IGNORECASE)
            if exit_match:
                ticker = exit_match.group(1)
                orders.append(TradeOrder(
                    ticker=ticker,
                    action=OrderType.SELL,
                    shares=None,
                    reason="Priority action: Exit completely",
                    priority=OrderPriority.HIGH
                ))
                continue
            
            # Parse lines like "2. Reduce CYTK by 50% (+$104 in proceeds)"
            reduce_match = re.search(r'(?:\d+\.\s*)?reduce\s+([A-Z]+)\s+by\s+(\d+)%', line, re.IGNORECASE)
            if reduce_match:
                ticker, percentage = reduce_match.groups()
                orders.append(TradeOrder(
                    ticker=ticker,
                    action=OrderType.REDUCE,
                    target_weight=100 - float(percentage),
                    reason=f"Priority action: Reduce by {percentage}%",
                    priority=OrderPriority.HIGH
                ))
                continue
            
            # Parse lines like "3. Trim QS by 50% (+$100 in proceeds)"
            trim_match = re.search(r'(?:\d+\.\s*)?trim\s+([A-Z]+)\s+by\s+(\d+)%', line, re.IGNORECASE)
            if trim_match:
                ticker, percentage = trim_match.groups()
                orders.append(TradeOrder(
                    ticker=ticker,
                    action=OrderType.REDUCE,
                    target_weight=100 - float(percentage),
                    reason=f"Priority action: Trim by {percentage}%",
                    priority=OrderPriority.HIGH
                ))
        
        return orders

class TradeExecutor:
    """Execute trades based on parsed orders"""
    
    def __init__(self, portfolio_reporter):
        self.portfolio = portfolio_reporter
        self.paper_trading = True  # Set to False for live trading
        self.executed_trades = []
        self.failed_trades = []
    
    def execute_orders(self, orders: List[TradeOrder]) -> List[TradeResult]:
        """Execute a list of trade orders"""
        results = []
        
        # Sort orders by priority (HIGH -> MEDIUM -> LOW)
        sorted_orders = sorted(orders, key=lambda x: x.priority.value)
        
        # Get current market data
        current_prices, _, _ = self.portfolio.fetch_current_data()
        if not current_prices:
            trade_logger.error("Failed to fetch current market data")
            return []
        
        for order in sorted_orders:
            result = self._execute_single_order(order, current_prices)
            results.append(result)
            
            if result.executed:
                self.executed_trades.append(result)
                # Update portfolio holdings
                self._update_portfolio_holdings(result)
            else:
                self.failed_trades.append(result)
        
        return results
    
    def _execute_single_order(self, order: TradeOrder, current_prices: Dict) -> TradeResult:
        """Execute a single trade order"""
        timestamp = datetime.now()
        
        # Validate ticker exists in market data
        if order.ticker not in current_prices:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=None,
                executed_shares=None,
                execution_value=None,
                error_message=f"No market data for {order.ticker}",
                timestamp=timestamp
            )
        
        current_price = current_prices[order.ticker]
        
        # Calculate shares to trade
        shares_to_trade = self._calculate_shares_to_trade(order, current_price)
        if shares_to_trade == 0:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message="No shares to trade",
                timestamp=timestamp
            )
        
        # Validate sufficient funds/shares
        validation_error = self._validate_order(order, shares_to_trade, current_price)
        if validation_error:
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message=validation_error,
                timestamp=timestamp
            )
        
        # Execute the trade (paper trading for now)
        if self.paper_trading:
            execution_price = current_price
            execution_value = shares_to_trade * execution_price
            
            trade_logger.info(f"PAPER TRADE: {order.action.value} {shares_to_trade} shares of {order.ticker} at ${execution_price:.2f}")
            
            return TradeResult(
                order=order,
                executed=True,
                execution_price=execution_price,
                executed_shares=shares_to_trade,
                execution_value=execution_value,
                error_message=None,
                timestamp=timestamp
            )
        else:
            # TODO: Implement live trading through broker API
            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message="Live trading not implemented",
                timestamp=timestamp
            )
    
    def _calculate_shares_to_trade(self, order: TradeOrder, current_price: float) -> int:
        """Calculate the number of shares to trade"""
        if order.shares is not None:
            return abs(order.shares)
        
        if order.target_weight is not None:
            total_value = self.portfolio.cash + sum(
                pos['shares'] * current_price 
                for ticker, pos in self.portfolio.holdings.items() 
                if ticker in [order.ticker] # This needs current prices for all holdings
            )
            target_value = total_value * (order.target_weight / 100)
            current_position_value = 0
            
            if order.ticker in self.portfolio.holdings:
                current_position_value = self.portfolio.holdings[order.ticker]['shares'] * current_price
            
            value_difference = target_value - current_position_value
            return abs(int(value_difference / current_price))
        
        if order.target_value is not None:
            return int(order.target_value / current_price)
        
        # For sell all orders
        if order.action == OrderType.SELL and order.ticker in self.portfolio.holdings:
            return self.portfolio.holdings[order.ticker]['shares']
        
        return 0
    
    def _validate_order(self, order: TradeOrder, shares: int, price: float) -> Optional[str]:
        """Validate if order can be executed"""
        if order.action in [OrderType.BUY, OrderType.INCREASE]:
            required_cash = shares * price
            if required_cash > self.portfolio.cash:
                return f"Insufficient funds: Need ${required_cash:.2f}, have ${self.portfolio.cash:.2f}"
        
        elif order.action in [OrderType.SELL, OrderType.REDUCE]:
            if order.ticker not in self.portfolio.holdings:
                return f"No position in {order.ticker} to sell"
            
            available_shares = self.portfolio.holdings[order.ticker]['shares']
            if shares > available_shares:
                return f"Insufficient shares: Need {shares}, have {available_shares}"
        
        return None
    
    def _update_portfolio_holdings(self, result: TradeResult):
        """Update portfolio holdings after successful trade"""
        if not result.executed:
            return
        
        order = result.order
        shares = result.executed_shares
        price = result.execution_price
        value = result.execution_value
        
        if order.action in [OrderType.BUY, OrderType.INCREASE]:
            # Add to or create position
            if order.ticker in self.portfolio.holdings:
                current_shares = self.portfolio.holdings[order.ticker]['shares']
                current_basis = self.portfolio.holdings[order.ticker]['shares'] * self.portfolio.holdings[order.ticker]['entry_price']
                new_basis = current_basis + value
                new_shares = current_shares + shares
                new_avg_price = new_basis / new_shares
                
                self.portfolio.holdings[order.ticker].update({
                    'shares': new_shares,
                    'entry_price': new_avg_price,
                    'allocation': new_basis
                })
            else:
                self.portfolio.holdings[order.ticker] = {
                    'shares': shares,
                    'entry_price': price,
                    'allocation': value
                }
            
            # Reduce cash
            self.portfolio.cash -= value
            
        elif order.action in [OrderType.SELL, OrderType.REDUCE]:
            if order.ticker in self.portfolio.holdings:
                current_shares = self.portfolio.holdings[order.ticker]['shares']
                
                if shares >= current_shares:
                    # Sell entire position
                    del self.portfolio.holdings[order.ticker]
                else:
                    # Reduce position
                    remaining_shares = current_shares - shares
                    self.portfolio.holdings[order.ticker]['shares'] = remaining_shares
                    # Allocation adjusts proportionally
                    original_allocation = self.portfolio.holdings[order.ticker]['allocation']
                    self.portfolio.holdings[order.ticker]['allocation'] = original_allocation * (remaining_shares / current_shares)
                
                # Add cash from sale
                self.portfolio.cash += value

class AutomatedTradingSystem:
    """Main system that orchestrates document parsing and trade execution"""
    
    def __init__(self, portfolio_reporter):
        self.portfolio = portfolio_reporter
        self.parser = DocumentParser()
        self.executor = TradeExecutor(portfolio_reporter)
    
    def execute_from_document(self, document_path: str) -> List[TradeResult]:
        """Execute trades from a document file"""
        try:
            with open(document_path, 'r') as f:
                content = f.read()
            
            # Determine document format and parse accordingly
            if document_path.endswith('.json'):
                orders = self.parser.parse_json_document(content)
            else:
                orders = self.parser.parse_text_document(content)
            
            if not orders:
                trade_logger.warning("No valid orders found in document")
                return []
            
            # Log parsed orders
            trade_logger.info(f"Parsed {len(orders)} orders from document")
            for order in orders:
                trade_logger.info(f"Order: {order.action.value} {order.ticker} - {order.reason}")
            
            # Execute orders
            results = self.executor.execute_orders(orders)
            
            # Log execution results
            executed_count = sum(1 for r in results if r.executed)
            failed_count = len(results) - executed_count
            
            trade_logger.info(f"Execution complete: {executed_count} executed, {failed_count} failed")
            
            return results
            
        except FileNotFoundError:
            trade_logger.error(f"Document not found: {document_path}")
            return []
        except Exception as e:
            trade_logger.error(f"Error executing from document: {e}")
            return []
    
    def generate_execution_report(self, results: List[TradeResult]) -> str:
        """Generate a human-readable execution report"""
        report = []
        report.append("=" * 60)
        report.append("AUTOMATED TRADE EXECUTION REPORT")
        report.append("=" * 60)
        report.append(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Orders: {len(results)}")
        
        executed = [r for r in results if r.executed]
        failed = [r for r in results if not r.executed]
        
        report.append(f"Executed: {len(executed)}")
        report.append(f"Failed: {len(failed)}")
        report.append("")
        
        if executed:
            report.append("EXECUTED TRADES:")
            report.append("-" * 40)
            total_value = 0
            for result in executed:
                order = result.order
                report.append(f"{order.action.value} {result.executed_shares} shares of {order.ticker}")
                report.append(f"  Price: ${result.execution_price:.2f}")
                report.append(f"  Value: ${result.execution_value:.2f}")
                report.append(f"  Reason: {order.reason}")
                report.append("")
                total_value += result.execution_value
            
            report.append(f"Total Trade Value: ${total_value:.2f}")
            report.append("")
        
        if failed:
            report.append("FAILED TRADES:")
            report.append("-" * 40)
            for result in failed:
                order = result.order
                report.append(f"{order.action.value} {order.ticker}: {result.error_message}")
            report.append("")
        
        # Updated portfolio summary
        report.append("UPDATED PORTFOLIO SUMMARY:")
        report.append("-" * 40)
        report.append(f"Cash Available: ${self.portfolio.cash:.2f}")
        report.append("Current Holdings:")
        for ticker, position in self.portfolio.holdings.items():
            report.append(f"  {ticker}: {position['shares']} shares @ ${position['entry_price']:.2f}")
        
        return "\n".join(report)

# Extension to existing DailyPortfolioReport class
def add_automated_trading_to_portfolio_reporter():
    """
    Add this method to your existing DailyPortfolioReport class
    """
    def _handle_insufficient_cash(self, order: TradeOrder, current_price: float, 
                              available_cash: float, timestamp: datetime) -> TradeResult:
        """Handle insufficient cash scenarios based on configuration"""
    
        required_cash = order.shares * current_price
        max_affordable_shares = int(available_cash / current_price) if available_cash >= current_price else 0
        affordability_ratio = (max_affordable_shares * current_price) / required_cash if required_cash > 0 else 0
        
        print(f"⚠️  INSUFFICIENT CASH for {order.ticker}:")
        print(f"   Requested: {order.shares} shares (${required_cash:.2f})")
        print(f"   Available: ${available_cash:.2f} (after ${self.min_cash_reserve:.2f} reserve)")
        print(f"   Max affordable: {max_affordable_shares} shares ({affordability_ratio:.1%} of order)")
        
        # Check if partial fills are disabled for this order
        if not order.allow_partial_fill:
            return TradeResult(
                order=order, executed=False, execution_price=current_price,
                executed_shares=0, execution_value=0, timestamp=timestamp,
                error_message=f"Order does not allow partial fills. Need ${required_cash:.2f}, have ${available_cash:.2f}"
            )
        
        # Handle based on partial fill mode
        if self.partial_fill_mode == PartialFillMode.REJECT:
            return TradeResult(
                order=order, executed=False, execution_price=current_price,
                executed_shares=0, execution_value=0, timestamp=timestamp,
                error_message=f"Partial fills disabled. Need ${required_cash:.2f}, have ${available_cash:.2f}"
            )
        
        elif self.partial_fill_mode == PartialFillMode.AUTOMATIC:
            if max_affordable_shares > 0:
                print(f"✅ AUTO-FILLING: {max_affordable_shares} shares")
                return self._execute_partial_fill(order, max_affordable_shares, current_price, timestamp)
            else:
                return TradeResult(
                    order=order, executed=False, execution_price=current_price,
                    executed_shares=0, execution_value=0, timestamp=timestamp,
                    error_message=f"Cannot afford even 1 share. Need ${current_price:.2f}, have ${available_cash:.2f}"
                )
        
        elif self.partial_fill_mode == PartialFillMode.SMART:
            if affordability_ratio >= self.partial_fill_threshold:
                print(f"✅ SMART AUTO-FILL: {max_affordable_shares} shares ({affordability_ratio:.1%} ≥ {self.partial_fill_threshold:.1%})")
                return self._execute_partial_fill(order, max_affordable_shares, current_price, timestamp)
            else:
                return self._ask_partial_fill_confirmation(order, max_affordable_shares, current_price, 
                                                        available_cash, affordability_ratio, timestamp)
        
        elif self.partial_fill_mode == PartialFillMode.ASK_CONFIRMATION:
            return self._ask_partial_fill_confirmation(order, max_affordable_shares, current_price,
                                                    available_cash, affordability_ratio, timestamp)
        
        # Fallback to reject
        return TradeResult(
            order=order, executed=False, execution_price=current_price,
            executed_shares=0, execution_value=0, timestamp=timestamp,
            error_message=f"Unknown partial fill mode: {self.partial_fill_mode}"
        )

def _execute_partial_fill(self, order: TradeOrder, shares: int, price: float, timestamp: datetime) -> TradeResult:
    """Execute a partial fill order"""
    if shares <= 0:
        return TradeResult(
            order=order, executed=False, execution_price=price,
            executed_shares=0, execution_value=0, timestamp=timestamp,
            error_message="No shares affordable for partial fill"
        )
    
    execution_value = shares * price
    print(f"📥 PAPER TRADE: BOUGHT {shares} shares of {order.ticker} at ${price:.2f} = ${execution_value:.2f} (PARTIAL FILL)")
    
    return TradeResult(
        order=order,
        executed=True,
        execution_price=price,
        executed_shares=shares,
        execution_value=execution_value,
        error_message=None,
        timestamp=timestamp
    )

def _ask_partial_fill_confirmation(self, order: TradeOrder, max_shares: int, price: float,
                                 available_cash: float, affordability_ratio: float, 
                                 timestamp: datetime) -> TradeResult:
    """Ask user for confirmation on partial fill"""
    
    if max_shares <= 0:
        return TradeResult(
            order=order, executed=False, execution_price=price,
            executed_shares=0, execution_value=0, timestamp=timestamp,
            error_message=f"Cannot afford even 1 share: ${available_cash:.2f} available, ${price:.2f} needed"
        )
    
    print(f"🤔 PARTIAL FILL DECISION NEEDED:")
    print(f"   Can afford {max_shares}/{order.shares} shares ({affordability_ratio:.1%} of requested)")
    print(f"   Cost: ${max_shares * price:.2f} of ${available_cash:.2f} available")
    
    while True:
        response = input(f"   Execute partial fill of {max_shares} {order.ticker} shares? (y/n/s=skip): ").lower().strip()
        
        if response in ['y', 'yes']:
            return self._execute_partial_fill(order, max_shares, price, timestamp)
        elif response in ['n', 'no', 's', 'skip']:
            return TradeResult(
                order=order, executed=False, execution_price=price,
                executed_shares=0, execution_value=0, timestamp=timestamp,
                error_message=f"Partial fill declined by user"
            )
        else:
            print("   Please enter 'y' for yes, 'n' for no, or 's' to skip")

def set_partial_fill_mode(self, mode: PartialFillMode, min_cash_reserve: float = None, 
                          threshold: float = None):
    """Configure partial fill behavior"""
    self.partial_fill_mode = mode
    if min_cash_reserve is not None:
        self.min_cash_reserve = min_cash_reserve
    if threshold is not None:
        self.partial_fill_threshold = threshold
    
    print(f"📊 Partial Fill Configuration Updated:")
    print(f"   Mode: {mode.value}")
    print(f"   Cash Reserve: ${self.min_cash_reserve:.2f}")
    if mode == PartialFillMode.SMART:
        print(f"   Auto-fill threshold: {self.partial_fill_threshold:.1%}")

    """Validate cash flow before executing trades"""
    print(f"\n💰 CASH FLOW ANALYSIS:")
    print("=" * 40)
    
    simulated_cash = self.cash
    validation_results = {
        'feasible': True,
        'total_sells': 0,
        'total_buys': 0,
        'final_cash': 0,
        'warnings': [],
        'phase_results': {}
    }
    
    execution_phases = self._prioritize_orders_for_cash_flow(orders)
    
    for phase_name, phase_orders in execution_phases.items():
        if not phase_orders or "HOLD" in phase_name:
            continue
            
        phase_sells = 0
        phase_buys = 0
        phase_warnings = []
        
        print(f"\n📋 {phase_name}:")
        
        for order in phase_orders:
            if order.ticker not in current_prices:
                phase_warnings.append(f"No price data for {order.ticker}")
                continue
                
            current_price = current_prices[order.ticker]
            
            if order.action in [OrderType.SELL, OrderType.REDUCE]:
                if order.ticker not in self.holdings:
                    phase_warnings.append(f"Cannot sell {order.ticker} - no position")
                    continue
                
                available_shares = self.holdings[order.ticker]['shares']
                
                if order.action == OrderType.REDUCE and order.target_weight:
                    shares_to_sell = available_shares - int(available_shares * order.target_weight / 100)
                else:
                    shares_to_sell = min(order.shares or available_shares, available_shares)
                
                proceeds = shares_to_sell * current_price
                simulated_cash += proceeds
                phase_sells += proceeds
                
                print(f"   📤 Sell {shares_to_sell} {order.ticker}: +${proceeds:.2f} → ${simulated_cash:.2f}")
                
            elif order.action == OrderType.BUY:
                required_cash = order.shares * current_price
                
                if required_cash > simulated_cash:
                    # Check if partial fill is possible
                    if simulated_cash >= current_price:
                        max_shares = int(simulated_cash / current_price)
                        partial_cost = max_shares * current_price
                        phase_warnings.append(f"Partial fill for {order.ticker}: {max_shares}/{order.shares} shares")
                        simulated_cash -= partial_cost
                        phase_buys += partial_cost
                        print(f"   📥 Buy {max_shares} {order.ticker} (partial): -${partial_cost:.2f} → ${simulated_cash:.2f}")
                    else:
                        validation_results['feasible'] = False
                        phase_warnings.append(f"Cannot afford any {order.ticker} shares")
                        print(f"   ❌ Cannot buy {order.ticker}: Need ${required_cash:.2f}, have ${simulated_cash:.2f}")
                else:
                    simulated_cash -= required_cash
                    phase_buys += required_cash
                    print(f"   📥 Buy {order.shares} {order.ticker}: -${required_cash:.2f} → ${simulated_cash:.2f}")
        
        validation_results['phase_results'][phase_name] = {
            'sells': phase_sells,
            'buys': phase_buys, 
            'warnings': phase_warnings
        }
        
        validation_results['total_sells'] += phase_sells
        validation_results['total_buys'] += phase_buys
        validation_results['warnings'].extend(phase_warnings)
    
    validation_results['final_cash'] = simulated_cash
    
    print(f"\n💰 CASH FLOW SUMMARY:")
    print(f"   Starting cash: ${self.cash:.2f}")
    print(f"   Total from sells: +${validation_results['total_sells']:.2f}")
    print(f"   Total for buys: -${validation_results['total_buys']:.2f}")
    print(f"   Final cash: ${validation_results['final_cash']:.2f}")
    print(f"   Net change: ${validation_results['final_cash'] - self.cash:+.2f}")
    
    if validation_results['warnings']:
        print(f"\n⚠️  WARNINGS ({len(validation_results['warnings'])}):")
        for warning in validation_results['warnings']:
            print(f"   • {warning}")
    
    if validation_results['feasible']:
        print(f"\n✅ All trades are feasible with current cash flow strategy")
    else:
        print(f"\n❌ Some trades cannot be executed due to insufficient cash")
    
    return validation_results
        """Execute automated trading from document"""
        trading_system = AutomatedTradingSystem(self)
        results = trading_system.execute_from_document(document_path)
        
        if results:
            report = trading_system.generate_execution_report(results)
            print(report)
            
            # Save execution report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f'trade_execution_report_{timestamp}.txt'
            with open(report_filename, 'w') as f:
                f.write(report)
            
            trade_logger.info(f"Execution report saved to {report_filename}")
        
        return results

# Test function to demonstrate parsing of the uploaded document
def test_claude_document_parsing():
    """Test parsing of Claude's analytical document format"""
    
    # Sample text from your uploaded document
    sample_text = """
    Immediate action required: Exit SOUN today, reduce CYTK exposure
    
    Exit SOUN completely - the risk-reward is heavily skewed against you with earnings volatility adding unpredictable movement to already deteriorating technicals.
    
    CYTK (Cytokinetics) requires a 50% position reduction despite earnings today at 4:00 PM ET.
    
    QS (+2.59%) presents a profit-taking opportunity after surging 315% from recent lows. The extreme volatility and negative analyst consensus suggest trimming 50% of this position to lock in gains.
    
    Hold your full position as NVDA continues dominating AI infrastructure.
    
    Maintain your position as RIG shows stabilizing fundamentals.
    
    Priority rebalancing actions:
    1. Exit SOUN completely (+$202 in proceeds)
    2. Reduce CYTK by 50% (+$104 in proceeds)  
    3. Trim QS by 50% (+$100 in proceeds)
    """
    
    parser = DocumentParser()
    orders = parser.parse_text_document(sample_text)
    
    print("PARSED ORDERS FROM CLAUDE DOCUMENT:")
    print("=" * 50)
    
    for i, order in enumerate(orders, 1):
        print(f"{i}. {order.action.value} {order.ticker}")
        if order.shares:
            print(f"   Shares: {order.shares}")
        if order.target_weight:
            print(f"   Target Weight: {order.target_weight}%")
        print(f"   Reason: {order.reason}")
        print(f"   Priority: {order.priority.value}")
        print()
    
    return orders

class DailyPortfolioReport:
    def __init__(self):
        # Updated portfolio holdings (from your corrected allocation)
        self.holdings = {
            'IONS': {'shares': 3, 'entry_price': 37.01, 'allocation': 111.03},  # Reduced from 4 shares
            'CRGY': {'shares': 26, 'entry_price': 9.10, 'allocation': 236.60},  # No change
            'SERV': {'shares': 23, 'entry_price': 10.15, 'allocation': 233.45}, # No change
            'CYTK': {'shares': 6, 'entry_price': 36.58, 'allocation': 219.48},  # No change
            'SOUN': {'shares': 19, 'entry_price': 11.01, 'allocation': 209.19}, # No change
            'QS': {'shares': 23, 'entry_price': 8.50, 'allocation': 138.00},    # No change
            'RIG': {'shares': 65, 'entry_price': 3.00, 'allocation': 195.00},   # No change
            'AMD': {'shares': 1, 'entry_price': 176.78, 'allocation': 176.78},  # No change
            'NVDA': {'shares': 1, 'entry_price': 175.00, 'allocation': 135.00}, # NEW POSITION
            'GOOGL': {'shares': 1, 'entry_price': 193.00, 'allocation': 193.00} # NEW POSITION
        }

        self.benchmarks = ['SPY', 'IWM', 'VIX']
        self.total_investment = 1964.58  # Unchanged - original investment
        self.cash = 2.34  # Minimal cash remaining
    
    def fetch_data_individually(self, tickers):
        """Fallback method to fetch data for each ticker individually"""
        
        print("🔄 Fetching tickers individually...")
        
        price_data_dict = {}
        successful_tickers = []
        
        for ticker in tickers:
            # Use ^VIX for VIX data
            fetch_ticker = '^VIX' if ticker == 'VIX' else ticker
            
            try:
                print(f"   Fetching {ticker}...")
                start_fetch_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                ticker_data = yf.download(fetch_ticker, start=start_fetch_date, progress=False, auto_adjust=True)
                
                if not ticker_data.empty:
                    if 'Close' in ticker_data.columns:
                        price_data_dict[ticker] = ticker_data['Close']
                    elif 'Adj Close' in ticker_data.columns:
                        price_data_dict[ticker] = ticker_data['Adj Close']
                    else:
                        numeric_cols = ticker_data.select_dtypes(include=[np.number]).columns
                        if len(numeric_cols) > 0:
                            price_data_dict[ticker] = ticker_data[numeric_cols[0]]
                    
                    successful_tickers.append(ticker)
                else:
                    print(f"   ⚠️  No data for {ticker}")
                    
            except Exception as e:
                print(f"   ❌ Failed to fetch {ticker}: {e}")
        
        if price_data_dict:
            self.price_data = pd.DataFrame(price_data_dict)
            self.price_data = self.price_data.fillna(method='ffill').fillna(method='bfill')
            
            # Initialize empty volume data
            self.volume_data = pd.DataFrame()
            
            print(f"✅ Successfully fetched {len(successful_tickers)} out of {len(tickers)} tickers")
            print(f"📊 Available data: {successful_tickers}")
            
            if len(self.price_data) > 0:
                print(f"📅 Data range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
                return True  # Keep returning True for success
        
        print("❌ Could not fetch any valid data")
        self.price_data = pd.DataFrame()  # Ensure empty DataFrame
        self.volume_data = pd.DataFrame()  # Ensure empty DataFrame
        return False

    def fetch_current_data(self):
        """Fetch current price data for all holdings and benchmarks"""
        
        print("📡 Fetching current market data...")
        
        # Get all tickers
        portfolio_tickers = list(self.holdings.keys())
        benchmark_tickers = ['SPY', 'IWM']  # Remove VIX for now
        all_tickers = portfolio_tickers + benchmark_tickers
        
        print(f"🎯 Fetching data for tickers: {all_tickers}")
        
        try:
            # Fetch data with more robust handling
            start_fetch_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            raw_data = yf.download(all_tickers, start=start_fetch_date, progress=False, auto_adjust=True)
            
            # Handle different data structures from yfinance
            if raw_data.empty:
                print("❌ No data returned from yfinance")
                return None, None, None  # Return tuple instead of False
            
            # Handle multi-ticker vs single ticker cases
            if len(all_tickers) == 1:
                if 'Adj Close' in raw_data.columns:
                    self.price_data = pd.DataFrame({all_tickers[0]: raw_data['Adj Close']})
                else:
                    self.price_data = pd.DataFrame({all_tickers[0]: raw_data['Close']})
            else:
                if isinstance(raw_data.columns, pd.MultiIndex):
                    if 'Adj Close' in raw_data.columns.get_level_values(0):
                        self.price_data = raw_data['Adj Close']
                    elif 'Close' in raw_data.columns.get_level_values(0):
                        self.price_data = raw_data['Close']
                    else:
                        print("❌ Could not find price data columns")
                        return None, None, None  # Return tuple instead of False
                else:
                    self.price_data = raw_data
            
            # Get volume data separately (excluding VIX which doesn't have volume)
            try:
                volume_raw = yf.download(all_tickers, start=start_fetch_date, progress=False, auto_adjust=True)
                if isinstance(volume_raw.columns, pd.MultiIndex) and 'Volume' in volume_raw.columns.get_level_values(0):
                    volume_data = volume_raw['Volume']
                else:
                    volume_data = pd.DataFrame()  # Empty if volume data unavailable
            except:
                volume_data = pd.DataFrame()
            
            # Try to get VIX separately using alternative ticker
            try:
                print("🔍 Attempting to fetch VIX data separately...")
                vix_data = yf.download('^VIX', start=start_fetch_date, progress=False, auto_adjust=True)
                if not vix_data.empty:
                    if 'Close' in vix_data.columns:
                        vix_prices = vix_data['Close']
                    else:
                        vix_prices = vix_data.iloc[:, 0]  # Take first column
                    
                    # Add VIX to price data
                    self.price_data['VIX'] = vix_prices
                    print("✅ VIX data fetched successfully using ^VIX")
                else:
                    print("⚠️  VIX data unavailable - continuing without VIX")
            except Exception as e:
                print(f"⚠️  VIX fetch failed: {e} - continuing without VIX")
            
            # Clean up data
            self.price_data = self.price_data.fillna(method='ffill').fillna(method='bfill')
            
            # Store volume data
            self.volume_data = volume_data
            
            # Verify we have some data
            if self.price_data.empty:
                print("❌ Price data is empty after processing")
                return None, None, None  # Return tuple instead of False
            
            print(f"✅ Successfully fetched data for {len(self.price_data.columns)} securities")
            print(f"📅 Data range: {self.price_data.index[0].date()} to {self.price_data.index[-1].date()}")
            print(f"📊 Available tickers: {list(self.price_data.columns)}")
            
            # Extract current prices (most recent row)
            current_prices = self.price_data.iloc[-1].to_dict()
            
            # Return the tuple that generate_report expects
            return current_prices, self.volume_data, self.price_data
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            print("🔄 Trying alternative approach...")
            
            # Alternative approach: fetch tickers individually
            success = self.fetch_data_individually(all_tickers + ['^VIX'])
            if success:
                # If successful, extract and return the data
                current_prices = self.price_data.iloc[-1].to_dict() if not self.price_data.empty else {}
                return current_prices, self.volume_data, self.price_data
            else:
                return None, None, None

    def calculate_position_metrics(self, current_prices):
        """Calculate key metrics for each position"""
        positions = []
        
        # STEP 1: Calculate the COMPLETE total portfolio value FIRST
        total_current_value = self.cash
        position_values = {}
        total_cost_basis = 0  # Track actual total investment
        
        # First pass: Calculate all position values and total
        for ticker, position in self.holdings.items():
            if ticker in current_prices:
                current_price = current_prices[ticker]
                current_value = position['shares'] * current_price
                cost_basis = position['shares'] * position['entry_price']
                position_values[ticker] = {
                    'current_price': current_price,
                    'current_value': current_value,
                    'cost_basis': cost_basis
                }
                total_current_value += current_value
                total_cost_basis += cost_basis
        
        # STEP 2: Now calculate metrics using the FINAL total for all positions
        for ticker, position in self.holdings.items():
            if ticker in position_values:
                pos_data = position_values[ticker]
                current_price = pos_data['current_price']
                current_value = pos_data['current_value']
                cost_basis = pos_data['cost_basis']
                
                # P&L calculations - FIXED to use actual cost basis
                pnl_dollar = current_value - cost_basis
                pnl_percent = (pnl_dollar / cost_basis) * 100
                daily_change = ((current_price - position['entry_price']) / position['entry_price']) * 100
                
                # ✅ FIXED: Use the complete total for weight calculations
                current_weight = (current_value / total_current_value) * 100 if total_current_value > 0 else 0
                target_weight = (cost_basis / total_cost_basis) * 100  # Fixed to use actual total cost basis
                weight_drift = current_weight - target_weight
                
                positions.append({
                    'ticker': ticker,
                    'shares': position['shares'],
                    'entry_price': position['entry_price'],
                    'current_price': current_price,
                    'current_value': current_value,
                    'cost_basis': cost_basis,
                    'pnl_dollar': pnl_dollar,
                    'pnl_percent': pnl_percent,
                    'daily_change': daily_change,
                    'current_weight': current_weight,
                    'target_weight': target_weight,
                    'weight_drift': weight_drift
                })
        
        return positions, total_current_value, total_cost_basis

    def check_alerts(self, positions):
        """Check for stop-loss and profit target alerts"""
        alerts = []
        
        stop_loss_targets = {
            'CYTK': -18, 'AMD': -13, 'IONS': -19, 'SOUN': -20,
            'QS': -25, 'RIG': -20, 'CRGY': -20, 'SERV': -20
        }
        
        profit_targets = {
            'CYTK': 40, 'AMD': 40, 'IONS': 40, 'SOUN': 50,
            'QS': 100, 'RIG': 40, 'CRGY': 30, 'SERV': 50
        }
        
        for pos in positions:
            ticker = pos['ticker']
            pnl_pct = pos['pnl_percent']
            
            if ticker in stop_loss_targets and pnl_pct <= stop_loss_targets[ticker]:
                alerts.append(f"🔴 STOP LOSS: {ticker} at {pnl_pct:.1f}% (target: {stop_loss_targets[ticker]}%)")
            
            if ticker in profit_targets and pnl_pct >= profit_targets[ticker]:
                alerts.append(f"🟢 PROFIT TARGET: {ticker} at {pnl_pct:.1f}% (target: {profit_targets[ticker]}%)")
        
        return alerts
    
    def get_volume_alerts(self, volume_data, price_data):
        """Check for unusual volume activity"""
        volume_alerts = []
        
        # Handle case where volume_data might be a Series instead of DataFrame
        if volume_data is None:
            return volume_alerts
        
        # Convert Series to DataFrame if needed
        if isinstance(volume_data, pd.Series):
            return volume_alerts  # Skip volume analysis if data structure is unexpected
        
        for ticker in self.holdings.keys():
            if ticker in volume_data.columns and len(volume_data[ticker]) >= 5:
                recent_volume = volume_data[ticker].dropna()
                if len(recent_volume) >= 5:
                    current_volume = recent_volume.iloc[-1]
                    avg_volume = recent_volume.iloc[-5:-1].mean()
                    
                    if current_volume > avg_volume * 2:  # 2x average volume
                        if ticker in price_data.columns and len(price_data[ticker]) >= 2:
                            price_change = ((price_data[ticker].iloc[-1] - price_data[ticker].iloc[-2]) / price_data[ticker].iloc[-2]) * 100
                            volume_alerts.append(f"📊 HIGH VOLUME: {ticker} - {current_volume/1000000:.1f}M vs {avg_volume/1000000:.1f}M avg (Price: {price_change:+.1f}%)")
        
        return volume_alerts
    
    def generate_report(self):
        """Generate complete daily report"""
        print("=" * 60)
        print(f"📊 DAILY PORTFOLIO REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        
        # Fetch data
        current_prices, volumes, price_history = self.fetch_current_data()
        if current_prices is None:
            print("❌ Failed to fetch market data")
            return
        
        # Calculate positions
        positions, total_value, total_cost_basis = self.calculate_position_metrics(current_prices)

        # Also update the P&L calculations to use the actual cost basis:
        total_pnl = total_value - total_cost_basis  # Use actual cost basis, not self.total_investment
        total_pnl_pct = (total_pnl / total_cost_basis) * 100

        # Update the account summary print statements:
        print(f"\n💰 ACCOUNT VALUE SUMMARY:")
        print(f"   Total Account Value:    ${total_value:,.2f}")
        print(f"   Total Cost Basis:       ${total_cost_basis:,.2f}")  # Show actual cost basis
        print(f"   Cash Available:         ${self.cash:.2f}")
        print(f"   Total P&L:              ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
        print(f"   Account Growth:         {((total_value / (total_cost_basis + self.cash)) - 1) * 100:+.2f}%")
        
        # Benchmark performance
        print(f"\n📈 BENCHMARK PERFORMANCE:")
        if 'SPY' in current_prices:
            spy_change = ((current_prices['SPY'] - price_history['SPY'].iloc[-2]) / price_history['SPY'].iloc[-2]) * 100
            print(f"   S&P 500 (SPY):     ${current_prices['SPY']:.2f} ({spy_change:+.2f}%)")
        
        if 'IWM' in current_prices:
            iwm_change = ((current_prices['IWM'] - price_history['IWM'].iloc[-2]) / price_history['IWM'].iloc[-2]) * 100
            print(f"   Russell 2000 (IWM): ${current_prices['IWM']:.2f} ({iwm_change:+.2f}%)")
        
        if 'VIX' in current_prices:
            print(f"   VIX:               {current_prices['VIX']:.2f}")
        
        # Individual positions with weight analysis
        print(f"\n🏢 POSITION DETAILS:")
        print(f"{'Ticker':<6} {'Shares':<7} {'Entry':<8} {'Current':<8} {'Value':<10} {'P&L $':<10} {'P&L %':<8} {'Cur.Wt':<7} {'Tgt.Wt':<7} {'Drift':<6}")
        print("-" * 95)
        
        # Sort by P&L %
        positions.sort(key=lambda x: x['pnl_percent'], reverse=True)
        
        # Track positions that need rebalancing
        rebalance_alerts = []
        
        for pos in positions:
            drift_alert = ""
            if abs(pos['weight_drift']) > 5:  # >5% weight drift
                drift_alert = " ⚠️"
                rebalance_alerts.append(f"{pos['ticker']}: {pos['weight_drift']:+.1f}% drift")
            
            print(f"{pos['ticker']:<6} {pos['shares']:<7} ${pos['entry_price']:<7.2f} ${pos['current_price']:<7.2f} "
                  f"${pos['current_value']:<9.2f} ${pos['pnl_dollar']:<9.2f} {pos['pnl_percent']:+.1f}%   "
                  f"{pos['current_weight']:.1f}%   {pos['target_weight']:.1f}%   {pos['weight_drift']:+.1f}%{drift_alert}")
            
        alerts = self.check_alerts(positions)
        volume_alerts = self.get_volume_alerts(volumes, price_history)
        
        if alerts or volume_alerts or rebalance_alerts:
            print(f"\n⚠️  ALERTS:")
            for alert in alerts + volume_alerts:
                print(f"   {alert}")
            if rebalance_alerts:
                print(f"   📊 REBALANCING NEEDED:")
                for alert in rebalance_alerts:
                    print(f"      {alert}")
        else:
            print(f"\n✅ No alerts triggered")
        
        # Top movers
        print(f"\n📊 TOP MOVERS:")
        best_performer = max(positions, key=lambda x: x['pnl_percent'])
        worst_performer = min(positions, key=lambda x: x['pnl_percent'])
        print(f"   Best:  {best_performer['ticker']} ({best_performer['pnl_percent']:+.1f}%)")
        print(f"   Worst: {worst_performer['ticker']} ({worst_performer['pnl_percent']:+.1f}%)")
        
        # Generate JSON with total account context
        report_data = {
            'date': datetime.now().isoformat(),
            'account_value': total_value,
            'initial_investment': self.total_investment,
            'cash_available': self.cash,
            'total_pnl_dollar': total_pnl,
            'total_pnl_percent': total_pnl_pct,
            'account_growth_percent': ((total_value / (self.total_investment + self.cash)) - 1) * 100,
            'positions': positions,
            'alerts': alerts,
            'volume_alerts': volume_alerts,
            'rebalancing_alerts': rebalance_alerts,
            'benchmarks': {
                'SPY': current_prices.get('SPY', 0),
                'IWM': current_prices.get('IWM', 0),
                'VIX': current_prices.get('VIX', 0)
            },
            'portfolio_metrics': {
                'total_positions': len(positions),
                'positions_profitable': len([p for p in positions if p['pnl_percent'] > 0]),
                'largest_position_weight': max([p['current_weight'] for p in positions]) if positions else 0,
                'concentration_risk': sum([p['current_weight'] for p in positions if p['current_weight'] > 15])
            }
        }
        
        # Generate formatted output file for AI analysis
        self.generate_analysis_file(report_data)

        # Generate performance chart
        self.plot_performance_chart(save_path='LLM Managed Portfolio Performance')

        # Generate position details chart
        self.plot_position_details(positions, total_value, save_path='LLM Position Details')
        
        # Export historical metrics
        self.export_historical_metrics(report_data)
        
        print(f"\n" + "=" * 60)
        print("📋 JSON DATA FOR CLAUDE ANALYSIS:")
        print("=" * 60)
        print(json.dumps(report_data, indent=2))
        
        return report_data
    
    def generate_analysis_file(self, report_data):
        """Generate formatted text file for AI analysis"""
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Create formatted content
        content = f"""Daily portfolio update for {current_date}. Here's the data:

{json.dumps(report_data, indent=2)}

Key questions:
- Any positions need rebalancing?
- Should I take profits/cut losses?
- Any new catalysts or news affecting holdings?
- Market outlook for tomorrow/this week?

Additional context:
- Portfolio total investment: ${self.total_investment:,.2f}
- Cash available: ${self.cash:.2f}
- Investment timeframe: August 5, 2025 to December 27, 2025
- Strategy: Catalyst-driven momentum with concentrated positions

Risk management parameters:
- Stop-loss triggers: CYTK (-18%), AMD (-13%), IONS (-19%), Others (-20%)
- Profit targets: High-growth (50%), Binary catalysts (40%), Speculative (100%), Value/Cyclical (30-40%)

Please provide analysis and trading recommendations based on this data."""

        # Write to file
        filename = 'portfolio_analysis_output.txt'
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"\n💾 Analysis file generated: {filename}")
            print("📋 Upload this file to Claude or copy/paste its contents for analysis")
        except Exception as e:
            print(f"❌ Error creating analysis file: {e}")
        
        return content
    
    def plot_performance_chart(self, save_path=None):
        """Create performance chart matching the reference style"""
        
        if not hasattr(self, 'price_data') or self.price_data is None:
            print("❌ No price data available for charting")
            return
        
        # Create the plot
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Calculate portfolio performance over time
        portfolio_values = []
        spy_values = []
        iwm_values = []
        dates = self.price_data.index
        
        initial_portfolio_value = self.total_investment + self.cash
        
        for date in dates:
            # Calculate daily portfolio value
            daily_portfolio_value = self.cash
            for ticker, position in self.holdings.items():
                if ticker in self.price_data.columns:
                    current_price = self.price_data.loc[date, ticker]
                    if not pd.isna(current_price):
                        daily_portfolio_value += position['shares'] * current_price
                    else:
                        daily_portfolio_value += position['allocation']
                else:
                    daily_portfolio_value += position['allocation']
            
            portfolio_values.append(daily_portfolio_value)
        
        # Calculate benchmark values (normalized to start at same dollar amount)
        if 'SPY' in self.price_data.columns:
            spy_start = self.price_data['SPY'].iloc[0]
            spy_values = (self.price_data['SPY'] / spy_start) * initial_portfolio_value
        
        if 'IWM' in self.price_data.columns:
            iwm_start = self.price_data['IWM'].iloc[0]
            iwm_values = (self.price_data['IWM'] / iwm_start) * initial_portfolio_value
        
        # Plot lines
        ax.plot(dates, portfolio_values, color='#1f77b4', linewidth=2.5, marker='o', markersize=3,
                label=f'Portfolio (${initial_portfolio_value:,.0f} Invested)', zorder=3)
        
        if len(spy_values) > 0:
            ax.plot(dates, spy_values, color='#ff7f0e', linewidth=2, linestyle='-',
                    label=f'S&P 500 (${initial_portfolio_value:,.0f} Invested)', zorder=2)
        
        if len(iwm_values) > 0:
            ax.plot(dates, iwm_values, color='#2ca02c', linewidth=2, linestyle='--',
                    label=f'Russell 2000 (${initial_portfolio_value:,.0f} Invested)', zorder=1)
        
        # Formatting
        ax.set_title('LLM Portfolio vs. S&P 500 vs. Russell 2000', fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel(f'Value of ${initial_portfolio_value:,.0f} Investment', fontsize=12)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        ax.legend(loc='upper left', fontsize=11)
        
        # Format y-axis as currency
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        
        # Add performance annotations
        if len(portfolio_values) > 0:
            portfolio_return = ((portfolio_values[-1] - initial_portfolio_value) / initial_portfolio_value) * 100
            ax.annotate(f'{portfolio_return:+.1f}%', 
                    xy=(dates[-1], portfolio_values[-1]),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#1f77b4',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if len(spy_values) > 0:
            spy_return = ((spy_values.iloc[-1] - initial_portfolio_value) / initial_portfolio_value) * 100
            ax.annotate(f'{spy_return:+.1f}%', 
                    xy=(dates[-1], spy_values.iloc[-1]),
                    xytext=(10, -10), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#ff7f0e',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        if len(iwm_values) > 0:
            iwm_return = ((iwm_values.iloc[-1] - initial_portfolio_value) / initial_portfolio_value) * 100
            ax.annotate(f'{iwm_return:+.1f}%', 
                    xy=(dates[-1], iwm_values.iloc[-1]),
                    xytext=(10, 0), textcoords='offset points',
                    fontsize=11, fontweight='bold', color='#2ca02c',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        # Format x-axis dates
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        num_days = len(dates)
        if num_days <= 7:
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        elif num_days <= 30:
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        else:
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Chart saved to {save_path}")
        
        plt.show()
    
    def plot_position_details(self, positions, total_value, save_path=None):
        """Create position details chart showing portfolio breakdown and performance"""
        
        if not positions:
            print("❌ No position data available for charting")
            return
        
        # Create figure with subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Position Details', fontsize=16, fontweight='bold')
        
        # Extract data for plotting
        tickers = [pos['ticker'] for pos in positions]
        current_values = [pos['current_value'] for pos in positions]
        pnl_dollars = [pos['pnl_dollar'] for pos in positions]
        pnl_percentages = [pos['pnl_percent'] for pos in positions]
        current_weights = [pos['current_weight'] for pos in positions]
        
        # Define colors for consistency
        colors = plt.cm.Set3(np.linspace(0, 1, len(positions)))
        profit_colors = ['#2E8B57' if pnl >= 0 else '#DC143C' for pnl in pnl_dollars]
        
        # 1. Portfolio Allocation (Pie Chart)
        ax1.pie(current_values, labels=tickers, autopct='%1.1f%%', startangle=90, colors=colors)
        ax1.set_title('Portfolio Allocation by Value', fontweight='bold', pad=20)
        
        # 2. Position Values (Horizontal Bar Chart)
        y_pos = np.arange(len(tickers))
        bars = ax2.barh(y_pos, current_values, color=colors, alpha=0.7)
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(tickers)
        ax2.set_xlabel('Current Value ($)')
        ax2.set_title('Position Values', fontweight='bold', pad=20)
        ax2.grid(axis='x', alpha=0.3)
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, current_values)):
            ax2.text(value + max(current_values) * 0.01, bar.get_y() + bar.get_height()/2, 
                    f'${value:.0f}', ha='left', va='center', fontsize=9)
        
        # 3. P&L Performance ($ and %)
        x_pos = np.arange(len(tickers))
        
        # Create twin axis for percentage
        ax3_twin = ax3.twinx()
        
        # Plot P&L dollars as bars
        bars3 = ax3.bar(x_pos, pnl_dollars, color=profit_colors, alpha=0.7, label='P&L ($)')
        ax3.set_xlabel('Positions')
        ax3.set_ylabel('P&L ($)', color='black')
        ax3.set_title('P&L Performance', fontweight='bold', pad=20)
        ax3.set_xticks(x_pos)
        ax3.set_xticklabels(tickers, rotation=45)
        ax3.grid(axis='y', alpha=0.3)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        
        # Plot P&L percentages as line
        line = ax3_twin.plot(x_pos, pnl_percentages, color='orange', marker='o', 
                            linewidth=2, markersize=6, label='P&L (%)')
        ax3_twin.set_ylabel('P&L (%)', color='orange')
        ax3_twin.tick_params(axis='y', labelcolor='orange')
        ax3_twin.axhline(y=0, color='orange', linestyle='--', alpha=0.5)
        
        # Add value labels on bars
        for bar, pnl_dollar, pnl_pct in zip(bars3, pnl_dollars, pnl_percentages):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + (max(pnl_dollars) * 0.02 if height >= 0 else min(pnl_dollars) * 0.02),
                    f'${pnl_dollar:.0f}', ha='center', va='bottom' if height >= 0 else 'top', fontsize=8)
        
        # 4. Weight Distribution vs Target
        ax4.barh(y_pos, current_weights, color=colors, alpha=0.7, label='Current Weight')
        ax4.set_yticks(y_pos)
        ax4.set_yticklabels(tickers)
        ax4.set_xlabel('Portfolio Weight (%)')
        ax4.set_title('Current Portfolio Weights', fontweight='bold', pad=20)
        ax4.grid(axis='x', alpha=0.3)
        
        # Add weight labels
        for i, weight in enumerate(current_weights):
            ax4.text(weight + max(current_weights) * 0.01, i, f'{weight:.1f}%', 
                    ha='left', va='center', fontsize=9)
        
        # Add portfolio summary text box
        total_pnl = sum(pnl_dollars)
        total_cost_basis = sum([pos['cost_basis'] for pos in positions])
        total_pnl_pct = (total_pnl / total_cost_basis) * 100 if total_cost_basis > 0 else 0
        profitable_positions = len([p for p in pnl_dollars if p >= 0])
        
        summary_text = f"""Portfolio Summary:
        Total Value: ${total_value:,.0f}
        Total P&L: ${total_pnl:+,.0f} ({total_pnl_pct:+.1f}%)
        Profitable Positions: {profitable_positions}/{len(positions)}
        Largest Position: {max(current_weights):.1f}%
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
        
        # Add text box to the figure
        fig.text(0.02, 0.02, summary_text, fontsize=10, 
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8),
                verticalalignment='bottom')
        
        # Adjust layout to prevent overlapping
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.15)  # Make room for summary text
        
        # Save the chart
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"📊 Position Details saved to {save_path}")
        
        plt.show()
        # plt.close()  # Clean up to prevent memory issues
        
    def export_historical_metrics(self, report_data):
        """Export daily metrics to CSV for historical tracking"""
        
        filename = 'portfolio_historical_metrics.csv'
        
        # Current metrics to track
        current_metrics = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'time': datetime.now().strftime('%H:%M:%S'),
            'account_value': report_data['account_value'],
            'total_pnl_dollar': report_data['total_pnl_dollar'],
            'total_pnl_percent': report_data['total_pnl_percent'],
            'account_growth_percent': report_data['account_growth_percent'],
            'spy_price': report_data['benchmarks']['SPY'],
            'iwm_price': report_data['benchmarks']['IWM'],
            'vix_level': report_data['benchmarks']['VIX'],
            'positions_profitable': report_data['portfolio_metrics']['positions_profitable'],
            'largest_position_weight': report_data['portfolio_metrics']['largest_position_weight'],
            'concentration_risk': report_data['portfolio_metrics']['concentration_risk'],
            'total_alerts': len(report_data['alerts']) + len(report_data['volume_alerts']) + len(report_data['rebalancing_alerts'])
        }
        
        # Add individual position performance
        for pos in report_data['positions']:
            current_metrics[f"{pos['ticker']}_price"] = pos['current_price']
            current_metrics[f"{pos['ticker']}_pnl_pct"] = pos['pnl_percent']
            current_metrics[f"{pos['ticker']}_weight"] = pos['current_weight']
            current_metrics[f"{pos['ticker']}_drift"] = pos['weight_drift']
        
        # Create DataFrame
        df_new = pd.DataFrame([current_metrics])
        
        # Append to existing file or create new one
        try:
            if os.path.exists(filename):
                df_existing = pd.read_csv(filename)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            
            df_combined.to_csv(filename, index=False)
            print(f"📈 Historical metrics saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving historical metrics: {e}")

# Usage
# if __name__ == "__main__":
#     reporter = DailyPortfolioReport()
#     reporter.generate_report()

# Usage 
if __name__ == "__main__":
    # Test the parsing
    test_orders = test_claude_document_parsing()
    
    print("\n" + "=" * 60)
    print("INTEGRATION WITH YOUR PORTFOLIO SCRIPT:")
    print("=" * 60)
    
    # This would be integrated into your existing Daily_Portfolio_Script.py
    # from Daily_Portfolio_Script import DailyPortfolioReport
    
    # Create portfolio instance
    portfolio = DailyPortfolioReport()
    
    # Execute automated trading from document
    # Will automatically look for doc if doc is unspecified
    results = portfolio.execute_automated_trading()
    
    # Generate updated portfolio report
    portfolio.generate_report()
    

# STEPS:
# 1. Save Claude's response as 'claude_recommendations.txt'
# 2. Add the automated trading methods to your DailyPortfolioReport class
# 3. Run: python Daily_Portfolio_Script.py --execute-trades claude_recommendations.txt
# 4. Review execution report and update holdings in script
    