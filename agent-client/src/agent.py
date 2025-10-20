"""Agent orchestrator for ERC-8004 agent client.

Main agent class that coordinates configuration, contract utilities,
plugin lifecycle, registration workflow, and runtime operations.
"""

import json
import logging
import signal
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

from .config import Config
from . import api_server
from .skills import call_verified_skill, get_verified_price, VerifiedCallError
from erc8004_common.utils import AgentCardBuilder, Web3Utility, Web3UtilityError
from erc8004_common.plugins import (
    IdentityRegistryPlugin,
    ReputationRegistryPlugin,
    ValidationRegistryPlugin,
)
from erc8004_common.plugins.base import (
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
    AGENT_CARD_FILE = STATE_DIR / "agent-card.json"
    HEARTBEAT_INTERVAL = 60  # seconds

    def __init__(self):
        """Initialize agent with default state."""
        self.config: Optional[Config] = None
        self.web3_utility: Optional[Web3Utility] = None
        self.identity_plugin: Optional[IdentityRegistryPlugin] = None
        self.reputation_plugin: Optional[ReputationRegistryPlugin] = None
        self.validation_plugin: Optional[ValidationRegistryPlugin] = None
        self.agent_id: Optional[int] = None
        self.running = False
        self._shutdown_requested = False
        self.api_server_thread: Optional[threading.Thread] = None

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)

    def initialize(self) -> None:
        """Initialize agent components: config, Web3 utility, plugins.

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

            # Initialize Web3Utility
            logger.info("Initializing Web3 utility")
            self.web3_utility = Web3Utility(self.config)
            if self.web3_utility.account:
                logger.info(
                    f"Web3 utility initialized for account: "
                    f"{self.web3_utility.account.address}"
                )

            # Initialize Identity Registry plugin
            logger.info("Loading Identity Registry plugin")
            self.identity_plugin = IdentityRegistryPlugin(
                web3_utility=self.web3_utility,
                config=self.config
            )
            self.identity_plugin.initialize()
            logger.info("Identity Registry plugin initialized")

            # Initialize Reputation Registry plugin (if configured)
            if self.config.reputation_registry_address:
                logger.info("Loading Reputation Registry plugin")
                self.reputation_plugin = ReputationRegistryPlugin(
                    web3_utility=self.web3_utility,
                    config=self.config
                )
                self.reputation_plugin.initialize()
                logger.info("Reputation Registry plugin initialized")
            else:
                logger.info("Reputation Registry not configured, skipping")

            # Initialize Validation Registry plugin (if configured)
            if self.config.validation_registry_address:
                logger.info("Loading Validation Registry plugin")
                self.validation_plugin = ValidationRegistryPlugin(
                    web3_utility=self.web3_utility,
                    config=self.config
                )
                self.validation_plugin.initialize()
                logger.info("Validation Registry plugin initialized")
            else:
                logger.info("Validation Registry not configured, skipping")

            # Load persisted state
            self._load_state()

            logger.info("Agent initialization complete")

        except Web3UtilityError as e:
            raise AgentError(f"Web3 utility initialization failed: {e}") from e
        except PluginInitializationError as e:
            raise AgentError(f"Plugin initialization failed: {e}") from e
        except Exception as e:
            raise AgentError(f"Unexpected initialization error: {e}") from e

    def set_domain(self, domain: str) -> None:
        """Set agent domain for registration.

        Note: This does NOT re-derive the key. The key was already derived at startup
        using rofl_key_id (ROFL mode) or private_key (local mode). This only sets
        the domain that will be used for agent registration.

        Args:
            domain: Domain string to set

        Raises:
            AgentError: If domain is invalid
        """
        if not domain or len(domain.strip()) == 0:
            raise AgentError("Domain cannot be empty")

        domain = domain.lower().strip()

        # Basic validation
        if "." not in domain and domain != "localhost" and ":" not in domain:
            raise AgentError("Invalid domain format")

        logger.info(f"Setting agent domain: {domain}")
        self.config.agent_domain = domain
        logger.info(f"✓ Domain set successfully: {domain}")

    @property
    def has_domain(self) -> bool:
        """Check if agent domain has been set.

        Returns:
            True if domain is set, False otherwise
        """
        return (
            self.config is not None
            and self.config.agent_domain is not None
            and len(self.config.agent_domain) > 0
        )

    @property
    def is_funded(self) -> bool:
        """Check if agent wallet has sufficient balance for registration.

        Returns:
            True if wallet is funded above minimum balance, False otherwise
        """
        if not self.web3_utility or not self.web3_utility.account or not self.config:
            return False

        try:
            balance_wei = self.web3_utility.w3.eth.get_balance(
                self.web3_utility.account.address
            )
            balance_eth = self.web3_utility.w3.from_wei(balance_wei, "ether")
            min_balance = getattr(self.config, "min_balance_for_registration", 0.001)
            return float(balance_eth) >= min_balance
        except Exception:
            return False

    @property
    def is_registered(self) -> bool:
        """Check if agent is registered on-chain.

        Returns:
            True if agent has an agent_id, False otherwise
        """
        return self.agent_id is not None

    @property
    def status(self) -> str:
        """Get current agent status.

        Returns:
            Status string: uninitialized, initialized, ready, registered, operational
        """
        if not self.web3_utility or not self.config:
            return "uninitialized"

        if self.agent_id is not None:
            if self.running:
                return "operational"
            return "registered"

        if self.has_domain and self.is_funded:
            return "ready"

        return "initialized"

    def ensure_registered(self) -> int:
        """Ensure agent is registered with Identity Registry (v1.0).

        Checks if agent is already registered (from state or on-chain).
        If not registered, executes registration workflow with optional tokenURI.

        Prerequisites:
            - Domain must be set (via set_domain or config)
            - Wallet must be funded

        Returns:
            Agent ID (ERC-721 tokenId, either existing or newly assigned)

        Raises:
            AgentError: If registration fails or prerequisites not met
        """
        if not self.identity_plugin or not self.web3_utility or not self.config:
            raise AgentError("Agent not initialized. Call initialize() first.")

        # Check prerequisites (only if domain is required for this agent type)
        # Note: agent-client may not need domain for registration, but we check anyway
        if not self.has_domain:
            # For client, domain is optional for registration, but log warning
            logger.warning(
                "Domain not set. Registration will proceed without domain. "
                "Use set_domain() or POST /api/config/domain if domain is needed."
            )

        if not self.is_funded:
            raise AgentError(
                f"Insufficient balance for registration. "
                f"Fund address {self.web3_utility.account.address} with at least "
                f"{self.config.min_balance_for_registration} ETH."
            )

        # Check if we have persisted agent_id
        if self.agent_id is not None:
            logger.info(f"Agent already registered with ID: {self.agent_id}")

            # Verify on-chain (v1.0: check if agent exists)
            try:
                if self.identity_plugin.agent_exists(self.agent_id):
                    owner = self.identity_plugin.owner_of(self.agent_id)
                    token_uri = self.identity_plugin.token_uri(self.agent_id)
                    logger.info(
                        f"Verified on-chain: agentId={self.agent_id}, "
                        f"owner={owner}, tokenURI={token_uri or '(none)'}"
                    )
                    return self.agent_id
                else:
                    logger.warning(
                        f"Agent ID {self.agent_id} not found on-chain. "
                        f"Proceeding with re-registration..."
                    )
                    self.agent_id = None
            except Exception as e:
                logger.warning(
                    f"Could not verify agent {self.agent_id} on-chain: {e}. "
                    f"Proceeding with re-registration..."
                )
                self.agent_id = None

        # Execute registration (v1.0: use tokenURI-based registration)
        logger.info("No existing registration found. Starting registration workflow...")

        try:
            # Use configured tokenURI if provided, otherwise register without URI
            token_uri = self.config.agent_token_uri or ""

            if token_uri:
                logger.info(f"Registering agent with tokenURI: {token_uri}")
                self.agent_id = self.identity_plugin.register(token_uri=token_uri)
            else:
                logger.info("Registering agent without tokenURI (can be set later)")
                self.agent_id = self.identity_plugin.register()

            logger.info(
                f"✓ Registration successful! "
                f"Agent ID: {self.agent_id} (ERC-721 NFT), "
                f"Owner: {self.web3_utility.account.address if self.web3_utility.account else 'unknown'}"
            )

            # Persist state
            self._save_state()

            # Generate and save AgentCard
            self.generate_and_save_agent_card()

            return self.agent_id

        except PluginExecutionError as e:
            raise AgentError(f"Registration failed: {e}") from e
        except Exception as e:
            raise AgentError(f"Unexpected registration error: {e}") from e

    async def discover_server_agent(self, server_agent_id: int) -> None:
        """Discover agent server and log its capabilities (v1.0).

        Performs complete agent discovery workflow (v1.0 tokenURI-based):
        1. Get tokenURI from IdentityRegistry (points to AgentCard URL)
        2. Fetch AgentCard from tokenURI
        3. Parse and log agent capabilities and skills

        Args:
            server_agent_id: Agent ID of server to discover (v1.0 uses agentId, not address)

        Raises:
            AgentError: If discovery fails (agent not found, network error, etc.)

        Example:
            >>> await agent.discover_server_agent(42)
            🔍 Discovering agent ID: 42
            ✅ Discovered agent: Server Agent
               Skills (3):
               - Identity Registration: Register agent in ERC-8004 Identity Registry
        """
        from erc8004_common.utils.agent_discovery import (
            discover_agent_by_id,
            AgentDiscoveryError,
        )

        logger.info(f"🔍 Discovering agent ID: {server_agent_id}")

        try:
            # Discover agent via registry and fetch AgentCard (v1.0)
            agent_card = await discover_agent_by_id(server_agent_id, self.identity_plugin)

            # Log agent information
            logger.info(f"✅ Discovered agent: {agent_card.name}")
            logger.info(f"   Description: {agent_card.description}")
            logger.info(f"   Version: {agent_card.version}")
            logger.info(f"   Protocol: {agent_card.protocolVersion}")

            # Log blockchain registrations
            if agent_card.registrations:
                reg = agent_card.registrations[0]
                logger.info(f"   Agent ID: {reg.agentId}")
                logger.info(f"   Address: {reg.agentAddress}")

            # Log capabilities
            logger.info(f"   Capabilities:")
            logger.info(f"   - Streaming: {agent_card.capabilities.streaming}")
            logger.info(
                f"   - Push Notifications: {agent_card.capabilities.pushNotifications}"
            )
            logger.info(
                f"   - State History: {agent_card.capabilities.stateTransitionHistory}"
            )

            # Log skills
            logger.info(f"   Skills ({len(agent_card.skills)}):")
            for skill in agent_card.skills:
                logger.info(f"   - {skill.name}: {skill.description}")
                if skill.tags:
                    logger.info(f"     Tags: {', '.join(skill.tags)}")
                logger.info(
                    f"     Input: {', '.join(skill.inputModes)} | "
                    f"Output: {', '.join(skill.outputModes)}"
                )

            # Log trust models
            if agent_card.trustModels:
                logger.info(f"   Trust Models: {', '.join(agent_card.trustModels)}")

        except AgentDiscoveryError as e:
            logger.error(f"❌ Failed to discover agent: {e}")
            raise AgentError(f"Agent discovery failed: {e}") from e
        except Exception as e:
            logger.error(f"❌ Unexpected error during discovery: {e}")
            raise AgentError(f"Unexpected discovery error: {e}") from e

    async def call_skill(
        self,
        server_agent_id: int,
        endpoint: str,
        method: str = "POST",
        json_data: Optional[dict] = None,
        timeout: int = 10,
    ) -> dict:
        """Call any ROFL server skill with full trustless verification (v1.0).

        Generic method for calling any skill endpoint on a ROFL-based agent server.
        Performs complete verification chain:
        1. Server discovery via identity registry (using agent ID)
        2. HTTP endpoint call
        3. Cryptographic signature verification (EIP-191)
        4. Signer identity verification against registry
        5. ROFL TEE attestation verification

        Args:
            server_agent_id: Server's agent ID from IdentityRegistry (v1.0)
            endpoint: Skill endpoint path (e.g., "/skills/price")
            method: HTTP method (default: POST)
            json_data: Request payload (optional)
            timeout: Request timeout in seconds (default: 10)

        Returns:
            Verified data payload from server

        Raises:
            AgentError: If agent not initialized or verification fails

        Example:
            >>> # Call price skill (v1.0 - using agent ID)
            >>> price_data = await agent.call_skill(
            ...     42,  # server agent ID
            ...     "/skills/price",
            ...     json_data={"symbol": "BTC-USD"}
            ... )
            >>> print(f"Price: ${price_data['price']}")

            >>> # Call any custom skill
            >>> result = await agent.call_skill(
            ...     42,  # server agent ID
            ...     "/skills/custom",
            ...     json_data={"query": "analyze"}
            ... )

        Security:
            All responses verified through cryptographic signature,
            identity registry authorization, and ROFL TEE attestation.
            Only returns data if ALL verification checks pass.
        """
        if not self.identity_plugin or not self.web3_utility:
            raise AgentError("Agent not initialized. Call initialize() first.")

        logger.info(f"🔐 Calling verified skill: agent ID {server_agent_id}{endpoint}")

        try:
            result = await call_verified_skill(
                server_agent_id=server_agent_id,
                endpoint=endpoint,
                identity_plugin=self.identity_plugin,
                web3_utility=self.web3_utility,
                method=method,
                json_data=json_data,
                timeout=timeout,
            )

            logger.info(f"✅ Skill call successful")
            return result

        except VerifiedCallError as e:
            logger.error(f"❌ Verified skill call failed: {e}")
            raise AgentError(f"Skill call failed: {e}") from e
        except Exception as e:
            logger.error(f"❌ Unexpected error calling skill: {e}")
            raise AgentError(f"Unexpected skill error: {e}") from e

    async def get_price(
        self,
        server_agent_id: int,
        symbol: str,
    ) -> dict:
        """Get verified cryptocurrency price from ROFL server (v1.0).

        Convenience wrapper around call_skill() specifically for the price endpoint.
        Provides full trustless verification of price data.

        Args:
            server_agent_id: Server's agent ID from IdentityRegistry (v1.0)
            symbol: Trading pair symbol (e.g., "BTC-USD", "ETH-USD")

        Returns:
            Verified price data:
            {
                "symbol": "BTCUSDT",
                "price": 45000.50,
                "timestamp": "2025-10-09T12:34:56.789Z"
            }

        Raises:
            AgentError: If agent not initialized or verification fails

        Example:
            >>> price_data = await agent.get_price(42, "BTC-USD")  # v1.0: agent ID
            >>> print(f"BTC Price: ${price_data['price']:,.2f}")
            BTC Price: $45,000.50

        Security:
            Complete trustless verification:
            - Server discovery via identity registry (using agent ID)
            - Cryptographic signature verification (EIP-191)
            - Signer identity verification
            - ROFL TEE attestation check
        """
        if not self.identity_plugin or not self.web3_utility:
            raise AgentError("Agent not initialized. Call initialize() first.")

        logger.info(f"📊 Getting verified price for {symbol} from agent ID {server_agent_id}")

        try:
            result = await get_verified_price(
                server_agent_id=server_agent_id,
                symbol=symbol,
                identity_plugin=self.identity_plugin,
                web3_utility=self.web3_utility,
            )

            logger.info(
                f"✅ Price retrieved: {result['symbol']} = ${result['price']:,.2f}"
            )
            return result

        except VerifiedCallError as e:
            logger.error(f"❌ Price fetch failed: {e}")
            raise AgentError(f"Price fetch failed: {e}") from e
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching price: {e}")
            raise AgentError(f"Unexpected price error: {e}") from e

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

        # Start API server in background thread
        self._start_api_server()

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

            if self.web3_utility:
                logger.debug("Cleaning up Web3 utility")

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

        # Check Web3 utility
        if self.web3_utility:
            try:
                connected = self.web3_utility.w3.is_connected()
                health["components"]["web3_utility"] = {
                    "status": "ok" if connected else "error",
                    "connected": connected,
                    "chain_id": self.web3_utility.w3.eth.chain_id if connected else None
                }
            except Exception as e:
                health["components"]["web3_utility"] = {
                    "status": "error",
                    "error": str(e)
                }
                health["healthy"] = False
        else:
            health["components"]["web3_utility"] = {
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

        # Check API server
        health["components"]["api_server"] = {
            "status": "ok" if self.api_server_thread and self.api_server_thread.is_alive() else "stopped",
            "running": self.api_server_thread.is_alive() if self.api_server_thread else False,
            "port": self.config.api_port if self.config else None
        }

        # Overall health
        if not all(
            comp["status"] in ["ok", "warning", "stopped"]
            for comp in health["components"].values()
        ):
            health["healthy"] = False

        return health

    def generate_and_save_agent_card(self) -> None:
        """Generate A2A and ERC-8004 compliant AgentCard and save to disk.

        Creates AgentCard with current agent state including registration data,
        CAIP-10 formatted address, and cryptographic signature proving ownership.
        Saves to agent-card.json in data directory.

        Raises:
            AgentError: If AgentCard generation or save fails
        """
        if not self.agent_id:
            raise AgentError("Cannot generate AgentCard: agent not registered")

        if not self.config:
            raise AgentError("Cannot generate AgentCard: config not loaded")

        if not self.web3_utility or not self.web3_utility.account:
            raise AgentError("Cannot generate AgentCard: Web3 utility not initialized")

        try:
            # Get chain ID from Web3 connection
            chain_id = self.web3_utility.w3.eth.chain_id

            # Build AgentCard using builder pattern with agent_config.json
            builder = AgentCardBuilder(
                agent_id=self.agent_id,
                agent_address=self.web3_utility.account.address,
                agent_domain=self.config.agent_domain,
                chain_id=chain_id,
                account=self.web3_utility.account,
            )

            # Override trust models and infrastructure for local mode
            if self.config.use_local_mode:
                logger.debug("Local mode detected, disabling TEE trust model")
                builder.override_trust_models(["feedback"])
                builder.override_infrastructure(
                    hosting="local",
                    tee_enabled=False,
                    attestation_provider=None,
                )

            # Build final AgentCard from config + runtime state
            agent_card = builder.build()

            # Ensure data directory exists
            self.STATE_DIR.mkdir(parents=True, exist_ok=True)

            # Save AgentCard to JSON file
            with open(self.AGENT_CARD_FILE, "w") as f:
                json.dump(agent_card.to_dict(), f, indent=2)

            logger.info(f"✓ AgentCard saved to {self.AGENT_CARD_FILE}")
            logger.debug(
                f"AgentCard: protocolVersion={agent_card.protocolVersion}, "
                f"trustModels={agent_card.trustModels}"
            )

        except Exception as e:
            raise AgentError(f"Failed to generate AgentCard: {e}") from e

    def _start_api_server(self) -> None:
        """Start FastAPI server in background thread for AgentCard hosting and lifecycle management.

        Starts API server on configured port to serve:
        - /.well-known/agent-card.json (RFC 8615 compliant)
        - /health (health check)
        - /api/v1/agent (agent info)
        - /api/wallet (wallet info for funding)
        - /api/status (agent status)
        - /api/register (manual registration)
        - /api/config (configuration)
        - /api/config/domain (set domain)

        Raises:
            AgentError: If API server fails to start
        """
        if not self.config:
            raise AgentError("Cannot start API server: config not loaded")

        try:
            port = self.config.api_port

            logger.info(f"Starting API server on port {port}")

            # Create thread for API server (pass agent for lifecycle management)
            self.api_server_thread = threading.Thread(
                target=api_server.run_server,
                args=("0.0.0.0", port, self),
                daemon=True,
                name="api-server"
            )

            self.api_server_thread.start()

            logger.info(
                f"✓ API server started successfully on http://0.0.0.0:{port}"
            )
            logger.info(
                f"  AgentCard: http://localhost:{port}/.well-known/agent-card.json"
            )
            logger.info(
                f"  Health: http://localhost:{port}/health"
            )
            logger.info(
                f"  Lifecycle: http://localhost:{port}/api/wallet, /api/status, /api/register"
            )

        except Exception as e:
            raise AgentError(f"Failed to start API server: {e}") from e

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
        """Persist agent state to disk (v1.0: includes tokenURI).

        Raises:
            StateError: If state persistence fails
        """
        if not self.config or not self.web3_utility:
            raise StateError("Cannot save state: agent not fully initialized")

        try:
            # Ensure state directory exists
            self.STATE_DIR.mkdir(parents=True, exist_ok=True)

            account_address = (
                self.web3_utility.account.address
                if self.web3_utility.account
                else None
            )

            # Get tokenURI if agent is registered (v1.0)
            token_uri = None
            if self.agent_id and self.identity_plugin:
                try:
                    token_uri = self.identity_plugin.token_uri(self.agent_id)
                except Exception:
                    pass  # Agent may not have tokenURI set yet

            state = {
                "agent_id": self.agent_id,
                "token_uri": token_uri,
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
