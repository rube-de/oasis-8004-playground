"""Base configuration for ERC-8004 applications.

Provides shared configuration fields for all ERC-8004 agents (clients, servers, validators).
Application-specific configurations should inherit from BaseConfig.
"""

from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from eth_utils import is_address, to_checksum_address


class BaseConfig(BaseSettings):
    """Base configuration for ERC-8004 applications.

    Shared Configuration:
        - RPC_URL: Ethereum RPC endpoint URL
        - IDENTITY_REGISTRY_ADDRESS: Deployed IdentityRegistry contract address
        - REPUTATION_REGISTRY_ADDRESS: Optional ReputationRegistry address
        - VALIDATION_REGISTRY_ADDRESS: Optional ValidationRegistry address
        - LOG_LEVEL: Logging verbosity (default: INFO)
        - GAS_MULTIPLIER: Gas estimation safety multiplier (default: 1.2)
        - TX_TIMEOUT: Transaction confirmation timeout in seconds (default: 120)
        - USE_LOCAL_MODE: Use local private key mode for development (default: False = ROFL mode)
        - ROFL_KEY_ID: Key ID for ROFL key generation (required in ROFL mode)

    Deployment Modes:
        - ROFL Mode (default): Keys generated securely in TEE via ROFL client
        - Local Mode (opt-in): Private keys from environment variables (development only)

    Example:
        >>> config = BaseConfig()  # Loads from environment variables
        >>> print(config.rpc_url)
        'http://localhost:8545'
        >>> print(config.use_local_mode)
        False  # ROFL mode is default
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Network configuration
    rpc_url: str = Field(
        default="http://localhost:8545",
        description="Ethereum RPC endpoint URL",
    )

    # Registry addresses
    identity_registry_address: str = Field(
        ...,
        description="Deployed IdentityRegistry contract address",
    )

    reputation_registry_address: Optional[str] = Field(
        default=None,
        description="ReputationRegistry contract address (optional)",
    )

    validation_registry_address: Optional[str] = Field(
        default=None,
        description="ValidationRegistry contract address (optional)",
    )

    # Operational settings
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

    # Key management configuration
    use_local_mode: bool = Field(
        default=False,
        description="Use local private key mode (development only). Default: False (ROFL mode)",
    )

    rofl_key_id: Optional[str] = Field(
        default=None,
        description="Key ID for ROFL key generation (required in ROFL mode)",
    )

    proxy_host: Optional[str] = Field(
        default=None,
        description="HTTP proxy host (mirror of ROFL_PROXY_HOST for verification)",
    )

    # Funding configuration
    min_balance_for_registration: float = Field(
        default=0.001,
        ge=0.0,
        description="Minimum wallet balance (in ETH) required for on-chain registration",
    )

    @field_validator("identity_registry_address", "reputation_registry_address", "validation_registry_address")
    @classmethod
    def validate_ethereum_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate Ethereum address format and convert to checksum format."""
        if v is None:
            return None

        if not is_address(v):
            raise ValueError(f"Invalid Ethereum address: {v}")

        return to_checksum_address(v)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is a valid Python logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()

        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")

        return v_upper
