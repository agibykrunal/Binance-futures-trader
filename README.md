# Binance Futures Testnet Trading Bot

A clean, production-quality Python CLI application for placing orders on the **Binance Futures Testnet (USDT-M)**. Built with a layered architecture (client / orders / validators / CLI), structured logging, and robust error handling.

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Public package surface
│   ├── client.py            # Binance REST API wrapper (signing, retries, error handling)
│   ├── orders.py            # High-level order placement + console formatting
│   ├── validators.py        # Input validation (all raises ValueError with clear messages)
│   └── logging_config.py   # Rotating file + console log handlers
├── logs/
│   └── trading_bot.log      # Auto-created on first run
├── cli.py                   # argparse CLI entry point
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Prerequisites

- Python 3.8 or newer
- A Binance Futures Testnet account

### 2. Get Testnet API credentials

1. Go to [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in (GitHub OAuth is supported)
3. Navigate to **API Key** in the top-right menu
4. Click **Generate** — copy your **API Key** and **Secret Key**

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set credentials

The bot reads credentials from environment variables (recommended) or CLI flags.

**Linux / macOS**
```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_api_secret_here"
```

**Windows (PowerShell)**
```powershell
$env:BINANCE_API_KEY="your_api_key_here"
$env:BINANCE_API_SECRET="your_api_secret_here"
```

Alternatively, pass them directly on every command:
```bash
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET place-order ...
```

---

## How to Run

### Check API connectivity

```bash
python cli.py ping
```

### Place a MARKET BUY order

```bash
python cli.py place-order \
  --symbol BTCUSDT \
  --side BUY \
  --type MARKET \
  --quantity 0.01
```

### Place a LIMIT SELL order

```bash
python cli.py place-order \
  --symbol BTCUSDT \
  --side SELL \
  --type LIMIT \
  --quantity 0.01 \
  --price 95000
```

### Place a STOP_MARKET SELL order *(bonus order type)*

```bash
python cli.py place-order \
  --symbol BTCUSDT \
  --side SELL \
  --type STOP_MARKET \
  --quantity 0.01 \
  --stop-price 88000
```

### Dry run (validate inputs, skip API call)

```bash
python cli.py place-order \
  --symbol ETHUSDT \
  --side BUY \
  --type LIMIT \
  --quantity 0.1 \
  --price 3200 \
  --dry-run
```

### View account balance

```bash
python cli.py account
```

### List open orders

```bash
python cli.py open-orders
python cli.py open-orders --symbol BTCUSDT   # filter by symbol
```

### Verbose debug logging to console

```bash
python cli.py --log-level DEBUG place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

---

## CLI Reference

```
usage: trading_bot [-h] [--api-key KEY] [--api-secret SECRET]
                   [--log-level {DEBUG,INFO,WARNING,ERROR}]
                   COMMAND ...

Commands:
  place-order    Place a market, limit, or stop-market order
  ping           Check connectivity to the testnet API
  account        Display account balance summary
  open-orders    List open orders

place-order flags:
  --symbol / -s   Trading pair, e.g. BTCUSDT         (required)
  --side          BUY or SELL                         (required)
  --type / -t     MARKET | LIMIT | STOP_MARKET        (required)
  --quantity / -q Order size in base asset            (required)
  --price / -p    Limit price (LIMIT orders only)
  --stop-price    Stop trigger price (STOP_MARKET only)
  --tif           Time-in-force: GTC | IOC | FOK      (default: GTC)
  --reduce-only   Mark as reduce-only order
  --dry-run       Validate and preview without submitting
```

---

## Logging

All logs are written to `logs/trading_bot.log` (rotating, max 5 × 5 MB).

- **DEBUG** — full HTTP request/response bodies, signed parameter dumps (signature redacted)
- **INFO** — order placement events, session boundaries, connectivity checks
- **WARNING** — validation failures, ping failures
- **ERROR** — API errors (with Binance error code + message), network failures

Console output defaults to **INFO**; change with `--log-level DEBUG`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing required field (e.g. price for LIMIT) | Clear `ValueError` with fix hint; exit 1 |
| Invalid side / order type | Descriptive error listing valid options |
| Non-numeric quantity / price | Human-readable message; exit 1 |
| Binance API error (e.g. -1121 invalid symbol) | Prints Binance error code + message; logged |
| Network timeout | `BinanceNetworkError` raised; logged; exit 1 |
| Connection refused | Same as above |
| Non-JSON response | Logged and surfaced as `BinanceAPIError` |

---

## Assumptions

1. **Testnet only** — the base URL is hardcoded to `https://testnet.binancefuture.com`. To target mainnet, change `TESTNET_BASE_URL` in `bot/client.py` (and use real credentials at your own risk).
2. **USDT-M futures** — all orders go to `/fapi/v1/order` (linear perpetuals). Coin-margined (DAPI) is not supported.
3. **Quantity precision** — the bot passes the quantity as provided. Binance will reject orders that don't match the symbol's `stepSize`; the error message from the API is surfaced clearly.
4. **No order management** — cancelling or amending orders is out of scope for this task but the `BinanceClient` is designed to be extended easily.
5. **Dependencies** — only `requests` and `urllib3` are required; no `python-binance` library is used so the signing and request logic is fully transparent.

---

## Running Tests (optional)

```bash
python -m pytest tests/ -v        # if tests/ directory is added
```

Core validation logic can be exercised inline:

```bash
python -c "
from bot.validators import validate_all
print(validate_all('BTCUSDT', 'BUY', 'LIMIT', 0.01, 95000))
"
```
