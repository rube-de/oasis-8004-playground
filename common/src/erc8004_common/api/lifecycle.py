"""Lifecycle management handlers for agent API.

Pure handler functions for wallet, status, and registration operations.
Framework-agnostic - no FastAPI dependencies.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_wallet_info(agent: Any, web3_utility: Any, config: Any) -> Dict[str, Any]:
    """Get wallet information including address, balance, and funding status.

    Args:
        agent: Agent instance
        web3_utility: Web3Utility instance with connection
        config: Configuration object with min_balance_for_registration

    Returns:
        Dictionary with wallet information

    Raises:
        ValueError: If web3_utility or config is None
    """
    if not web3_utility:
        raise ValueError("Web3Utility not initialized")

    if not config:
        raise ValueError("Configuration not loaded")

    if not web3_utility.account:
        raise ValueError("No signing account configured")

    address = web3_utility.account.address

    # Get balance
    balance_wei = web3_utility.w3.eth.get_balance(address)
    balance_eth = web3_utility.w3.from_wei(balance_wei, "ether")

    # Check funding status
    min_balance = getattr(config, "min_balance_for_registration", 0.001)
    funded = float(balance_eth) >= min_balance

    # Get chain info
    chain_id = web3_utility.w3.eth.chain_id

    # Chain name mapping (expand as needed)
    chain_names = {
        1: "Ethereum Mainnet",
        11155111: "Ethereum Sepolia",
        23294: "Oasis Sapphire Testnet",
        23295: "Oasis Sapphire Mainnet",
    }
    chain_name = chain_names.get(chain_id, f"Chain {chain_id}")

    # EIP-681 payment URI for QR code
    qr_code_data = f"ethereum:{address}?chainId={chain_id}"

    # ROFL mode detection
    rofl_mode = not getattr(config, "use_local_mode", False)
    rofl_key_id = getattr(config, "rofl_key_id", None) if rofl_mode else None

    return {
        "address": address,
        "balance": str(balance_eth),
        "balance_wei": str(balance_wei),
        "funded": funded,
        "minimum_balance": str(min_balance),
        "chain_id": chain_id,
        "chain_name": chain_name,
        "qr_code_data": qr_code_data,
        "rofl_mode": rofl_mode,
        "rofl_key_id": rofl_key_id,
    }


def get_status(agent: Any) -> Dict[str, Any]:
    """Get agent status including registration, funding, and operational state.

    Args:
        agent: Agent instance with state

    Returns:
        Dictionary with comprehensive status information

    Raises:
        ValueError: If agent is None
    """
    if not agent:
        raise ValueError("Agent not initialized")

    # Determine current status
    status = "uninitialized"

    if agent.web3_utility and agent.config:
        # Agent is initialized (key derived, Web3 connected)
        status = "initialized"

        # Check if domain is set
        domain = getattr(agent.config, "agent_domain", None)
        has_domain = domain is not None and len(domain) > 0

        # Check if funded
        funded = False
        balance_eth = "0"
        if agent.web3_utility.account:
            balance_wei = agent.web3_utility.w3.eth.get_balance(
                agent.web3_utility.account.address
            )
            balance_eth = str(agent.web3_utility.w3.from_wei(balance_wei, "ether"))
            min_balance = getattr(agent.config, "min_balance_for_registration", 0.001)
            funded = float(balance_eth) >= min_balance

        # Check if registered
        is_registered = agent.agent_id is not None

        if has_domain and funded:
            status = "ready"  # Ready to register

        if is_registered:
            status = "registered"  # Registered on-chain

        if is_registered and agent.running:
            status = "operational"  # Fully operational

    # Build response
    address = (
        agent.web3_utility.account.address
        if agent.web3_utility and agent.web3_utility.account
        else "unknown"
    )
    domain = getattr(agent.config, "agent_domain", None) if agent.config else None
    chain_id = agent.web3_utility.w3.eth.chain_id if agent.web3_utility else 0

    # ROFL info
    rofl_enabled = not getattr(agent.config, "use_local_mode", False) if agent.config else False
    rofl_key_id = getattr(agent.config, "rofl_key_id", None) if agent.config and rofl_enabled else None

    # Balance info
    funded = False
    balance_eth = "0"
    if agent.web3_utility and agent.web3_utility.account:
        balance_wei = agent.web3_utility.w3.eth.get_balance(
            agent.web3_utility.account.address
        )
        balance_eth = str(agent.web3_utility.w3.from_wei(balance_wei, "ether"))
        min_balance = getattr(agent.config, "min_balance_for_registration", 0.001)
        funded = float(balance_eth) >= min_balance

    return {
        "status": status,
        "agent": {
            "domain": domain,
            "address": address,
            "agent_id": agent.agent_id,
            "is_registered": agent.agent_id is not None,
            "chain_id": chain_id,
        },
        "rofl": {
            "enabled": rofl_enabled,
            "key_id": rofl_key_id,
        },
        "balance": {
            "eth": balance_eth,
            "funded": funded,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def register_agent(agent: Any) -> Dict[str, Any]:
    """Trigger agent registration on-chain.

    Prerequisites:
        - Domain must be set (via set_domain)
        - Wallet must be funded

    Args:
        agent: Agent instance

    Returns:
        Dictionary with registration result

    Raises:
        ValueError: If prerequisites not met
        Exception: If registration fails
    """
    if not agent:
        raise ValueError("Agent not initialized")

    if not agent.config:
        raise ValueError("Configuration not loaded")

    if not agent.web3_utility or not agent.web3_utility.account:
        raise ValueError("Web3 utility not initialized")

    # Check if domain is set
    domain = getattr(agent.config, "agent_domain", None)
    if not domain or len(domain.strip()) == 0:
        raise ValueError(
            "Domain not set. Call POST /api/config/domain to set domain before registration."
        )

    # Check if funded
    balance_wei = agent.web3_utility.w3.eth.get_balance(
        agent.web3_utility.account.address
    )
    balance_eth = agent.web3_utility.w3.from_wei(balance_wei, "ether")
    min_balance = getattr(agent.config, "min_balance_for_registration", 0.001)

    if float(balance_eth) < min_balance:
        raise ValueError(
            f"Insufficient balance for registration. "
            f"Current: {balance_eth} ETH, Required: {min_balance} ETH. "
            f"Fund address {agent.web3_utility.account.address} before registering."
        )

    # Check if already registered
    already_registered = False
    if agent.agent_id is not None:
        logger.info(f"Agent already registered with ID: {agent.agent_id}")
        already_registered = True

        # Return existing registration info
        return {
            "success": True,
            "agent_id": agent.agent_id,
            "domain": domain,
            "address": agent.web3_utility.account.address,
            "tx_hash": "0x0",  # No transaction for existing registration
            "explorer_url": None,
            "already_registered": True,
        }

    # Execute registration
    logger.info(f"Registering agent with domain: {domain}")

    try:
        # Call agent's ensure_registered method
        agent_id = agent.ensure_registered()

        # Get transaction hash from identity plugin if available
        # (Note: ensure_registered doesn't return tx_hash, would need to modify it)
        tx_hash = "0x0"  # Placeholder - actual tx_hash would need to be captured

        # Build explorer URL
        chain_id = agent.web3_utility.w3.eth.chain_id
        explorer_url = None

        # Chain explorer mapping
        explorers = {
            1: "https://etherscan.io/tx",
            11155111: "https://sepolia.etherscan.io/tx",
            23294: "https://explorer.oasis.io/testnet/sapphire/tx",
            23295: "https://explorer.oasis.io/mainnet/sapphire/tx",
        }

        if chain_id in explorers and tx_hash != "0x0":
            explorer_url = f"{explorers[chain_id]}/{tx_hash}"

        logger.info(f"✓ Registration successful! Agent ID: {agent_id}")

        return {
            "success": True,
            "agent_id": agent_id,
            "domain": domain,
            "address": agent.web3_utility.account.address,
            "tx_hash": tx_hash,
            "explorer_url": explorer_url,
            "already_registered": False,
        }

    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise Exception(f"Registration failed: {str(e)}") from e
