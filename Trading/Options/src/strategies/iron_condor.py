"""
Iron Condor strategy implementation.

Implements Iron Condor: A market-neutral credit spread combining:
1. Bull Put Spread (lower strikes): Sell higher strike put, buy lower strike put
2. Bear Call Spread (upper strikes): Sell lower strike call, buy higher strike call

Optimal in high IV environments (60-85%) for range-bound price action with IV mean reversion.
"""

from datetime import datetime
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy, Signal, Position


class IronCondor(BaseStrategy):
    """
    Iron Condor - Market-neutral credit spread.

    Combines Bull Put Spread + Bear Call Spread to profit from:
    - Range-bound underlying price movement
    - IV contraction (volatility mean reversion)
    - Time decay on all four legs
    """

    def __init__(self, config: Dict):
        super().__init__("Iron Condor", config)
        self.entry_config = config.get('entry', {})
        self.exit_config = config.get('exit', {})
        self.debug = config.get('debug', False)
        self.spread_type = 'iron_condor'

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
        Calculate the net credit for a spread.

        Args:
            options_chain: Options chain data
            short_strike: Strike price of short option
            long_strike: Strike price of long option
            option_type: 'call' or 'put'

        Returns:
            Net credit (positive for credit spread)
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

        # For credit spreads: receive at bid for short, pay at ask for long
        short_price = short_option.iloc[0]['bid']
        long_price = long_option.iloc[0]['ask']

        return short_price - long_price

    def _find_put_strikes(
        self,
        options_chain: pd.DataFrame,
        underlying_price: float
    ) -> Optional[Tuple[float, float, float]]:
        """
        Find put spread strikes BELOW current price.

        Returns: (short_strike, long_strike, put_credit) or None
        """
        put_short_delta = self.entry_config.get('put_short_delta', 0.20)
        put_long_delta = self.entry_config.get('put_long_delta', 0.10)

        # Find strikes by delta
        short_strike = self._find_strike_by_delta(
            options_chain, put_short_delta, 'put', tolerance=0.05
        )
        long_strike = self._find_strike_by_delta(
            options_chain, put_long_delta, 'put', tolerance=0.05
        )

        if not short_strike or not long_strike:
            return None

        # Ensure short_strike > long_strike (for put spread below price)
        if long_strike >= short_strike:
            return None

        # Calculate put spread credit
        put_credit = self._get_spread_price(
            options_chain, short_strike, long_strike, 'put'
        )

        if put_credit is None or put_credit <= 0:
            return None

        return (short_strike, long_strike, put_credit)

    def _find_call_strikes(
        self,
        options_chain: pd.DataFrame,
        underlying_price: float
    ) -> Optional[Tuple[float, float, float]]:
        """
        Find call spread strikes ABOVE current price.

        Returns: (short_strike, long_strike, call_credit) or None
        """
        call_short_delta = self.entry_config.get('call_short_delta', 0.20)
        call_long_delta = self.entry_config.get('call_long_delta', 0.10)

        # Find strikes by delta
        short_strike = self._find_strike_by_delta(
            options_chain, call_short_delta, 'call', tolerance=0.05
        )
        long_strike = self._find_strike_by_delta(
            options_chain, call_long_delta, 'call', tolerance=0.05
        )

        if not short_strike or not long_strike:
            return None

        # Ensure short_strike < long_strike (for call spread above price)
        if short_strike >= long_strike:
            return None

        # Calculate call spread credit
        call_credit = self._get_spread_price(
            options_chain, short_strike, long_strike, 'call'
        )

        if call_credit is None or call_credit <= 0:
            return None

        return (short_strike, long_strike, call_credit)

    def _get_iron_condor_credit(
        self,
        options_chain: pd.DataFrame,
        put_short: float,
        put_long: float,
        call_short: float,
        call_long: float
    ) -> Optional[float]:
        """Calculate total credit received for Iron Condor."""
        # Put spread credit
        put_credit = self._get_spread_price(options_chain, put_short, put_long, 'put')

        # Call spread credit
        call_credit = self._get_spread_price(options_chain, call_short, call_long, 'call')

        if put_credit is None or call_credit is None:
            return None

        total_credit = put_credit + call_credit

        # Validate against min threshold
        min_credit = self.entry_config.get('min_credit', 1.5)
        if total_credit < min_credit:
            return None

        return total_credit

    def generate_entry_signal(
        self,
        date: datetime,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate entry signal for Iron Condor."""

        # Filter options by DTE range
        dte_min = self.entry_config.get('dte_min', 30)
        dte_max = self.entry_config.get('dte_max', 45)

        valid_options = options_data[
            (options_data['dte'] >= dte_min) &
            (options_data['dte'] <= dte_max)
        ].copy()

        if valid_options.empty:
            return None

        # Check IV Percentile filters
        iv_percentile = kwargs.get('iv_percentile')
        iv_percentile_max = self.entry_config.get('iv_percentile_max', 85)
        iv_percentile_min = self.entry_config.get('iv_percentile_min', 60)

        if iv_percentile is not None and (iv_percentile > iv_percentile_max or iv_percentile < iv_percentile_min):
            if self.debug:
                print(f"  ❌ IV Percentile filter failed: {iv_percentile:.1f}%, range=[{iv_percentile_min}, {iv_percentile_max}]")
            return None

        # Find put spread strikes (below current price)
        put_strikes = self._find_put_strikes(valid_options, underlying_price)
        if not put_strikes:
            if self.debug:
                print(f"  ❌ Could not find put spread strikes")
            return None

        put_short, put_long, put_credit = put_strikes

        # Find call spread strikes (above current price)
        call_strikes = self._find_call_strikes(valid_options, underlying_price)
        if not call_strikes:
            if self.debug:
                print(f"  ❌ Could not find call spread strikes")
            return None

        call_short, call_long, call_credit = call_strikes

        # Get total credit
        total_credit = self._get_iron_condor_credit(
            valid_options, put_short, put_long, call_short, call_long
        )

        if not total_credit:
            if self.debug:
                print(f"  ❌ Total credit below minimum threshold")
            return None

        # Validate wing widths
        max_wing_width = self.entry_config.get('max_wing_width', 10.0)
        put_width = put_short - put_long
        call_width = call_long - call_short

        if put_width > max_wing_width or call_width > max_wing_width:
            if self.debug:
                print(f"  ❌ Wing widths exceed limit: put={put_width:.2f}, call={call_width:.2f}")
            return None

        # Get DTE for tracking
        dte = valid_options.iloc[0]['dte']

        return Signal(
            date=date,
            signal_type='entry',
            strategy_name=self.name,
            underlying_price=underlying_price,
            # Store all four strikes
            put_short_strike=put_short,
            put_long_strike=put_long,
            call_short_strike=call_short,
            call_long_strike=call_long,
            total_credit=total_credit,
            dte=dte,
            notes=f"IC: Sell {put_short:.0f}P/{call_short:.0f}C, Buy {put_long:.0f}P/{call_long:.0f}C (${total_credit:.2f} credit)"
        )

    def generate_exit_signal(
        self,
        date: datetime,
        position: Position,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate exit signal for open Iron Condor position."""

        # Extract strikes from 4-leg position
        if len(position.legs) < 4:
            return None

        put_short = position.legs[0]['strike']  # Sell put
        put_long = position.legs[1]['strike']   # Buy put
        call_short = position.legs[2]['strike']  # Sell call
        call_long = position.legs[3]['strike']   # Buy call

        # Get current Iron Condor value
        current_value = self._get_current_iron_condor_value(
            options_data, put_short, put_long, call_short, call_long
        )

        if current_value is None:
            return None

        position.current_price = current_value
        position.unrealized_pnl = (position.entry_price - current_value) * position.contracts * 100

        # Calculate profit/loss for exit checks
        current_profit = position.entry_price - current_value

        # Determine max risk (wider wing - credit)
        put_width = put_short - put_long
        call_width = call_long - call_short
        max_width = max(put_width, call_width)
        max_loss = (max_width - position.entry_price) * position.contracts * 100

        # Check profit target (percentage of max profit)
        profit_target = self.exit_config.get('profit_target', 0.50)
        max_profit = position.entry_price * position.contracts * 100

        if current_profit > 0 and max_profit > 0:
            current_profit_pct = (current_profit * position.contracts * 100) / max_profit
            if current_profit_pct >= profit_target:
                return Signal(
                    date=date,
                    signal_type='exit',
                    strategy_name=self.name,
                    underlying_price=underlying_price,
                    exit_reason=f"Profit target reached: {current_profit_pct:.1%} (target: {profit_target:.1%})"
                )

        # Check stop loss (percentage of max loss)
        stop_loss_pct = self.exit_config.get('stop_loss', 0.75)
        if current_profit < 0 and max_loss > 0:
            current_loss = abs(current_profit * position.contracts * 100)
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
        current_dte = options_data.iloc[0]['dte'] if not options_data.empty else 0
        dte_min = self.exit_config.get('dte_min', 14)

        if current_dte <= dte_min:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"DTE exit: {current_dte} <= {dte_min}"
            )

        # Check price breach (early warning system)
        breach_threshold = self.exit_config.get('breach_threshold', 0.02)

        # Check if price approaching short put
        put_breach_price = put_short * (1 + breach_threshold)
        if underlying_price <= put_breach_price:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Put breach warning: price {underlying_price:.0f} <= {put_breach_price:.0f}"
            )

        # Check if price approaching short call
        call_breach_price = call_short * (1 - breach_threshold)
        if underlying_price >= call_breach_price:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Call breach warning: price {underlying_price:.0f} >= {call_breach_price:.0f}"
            )

        return None  # No exit conditions met

    def _get_current_iron_condor_value(
        self,
        options_chain: pd.DataFrame,
        put_short: float,
        put_long: float,
        call_short: float,
        call_long: float
    ) -> Optional[float]:
        """Calculate current buyback cost for entire Iron Condor."""
        put_spread_value = self._get_spread_price(
            options_chain, put_short, put_long, 'put'
        )
        call_spread_value = self._get_spread_price(
            options_chain, call_short, call_long, 'call'
        )

        if put_spread_value is None or call_spread_value is None:
            return None

        return put_spread_value + call_spread_value

    def calculate_position_size(
        self,
        signal: Signal,
        account_value: float,
        **kwargs
    ) -> int:
        """
        Calculate position size based on max risk and available budget.

        For Iron Condor:
        - Max risk = wider wing width - total credit received
        - Position size limited by available_risk_budget
        """
        available_risk_budget = kwargs.get('available_risk_budget', float('inf'))

        if available_risk_budget <= 0:
            return 0

        # Calculate max risk per contract
        put_width = signal.put_short_strike - signal.put_long_strike
        call_width = signal.call_long_strike - signal.call_short_strike
        max_width = max(put_width, call_width)

        # Max risk = (wider wing - credit) * $100
        max_risk_per_contract = (max_width - signal.total_credit) * 100

        # Check for Kelly sizing
        full_config = kwargs.get('full_config')
        if full_config:
            position_sizing = full_config.get('position_sizing', {})
            method = position_sizing.get('method', 'fixed_risk')

            if method == 'kelly':
                kelly_pct_dict = position_sizing.get('kelly_pct', {})
                kelly_pct = kelly_pct_dict.get('iron_condor')

                if kelly_pct is not None:
                    kelly_risk = account_value * kelly_pct
                    contracts_kelly = int(kelly_risk / max_risk_per_contract)
                else:
                    print(f"⚠ Kelly % not found for iron_condor, defaulting to 1 contract")
                    contracts_kelly = 1

                # Cap by available budget
                contracts_budget = int(available_risk_budget / max_risk_per_contract)
                contracts = min(contracts_kelly, contracts_budget)

                return max(1, contracts) if contracts > 0 else 0

        # Fixed risk method: use all available risk budget
        contracts = int(available_risk_budget / max_risk_per_contract)

        return max(1, contracts) if contracts > 0 else 0
