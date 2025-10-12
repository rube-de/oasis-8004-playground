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
from .agent_discovery import (
    discover_agent_by_id,
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
from .address import (
    extract_address_from_caip10,
    parse_caip10,
    to_caip10,
    AddressFormatError,
)

__all__ = [
    "ABILoadError",
    "ConnectionError",
    "SigningError",
    "Web3Utility",
    "Web3UtilityError",
    "discover_agent_by_id",
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
    "extract_address_from_caip10",
    "parse_caip10",
    "to_caip10",
    "AddressFormatError",
]
