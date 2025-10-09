"""ERC-8004 Utilities

Utility classes for Web3 contract interactions and common operations.
"""

from .contract_utility import (
    ABILoadError,
    ConnectionError,
    ContractUtility,
    ContractUtilityError,
)
from .agent_discovery import (
    discover_agent,
    fetch_agent_card,
    parse_agent_card,
    AgentDiscoveryError,
    AgentNotFoundError,
    AgentCardFetchError,
    AgentCardParseError,
)
from .rofl_attestation import (
    verify_rofl_attestation,
    get_rofl_metadata,
    ROFLAttestationError,
    AttestationVerificationError,
)

__all__ = [
    "ABILoadError",
    "ConnectionError",
    "ContractUtility",
    "ContractUtilityError",
    "discover_agent",
    "fetch_agent_card",
    "parse_agent_card",
    "AgentDiscoveryError",
    "AgentNotFoundError",
    "AgentCardFetchError",
    "AgentCardParseError",
    "verify_rofl_attestation",
    "get_rofl_metadata",
    "ROFLAttestationError",
    "AttestationVerificationError",
]
