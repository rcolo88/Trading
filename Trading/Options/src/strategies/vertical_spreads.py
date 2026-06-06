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
from ..utils.execution import net_open, net_close


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
        self.debug = config.get('debug', False)

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

    def _leg_rows(self, chain, short_strike, long_strike, option_type):
        """The (short_row, long_row) option quotes for this spread, or None if either is missing."""
        s = chain[(chain['strike'] == short_strike) & (chain['option_type'] == option_type)]
        l = chain[(chain['strike'] == long_strike) & (chain['option_type'] == option_type)]
        if s.empty or l.empty:
            return None
        return s.iloc[0], l.iloc[0]

    def _get_spread_price(
        self,
        options_chain: pd.DataFrame,
        short_strike: float,
        long_strike: float,
        option_type: str,
        fraction: float = 0.5,
        extra: float = 0.0,
    ) -> Optional[float]:
        """Signed cash to OPEN the spread, per share: >0 = net debit paid, <0 = net credit received."""
        rows = self._leg_rows(options_chain, short_strike, long_strike, option_type)
        if rows is None:
            return None
        short, long = rows
        return net_open([(short['bid'], short['ask'], False), (long['bid'], long['ask'], True)], fraction, extra)

    def generate_entry_signal(
        self,
        date: datetime,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate entry signal for vertical spread."""

        fraction = kwargs.get('fill_fraction', 0.5)
        extra = kwargs.get('extra_slippage', 0.0)

        # Filter options by DTE range
        dte_min = self.entry_config.get('dte_min', 30)
        dte_max = self.entry_config.get('dte_max', 45)

        valid_options = options_data[
            (options_data['dte'] >= dte_min) &
            (options_data['dte'] <= dte_max)
        ].copy()

        if valid_options.empty:
            return None

        # Check VIX filters - strategy-specific first, then global fallback
        vix = kwargs.get('vix')
        vix_max = self.entry_config.get('vix_max', kwargs.get('vix_max', 100))
        vix_min = self.entry_config.get('vix_min', kwargs.get('vix_min', 0))

        if vix is not None and (vix > vix_max or vix < vix_min):
            if self.debug:
                print(f"  ❌ VIX filter failed: {vix:.1f}, range=[{vix_min}, {vix_max}]")
            return None  # VIX outside strategy's acceptable range

        # Find strikes based on delta targeting
        option_type = self._get_option_type()
        short_delta = self.entry_config.get('short_delta', 0.30)
        long_delta = self.entry_config.get('long_delta', 0.20)

        short_strike = self._find_strike_by_delta(valid_options, short_delta, option_type)
        long_strike = self._find_strike_by_delta(valid_options, long_delta, option_type)

        if not short_strike or not long_strike or short_strike == long_strike:
            return None  # Need two distinct strikes (degenerate spread otherwise)

        # Net debit (>0) or credit (<0) to open, at the limit-fill price
        spread_price = self._get_spread_price(
            valid_options, short_strike, long_strike, option_type, fraction, extra
        )

        if spread_price is None:
            return None  # A leg is missing from the chain

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

        lf = kwargs.get('limit_fraction', 0.5)
        mf = kwargs.get('market_fraction', 1.0)
        extra = kwargs.get('extra_slippage', 0.0)
        short_leg = position.legs[0]  # Short option
        long_leg = position.legs[1]   # Long option

        rows = self._leg_rows(options_data, short_leg['strike'], long_leg['strike'], short_leg['option_type'])
        if rows is None:
            return None
        short, long = rows

        # Planned exits fill at the limit fraction; a stop-loss is a market order (handled below).
        legs = [(short['bid'], short['ask'], False), (long['bid'], long['ask'], True)]
        close_val = net_close(legs, lf, extra)
        position.current_price = close_val
        profit = close_val - position.entry_price  # per share, >0 = gain
        position.unrealized_pnl = profit * position.contracts * 100

        # Defined risk from the signed open cost: credit spread (entry<0) vs debit spread (entry>0).
        strike_width = abs(short_leg['strike'] - long_leg['strike'])
        if position.entry_price < 0:
            max_profit = -position.entry_price          # credit collected
            max_loss = strike_width - max_profit
        else:
            max_profit = strike_width - position.entry_price
            max_loss = position.entry_price             # debit paid

        # Check profit target (percentage of max profit)
        profit_target = self.exit_config.get('profit_target', 0.50)
        if profit > 0 and max_profit > 0 and profit / max_profit >= profit_target:
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Profit target reached: {profit / max_profit:.1%} (target: {profit_target:.1%})"
            )

        # Check stop loss (percentage of max loss). A stop is a market order — refill at the wider
        # market fraction so the booked exit reflects crossing the spread.
        stop_loss_pct = self.exit_config.get('stop_loss', 0.50)
        if profit < 0 and max_loss > 0 and (-profit) / max_loss >= stop_loss_pct:
            position.current_price = net_close(legs, mf, extra)
            position.unrealized_pnl = (position.current_price - position.entry_price) * position.contracts * 100
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Stop loss triggered: {(-profit) / max_loss:.1%} loss (limit: {stop_loss_pct:.1%})"
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
        Position size is constrained by available risk budget.
        Supports both fixed risk and Kelly Criterion methods.
        """
        # Get available risk budget (passed from backtester)
        available_risk_budget = kwargs.get('available_risk_budget', float('inf'))

        # If no risk budget available, return 0 contracts
        if available_risk_budget <= 0:
            return 0

        # Max risk for vertical spread = strike width (conservative estimate)
        strike_width = abs(signal.short_strike - signal.long_strike)
        max_risk_per_contract = strike_width * 100  # $100 per point

        # Check if full_config provided
        full_config = kwargs.get('full_config')

        if full_config:
            position_sizing = full_config.get('position_sizing', {})
            method = position_sizing.get('method', 'fixed_risk')

            if method == 'kelly':
                # Use Kelly Criterion from config
                kelly_pct_dict = position_sizing.get('kelly_pct', {})
                kelly_pct = kelly_pct_dict.get(self.spread_type)

                if kelly_pct is not None:
                    # Kelly sizing: risk a percentage of portfolio
                    kelly_risk_dollars = account_value * kelly_pct
                    contracts_kelly = int(kelly_risk_dollars / max_risk_per_contract)
                else:
                    print(f"⚠ Kelly % not found for {self.spread_type}, defaulting to 1 contract")
                    contracts_kelly = 1

                # Cap by available risk budget
                contracts_budget = int(available_risk_budget / max_risk_per_contract)
                contracts = min(contracts_kelly, contracts_budget)

                return max(1, contracts) if contracts > 0 else 0

        # Fixed risk method: use all available risk budget
        contracts = int(available_risk_budget / max_risk_per_contract)

        return max(1, contracts) if contracts > 0 else 0

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
