"""
Vertical spread strategies implementation.

Implements four types of vertical spreads:
1. Bull Put Spread (credit spread - neutral to bullish)
2. Bear Call Spread (credit spread - neutral to bearish)
3. Bull Call Spread (debit spread - moderately bullish)
4. Bear Put Spread (debit spread - moderately bearish)
"""

from datetime import datetime
from typing import Dict, Optional
import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, Signal, Position


class VerticalSpread(BaseStrategy):
    """Base class for vertical spread strategies."""

    def __init__(self, name: str, config: Dict, spread_type: str):
        """
        Initialize vertical spread strategy.

        Args:
            name: Strategy name
            config: Strategy configuration
            spread_type: Type of spread (bull_put, bear_call, bull_call, bear_put)
        """
        super().__init__(name, config)
        self.spread_type = spread_type
        self.entry_config = config.get('entry', {})
        self.exit_config = config.get('exit', {})

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
            target_delta: Target delta value (e.g., 0.30)
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
        short_strike: float,
        long_strike: float,
        option_type: str
    ) -> Optional[float]:
        """
        Calculate the net premium for the spread.

        Args:
            options_chain: Options chain data
            short_strike: Strike price of short option
            long_strike: Strike price of long option
            option_type: 'call' or 'put'

        Returns:
            Net premium (positive for credit, negative for debit)
        """
        short_option = options_chain[
            (options_chain['strike'] == short_strike) &
            (options_chain['option_type'] == option_type)
        ]
        long_option = options_chain[
            (options_chain['strike'] == long_strike) &
            (options_chain['option_type'] == option_type)
        ]

        if short_option.empty or long_option.empty:
            return None

        # For credit spreads: receive premium (short - long is positive)
        # For debit spreads: pay premium (short - long is negative)
        short_price = short_option.iloc[0]['bid']  # We sell at bid
        long_price = long_option.iloc[0]['ask']     # We buy at ask

        return short_price - long_price

    def generate_entry_signal(
        self,
        date: datetime,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate entry signal for vertical spread."""

        # Filter options by DTE range
        dte_min = self.entry_config.get('dte_min', 30)
        dte_max = self.entry_config.get('dte_max', 45)

        valid_options = options_data[
            (options_data['dte'] >= dte_min) &
            (options_data['dte'] <= dte_max)
        ].copy()

        if valid_options.empty:
            return None

        # Check market filters if provided
        vix = kwargs.get('vix')
        vix_max = kwargs.get('vix_max', float('inf'))
        vix_min = kwargs.get('vix_min', 0)

        if vix and (vix > vix_max or vix < vix_min):
            return None  # Market conditions not favorable

        # Find strikes based on delta targeting
        option_type = self._get_option_type()
        short_delta = self.entry_config.get('short_delta', 0.30)
        long_delta = self.entry_config.get('long_delta', 0.20)

        short_strike = self._find_strike_by_delta(valid_options, short_delta, option_type)
        long_strike = self._find_strike_by_delta(valid_options, long_delta, option_type)

        if not short_strike or not long_strike:
            return None

        # Get spread price
        spread_price = self._get_spread_price(
            valid_options, short_strike, long_strike, option_type
        )

        if spread_price is None or spread_price <= 0:
            return None  # Invalid pricing or unprofitable spread

        # Get DTE for the selected expiration
        dte = valid_options[valid_options['strike'] == short_strike].iloc[0]['dte']

        return Signal(
            date=date,
            signal_type='entry',
            strategy_name=self.name,
            underlying_price=underlying_price,
            short_strike=short_strike,
            long_strike=long_strike,
            dte=dte,
            notes=f"{self.spread_type}: Sell {short_strike} / Buy {long_strike} {option_type}"
        )

    def generate_exit_signal(
        self,
        date: datetime,
        position: Position,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate exit signal for open vertical spread position."""

        # Get current position price
        short_leg = position.legs[0]  # Short option
        long_leg = position.legs[1]   # Long option

        current_price = self._get_spread_price(
            options_data,
            short_leg['strike'],
            long_leg['strike'],
            short_leg['option_type']
        )

        if current_price is None:
            return None

        position.current_price = current_price
        position.unrealized_pnl = (current_price - position.entry_price) * position.contracts * 100

        # Calculate profit/loss for exit checks
        # For credit spreads: entry_price is positive (credit received)
        # For debit spreads: entry_price is negative (debit paid)

        # Determine strike width for max loss calculation
        strike_width = abs(short_leg['strike'] - long_leg['strike'])

        # For credit spreads (entry_price > 0):
        #   Max profit = entry_price (credit received)
        #   Max loss = strike_width - entry_price
        # For debit spreads (entry_price < 0):
        #   Max profit = strike_width - abs(entry_price)
        #   Max loss = abs(entry_price) (debit paid)

        is_credit_spread = position.entry_price > 0

        if is_credit_spread:
            max_profit = position.entry_price
            max_loss = strike_width - position.entry_price
            # Profit: spread decreases in value (current < entry)
            current_profit = position.entry_price - current_price
        else:
            # Debit spread
            max_profit = strike_width - abs(position.entry_price)
            max_loss = abs(position.entry_price)
            # Profit: spread increases in value (current > entry)
            current_profit = current_price - position.entry_price

        # Check profit target (percentage of max profit)
        profit_target = self.exit_config.get('profit_target', 0.50)
        if current_profit > 0:
            current_profit_pct = current_profit / max_profit
            if current_profit_pct >= profit_target:
                return Signal(
                    date=date,
                    signal_type='exit',
                    strategy_name=self.name,
                    underlying_price=underlying_price,
                    exit_reason=f"Profit target reached: {current_profit_pct:.1%} (target: {profit_target:.1%})"
                )

        # Check stop loss (percentage of max loss)
        stop_loss_pct = self.exit_config.get('stop_loss', 0.50)
        if current_profit < 0:
            current_loss = abs(current_profit)
            current_loss_pct = current_loss / max_loss
            if current_loss_pct >= stop_loss_pct:
                return Signal(
                    date=date,
                    signal_type='exit',
                    strategy_name=self.name,
                    underlying_price=underlying_price,
                    exit_reason=f"Stop loss triggered: {current_loss_pct:.1%} loss (limit: {stop_loss_pct:.1%})"
                )

        # Check DTE-based exit
        current_dte = options_data[
            options_data['strike'] == short_leg['strike']
        ].iloc[0]['dte'] if not options_data.empty else 0

        dte_min = self.exit_config.get('dte_min', 21)
        if current_dte <= dte_min:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"DTE exit: {current_dte} <= {dte_min}"
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

        For vertical spreads, we calculate based on max risk per trade.
        """
        risk_per_trade_pct = kwargs.get('risk_per_trade_percent', 2.0)
        max_risk_dollars = account_value * (risk_per_trade_pct / 100)

        # Max risk for vertical spread = strike width - premium received (for credit)
        strike_width = abs(signal.short_strike - signal.long_strike)

        # This would need the actual spread price - simplified for now
        # In practice, we'd get this from the options data
        max_risk_per_contract = strike_width * 100  # $100 per point

        contracts = int(max_risk_dollars / max_risk_per_contract)

        return max(1, contracts)  # At least 1 contract

    def _get_option_type(self) -> str:
        """Get option type based on spread type."""
        if self.spread_type in ['bull_put_spread', 'bear_put_spread']:
            return 'put'
        return 'call'


class BullPutSpread(VerticalSpread):
    """
    Bull Put Spread (Credit Spread).

    Setup: Sell higher strike put, buy lower strike put
    Max Profit: Premium collected
    Max Loss: Strike width - premium
    Outlook: Neutral to bullish
    """

    def __init__(self, config: Dict):
        super().__init__("Bull Put Spread", config, "bull_put_spread")


class BearCallSpread(VerticalSpread):
    """
    Bear Call Spread (Credit Spread).

    Setup: Sell lower strike call, buy higher strike call
    Max Profit: Premium collected
    Max Loss: Strike width - premium
    Outlook: Neutral to bearish
    """

    def __init__(self, config: Dict):
        super().__init__("Bear Call Spread", config, "bear_call_spread")


class BullCallSpread(VerticalSpread):
    """
    Bull Call Spread (Debit Spread).

    Setup: Buy lower strike call, sell higher strike call
    Max Profit: Strike width - premium paid
    Max Loss: Premium paid
    Outlook: Moderately bullish
    """

    def __init__(self, config: Dict):
        super().__init__("Bull Call Spread", config, "bull_call_spread")


class BearPutSpread(VerticalSpread):
    """
    Bear Put Spread (Debit Spread).

    Setup: Buy higher strike put, sell lower strike put
    Max Profit: Strike width - premium paid
    Max Loss: Premium paid
    Outlook: Moderately bearish
    """

    def __init__(self, config: Dict):
        super().__init__("Bear Put Spread", config, "bear_put_spread")
