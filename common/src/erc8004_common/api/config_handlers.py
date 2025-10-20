"""Configuration management handlers for agent API.

Pure handler functions for retrieving and updating agent configuration.
Framework-agnostic - no FastAPI dependencies.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_config(agent: Any) -> Dict[str, Any]:
    """Get current agent configuration.

    Args:
        agent: Agent instance with configuration

    Returns:
        Dictionary with current configuration

    Raises:
        ValueError: If agent or config is None
    """
    if not agent:
        raise ValueError("Agent not initialized")

    if not agent.config:
        raise ValueError("Configuration not loaded")

    config = agent.config

    # Get domain (may be None if not set yet)
    domain = getattr(config, "agent_domain", None)

    # Get chain ID
    chain_id = 0
    if agent.web3_utility and agent.web3_utility.w3:
        chain_id = agent.web3_utility.w3.eth.chain_id

    # ROFL configuration
    rofl_enabled = not getattr(config, "use_local_mode", False)
    rofl_key_id = getattr(config, "rofl_key_id", None) if rofl_enabled else None
    rofl_socket_path = getattr(config, "rofl_socket_path", None) if rofl_enabled else None

    # Registry addresses
    identity_registry = getattr(config, "identity_registry_address", "")
    reputation_registry = getattr(config, "reputation_registry_address", None)
    validation_registry = getattr(config, "validation_registry_address", None)

    return {
        "domain": domain,
        "chain_id": chain_id,
        "rofl_enabled": rofl_enabled,
        "rofl_key_id": rofl_key_id,
        "rofl_socket_path": rofl_socket_path,
        "identity_registry": identity_registry,
        "reputation_registry": reputation_registry,
        "validation_registry": validation_registry,
    }


async def set_domain(agent: Any, domain: str) -> Dict[str, Any]:
    """Set agent domain for registration.

    Note: This does NOT re-derive the key. The key was already derived at startup
    using rofl_key_id (ROFL mode) or private_key (local mode). This only sets
    the domain that will be used for agent registration.

    Args:
        agent: Agent instance
        domain: Domain string to set

    Returns:
        Dictionary with update confirmation

    Raises:
        ValueError: If agent is None or domain is invalid
    """
    if not agent:
        raise ValueError("Agent not initialized")

    if not agent.config:
        raise ValueError("Configuration not loaded")

    if not domain or len(domain.strip()) == 0:
        raise ValueError("Domain cannot be empty")

    # Validate domain format (basic validation)
    domain = domain.lower().strip()

    # Check if domain contains at least one dot or is localhost
    if "." not in domain and domain != "localhost" and ":" not in domain:
        raise ValueError(
            "Invalid domain format. Must be a valid domain name or 'localhost' with optional port."
        )

    logger.info(f"Setting agent domain: {domain}")

    # Set domain in config
    # Note: This is a runtime configuration change, not persisted to .env
    agent.config.agent_domain = domain

    logger.info(f"✓ Domain set successfully: {domain}")

    # Key is NOT re-derived - it was already generated at startup
    # The address remains the same
    address_updated = False
    restart_required = False

    return {
        "success": True,
        "domain": domain,
        "address_updated": address_updated,
        "restart_required": restart_required,
    }
