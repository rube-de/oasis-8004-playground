"""Pydantic models for agent lifecycle API.

Request and response models for lifecycle management endpoints.
Used by all agent types (server, client, validator).
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


# Wallet endpoint models
class WalletResponse(BaseModel):
    """Response model for GET /api/wallet endpoint."""

    address: str = Field(..., description="Ethereum address of the agent")
    balance: str = Field(..., description="Current balance in ETH")
    balance_wei: str = Field(..., description="Current balance in wei")
    funded: bool = Field(..., description="Whether wallet has sufficient balance for registration")
    minimum_balance: str = Field(..., description="Minimum balance required for registration (ETH)")
    chain_id: int = Field(..., description="Connected blockchain chain ID")
    chain_name: str = Field(..., description="Human-readable chain name")
    qr_code_data: Optional[str] = Field(
        None, description="EIP-681 formatted payment URI for QR code generation"
    )
    rofl_mode: bool = Field(..., description="Whether agent is running in ROFL mode")
    rofl_key_id: Optional[str] = Field(None, description="ROFL key ID used for key generation")


# Status endpoint models
class AgentStatusInfo(BaseModel):
    """Agent-specific status information."""

    domain: Optional[str] = Field(None, description="Agent domain (may be None if not set)")
    address: str = Field(..., description="Agent Ethereum address")
    agent_id: Optional[int] = Field(None, description="On-chain agent ID (None if not registered)")
    is_registered: bool = Field(..., description="Whether agent is registered on-chain")
    chain_id: int = Field(..., description="Connected chain ID")


class RoflStatusInfo(BaseModel):
    """ROFL-specific status information."""

    enabled: bool = Field(..., description="Whether ROFL mode is enabled")
    key_id: Optional[str] = Field(None, description="ROFL key ID used for key generation")


class BalanceStatusInfo(BaseModel):
    """Balance status information."""

    eth: str = Field(..., description="Current balance in ETH")
    funded: bool = Field(..., description="Whether balance is sufficient for registration")


class StatusResponse(BaseModel):
    """Response model for GET /api/status endpoint."""

    status: str = Field(
        ...,
        description=(
            "Current agent status: "
            "uninitialized (not started), "
            "initialized (key derived, no domain), "
            "ready (domain set and funded), "
            "registered (on-chain registration complete), "
            "operational (running and ready for tasks)"
        ),
    )
    agent: AgentStatusInfo = Field(..., description="Agent-specific information")
    rofl: RoflStatusInfo = Field(..., description="ROFL configuration")
    balance: BalanceStatusInfo = Field(..., description="Wallet balance information")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")


# Register endpoint models
class RegisterResponse(BaseModel):
    """Response model for POST /api/register endpoint."""

    success: bool = Field(..., description="Whether registration was successful")
    agent_id: int = Field(..., description="Assigned agent ID (ERC-721 tokenId)")
    domain: str = Field(..., description="Agent domain used for registration")
    address: str = Field(..., description="Agent Ethereum address")
    tx_hash: str = Field(..., description="Transaction hash of registration")
    explorer_url: Optional[str] = Field(None, description="Block explorer URL for transaction")
    already_registered: bool = Field(
        ..., description="Whether agent was already registered (idempotent operation)"
    )


# Configuration endpoint models
class ConfigResponse(BaseModel):
    """Response model for GET /api/config endpoint."""

    domain: Optional[str] = Field(None, description="Current agent domain (may be None)")
    chain_id: int = Field(..., description="Connected chain ID")
    rofl_enabled: bool = Field(..., description="Whether ROFL mode is enabled")
    rofl_key_id: Optional[str] = Field(None, description="ROFL key ID")
    rofl_socket_path: Optional[str] = Field(None, description="ROFL socket path")
    identity_registry: str = Field(..., description="Identity Registry contract address")
    reputation_registry: Optional[str] = Field(None, description="Reputation Registry address")
    validation_registry: Optional[str] = Field(None, description="Validation Registry address")


class DomainConfigRequest(BaseModel):
    """Request model for POST /api/config/domain endpoint."""

    domain: str = Field(
        ...,
        description="Agent domain to set (e.g., 'my-agent-8000.rofl.oasis.io' or 'localhost:8000')",
        min_length=1,
    )


class DomainConfigResponse(BaseModel):
    """Response model for POST /api/config/domain endpoint."""

    success: bool = Field(..., description="Whether domain update was successful")
    domain: str = Field(..., description="Updated domain value")
    address_updated: bool = Field(
        ..., description="Whether address was updated (always false, key already exists)"
    )
    restart_required: bool = Field(
        ..., description="Whether agent restart is required (always false for domain updates)"
    )


# Metadata endpoint models (Phase 2)
class MetadataUpdateRequest(BaseModel):
    """Request model for POST /api/metadata/update endpoint."""

    key: str = Field(..., description="Metadata key to update", min_length=1)
    value: str = Field(..., description="Metadata value to set", min_length=1)


class MetadataUpdateResponse(BaseModel):
    """Response model for POST /api/metadata/update endpoint."""

    success: bool = Field(..., description="Whether metadata update was successful")
    agent_id: int = Field(..., description="Agent ID")
    tx_hash: str = Field(..., description="Transaction hash")
    key: str = Field(..., description="Updated metadata key")
    value: str = Field(..., description="Updated metadata value")


class MetadataGetResponse(BaseModel):
    """Response model for GET /api/metadata/{key} endpoint."""

    agent_id: int = Field(..., description="Agent ID")
    key: str = Field(..., description="Metadata key")
    value: str = Field(..., description="Metadata value")


# Signing endpoint models (Phase 2)
class SignRequest(BaseModel):
    """Request model for POST /api/sign endpoint."""

    message: str = Field(..., description="Message to sign", min_length=1)


class SignResponse(BaseModel):
    """Response model for POST /api/sign endpoint."""

    message: str = Field(..., description="Original message")
    message_hash: str = Field(..., description="Keccak256 hash of the message")
    signature: str = Field(..., description="EIP-191 signature (hex)")
    eip191_signature: str = Field(..., description="Full EIP-191 formatted signature")
    signer_address: str = Field(..., description="Ethereum address that signed the message")
    rofl_key_id: Optional[str] = Field(None, description="ROFL key ID used for signing")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp")
