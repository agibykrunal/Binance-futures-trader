#!/usr/bin/env python3
"""
cli.py — Command-line entry point for the Binance Futures Testnet Trading Bot.

Usage examples
--------------
# Market BUY
python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

# Limit SELL
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT \
    --quantity 0.01 --price 95000

# Stop-Market SELL (bonus order type)
python cli.py place-order --symbol BTCUSDT --side SELL --type STOP_MARKET \
    --quantity 0.01 --stop-price 88000

# Dry-run (validate only, no API call)
python cli.py place-order --symbol BTCUSDT --side BUY --type LIMIT \
    --quantity 0.01 --price 90000 --dry-run

# Ping the API
python cli.py ping

# Account info
python cli.py account

# List open orders
python cli.py open-orders --symbol BTCUSDT

# Verbose debug output
python cli.py --log-level DEBUG place-order --symbol BTCUSDT --side BUY \
    --type MARKET --quantity 0.01
"""

from __future__ import annotations

import argparse
import os
import sys

from bot import BinanceAPIError, BinanceClient, BinanceNetworkError, place_order, setup_logging
from bot.logging_config import get_logger

logger = get_logger("cli")


class _C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"


def _die(message: str, code: int = 1) -> None:
    print(f"\n  {_C.RED}{_C.BOLD}✗ Error:{_C.RESET} {message}\n", file=sys.stderr)
    logger.error("Fatal: %s", message)
    sys.exit(code)


def _get_client(args: argparse.Namespace) -> BinanceClient:
    api_key    = getattr(args, "api_key", None)    or os.environ.get("BINANCE_API_KEY", "")
    api_secret = getattr(args, "api_secret", None) or os.environ.get("BINANCE_API_SECRET", "")
    if not api_key:
        _die("API key not provided. Set BINANCE_API_KEY env var or pass --api-key.")
    if not api_secret:
        _die("API secret not provided. Set BINANCE_API_SECRET env var or pass --api-secret.")
    return BinanceClient(api_key=api_key, api_secret=api_secret)


def cmd_place_order(args: argparse.Namespace) -> None:
    client = _get_client(args)
    result = place_order(
        client=client,
        symbol=args.symbol,
        side=args.side.upper(),
        order_type=args.type.upper(),
        quantity=args.quantity,
        price=args.price,
        stop_price=args.stop_price,
        time_in_force=args.tif.upper(),
        reduce_only=args.reduce_only,
        dry_run=args.dry_run,
    )
    if result is None and not args.dry_run:
        sys.exit(1)


def cmd_ping(args: argparse.Namespace) -> None:
    client = _get_client(args)
    if client.ping():
        print(f"\n  {_C.GREEN}{_C.BOLD}✓ Ping successful — testnet is reachable.{_C.RESET}\n")
    else:
        _die("Ping failed. Check your connection or testnet status.")


def cmd_account(args: argparse.Namespace) -> None:
    client = _get_client(args)
    try:
        info = client.get_account_info()
    except (BinanceAPIError, BinanceNetworkError) as exc:
        _die(str(exc))

    line = "─" * 60
    print(f"\n{_C.CYAN}{_C.BOLD}{line}{_C.RESET}")
    print(f"  {_C.BOLD}ACCOUNT SUMMARY{_C.RESET}")
    print(f"{_C.CYAN}{line}{_C.RESET}")
    print(f"  {'Wallet Balance':<26} {info.get('totalWalletBalance', 'N/A')} USDT")
    print(f"  {'Margin Balance':<26} {info.get('totalMarginBalance', 'N/A')} USDT")
    print(f"  {'Unrealized P&L':<26} {info.get('totalUnrealizedProfit', 'N/A')} USDT")
    print(f"  {'Can Trade':<26} {info.get('canTrade', False)}")
    print(f"{_C.CYAN}{line}{_C.RESET}")
    assets = [a for a in info.get("assets", []) if float(a.get("walletBalance", 0)) != 0.0]
    if assets:
        print(f"\n  {_C.BOLD}Non-zero asset balances:{_C.RESET}")
        for a in assets:
            print(f"    {a['asset']:<10} wallet={a['walletBalance']}  unrealized={a.get('unrealizedProfit','0')}")
    print()


