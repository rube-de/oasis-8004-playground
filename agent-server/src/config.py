"""Configuration management for ERC-8004 agent server.

Uses Pydantic Settings for type-safe configuration loading from environment variables.
Extends BaseConfig from erc8004_common with server-specific settings.
"""

import logging
from pydantic import Field, field_validator, model_validator
from erc8004_common.utils.config import BaseConfig

logger = logging.getLogger(__name__)


class Config(BaseConfig):
    """Agent server configuration loaded from environment variables.

    Server-Specific Required Configuration:
        - AGENT_DOMAIN: Domain for agent registration (RFC 8615, also used as ROFL key-id)

    Key Management (mode-dependent):
        - USE_LOCAL_MODE: false (default) → ROFL mode, keys generated in TEE
        - USE_LOCAL_MODE: true → Local mode, requires PRIVATE_KEY in env vars

    Local Mode Only (development):
        - PRIVATE_KEY: Private key for transaction signing (without 0x prefix)

    Optional AgentCard Customization:
        - AGENT_NAME: Custom agent name for AgentCard (default: auto-generated)
        - AGENT_DESCRIPTION: Custom agent description for AgentCard
        - AGENT_VERSION: Agent version for AgentCard (default: "1.0.0")

    Optional API Server Configuration:
        - API_PORT: Port for AgentCard API server (default: 80 for Docker)

    Inherited from BaseConfig:
        - RPC_URL: Ethereum RPC endpoint URL
        - IDENTITY_REGISTRY_ADDRESS: Deployed IdentityRegistry contract address
        - LOG_LEVEL: Logging verbosity (default: INFO)
        - GAS_MULTIPLIER: Gas estimation safety multiplier (default: 1.2)
        - TX_TIMEOUT: Transaction confirmation timeout in seconds (default: 120)
        - USE_LOCAL_MODE: Use local private key mode (default: False = ROFL mode)
        - ROFL_SOCKET_PATH: Path to ROFL socket (default: /run/rofl-appd.sock)
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

    # Server-specific fields
    private_key: str | None = Field(
        default=None,
        description="Private key for LOCAL MODE ONLY (without 0x prefix). Not used in ROFL mode.",
    )

    agent_domain: str = Field(
        ...,
        description="Domain for agent registration (RFC 8615). Also used as ROFL key-id in production.",
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

    # API server configuration (default port 80 for Docker)
    api_port: int = Field(
        default=80,
        description="Port for AgentCard API server (default: 80 for Docker)",
        ge=1,
        le=65535,
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
