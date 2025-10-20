"""FastAPI server for serving AgentCard and agent API endpoints.

RFC 8615 compliant AgentCard hosting at /.well-known/agent-card.json
with proper CORS support for cross-origin agent discovery.
"""

import json
import logging
from pathlib import Path
from typing import Any, TypeVar, Generic, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from .skills.price_fetcher import get_price, PriceFetchError, InvalidSymbolError, NetworkError, RateLimitError
from erc8004_common.utils import Web3Utility
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


# AgentCard and registration file paths
AGENT_CARD_PATH = Path("/app/data/agent-card.json")
AGENT_REGISTRATION_PATH = Path("/app/data/agent-registration.json")
AGENT_STATE_PATH = Path("/app/data/agent_state.json")


# Generic signed response model
DataT = TypeVar('DataT')


class SignedResponse(BaseModel, Generic[DataT]):
    """Generic signed response wrapper for all skills.

    This standard envelope enables trustless verification for any skill.
    All skills return data in this format to support cryptographic verification.

    Attributes:
        data: Skill-specific payload
        signature: EIP-191 signature (hex string)
        signer: Ethereum address that signed the data
    """
    data: DataT
    signature: str = Field(..., description="EIP-191 signature (hex)")
    signer: str = Field(..., description="Ethereum address of signer")


def sign_response_data(web3_utility: Optional[Web3Utility], data: dict) -> dict:
    """Sign skill response data and return signed envelope.

    Generic signing utility for all skill endpoints. Takes any data dict
    and returns the standard signed envelope format.

    Args:
        web3_utility: Web3Utility instance with signing account
        data: Skill-specific data to sign

    Returns:
        Signed envelope: {"data": {...}, "signature": "0x...", "signer": "0x..."}

    Raises:
        ValueError: If web3_utility is None or has no signing account

    Example:
        >>> price_data = {"symbol": "BTCUSDT", "price": 45000.50, "timestamp": "..."}
        >>> signed = sign_response_data(web3_utility, price_data)
        >>> # Returns: {"data": price_data, "signature": "0x...", "signer": "0x..."}
    """
    if not web3_utility:
        raise ValueError("Web3Utility required for signing responses")

    if not web3_utility.account:
        raise ValueError(
            "Web3Utility has no signing account configured. "
            "Ensure private_key is set in configuration."
        )

    # Sign data using Web3Utility
    signed = web3_utility.sign_data(data)
    return signed


# Request/Response models
class PriceRequest(BaseModel):
    """Request model for price fetching."""
    symbol: str = Field(
        ...,
        description="Trading pair symbol (e.g., 'BTC-USD', 'BTCUSDT')",
        examples=["BTC-USD", "ETH-USD", "BTCUSDT"],
    )


class PriceData(BaseModel):
    """Price data payload (skill-specific)."""
    symbol: str = Field(..., description="Normalized symbol in Binance format")
    price: float = Field(..., description="Current price")
    timestamp: str = Field(..., description="UTC timestamp of the price")