def cmd_open_orders(args: argparse.Namespace) -> None:
    client = _get_client(args)
    try:
        orders = client.get_open_orders(symbol=getattr(args, "symbol", None))
    except (BinanceAPIError, BinanceNetworkError) as exc:
        _die(str(exc))

    line = "─" * 60
    if not orders:
        print("\n  No open orders found.\n")
        return
    print(f"\n{_C.CYAN}{_C.BOLD}{line}{_C.RESET}")
    print(f"  {_C.BOLD}OPEN ORDERS ({len(orders)}){_C.RESET}")
    print(f"{_C.CYAN}{line}{_C.RESET}")
    for o in orders:
        sc = _C.GREEN if o["side"] == "BUY" else _C.RED
        print(f"  [{o['orderId']}] {sc}{o['side']}{_C.RESET} {o['type']} {o['symbol']}  qty={o['origQty']}  price={o['price']}  status={o['status']}")
    print(f"{_C.CYAN}{line}{_C.RESET}\n")


def _add_credentials(p: argparse.ArgumentParser) -> None:
    p.add_argument("--api-key",    dest="api_key",    metavar="KEY",    default=None,
                   help="Binance API key (overrides BINANCE_API_KEY env var).")
    p.add_argument("--api-secret", dest="api_secret", metavar="SECRET", default=None,
                   help="Binance API secret (overrides BINANCE_API_SECRET env var).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    _add_credentials(parser)
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log verbosity (default: INFO).",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # place-order
    po = sub.add_parser("place-order", help="Place a market, limit, or stop-market order.")
    _add_credentials(po)
    po.add_argument("--symbol",    "-s", required=True, metavar="SYMBOL", help="Trading pair, e.g. BTCUSDT.")
    po.add_argument("--side",            required=True, metavar="SIDE",
                    choices=["BUY","SELL","buy","sell"], help="BUY or SELL.")
    po.add_argument("--type",      "-t", required=True, metavar="TYPE",
                    choices=["MARKET","LIMIT","STOP_MARKET","market","limit","stop_market"],
                    help="MARKET | LIMIT | STOP_MARKET.")
    po.add_argument("--quantity",  "-q", required=True, type=float, metavar="QTY",
                    help="Order quantity in base asset.")
    po.add_argument("--price",     "-p", type=float, default=None, metavar="PRICE",
                    help="Limit price (required for LIMIT orders).")
    po.add_argument("--stop-price",      type=float, default=None, dest="stop_price",
                    metavar="STOP_PRICE", help="Stop trigger price (STOP_MARKET orders).")
    po.add_argument("--tif",             default="GTC", choices=["GTC","IOC","FOK"],
                    metavar="TIF", help="Time-in-force (default: GTC).")
    po.add_argument("--reduce-only",     action="store_true", help="Mark as reduce-only.")
    po.add_argument("--dry-run",         action="store_true", help="Preview without submitting.")
    po.set_defaults(func=cmd_place_order)

    # ping
    pg = sub.add_parser("ping", help="Check connectivity to the testnet API.")
    _add_credentials(pg)
    pg.set_defaults(func=cmd_ping)

    # account
    ac = sub.add_parser("account", help="Display account balance summary.")
    _add_credentials(ac)
    ac.set_defaults(func=cmd_account)

    # open-orders
    oo = sub.add_parser("open-orders", help="List all open orders.")
    _add_credentials(oo)
    oo.add_argument("--symbol", "-s", default=None, metavar="SYMBOL",
                    help="Filter by symbol (optional).")
    oo.set_defaults(func=cmd_open_orders)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(log_level=args.log_level)
    logger.debug("CLI arguments: %s", args)
    logger.info("=== Trading Bot Session Start ===")
    try:
        args.func(args)
    finally:
        logger.info("=== Session End ===")


if __name__ == "__main__":
    main()
