"""
kgkgkgkggkggggkg
Binance Futures Testnet REST API client.
Wraps raw HTTP interactions: signing, timestamp injection,
request/response logging, and structured error handling.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging_config import get_logger

logger = get_logger("client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10  # seconds
RECV_WINDOW = 5000   # milliseconds


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error response."""

    def __init__(self, code: int, message: str, status_code: int = 0):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"Binance API error {code}: {message}")


class BinanceNetworkError(Exception):
    """Raised on network-level failures (timeouts, connection errors)."""


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Handles:
    - HMAC-SHA256 request signing
    - Timestamp injection
    - Automatic retries on transient errors
    - Structured logging of every request and response
    - Unified exception hierarchy
    """

    def __init__(self, api_key: str, api_secret: str, base_url: str = TESTNET_BASE_URL):
        if not api_key or not api_secret:
            raise ValueError("API key and secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")

        self._session = self._build_session()
        logger.info("BinanceClient initialised. Base URL: %s", self._base_url)

    # Internal helpers
  

    def _build_session(self) -> requests.Session:
        """Create a requests Session with retry logic."""
        session = requests.Session()
        session.headers.update({"X-MBX-APIKEY": self._api_key})

        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append HMAC-SHA256 signature to a parameter dictionary."""
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Parse response and raise BinanceAPIError on non-2xx or API error codes."""
        logger.debug(
            "HTTP %s %s → status %d | body: %s",
            response.request.method,
            response.url,
            response.status_code,
            response.text[:500],
        )

        try:
            data = response.json()
        except ValueError:
            logger.error("Non-JSON response body: %s", response.text[:300])
            raise BinanceAPIError(
                code=-1,
                message=f"Non-JSON response (HTTP {response.status_code}): {response.text[:200]}",
                status_code=response.status_code,
            )

        # Binance error responses always contain a 'code' key (negative integer)
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            logger.error(
                "API error | code=%s | msg=%s", data.get("code"), data.get("msg")
            )
            raise BinanceAPIError(
                code=data["code"],
                message=data.get("msg", "Unknown error"),
                status_code=response.status_code,
            )

        return data

    def _post(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sign and POST to a private endpoint."""
        params["timestamp"] = self._timestamp()
        params["recvWindow"] = RECV_WINDOW
        params = self._sign(params)

        url = f"{self._base_url}{endpoint}"
        logger.info("POST %s | params: %s", endpoint, self._sanitise(params))

        try:
            response = self._session.post(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.Timeout:
            logger.error("Request timed out: POST %s", endpoint)
            raise BinanceNetworkError(f"Request timed out (POST {endpoint})")
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: POST %s | %s", endpoint, exc)
            raise BinanceNetworkError(f"Connection error: {exc}")
        except requests.exceptions.RequestException as exc:
            logger.error("Request error: POST %s | %s", endpoint, exc)
            raise BinanceNetworkError(f"Request failed: {exc}")

        return self._handle_response(response)

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """GET from a public endpoint (no signing required)."""
        url = f"{self._base_url}{endpoint}"
        logger.debug("GET %s | params: %s", endpoint, params)

        try:
            response = self._session.get(
                url, params=params or {}, timeout=DEFAULT_TIMEOUT
            )
        except requests.exceptions.Timeout:
            raise BinanceNetworkError(f"Request timed out (GET {endpoint})")
        except requests.exceptions.ConnectionError as exc:
            raise BinanceNetworkError(f"Connection error: {exc}")

        return self._handle_response(response)

    @staticmethod
    def _sanitise(params: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of params with the signature redacted for safe logging."""
        safe = dict(params)
        if "signature" in safe:
            safe["signature"] = "***"
        return safe

    
    # Public API methods
    

    def ping(self) -> bool:
        """Check connectivity to the API. Returns True on success."""
        try:
            self._get("/fapi/v1/ping")
            logger.info("Ping successful.")
            return True
        except Exception as exc:
            logger.warning("Ping failed: %s", exc)
            return False

    def get_server_time(self) -> int:
        """Return server time in milliseconds."""
        data = self._get("/fapi/v1/time")
        return data["serverTime"]

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Fetch exchange information, optionally filtered by symbol."""
        params = {"symbol": symbol} if symbol else {}
        return self._get("/fapi/v1/exchangeInfo", params)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a futures order on the testnet.

        Args:
            symbol:        Trading pair, e.g. 'BTCUSDT'.
            side:          'BUY' or 'SELL'.
            order_type:    'MARKET', 'LIMIT', or 'STOP_MARKET'.
            quantity:      Order quantity in base asset.
            price:         Limit price (required for LIMIT orders).
            stop_price:    Stop trigger price (required for STOP_MARKET orders).
            time_in_force: 'GTC' | 'IOC' | 'FOK' (ignored for MARKET).
            reduce_only:   Whether this is a reduce-only order.

        Returns:
            Raw API response dictionary.

        Raises:
            BinanceAPIError: On API-level failures.
            BinanceNetworkError: On network failures.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("Price is required for LIMIT orders.")
            params["price"] = price
            params["timeInForce"] = time_in_force

        elif order_type == "STOP_MARKET":
            if stop_price is None:
                raise ValueError("stopPrice is required for STOP_MARKET orders.")
            params["stopPrice"] = stop_price

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(
            "Placing %s %s order | symbol=%s | qty=%s | price=%s | stopPrice=%s",
            side,
            order_type,
            symbol,
            quantity,
            price,
            stop_price,
        )

        response = self._post("/fapi/v1/order", params)
        logger.info(
            "Order placed successfully | orderId=%s | status=%s",
            response.get("orderId"),
            response.get("status"),
        )
        return response

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Fetch all open orders, optionally filtered by symbol."""
        params: Dict[str, Any] = {"timestamp": self._timestamp(), "recvWindow": RECV_WINDOW}
        if symbol:
            params["symbol"] = symbol
        params = self._sign(params)
        url = f"{self._base_url}/fapi/v1/openOrders"
        try:
            response = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise BinanceNetworkError(f"Request failed: {exc}")
        return self._handle_response(response)

    def get_account_info(self) -> Dict[str, Any]:
        """Return account balance and position information."""
        params: Dict[str, Any] = {"timestamp": self._timestamp(), "recvWindow": RECV_WINDOW}
        params = self._sign(params)
        url = f"{self._base_url}/fapi/v2/account"
        try:
            response = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise BinanceNetworkError(f"Request failed: {exc}")
        return self._handle_response(response)
