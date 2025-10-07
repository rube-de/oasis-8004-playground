"""Cryptocurrency price fetching skill using Binance public API.

This module provides functionality to fetch real-time cryptocurrency prices
from Binance's public API endpoint. No authentication required.
"""

import logging
import re
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Binance public API endpoint
BINANCE_API_BASE = "https://api.binance.com/api/v3"
TICKER_ENDPOINT = f"{BINANCE_API_BASE}/ticker/price"

# Request timeout in seconds
REQUEST_TIMEOUT = 10.0


class PriceFetchError(Exception):
    """Base exception for price fetching errors."""
    pass


class InvalidSymbolError(PriceFetchError):
    """Raised when symbol format is invalid or not found."""
    pass


class NetworkError(PriceFetchError):
    """Raised when network request fails."""
    pass


class RateLimitError(PriceFetchError):
    """Raised when Binance API rate limit is exceeded."""
    pass


def normalize_symbol(symbol: str) -> str:
    """Normalize trading pair symbol to Binance format.

    Supports formats like:
    - BTC-USD, ETH-USD (converts to BTCUSDT, ETHUSDT)
    - BTCUSDT, ETHUSDT (passes through)
    - btc-usd, eth-usd (case insensitive)

    Args:
        symbol: Trading pair symbol in various formats

    Returns:
        Normalized symbol in Binance format (e.g., BTCUSDT)

    Raises:
        InvalidSymbolError: If symbol format is invalid

    Example:
        >>> normalize_symbol("BTC-USD")
        "BTCUSDT"
        >>> normalize_symbol("ETHUSDT")
        "ETHUSDT"
    """
    if not symbol or not isinstance(symbol, str):
        raise InvalidSymbolError("Symbol must be a non-empty string")

    # Remove whitespace and convert to uppercase
    symbol = symbol.strip().upper()

    # Pattern 1: XXX-YYY format (e.g., BTC-USD)
    if "-" in symbol:
        parts = symbol.split("-")
        if len(parts) != 2:
            raise InvalidSymbolError(
                f"Invalid symbol format: {symbol}. Expected format: BTC-USD or BTCUSDT"
            )

        base, quote = parts

        # Convert USD to USDT for Binance
        if quote == "USD":
            quote = "USDT"

        return f"{base}{quote}"

    # Pattern 2: Already in Binance format (e.g., BTCUSDT)
    # Basic validation: should be 6-12 characters, alphanumeric
    if not re.match(r"^[A-Z0-9]{6,12}$", symbol):
        raise InvalidSymbolError(
            f"Invalid symbol format: {symbol}. Expected format: BTC-USD or BTCUSDT"
        )

    return symbol


async def get_price(symbol: str) -> dict[str, Any]:
    """Fetch current price for a cryptocurrency trading pair from Binance.

    Args:
        symbol: Trading pair symbol (e.g., "BTC-USD", "BTCUSDT")

    Returns:
        Dictionary with price information:
        {
            "symbol": "BTCUSDT",
            "price": 45000.50,
            "timestamp": "2025-10-07T12:34:56.789Z"
        }

    Raises:
        InvalidSymbolError: If symbol format is invalid or not found on Binance
        NetworkError: If network request fails
        RateLimitError: If Binance API rate limit exceeded

    Example:
        >>> price_data = await get_price("BTC-USD")
        >>> print(f"BTC price: ${price_data['price']}")
        BTC price: $45000.50
    """
    # Normalize symbol to Binance format
    try:
        normalized_symbol = normalize_symbol(symbol)
    except InvalidSymbolError:
        logger.error(f"Invalid symbol format: {symbol}")
        raise

    logger.info(f"Fetching price for {normalized_symbol} from Binance")

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                TICKER_ENDPOINT,
                params={"symbol": normalized_symbol},
            )

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning(f"Binance API rate limit exceeded for {normalized_symbol}")
                raise RateLimitError(
                    "Binance API rate limit exceeded. Please try again later."
                )

            # Handle symbol not found
            if response.status_code == 400:
                logger.error(f"Symbol not found on Binance: {normalized_symbol}")
                raise InvalidSymbolError(
                    f"Symbol {normalized_symbol} not found on Binance. "
                    f"Check symbol format (e.g., BTC-USD, ETHUSDT)."
                )

            # Handle other errors
            if response.status_code != 200:
                logger.error(
                    f"Binance API error: status={response.status_code}, "
                    f"body={response.text}"
                )
                raise NetworkError(
                    f"Binance API returned error: {response.status_code}"
                )

            # Parse response
            data = response.json()

            # Extract price
            price_str = data.get("price")
            if not price_str:
                raise NetworkError("Invalid response from Binance API: missing price")

            price = float(price_str)

            # Build result
            result = {
                "symbol": normalized_symbol,
                "price": price,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            logger.info(
                f"Successfully fetched price: {normalized_symbol} = {price}"
            )

            return result

    except httpx.TimeoutException as e:
        logger.error(f"Request timeout for {normalized_symbol}: {e}")
        raise NetworkError(
            f"Request to Binance API timed out after {REQUEST_TIMEOUT}s"
        ) from e

    except httpx.RequestError as e:
        logger.error(f"Network error for {normalized_symbol}: {e}")
        raise NetworkError(
            f"Failed to connect to Binance API: {e}"
        ) from e

    except (ValueError, KeyError) as e:
        logger.error(f"Failed to parse Binance response for {normalized_symbol}: {e}")
        raise NetworkError(
            f"Invalid response format from Binance API"
        ) from e


# Sync wrapper for non-async contexts
def get_price_sync(symbol: str) -> dict[str, Any]:
    """Synchronous wrapper for get_price().

    Args:
        symbol: Trading pair symbol (e.g., "BTC-USD", "BTCUSDT")

    Returns:
        Dictionary with price information

    Raises:
        PriceFetchError: If price fetching fails
    """
    import asyncio

    try:
        return asyncio.run(get_price(symbol))
    except Exception as e:
        logger.error(f"Error fetching price: {e}")
        raise
