"""
Performance metrics and analysis module.

Calculates various performance metrics for backtesting results including:
- Returns and P&L
- Risk metrics (Sharpe, Sortino, Calmar ratios)
- Drawdown analysis
- Win/loss statistics
- Greeks exposure
"""

from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


class PerformanceAnalyzer:
    """Analyze backtesting performance and generate metrics."""

    def __init__(self, equity_curve: pd.DataFrame, trades: pd.DataFrame):
        """
        Initialize performance analyzer.

        Args:
            equity_curve: DataFrame with daily equity values
            trades: DataFrame with individual trade results
        """
        self.equity_curve = equity_curve
        self.trades = trades

    def calculate_all_metrics(self, initial_capital: float) -> Dict:
        """
        Calculate comprehensive performance metrics.

        Args:
            initial_capital: Starting capital

        Returns:
            Dictionary with all performance metrics
        """
        metrics = {}

        # Basic P&L metrics
        metrics.update(self._calculate_pnl_metrics(initial_capital))

        # Risk metrics
        metrics.update(self._calculate_risk_metrics())

        # Trade statistics
        metrics.update(self._calculate_trade_stats())

        # Time-based metrics
        metrics.update(self._calculate_time_metrics())

        return metrics

    def _calculate_pnl_metrics(self, initial_capital: float) -> Dict:
        """Calculate profit/loss metrics."""
        final_value = self.equity_curve['total_value'].iloc[-1]
        total_pnl = final_value - initial_capital
        total_return_pct = (total_pnl / initial_capital) * 100

        # Annualized return
        days = len(self.equity_curve)
        years = days / 252  # Trading days per year
        annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        return {
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'annualized_return_pct': annualized_return
        }

    def _calculate_risk_metrics(self) -> Dict:
        """Calculate risk-adjusted metrics."""
        # Daily returns
        returns = self.equity_curve['total_value'].pct_change().dropna()

        # Sharpe ratio (annualized)
        risk_free_rate = 0.02  # 2% annual
        daily_rf = risk_free_rate / 252
        excess_returns = returns - daily_rf

        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0

        # Sortino ratio (only penalize downside volatility)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        sortino_ratio = np.sqrt(252) * excess_returns.mean() / downside_std if downside_std > 0 else 0

        # Max drawdown
        cummax = self.equity_curve['total_value'].cummax()
        drawdown = (self.equity_curve['total_value'] - cummax) / cummax
        max_drawdown = drawdown.min() * 100

        # Calmar ratio (return / max drawdown)
        annualized_return = self._calculate_pnl_metrics(
            self.equity_curve['total_value'].iloc[0]
        )['annualized_return_pct']
        calmar_ratio = abs(annualized_return / max_drawdown) if max_drawdown != 0 else 0

        # Volatility (annualized)
        volatility = returns.std() * np.sqrt(252) * 100

        return {
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown_pct': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'volatility_pct': volatility
        }

    def _calculate_trade_stats(self) -> Dict:
        """Calculate trade-level statistics."""
        if len(self.trades) == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate_pct': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'largest_win': 0,
                'largest_loss': 0,
                'profit_factor': 0
            }

        winning_trades = self.trades[self.trades['net_pnl'] > 0]
        losing_trades = self.trades[self.trades['net_pnl'] <= 0]

        total_trades = len(self.trades)
        num_wins = len(winning_trades)
        num_losses = len(losing_trades)

        win_rate = (num_wins / total_trades) * 100 if total_trades > 0 else 0

        avg_win = winning_trades['net_pnl'].mean() if num_wins > 0 else 0
        avg_loss = losing_trades['net_pnl'].mean() if num_losses > 0 else 0

        largest_win = winning_trades['net_pnl'].max() if num_wins > 0 else 0
        largest_loss = losing_trades['net_pnl'].min() if num_losses > 0 else 0

        total_wins = winning_trades['net_pnl'].sum() if num_wins > 0 else 0
        total_losses = abs(losing_trades['net_pnl'].sum()) if num_losses > 0 else 0

        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        return {
            'total_trades': total_trades,
            'winning_trades': num_wins,
            'losing_trades': num_losses,
            'win_rate_pct': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'profit_factor': profit_factor,
            'avg_days_in_trade': self.trades['days_in_trade'].mean() if total_trades > 0 else 0
        }

    def _calculate_time_metrics(self) -> Dict:
        """Calculate time-based performance metrics."""
        # Monthly returns
        equity_monthly = self.equity_curve.set_index('date').resample('M')['total_value'].last()
        monthly_returns = equity_monthly.pct_change().dropna() * 100

        positive_months = (monthly_returns > 0).sum()
        total_months = len(monthly_returns)

        return {
            'positive_months': positive_months,
            'total_months': total_months,
            'positive_months_pct': (positive_months / total_months) * 100 if total_months > 0 else 0,
            'best_month_pct': monthly_returns.max() if len(monthly_returns) > 0 else 0,
            'worst_month_pct': monthly_returns.min() if len(monthly_returns) > 0 else 0,
            'avg_monthly_return_pct': monthly_returns.mean() if len(monthly_returns) > 0 else 0
        }

    def plot_equity_curve(self, figsize=(12, 6)) -> None:
        """Plot equity curve over time."""
        fig, ax = plt.subplots(figsize=figsize)

        ax.plot(
            self.equity_curve['date'],
            self.equity_curve['total_value'],
            linewidth=2,
            label='Total Value'
        )
        ax.plot(
            self.equity_curve['date'],
            self.equity_curve['account_value'],
            linewidth=1.5,
            alpha=0.7,
            label='Realized Value'
        )

        ax.set_xlabel('Date')
        ax.set_ylabel('Account Value ($)')
        ax.set_title('Equity Curve')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def plot_drawdown(self, figsize=(12, 6)) -> None:
        """Plot drawdown over time."""
        cummax = self.equity_curve['total_value'].cummax()
        drawdown = (self.equity_curve['total_value'] - cummax) / cummax * 100

        fig, ax = plt.subplots(figsize=figsize)

        ax.fill_between(
            self.equity_curve['date'],
            drawdown,
            0,
            alpha=0.3,
            color='red'
        )
        ax.plot(
            self.equity_curve['date'],
            drawdown,
            linewidth=1.5,
            color='red'
        )

        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.set_title('Drawdown Over Time')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        plt.tight_layout()
        plt.show()

    def plot_monthly_returns(self, figsize=(12, 6)) -> None:
        """Plot monthly returns as a bar chart."""
        equity_monthly = self.equity_curve.set_index('date').resample('M')['total_value'].last()
        monthly_returns = equity_monthly.pct_change().dropna() * 100

        fig, ax = plt.subplots(figsize=figsize)

        colors = ['green' if x > 0 else 'red' for x in monthly_returns]

        monthly_returns.plot(kind='bar', ax=ax, color=colors, alpha=0.7)

        ax.set_xlabel('Month')
        ax.set_ylabel('Return (%)')
        ax.set_title('Monthly Returns')
        ax.grid(True, alpha=0.3, axis='y')
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)

        plt.tight_layout()
        plt.show()

    def plot_trade_distribution(self, figsize=(12, 5)) -> None:
        """Plot distribution of trade P&L."""
        if len(self.trades) == 0:
            print("No trades to plot")
            return

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Histogram
        ax1.hist(
            self.trades['net_pnl'],
            bins=30,
            edgecolor='black',
            alpha=0.7
        )
        ax1.axvline(x=0, color='red', linestyle='--', linewidth=2)
        ax1.set_xlabel('P&L ($)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Trade P&L Distribution')
        ax1.grid(True, alpha=0.3)

        # Cumulative P&L
        cumulative_pnl = self.trades['net_pnl'].cumsum()
        ax2.plot(cumulative_pnl, linewidth=2)
        ax2.set_xlabel('Trade Number')
        ax2.set_ylabel('Cumulative P&L ($)')
        ax2.set_title('Cumulative P&L Over Trades')
        ax2.grid(True, alpha=0.3)
        ax2.axhline(y=0, color='red', linestyle='--', linewidth=1)

        plt.tight_layout()
        plt.show()

    def plot_open_positions(self, figsize=(12, 6)) -> None:
        """Plot number of open positions over time."""
        fig, ax = plt.subplots(figsize=figsize)

        ax.plot(
            self.equity_curve['date'],
            self.equity_curve['open_positions'],
            linewidth=1.5
        )
        ax.fill_between(
            self.equity_curve['date'],
            self.equity_curve['open_positions'],
            alpha=0.3
        )

        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Positions')
        ax.set_title('Open Positions Over Time')
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def generate_report(self, metrics: Dict) -> str:
        """
        Generate formatted text report.

        Args:
            metrics: Dictionary of calculated metrics

        Returns:
            Formatted string report
        """
        report = []
        report.append("\n" + "="*70)
        report.append("PERFORMANCE REPORT")
        report.append("="*70)

        report.append("\nPROFIT & LOSS")
        report.append("-" * 70)
        report.append(f"Initial Capital:        ${metrics['initial_capital']:,.2f}")
        report.append(f"Final Value:            ${metrics['final_value']:,.2f}")
        report.append(f"Total P&L:              ${metrics['total_pnl']:,.2f}")
        report.append(f"Total Return:           {metrics['total_return_pct']:.2f}%")
        report.append(f"Annualized Return:      {metrics['annualized_return_pct']:.2f}%")

        report.append("\nRISK METRICS")
        report.append("-" * 70)
        report.append(f"Sharpe Ratio:           {metrics['sharpe_ratio']:.2f}")
        report.append(f"Sortino Ratio:          {metrics['sortino_ratio']:.2f}")
        report.append(f"Calmar Ratio:           {metrics['calmar_ratio']:.2f}")
        report.append(f"Max Drawdown:           {metrics['max_drawdown_pct']:.2f}%")
        report.append(f"Volatility (Annual):    {metrics['volatility_pct']:.2f}%")

        report.append("\nTRADE STATISTICS")
        report.append("-" * 70)
        report.append(f"Total Trades:           {metrics['total_trades']}")
        report.append(f"Winning Trades:         {metrics['winning_trades']}")
        report.append(f"Losing Trades:          {metrics['losing_trades']}")
        report.append(f"Win Rate:               {metrics['win_rate_pct']:.2f}%")
        report.append(f"Profit Factor:          {metrics['profit_factor']:.2f}")
        report.append(f"Average Win:            ${metrics['avg_win']:.2f}")
        report.append(f"Average Loss:           ${metrics['avg_loss']:.2f}")
        report.append(f"Largest Win:            ${metrics['largest_win']:.2f}")
        report.append(f"Largest Loss:           ${metrics['largest_loss']:.2f}")
        report.append(f"Avg Days in Trade:      {metrics['avg_days_in_trade']:.1f}")

        report.append("\nMONTHLY PERFORMANCE")
        report.append("-" * 70)
        report.append(f"Total Months:           {metrics['total_months']}")
        report.append(f"Positive Months:        {metrics['positive_months']} ({metrics['positive_months_pct']:.1f}%)")
        report.append(f"Best Month:             {metrics['best_month_pct']:.2f}%")
        report.append(f"Worst Month:            {metrics['worst_month_pct']:.2f}%")
        report.append(f"Avg Monthly Return:     {metrics['avg_monthly_return_pct']:.2f}%")

        report.append("\n" + "="*70 + "\n")

        return "\n".join(report)
