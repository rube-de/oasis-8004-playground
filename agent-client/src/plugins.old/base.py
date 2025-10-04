"""Base plugin interface for ERC-8004 registry interactions."""

from abc import ABC, abstractmethod
import logging
from typing import Optional, Any
from web3.contract import Contract

logger = logging.getLogger(__name__)


class PluginError(Exception):
    """Base exception for all plugin errors."""
    pass


class PluginInitializationError(PluginError):
    """Raised when plugin initialization fails."""
    pass


class PluginExecutionError(PluginError):
    """Raised when plugin execution encounters an error."""
    pass


class TransactionError(PluginError):
    """Raised when transaction submission or confirmation fails."""
    pass


class ContractCallError(PluginError):
    """Raised when contract call (read operation) fails."""
    pass


class BaseRegistryPlugin(ABC):
    """Abstract base class for registry plugins.

    Subclasses must implement: name, contract_address, initialize().
    Each plugin defines its own operation methods (e.g., register(), submit_feedback()).
    """

    def __init__(self, contract_utility: Any, config: Any):
        """Initialize plugin with ContractUtility and Config."""
        self.contract_utility = contract_utility
        self.config = config
        self._contract: Optional[Contract] = None
        self._initialized = False

        logger.debug(f"Plugin instantiated: {self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name for logging (e.g., 'IdentityRegistry')."""
        pass

    @property
    @abstractmethod
    def contract_address(self) -> str:
        """Registry contract address."""
        pass

    @property
    def is_initialized(self) -> bool:
        """True if initialize() completed successfully."""
        return self._initialized

    @property
    def contract(self) -> Contract:
        """Web3 contract instance. Raises PluginInitializationError if not initialized."""
        if not self._initialized or self._contract is None:
            raise PluginInitializationError(
                f"{self.name} plugin not initialized. Call initialize() first."
            )
        return self._contract

    @abstractmethod
    def initialize(self) -> None:
        """Load contract and set self._initialized = True."""
        pass

    def _ensure_initialized(self) -> None:
        """Verify plugin initialized. Raises PluginInitializationError if not."""
        if not self._initialized:
            raise PluginInitializationError(
                f"{self.name} plugin not initialized. Call initialize() first."
            )

    def __repr__(self) -> str:
        """String representation for debugging."""
        init_status = "initialized" if self._initialized else "not initialized"
        return f"<{self.name} plugin ({init_status})>"
