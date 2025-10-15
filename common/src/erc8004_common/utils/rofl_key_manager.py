"""ROFL key management for secure key generation in TEE.

Provides utilities for generating and retrieving cryptographic keys from
Oasis ROFL (Runtime Off-chain Logic Framework) service. Keys are generated
within a Trusted Execution Environment (TEE) and never exposed as plaintext
to the host system.

Key Features:
- TEE-based key generation (SECP256K1)
- Persistent key storage by key-id
- Idempotent operations (same key-id → same key)
- Async/sync API support

Example:
    >>> # Sync usage (most common)
    >>> key = RoflKeyManager.generate_or_get_key_sync("agent.example.com")
    >>> print(f"Key: {key[:10]}...")

    >>> # Async usage
    >>> key = await RoflKeyManager.generate_or_get_key_async("agent.example.com")
"""

import asyncio
import logging
from typing import Optional

try:
    from oasis_rofl_client import RoflClient
    ROFL_AVAILABLE = True
except ImportError:
    ROFL_AVAILABLE = False

logger = logging.getLogger(__name__)


class RoflKeyManagerError(Exception):
    """Base exception for ROFL key manager errors."""
    pass


class RoflKeyManager:
    """Utility for ROFL-based key generation and retrieval.

    Provides sync and async methods to generate or retrieve SECP256K1 keys
    from the ROFL service. Keys are stored persistently by key-id within
    the TEE, enabling secure key reuse across application restarts.

    The key-id should be a unique, stable identifier for the agent
    (e.g., agent domain name).
    """

    @staticmethod
    async def generate_or_get_key_async(
        key_id: str,
        socket_path: str = "/run/rofl-appd.sock"
    ) -> str:
        """Generate or retrieve SECP256K1 key from ROFL (async).

        Generates a new SECP256K1 private key if the key-id doesn't exist,
        or retrieves the existing key if it does. Keys are stored persistently
        within ROFL's TEE storage.

        Args:
            key_id: Unique identifier for the key (e.g., "agent.example.com").
                    Should be stable across restarts to enable key reuse.
            socket_path: Path to ROFL Unix socket. Default: /run/rofl-appd.sock

        Returns:
            Private key as hex string (64 characters, without 0x prefix)

        Raises:
            RoflKeyManagerError: If ROFL client is unavailable or key
                                generation/retrieval fails

        Example:
            >>> key = await RoflKeyManager.generate_or_get_key_async(
            ...     key_id="agent.example.com"
            ... )
            >>> print(f"Generated key: {key[:10]}...")
        """
        if not ROFL_AVAILABLE:
            raise RoflKeyManagerError(
                "oasis-rofl-client not installed. "
                "Install with: uv add oasis-rofl-client"
            )

        try:
            # Initialize ROFL client with Unix socket connection
            logger.info(f"Connecting to ROFL service: {socket_path}")
            client = RoflClient(url=f"unix://{socket_path}")

            logger.info(f"Generating/retrieving ROFL key: key_id={key_id}")

            # Generate or retrieve key (SECP256K1 is default)
            # This operation is idempotent - same key_id returns same key
            key_hex = await client.generate_key(key_id)

            # Normalize key format (remove 0x prefix if present)
            if key_hex.startswith("0x"):
                key_hex = key_hex[2:]

            # Validate key length (should be 64 hex chars = 32 bytes)
            if len(key_hex) != 64:
                raise RoflKeyManagerError(
                    f"Invalid key length from ROFL: expected 64 chars, got {len(key_hex)}"
                )

            logger.info(f"✓ ROFL key ready: key_id={key_id}, length={len(key_hex)}")

            return key_hex

        except ImportError as e:
            raise RoflKeyManagerError(
                f"Failed to import oasis-rofl-client: {e}"
            ) from e
        except ConnectionError as e:
            raise RoflKeyManagerError(
                f"Failed to connect to ROFL service at {socket_path}: {e}. "
                f"Ensure ROFL service (rofl-appd) is running."
            ) from e
        except Exception as e:
            raise RoflKeyManagerError(
                f"Failed to generate/retrieve ROFL key: {e}. "
                f"Check ROFL service status and socket permissions."
            ) from e

    @staticmethod
    def generate_or_get_key_sync(
        key_id: str,
        socket_path: str = "/run/rofl-appd.sock"
    ) -> str:
        """Generate or retrieve SECP256K1 key from ROFL (sync wrapper).

        Synchronous wrapper around generate_or_get_key_async(). Creates a new
        event loop for the async operation. Suitable for synchronous codebases.

        Args:
            key_id: Unique identifier for the key (e.g., "agent.example.com")
            socket_path: Path to ROFL Unix socket. Default: /run/rofl-appd.sock

        Returns:
            Private key as hex string (64 characters, without 0x prefix)

        Raises:
            RoflKeyManagerError: If key generation/retrieval fails

        Example:
            >>> # Use in synchronous code
            >>> key = RoflKeyManager.generate_or_get_key_sync("agent.example.com")
            >>> from eth_account import Account
            >>> account = Account.from_key(f"0x{key}")
            >>> print(f"Address: {account.address}")
        """
        try:
            # Run async method in new event loop
            return asyncio.run(
                RoflKeyManager.generate_or_get_key_async(key_id, socket_path)
            )
        except RuntimeError as e:
            # Handle event loop issues
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                raise RoflKeyManagerError(
                    "Cannot call sync method from async context. "
                    "Use generate_or_get_key_async() instead."
                ) from e
            raise
