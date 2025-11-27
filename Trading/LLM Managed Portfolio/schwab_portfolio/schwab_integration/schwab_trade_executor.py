"""
Schwab Live Trade Executor Module
Handles real order placement and execution through Schwab API
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

from core.trading_models import TradeOrder, TradeResult, OrderType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """Schwab order status enumeration"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    REJECTED = "REJECTED"
    CANCELED = "CANCELED"
    QUEUED = "QUEUED"
    WORKING = "WORKING"


class SchwabTradeExecutor:
    """
    Executes live trades through Schwab API
    Handles order placement, status tracking, and position reconciliation
    """

    def __init__(self, schwab_client, account_manager, portfolio_manager, dry_run: bool = True):
        """
        Initialize Schwab trade executor

        Args:
            schwab_client: Authenticated schwab-py client instance
            account_manager: SchwabAccountManager instance
            portfolio_manager: PortfolioManager instance
            dry_run: If True, simulates trades without real execution (default: True)
        """
        self.client = schwab_client
        self.account_manager = account_manager
        self.portfolio = portfolio_manager
        self.dry_run = dry_run

        # Order tracking
        self.executed_orders = []
        self.failed_orders = []

        mode = "DRY-RUN" if dry_run else "LIVE TRADING"
        logger.info(f"✅ Schwab Trade Executor initialized in {mode} mode")

    def set_dry_run_mode(self, enabled: bool):
        """
        Toggle dry-run mode

        Args:
            enabled: True for simulation, False for live trading
        """
        old_mode = "DRY-RUN" if self.dry_run else "LIVE"
        new_mode = "DRY-RUN" if enabled else "LIVE"
        self.dry_run = enabled
        logger.info(f"🔄 Mode changed: {old_mode} → {new_mode}")

    def place_market_order(self, order: TradeOrder, current_price: float) -> TradeResult:
        """
        Place a market order through Schwab API

        Args:
            order: TradeOrder object with order details
            current_price: Current market price for estimation

        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()

        try:
            # Get account hash
            account_hash = self.account_manager.account_hash
            if not account_hash:
                raise Exception("No account hash available. Sync account first.")

            # Determine order quantity
            if order.action == OrderType.BUY:
                if order.shares:
                    quantity = order.shares
                elif order.target_value:
                    quantity = int(order.target_value / current_price)
                else:
                    raise ValueError("Order must specify shares or target_value")
            elif order.action in [OrderType.SELL, OrderType.REDUCE]:
                position = self.portfolio.get_position_info(order.ticker)
                if not position or position['shares'] == 0:
                    raise ValueError(f"No position to sell for {order.ticker}")

                if order.shares:
                    quantity = min(order.shares, position['shares'])
                elif order.action == OrderType.REDUCE:
                    quantity = position['shares'] // 2  # Reduce by half
                else:
                    quantity = position['shares']  # Sell all
            else:
                raise ValueError(f"Unsupported order action: {order.action}")

            # Build order specification using schwab-py order builders
            if order.action == OrderType.BUY:
                from schwab.orders.equities import equity_buy_market
                order_spec = equity_buy_market(order.ticker, quantity)
            elif order.action in [OrderType.SELL, OrderType.REDUCE]:
                from schwab.orders.equities import equity_sell_market
                order_spec = equity_sell_market(order.ticker, quantity)
            else:
                raise ValueError(f"Cannot build order for action: {order.action}")

            # Convert order_spec to JSON
            order_json = order_spec.build()

            # Estimate execution value
            estimated_value = quantity * current_price

            if self.dry_run:
                # DRY RUN: Simulate the order without placing it
                logger.info(f"🧪 DRY RUN: Would place {order.action.value} order for {quantity} shares of {order.ticker}")
                logger.info(f"   Estimated value: ${estimated_value:.2f}")
                logger.info(f"   Order spec: {json.dumps(order_json, indent=2)}")

                return TradeResult(
                    order=order,
                    executed=True,
                    execution_price=current_price,
                    executed_shares=quantity,
                    execution_value=estimated_value,
                    error_message=None,
                    timestamp=timestamp,
                    order_id=f"DRY_RUN_{timestamp.timestamp()}"
                )

            # LIVE TRADING: Place real order
            logger.info(f"🚀 LIVE: Placing {order.action.value} order for {quantity} shares of {order.ticker}")

            response = self.client.place_order(account_hash, order_spec)

            if response.status_code in [200, 201]:
                # Order placed successfully
                order_id = self._extract_order_id(response)
                logger.info(f"✅ Order placed successfully: {order_id}")

                # Track order
                self.executed_orders.append({
                    'order_id': order_id,
                    'ticker': order.ticker,
                    'action': order.action.value,
                    'quantity': quantity,
                    'timestamp': timestamp.isoformat()
                })

                # Wait briefly and check order status
                import time
                time.sleep(2)  # Give Schwab time to process
                order_status = self.get_order_status(order_id)

                # Determine actual execution details
                actual_quantity = quantity  # Default assumption
                actual_price = current_price

                if order_status and 'orderActivityCollection' in order_status:
                    activities = order_status['orderActivityCollection']
                    if activities:
                        execution_legs = activities[0].get('executionLegs', [])
                        if execution_legs:
                            actual_price = float(execution_legs[0].get('price', current_price))
                            actual_quantity = int(execution_legs[0].get('quantity', quantity))

                actual_value = actual_quantity * actual_price

                return TradeResult(
                    order=order,
                    executed=True,
                    execution_price=actual_price,
                    executed_shares=actual_quantity,
                    execution_value=actual_value,
                    error_message=None,
                    timestamp=timestamp,
                    order_id=order_id
                )

            else:
                # Order rejected
                error_msg = f"Order rejected: HTTP {response.status_code}"
                logger.error(f"❌ {error_msg}")
                logger.error(f"   Response: {response.text}")

                self.failed_orders.append({
                    'ticker': order.ticker,
                    'action': order.action.value,
                    'quantity': quantity,
                    'error': error_msg,
                    'timestamp': timestamp.isoformat()
                })

                return TradeResult(
                    order=order,
                    executed=False,
                    execution_price=current_price,
                    executed_shares=0,
                    execution_value=0,
                    error_message=error_msg,
                    timestamp=timestamp
                )

        except Exception as e:
            error_msg = f"Exception during order placement: {str(e)}"
            logger.error(f"❌ {error_msg}")

            return TradeResult(
                order=order,
                executed=False,
                execution_price=current_price,
                executed_shares=0,
                execution_value=0,
                error_message=error_msg,
                timestamp=timestamp
            )

    def place_limit_order(self, order: TradeOrder, limit_price: float) -> TradeResult:
        """
        Place a limit order through Schwab API

        Args:
            order: TradeOrder object with order details
            limit_price: Limit price for the order

        Returns:
            TradeResult with execution details
        """
        timestamp = datetime.now()

        try:
            account_hash = self.account_manager.account_hash
            if not account_hash:
                raise Exception("No account hash available. Sync account first.")

            # Determine quantity (similar to market order)
            if order.action == OrderType.BUY:
                if order.shares:
                    quantity = order.shares
                elif order.target_value:
                    quantity = int(order.target_value / limit_price)
                else:
                    raise ValueError("Order must specify shares or target_value")
            elif order.action in [OrderType.SELL, OrderType.REDUCE]:
                position = self.portfolio.get_position_info(order.ticker)
                if not position or position['shares'] == 0:
                    raise ValueError(f"No position to sell for {order.ticker}")

                if order.shares:
                    quantity = min(order.shares, position['shares'])
                elif order.action == OrderType.REDUCE:
                    quantity = position['shares'] // 2
                else:
                    quantity = position['shares']
            else:
                raise ValueError(f"Unsupported order action: {order.action}")

            # Build limit order specification
            if order.action == OrderType.BUY:
                from schwab.orders.equities import equity_buy_limit
                order_spec = equity_buy_limit(order.ticker, quantity, limit_price)
            elif order.action in [OrderType.SELL, OrderType.REDUCE]:
                from schwab.orders.equities import equity_sell_limit
                order_spec = equity_sell_limit(order.ticker, quantity, limit_price)
            else:
                raise ValueError(f"Cannot build order for action: {order.action}")

            order_json = order_spec.build()
            estimated_value = quantity * limit_price

            if self.dry_run:
                logger.info(f"🧪 DRY RUN: Would place {order.action.value} LIMIT order for {quantity} shares of {order.ticker} @ ${limit_price:.2f}")
                logger.info(f"   Estimated value: ${estimated_value:.2f}")
                logger.info(f"   Order spec: {json.dumps(order_json, indent=2)}")

                return TradeResult(
                    order=order,
                    executed=True,
                    execution_price=limit_price,
                    executed_shares=quantity,
                    execution_value=estimated_value,
                    error_message=None,
                    timestamp=timestamp,
                    order_id=f"DRY_RUN_LIMIT_{timestamp.timestamp()}"
                )

            # LIVE: Place limit order
            logger.info(f"🚀 LIVE: Placing {order.action.value} LIMIT order for {quantity} shares of {order.ticker} @ ${limit_price:.2f}")

            response = self.client.place_order(account_hash, order_spec)

            if response.status_code in [200, 201]:
                order_id = self._extract_order_id(response)
                logger.info(f"✅ Limit order placed successfully: {order_id}")

                self.executed_orders.append({
                    'order_id': order_id,
                    'ticker': order.ticker,
                    'action': order.action.value,
                    'order_type': 'LIMIT',
                    'quantity': quantity,
                    'limit_price': limit_price,
                    'timestamp': timestamp.isoformat()
                })

                return TradeResult(
                    order=order,
                    executed=True,  # Order placed, not necessarily filled yet
                    execution_price=limit_price,
                    executed_shares=quantity,
                    execution_value=estimated_value,
                    error_message="Limit order placed (not yet filled)",
                    timestamp=timestamp,
                    order_id=order_id
                )

            else:
                error_msg = f"Limit order rejected: HTTP {response.status_code}"
                logger.error(f"❌ {error_msg}")

                return TradeResult(
                    order=order,
                    executed=False,
                    execution_price=limit_price,
                    executed_shares=0,
                    execution_value=0,
                    error_message=error_msg,
                    timestamp=timestamp
                )

        except Exception as e:
            error_msg = f"Exception during limit order placement: {str(e)}"
            logger.error(f"❌ {error_msg}")

            return TradeResult(
                order=order,
                executed=False,
                execution_price=limit_price,
                executed_shares=0,
                execution_value=0,
                error_message=error_msg,
                timestamp=timestamp
            )

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """
        Get current status of an order

        Args:
            order_id: Schwab order ID

        Returns:
            Dict with order status information or None if failed
        """
        try:
            if self.dry_run:
                logger.info(f"🧪 DRY RUN: Would check status for order {order_id}")
                return {'status': 'FILLED', 'dry_run': True}

            account_hash = self.account_manager.account_hash
            response = self.client.get_order(account_hash, order_id)

            if response.status_code == 200:
                order_data = response.json()
                status = order_data.get('status', 'UNKNOWN')
                logger.info(f"📊 Order {order_id} status: {status}")
                return order_data
            else:
                logger.error(f"❌ Failed to get order status: HTTP {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"❌ Error getting order status: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order

        Args:
            order_id: Schwab order ID

        Returns:
            True if cancellation successful, False otherwise
        """
        try:
            if self.dry_run:
                logger.info(f"🧪 DRY RUN: Would cancel order {order_id}")
                return True

            account_hash = self.account_manager.account_hash
            response = self.client.cancel_order(account_hash, order_id)

            if response.status_code == 200:
                logger.info(f"✅ Order {order_id} cancelled successfully")
                return True
            else:
                logger.error(f"❌ Failed to cancel order: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"❌ Error cancelling order: {e}")
            return False

    def _extract_order_id(self, response) -> str:
        """
        Extract order ID from Schwab API response

        Args:
            response: HTTP response from order placement

        Returns:
            Order ID string
        """
        try:
            # Schwab returns order ID in Location header
            location = response.headers.get('Location', '')
            if location:
                # Extract order ID from URL like: .../accounts/{hash}/orders/{orderId}
                parts = location.split('/')
                if parts:
                    return parts[-1]

            # Fallback: Try to extract from response body
            try:
                response_data = response.json()
                if 'orderId' in response_data:
                    return response_data['orderId']
            except:
                pass

            # Last resort: Generate timestamp-based ID
            return f"ORDER_{datetime.now().timestamp()}"

        except Exception as e:
            logger.warning(f"⚠️  Could not extract order ID: {e}")
            return f"ORDER_{datetime.now().timestamp()}"

    def reconcile_positions_after_trades(self) -> bool:
        """
        Sync portfolio state with Schwab account after trade execution

        Returns:
            True if reconciliation successful, False otherwise
        """
        try:
            logger.info("🔄 Reconciling positions after trades...")

            # Fetch fresh account data from Schwab
            success = self.account_manager.sync_to_local_portfolio()

            if success:
                logger.info("✅ Portfolio reconciled with Schwab account")
                return True
            else:
                logger.error("❌ Failed to reconcile portfolio")
                return False

        except Exception as e:
            logger.error(f"❌ Error during reconciliation: {e}")
            return False

    def get_execution_summary(self) -> Dict:
        """
        Get summary of executed and failed orders

        Returns:
            Dict with execution statistics
        """
        return {
            'executed_count': len(self.executed_orders),
            'failed_count': len(self.failed_orders),
            'executed_orders': self.executed_orders,
            'failed_orders': self.failed_orders,
            'mode': 'DRY_RUN' if self.dry_run else 'LIVE'
        }

    def print_execution_summary(self):
        """Print formatted execution summary to console"""
        summary = self.get_execution_summary()

        print("\n" + "=" * 60)
        print(f"📊 TRADE EXECUTION SUMMARY ({summary['mode']} MODE)")
        print("=" * 60)
        print(f"✅ Successful: {summary['executed_count']}")
        print(f"❌ Failed:     {summary['failed_count']}")
        print("-" * 60)

        if summary['executed_orders']:
            print("\n✅ Executed Orders:")
            for order in summary['executed_orders']:
                print(f"   {order['action']} {order['quantity']} {order['ticker']} - ID: {order.get('order_id', 'N/A')}")

        if summary['failed_orders']:
            print("\n❌ Failed Orders:")
            for order in summary['failed_orders']:
                print(f"   {order['action']} {order['quantity']} {order['ticker']} - Error: {order['error']}")

        print("=" * 60)
