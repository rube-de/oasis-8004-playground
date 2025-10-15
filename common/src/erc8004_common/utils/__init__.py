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
    fetch_registration_json,
    extract_agent_card_url,
    fetch_agent_card_from_url,
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
from .rofl_key_manager import (
    RoflKeyManager,
    RoflKeyManagerError,
)
from .agent_metadata import (
    get_chain_name,
    format_caip10_address,
    build_erc8004_registration,
    build_erc8004_registration_with_config,
    CHAIN_NAMES,
)

__all__ = [
    "ABILoadError",
    "ConnectionError",
    "SigningError",
    "Web3Utility",
    "Web3UtilityError",
    "discover_agent_by_id",
    "fetch_registration_json",
    "extract_agent_card_url",
    "fetch_agent_card_from_url",
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
    "RoflKeyManager",
    "RoflKeyManagerError",
    "get_chain_name",
    "format_caip10_address",
    "build_erc8004_registration",
    "build_erc8004_registration_with_config",
    "CHAIN_NAMES",
]
