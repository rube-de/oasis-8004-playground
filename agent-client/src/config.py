"""Configuration management for ERC-8004 agent client.

Uses Pydantic Settings for type-safe configuration loading from environment variables.
Extends BaseConfig from erc8004_common with client-specific settings.
"""

import logging
from pydantic import Field, field_validator, model_validator
from erc8004_common.utils.config import BaseConfig

logger = logging.getLogger(__name__)


class Config(BaseConfig):
    """Agent client configuration loaded from environment variables.

    Key Management (mode-dependent):
        - USE_LOCAL_MODE: false (default) → ROFL mode, keys generated in TEE
        - USE_LOCAL_MODE: true → Local mode, requires PRIVATE_KEY in env vars

    Local Mode Only (development):
        - PRIVATE_KEY: Private key for transaction signing (without 0x prefix)

    Optional Registration Configuration (v1.0):
        - AGENT_TOKEN_URI: TokenURI for registration (IPFS/HTTPS, optional)

    Agent Metadata Configuration:
        Agent metadata (name, description, skills, capabilities) is configured in
        agent_config.json (not environment variables). This separates static agent
        configuration from runtime environment settings.

    Optional API Server Configuration:
        - API_PORT: Port for AgentCard API server (default: 80)
        - AGENT_DOMAIN: Agent domain for RFC 8615/A2A Protocol (default: "localhost")
          NOTE: v1.0 removed on-chain domain storage - this is off-chain only
          In ROFL mode: Used as key-id for persistent key generation

    Inherited from BaseConfig:
        - RPC_URL: Ethereum RPC endpoint URL
        - IDENTITY_REGISTRY_ADDRESS: Deployed IdentityRegistry contract address
        - LOG_LEVEL: Logging verbosity (default: INFO)
        - GAS_MULTIPLIER: Gas estimation safety multiplier (default: 1.2)
        - TX_TIMEOUT: Transaction confirmation timeout in seconds (default: 120)
        - USE_LOCAL_MODE: Use local private key mode (default: False = ROFL mode)
        - REPUTATION_REGISTRY_ADDRESS: Optional ReputationRegistry address
        - VALIDATION_REGISTRY_ADDRESS: Optional ValidationRegistry address

    Example:
        >>> # ROFL mode (default, production)
        >>> config = Config()
        >>> print(config.use_local_mode)
        False

        >>> # Local mode (development)
        >>> # Set USE_LOCAL_MODE=true and PRIVATE_KEY in .env
    """

    # Client-specific fields
    private_key: str | None = Field(
        default=None,
        description="Private key for LOCAL MODE ONLY (without 0x prefix). Not used in ROFL mode.",
    )

    # Optional agent registration fields (v1.0)
    agent_token_uri: str | None = Field(
        default=None,
        description="Agent tokenURI for registration (IPFS/HTTPS URI, optional)",
    )

    # Agent metadata (name, description, skills, capabilities) is now configured
    # in agent_config.json (not environment variables)

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
    agent_domain: str | None = Field(
        default=None,
        description="Agent domain for RFC 8615 AgentCard hosting and A2A Protocol URL (optional, can be set via API)",
    )

    # Optional agent discovery configuration (v1.0)
    # v1.0 Note: Discovery requires agent ID (not address) as contracts don't support reverse lookups
    agent_server_id: int | None = Field(
        default=None,
        description="Optional: Agent server ID for discovery on startup (v1.0 uses agentId, not address)",
    )

    @model_validator(mode='after')
    def validate_key_configuration(self) -> 'Config':
        """Validate key configuration based on deployment mode.

        Ensures proper configuration for each mode:
        - Local mode: Requires PRIVATE_KEY
        - ROFL mode: Warns if PRIVATE_KEY is set (will be ignored)

        Returns:
            self: Validated config instance

        Raises:
            ValueError: If local mode is enabled without PRIVATE_KEY
        """
        if self.use_local_mode:
            # Local mode (development): require private_key
            if not self.private_key:
                raise ValueError(
                    "LOCAL MODE ERROR: private_key is required when use_local_mode=true. "
                    "Set PRIVATE_KEY in your .env.local file for development."
                )
            logger.info("🔓 LOCAL MODE enabled: Using private key from environment")
        else:
            # ROFL mode (production, default): warn if private_key is set
            if self.private_key:
                logger.warning(
                    "⚠️  ROFL MODE: PRIVATE_KEY env var will be IGNORED. "
                    "Keys are generated securely in TEE via ROFL. "
                    "Remove PRIVATE_KEY from production environment for security!"
                )
            logger.info("🔒 ROFL MODE enabled: Keys will be generated in TEE")

        return self

    @field_validator("private_key")
    @classmethod
    def validate_private_key(cls, v: str | None) -> str | None:
        """Validate private key format (if provided).

        Ensures private key is a valid hex string of 64 characters (32 bytes).
        Removes 0x prefix if present. Allows None for ROFL mode.

        Args:
            v: Private key string or None

        Returns:
            Validated private key without 0x prefix, or None

        Raises:
            ValueError: If private key format is invalid
        """
        # Allow None for ROFL mode
        if v is None:
            return None

        # Remove 0x prefix if present
        if v.startswith("0x"):
            v = v[2:]

        # Check if it's a valid hex string of correct length
        if len(v) != 64:
            raise ValueError(
                "Private key must be 64 hex characters (32 bytes). "
                f"Got {len(v)} characters."
            )

        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Private key must be a valid hex string")

        return v
