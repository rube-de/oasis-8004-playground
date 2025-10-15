# ERC-8004 Common Infrastructure

Shared components for ERC-8004 agent implementations.

## Components

### Plugins (`erc8004_common.plugins`)

- `BaseRegistryPlugin` - Abstract base for registry plugins
- `IdentityRegistryPlugin` - Identity Registry operations
- Exceptions: `PluginError`, `PluginInitializationError`, `TransactionError`, `ContractCallError`

### Utilities (`erc8004_common.utils`)

- `ContractUtility` - Web3 contract interactions, ABI loading, transaction signing
- Agent Discovery - ERC-8004 v1.0 compliant agent discovery via tokenURI
- Message Signing - EIP-191 signing and verification
- ROFL Attestation - TEE attestation verification (mock)

### Configuration (`erc8004_common.config`)

- `BaseConfig` - Shared configuration for RPC, registry addresses, operational settings

## Usage

### Client (with signing)

```python
from erc8004_common.config import BaseConfig
from erc8004_common.utils import ContractUtility
from erc8004_common.plugins import IdentityRegistryPlugin

class ClientConfig(BaseConfig):
    private_key: str
    agent_domain: str

config = ClientConfig()
utility = ContractUtility(config)
plugin = IdentityRegistryPlugin(utility, config)
plugin.initialize()
agent_id = plugin.register()
```

### Server (read-only)

```python
class ServerConfig(BaseConfig):
    server_port: int = 8080

config = ServerConfig()
utility = ContractUtility(config)  # No private key = read-only
plugin = IdentityRegistryPlugin(utility, config)
plugin.initialize()
agent = plugin.get_agent(agent_id)
```

## Installation

In your application's `pyproject.toml`:

```toml
[project]
dependencies = ["erc8004-common"]

[tool.uv.sources]
erc8004-common = { path = "./common", editable = true }
```

## Dependencies

- `web3>=7.6.0`
- `pydantic>=2.10.0`
- `pydantic-settings>=2.7.0`
- `eth-account>=0.11.0`
- `eth-utils>=4.0.0`

## License

MIT
