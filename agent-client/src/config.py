"""Configuration management for ERC-8004 agent client.

Uses Pydantic Settings for type-safe configuration loading from environment variables.
All configuration values are validated at startup to catch issues early.
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from eth_utils import is_address, to_checksum_address


class Config(BaseSettings):
    """Agent client configuration loaded from environment variables.

    Required Configuration:
        - RPC_URL: Ethereum RPC endpoint URL
        - PRIVATE_KEY: Private key for transaction signing (without 0x prefix)
        - IDENTITY_REGISTRY_ADDRESS: Deployed IdentityRegistry contract address
        - AGENT_DOMAIN: Domain for agent registration (RFC 8615 compliant)

    Optional Configuration:
        - LOG_LEVEL: Logging verbosity (default: INFO)
        - GAS_MULTIPLIER: Gas estimation safety multiplier (default: 1.2)
        - TX_TIMEOUT: Transaction confirmation timeout in seconds (default: 120)
        - REPUTATION_REGISTRY_ADDRESS: Future ReputationRegistry address
        - VALIDATION_REGISTRY_ADDRESS: Future ValidationRegistry address

    Example:
        >>> config = Config()  # Loads from environment variables
        >>> print(config.rpc_url)
        'http://localhost:8545'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Required fields
    rpc_url: str = Field(
        default="http://localhost:8545",
        description="Ethereum RPC endpoint URL",
    )

    private_key: str = Field(
        ...,
        description="Private key for transaction signing (without 0x prefix)",
    )

    identity_registry_address: str = Field(
        ...,
        description="Deployed IdentityRegistry contract address",
    )

    agent_domain: str = Field(
        ...,
        description="Domain for agent registration (RFC 8615 compliant)",
    )

    # Optional fields
    log_level: str = Field(
        default="INFO",
        description="Logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    gas_multiplier: float = Field(
        default=1.2,
        ge=1.0,
        le=3.0,
        description="Gas estimation safety multiplier",
    )

    tx_timeout: int = Field(
        default=120,
        ge=10,
        le=600,
        description="Transaction confirmation timeout in seconds",
    )

    reputation_registry_address: Optional[str] = Field(
        default=None,
        description="ReputationRegistry contract address (future use)",
    )

    validation_registry_address: Optional[str] = Field(
        default=None,
        description="ValidationRegistry contract address (future use)",
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

    @field_validator("identity_registry_address", "reputation_registry_address", "validation_registry_address")
    @classmethod
    def validate_ethereum_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate Ethereum address format.

        Ensures address is a valid Ethereum address and converts to checksum format.

        Args:
            v: Ethereum address string or None

        Returns:
            Checksummed Ethereum address or None

        Raises:
            ValueError: If address format is invalid
        """
        if v is None:
            return None

        if not is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")

        # Convert to checksum address for consistency
        return to_checksum_address(v)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level.

        Ensures log level is a valid Python logging level.

        Args:
            v: Log level string

        Returns:
            Uppercased log level

        Raises:
            ValueError: If log level is invalid
        """
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()

        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")

        return v_upper

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
