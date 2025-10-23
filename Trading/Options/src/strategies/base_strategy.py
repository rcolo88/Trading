"""
Base strategy template for options backtesting.

This module provides an abstract base class that all strategy implementations
should inherit from. It defines the interface for entry/exit signals, position
management, and performance tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


@dataclass
class Position:
    """Represents an options position (single leg or spread)."""

    strategy_name: str
    entry_date: datetime
    entry_price: float
    contracts: int

    # Legs of the position (for spreads)
    legs: List[Dict]

    # Position tracking
    current_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None

    # Greeks and risk metrics
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0

    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    # Metadata
    notes: str = ""

    @property
    def is_open(self) -> bool:
        """Check if position is still open."""
        return self.exit_date is None

    @property
    def days_in_trade(self) -> int:
        """Calculate days in trade."""
        end_date = self.exit_date if self.exit_date else datetime.now()
        return (end_date - self.entry_date).days

    @property
    def return_pct(self) -> float:
        """Calculate percentage return on the position."""
        if self.exit_price is None:
            return 0.0
        return (self.exit_price - self.entry_price) / abs(self.entry_price) * 100


@dataclass
class Signal:
    """Represents a trading signal."""

    date: datetime
    signal_type: str  # 'entry' or 'exit'
    strategy_name: str
    underlying_price: float

    # For entry signals
    short_strike: Optional[float] = None
    long_strike: Optional[float] = None
    dte: Optional[int] = None

    # For exit signals
    position_id: Optional[str] = None
    exit_reason: Optional[str] = None

    # Additional metadata
    confidence: float = 1.0
    notes: str = ""


class BaseStrategy(ABC):
    """
    Abstract base class for all options strategies.

    All strategies must implement:
    - generate_entry_signal: Determine when to enter a position
    - generate_exit_signal: Determine when to exit a position
    - calculate_position_size: Determine how many contracts to trade
    """

    def __init__(self, name: str, config: Dict):
        """
        Initialize the strategy.

        Args:
            name: Strategy name
            config: Strategy configuration dictionary from config.yaml
        """
        self.name = name
        self.config = config
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []

    @abstractmethod
    def generate_entry_signal(
        self,
        date: datetime,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """
        Generate entry signal based on strategy rules.

        Args:
            date: Current date
            options_data: DataFrame with options chain data
            underlying_price: Current underlying price
            **kwargs: Additional market data (VIX, IV rank, etc.)

        Returns:
            Signal object if entry conditions met, None otherwise
        """
        pass

    @abstractmethod
    def generate_exit_signal(
        self,
        date: datetime,
        position: Position,
        options_data: pd.DataFrame,
        underlying_price: float,
        **kwargs
    ) -> Optional[Signal]:
        """
        Generate exit signal for an open position.

        Args:
            date: Current date
            position: Current open position
            options_data: DataFrame with options chain data
            underlying_price: Current underlying price
            **kwargs: Additional market data

        Returns:
            Signal object if exit conditions met, None otherwise
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self,
        signal: Signal,
        account_value: float,
        **kwargs
    ) -> int:
        """
        Calculate the number of contracts to trade.

        Args:
            signal: Entry signal
            account_value: Current account value
            **kwargs: Additional parameters

        Returns:
            Number of contracts to trade
        """
        pass

    def update_position_greeks(
        self,
        position: Position,
        options_data: pd.DataFrame
    ) -> None:
        """
        Update position Greeks based on current market data.

        Args:
            position: Position to update
            options_data: Current options chain data
        """
        # This would be implemented to calculate/update position Greeks
        # based on current options data
        pass

    def get_open_positions(self) -> List[Position]:
        """Get all currently open positions."""
        return [p for p in self.positions if p.is_open]

    def get_closed_positions(self) -> List[Position]:
        """Get all closed positions."""
        return self.closed_positions

    def close_position(
        self,
        position: Position,
        exit_date: datetime,
        exit_price: float,
        exit_reason: str = ""
    ) -> None:
        """
        Close an open position.

        Args:
            position: Position to close
            exit_date: Exit date
            exit_price: Exit price
            exit_reason: Reason for exit
        """
        position.exit_date = exit_date
        position.exit_price = exit_price
        position.realized_pnl = (exit_price - position.entry_price) * position.contracts * 100
        position.notes = exit_reason

        self.positions.remove(position)
        self.closed_positions.append(position)

    def get_performance_summary(self) -> Dict:
        """
        Calculate strategy performance metrics.

        Returns:
            Dictionary with performance statistics
        """
        if not self.closed_positions:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
            }

        total_trades = len(self.closed_positions)
        winning_trades = [p for p in self.closed_positions if p.realized_pnl > 0]
        losing_trades = [p for p in self.closed_positions if p.realized_pnl <= 0]

        total_pnl = sum(p.realized_pnl for p in self.closed_positions)
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        avg_win = (
            sum(p.realized_pnl for p in winning_trades) / len(winning_trades)
            if winning_trades else 0
        )
        avg_loss = (
            sum(p.realized_pnl for p in losing_trades) / len(losing_trades)
            if losing_trades else 0
        )

        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "average_win": avg_win,
            "average_loss": avg_loss,
            "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'),
            "average_days_in_trade": np.mean([p.days_in_trade for p in self.closed_positions]),
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"open_positions={len(self.get_open_positions())}, "
            f"closed_positions={len(self.closed_positions)})"
        )
