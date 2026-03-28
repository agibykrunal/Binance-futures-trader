"""
Order placement logic and response formatting.

This module sits between the CLI and the BinanceClient, providing:
- A high-level place_order() wrapper with rich console output
- Response parsing helpers
- Pretty-printing utilities
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .client import BinanceAPIError, BinanceClient, BinanceNetworkError
from .logging_config import get_logger
from .validators import validate_all

logger = get_logger("orders")


# ANSI colour helpers (degrade gracefully when not in a TTY)
class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    GREY = "\033[90m"


def _line(char: str = "─", width: int = 60) -> str:
    return char * width


def _header(title: str) -> str:
    return (
        f"\n{_C.CYAN}{_C.BOLD}{_line()}{_C.RESET}\n"
        f"  {_C.BOLD}{title}{_C.RESET}\n"
        f"{_C.CYAN}{_line()}{_C.RESET}"
    )


def _kv(key: str, value: Any, colour: str = "") -> str:
    val_str = f"{colour}{value}{_C.RESET}" if colour else str(value)
    return f"  {_C.GREY}{key:<22}{_C.RESET} {val_str}"


def print_order_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float],
    stop_price: Optional[float],
) -> None:
    """Print a formatted summary of the order about to be sent."""
    side_colour = _C.GREEN if side == "BUY" else _C.RED
    print(_header("ORDER REQUEST SUMMARY"))
    print(_kv("Symbol", symbol, _C.BOLD))
    print(_kv("Side", side, side_colour + _C.BOLD))
    print(_kv("Order Type", order_type))
    print(_kv("Quantity", quantity))
    if price is not None:
        print(_kv("Limit Price", f"{price:,.8f}"))
    if stop_price is not None:
        print(_kv("Stop Price", f"{stop_price:,.8f}"))
    print(f"{_C.CYAN}{_line()}{_C.RESET}\n")


def print_order_response(response: Dict[str, Any]) -> None:
    """Print a formatted summary of the API response."""
    status = response.get("status", "UNKNOWN")
    status_colour = _C.GREEN if status in ("FILLED", "NEW") else _C.YELLOW

    print(_header("ORDER RESPONSE"))
    print(_kv("Order ID", response.get("orderId", "N/A"), _C.BOLD))
    print(_kv("Client Order ID", response.get("clientOrderId", "N/A")))
    print(_kv("Symbol", response.get("symbol", "N/A")))
    print(_kv("Side", response.get("side", "N/A")))
    print(_kv("Type", response.get("type", "N/A")))
    print(_kv("Status", status, status_colour + _C.BOLD))
    print(_kv("Orig Quantity", response.get("origQty", "N/A")))
    print(_kv("Executed Qty", response.get("executedQty", "0")))

    avg_price = response.get("avgPrice") or response.get("price", "N/A")
    print(_kv("Avg / Limit Price", avg_price))

    print(_kv("Time in Force", response.get("timeInForce", "N/A")))
    print(_kv("Update Time (ms)", response.get("updateTime", "N/A")))

    print(f"{_C.CYAN}{_line()}{_C.RESET}")
    print(f"\n  {_C.GREEN}{_C.BOLD}✓ Order placed successfully!{_C.RESET}\n")


def print_error(message: str) -> None:
    """Print a formatted error message."""
    print(f"\n  {_C.RED}{_C.BOLD}✗ Error:{_C.RESET} {message}\n")


def place_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: float | str | None = None,
    stop_price: float | str | None = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Validate inputs, display summary, place the order, and display the result.

    Args:
        client:         Authenticated BinanceClient.
        symbol:         Trading pair.
        side:           'BUY' or 'SELL'.
        order_type:     'MARKET', 'LIMIT', or 'STOP_MARKET'.
        quantity:       Order quantity.
        price:          Limit price (LIMIT orders only).
        stop_price:     Stop trigger price (STOP_MARKET only).
        time_in_force:  Time-in-force flag for LIMIT orders.
        reduce_only:    Whether the order reduces an existing position.
        dry_run:        If True, validate and display summary but skip API call.

    Returns:
        API response dict on success, or None on failure / dry_run.
    """
    # ── Validate ──────────────────────────────────────────────────────
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
    except ValueError as exc:
        logger.warning("Input validation failed: %s", exc)
        print_error(str(exc))
        return None

    # ── Print request summary ─────────────────────────────────────────
    print_order_summary(
        symbol=params["symbol"],
        side=params["side"],
        order_type=params["order_type"],
        quantity=params["quantity"],
        price=params["price"],
        stop_price=params["stop_price"],
    )

    if dry_run:
        print(
            f"  {_C.YELLOW}[DRY RUN]{_C.RESET} "
            "Order not submitted. Remove --dry-run to place it.\n"
        )
        logger.info("Dry run — order not submitted.")
        return None

    # ── Place order ───────────────────────────────────────────────────
    try:
        response = client.place_order(
            symbol=params["symbol"],
            side=params["side"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params["price"],
            stop_price=params["stop_price"],
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
    except BinanceAPIError as exc:
        logger.error("API error placing order: code=%s msg=%s", exc.code, exc.message)
        print_error(f"Binance API error (code {exc.code}): {exc.message}")
        return None
    except BinanceNetworkError as exc:
        logger.error("Network error placing order: %s", exc)
        print_error(f"Network error: {exc}")
        return None
    except Exception as exc:
        logger.exception("Unexpected error placing order: %s", exc)
        print_error(f"Unexpected error: {exc}")
        return None

    # ── Display response ──────────────────────────────────────────────
    logger.debug("Full order response: %s", json.dumps(response, indent=2))
    print_order_response(response)
    return response
