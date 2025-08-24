"""
Trading Models and Data Structures
Contains all data classes, enums, and type definitions used in the trading system
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    REDUCE = "REDUCE"
    HOLD = "HOLD"


class OrderPriority(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PartialFillMode(Enum):
    """Configuration options for handling partial fills when insufficient cash"""
    AUTOMATIC = "AUTOMATIC"        # Always fill max affordable shares
    ASK_CONFIRMATION = "ASK"       # Ask user for each partial fill  
    REJECT = "REJECT"              # Reject orders that can't be filled completely
    SMART = "SMART"                # Auto-fill if >threshold% affordable, ask if below

    def __str__(self):
        """String representation for logging"""
        return self.value
    
    def __repr__(self):
        """Developer representation"""
        return f"PartialFillMode.{self.name}"
    
    @classmethod
    def from_string(cls, value: str):
        """Create enum from string value"""
        value = value.upper()
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"Invalid PartialFillMode: {value}")
    
    @property
    def description(self):
        """Human-readable description of the mode"""
        descriptions = {
            self.AUTOMATIC: "Automatically fills maximum affordable shares",
            self.ASK_CONFIRMATION: "Asks for confirmation before partial fills",
            self.REJECT: "Rejects any orders that cannot be filled completely", 
            self.SMART: "Auto-fills if >80% affordable, asks confirmation if <80%"
        }
        return descriptions[self]
    
    @property
    def requires_user_input(self):
        """Whether this mode may require user interaction"""
        return self in [self.ASK_CONFIRMATION, self.SMART]


@dataclass
class TradeOrder:
    """Represents a single trade order"""
    ticker: str
    action: OrderType
    shares: Optional[int] = None
    target_weight: Optional[float] = None
    target_value: Optional[float] = None
    reason: str = ""
    priority: OrderPriority = OrderPriority.MEDIUM
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    profit_target: Optional[float] = None


@dataclass
class TradeResult:
    """Represents the result of an executed trade"""
    order: TradeOrder
    executed: bool
    execution_price: Optional[float]
    executed_shares: Optional[int]
    execution_value: Optional[float]
    error_message: Optional[str]
    timestamp: datetime