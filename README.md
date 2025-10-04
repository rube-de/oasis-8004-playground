# ERC-8004 on Oasis Network Playground

Experimental playground for exploring ERC-8004 (Trustless Agents) implementations on Oasis Network with ROFL integration.

## Project Structure

```
.
├── common/                # Shared ERC-8004 infrastructure
├── contracts/             # Solidity contracts (IdentityRegistry, etc.)
├── agent-client/          # ERC-8004 agent client implementation
├── agent-server/          # Future: Agent server for task execution
└── agent-validator/       # Future: Validation service with ROFL
```

## Components

- **[common/](common/)** - Shared plugins, utilities, and config for all agents
- **[agent-client/](agent-client/)** - MVP agent that registers with Identity Registry
- **[contracts/](contracts/)** - ERC-8004 registry smart contracts

## Quick Start

### Run Agent Client

```bash
cd agent-client
cp .env.example .env
# Edit .env with your configuration
docker-compose up --build
```

## Resources

### ERC-8004
- [Specification](https://eips.ethereum.org/EIPS/eip-8004)
- [Discussion](https://ethereum-magicians.org/t/erc-8004-trustless-agents/25098)
- [Phala Implementation](https://github.com/HashWarlock/erc-8004-ex-phala)
- [ChaosChain Implementation](https://github.com/ChaosChain/chaoschain-genesis-studio)

### Oasis ROFL
- [Overview](https://docs.oasis.io/build/rofl/)
- [Features](https://docs.oasis.io/build/rofl/features)
- [Demo](https://github.com/oasisprotocol/rofl-paymaster)

## License

MIT
