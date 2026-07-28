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

    def _leg_rows(self, chain, short_strike, long_strike, option_type, expiration=None):
        """The (short_row, long_row) option quotes for this spread, or None if either is missing.

        Pass `expiration` whenever it is known: a daily chain quotes the same strike at MANY
        expirations, and iloc[0] on an unfiltered match silently prices the leg off whichever
        expiration happens to come first (usually the nearest weekly, not the one held).
        """
        s = chain[(chain['strike'] == short_strike) & (chain['option_type'] == option_type)]
        l = chain[(chain['strike'] == long_strike) & (chain['option_type'] == option_type)]
        if expiration is not None:
            s = s[s['expiration'] == expiration]
            l = l[l['expiration'] == expiration]
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
        expiration=None,
    ) -> Optional[float]:
        """Signed cash to OPEN the spread, per share: >0 = net debit paid, <0 = net credit received."""
        rows = self._leg_rows(options_chain, short_strike, long_strike, option_type, expiration)
        if rows is None:
            return None
        short, long = rows
        return net_open([(short['bid'], short['ask'], False), (long['bid'], long['ask'], True)], fraction, extra)

    def _is_credit_spread(self) -> bool:
        """Bull put / bear call collect a credit; bull call / bear put pay a debit."""
        return self.spread_type in ('bull_put_spread', 'bear_call_spread')

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

        # Entry window: the optimizer passes a single dte_target (window = target ± tolerance,
        # mirroring the calendar's near_dte/dte_tolerance design); a plain config gives
        # [dte_min, dte_max] and targets the window midpoint. dte_target takes precedence.
        dte_target = self.entry_config.get('dte_target')
        if dte_target is not None:
            tolerance = self.entry_config.get('dte_tolerance', 5)
            dte_lo, dte_hi = dte_target - tolerance, dte_target + tolerance
        else:
            dte_lo = self.entry_config.get('dte_min', 30)
            dte_hi = self.entry_config.get('dte_max', 45)
            dte_target = (dte_lo + dte_hi) / 2.0

        option_type = self._get_option_type()
        candidates = options_data[
            (options_data['dte'] >= dte_lo) &
            (options_data['dte'] <= dte_hi) &
            (options_data['option_type'] == option_type)
        ]

        # The position must OUTLIVE the DTE exit rule, or that exit is already true at entry and
        # the trade is force-closed immediately (the degenerate ~1-day trades the 2026-07-12
        # calendar audit found; same failure class here).
        exit_dte = self.exit_config.get('dte_min', 21)
        candidates = candidates[candidates['dte'] > exit_dte]

        if candidates.empty:
            return None

        # Check VIX filters - strategy-specific first, then global fallback
        vix = kwargs.get('vix')
        vix_max = self.entry_config.get('vix_max', kwargs.get('vix_max', 100))
        vix_min = self.entry_config.get('vix_min', kwargs.get('vix_min', 0))

        if vix is not None and (vix > vix_max or vix < vix_min):
            if self.debug:
                print(f"  ❌ VIX filter failed: {vix:.1f}, range=[{vix_min}, {vix_max}]")
            return None  # VIX outside strategy's acceptable range

        # Pin BOTH legs to the ONE expiration whose DTE is closest to the target. Delta-targeting
        # across the whole window let each leg come from a different expiration — a diagonal
        # priced and risk-modeled as if it were a vertical.
        dte_pick = min(candidates['dte'].unique(), key=lambda d: abs(d - dte_target))
        chain = candidates[candidates['dte'] == dte_pick]

        # Find strikes based on delta targeting (within the pinned expiration only)
        short_delta = self.entry_config.get('short_delta', 0.30)
        long_delta = self.entry_config.get('long_delta', 0.20)

        short_strike = self._find_strike_by_delta(chain, short_delta, option_type)
        long_strike = self._find_strike_by_delta(chain, long_delta, option_type)

        if not short_strike or not long_strike or short_strike == long_strike:
            return None  # Need two distinct strikes (degenerate spread otherwise)

        # Price from the exact legs selected above; net debit (>0) or credit (<0) at the limit fill
        rows = self._leg_rows(chain, short_strike, long_strike, option_type)
        if rows is None:
            return None  # A leg is missing from the chain
        short_row, long_row = rows
        spread_price = net_open(
            [(short_row['bid'], short_row['ask'], False), (long_row['bid'], long_row['ask'], True)],
            fraction, extra
        )

        # A credit spread must OPEN at a credit and a debit spread at a debit; the wrong sign means
        # delta targeting picked inverted/pathological strikes and every max-profit/max-loss figure
        # downstream would be nonsense.
        if self._is_credit_spread():
            if spread_price >= 0:
                return None
        elif spread_price <= 0:
            return None

        signal = Signal(
            date=date,
            signal_type='entry',
            strategy_name=self.name,
            underlying_price=underlying_price,
            short_strike=short_strike,
            long_strike=long_strike,
            dte=int(dte_pick),
            notes=f"{self.spread_type}: Sell {short_strike} / Buy {long_strike} {option_type} @ {int(dte_pick)}DTE"
        )
        # Both legs share this expiration; exits re-quote against it, never a lookalike strike
        # at some other expiration.
        signal.expiration = short_row['expiration']
        return signal

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
        stop_slip = kwargs.get('stop_slippage', 0.0)
        short_leg = position.legs[0]  # Short option
        long_leg = position.legs[1]   # Long option
        expiration = short_leg.get('expiration')  # both legs share it (pinned at entry)
        today = pd.Timestamp(date).normalize()

        # Defined risk from the signed open cost: credit spread (entry<0) vs debit spread (entry>0).
        strike_width = abs(short_leg['strike'] - long_leg['strike'])
        if position.entry_price < 0:
            max_profit = -position.entry_price          # credit collected
            max_loss = strike_width - max_profit
        else:
            max_profit = strike_width - position.entry_price
            max_loss = position.entry_price             # debit paid

        # Expiration reached: no quotes remain, the position settles at intrinsic value.
        # (Normally the DTE exit fires well before this; settlement is the safety net that keeps a
        # data gap from leaving a zombie position marked at its entry price until end of backtest.)
        if expiration is not None and pd.Timestamp(expiration).normalize() <= today:
            def _intrinsic(strike, opt_type):
                return (max(strike - underlying_price, 0.0) if opt_type == 'put'
                        else max(underlying_price - strike, 0.0))
            close_val = (_intrinsic(long_leg['strike'], long_leg['option_type'])
                         - _intrinsic(short_leg['strike'], short_leg['option_type']))
            position.current_price = close_val
            position.unrealized_pnl = (close_val - position.entry_price) * position.contracts * 100
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason="Expired: settled at intrinsic value"
            )

        # Re-quote the exact held contracts (strike AND expiration). Matching on strike alone
        # priced the exit off whichever expiration listed that strike first — usually the nearest
        # weekly, whose near-zero time value systematically faked profits on credit spreads.
        rows = self._leg_rows(options_data, short_leg['strike'], long_leg['strike'],
                              short_leg['option_type'], expiration)
        if rows is None:
            return None  # data gap while the expiration is still live -> hold, re-check next day
        short, long = rows

        # Planned exits fill at the limit fraction; a stop-loss is a market order (handled below).
        legs = [(short['bid'], short['ask'], False), (long['bid'], long['ask'], True)]
        close_val = net_close(legs, lf, extra)
        position.current_price = close_val
        profit = close_val - position.entry_price  # per share, >0 = gain
        position.unrealized_pnl = profit * position.contracts * 100

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
        # market fraction so the booked exit reflects crossing the spread. On top of that, a
        # multi-leg stop can't rest on the book (e.g. Robinhood), so the fill lands LATER and WORSE
        # than the trigger: book an extra `stop_slip` fraction of the entry credit/debit of
        # monitoring-lag overshoot (parity with the calendar's stop model).
        stop_loss_pct = self.exit_config.get('stop_loss', 0.50)
        if profit < 0 and max_loss > 0 and (-profit) / max_loss >= stop_loss_pct:
            position.current_price = net_close(legs, mf, extra) - stop_slip * abs(position.entry_price)
            position.unrealized_pnl = (position.current_price - position.entry_price) * position.contracts * 100
            return Signal(
                date=date,
                signal_type='exit',
                strategy_name=self.name,
                underlying_price=underlying_price,
                exit_reason=f"Stop loss triggered: {(-profit) / max_loss:.1%} loss (limit: {stop_loss_pct:.1%})"
            )

        # DTE-based exit, computed from the position's own expiration (the old chain lookup took
        # the FIRST row at the short strike — any expiration — so this trigger fired on the wrong
        # calendar entirely).
        if expiration is not None:
            current_dte = (pd.Timestamp(expiration).normalize() - today).days
        else:
            current_dte = int(short['dte'])

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

        # Max risk per contract from the ACTUAL open price when the backtester provides it
        # (credit: width - credit; debit: the debit) — the same formula the risk-budget
        # accounting uses, so sizing and budget agree. Fall back to full width otherwise.
        strike_width = abs(signal.short_strike - signal.long_strike)
        entry_price = kwargs.get('entry_price')  # signed: >0 debit paid, <0 credit received
        if entry_price is not None and entry_price < 0:
            max_risk_per_contract = (strike_width + entry_price) * 100
        elif entry_price is not None and entry_price > 0:
            max_risk_per_contract = entry_price * 100
        else:
            max_risk_per_contract = strike_width * 100
        if max_risk_per_contract <= 0:
            max_risk_per_contract = strike_width * 100  # arbitrage-looking quote: be conservative

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
