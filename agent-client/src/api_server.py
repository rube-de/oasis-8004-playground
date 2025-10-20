"""FastAPI server for serving AgentCard and agent API endpoints.

RFC 8615 compliant AgentCard hosting at /.well-known/agent-card.json
with proper CORS support for cross-origin agent discovery.
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from erc8004_common.api import lifecycle, config_handlers
from erc8004_common.api.models import (
    WalletResponse,
    StatusResponse,
    RegisterResponse,
    ConfigResponse,
    DomainConfigRequest,
    DomainConfigResponse,
)

logger = logging.getLogger(__name__)


# AgentCard file path
AGENT_CARD_PATH = Path("/app/data/agent-card.json")
AGENT_STATE_PATH = Path("/app/data/agent_state.json")


def create_app(agent: Any = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        agent: Agent instance for lifecycle management (optional)

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="ERC-8004 Agent Client API",
        description="A2A Protocol and ERC-8004 compliant agent client with lifecycle management",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Store agent for endpoint access
    app.state.agent = agent

    # CORS middleware for agent discovery
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for agent discovery
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "OPTIONS"],
        allow_headers=["*"],
        max_age=600,  # Cache preflight requests for 10 minutes
    )

    # Endpoints
    @app.get(
        "/.well-known/agent-card.json",
        tags=["RFC 8615"],
        summary="Get AgentCard",
        description="RFC 8615 compliant AgentCard endpoint per A2A Protocol v0.3.0",
    )
    async def get_agent_card() -> JSONResponse:
        """Serve A2A Protocol v0.3.0 and ERC-8004 compliant AgentCard.

        Returns AgentCard with:
        - A2A Protocol v0.3.0 fields (protocolVersion, capabilities, skills)
        - ERC-8004 extensions (registrations with CAIP-10 addresses, trustModels)
        - Cryptographic signatures proving address ownership

        Returns:
            JSONResponse with AgentCard data

        Raises:
            HTTPException: 404 if AgentCard file not found
            HTTPException: 500 if AgentCard file is invalid
        """
        if not AGENT_CARD_PATH.exists():
            logger.error(f"AgentCard not found at {AGENT_CARD_PATH}")
            raise HTTPException(
                status_code=404,
                detail="AgentCard not found. Agent may not be registered yet.",
            )

        try:
            with open(AGENT_CARD_PATH) as f:
                agent_card = json.load(f)

            return JSONResponse(
                content=agent_card,
                headers={
                    "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
                    "Content-Type": "application/json",
                },
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid AgentCard JSON: {e}")
            raise HTTPException(
                status_code=500, detail="AgentCard file contains invalid JSON"
            )
        except Exception as e:
            logger.error(f"Error reading AgentCard: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @app.get("/health", tags=["Health"], summary="Health check")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for container orchestration.

        Returns:
            Health status dict
        """
        return {"status": "healthy"}

    @app.get(
        "/api/v1/agent",
        tags=["Agent API"],
        summary="Get agent info",
        description="Get agent registration information",
    )
    async def get_agent_info() -> JSONResponse:
        """Get agent registration information from state file.

        Returns:
            Agent info including ID, domain, and address

        Raises:
            HTTPException: 404 if agent state not found
            HTTPException: 500 if state file is invalid
        """
        if not AGENT_STATE_PATH.exists():
            raise HTTPException(
                status_code=404,
                detail="Agent state not found. Agent may not be initialized.",
            )

        try:
            with open(AGENT_STATE_PATH) as f:
                state = json.load(f)

            return JSONResponse(
                content={
                    "agent_id": state.get("agent_id"),
                    "domain": state.get("domain"),
                    "address": state.get("address"),
                    "registered_at": state.get("timestamp"),
                },
                headers={"Cache-Control": "public, max-age=60"},
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid state JSON: {e}")
            raise HTTPException(status_code=500, detail="State file contains invalid JSON")
        except Exception as e:
            logger.error(f"Error reading agent state: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    # Lifecycle Management Endpoints
    @app.get(
        "/api/wallet",
        tags=["Lifecycle"],
        summary="Get wallet information",
        description="Get agent wallet address, balance, and funding status for ROFL deployment",
        response_model=WalletResponse,
    )
    async def get_wallet() -> WalletResponse:
        """Get wallet address and balance for funding.

        Returns agent's Ethereum address (derived from ROFL_KEY_ID at startup)
        along with current balance and funding status. Use this endpoint to get
        the address for funding before registration.

        Returns:
            Wallet information including address, balance, and funding status

        Raises:
            HTTPException: 500 if agent not initialized
        """
        if not app.state.agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")

        try:
            wallet_info = lifecycle.get_wallet_info(
                agent=app.state.agent,
                web3_utility=app.state.agent.web3_utility,
                config=app.state.agent.config,
            )
            return WalletResponse(**wallet_info)
        except Exception as e:
            logger.error(f"Failed to get wallet info: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(
        "/api/status",
        tags=["Lifecycle"],
        summary="Get agent status",
        description="Get comprehensive agent status including registration, funding, and operational state",
        response_model=StatusResponse,
    )
    async def get_status() -> StatusResponse:
        """Get agent registration and operational status.

        Returns current state: initialized, ready, registered, or operational.
        Use this to check prerequisites before registration.

        Returns:
            Comprehensive status information

        Raises:
            HTTPException: 500 if agent not initialized
        """
        if not app.state.agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")

        try:
            status_info = lifecycle.get_status(agent=app.state.agent)
            return StatusResponse(**status_info)
        except Exception as e:
            logger.error(f"Failed to get status: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(
        "/api/register",
        tags=["Lifecycle"],
        summary="Trigger agent registration",
        description="Manually trigger on-chain agent registration (requires wallet funded)",
        response_model=RegisterResponse,
    )
    async def register() -> RegisterResponse:
        """Trigger agent registration on-chain.

        Prerequisites:
            - Wallet must be funded with at least min_balance_for_registration
            - Domain is optional for client registration

        Returns:
            Registration result with agent_id and transaction hash

        Raises:
            HTTPException: 400 if prerequisites not met, 500 if registration fails
        """
        if not app.state.agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")

        try:
            result = await lifecycle.register_agent(agent=app.state.agent)
            return RegisterResponse(**result)
        except ValueError as e:
            # Prerequisites not met (insufficient balance, etc.)
            logger.warning(f"Registration prerequisites not met: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Configuration Management Endpoints
    @app.get(
        "/api/config",
        tags=["Configuration"],
        summary="Get agent configuration",
        description="Get current agent configuration including domain, ROFL settings, and registry addresses",
        response_model=ConfigResponse,
    )
    async def get_config() -> ConfigResponse:
        """Get current agent configuration.

        Returns:
            Configuration including domain, ROFL settings, chain info, and registries

        Raises:
            HTTPException: 500 if agent not initialized
        """
        if not app.state.agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")

        try:
            config_info = config_handlers.get_config(agent=app.state.agent)
            return ConfigResponse(**config_info)
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post(
        "/api/config/domain",
        tags=["Configuration"],
        summary="Set agent domain",
        description="Set agent domain (optional for client, does NOT re-derive key)",
        response_model=DomainConfigResponse,
    )
    async def set_domain(request: DomainConfigRequest) -> DomainConfigResponse:
        """Set agent domain.

        Note: This does NOT re-derive the key. The key was already derived at startup
        using ROFL_KEY_ID. This only sets the domain for AgentCard hosting and A2A protocol.
        Domain is optional for client agents.

        Args:
            request: Domain configuration request

        Returns:
            Domain update confirmation

        Raises:
            HTTPException: 400 if domain invalid, 500 if update fails
        """
        if not app.state.agent:
            raise HTTPException(status_code=500, detail="Agent not initialized")

        try:
            result = await config_handlers.set_domain(
                agent=app.state.agent,
                domain=request.domain,
            )
            return DomainConfigResponse(**result)
        except ValueError as e:
            logger.warning(f"Invalid domain: {e}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to set domain: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get(
        "/",
        tags=["Info"],
        summary="API info",
        description="Get API server information",
    )
    async def root() -> dict[str, Any]:
        """Root endpoint with API information.

        Returns:
            API metadata and available endpoints
        """
        return {
            "name": "ERC-8004 Agent Client API",
            "version": "1.0.0",
            "protocol": "A2A v0.3.0",
            "endpoints": {
                "agent_card": "/.well-known/agent-card.json",
                "agent_info": "/api/v1/agent",
                "health": "/health",
                "docs": "/api/docs",
                # Lifecycle endpoints
                "wallet": "/api/wallet",
                "status": "/api/status",
                "register": "/api/register",
                "config": "/api/config",
                "set_domain": "/api/config/domain",
            },
        }

    return app


def run_server(host: str = "0.0.0.0", port: int = 80, agent: Any = None) -> None:
    """Run the FastAPI server with uvicorn.

    Args:
        host: Host to bind to (default: 0.0.0.0 for container)
        port: Port to bind to (default: 80 for Docker)
        agent: Agent instance for lifecycle management (required for lifecycle endpoints)
    """
    app = create_app(agent)

    logger.info(f"Starting API server on {host}:{port}")

    if agent:
        logger.info("Lifecycle management endpoints enabled")
    else:
        logger.warning("Lifecycle endpoints disabled - agent not provided")

    # Run uvicorn in thread-safe mode when called from thread
    # Use Server class instead of uvicorn.run() for thread safety
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    server.run()


# For testing/development
if __name__ == "__main__":
    run_server()
