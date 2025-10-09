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

logger = logging.getLogger(__name__)


# AgentCard file path
AGENT_CARD_PATH = Path("/app/data/agent-card.json")
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


def create_app(web3_utility: Optional[Web3Utility] = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        web3_utility: Web3Utility for signing responses (optional for read-only mode)

    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title="ERC-8004 Agent API",
        description="A2A Protocol and ERC-8004 compliant agent API server",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Store web3_utility for endpoint access
    app.state.web3_utility = web3_utility

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
                "agent_card": "/.well-known/agent-card.json",
                "agent_info": "/api/v1/agent",
                "price_skill": "/api/v1/skills/price",
                "health": "/health",
                "docs": "/api/docs",
            },
        }

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 80,
    web3_utility: Optional[Web3Utility] = None
) -> None:
    """Run the FastAPI server with uvicorn.

    Args:
        host: Host to bind to (default: 0.0.0.0 for container)
        port: Port to bind to (default: 80 for Docker)
        web3_utility: Web3Utility for signing responses (required for skills)
    """
    app = create_app(web3_utility)

    logger.info(f"Starting API server on {host}:{port}")
    if web3_utility and web3_utility.account:
        logger.info(f"API signing enabled with account: {web3_utility.account.address}")
    else:
        logger.warning("API signing disabled - web3_utility not provided")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )


# For testing/development
if __name__ == "__main__":
    run_server()