def create_app(web3_utility: Optional[Web3Utility] = None, agent: Any = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        web3_utility: Web3Utility for signing responses (optional for read-only mode)
        agent: Agent instance for lifecycle management (optional)

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="ERC-8004 Agent API",
        description="A2A Protocol and ERC-8004 compliant agent API server with lifecycle management",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Store web3_utility and agent for endpoint access
    app.state.web3_utility = web3_utility
    app.state.agent = agent

    # CORS middleware for agent discovery and skills
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for agent discovery
        allow_credentials=False,
        allow_methods=["GET", "POST", "HEAD", "OPTIONS"],  # Added POST for skills
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

    @app.get(
        "/agent.json",
        tags=["ERC-8004"],
        summary="Get Agent Registration (tokenURI)",
        description="ERC-8004 v1.0 registration-v1 format for Identity Registry tokenURI",
    )
    async def get_agent_registration() -> JSONResponse:
        """Serve ERC-8004 v1.0 registration metadata (registration-v1 format).

        This endpoint serves the minimal registration metadata that the tokenURI
        points to in the Identity Registry. It is separate from the full A2A agent
        card and contains only essential identity and endpoint information.

        Registration format includes:
        - Agent name and description
        - Endpoints (A2A card link, wallet addresses)
        - Supported trust models (feedback, tee-attestation)
        - Blockchain registrations (agentId, registry address)

        Returns:
            JSONResponse with registration-v1 format

        Raises:
            HTTPException: 404 if registration file not found
            HTTPException: 500 if registration file is invalid
        """
        if not AGENT_REGISTRATION_PATH.exists():
            logger.error(f"Agent registration not found at {AGENT_REGISTRATION_PATH}")
            raise HTTPException(
                status_code=404,
                detail="Agent registration not found. Agent may not be registered yet.",
            )

        try:
            with open(AGENT_REGISTRATION_PATH) as f:
                registration = json.load(f)

            return JSONResponse(
                content=registration,
                headers={
                    "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
                    "Content-Type": "application/json",
                },
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid registration JSON: {e}")
            raise HTTPException(
                status_code=500, detail="Registration file contains invalid JSON"
            )
        except Exception as e:
            logger.error(f"Error reading registration: {e}")
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

    @app.post(
        "/api/v1/skills/price",
        tags=["Skills"],
        summary="Get cryptocurrency price (signed)",
        description="Fetch real-time cryptocurrency price with cryptographic signature",
        response_model=SignedResponse[PriceData],
    )
    async def get_crypto_price(request: PriceRequest) -> SignedResponse[PriceData]:
        """Fetch cryptocurrency price from Binance API with trustless verification.

        Returns signed price data that can be verified by clients:
        - Cryptographic signature (EIP-191)
        - Server's Ethereum address
        - Price payload

        Args:
            request: Price request with symbol

        Returns:
            Signed price response with signature and signer

        Raises:
            HTTPException: 400 for invalid symbol, 429 for rate limit, 503 for network errors
        """
        try:
            # 1. Fetch price from Binance (skill-specific logic)
            price_data = await get_price(request.symbol)

            # 2. Sign using generic wrapper
            web3_utility = app.state.web3_utility
            signed = sign_response_data(web3_utility, price_data)

            # 3. Return signed envelope
            return SignedResponse[PriceData](**signed)

        except InvalidSymbolError as e:
            logger.warning(f"Invalid symbol requested: {request.symbol}")
            raise HTTPException(status_code=400, detail=str(e))

        except RateLimitError as e:
            logger.warning("Binance API rate limit exceeded")
            raise HTTPException(status_code=429, detail=str(e))

        except NetworkError as e:
            logger.error(f"Network error fetching price: {e}")
            raise HTTPException(status_code=503, detail=str(e))

        except ValueError as e:
            # Signing errors (no web3_utility or account)
            logger.error(f"Signing error: {e}")
            raise HTTPException(
                status_code=500,
                detail="Server signing configuration error"
            )

        except PriceFetchError as e:
            logger.error(f"Unexpected error fetching price: {e}")
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
        description="Manually trigger on-chain agent registration (requires domain set and wallet funded)",
        response_model=RegisterResponse,
    )
    async def register() -> RegisterResponse:
        """Trigger agent registration on-chain.

        Prerequisites:
            - Domain must be set (via POST /api/config/domain)
            - Wallet must be funded with at least min_balance_for_registration

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
            # Prerequisites not met (domain not set, insufficient balance, etc.)
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
        description="Set agent domain for registration (does NOT re-derive key, key already exists from startup)",
        response_model=DomainConfigResponse,
    )
    async def set_domain(request: DomainConfigRequest) -> DomainConfigResponse:
        """Set agent domain for registration.

        Note: This does NOT re-derive the key. The key was already derived at startup
        using ROFL_KEY_ID. This only sets the domain that will be used for registration.

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
            "name": "ERC-8004 Agent API",
            "version": "1.0.0",
            "protocol": "A2A v0.3.0",
            "endpoints": {
                "registration": "/agent.json",
                "agent_card": "/.well-known/agent-card.json",
                "agent_info": "/api/v1/agent",
                "price_skill": "/api/v1/skills/price",
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


def run_server(
    host: str = "0.0.0.0",
    port: int = 80,
    web3_utility: Optional[Web3Utility] = None,
    agent: Any = None
) -> None:
    """Run the FastAPI server with uvicorn.

    Args:
        host: Host to bind to (default: 0.0.0.0 for container)
        port: Port to bind to (default: 80 for Docker)
        web3_utility: Web3Utility for signing responses (required for skills)
        agent: Agent instance for lifecycle management (required for lifecycle endpoints)
    """
    app = create_app(web3_utility, agent)

    logger.info(f"Starting API server on {host}:{port}")
    if web3_utility and web3_utility.account:
        logger.info(f"API signing enabled with account: {web3_utility.account.address}")
    else:
        logger.warning("API signing disabled - web3_utility not provided")

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
