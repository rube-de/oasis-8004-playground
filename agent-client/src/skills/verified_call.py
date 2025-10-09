"""Generic verified skill calling with trustless verification.

This module provides skill-agnostic verification for any ROFL-based
agent server. Use this for calling ANY skill endpoint, not just specific ones.

The verification pattern is universal:
1. Discover server via identity registry
2. Call skill HTTP endpoint
3. Verify signature on response
4. Verify signer matches registry
5. Verify ROFL TEE attestation

This ensures trustless execution for all agent-to-agent interactions.
"""

import logging
from typing import Any, Optional

import httpx

from erc8004_common.utils import verify_rofl_attestation
from erc8004_common.plugins import IdentityRegistryPlugin

logger = logging.getLogger(__name__)


class VerifiedCallError(Exception):
    """Raised when verified skill call fails at any verification step."""

    pass


async def call_verified_skill(
    server_address: str,
    endpoint: str,
    identity_plugin: IdentityRegistryPlugin,
    web3_utility: Any,
    method: str = "POST",
    json_data: Optional[dict] = None,
    timeout: int = 10,
) -> dict:
    """Call any skill endpoint with full trustless verification.

    This is the core verification function that works with ANY skill.
    It handles the complete trust chain automatically.

    Args:
        server_address: Server's Ethereum address
        endpoint: Skill endpoint path (e.g., "/skills/price")
        identity_plugin: Initialized identity registry plugin
        web3_utility: Web3Utility instance for signature verification
        method: HTTP method (default: POST)
        json_data: Request payload (optional)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Verified data payload (only the 'data' field from signed response)

    Raises:
        VerifiedCallError: If any verification step fails

    Example:
        >>> # Call price skill
        >>> data = await call_verified_skill(
        ...     "0xSERVER",
        ...     "/skills/price",
        ...     identity_plugin,
        ...     web3_utility,
        ...     json_data={"symbol": "BTC-USD"}
        ... )
        >>> print(data['price'])

        >>> # Call any custom skill
        >>> data = await call_verified_skill(
        ...     "0xSERVER",
        ...     "/skills/custom",
        ...     identity_plugin,
        ...     web3_utility,
        ...     json_data={"query": "analyze"}
        ... )

    Security:
        All responses are verified through:
        - Cryptographic signature (EIP-191)
        - Identity registry authorization
        - ROFL TEE attestation
    """
    from erc8004_common.utils import discover_agent

    logger.info(f"🔐 Verified call: {server_address}{endpoint}")

    # Step 1: Discover server agent via identity registry
    logger.info("1️⃣ Discovering server agent...")
    try:
        agent_card = await discover_agent(server_address, identity_plugin)
        logger.info(f"   ✅ Found: {agent_card.name} at {agent_card.url}")
    except Exception as e:
        raise VerifiedCallError(
            f"Server discovery failed for {server_address}: {e}"
        ) from e

    # Step 2: Call skill endpoint
    logger.info(f"2️⃣ Calling skill endpoint {endpoint}...")
    url = f"{agent_card.url}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method.upper() == "POST":
                response = await client.post(url, json=json_data or {})
            elif method.upper() == "GET":
                response = await client.get(url, params=json_data or {})
            else:
                raise VerifiedCallError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            signed_response = response.json()

        logger.info(f"   ✅ Received signed response")

    except httpx.HTTPStatusError as e:
        raise VerifiedCallError(
            f"HTTP {e.response.status_code}: {e.response.text}"
        ) from e
    except httpx.TimeoutException as e:
        raise VerifiedCallError(
            f"Request timeout after {timeout}s"
        ) from e
    except httpx.NetworkError as e:
        raise VerifiedCallError(
            f"Network error: {e}"
        ) from e
    except Exception as e:
        raise VerifiedCallError(
            f"Skill call failed: {e}"
        ) from e

    # Validate response structure
    if not isinstance(signed_response, dict):
        raise VerifiedCallError(
            f"Invalid response type: expected dict, got {type(signed_response).__name__}"
        )

    if 'data' not in signed_response or 'signature' not in signed_response:
        raise VerifiedCallError(
            "Invalid response format: missing 'data' or 'signature' fields"
        )

    # Step 3: Verify cryptographic signature
    logger.info("3️⃣ Verifying signature...")
    try:
        is_valid, recovered_address = web3_utility.verify_signature(signed_response)

        if not is_valid:
            raise VerifiedCallError(
                "Invalid signature - data may have been tampered with"
            )

        logger.info(f"   ✅ Signature valid from {recovered_address}")

    except VerifiedCallError:
        raise
    except Exception as e:
        raise VerifiedCallError(
            f"Signature verification failed: {e}"
        ) from e

    # Step 4: Verify signer matches identity registry
    logger.info("4️⃣ Verifying signer matches identity registry...")

    if recovered_address.lower() != server_address.lower():
        raise VerifiedCallError(
            f"❌ SECURITY ALERT: Signer mismatch!\n"
            f"   Expected (from registry): {server_address}\n"
            f"   Got (from signature): {recovered_address}\n"
            f"   This could indicate a man-in-the-middle attack or misconfiguration."
        )

    logger.info(f"   ✅ Signer matches registry: {server_address}")

    # Step 5: Verify ROFL TEE attestation
    logger.info("5️⃣ Verifying ROFL attestation...")

    try:
        has_attestation = await verify_rofl_attestation(server_address)

        if not has_attestation:
            raise VerifiedCallError(
                f"❌ SECURITY ALERT: Server lacks valid ROFL attestation!\n"
                f"   Address: {server_address}\n"
                f"   Cannot trust data from non-TEE source.\n"
                f"   Server must be running in a trusted execution environment."
            )

        logger.info(f"   ✅ Valid ROFL attestation confirmed")

    except VerifiedCallError:
        raise
    except Exception as e:
        raise VerifiedCallError(
            f"Attestation verification failed: {e}"
        ) from e

    # All verification checks passed!
    logger.info(f"✅ All verification checks passed! Data is trustworthy.")

    # Return only the data payload (without signature envelope)
    return signed_response['data']
