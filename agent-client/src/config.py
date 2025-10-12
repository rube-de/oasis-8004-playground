"""Configuration management for ERC-8004 agent client.

Uses Pydantic Settings for type-safe configuration loading from environment variables.
Extends BaseConfig from erc8004_common with client-specific settings.
"""

from pydantic import Field, field_validator
from erc8004_common.utils.config import BaseConfig


class Config(BaseConfig):
    """Agent client configuration loaded from environment variables.

    Client-Specific Required Configuration:
        - PRIVATE_KEY: Private key for transaction signing (without 0x prefix)

    Optional Registration Configuration (v1.0):
        - AGENT_TOKEN_URI: TokenURI for registration (IPFS/HTTPS, optional)
        - AGENT_NAME: Custom agent name for registration/AgentCard (default: auto-generated)
        - AGENT_DESCRIPTION: Custom agent description for registration/AgentCard
        - AGENT_VERSION: Agent version for AgentCard (default: "1.0.0")

    Optional API Server Configuration:
        - API_PORT: Port for AgentCard API server (default: 80)
        - AGENT_DOMAIN: Agent domain for RFC 8615/A2A Protocol (default: "localhost")
          NOTE: v1.0 removed on-chain domain storage - this is off-chain only

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

    # Client-specific required fields
    private_key: str = Field(
        ...,
        description="Private key for transaction signing (without 0x prefix)",
    )

    # Optional agent registration fields (v1.0)
    agent_token_uri: str | None = Field(
        default=None,
        description="Agent tokenURI for registration (IPFS/HTTPS URI, optional)",
    )

    # Optional AgentCard customization fields
    agent_name: str | None = Field(
        default=None,
        description="Custom agent name for AgentCard and registration (defaults to auto-generated)",
    )

    agent_description: str | None = Field(
        default=None,
        description="Custom agent description for AgentCard and registration",
    )

    agent_version: str = Field(
        default="1.0.0",
        description="Agent version for AgentCard (semantic versioning)",
    )

    # API server configuration
    api_port: int = Field(
        default=80,
        description="Port for AgentCard API server (default: 80 for Docker)",
        ge=1,
        le=65535,
    )

    # Agent domain configuration (OFF-CHAIN ONLY - RFC 8615 / A2A Protocol)
    # NOTE: v1.0 removed on-chain domain storage from IdentityRegistry
    # Domain is now used exclusively for off-chain service discovery and API endpoints
    agent_domain: str = Field(
        default="localhost",
        description="Agent domain for RFC 8615 AgentCard hosting and A2A Protocol URL (NOT stored on-chain)",
    )

    # Optional agent discovery configuration (v1.0)
    # v1.0 Note: Discovery requires agent ID (not address) as contracts don't support reverse lookups
    agent_server_id: int | None = Field(
        default=None,
        description="Optional: Agent server ID for discovery on startup (v1.0 uses agentId, not address)",
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
