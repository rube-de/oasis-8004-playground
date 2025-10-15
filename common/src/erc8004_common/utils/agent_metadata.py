"""ERC-8004 registration metadata utilities.

This module provides utilities for building ERC-8004 v1.0 compliant registration
metadata (registration-v1 format) separate from A2A protocol agent cards.

Key Distinction:
    - Registration format (this module): For tokenURI, minimal metadata for on-chain identity
    - Agent card format (agent_card.py): For A2A protocol discovery, full agent capabilities

ERC-8004 v1.0 Registration Format:
    The tokenURI in IdentityRegistry should point to a JSON file with this structure:
    {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": "Agent Name",
        "description": "Agent description",
        "endpoints": [
            {
                "name": "A2A",
                "endpoint": "https://domain/.well-known/agent-card.json",
                "version": "0.3.0"
            },
            {
                "name": "agentWallet-ChainName",
                "endpoint": "eip155:chainId:address"
            }
        ],
        "supportedTrust": ["tee-attestation", "feedback"],
        "registrations": [
            {
                "agentId": 1,
                "agentRegistry": "eip155:chainId:identityRegistryAddress"
            }
        ]
    }

Reference:
    https://eips.ethereum.org/EIPS/eip-8004
"""

from typing import Dict, Any, Optional, List


# Chain ID to name mapping for endpoint labeling
CHAIN_NAMES: Dict[int, str] = {
    # Mainnets
    1: "Ethereum",
    10: "Optimism",
    56: "BSC",
    137: "Polygon",
    8453: "Base",
    42161: "Arbitrum",
    23294: "Oasis-Sapphire",

    # Testnets
    31337: "Hardhat-Local",
    1337: "Ganache-Local",
    11155111: "Ethereum-Sepolia",
    84532: "Base-Sepolia",
    11155420: "Optimism-Sepolia",
    919: "Mode-Testnet",
    16602: "0G-Testnet",
    23295: "Oasis-Sapphire-Testnet",
    17000: "Holesky",
    421614: "Arbitrum-Sepolia",
    80002: "Polygon-Amoy",
}


def get_chain_name(chain_id: int) -> str:
    """Get human-readable chain name from chain ID.

    Args:
        chain_id: EVM chain ID

    Returns:
        Chain name (e.g., "Ethereum-Sepolia", "Base-Sepolia")
        Falls back to "Chain-{chain_id}" if unknown

    Example:
        >>> get_chain_name(11155111)
        'Ethereum-Sepolia'
        >>> get_chain_name(999999)
        'Chain-999999'
    """
    return CHAIN_NAMES.get(chain_id, f"Chain-{chain_id}")


def format_caip10_address(chain_id: int, address: str) -> str:
    """Format Ethereum address as CAIP-10 identifier.

    CAIP-10 defines chain-agnostic account identifiers:
    https://github.com/ChainAgnostic/CAIPs/blob/master/CAIPs/caip-10.md

    Args:
        chain_id: EVM chain ID (e.g., 1 for mainnet, 31337 for hardhat)
        address: Ethereum address (with or without 0x prefix)

    Returns:
        CAIP-10 formatted address: eip155:{chain_id}:{address}

    Example:
        >>> format_caip10_address(1, "0x1234...5678")
        'eip155:1:0x1234...5678'
    """
    # Ensure address has 0x prefix
    if not address.startswith("0x"):
        address = f"0x{address}"

    return f"eip155:{chain_id}:{address}"


