"""
Centralized Logging Configuration

Provides consistent logging setup across all modules with standard formatters,
handlers, and configuration options.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# Standard log format
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    log_to_console: bool = True,
    format_string: Optional[str] = None,
    detailed: bool = False
) -> logging.Logger:
    """
    Setup standardized logging configuration

    Args:
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        log_file: Optional file path for logging output
        log_to_console: Whether to also log to console (default True)
        format_string: Custom format string (uses default if None)
        detailed: Use detailed format with file/line numbers

    Returns:
        Root logger instance
    """

    # Determine format
    if format_string is None:
        format_string = DETAILED_FORMAT if detailed else DEFAULT_FORMAT

    # Create formatter
    formatter = logging.Formatter(format_string)

    # Get root logger and clear existing handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []  # Clear existing handlers to avoid duplicates

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Get a logger for a specific module

    Args:
        module_name: Name of the module (typically __name__)

    Returns:
        Logger instance for the module

    Example:
        from core.logging_config import get_module_logger
        logger = get_module_logger(__name__)
        logger.info("Application started")
    """
    return logging.getLogger(module_name)


# Initialize default logging on import (INFO level, console only)
setup_logging(level=logging.INFO, log_to_console=True)
