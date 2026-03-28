"""
Input validation for trading bot CLI arguments.
All validation raises ValueError with descriptive messages.
"""

from __future__ import annotations

from typing import Optional


VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}

# Reasonable guard-rails (not exchange limits — those are checked server-side)
MIN_QUANTITY = 0.0
MAX_QUANTITY = 1_000_000.0
MIN_PRICE = 0.0
MAX_PRICE = 10_000_000.0


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalise a trading symbol.

    Args:
        symbol: Raw symbol string from the user, e.g. 'btcusdt'.

    Returns:
        Upper-cased symbol string.

    Raises:
        ValueError: If the symbol is empty or contains invalid characters.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Symbol cannot be empty.")
    if not symbol.isalnum():
        raise ValueError(
            f"Symbol '{symbol}' contains invalid characters. "
            "Only alphanumeric characters are allowed (e.g. BTCUSDT)."
        )
    return symbol


def validate_side(side: str) -> str:
    """
    Validate order side.

    Args:
        side: 'BUY' or 'SELL' (case-insensitive).

    Returns:
        Upper-cased side string.

    Raises:
        ValueError: If side is not BUY or SELL.
    """
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """
    Validate order type.

    Args:
        order_type: 'MARKET', 'LIMIT', or 'STOP_MARKET' (case-insensitive).

    Returns:
        Upper-cased order type string.

    Raises:
        ValueError: If the order type is not supported.
    """
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: float | str) -> float:
    """
    Validate order quantity.

    Args:
        quantity: Numeric quantity as float or parseable string.

    Returns:
        Validated quantity as float.

    Raises:
        ValueError: If quantity is non-numeric, zero, or out of range.
    """
    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise ValueError(f"Quantity must be a number, got '{quantity}'.")

    if quantity <= MIN_QUANTITY:
        raise ValueError(f"Quantity must be greater than {MIN_QUANTITY}, got {quantity}.")
    if quantity > MAX_QUANTITY:
        raise ValueError(
            f"Quantity {quantity} exceeds maximum allowed value of {MAX_QUANTITY}."
        )
    return quantity


def validate_price(price: float | str | None, order_type: str) -> Optional[float]:
    """
    Validate order price based on order type.

    Args:
        price: Numeric price as float/string, or None.
        order_type: The order type (upper-cased).

    Returns:
        Validated price as float, or None for MARKET orders.

    Raises:
        ValueError: If price is missing for LIMIT/STOP_MARKET, or invalid.
    """
    if order_type == "MARKET":
        if price is not None:
            # Warn but don't fail — just ignore it
            pass
        return None

    # LIMIT and STOP_MARKET both require a price
    if price is None:
        raise ValueError(
            f"Price is required for {order_type} orders. "
            "Provide it with --price."
        )

    try:
        price = float(price)
    except (TypeError, ValueError):
        raise ValueError(f"Price must be a number, got '{price}'.")

    if price <= MIN_PRICE:
        raise ValueError(f"Price must be greater than {MIN_PRICE}, got {price}.")
    if price > MAX_PRICE:
        raise ValueError(
            f"Price {price} exceeds maximum allowed value of {MAX_PRICE}."
        )
    return price


def validate_stop_price(
    stop_price: float | str | None, order_type: str
) -> Optional[float]:
    """
    Validate stop price for STOP_MARKET orders.

    Args:
        stop_price: Numeric stop price or None.
        order_type: Upper-cased order type.

    Returns:
        Validated stop price as float, or None.

    Raises:
        ValueError: If stop price is required but missing or invalid.
    """
    if order_type != "STOP_MARKET":
        return None

    if stop_price is None:
        raise ValueError(
            "Stop price is required for STOP_MARKET orders. "
            "Provide it with --stop-price."
        )

    try:
        stop_price = float(stop_price)
    except (TypeError, ValueError):
        raise ValueError(f"Stop price must be a number, got '{stop_price}'.")

    if stop_price <= MIN_PRICE:
        raise ValueError(
            f"Stop price must be greater than {MIN_PRICE}, got {stop_price}."
        )
    return stop_price


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: float | str | None = None,
    stop_price: float | str | None = None,
) -> dict:
    """
    Run all validations and return a clean parameter dictionary.

    Returns:
        dict with keys: symbol, side, order_type, quantity, price, stop_price.

    Raises:
        ValueError: On the first validation failure encountered.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity = validate_quantity(quantity)
    price = validate_price(price, order_type)
    stop_price = validate_stop_price(stop_price, order_type)

    return {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "price": price,
        "stop_price": stop_price,
    }
