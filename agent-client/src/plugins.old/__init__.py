"""ERC-8004 Registry Plugins.

Provides plugin interfaces for interacting with ERC-8004 registries:
    - IdentityRegistry: Agent registration and identity management
    - ReputationRegistry: Feedback and reputation tracking (future)
    - ValidationRegistry: Task validation mechanisms (future)

Example:
    >>> from plugins import IdentityRegistryPlugin
    >>> plugin = IdentityRegistryPlugin(contract_utility, config)
    >>> plugin.initialize()
    >>> agent_id = plugin.register()
"""

from .base import (
    BaseRegistryPlugin,
    PluginError,
    PluginInitializationError,
    TransactionError,
    ContractCallError,
)
from .identity_registry import IdentityRegistryPlugin

__all__ = [
    "BaseRegistryPlugin",
    "PluginError",
    "PluginInitializationError",
    "TransactionError",
    "ContractCallError",
    "IdentityRegistryPlugin",
]
