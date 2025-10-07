"""Configuration management for ERC-8004 agent server.

Uses Pydantic Settings for type-safe configuration loading from environment variables.
Extends BaseConfig from erc8004_common with server-specific settings.
"""

from pydantic import Field, field_validator
from erc8004_common.utils.config import BaseConfig


class Config(BaseConfig):
    """Agent server configuration loaded from environment variables.

    Server-Specific Required Configuration:
        - PRIVATE_KEY: Private key for transaction signing (without 0x prefix)
        - AGENT_DOMAIN: Domain for agent registration (RFC 8615 compliant)

    Optional AgentCard Customization:
        - AGENT_NAME: Custom agent name for AgentCard (default: auto-generated)
        - AGENT_DESCRIPTION: Custom agent description for AgentCard
        - AGENT_VERSION: Agent version for AgentCard (default: "1.0.0")

    Optional API Server Configuration:
        - API_PORT: Port for AgentCard API server (default: 8001 for server)

    Inherited from BaseConfig:
        - RPC_URL: Ethereum RPC endpoint URL
        - IDENTITY_REGISTRY_ADDRESS: Deployed IdentityRegistry contract address
        - LOG_LEVEL: Logging verbosity (default: INFO)
        - GAS_MULTIPLIER: Gas estimation safety multiplier (default: 1.2)
        - TX_TIMEOUT: Transaction confirmation timeout in seconds (default: 120)
        - REPUTATION_REGISTRY_ADDRESS: Optional ReputationRegistry address
        - VALIDATION_REGISTRY_ADDRESS: Optional ValidationRegistry address

    Example:
        >>> config = Config()  # Loads from environment variables
        >>> print(config.rpc_url)
        'http://localhost:8545'
    """

    # Server-specific required fields
    private_key: str = Field(
        ...,
        description="Private key for transaction signing (without 0x prefix)",
    )

    agent_domain: str = Field(
        ...,
        description="Domain for agent registration (RFC 8615 compliant)",
    )

    # Optional AgentCard customization fields
    agent_name: str | None = Field(
        default=None,
        description="Custom agent name for AgentCard (defaults to 'ERC-8004 Agent {id}')",
    )

    agent_description: str | None = Field(
        default=None,
        description="Custom agent description for AgentCard",
    )

    agent_version: str = Field(
        default="1.0.0",
        description="Agent version for AgentCard (semantic versioning)",
    )

    # API server configuration (default port 8001 for server)
    api_port: int = Field(
        default=8001,
        description="Port for AgentCard API server (default: 8001 for server)",
        ge=1024,
        le=65535,
    )

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str) -> str:
        """Validate private key format.

        Ensures private key is a valid hex string of 64 characters (32 bytes).
        Removes 0x prefix if present.

        Args:
            v: Private key string

        Returns:
            Validated private key without 0x prefix

        Raises:
            ValueError: If private key format is invalid
        """
        # Remove 0x prefix if present
        if v.startswith("0x"):
            v = v[2:]

        # Check if it's a valid hex string of correct length
        if len(v) != 64:
            raise ValueError("Private key must be 64 hex characters (32 bytes)")

        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Private key must be a valid hex string")

        return v

    @field_validator("agent_domain")
    @classmethod
    def validate_agent_domain(cls, v: str) -> str:
        """Validate agent domain format.

        Basic validation for domain format. Should be RFC 8615 compliant.

        Args:
            v: Domain string

        Returns:
            Validated domain

        Raises:
            ValueError: If domain format is invalid
        """
        if not v or len(v.strip()) == 0:
            raise ValueError("Agent domain cannot be empty")

        # Basic validation: should contain at least one dot or be localhost
        if "." not in v and v != "localhost":
            raise ValueError("Agent domain must be a valid domain name or 'localhost'")

        return v.lower().strip()
