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
]