def build_erc8004_registration(
    agent_domain: str,
    agent_address: str,
    chain_id: int,
    identity_registry_address: str,
    name: str,
    description: str,
    agent_id: Optional[int] = None,
    use_rofl: bool = False,
    protocol: str = "http",
) -> Dict[str, Any]:
    """Build ERC-8004 v1.0 registration-v1 format for tokenURI.

    Creates the minimal registration metadata required by ERC-8004 spec.
    This is separate from the full A2A protocol agent card.

    The registration format includes:
    - Agent identity information
    - Endpoints (A2A card, wallet addresses)
    - Supported trust models
    - Blockchain registrations (if agent_id is known)

    Args:
        agent_domain: Agent domain (e.g., "agent.example.com")
        agent_address: Agent's Ethereum address (checksummed)
        chain_id: Blockchain chain ID
        identity_registry_address: Identity Registry contract address
        name: Agent name
        description: Agent description
        agent_id: Agent ID from registry (None if not yet registered)
        use_rofl: Whether agent uses ROFL/TEE (affects supportedTrust)
        protocol: Protocol for endpoints (http or https)

    Returns:
        Dictionary with registration-v1 format, ready for JSON serialization

    Example:
        >>> registration = build_erc8004_registration(
        ...     agent_domain="agent.local",
        ...     agent_address="0x1234...",
        ...     chain_id=31337,
        ...     identity_registry_address="0xabcd...",
        ...     name="My Agent",
        ...     description="Test agent",
        ...     agent_id=1,
        ...     use_rofl=True
        ... )
        >>> registration["type"]
        'https://eips.ethereum.org/EIPS/eip-8004#registration-v1'
    """
    # Build endpoints array
    endpoints: List[Dict[str, Any]] = []

    # 1. A2A endpoint (points to agent-card.json for full discovery)
    endpoints.append({
        "name": "A2A",
        "endpoint": f"{protocol}://{agent_domain}/.well-known/agent-card.json",
        "version": "0.3.0"
    })

    # 2. Agent wallet endpoint (CAIP-10 format)
    chain_name = get_chain_name(chain_id)
    endpoints.append({
        "name": f"agentWallet-{chain_name}",
        "endpoint": format_caip10_address(chain_id, agent_address)
    })

    # Build supported trust models
    supported_trust = ["feedback"]  # Always support feedback-based trust
    if use_rofl:
        supported_trust.append("tee-attestation")  # Add TEE if ROFL enabled

    # Build registration object
    registration: Dict[str, Any] = {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": name,
        "description": description,
        "endpoints": endpoints,
        "supportedTrust": supported_trust,
    }

    # Add registrations array if agent_id is known (post-registration)
    if agent_id is not None:
        registration["registrations"] = [
            {
                "agentId": agent_id,
                "agentRegistry": format_caip10_address(
                    chain_id,
                    identity_registry_address
                )
            }
        ]

    return registration


def build_erc8004_registration_with_config(
    agent_domain: str,
    agent_address: str,
    chain_id: int,
    identity_registry_address: str,
    agent_id: Optional[int],
    config: Any,  # Config object with agent_name, agent_description, etc.
    protocol: str = "http",
) -> Dict[str, Any]:
    """Build ERC-8004 registration using Config object for customization.

    Convenience wrapper around build_erc8004_registration() that extracts
    agent name, description, and ROFL settings from a Config object.

    Args:
        agent_domain: Agent domain
        agent_address: Agent's Ethereum address
        chain_id: Blockchain chain ID
        identity_registry_address: Identity Registry address
        agent_id: Agent ID (None if not yet registered)
        config: Config object with optional agent_name, agent_description, use_local_mode
        protocol: Protocol for endpoints (http or https)

    Returns:
        Dictionary with registration-v1 format

    Example:
        >>> from agent.config import Config
        >>> config = Config()
        >>> registration = build_erc8004_registration_with_config(
        ...     agent_domain=config.agent_domain,
        ...     agent_address="0x1234...",
        ...     chain_id=31337,
        ...     identity_registry_address=config.identity_registry_address,
        ...     agent_id=1,
        ...     config=config
        ... )
    """
    # Extract name and description from config
    name = getattr(config, "agent_name", None)
    if name is None:
        name = f"ERC-8004 Agent {agent_id}" if agent_id else "ERC-8004 Agent"

    description = getattr(config, "agent_description", None)
    if description is None:
        description = (
            "ERC-8004 compliant autonomous agent with identity "
            "registration capabilities"
        )

    # Determine if ROFL is being used (inverse of use_local_mode)
    use_rofl = not getattr(config, "use_local_mode", False)

    return build_erc8004_registration(
        agent_domain=agent_domain,
        agent_address=agent_address,
        chain_id=chain_id,
        identity_registry_address=identity_registry_address,
        name=name,
        description=description,
        agent_id=agent_id,
        use_rofl=use_rofl,
        protocol=protocol,
    )
