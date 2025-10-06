"""ERC-8004 Common Infrastructure Package

Shared components for ERC-8004 agent implementations including:
- Registry plugins (Identity, Reputation, Validation)
- Contract utilities for Web3 interactions
- Base configuration classes
- AgentCard generation (A2A Protocol v0.3.0 compliant)
"""

from .utils.agent_card import (
    AgentCard,
    generate_agent_card,
    sign_agent_registration,
    format_caip10_address,
    Provider,
    Extension,
    Capabilities,
    Skill,
    Registration,
)

__version__ = "0.1.0"

__all__ = [
    "AgentCard",
    "generate_agent_card",
    "sign_agent_registration",
    "format_caip10_address",
    "Provider",
    "Extension",
    "Capabilities",
    "Skill",
    "Registration",
]
