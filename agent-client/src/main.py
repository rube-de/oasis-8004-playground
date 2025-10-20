"""Main entry point for ERC-8004 agent client.

Handles application startup, logging configuration, registration workflow,
and long-running agent operations. Provides proper error handling and
graceful shutdown.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import NoReturn

from .agent import Agent, AgentError
from .config import Config


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application.

    Sets up logging with timestamps, log levels, and proper formatting.
    Logs are output to stdout for Docker container compatibility.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Set specific logger levels
    logging.getLogger("web3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def display_banner() -> None:
    """Display application banner on startup."""
    print("=" * 60)
    print("  ERC-8004 Agent Client")
    print("  Identity Registry Integration")
    print("=" * 60)
    print()


def display_startup_success(agent: Agent) -> None:
    """Display successful startup information.

    Args:
        agent: Initialized and registered agent instance
    """
    print()
    print("✓" + "=" * 59)
    print("  AGENT REGISTRATION SUCCESSFUL")
    print("=" * 60)
    print(f"  Agent ID:      {agent.agent_id}")
    if agent.config:
        print(f"  Domain:        {agent.config.agent_domain}")
    if agent.web3_utility and agent.web3_utility.account:
        print(f"  Address:       {agent.web3_utility.account.address}")
    print("=" * 60)
    print()


def display_error(error: Exception, context: str = "") -> None:
    """Display error information with helpful suggestions.

    Args:
        error: The exception that occurred
        context: Additional context about when the error occurred
    """
    print()
    print("✗" + "=" * 59)
    print("  ERROR")
    if context:
        print(f"  Context: {context}")
    print("=" * 60)
    print(f"  {type(error).__name__}: {error}")
    print("=" * 60)
    print()
    print("Suggestions:")

    # Provide context-specific suggestions
    error_msg = str(error).lower()

    if "connection" in error_msg or "rpc" in error_msg:
        print("  • Verify RPC_URL is correct and the node is running")
        print("  • Check network connectivity")
        print("  • Ensure firewall allows connections to RPC endpoint")
    elif "private key" in error_msg or "signing" in error_msg:
        print("  • Verify PRIVATE_KEY is correct (without 0x prefix)")
        print("  • Ensure private key has sufficient permissions")
        print("  • Check that the key matches the expected address")
    elif "contract" in error_msg or "abi" in error_msg:
        print("  • Verify IDENTITY_REGISTRY_ADDRESS is correct")
        print("  • Ensure contract is deployed at the specified address")
        print("  • Check that ABI files are present in /app/abis/")
    elif "gas" in error_msg:
        print("  • Ensure account has sufficient funds for gas")
        print("  • Try increasing GAS_MULTIPLIER in configuration")
        print("  • Check network congestion and gas prices")
    elif "domain" in error_msg:
        print("  • Verify AGENT_DOMAIN is RFC 8615 compliant")
        print("  • Ensure domain format is correct")
    else:
        print("  • Check all environment variables in .env file")
        print("  • Review logs above for more details")
        print("  • Ensure all prerequisites are met")

    print()


async def test_skills(agent: Agent, server_agent_id: int) -> None:
    """Test skill verification with ROFL server (v1.0).

    Demonstrates trustless skill calling with complete verification chain:
    - Generic skill call (call_skill)
    - Convenience wrapper (get_price)

    Args:
        agent: Initialized agent instance
        server_agent_id: Server's agent ID from IdentityRegistry (v1.0)

    Raises:
        AgentError: If skill tests fail
    """
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Testing trustless skill verification...")
    logger.info("=" * 60)

    try:
        # Test 1: Get price using convenience method
        logger.info("\n📊 Test 1: Get verified price (BTC-USD)")
        logger.info("-" * 60)

        price_data = await agent.get_price(
            server_agent_id=server_agent_id,
            symbol="BTC-USD"
        )

        logger.info(f"✅ Price verification successful!")
        logger.info(f"   Symbol: {price_data['symbol']}")
        logger.info(f"   Price: ${price_data['price']:,.2f}")
        logger.info(f"   Timestamp: {price_data['timestamp']}")

        # Test 2: Call price skill using generic method
        logger.info("\n🔐 Test 2: Generic skill call (ETH-USD)")
        logger.info("-" * 60)

        eth_data = await agent.call_skill(
            server_agent_id=server_agent_id,
            endpoint="/skills/price",
            method="POST",
            json_data={"symbol": "ETH-USD"}
        )

        logger.info(f"✅ Generic skill call successful!")
        logger.info(f"   Symbol: {eth_data['symbol']}")
        logger.info(f"   Price: ${eth_data['price']:,.2f}")
        logger.info(f"   Timestamp: {eth_data['timestamp']}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ All skill tests passed!")
        logger.info("=" * 60 + "\n")

    except AgentError as e:
        logger.error(f"\n❌ Skill test failed: {e}")
        logger.info("\nNote: Skill tests require:")
        logger.info("  • Agent server running and registered")
        logger.info("  • Valid AGENT_SERVER_ID in .env (v1.0)")
        logger.info("  • Server implements /skills/price endpoint")
        logger.info("  • Server has ROFL attestation")
        raise


def main() -> NoReturn:
    """Main application entry point.

    Orchestrates the complete agent lifecycle:
    1. Load configuration
    2. Setup logging
    3. Initialize agent
    4. Ensure registration (check existing or register new)
    5. Run main event loop

    Exits with appropriate status codes:
    - 0: Successful execution
    - 1: Error occurred
    """
    logger = logging.getLogger(__name__)
    agent: Agent | None = None

    try:
        # Load configuration first to get log level
        config = Config()

        # Setup logging with configured level
        setup_logging(config.log_level)

        # Display banner
        display_banner()

        logger.info("Starting ERC-8004 Agent Client")
        logger.info(f"Configuration loaded from environment")
        logger.debug(f"RPC URL: {config.rpc_url}")
        logger.debug(f"Agent Domain: {config.agent_domain}")
        logger.debug(f"Identity Registry: {config.identity_registry_address}")

        # Log ROFL environment details (if running in ROFL mode)
        if not config.use_local_mode:
            logger.info(f"🔌 Proxy Host (PROXY_HOST): {config.proxy_host or 'not set'}")

        # Initialize agent
        logger.info("Initializing agent...")
        agent = Agent()
        agent.initialize()
        logger.info("Agent initialized successfully")

        # Check if domain is set in config
        if agent.config.agent_domain:
            logger.info(f"Domain configured: {agent.config.agent_domain}")

            # Legacy behavior: if domain is set, attempt registration
            # This maintains backward compatibility for existing deployments
            logger.info("Checking registration status...")
            try:
                agent_id = agent.ensure_registered()
                logger.info(f"Agent operational with ID: {agent_id}")
                display_startup_success(agent)
            except AgentError as e:
                logger.warning(f"Auto-registration failed: {e}")
                logger.info("Agent will start without registration. Use API endpoints to complete setup:")
                logger.info("  1. Fund wallet: GET /api/wallet")
                logger.info("  2. Check status: GET /api/status")
                logger.info("  3. Register: POST /api/register")
        else:
            logger.info("No domain configured - starting in unregistered mode")
            logger.info("Agent will start with lifecycle API endpoints available:")
            logger.info("  1. Set domain: POST /api/config/domain (optional for client)")
            logger.info("  2. Get wallet address: GET /api/wallet")
            logger.info("  3. Fund wallet externally")
            logger.info("  4. Check status: GET /api/status")
            logger.info("  5. Register: POST /api/register")

        # Optional: Discover agent-server if configured (v1.0)
        if config.agent_server_id and agent.agent_id:
            logger.info(f"Agent server ID configured: {config.agent_server_id}, initiating discovery...")
            try:
                asyncio.run(agent.discover_server_agent(config.agent_server_id))

                # Test skills after successful discovery
                logger.info(f"Testing skills with discovered server agent ID {config.agent_server_id}...")
                asyncio.run(test_skills(agent, config.agent_server_id))

            except AgentError as e:
                logger.warning(f"Agent discovery or skill test failed (non-fatal): {e}")
                logger.info("Continuing with normal operations...")
        else:
            if config.agent_server_id and not agent.agent_id:
                logger.info("Agent server ID configured but client not registered yet. Skipping discovery.")
            else:
                logger.info("No agent server ID configured (AGENT_SERVER_ID), skipping discovery and skill tests")

        # Run main event loop
        logger.info("Starting main event loop...")
        agent.run()

        # Graceful shutdown (should not reach here normally)
        logger.info("Agent stopped")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        if agent:
            agent.shutdown()
        sys.exit(0)

    except AgentError as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        display_error(e, "Agent operation failed")
        if agent:
            agent.shutdown()
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        display_error(e, "Unexpected error occurred")
        if agent:
            agent.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
