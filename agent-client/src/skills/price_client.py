"""Price feed skill client using generic trustless verification.

This is a convenience wrapper around the generic call_verified_skill()
function specifically for the price endpoint.
"""

import logging
from typing import Any

from .verified_call import call_verified_skill, VerifiedCallError
from erc8004_common.plugins import IdentityRegistryPlugin

logger = logging.getLogger(__name__)


async def get_verified_price(
    server_agent_id: int,
    symbol: str,
    identity_plugin: IdentityRegistryPlugin,
    web3_utility: Any,
) -> dict:
    """Get verified cryptocurrency price from ROFL-based agent server (v1.0).

    Convenience wrapper around call_verified_skill() for the price endpoint.
    Provides full trustless verification of the price data.

    Args:
        server_agent_id: Server's agent ID from IdentityRegistry (v1.0)
        symbol: Trading pair symbol (e.g., "BTC-USD", "ETH-USD")
        identity_plugin: Initialized identity registry plugin
        web3_utility: Web3Utility instance for signature verification

    Returns:
        Verified price data dictionary:
        {
            "symbol": "BTCUSDT",
            "price": 45000.50,
            "timestamp": "2025-10-09T12:34:56.789Z"
        }

    Raises:
        VerifiedCallError: If any verification step fails

    Example:
        >>> price_data = await get_verified_price(
        ...     42,  # server agent ID (v1.0)
        ...     "BTC-USD",
        ...     identity_plugin,
        ...     web3_utility
        ... )
        >>> print(f"BTC Price: ${price_data['price']:,.2f}")
        BTC Price: $45,000.50

    Security:
        This function performs complete trustless verification:
        - Server discovery via identity registry (using agent ID)
        - Cryptographic signature verification (EIP-191)
        - Signer identity verification
        - ROFL TEE attestation check

        Only returns data if ALL verification checks pass.
    """
    logger.info(f"📊 Getting verified price for {symbol} from agent ID {server_agent_id}")

    price_data = await call_verified_skill(
        server_agent_id=server_agent_id,
        endpoint="/skills/price",
        identity_plugin=identity_plugin,
        web3_utility=web3_utility,
        method="POST",
        json_data={"symbol": symbol},
    )

    logger.info(
        f"✅ Trusted price: {price_data['symbol']} = ${price_data['price']:,.2f}"
    )

    return price_data
