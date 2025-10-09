"""ERC-8004 Utilities

Utility classes for Web3 operations and common functions.
"""

from .web3_utility import (
    ABILoadError,
    ConnectionError,
    SigningError,
    Web3Utility,
    Web3UtilityError,
)
# Backward compatibility aliases
ContractUtility = Web3Utility
ContractUtilityError = Web3UtilityError
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
    "SigningError",
    "Web3Utility",
    "Web3UtilityError",
    "ContractUtility",  # Backward compatibility
    "ContractUtilityError",  # Backward compatibility
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
