# ERC-8004 Common Infrastructure

Shared components for ERC-8004 agent implementations on Oasis Network.

## Overview

This package provides reusable infrastructure for building ERC-8004 compliant agents, including:

- **Registry Plugins**: Identity, Reputation, and Validation registry interactions
- **Contract Utilities**: Web3 abstraction layer for contract interactions
- **Base Configuration**: Shared configuration models for all agent types

## Components

### Plugins (`erc8004_common.plugins`)

- `BaseRegistryPlugin`: Abstract base class for registry plugins
- `IdentityRegistryPlugin`: Identity Registry operations (registration, resolution, queries)
- Plugin exceptions: `PluginError`, `PluginInitializationError`, `TransactionError`, `ContractCallError`

### Utilities (`erc8004_common.utils`)

- `Web3Utility`: Comprehensive Web3 operations layer
  - ABI loading from Hardhat artifacts
  - Transaction signing middleware
  - Contract instance creation
  - Message signing and verification (EIP-191)
  - Methods: `get_contract()`, `sign_data()`, `verify_signature()`
- `verify_rofl_attestation(agent_address)`: Verify ROFL TEE attestation (**MOCK**)
  - Validates agent has valid TEE attestation from Oasis ROFL
  - Future: Query Sapphire network metadata for attestation verification
- `get_rofl_metadata(agent_address)`: Get ROFL metadata for agent (**MOCK**)
  - Future: Retrieve attestation quote, signature chain, enclave measurements
- Agent Discovery (ERC-8004 v1.0):
  - `discover_agent_by_id()`: Two-step discovery: tokenURI → registration JSON → agent card
  - `fetch_registration_json()`: Fetch registration metadata from tokenURI
  - `extract_agent_card_url()`: Extract A2A endpoint from registration
  - `fetch_agent_card_from_url()`: Fetch AgentCard from full URL
  - `parse_agent_card()`: Parse and validate AgentCard JSON
- Utility exceptions: `Web3UtilityError`, `ABILoadError`, `ConnectionError`, `SigningError`, `ROFLAttestationError`, `AgentDiscoveryError`

### Configuration (`erc8004_common.config`)

- `BaseConfig`: Base configuration class with shared settings
  - RPC URL and network configuration
  - Registry contract addresses
  - Operational settings (gas, timeouts, logging)

## Usage

### In Agent Client

```python
from erc8004_common.config import BaseConfig
from erc8004_common.utils import Web3Utility
from erc8004_common.plugins import IdentityRegistryPlugin

class ClientConfig(BaseConfig):
    # Add client-specific fields
    private_key: str
    agent_domain: str

config = ClientConfig()
utility = Web3Utility(config)
plugin = IdentityRegistryPlugin(utility, config)
plugin.initialize()
agent_id = plugin.register()
```

### In Agent Server

```python
from erc8004_common.config import BaseConfig
from erc8004_common.utils import Web3Utility
from erc8004_common.plugins import IdentityRegistryPlugin

class ServerConfig(BaseConfig):
    # Add server-specific fields
    server_port: int = 8080

config = ServerConfig()
utility = Web3Utility(config)
plugin = IdentityRegistryPlugin(utility, config)
plugin.initialize()
# Query operations (no private key needed)
agent = plugin.get_agent(agent_id)
```

### Message Signing and Verification

Sign and verify data using EIP-191 (Ethereum Signed Message):

```python
from erc8004_common.utils import Web3Utility

# Initialize with private key
config = Config(private_key="0x...")
utility = Web3Utility(config)

# Sign data
price_data = {"symbol": "BTC-USD", "price": 45000.50, "timestamp": "2025-10-09T12:00:00Z"}
signed = utility.sign_data(price_data)

# Returns: {"data": {...}, "signature": "0x...", "signer": "0x..."}
print(f"Signed by: {signed['signer']}")
print(f"Signature: {signed['signature']}")

# Verify signature
is_valid, recovered_address = utility.verify_signature(signed)
if is_valid:
    print(f"✅ Valid signature from {recovered_address}")
else:
    print("❌ Invalid signature")
```

### ROFL Attestation Verification

**Note**: Current implementation is a mock. Future versions will query Oasis Sapphire network.

```python
from erc8004_common.utils import verify_rofl_attestation

# Verify agent has valid ROFL TEE attestation
agent_address = "0x1234567890abcdef1234567890abcdef12345678"
is_valid = await verify_rofl_attestation(agent_address)

if is_valid:
    print("✅ Agent has valid ROFL attestation")
else:
    print("❌ Agent does not have valid attestation")
```

**Mock Configuration**:
```bash
# Optional: Configure mock to only validate specific addresses
export MOCK_VALID_ROFL_ADDRESSES="0xabc...,0xdef..."
```

## Installation

This package is designed for local development as part of the ERC-8004 playground monorepo.

In your application's `pyproject.toml`:

```toml
[project]
dependencies = [
    "erc8004-common",
]

[tool.uv.sources]
erc8004-common = { path = "../common", editable = true }
```

## Dependencies

- `web3>=7.6.0` - Ethereum interaction
- `pydantic>=2.10.0` - Data validation
- `pydantic-settings>=2.7.0` - Environment configuration
- `eth-account>=0.11.0` - Account and signing
- `eth-utils>=4.0.0` - Ethereum utilities

## License

MIT
