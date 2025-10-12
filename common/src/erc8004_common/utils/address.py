"""Address utilities for CAIP-10 format handling.

CAIP-10 (Chain Agnostic Improvement Proposal 10) defines a standard for
blockchain account addresses across different chains.

Format: namespace:reference:address
Example: eip155:1:0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb

References:
- CAIP-10 spec: https://github.com/ChainAgnostic/CAIPs/blob/master/CAIPs/caip-10.md
- Used in ERC-8004 AgentCard for blockchain registrations
"""

import re
from typing import Optional


class AddressFormatError(Exception):
    """Raised when address format is invalid."""
    pass


def extract_address_from_caip10(caip10_or_plain: str) -> str:
    """Extract plain Ethereum address from CAIP-10 format or return as-is.

    Handles both CAIP-10 formatted addresses and plain Ethereum addresses.
    This is useful for comparing addresses from different sources:
    - AgentCard registrations (CAIP-10 format)
    - Signature recovery (plain Ethereum format)

    Args:
        caip10_or_plain: Address in CAIP-10 format (e.g., "eip155:1:0x742d35...")
                        or plain Ethereum format (e.g., "0x742d35...")

    Returns:
        Plain Ethereum address (e.g., "0x742d35...")

    Raises:
        AddressFormatError: If address format is invalid

    Examples:
        >>> extract_address_from_caip10("eip155:1:0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"

        >>> extract_address_from_caip10("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"

    CAIP-10 Format:
        namespace:reference:address
        - namespace: "eip155" (Ethereum)
        - reference: chain ID (e.g., "1" for mainnet, "11155111" for Sepolia)
        - address: Ethereum address with 0x prefix

    Security Note:
        This function is designed for ADDRESS COMPARISON only, not for
        cryptographic operations. EIP-191 signature verification inherently
        uses plain Ethereum addresses, while CAIP-10 is for identification.
    """
    if not caip10_or_plain:
        raise AddressFormatError("Address cannot be empty")

    # If it's already a plain Ethereum address, return as-is
    if caip10_or_plain.startswith("0x"):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", caip10_or_plain):
            raise AddressFormatError(
                f"Invalid Ethereum address format: {caip10_or_plain}"
            )
        return caip10_or_plain

    # Parse CAIP-10 format: namespace:reference:address
    parts = caip10_or_plain.split(":")
    if len(parts) != 3:
        raise AddressFormatError(
            f"Invalid CAIP-10 format: expected 3 parts (namespace:reference:address), "
            f"got {len(parts)} parts in '{caip10_or_plain}'"
        )

    namespace, reference, address = parts

    # Validate namespace (should be eip155 for Ethereum)
    if namespace != "eip155":
        raise AddressFormatError(
            f"Unsupported namespace '{namespace}' (expected 'eip155' for Ethereum)"
        )

    # Validate reference (should be numeric chain ID)
    if not reference.isdigit():
        raise AddressFormatError(
            f"Invalid chain reference '{reference}' (expected numeric chain ID)"
        )

    # Validate address (should be 0x-prefixed hex)
    if not address.startswith("0x"):
        raise AddressFormatError(
            f"Invalid address format '{address}' (expected 0x prefix)"
        )

    if not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        raise AddressFormatError(
            f"Invalid Ethereum address format: {address}"
        )

    return address


def parse_caip10(caip10_address: str) -> dict:
    """Parse CAIP-10 address into components.

    Args:
        caip10_address: Address in CAIP-10 format (e.g., "eip155:1:0x742d35...")

    Returns:
        Dictionary with components:
        {
            "namespace": "eip155",
            "chain_id": 1,
            "address": "0x742d35..."
        }

    Raises:
        AddressFormatError: If format is invalid

    Example:
        >>> parse_caip10("eip155:11155111:0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
        {
            "namespace": "eip155",
            "chain_id": 11155111,
            "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        }
    """
    parts = caip10_address.split(":")
    if len(parts) != 3:
        raise AddressFormatError(
            f"Invalid CAIP-10 format: expected 3 parts, got {len(parts)}"
        )

    namespace, reference, address = parts

    if namespace != "eip155":
        raise AddressFormatError(f"Unsupported namespace: {namespace}")

    if not reference.isdigit():
        raise AddressFormatError(f"Invalid chain reference: {reference}")

    return {
        "namespace": namespace,
        "chain_id": int(reference),
        "address": address,
    }


def to_caip10(address: str, chain_id: int) -> str:
    """Convert plain Ethereum address to CAIP-10 format.

    Args:
        address: Plain Ethereum address (e.g., "0x742d35...")
        chain_id: Ethereum chain ID (e.g., 1 for mainnet, 11155111 for Sepolia)

    Returns:
        CAIP-10 formatted address (e.g., "eip155:1:0x742d35...")

    Raises:
        AddressFormatError: If address format is invalid

    Example:
        >>> to_caip10("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb", 1)
        "eip155:1:0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
    """
    if not address.startswith("0x"):
        raise AddressFormatError(f"Address must start with 0x: {address}")

    if not re.match(r"^0x[a-fA-F0-9]{40}$", address):
        raise AddressFormatError(f"Invalid Ethereum address format: {address}")

    if chain_id <= 0:
        raise AddressFormatError(f"Invalid chain_id: {chain_id}")

    return f"eip155:{chain_id}:{address}"
