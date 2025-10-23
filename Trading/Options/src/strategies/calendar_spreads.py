"""
Calendar spread strategies implementation.

Calendar spreads (also known as time spreads or horizontal spreads) involve:
- Buying and selling options at the SAME strike price
- Different expiration dates (near-term vs far-term)
- Profit from time decay differential between the two expirations
- Can be implemented with calls or puts

Types implemented:
1. Call Calendar Spread - Sell near-term call, buy far-term call (same strike)
2. Put Calendar Spread - Sell near-term put, buy far-term put (same strike)
3. Diagonal Spread - Similar to calendar but different strikes (future enhancement)
"""

from datetime import datetime
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, Signal, Position


class CalendarSpread(BaseStrategy):
    """Base class for calendar spread strategies."""

    def __init__(self, name: str, config: Dict, spread_type: str):
        """
        Initialize calendar spread strategy.

        Args:
            name: Strategy name
            config: Strategy configuration
            spread_type: Type of spread (call_calendar, put_calendar)
        """
        super().__init__(name, config)
        self.spread_type = spread_type
        self.entry_config = config.get('entry', {})
        self.exit_config = config.get('exit', {})

    def _find_strike_by_moneyness(
        self,
        options_chain: pd.DataFrame,
        underlying_price: float,
        moneyness_pct: float,
        option_type: str,
        tolerance: float = 0.02
    ) -> Optional[float]:
        """
        Find strike price based on moneyness (percentage from underlying).

        Args:
            options_chain: DataFrame with options data
            underlying_price: Current underlying price
            moneyness_pct: Target moneyness as percentage (0.0 = ATM, 0.05 = 5% OTM)
            option_type: 'call' or 'put'
            tolerance: Acceptable moneyness tolerance

        Returns:
            Strike price or None if not found
        """
        filtered = options_chain[options_chain['option_type'] == option_type].copy()

        if filtered.empty:
            return None

        # Calculate target strike based on moneyness
        if option_type == 'call':
            target_strike = underlying_price * (1 + moneyness_pct)
        else:  # put
            target_strike = underlying_price * (1 - moneyness_pct)

        # Find closest strike to target
        filtered['strike_diff'] = abs(filtered['strike'] - target_strike)
        closest = filtered.loc[filtered['strike_diff'].idxmin()]

        # Verify it's within tolerance
        actual_moneyness = abs((closest['strike'] - underlying_price) / underlying_price)
        if actual_moneyness <= abs(moneyness_pct) + tolerance:
            return closest['strike']

        return None

    def _find_strike_by_delta(
        self,
        options_chain: pd.DataFrame,
        target_delta: float,
        option_type: str,
        tolerance: float = 0.05
    ) -> Optional[float]:
        """
        Find strike price closest to target delta.

        Args:
            options_chain: DataFrame with options data including delta
            target_delta: Target delta value (e.g., 0.50 for ATM)
            option_type: 'call' or 'put'
            tolerance: Acceptable delta tolerance

        Returns:
            Strike price or None if not found
        """
        filtered = options_chain[options_chain['option_type'] == option_type].copy()

        if filtered.empty:
            return None

        # Find closest delta
        filtered['delta_diff'] = abs(abs(filtered['delta']) - abs(target_delta))
        closest = filtered.loc[filtered['delta_diff'].idxmin()]

        if closest['delta_diff'] <= tolerance:
            return closest['strike']

        return None

    def _get_spread_price(
        self,
        options_chain: pd.DataFrame,
        strike: float,
        near_dte: int,
        far_dte: int,
        option_type: str
    ) -> Optional[float]:
        """
        Calculate the net debit for the calendar spread.

        Calendar spreads are typically entered for a debit:
        - Buy the far-term option (higher premium)
        - Sell the near-term option (lower premium)
        - Net debit = far_term_price - near_term_price

        Args:
            options_chain: Options chain data
            strike: Strike price (same for both legs)
            near_dte: DTE for near-term option (short leg)
            far_dte: DTE for far-term option (long leg)
            option_type: 'call' or 'put'

        Returns:
            Net debit (positive value for calendar spread)
        """
        # Find near-term option (we sell this)
        near_option = options_chain[
            (options_chain['strike'] == strike) &
            (options_chain['option_type'] == option_type) &
            (options_chain['dte'] >= near_dte - 2) &
            (options_chain['dte'] <= near_dte + 2)
        ]

        # Find far-term option (we buy this)
        far_option = options_chain[
            (options_chain['strike'] == strike) &
            (options_chain['option_type'] == option_type) &
            (options_chain['dte'] >= far_dte - 2) &
            (options_chain['dte'] <= far_dte + 2)
        ]

        if near_option.empty or far_option.empty:
            return None

        # Use bid for sell (near-term), ask for buy (far-term)
        near_price = near_option.iloc[0]['bid']  # We sell at bid
        far_price = far_option.iloc[0]['ask']    # We buy at ask

        # Calendar spread is a debit: we pay (far - near)
        net_debit = far_price - near_price

        # Verify this makes sense (far-term should be more expensive)
        if net_debit <= 0:
            return None

        return net_debit

    def generate_entry_signal(
        self,
        date: datetime,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate entry signal for calendar spread."""

        # Get DTE targets
        near_dte_target = self.entry_config.get('near_dte', 30)
        far_dte_target = self.entry_config.get('far_dte', 60)
        dte_tolerance = self.entry_config.get('dte_tolerance', 5)

        # Filter options within DTE ranges
        near_options = options_data[
            (options_data['dte'] >= near_dte_target - dte_tolerance) &
            (options_data['dte'] <= near_dte_target + dte_tolerance)
        ].copy()

        far_options = options_data[
            (options_data['dte'] >= far_dte_target - dte_tolerance) &
            (options_data['dte'] <= far_dte_target + dte_tolerance)
        ].copy()

        if near_options.empty or far_options.empty:
            return None

        # Check market filters if provided
        vix = kwargs.get('vix')
        vix_max = kwargs.get('vix_max', float('inf'))
        vix_min = kwargs.get('vix_min', 0)

        if vix and (vix > vix_max or vix < vix_min):
            return None

        # Find strike based on strategy configuration
        option_type = self._get_option_type()
        strike_selection = self.entry_config.get('strike_selection', 'atm')

        if strike_selection == 'atm':
            # Use delta targeting for ATM (0.50 delta)
            strike = self._find_strike_by_delta(near_options, 0.50, option_type)
        elif strike_selection == 'delta':
            # Use specific delta target
            target_delta = self.entry_config.get('target_delta', 0.50)
            strike = self._find_strike_by_delta(near_options, target_delta, option_type)
        elif strike_selection == 'moneyness':
            # Use moneyness percentage
            moneyness = self.entry_config.get('moneyness', 0.0)  # 0.0 = ATM
            strike = self._find_strike_by_moneyness(
                near_options, underlying_price, moneyness, option_type
            )
        else:
            return None

        if not strike:
            return None

        # Verify the strike exists in far-term options too
        far_strike_exists = not far_options[
            (far_options['strike'] == strike) &
            (far_options['option_type'] == option_type)
        ].empty

        if not far_strike_exists:
            return None

        # Get actual DTEs
        near_dte_actual = near_options[
            (near_options['strike'] == strike) &
            (near_options['option_type'] == option_type)
        ].iloc[0]['dte']

        far_dte_actual = far_options[
            (far_options['strike'] == strike) &
            (far_options['option_type'] == option_type)
        ].iloc[0]['dte']

        # Get spread price
        spread_price = self._get_spread_price(
            options_data, strike, near_dte_actual, far_dte_actual, option_type
        )

        if spread_price is None or spread_price <= 0:
            return None

        # Optional: Check minimum credit/debit requirements
        min_debit = self.entry_config.get('min_debit', 0.0)
        max_debit = self.entry_config.get('max_debit', float('inf'))

        if spread_price < min_debit or spread_price > max_debit:
            return None

        return Signal(
            date=date,
            signal_type='entry',
            strategy_name=self.name,
            underlying_price=underlying_price,
            short_strike=strike,  # Same strike for both legs
            long_strike=strike,   # Same strike for calendar spread
            dte=near_dte_actual,  # Near-term DTE for tracking
            notes=f"{self.spread_type}: Sell {near_dte_actual}DTE / Buy {far_dte_actual}DTE @ ${strike} {option_type}"
        )

    def generate_exit_signal(
        self,
        date: datetime,
        position: Position,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate exit signal for open calendar spread position."""

        # Get position details
        short_leg = position.legs[0]  # Near-term option (short)
        long_leg = position.legs[1]   # Far-term option (long)
        strike = short_leg['strike']
        option_type = short_leg['option_type']

        # Find current near-term DTE
        near_option = options_data[
            (options_data['strike'] == strike) &
            (options_data['option_type'] == option_type)
        ]

        if near_option.empty:
            return None

        # Get the option closest to original near-term DTE
        near_option_sorted = near_option.sort_values('dte')
        current_near = near_option_sorted.iloc[0] if len(near_option_sorted) > 0 else None

        if current_near is None:
            return None

        current_near_dte = current_near['dte']

        # Exit before near-term expiration (mandatory)
        dte_exit = self.exit_config.get('dte_exit', 7)
        if current_near_dte <= dte_exit:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Near-term expiration approaching: {current_near_dte} DTE <= {dte_exit}"
            )

        # Calculate current spread value
        far_option = options_data[
            (options_data['strike'] == strike) &
            (options_data['option_type'] == option_type) &
            (options_data['dte'] > current_near_dte)
        ]

        if far_option.empty:
            # Far option may have expired, exit immediately
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason="Far-term option data unavailable"
            )

        # Use the far option with DTE closest to original far DTE
        # For simplicity, use the first one found with higher DTE
        far_option_sorted = far_option.sort_values('dte')
        current_far = far_option_sorted.iloc[0]

        # Calculate current spread price
        near_price = (current_near['bid'] + current_near['ask']) / 2
        far_price = (current_far['bid'] + current_far['ask']) / 2
        current_spread_price = far_price - near_price

        # Update position
        position.current_price = current_spread_price
        position.unrealized_pnl = (current_spread_price - position.entry_price) * position.contracts * 100

        # Check profit target (for calendar spreads, we want spread to widen)
        profit_target_pct = self.exit_config.get('profit_target', 0.25)
        profit_pct = (current_spread_price - position.entry_price) / position.entry_price

        if profit_pct >= profit_target_pct:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Profit target reached: {profit_pct:.1%}"
            )

        # Check stop loss (spread collapsed)
        stop_loss_pct = self.exit_config.get('stop_loss', -0.50)
        if profit_pct <= stop_loss_pct:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Stop loss triggered: {profit_pct:.1%}"
            )

        # Check if underlying moved too far from strike
        max_move_pct = self.exit_config.get('max_underlying_move', 0.10)
        price_move = abs(underlying_price - strike) / strike

        if price_move >= max_move_pct:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Underlying moved too far: {price_move:.1%} from strike"
            )

        return None  # No exit conditions met

    def calculate_position_size(
        self,
        signal: Signal,
        account_value: float,
        **kwargs
    ) -> int:
        """
        Calculate position size based on risk management rules.

        For calendar spreads, max risk is the debit paid.
        """
        risk_per_trade_pct = kwargs.get('risk_per_trade_percent', 2.0)
        max_risk_dollars = account_value * (risk_per_trade_pct / 100)

        # For calendar spreads, we'd need the actual spread price
        # This is a simplified calculation
        # In practice, we'd get the exact debit from entry signal
        estimated_debit = 2.0  # Placeholder, would be from actual data
        max_risk_per_contract = estimated_debit * 100  # $100 per point

        contracts = int(max_risk_dollars / max_risk_per_contract)

        return max(1, contracts)  # At least 1 contract

    def _get_option_type(self) -> str:
        """Get option type based on spread type."""
        if 'put' in self.spread_type:
            return 'put'
        return 'call'


