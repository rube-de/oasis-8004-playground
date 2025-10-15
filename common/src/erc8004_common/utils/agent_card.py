"""A2A and ERC-8004 compliant AgentCard implementation.

This module provides AgentCard data structures compliant with:
- A2A Protocol v0.3.0 (Linux Foundation)
- ERC-8004 Trustless Agents specification
- RFC 8615 Well-Known URIs

RFC 8615 Hosting Requirement:
    AgentCard must be served at: https://{domain}/.well-known/agent-card.json
    Content-Type: application/json
    CORS: Allow cross-origin requests for agent discovery

A2A Protocol Compliance:
    Implements protocolVersion 0.3.0 with required fields:
    - protocolVersion, name, description, version, url, preferredTransport
    - capabilities (nested object with extensions support)
    - skills array with structured skill definitions
    - defaultInputModes and defaultOutputModes

ERC-8004 Extensions:
    - registrations: Array of blockchain identities with CAIP-10 addresses
    - trustModels: Supported trust mechanisms (feedback, tee-attestation, etc.)
    - signatures: Cryptographic proof of address ownership

Future Implementation:
    - HTTP server (Flask/FastAPI) serving /.well-known/agent-card.json
    - TLS certificate management for HTTPS
    - Dynamic AgentCard generation from agent state
    - JWS signature verification for card integrity
"""

from dataclasses import dataclass, field, asdict
from typing import Any
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils import to_checksum_address


@dataclass
class Provider:
    """Agent provider/organization information."""

    organization: str
    url: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class Extension:
    """A2A protocol extension definition."""

    uri: str
    description: str
    required: bool = False
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class Capabilities:
    """A2A protocol capabilities object."""

    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False
    extensions: list[Extension] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "streaming": self.streaming,
            "pushNotifications": self.pushNotifications,
            "stateTransitionHistory": self.stateTransitionHistory,
            "extensions": [ext.to_dict() for ext in self.extensions],
        }


@dataclass
class Skill:
    """A2A protocol skill definition."""

    id: str
    name: str
    description: str
    tags: list[str] = field(default_factory=list)
    inputModes: list[str] = field(default_factory=lambda: ["text"])
    outputModes: list[str] = field(default_factory=lambda: ["text"])

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class Registration:
    """ERC-8004 blockchain registration entry.

    Contains agent identity information from IdentityRegistry including
    CAIP-10 formatted address and cryptographic signature proving ownership.
    """

    agentId: int
    agentAddress: str  # CAIP-10 format: eip155:{chainId}:{address}
    signature: str  # Hex-encoded signature proving address ownership

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)


