"""
Optopsy backtesting wrapper.

This module provides integration with the Optopsy library for backtesting
options strategies. It handles data formatting, strategy execution, and
result aggregation.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
import optopsy as op  # Will be imported once data is ready

from ..strategies.base_strategy import BaseStrategy, Position, Signal


class OptopsyBacktester:
    """
    Wrapper for Optopsy backtesting library.

    Handles data preparation, strategy execution, and performance tracking.
    """

    def __init__(self, config: Dict):
        """
        Initialize backtester.

        Args:
            config: Configuration dictionary from config.yaml
        """
        self.config = config
        self.backtest_config = config.get('backtest', {})
        self.cost_config = config.get('costs', {})

        self.start_date = pd.to_datetime(self.backtest_config.get('start_date'))
        self.end_date = pd.to_datetime(self.backtest_config.get('end_date'))
        self.initial_capital = self.backtest_config.get('initial_capital', 10000)

        self.account_value = self.initial_capital
        self.equity_curve = []
        self.all_trades = []

    def prepare_optopsy_data(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """
        Convert raw options data to Optopsy format.

        Optopsy expects specific column names:
        - underlying_symbol
        - underlying_price
        - option_type (call/put)
        - expiration
        - quote_date
        - strike
        - bid
        - ask
        - delta
        - gamma (optional)
        - theta (optional)
        - vega (optional)

        Args:
            raw_data: Raw options data from data fetchers

        Returns:
            DataFrame formatted for Optopsy
        """
        # This will depend on the source data format
        # Example transformation:
        optopsy_data = raw_data.copy()

        # Ensure required columns exist and are properly named
        required_columns = [
            'underlying_symbol', 'underlying_price', 'option_type',
            'expiration', 'quote_date', 'strike', 'bid', 'ask', 'delta'
        ]

        for col in required_columns:
            if col not in optopsy_data.columns:
                raise ValueError(f"Missing required column: {col}")

        # Convert dates to datetime
        optopsy_data['expiration'] = pd.to_datetime(optopsy_data['expiration'])
        optopsy_data['quote_date'] = pd.to_datetime(optopsy_data['quote_date'])

        # Calculate DTE if not present
        if 'dte' not in optopsy_data.columns:
            optopsy_data['dte'] = (
                optopsy_data['expiration'] - optopsy_data['quote_date']
            ).dt.days

        # Ensure option_type is lowercase
        optopsy_data['option_type'] = optopsy_data['option_type'].str.lower()

        return optopsy_data

    def run_backtest(
        self,
        strategy: BaseStrategy,
        options_data: pd.DataFrame,
        underlying_data: pd.DataFrame
    ) -> Dict:
        """
        Run backtest for a given strategy.

        Args:
            strategy: Strategy instance to backtest
            options_data: Historical options data
            underlying_data: Historical underlying price data

        Returns:
            Dictionary with backtest results
        """
        # Prepare data
        optopsy_data = self.prepare_optopsy_data(options_data)

        # Reset account and strategy
        self.account_value = self.initial_capital
        self.equity_curve = []
        self.all_trades = []
        self.daily_entry_log = []  # Track daily entry attempts for reporting
        strategy.positions = []
        strategy.closed_positions = []

        # Determine actual trading date range from available data
        # Use the intersection of config dates and available data
        options_start = optopsy_data['quote_date'].min()
        options_end = optopsy_data['quote_date'].max()
        underlying_start = underlying_data.index.min()
        underlying_end = underlying_data.index.max()

        # Remove timezone info for comparison if present
        if hasattr(underlying_start, 'tz') and underlying_start.tz is not None:
            underlying_start = underlying_start.tz_localize(None)
            underlying_end = underlying_end.tz_localize(None)
            underlying_data.index = underlying_data.index.tz_localize(None)

        # Use the overlapping period
        actual_start = max(self.start_date, options_start, underlying_start)
        actual_end = min(self.end_date, options_end, underlying_end)

        if actual_start > actual_end:
            raise ValueError(
                f"No overlapping data found!\n"
                f"Config dates: {self.start_date.date()} to {self.end_date.date()}\n"
                f"Options data: {options_start.date()} to {options_end.date()}\n"
                f"Underlying data: {underlying_start.date()} to {underlying_end.date()}"
            )

        # Get trading dates
        trading_dates = pd.date_range(
            start=actual_start,
            end=actual_end,
            freq='B'  # Business days
        )

        print(f"Running backtest for {strategy.name}")
        print(f"Config period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Actual period: {actual_start.date()} to {actual_end.date()}")
        print(f"Initial capital: ${self.initial_capital:,.2f}")
        print(f"Trading days: {len(trading_dates)}")

        # Daily trade tracking for enforcing one trade per day limit
        trades_entered_today = 0

        # Main backtest loop
        for current_date in trading_dates:
            # Reset daily trade counter at start of each day
            trades_entered_today = 0
            # Get data for current date
            daily_options = optopsy_data[
                optopsy_data['quote_date'] == current_date
            ]

            if daily_options.empty:
                continue

            underlying_price = underlying_data.loc[
                underlying_data.index == current_date, 'close'
            ].values[0] if current_date in underlying_data.index else None

            if underlying_price is None:
                continue

            # Check exit signals for open positions
            open_positions = strategy.get_open_positions()
            for position in open_positions:
                exit_signal = strategy.generate_exit_signal(
                    date=current_date,
                    position=position,
                    options_data=daily_options,
                    underlying_price=underlying_price
                )

                if exit_signal:
                    # Close position
                    exit_price = position.current_price
                    strategy.close_position(
                        position=position,
                        exit_date=current_date,
                        exit_price=exit_price,
                        exit_reason=exit_signal.exit_reason
                    )

                    # Update account value
                    self.account_value += position.realized_pnl

                    # Apply transaction costs
                    commission = self._calculate_commission(position.contracts)
                    self.account_value -= commission

                    # Record trade with detailed leg information
                    entry_dte = None
                    if hasattr(position, 'entry_dte'):
                        entry_dte = position.entry_dte

                    # Build detailed trade record
                    trade_record = {
                        'entry_date': position.entry_date,
                        'exit_date': position.exit_date,
                        'strategy': strategy.name,
                        'underlying_price_entry': getattr(position, 'underlying_price_entry', None),
                        'underlying_price_exit': underlying_price,
                        'vix_entry': getattr(position, 'vix_entry', None),
                        'vix_exit': vix if 'vix' in daily_options.columns else None,
                        'entry_dte': entry_dte,
                        'entry_price': position.entry_price,
                        'exit_price': position.exit_price,
                        'contracts': position.contracts,
                        'pnl': position.realized_pnl,
                        'commission': commission,
                        'net_pnl': position.realized_pnl - commission,
                        'days_in_trade': position.days_in_trade,
                        'exit_reason': exit_signal.exit_reason
                    }

                    # Add leg details
                    for i, leg in enumerate(position.legs):
                        leg_num = i + 1
                        trade_record[f'leg{leg_num}_strike'] = leg['strike']
                        trade_record[f'leg{leg_num}_type'] = leg['option_type']
                        trade_record[f'leg{leg_num}_position'] = 1 if leg['position'] == 'long' else -1
                        trade_record[f'leg{leg_num}_delta'] = getattr(leg, 'delta', None) if hasattr(leg, 'delta') else leg.get('delta')
                        trade_record[f'leg{leg_num}_price'] = getattr(leg, 'price', None) if hasattr(leg, 'price') else leg.get('price')
                        trade_record[f'leg{leg_num}_expiration'] = getattr(leg, 'expiration', None) if hasattr(leg, 'expiration') else leg.get('expiration')

                    # Add calendar-specific fields
                    if hasattr(position, 'near_expiration'):
                        trade_record['near_expiration'] = position.near_expiration
                    if hasattr(position, 'far_expiration'):
                        trade_record['far_expiration'] = position.far_expiration

                    self.all_trades.append(trade_record)

            # Check for new entry signals
            # BACKTEST RULE: Maximum one trade per day per strategy
            # GOAL: Try to enter at least one trade per day if position sizing allows
            max_positions = self.config.get('position_sizing', {}).get('max_positions', 5)
            current_positions = len(strategy.get_open_positions())

            # Only attempt entry if:
            # 1. Haven't entered a trade today (trades_entered_today < 1)
            # 2. Have room for more positions (current_positions < max_positions)
            if trades_entered_today < 1 and current_positions < max_positions:
                # Get VIX for the day (if available)
                vix = daily_options['vix'].iloc[0] if 'vix' in daily_options.columns and not daily_options.empty else None

                entry_signal = strategy.generate_entry_signal(
                    date=current_date,
                    options_data=daily_options,
                    underlying_price=underlying_price,
                    vix=vix
                )

                if entry_signal:
                    # Calculate position size
                    contracts = strategy.calculate_position_size(
                        signal=entry_signal,
                        account_value=self.account_value,
                        risk_per_trade_percent=self.config.get('position_sizing', {}).get('risk_per_trade_percent', 2.0),
                        full_config=self.config  # Pass full config for Kelly parameters
                    )

                    # Get entry price
                    entry_price = self._get_entry_price(daily_options, entry_signal)

                    if entry_price and contracts > 0:
                        # Get leg details from options data
                        option_type = 'put' if 'put' in strategy.spread_type else 'call'

                        # Get short leg details
                        short_leg_data = self._get_leg_details(
                            daily_options, entry_signal.short_strike, option_type, entry_signal
                        )

                        # Get long leg details
                        long_leg_data = self._get_leg_details(
                            daily_options, entry_signal.long_strike, option_type, entry_signal, is_long=True
                        )

                        # Create position
                        position = Position(
                            strategy_name=strategy.name,
                            entry_date=current_date,
                            entry_price=entry_price,
                            contracts=contracts,
                            legs=[
                                {
                                    'strike': entry_signal.short_strike,
                                    'option_type': option_type,
                                    'position': 'short',
                                    'delta': short_leg_data.get('delta'),
                                    'price': short_leg_data.get('price'),
                                    'expiration': short_leg_data.get('expiration')
                                },
                                {
                                    'strike': entry_signal.long_strike,
                                    'option_type': option_type,
                                    'position': 'long',
                                    'delta': long_leg_data.get('delta'),
                                    'price': long_leg_data.get('price'),
                                    'expiration': long_leg_data.get('expiration')
                                }
                            ],
                            notes=entry_signal.notes
                        )

                        # Store entry market conditions
                        position.underlying_price_entry = underlying_price
                        position.vix_entry = vix

                        # Store entry DTE for Kelly analysis
                        if hasattr(entry_signal, 'dte') and entry_signal.dte is not None:
                            position.entry_dte = entry_signal.dte

                        # Store expiration dates for calendar spreads
                        if hasattr(entry_signal, 'near_expiration'):
                            position.near_expiration = entry_signal.near_expiration
                        if hasattr(entry_signal, 'far_expiration'):
                            position.far_expiration = entry_signal.far_expiration

                        strategy.positions.append(position)

                        # Increment daily trade counter (enforce max one trade per day)
                        trades_entered_today += 1

                        # Apply entry commission
                        commission = self._calculate_commission(contracts)
                        self.account_value -= commission

            # Track daily entry attempts for reporting
            self.daily_entry_log.append({
                'date': current_date,
                'trades_entered': trades_entered_today,
                'attempted_entry': (trades_entered_today < 1 and current_positions < max_positions),
                'entry_blocked_reason': (
                    'max_positions_reached' if current_positions >= max_positions
                    else 'already_entered_today' if trades_entered_today >= 1
                    else 'no_entry_signal' if trades_entered_today == 0
                    else 'entered'
                )
            })

            # Record equity curve
            total_unrealized = sum(
                p.unrealized_pnl for p in strategy.get_open_positions()
            )
            self.equity_curve.append({
                'date': current_date,
                'account_value': self.account_value,
                'unrealized_pnl': total_unrealized,
                'total_value': self.account_value + total_unrealized,
                'open_positions': len(strategy.get_open_positions()),
                'trades_entered_today': trades_entered_today
            })

        # Close any remaining positions at end of backtest
        for position in strategy.get_open_positions():
            final_price = position.current_price if position.current_price else position.entry_price
            strategy.close_position(
                position=position,
                exit_date=self.end_date,
                exit_price=final_price,
                exit_reason="End of backtest period"
            )
            self.account_value += position.realized_pnl

        # Compile results
        results = self._compile_results(strategy)

        return results

    def _get_entry_price(
        self,
        options_data: pd.DataFrame,
        signal: Signal
    ) -> Optional[float]:
        """Get entry price for a spread."""
        option_type = 'put' if 'put' in signal.strategy_name.lower() else 'call'

        # Check if this is a calendar spread (same strike, different DTEs)
        is_calendar = (signal.short_strike == signal.long_strike) and ('calendar' in signal.strategy_name.lower())

        if is_calendar:
            # For calendar spreads, use stored expiration dates from signal
            if hasattr(signal, 'near_expiration') and hasattr(signal, 'far_expiration'):
                near_term = options_data[
                    (options_data['strike'] == signal.short_strike) &
                    (options_data['option_type'] == option_type) &
                    (options_data['expiration'] == signal.near_expiration)
                ]

                far_term = options_data[
                    (options_data['strike'] == signal.short_strike) &
                    (options_data['option_type'] == option_type) &
                    (options_data['expiration'] == signal.far_expiration)
                ]

                if near_term.empty or far_term.empty:
                    return None

                # Use bid for sell (near-term), ask for buy (far-term)
                short_price = near_term.iloc[0]['bid']
                long_price = far_term.iloc[0]['ask']

                # Calendar spread is a debit: we pay (far - near)
                net_debit = long_price - short_price

                return net_debit if net_debit > 0 else None
            else:
                # Fallback: use shortest and longest DTE
                short_option = options_data[
                    (options_data['strike'] == signal.short_strike) &
                    (options_data['option_type'] == option_type)
                ].sort_values('dte')

                if short_option.empty or len(short_option) < 2:
                    return None

                near_term = short_option.iloc[0]
                far_term = short_option.iloc[-1]

                short_price = near_term['bid']
                long_price = far_term['ask']

                net_debit = long_price - short_price

                return net_debit if net_debit > 0 else None
        else:
            # Vertical spread - different strikes
            short_option = options_data[
                (options_data['strike'] == signal.short_strike) &
                (options_data['option_type'] == option_type)
            ]
            long_option = options_data[
                (options_data['strike'] == signal.long_strike) &
                (options_data['option_type'] == option_type)
            ]

            if short_option.empty or long_option.empty:
                return None

            # Use mid price for entry
            short_price = (short_option.iloc[0]['bid'] + short_option.iloc[0]['ask']) / 2
            long_price = (long_option.iloc[0]['bid'] + long_option.iloc[0]['ask']) / 2

            return short_price - long_price

    def _get_leg_details(
        self,
        options_data: pd.DataFrame,
        strike: float,
        option_type: str,
        signal: Signal,
        is_long: bool = False
    ) -> Dict:
        """
        Get detailed leg information (delta, price, expiration) for trade export.

        Args:
            options_data: Options data for the day
            strike: Strike price
            option_type: 'call' or 'put'
            signal: Entry signal (contains expiration info for calendar spreads)
            is_long: True if this is the long leg, False for short leg

        Returns:
            Dictionary with delta, price, and expiration
        """
        # Check if calendar spread
        is_calendar = (signal.short_strike == signal.long_strike) and hasattr(signal, 'near_expiration')

        if is_calendar:
            # Use stored expirations for calendar spreads
            if is_long and hasattr(signal, 'far_expiration'):
                expiration = signal.far_expiration
            elif not is_long and hasattr(signal, 'near_expiration'):
                expiration = signal.near_expiration
            else:
                expiration = None

            # Filter by expiration if available
            if expiration is not None:
                leg_options = options_data[
                    (options_data['strike'] == strike) &
                    (options_data['option_type'] == option_type) &
                    (options_data['expiration'] == expiration)
                ]
            else:
                leg_options = options_data[
                    (options_data['strike'] == strike) &
                    (options_data['option_type'] == option_type)
                ].sort_values('dte')
                leg_options = leg_options.iloc[[-1] if is_long else [0]]
        else:
            # Vertical spread - just filter by strike
            leg_options = options_data[
                (options_data['strike'] == strike) &
                (options_data['option_type'] == option_type)
            ]

        if leg_options.empty:
            return {'delta': None, 'price': None, 'expiration': None}

        leg = leg_options.iloc[0]

        # Use ask for long, bid for short
        if is_long:
            price = leg['ask']
        else:
            price = leg['bid']

        return {
            'delta': leg.get('delta'),
            'price': price,
            'expiration': leg.get('expiration')
        }

    def _calculate_commission(self, contracts: int) -> float:
        """Calculate commission for a trade."""
        per_contract = self.cost_config.get('commission_per_contract', 0.65)
        # 2 legs * 2 sides (entry + exit) * contracts
        return per_contract * 2 * 2 * contracts

    def _compile_results(self, strategy: BaseStrategy) -> Dict:
        """Compile backtest results."""
        if not self.equity_curve:
            raise ValueError(
                "No equity curve data recorded during backtest!\n"
                "This usually means no valid trading days were found.\n"
                "Check that your options_data and underlying_data have overlapping dates."
            )

        equity_df = pd.DataFrame(self.equity_curve)
        trades_df = pd.DataFrame(self.all_trades)

        # Calculate returns
        equity_df['returns'] = equity_df['total_value'].pct_change()

        # Performance metrics
        final_value = equity_df['total_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100

        # Calculate max drawdown
        equity_df['cummax'] = equity_df['total_value'].cummax()
        equity_df['drawdown'] = (equity_df['total_value'] - equity_df['cummax']) / equity_df['cummax']
        max_drawdown = equity_df['drawdown'].min() * 100

        # Sharpe ratio (annualized)
        risk_free_rate = 0.02  # 2% annual
        daily_rf = risk_free_rate / 252
        excess_returns = equity_df['returns'] - daily_rf
        if len(excess_returns) > 1 and excess_returns.std() > 0:
            sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std()
        else:
            sharpe_ratio = 0

        # Win rate and profit metrics
        if len(trades_df) > 0:
            win_rate = (trades_df['net_pnl'] > 0).sum() / len(trades_df) * 100
            avg_win = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].mean() if (trades_df['net_pnl'] > 0).any() else 0
            avg_loss = trades_df[trades_df['net_pnl'] <= 0]['net_pnl'].mean() if (trades_df['net_pnl'] <= 0).any() else 0
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        else:
            win_rate = avg_win = avg_loss = profit_factor = 0

        # Daily entry statistics
        daily_log_df = pd.DataFrame(self.daily_entry_log)
        total_trading_days = len(daily_log_df)
        days_with_entry = (daily_log_df['trades_entered'] > 0).sum()
        days_no_entry = total_trading_days - days_with_entry
        days_blocked_by_max_positions = (daily_log_df['entry_blocked_reason'] == 'max_positions_reached').sum()
        days_no_signal = (daily_log_df['entry_blocked_reason'] == 'no_entry_signal').sum()
        daily_entry_rate = (days_with_entry / total_trading_days * 100) if total_trading_days > 0 else 0

        results = {
            'strategy_name': strategy.name,
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return_pct': total_return,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(trades_df),
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'equity_curve': equity_df,
            'trades': trades_df,
            # Daily entry statistics
            'total_trading_days': total_trading_days,
            'days_with_entry': days_with_entry,
            'days_no_entry': days_no_entry,
            'days_blocked_by_max_positions': days_blocked_by_max_positions,
            'days_no_signal': days_no_signal,
            'daily_entry_rate_pct': daily_entry_rate,
            'daily_entry_log': daily_log_df,
        }

        return results

    def print_results(self, results: Dict) -> None:
        """Print backtest results in a formatted manner."""
        print("\n" + "="*60)
        print(f"BACKTEST RESULTS: {results['strategy_name']}")
        print("="*60)
        print(f"Initial Capital:    ${results['initial_capital']:,.2f}")
        print(f"Final Value:        ${results['final_value']:,.2f}")
        print(f"Total Return:       {results['total_return_pct']:.2f}%")
        print(f"Max Drawdown:       {results['max_drawdown_pct']:.2f}%")
        print(f"Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
        print(f"\nTotal Trades:       {results['total_trades']}")
        print(f"Win Rate:           {results['win_rate_pct']:.2f}%")
        print(f"Avg Win:            ${results['avg_win']:.2f}")
        print(f"Avg Loss:           ${results['avg_loss']:.2f}")
        print(f"Profit Factor:      {results['profit_factor']:.2f}")
        print(f"\n--- Daily Entry Statistics ---")
        print(f"Total Trading Days:       {results['total_trading_days']}")
        print(f"Days with Entry:          {results['days_with_entry']} ({results['daily_entry_rate_pct']:.1f}%)")
        print(f"Days No Entry:            {results['days_no_entry']}")
        print(f"  - No entry signal:      {results['days_no_signal']}")
        print(f"  - Max positions reached: {results['days_blocked_by_max_positions']}")
        print("="*60 + "\n")

    def export_trades(
        self,
        results: Dict,
        output_dir: str = 'backtest_results',
        format: str = 'csv'
    ) -> str:
        """
        Export detailed trade information to CSV or XLSX file.

        Args:
            results: Backtest results dictionary
            output_dir: Directory to save export files (default: 'backtest_results')
            format: Export format - 'csv' or 'xlsx' (default: 'csv')

        Returns:
            Path to the exported file
        """
        import os
        from datetime import datetime as dt

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Sanitize strategy name for filename
        strategy_name = results['strategy_name'].replace(' ', '_').replace('/', '_')

        # Create filename (static, will overwrite on each run)
        if format == 'xlsx':
            filename = f"{strategy_name}.xlsx"
        else:
            filename = f"{strategy_name}.csv"

        filepath = os.path.join(output_dir, filename)

        # Get trades DataFrame
        trades_df = results['trades'].copy()

        if trades_df.empty:
            print(f"⚠️  No trades to export for {results['strategy_name']}")
            return None

        # Reorder columns for better readability
        column_order = [
            'entry_date',
            'exit_date',
            'strategy',
            'underlying_price_entry',
            'underlying_price_exit',
            'vix_entry',
            'vix_exit',
            'entry_dte',
            'entry_price',
            'exit_price',
            'contracts',
            # Leg 1 (short)
            'leg1_strike',
            'leg1_type',
            'leg1_position',
            'leg1_delta',
            'leg1_price',
            'leg1_expiration',
            # Leg 2 (long)
            'leg2_strike',
            'leg2_type',
            'leg2_position',
            'leg2_delta',
            'leg2_price',
            'leg2_expiration',
            # Calendar specific
            'near_expiration',
            'far_expiration',
            # P&L
            'pnl',
            'commission',
            'net_pnl',
            'days_in_trade',
            'exit_reason'
        ]

        # Only include columns that exist in the DataFrame
        ordered_columns = [col for col in column_order if col in trades_df.columns]
        trades_export = trades_df[ordered_columns]

        # Export to file
        if format == 'xlsx':
            try:
                import openpyxl
                trades_export.to_excel(filepath, index=False, engine='openpyxl')
                print(f"✅ Exported {len(trades_export)} trades to: {filepath}")
            except ImportError:
                print("⚠️  openpyxl not installed. Install with: pip install openpyxl")
                print("   Falling back to CSV export...")
                filepath = filepath.replace('.xlsx', '.csv')
                trades_export.to_csv(filepath, index=False)
                print(f"✅ Exported {len(trades_export)} trades to: {filepath}")
        else:
            trades_export.to_csv(filepath, index=False)
            print(f"✅ Exported {len(trades_export)} trades to: {filepath}")

        return filepath
