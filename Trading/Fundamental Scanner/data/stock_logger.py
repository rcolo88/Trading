"""
Stock-Specific Logger

Tracks warnings and errors for specific stocks in a dedicated log file.
Log location: schwab_portfolio/outputs/stock_warnings.log
Log format: [TICKER] Level: Message
Rotation: Overwritten on each run (not appended)
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

class StockLogger:
    """Dedicated logger for stock-specific warnings and errors"""
    
    def __init__(self, log_file: str = None):
        outputs_dir = Path(__file__).parent.parent / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        self.log_file = log_file or str(outputs_dir / "stock_warnings.log")
        self._setup_logger()
    
    def _setup_logger(self):
        """Setup logger that writes to file with ticker prefix support"""
        self.logger = logging.getLogger('stock_warnings')
        self.logger.setLevel(logging.WARNING)
        
        # Remove any existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # File handler with overwrite mode
        handler = logging.FileHandler(self.log_file, mode='w')
        handler.setLevel(logging.WARNING)
        
        # Format: [TICKER] LEVEL: Message
        formatter = logging.Formatter('[%(levelname)s] [%(message)s]')
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
    
    def warning(self, ticker: str, message: str):
        """Log warning for specific stock"""
        self.logger.warning(f"{ticker}] {message}")
    
    def error(self, ticker: str, message: str):
        """Log error for specific stock"""
        self.logger.error(f"{ticker}] {message}")
    
    def clear(self):
        """Clear/reset the log file"""
        with open(self.log_file, 'w') as f:
            f.write(f"# Stock Warnings Log - {datetime.now().isoformat()}\n")
            f.write("# This file is overwritten on each run\n\n")

# Global instance
_stock_logger: Optional['StockLogger'] = None

def get_stock_logger() -> 'StockLogger':
    """Get or create global stock logger instance"""
    global _stock_logger
    if _stock_logger is None:
        _stock_logger = StockLogger()
    return _stock_logger
