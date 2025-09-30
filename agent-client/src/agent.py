"""Agent orchestrator for ERC-8004 agent client.

Main agent class that coordinates configuration, contract utilities,
plugin lifecycle, registration workflow, and runtime operations.
"""

import json
import logging
import signal
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .config import Config
from .utils.contract_utility import ContractUtility, ContractUtilityError
from .plugins.identity_registry import IdentityRegistryPlugin
from .plugins.base import (
    PluginInitializationError,
    PluginExecutionError,
)

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for Agent errors."""
    pass


class StateError(AgentError):
    """Raised when state persistence operations fail."""
    pass


class Agent:
    """Main agent orchestrator for ERC-8004 operations.

    Coordinates configuration loading, contract interactions, plugin lifecycle,
    registration workflow, and long-running operations. Handles state persistence
    and graceful shutdown.

    Example:
        >>> agent = Agent()
        >>> agent.initialize()
        >>> agent.ensure_registered()
        >>> agent.run()
    """

    STATE_DIR = Path("/app/data")
    STATE_FILE = STATE_DIR / "agent_state.json"
    HEARTBEAT_INTERVAL = 60  # seconds

    def __init__(self):
        """Initialize agent with default state."""
        self.config: Optional[Config] = None
        self.contract_utility: Optional[ContractUtility] = None
        self.identity_plugin: Optional[IdentityRegistryPlugin] = None
        self.agent_id: Optional[int] = None
        self.running = False
        self._shutdown_requested = False

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)

    def initialize(self) -> None:
        """Initialize agent components: config, contract utility, plugins.

        Raises:
            AgentError: If initialization fails
        """
        logger.info("Initializing agent...")

        try:
            # Load configuration
            logger.info("Loading configuration from environment")
            self.config = Config()
            logger.info(
                f"Configuration loaded: "
                f"RPC={self.config.rpc_url}, "
                f"domain={self.config.agent_domain}"
            )

            # Initialize ContractUtility
            logger.info("Initializing contract utility")
            self.contract_utility = ContractUtility(self.config)
            if self.contract_utility.account:
                logger.info(
                    f"Contract utility initialized for account: "
                    f"{self.contract_utility.account.address}"
                )

            # Initialize Identity Registry plugin
            logger.info("Loading Identity Registry plugin")
            self.identity_plugin = IdentityRegistryPlugin(
                contract_utility=self.contract_utility,
                config=self.config
            )
            self.identity_plugin.initialize()
            logger.info("Identity Registry plugin initialized")

            # Load persisted state
            self._load_state()

            logger.info("Agent initialization complete")

        except ContractUtilityError as e:
            raise AgentError(f"Contract utility initialization failed: {e}") from e
        except PluginInitializationError as e:
            raise AgentError(f"Plugin initialization failed: {e}") from e
        except Exception as e:
            raise AgentError(f"Unexpected initialization error: {e}") from e

    def ensure_registered(self) -> int:
        """Ensure agent is registered with Identity Registry.

        Checks if agent is already registered (from state or on-chain).
        If not registered, executes registration workflow.

        Returns:
            Agent ID (either existing or newly assigned)

        Raises:
            AgentError: If registration fails
        """
        if not self.identity_plugin or not self.contract_utility or not self.config:
            raise AgentError("Agent not initialized. Call initialize() first.")

        # Check if we have persisted agent_id
        if self.agent_id is not None:
            logger.info(f"Agent already registered with ID: {self.agent_id}")

            # Verify on-chain
            try:
                agent_info = self.identity_plugin.get_agent(self.agent_id)
                logger.info(
                    f"Verified on-chain: "
                    f"domain={agent_info['agentDomain']}, "
                    f"address={agent_info['agentAddress']}"
                )
                return self.agent_id
            except Exception as e:
                logger.warning(
                    f"Could not verify agent {self.agent_id} on-chain: {e}. "
                    f"Proceeding with re-registration..."
                )
                self.agent_id = None

        # Check if address is already registered
        try:
            if self.contract_utility.account:
                agent_address = self.contract_utility.account.address
                existing = self.identity_plugin.resolve_by_address(agent_address)

                if existing:
                    agent_id = existing["agentId"]
                    logger.info(
                        f"Agent already registered on-chain with ID: {agent_id}"
                    )
                    self.agent_id = agent_id
                    self._save_state()
                    return agent_id
        except Exception:
            # Not found, proceed with registration
            pass

        # Execute registration
        logger.info("No existing registration found. Starting registration workflow...")

        try:
            self.agent_id = self.identity_plugin.register()

            logger.info(
                f"✓ Registration successful! "
                f"Agent ID: {self.agent_id}, "
                f"Domain: {self.config.agent_domain}, "
                f"Address: {self.contract_utility.account.address if self.contract_utility.account else 'unknown'}"
            )

            # Persist state
            self._save_state()

            return self.agent_id

        except PluginExecutionError as e:
            raise AgentError(f"Registration failed: {e}") from e
        except Exception as e:
            raise AgentError(f"Unexpected registration error: {e}") from e

    def run(self) -> None:
        """Run main agent event loop.

        Enters long-running event loop that keeps the agent operational.
        Logs periodic heartbeat and status messages.
        Handles graceful shutdown on signal.
        """
        if not self.agent_id:
            raise AgentError(
                "Agent not registered. Call ensure_registered() first."
            )

        logger.info(
            f"🚀 Agent {self.agent_id} operational and running..."
        )
        logger.info(
            f"Heartbeat interval: {self.HEARTBEAT_INTERVAL}s"
        )

        self.running = True
        last_heartbeat = time.time()

        try:
            while self.running and not self._shutdown_requested:
                current_time = time.time()

                # Periodic heartbeat
                if current_time - last_heartbeat >= self.HEARTBEAT_INTERVAL:
                    self._log_heartbeat()
                    last_heartbeat = current_time

                # Sleep briefly to avoid busy-waiting
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Gracefully shutdown agent and cleanup resources."""
        if not self.running:
            return

        logger.info("Shutting down agent...")
        self.running = False

        # Cleanup resources
        try:
            if self.identity_plugin:
                logger.debug("Cleaning up Identity Registry plugin")

            if self.contract_utility:
                logger.debug("Cleaning up contract utility")

            logger.info("✓ Agent shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on agent components.

        Returns:
            Dictionary with health status of each component
        """
        health = {
            "healthy": True,
            "components": {}
        }

        # Check configuration
        health["components"]["config"] = {
            "status": "ok" if self.config else "error",
            "loaded": self.config is not None
        }

        # Check contract utility
        if self.contract_utility:
            try:
                connected = self.contract_utility.w3.is_connected()
                health["components"]["contract_utility"] = {
                    "status": "ok" if connected else "error",
                    "connected": connected,
                    "chain_id": self.contract_utility.w3.eth.chain_id if connected else None
                }
            except Exception as e:
                health["components"]["contract_utility"] = {
                    "status": "error",
                    "error": str(e)
                }
                health["healthy"] = False
        else:
            health["components"]["contract_utility"] = {
                "status": "error",
                "loaded": False
            }
            health["healthy"] = False

        # Check identity plugin
        health["components"]["identity_plugin"] = {
            "status": "ok" if self.identity_plugin and self.identity_plugin.is_initialized else "error",
            "initialized": self.identity_plugin.is_initialized if self.identity_plugin else False
        }

        # Check registration status
        health["components"]["registration"] = {
            "status": "ok" if self.agent_id else "warning",
            "agent_id": self.agent_id,
            "registered": self.agent_id is not None
        }

        # Overall health
        if not all(
            comp["status"] in ["ok", "warning"]
            for comp in health["components"].values()
        ):
            health["healthy"] = False

        return health

    def _handle_shutdown_signal(self, signum: int, _frame: object) -> None:
        """Handle shutdown signals (SIGTERM, SIGINT)."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} signal")
        self._shutdown_requested = True

    def _log_heartbeat(self) -> None:
        """Log periodic heartbeat with status."""
        if self.config:
            logger.info(
                f"💓 Heartbeat: Agent {self.agent_id} running, "
                f"domain={self.config.agent_domain}"
            )

    def _load_state(self) -> None:
        """Load persisted agent state from disk.

        Raises:
            StateError: If state loading fails critically
        """
        try:
            if not self.STATE_FILE.exists():
                logger.debug(f"No state file found at {self.STATE_FILE}")
                return

            with open(self.STATE_FILE, "r") as f:
                state = json.load(f)

            self.agent_id = state.get("agent_id")

            if self.agent_id:
                logger.info(f"Loaded agent state: agent_id={self.agent_id}")

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse state file: {e}. Starting fresh.")
        except Exception as e:
            logger.warning(f"Failed to load state: {e}. Starting fresh.")

    def _save_state(self) -> None:
        """Persist agent state to disk.

        Raises:
            StateError: If state persistence fails
        """
        if not self.config or not self.contract_utility:
            raise StateError("Cannot save state: agent not fully initialized")

        try:
            # Ensure state directory exists
            self.STATE_DIR.mkdir(parents=True, exist_ok=True)

            account_address = (
                self.contract_utility.account.address
                if self.contract_utility.account
                else None
            )

            state = {
                "agent_id": self.agent_id,
                "domain": self.config.agent_domain,
                "address": account_address,
                "timestamp": time.time()
            }

            # Write atomically via temporary file
            temp_file = self.STATE_FILE.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(state, f, indent=2)

            temp_file.replace(self.STATE_FILE)

            logger.debug(f"Agent state saved to {self.STATE_FILE}")

        except Exception as e:
            raise StateError(f"Failed to save state: {e}") from e
