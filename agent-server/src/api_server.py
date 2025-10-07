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

logger = logging.getLogger(__name__)


# AgentCard file path
AGENT_CARD_PATH = Path("/app/data/agent-card.json")
AGENT_STATE_PATH = Path("/app/data/agent_state.json")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

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
                "health": "/health",
                "docs": "/api/docs",
            },
        }

    return app


def run_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Run the FastAPI server with uvicorn.

    Args:
        host: Host to bind to (default: 0.0.0.0 for container)
        port: Port to bind to (default: 8001 for server)
    """
    app = create_app()

    logger.info(f"Starting API server on {host}:{port}")

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
