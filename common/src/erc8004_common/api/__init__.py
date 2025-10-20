"""Agent lifecycle API handlers and models.

Shared API infrastructure for all ERC-8004 agent types.
Provides pure handler functions and Pydantic models for:
- Wallet management (funding verification)
- Status monitoring (registration, operational state)
- Registration control (manual trigger)
- Configuration management (domain updates)

Usage:
    from erc8004_common.api import lifecycle, config_handlers, models

    # In FastAPI endpoints:
    @app.get("/api/wallet")
    async def get_wallet():
        return lifecycle.get_wallet_info(agent, web3_utility, config)
"""

# Import handlers
from . import lifecycle
from . import config_handlers

# Import models for convenience
from .models import (
    # Wallet models
    WalletResponse,
    # Status models
    StatusResponse,
    AgentStatusInfo,
    RoflStatusInfo,
    BalanceStatusInfo,
    # Register models
    RegisterResponse,
    # Config models
    ConfigResponse,
    DomainConfigRequest,
    DomainConfigResponse,
    # Metadata models (Phase 2)
    MetadataUpdateRequest,
    MetadataUpdateResponse,
    MetadataGetResponse,
    # Signing models (Phase 2)
    SignRequest,
    SignResponse,
)

__all__ = [
    # Handler modules
    "lifecycle",
    "config_handlers",
    # Wallet models
    "WalletResponse",
    # Status models
    "StatusResponse",
    "AgentStatusInfo",
    "RoflStatusInfo",
    "BalanceStatusInfo",
    # Register models
    "RegisterResponse",
    # Config models
    "ConfigResponse",
    "DomainConfigRequest",
    "DomainConfigResponse",
    # Metadata models (Phase 2)
    "MetadataUpdateRequest",
    "MetadataUpdateResponse",
    "MetadataGetResponse",
    # Signing models (Phase 2)
    "SignRequest",
    "SignResponse",
]
