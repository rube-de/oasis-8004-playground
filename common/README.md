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

- `ContractUtility`: Web3 contract interaction layer
  - ABI loading from Hardhat artifacts
  - Transaction signing middleware
  - Contract instance creation
- Utility exceptions: `ContractUtilityError`, `ABILoadError`, `ConnectionError`

### Configuration (`erc8004_common.config`)

- `BaseConfig`: Base configuration class with shared settings
  - RPC URL and network configuration
  - Registry contract addresses
  - Operational settings (gas, timeouts, logging)

## Usage

### In Agent Client

```python
from erc8004_common.config import BaseConfig
from erc8004_common.utils import ContractUtility
from erc8004_common.plugins import IdentityRegistryPlugin

class ClientConfig(BaseConfig):
    # Add client-specific fields
    private_key: str
    agent_domain: str

config = ClientConfig()
utility = ContractUtility(config)
plugin = IdentityRegistryPlugin(utility, config)
plugin.initialize()
agent_id = plugin.register()
```

### In Agent Server

```python
from erc8004_common.config import BaseConfig
from erc8004_common.utils import ContractUtility
from erc8004_common.plugins import IdentityRegistryPlugin

class ServerConfig(BaseConfig):
    # Add server-specific fields
    server_port: int = 8080

config = ServerConfig()
utility = ContractUtility(config)
plugin = IdentityRegistryPlugin(utility, config)
plugin.initialize()
# Query operations (no private key needed)
agent = plugin.get_agent(agent_id)
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
