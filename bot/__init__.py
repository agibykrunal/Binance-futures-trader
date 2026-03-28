"""
trading_bot.bot — core package.

Exposes the main public surface:
  BinanceClient, BinanceAPIError, BinanceNetworkError,
  place_order (high-level), validators, and logging helpers.
"""

from .client import BinanceAPIError, BinanceClient, BinanceNetworkError
from .logging_config import get_logger, setup_logging
from .orders import place_order
from .validators import validate_all

__all__ = [
    "BinanceClient",
    "BinanceAPIError",
    "BinanceNetworkError",
    "place_order",
    "validate_all",
    "setup_logging",
    "get_logger",
]
