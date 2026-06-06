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
from ..utils.execution import net_close


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

        # Check VIX filters
        vix = kwargs.get('vix')
        vix_max = self.entry_config.get('vix_max', 25)
        vix_min = self.entry_config.get('vix_min', 15)

        if vix is not None and (vix > vix_max or vix < vix_min):
            if self.debug:
                print(f"  ❌ VIX filter failed: {vix:.1f}, range=[{vix_min}, {vix_max}]")
            return None

        # Pin ALL four legs to a single expiration (the one nearest the DTE-window midpoint) so the
        # spread is priced and managed consistently — otherwise strikes leak across expirations.
        target_dte = (dte_min + dte_max) / 2
        exp_dte = valid_options.groupby('expiration')['dte'].first()
        chosen_exp = (exp_dte - target_dte).abs().idxmin()
        valid_options = valid_options[valid_options['expiration'] == chosen_exp]

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
        dte = int(valid_options.iloc[0]['dte'])

        # Signal carries only the base dataclass fields; the four IC strikes + credit + expiration
        # are attached as attributes (the engine and calculate_position_size read them back).
        signal = Signal(
            date=date,
            signal_type='entry',
            strategy_name=self.name,
            underlying_price=underlying_price,
            dte=dte,
            notes=f"IC: Sell {put_short:.0f}P/{call_short:.0f}C, Buy {put_long:.0f}P/{call_long:.0f}C (${total_credit:.2f} credit)"
        )
        signal.put_short_strike = put_short
        signal.put_long_strike = put_long
        signal.call_short_strike = call_short
        signal.call_long_strike = call_long
        signal.total_credit = total_credit
        signal.expiration = chosen_exp
        return signal

    def generate_exit_signal(
        self,
        date: datetime,
        position: Position,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """Generate exit signal for open Iron Condor position."""
        lf = kwargs.get('limit_fraction', 0.5)
        mf = kwargs.get('market_fraction', 1.0)
        extra = kwargs.get('extra_slippage', 0.0)

        if len(position.legs) < 4:
            return None
        exp = position.legs[0].get('expiration')

        # Current quotes for all four legs, matched to the position's expiration.
        legs_q = []
        for leg in position.legs:
            row = options_data[
                (options_data['strike'] == leg['strike']) &
                (options_data['option_type'] == leg['option_type'])
            ]
            if exp is not None and 'expiration' in options_data.columns:
                row = row[row['expiration'] == exp]
            if row.empty:
                return None  # a leg isn't quoted today; managed (DTE) exit fires before expiry
            r = row.iloc[0]
            legs_q.append((r['bid'], r['ask'], leg['position'] == 'long'))

        # Value to close (signed). entry_price is the signed open cost (<0 = net credit received).
        close_val = net_close(legs_q, lf, extra)
        position.current_price = close_val
        profit = close_val - position.entry_price          # per share, >0 = gain
        position.unrealized_pnl = profit * position.contracts * 100

        # Defined risk from the wings and the credit collected.
        put_width = position.legs[0]['strike'] - position.legs[1]['strike']
        call_width = position.legs[3]['strike'] - position.legs[2]['strike']
        credit = -position.entry_price
        max_profit = credit
        max_loss = max(put_width, call_width) - credit

        # Profit target (fraction of the credit captured)
        profit_target = self.exit_config.get('profit_target', 0.50)
        if profit > 0 and max_profit > 0 and profit / max_profit >= profit_target:
            return Signal(date=date, signal_type='exit', strategy_name=self.name,
                          underlying_price=underlying_price,
                          exit_reason=f"Profit target reached: {profit / max_profit:.1%} (target: {profit_target:.1%})")

        # Stop loss — a market order: refill at the wider market fraction.
        stop_loss_pct = self.exit_config.get('stop_loss', 0.75)
        if profit < 0 and max_loss > 0 and (-profit) / max_loss >= stop_loss_pct:
            position.current_price = net_close(legs_q, mf, extra)
            position.unrealized_pnl = (position.current_price - position.entry_price) * position.contracts * 100
            return Signal(date=date, signal_type='exit', strategy_name=self.name,
                          underlying_price=underlying_price,
                          exit_reason=f"Stop loss triggered: {(-profit) / max_loss:.1%} loss (limit: {stop_loss_pct:.1%})")

        # DTE exit (gamma ramps inside ~21 DTE) — days to the position's expiration.
        dte_min = self.exit_config.get('dte_min', 21)
        current_dte = (pd.Timestamp(exp) - pd.Timestamp(date)).days if exp is not None else 0
        if current_dte <= dte_min:
            return Signal(date=date, signal_type='exit', strategy_name=self.name,
                          underlying_price=underlying_price,
                          exit_reason=f"DTE exit: {current_dte} <= {dte_min}")

        # Breach warnings (price reaches a short strike)
        breach = self.exit_config.get('breach_threshold', 0.02)
        put_short, call_short = position.legs[0]['strike'], position.legs[2]['strike']
        if underlying_price <= put_short * (1 + breach):
            return Signal(date=date, signal_type='exit', strategy_name=self.name,
                          underlying_price=underlying_price,
                          exit_reason=f"Put breach: {underlying_price:.0f} <= {put_short * (1 + breach):.0f}")
        if underlying_price >= call_short * (1 - breach):
            return Signal(date=date, signal_type='exit', strategy_name=self.name,
                          underlying_price=underlying_price,
                          exit_reason=f"Call breach: {underlying_price:.0f} >= {call_short * (1 - breach):.0f}")

        return None

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