@dataclass
class AgentCard:
    """A2A Protocol v0.3.0 and ERC-8004 compliant AgentCard.

    Represents discoverable agent metadata per A2A Protocol v0.3.0 with
    ERC-8004 blockchain extensions. Hosted at /.well-known/agent-card.json
    per RFC 8615.

    A2A Protocol Fields (Required):
        protocolVersion: A2A protocol version (currently "0.3.0")
        name: Human-readable agent name
        description: Agent capabilities and purpose
        version: Agent version (semantic versioning)
        url: Primary API endpoint
        preferredTransport: Preferred communication protocol
        capabilities: Nested capabilities object
        skills: Array of agent skills
        defaultInputModes: Supported input modes
        defaultOutputModes: Supported output modes

    ERC-8004 Extensions (Required for blockchain agents):
        registrations: Array of blockchain identities
        trustModels: Supported trust mechanisms

    Optional Fields:
        provider: Organization information
        ValidationRequestsURI: Validation requests endpoint (for server agents)
        ValidationResponsesURI: Validation responses endpoint (for validators)
        metadata: Additional custom fields
    """

    # A2A Protocol v0.3.0 required fields
    protocolVersion: str
    name: str
    description: str
    version: str
    url: str
    preferredTransport: str
    capabilities: Capabilities
    skills: list[Skill]
    defaultInputModes: list[str]
    defaultOutputModes: list[str]

    # ERC-8004 required extensions
    registrations: list[Registration]
    trustModels: list[str]

    # Optional fields
    provider: Provider | None = None
    ValidationRequestsURI: str | None = None
    ValidationResponsesURI: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert AgentCard to JSON-serializable dictionary.

        Returns:
            Complete AgentCard as dict, ready for JSON serialization
        """
        result = {
            "protocolVersion": self.protocolVersion,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "preferredTransport": self.preferredTransport,
            "capabilities": self.capabilities.to_dict(),
            "skills": [skill.to_dict() for skill in self.skills],
            "defaultInputModes": self.defaultInputModes,
            "defaultOutputModes": self.defaultOutputModes,
            "registrations": [reg.to_dict() for reg in self.registrations],
            "trustModels": self.trustModels,
        }

        # Add optional fields if present
        if self.provider:
            result["provider"] = self.provider.to_dict()
        if self.ValidationRequestsURI:
            result["ValidationRequestsURI"] = self.ValidationRequestsURI
        if self.ValidationResponsesURI:
            result["ValidationResponsesURI"] = self.ValidationResponsesURI
        if self.metadata:
            result["metadata"] = self.metadata

        return result


def format_caip10_address(chain_id: int, address: str) -> str:
    """Format Ethereum address as CAIP-10 identifier.

    CAIP-10 defines chain-agnostic account identifiers:
    https://github.com/ChainAgnostic/CAIPs/blob/master/CAIPs/caip-10.md

    Args:
        chain_id: EVM chain ID (e.g., 1 for mainnet, 31337 for hardhat)
        address: Ethereum address (with or without 0x prefix)

    Returns:
        CAIP-10 formatted address: eip155:{chain_id}:{address}

    Example:
        >>> format_caip10_address(1, "0x1234...5678")
        "eip155:1:0x1234...5678"
    """
    # Ensure address has 0x prefix
    if not address.startswith("0x"):
        address = f"0x{address}"

    return f"eip155:{chain_id}:{address}"


def sign_agent_registration(
    agent_id: int,
    agent_address: str,
    agent_domain: str,
    account: Account,
) -> str:
    """Generate signature proving ownership of agent address.

    Creates a cryptographic signature over agent registration data using
    Ethereum personal_sign. This proves the agent controls the private key
    for the registered address.

    Args:
        agent_id: Agent ID from IdentityRegistry
        agent_address: Ethereum address (checksummed)
        agent_domain: Agent domain from registration
        account: Web3 Account object for signing

    Returns:
        Hex-encoded signature (with 0x prefix)

    Example:
        >>> account = Account.from_key(private_key)
        >>> sig = sign_agent_registration(1, "0x123...", "agent.local", account)
        >>> sig.startswith("0x")
        True
    """
    # Create message to sign
    message = f"ERC-8004 Agent Registration\nAgent ID: {agent_id}\nAddress: {agent_address}\nDomain: {agent_domain}"

    # Encode message for Ethereum signing
    message_hash = encode_defunct(text=message)

    # Sign message
    signed_message = account.sign_message(message_hash)

    # Return hex-encoded signature
    return signed_message.signature.hex()


# Future: HTTP server implementation
#
# from flask import Flask, jsonify, request
# from flask_cors import CORS
#
# app = Flask(__name__)
# CORS(app)  # Enable CORS for agent discovery
#
# @app.route('/.well-known/agent-card.json')
# def serve_agent_card():
#     """Serve AgentCard at RFC 8615 compliant path.
#
#     Returns:
#         JSON response with AgentCard data
#         Content-Type: application/json
#     """
#     # Load agent state
#     agent_state = load_agent_state()
#
#     # Generate AgentCard
#     card = generate_agent_card(
#         agent_id=agent_state['agent_id'],
#         agent_address=agent_state['agent_address'],
#         agent_domain=agent_state['agent_domain'],
#         chain_id=agent_state['chain_id'],
#         private_key=get_private_key(),
#     )
#
#     return jsonify(card.to_dict()), 200, {
#         'Content-Type': 'application/json',
#         'Cache-Control': 'public, max-age=300',  # 5 min cache
#     }
#
# @app.route('/health')
# def health_check():
#     """Health check endpoint for monitoring."""
#     return jsonify({"status": "healthy"}), 200
