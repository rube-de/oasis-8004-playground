"""ERC-8004 Registry Plugins

Plugin implementations for interacting with ERC-8004 on-chain registries.
"""

from .base import (
    BaseRegistryPlugin,
    ContractCallError,
    PluginError,
    PluginExecutionError,
    PluginInitializationError,
    TransactionError,
)
from .identity_registry import IdentityRegistryPlugin
from .reputation_registry import ReputationRegistryPlugin
from .validation_registry import ValidationRegistryPlugin

__all__ = [
    "BaseRegistryPlugin",
    "ContractCallError",
    "IdentityRegistryPlugin",
    "PluginError",
    "PluginExecutionError",
    "PluginInitializationError",
    "ReputationRegistryPlugin",
    "TransactionError",
    "ValidationRegistryPlugin",
]