class CallCalendarSpread(CalendarSpread):
    """
    Call Calendar Spread (Time Spread).

    Setup: Sell near-term call, buy far-term call (same strike)
    Max Profit: When underlying is at strike at near-term expiration
    Max Loss: Net debit paid
    Outlook: Neutral to slightly bullish, expect low volatility
    Best conditions: Low IV, expecting IV to increase
    """

    def __init__(self, config: Dict):
        super().__init__("Call Calendar Spread", config, "call_calendar")


class PutCalendarSpread(CalendarSpread):
    """
    Put Calendar Spread (Time Spread).

    Setup: Sell near-term put, buy far-term put (same strike)
    Max Profit: When underlying is at strike at near-term expiration
    Max Loss: Net debit paid
    Outlook: Neutral to slightly bearish, expect low volatility
    Best conditions: Low IV, expecting IV to increase
    """

    def __init__(self, config: Dict):
        super().__init__("Put Calendar Spread", config, "put_calendar")


class DiagonalSpread(CalendarSpread):
    """
    Diagonal Spread (Time + Vertical Spread).

    Similar to calendar spread but with different strikes.

    Setup: Sell near-term option, buy far-term option (different strikes)
    - Call diagonal: Sell lower strike near-term, buy higher strike far-term
    - Put diagonal: Sell higher strike near-term, buy lower strike far-term

    This combines time decay with directional bias.

    Note: This is a future enhancement. For now, it inherits calendar spread
    logic but can be extended to support different strikes.
    """

    def __init__(self, config: Dict, diagonal_type: str = "call"):
        spread_type = f"{diagonal_type}_diagonal"
        super().__init__(f"{diagonal_type.title()} Diagonal Spread", config, spread_type)
        # Future: Override strike selection logic for different strikes
