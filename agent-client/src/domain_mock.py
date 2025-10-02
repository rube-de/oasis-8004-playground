"""Mock domain hosting for ERC-8004 AgentCard.

This module provides the AgentCard data structure and mock implementations
per ERC-8004 specification and RFC 8615 (Well-Known URIs).

RFC 8615 Compliance:
    AgentCard must be hosted at: https://{domain}/.well-known/agent-card.json

    Example: If agent domain is "agent.example.com", the AgentCard should be
    accessible at: https://agent.example.com/.well-known/agent-card.json

ERC-8004 AgentCard Structure:
    {
        "name": "Human-readable agent name",
        "description": "Agent capabilities and purpose",
        "version": "Semantic version (e.g., 1.0.0)",
        "capabilities": ["list", "of", "supported", "operations"],
        "endpoint": "https://api.example.com/agent",
        "protocol": "Protocol identifier (e.g., A2A-v1)",
        "metadata": {
            "optional": "additional fields"
        }
    }

Future Implementation:
    - HTTP server (Flask/FastAPI) serving AgentCard
    - TLS certificate management
    - Dynamic AgentCard generation from configuration
    - Health check endpoint
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentCard:
    """ERC-8004 AgentCard structure.

    Represents discoverable agent metadata per ERC-8004 specification.
    Hosted at .well-known/agent-card.json per RFC 8615.
    """

    name: str
    description: str
    version: str
    capabilities: list[str]
    endpoint: str
    protocol: str = "A2A-v1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert AgentCard to JSON-serializable dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "capabilities": self.capabilities,
            "endpoint": self.endpoint,
            "protocol": self.protocol,
            "metadata": self.metadata,
        }


def generate_mock_agent_card(
    agent_domain: str,
    agent_address: str,
    agent_id: int | None = None,
) -> AgentCard:
    """Generate mock AgentCard with sample data.

    Args:
        agent_domain: Agent's registered domain
        agent_address: Agent's Ethereum address
        agent_id: Optional agent ID from IdentityRegistry

    Returns:
        AgentCard instance with mock data
    """
    metadata = {
        "agent_domain": agent_domain,
        "agent_address": agent_address,
        "blockchain": "ethereum",
        "network": "hardhat-local",
    }

    if agent_id is not None:
        metadata["agent_id"] = agent_id

    return AgentCard(
        name=f"Agent at {agent_domain}",
        description="ERC-8004 compliant autonomous agent with identity registration",
        version="0.1.0",
        capabilities=[
            "identity.register",
            "identity.resolve",
            "identity.update",
        ],
        endpoint=f"https://{agent_domain}/api/v1",
        protocol="A2A-v1",
        metadata=metadata,
    )


# Future: HTTP server implementation
#
# from flask import Flask, jsonify
#
# app = Flask(__name__)
#
# @app.route('/.well-known/agent-card.json')
# def serve_agent_card():
#     """Serve AgentCard at RFC 8615 compliant path."""
#     card = generate_mock_agent_card(...)
#     return jsonify(card.to_dict())
#
# @app.route('/health')
# def health_check():
#     """Health check endpoint for monitoring."""
#     return jsonify({"status": "healthy"})
