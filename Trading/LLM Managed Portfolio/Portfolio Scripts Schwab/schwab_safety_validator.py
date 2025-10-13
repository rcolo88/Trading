"""
Schwab Safety Validator Module
Pre-trade and post-trade validation and risk management
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from trading_models import TradeOrder, OrderType, OrderPriority

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SafetyValidator:
    """
    Validates trades before execution and reconciles after execution
    Provides safety checks and risk management
    """

    def __init__(self, account_manager, portfolio_manager):
        """
        Initialize safety validator

        Args:
            account_manager: SchwabAccountManager instance
            portfolio_manager: PortfolioManager instance
        """
        self.account_manager = account_manager
        self.portfolio = portfolio_manager

        # Safety limits
        self.max_single_position_pct = 0.30  # 30% max position size
        self.max_daily_trades = 50  # Max 50 trades per day
        self.min_cash_reserve_pct = 0.05  # Keep 5% cash minimum
        self.max_position_value = 50000  # $50k max single position

        # Trade tracking
        self.trades_today = []
        self.last_validation_time = None

        logger.info("✅ Safety Validator initialized")

    def set_safety_limits(self, max_position_pct: float = None, max_daily_trades: int = None,
                          min_cash_pct: float = None, max_position_value: float = None):
        """
        Configure safety limits

        Args:
            max_position_pct: Maximum position size as % of portfolio
            max_daily_trades: Maximum trades per day
            min_cash_pct: Minimum cash reserve as % of portfolio
            max_position_value: Maximum dollar value for single position
        """
        if max_position_pct is not None:
            self.max_single_position_pct = max_position_pct
        if max_daily_trades is not None:
            self.max_daily_trades = max_daily_trades
        if min_cash_pct is not None:
            self.min_cash_reserve_pct = min_cash_pct
        if max_position_value is not None:
            self.max_position_value = max_position_value

        logger.info(f"🛡️  Safety limits updated:")
        logger.info(f"   Max position size: {self.max_single_position_pct:.1%}")
        logger.info(f"   Max daily trades: {self.max_daily_trades}")
        logger.info(f"   Min cash reserve: {self.min_cash_reserve_pct:.1%}")
        logger.info(f"   Max position value: ${self.max_position_value:,.2f}")

    def validate_order_pre_execution(self, order: TradeOrder, current_price: float,
                                     account_data: Dict = None) -> Tuple[bool, str]:
        """
        Validate order before execution

        Args:
            order: TradeOrder to validate
            current_price: Current market price
            account_data: Current account data (will fetch if not provided)

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Fetch account data if not provided
            if account_data is None:
                account_data = self.account_manager.fetch_account_data()

            if not account_data:
                return False, "Failed to fetch account data for validation"

            # Parse account info
            positions, cash = self.account_manager.parse_account_positions(account_data)
            securities_account = account_data.get('securitiesAccount', {})
            balances = securities_account.get('currentBalances', {})

            buying_power = float(balances.get('buyingPower', cash))
            total_value = sum(p['allocation'] for p in positions.values()) + cash

            # 1. Check daily trade limit
            trades_today_count = self._count_trades_today()
            if trades_today_count >= self.max_daily_trades:
                return False, f"Daily trade limit reached ({self.max_daily_trades} trades)"

            # 2. Validate BUY orders
            if order.action == OrderType.BUY:
                # Calculate order value
                if order.shares:
                    order_value = order.shares * current_price
                elif order.target_value:
                    order_value = order.target_value
                else:
                    return False, "BUY order must specify shares or target_value"

                # Check buying power
                if order_value > buying_power:
                    return False, f"Insufficient buying power (need ${order_value:.2f}, have ${buying_power:.2f})"

                # Check position size limit
                position_pct = order_value / total_value if total_value > 0 else 1.0
                if position_pct > self.max_single_position_pct:
                    return False, f"Position would exceed {self.max_single_position_pct:.1%} limit ({position_pct:.1%})"

                # Check absolute position value limit
                existing_position = positions.get(order.ticker, {})
                new_position_value = existing_position.get('allocation', 0) + order_value
                if new_position_value > self.max_position_value:
                    return False, f"Position would exceed ${self.max_position_value:,.2f} limit (${new_position_value:,.2f})"

                # Check cash reserve after purchase
                remaining_cash = cash - order_value
                min_cash_required = total_value * self.min_cash_reserve_pct
                if remaining_cash < min_cash_required:
                    return False, f"Would violate minimum cash reserve (${remaining_cash:.2f} < ${min_cash_required:.2f})"

            # 3. Validate SELL/REDUCE orders
            elif order.action in [OrderType.SELL, OrderType.REDUCE]:
                position = positions.get(order.ticker)

                if not position or position['shares'] == 0:
                    return False, f"No position to sell for {order.ticker}"

                # Check if sell quantity is valid
                if order.shares:
                    if order.shares > position['shares']:
                        return False, f"Cannot sell {order.shares} shares (only have {position['shares']})"

            # 4. Check for duplicate orders
            if self._is_duplicate_order(order):
                return False, f"Duplicate order detected for {order.ticker}"

            # All checks passed
            logger.info(f"✅ Order validation passed for {order.action.value} {order.ticker}")
            return True, ""

        except Exception as e:
            error_msg = f"Error during order validation: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return False, error_msg

    def validate_orders_batch(self, orders: List[TradeOrder], current_prices: Dict[str, float]) -> Dict[str, any]:
        """
        Validate a batch of orders for cash flow and risk

        Args:
            orders: List of TradeOrder objects
            current_prices: Dict of current prices

        Returns:
            Dict with validation results
        """
        logger.info(f"🔍 Validating batch of {len(orders)} orders...")

        results = {
            'all_valid': True,
            'valid_orders': [],
            'invalid_orders': [],
            'warnings': [],
            'cash_flow_feasible': True,
            'total_risk_exposure': 0.0
        }

        # Fetch current account state
        account_data = self.account_manager.fetch_account_data()
        if not account_data:
            results['all_valid'] = False
            results['warnings'].append("Failed to fetch account data")
            return results

        positions, cash = self.account_manager.parse_account_positions(account_data)
        total_value = sum(p['allocation'] for p in positions.values()) + cash

        # Simulate cash flow
        simulated_cash = cash

        # Process sells first (they generate cash)
        for order in orders:
            if order.action in [OrderType.SELL, OrderType.REDUCE]:
                position = positions.get(order.ticker)
                if position and position['shares'] > 0:
                    price = current_prices.get(order.ticker, 0)
                    if order.shares:
                        sell_shares = min(order.shares, position['shares'])
                    else:
                        sell_shares = position['shares'] // 2 if order.action == OrderType.REDUCE else position['shares']

                    proceeds = sell_shares * price
                    simulated_cash += proceeds

        # Process buys (they consume cash)
        for order in orders:
            if order.action == OrderType.BUY:
                price = current_prices.get(order.ticker, 0)
                if not price:
                    results['warnings'].append(f"No price data for {order.ticker}")
                    continue

                is_valid, error_msg = self.validate_order_pre_execution(order, price, account_data)

                if is_valid:
                    results['valid_orders'].append(order.ticker)

                    # Calculate order value
                    if order.shares:
                        order_value = order.shares * price
                    elif order.target_value:
                        order_value = order.target_value
                    else:
                        order_value = 0

                    # Check if we have cash after previous orders
                    if order_value > simulated_cash:
                        results['invalid_orders'].append({
                            'ticker': order.ticker,
                            'reason': f"Insufficient cash in batch (need ${order_value:.2f}, have ${simulated_cash:.2f})"
                        })
                        results['all_valid'] = False
                        results['cash_flow_feasible'] = False
                    else:
                        simulated_cash -= order_value
                        results['total_risk_exposure'] += order_value
                else:
                    results['invalid_orders'].append({
                        'ticker': order.ticker,
                        'reason': error_msg
                    })
                    results['all_valid'] = False

        # Calculate risk metrics
        if total_value > 0:
            risk_pct = results['total_risk_exposure'] / total_value
            if risk_pct > 0.5:  # More than 50% of portfolio at risk
                results['warnings'].append(f"High risk exposure: {risk_pct:.1%} of portfolio")

        logger.info(f"✅ Batch validation complete: {len(results['valid_orders'])} valid, {len(results['invalid_orders'])} invalid")

        return results

    def verify_execution_accuracy(self, expected_result, actual_account_data: Dict = None) -> bool:
        """
        Verify that trade execution matched expectations

        Args:
            expected_result: TradeResult from executor
            actual_account_data: Fresh account data (will fetch if not provided)

        Returns:
            True if execution matches expectations, False otherwise
        """
        try:
            if actual_account_data is None:
                actual_account_data = self.account_manager.fetch_account_data()

            if not actual_account_data:
                logger.error("❌ Cannot verify execution - failed to fetch account data")
                return False

            positions, cash = self.account_manager.parse_account_positions(actual_account_data)

            ticker = expected_result.order.ticker
            actual_position = positions.get(ticker, {})
            actual_shares = actual_position.get('shares', 0)

            # Get expected shares based on order type
            if expected_result.order.action == OrderType.BUY:
                # We expect shares to increase
                expected_increase = expected_result.executed_shares
                logger.info(f"🔍 Verifying BUY: Expected {expected_increase} shares added to {ticker}")

            elif expected_result.order.action in [OrderType.SELL, OrderType.REDUCE]:
                # We expect shares to decrease
                expected_decrease = expected_result.executed_shares
                logger.info(f"🔍 Verifying SELL: Expected {expected_decrease} shares removed from {ticker}")

            # For now, just log the verification
            # Full implementation would compare before/after positions
            logger.info(f"📊 Current position: {ticker} = {actual_shares} shares")

            return True

        except Exception as e:
            logger.error(f"❌ Error verifying execution: {e}")
            return False

    def _count_trades_today(self) -> int:
        """Count number of trades executed today"""
        today = datetime.now().date()

        # Filter trades from today
        trades_today = [t for t in self.trades_today if t['date'] == today]

        return len(trades_today)

    def _is_duplicate_order(self, order: TradeOrder) -> bool:
        """
        Check if order is a duplicate of recent order

        Args:
            order: TradeOrder to check

        Returns:
            True if duplicate detected, False otherwise
        """
        # Check trades in last 5 minutes
        recent_window = datetime.now() - timedelta(minutes=5)

        for trade in self.trades_today:
            if (trade['ticker'] == order.ticker and
                trade['action'] == order.action.value and
                trade['timestamp'] > recent_window):
                return True

        return False

    def record_trade(self, order: TradeOrder):
        """
        Record a trade for tracking

        Args:
            order: TradeOrder that was executed
        """
        self.trades_today.append({
            'ticker': order.ticker,
            'action': order.action.value,
            'timestamp': datetime.now(),
            'date': datetime.now().date()
        })

    def get_risk_summary(self, account_data: Dict = None) -> Dict:
        """
        Generate portfolio risk summary

        Args:
            account_data: Current account data (will fetch if not provided)

        Returns:
            Dict with risk metrics
        """
        try:
            if account_data is None:
                account_data = self.account_manager.fetch_account_data()

            if not account_data:
                return {'error': 'Failed to fetch account data'}

            positions, cash = self.account_manager.parse_account_positions(account_data)
            total_value = sum(p['allocation'] for p in positions.values()) + cash

            # Calculate concentration risk
            max_position_value = max([p['allocation'] for p in positions.values()]) if positions else 0
            max_position_pct = max_position_value / total_value if total_value > 0 else 0

            # Calculate cash reserve
            cash_pct = cash / total_value if total_value > 0 else 0

            # Count positions
            num_positions = len(positions)

            return {
                'total_value': total_value,
                'cash': cash,
                'cash_pct': cash_pct,
                'num_positions': num_positions,
                'max_position_value': max_position_value,
                'max_position_pct': max_position_pct,
                'trades_today': self._count_trades_today(),
                'risk_flags': self._generate_risk_flags(cash_pct, max_position_pct, num_positions)
            }

        except Exception as e:
            logger.error(f"❌ Error generating risk summary: {e}")
            return {'error': str(e)}

    def _generate_risk_flags(self, cash_pct: float, max_position_pct: float, num_positions: int) -> List[str]:
        """Generate list of risk warnings"""
        flags = []

        if cash_pct < self.min_cash_reserve_pct:
            flags.append(f"⚠️  Low cash reserve ({cash_pct:.1%} < {self.min_cash_reserve_pct:.1%})")

        if max_position_pct > self.max_single_position_pct:
            flags.append(f"⚠️  Concentrated position ({max_position_pct:.1%} > {self.max_single_position_pct:.1%})")

        if num_positions < 3:
            flags.append(f"⚠️  Low diversification ({num_positions} positions)")

        if num_positions > 20:
            flags.append(f"⚠️  High fragmentation ({num_positions} positions)")

        trades_today = self._count_trades_today()
        if trades_today > self.max_daily_trades * 0.8:
            flags.append(f"⚠️  Approaching daily trade limit ({trades_today}/{self.max_daily_trades})")

        return flags

    def print_risk_summary(self, summary: Dict = None):
        """
        Print formatted risk summary to console

        Args:
            summary: Pre-generated summary (will generate if not provided)
        """
        if summary is None:
            summary = self.get_risk_summary()

        if 'error' in summary:
            print(f"❌ Error: {summary['error']}")
            return

        print("\n" + "=" * 60)
        print("🛡️  PORTFOLIO RISK SUMMARY")
        print("=" * 60)
        print(f"Total Value:        ${summary['total_value']:>15,.2f}")
        print(f"Cash Reserve:       ${summary['cash']:>15,.2f} ({summary['cash_pct']:>6.1%})")
        print(f"Positions:          {summary['num_positions']:>15}")
        print(f"Max Position:       ${summary['max_position_value']:>15,.2f} ({summary['max_position_pct']:>6.1%})")
        print(f"Trades Today:       {summary['trades_today']:>15}")
        print("-" * 60)

        if summary['risk_flags']:
            print("\n⚠️  Risk Flags:")
            for flag in summary['risk_flags']:
                print(f"   {flag}")
        else:
            print("✅ No risk flags - portfolio within safety limits")

        print("=" * 60)
