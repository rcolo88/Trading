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
# import optopsy as op  # Will be imported once data is ready

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
        strategy.positions = []
        strategy.closed_positions = []

        # Get trading dates
        trading_dates = pd.date_range(
            start=self.start_date,
            end=self.end_date,
            freq='B'  # Business days
        )

        print(f"Running backtest for {strategy.name}")
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Initial capital: ${self.initial_capital:,.2f}")
        print(f"Trading days: {len(trading_dates)}")

        # Main backtest loop
        for current_date in trading_dates:
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

                    # Record trade
                    self.all_trades.append({
                        'entry_date': position.entry_date,
                        'exit_date': position.exit_date,
                        'strategy': strategy.name,
                        'pnl': position.realized_pnl,
                        'commission': commission,
                        'net_pnl': position.realized_pnl - commission,
                        'days_in_trade': position.days_in_trade,
                        'exit_reason': exit_signal.exit_reason
                    })

            # Check for new entry signals
            max_positions = self.config.get('position_sizing', {}).get('max_positions', 5)
            current_positions = len(strategy.get_open_positions())

            if current_positions < max_positions:
                entry_signal = strategy.generate_entry_signal(
                    date=current_date,
                    options_data=daily_options,
                    underlying_price=underlying_price
                )

                if entry_signal:
                    # Calculate position size
                    contracts = strategy.calculate_position_size(
                        signal=entry_signal,
                        account_value=self.account_value,
                        risk_per_trade_percent=self.config.get('position_sizing', {}).get('risk_per_trade_percent', 2.0)
                    )

                    # Get entry price
                    entry_price = self._get_entry_price(daily_options, entry_signal)

                    if entry_price and contracts > 0:
                        # Create position
                        position = Position(
                            strategy_name=strategy.name,
                            entry_date=current_date,
                            entry_price=entry_price,
                            contracts=contracts,
                            legs=[
                                {
                                    'strike': entry_signal.short_strike,
                                    'option_type': 'put' if 'put' in strategy.spread_type else 'call',
                                    'position': 'short'
                                },
                                {
                                    'strike': entry_signal.long_strike,
                                    'option_type': 'put' if 'put' in strategy.spread_type else 'call',
                                    'position': 'long'
                                }
                            ],
                            notes=entry_signal.notes
                        )

                        strategy.positions.append(position)

                        # Apply entry commission
                        commission = self._calculate_commission(contracts)
                        self.account_value -= commission

            # Record equity curve
            total_unrealized = sum(
                p.unrealized_pnl for p in strategy.get_open_positions()
            )
            self.equity_curve.append({
                'date': current_date,
                'account_value': self.account_value,
                'unrealized_pnl': total_unrealized,
                'total_value': self.account_value + total_unrealized,
                'open_positions': len(strategy.get_open_positions())
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

    def _calculate_commission(self, contracts: int) -> float:
        """Calculate commission for a trade."""
        per_contract = self.cost_config.get('commission_per_contract', 0.65)
        # 2 legs * 2 sides (entry + exit) * contracts
        return per_contract * 2 * 2 * contracts

    def _compile_results(self, strategy: BaseStrategy) -> Dict:
        """Compile backtest results."""
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
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if len(excess_returns) > 1 else 0

        # Win rate and profit metrics
        if len(trades_df) > 0:
            win_rate = (trades_df['net_pnl'] > 0).sum() / len(trades_df) * 100
            avg_win = trades_df[trades_df['net_pnl'] > 0]['net_pnl'].mean() if (trades_df['net_pnl'] > 0).any() else 0
            avg_loss = trades_df[trades_df['net_pnl'] <= 0]['net_pnl'].mean() if (trades_df['net_pnl'] <= 0).any() else 0
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        else:
            win_rate = avg_win = avg_loss = profit_factor = 0

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
        print("="*60 + "\n")
