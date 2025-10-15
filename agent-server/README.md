# ERC-8004 Agent Server

Modern Python application implementing an ERC-8004 compliant agent server with Identity Registry integration.

## Overview

This agent server provides:
- **Identity Registration**: Register agent server with IdentityRegistry contract
- **A2A AgentCard Generation**: Automatic generation of A2A Protocol v0.3.0 and ERC-8004 compliant AgentCards with CAIP-10 addresses
- **FastAPI Server**: RFC 8615 compliant AgentCard hosting at `/.well-known/agent-card.json` with CORS support
- **Plugin Architecture**: Extensible design for future Reputation and Validation registries
- **Long-Running Operation**: Continuous agent lifecycle with state persistence
- **Docker-Native**: Built for containerized deployment

## 🔒 Deployment Modes

The agent server supports two deployment modes for key management:

### ROFL Mode (Default, Production) 🔒

**Secure by default.** Keys are generated within a Trusted Execution Environment (TEE) via Oasis ROFL.

**Key Features:**
- ✅ **TEE Security**: Private keys generated and stored in hardware-isolated TEE
- ✅ **No Env Var Keys**: No private keys in environment variables or config files
- ✅ **TEE Attestation**: Cryptographic proof of secure execution
- ✅ **Key Persistence**: Keys persist across restarts using agent domain as key-id
- ✅ **Production Ready**: Designed for production deployments

**Requirements:**
- ROFL service (rofl-appd) running on host
- ROFL Unix socket accessible at `/run/rofl-appd.sock`
- `AGENT_DOMAIN` configured (used as ROFL key-id)

**Usage:**
```bash
# Copy and configure production environment
cp .env.example .env
vim .env  # No PRIVATE_KEY needed!

# Run with production compose (ROFL mode is automatic)
docker-compose up --build
```

### Local Mode (Development Only) 🔓

**Explicit opt-in for local development.** Uses private keys from environment variables.

**Key Features:**
- ⚠️  **Dev Only**: NOT recommended for production
- ✅ **Simple Setup**: No ROFL infrastructure needed
- ✅ **Quick Iteration**: Fast local testing with known keys
- ⚠️  **Less Secure**: Private keys stored as plaintext in environment

**Requirements:**
- Private key in environment variables
- `USE_LOCAL_MODE=true` flag set

**Usage:**
```bash
# Copy and configure local environment
cp .env.example.local .env.local
vim .env.local  # Set USE_LOCAL_MODE=true and PRIVATE_KEY

# Run with local compose file
docker-compose -f docker-compose.local.yml up --build
```

### Mode Comparison

| Feature | ROFL Mode (Default) | Local Mode (Opt-in) |
|---------|---------------------|---------------------|
| **Security** | 🔒 High (TEE) | ⚠️ Low (env vars) |
| **Production Ready** | ✅ Yes | ❌ No |
| **Private Key in Env** | ❌ No | ⚠️ Yes (required) |
| **TEE Attestation** | ✅ Available | ❌ Not available |
| **ROFL Service Required** | ✅ Yes | ❌ No |
| **Setup Complexity** | Medium | Simple |
| **Key Persistence** | ✅ Automatic | Manual |
| **Use Case** | Production deployment | Local development |

**Security Recommendation:** Always use ROFL mode for production deployments. Only use local mode for development on trusted local machines.

## Prerequisites

- Docker and Docker Compose
- Compiled smart contracts (hardhat artifacts at `../contracts/artifacts/`)
- Running Ethereum node or RPC endpoint
- **For ROFL mode (production)**: ROFL service (rofl-appd) running on host
- **For local mode (development)**: Private key for testing

## Quick Start

> **Note:** This quick start uses **Local Mode** for simplicity. For production deployments, see [ROFL Mode](#rofl-mode-default-production-) above.

### 1. Configure Environment (Local Mode)

Copy the local example environment file:

```bash
cp .env.example.local .env.local
```

Edit `.env.local` with your configuration:

```env
# Required: Enable local development mode
USE_LOCAL_MODE=true

# Required: Network configuration
RPC_URL=http://localhost:8545
IDENTITY_REGISTRY_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
AGENT_DOMAIN=localhost

# Required: Development private key (64 hex chars, no 0x)
PRIVATE_KEY=your_development_private_key_here

# Optional
LOG_LEVEL=DEBUG
API_PORT=8001
```

**Security Note**: Never use production keys in local mode!

### 2. Build Docker Image

Build the Docker image (from agent-server directory):

```bash
docker-compose -f docker-compose.local.yml build
```

**Note**: Rebuild when contracts change to update bundled ABIs.

### 3. Run Agent (Local Mode)

```bash
docker-compose -f docker-compose.local.yml up
```

Or run in detached mode:

```bash
docker-compose -f docker-compose.local.yml up -d
```

### 4. View Logs

```bash
docker-compose -f docker-compose.local.yml logs -f agent-server
```

### 5. Stop Agent

```bash
docker-compose down
```

## Expected Output

### First Run (Registration)

```
INFO - Starting ERC-8004 Agent Server
INFO - Loading configuration from environment
INFO - Initializing Web3 utility
INFO - Loading IdentityRegistryPlugin
INFO - Checking existing registration state...
INFO - No existing registration found. Proceeding with registration.
INFO - Registering agent with domain: server.localhost
INFO - Transaction sent: 0xabc...def
INFO - Waiting for confirmation...
INFO - Agent registered successfully!
INFO - Agent ID: 2
INFO - Domain: server.localhost
INFO - Address: 0x789...012
INFO - Transaction: 0xabc...def
INFO - Agent state persisted to: /app/data/agent_state.json
INFO - AgentCard saved to /app/data/agent-card.json
INFO - Starting API server on port 8001
INFO - API server started successfully on http://0.0.0.0:8001
INFO -   AgentCard: http://localhost:8001/.well-known/agent-card.json
INFO -   Health: http://localhost:8001/health
INFO - Agent running and ready for operations...
INFO - Heartbeat: Agent operational (ID: 2)
```

### Subsequent Runs (Already Registered)

```
INFO - Starting ERC-8004 Agent Server
INFO - Loading configuration from environment
INFO - Checking existing registration state...
INFO - Agent already registered with ID: 2
INFO - Skipping registration.
INFO - Agent running and ready for operations...
INFO - Heartbeat: Agent operational (ID: 2)
```

## Configuration Reference

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `RPC_URL` | Ethereum RPC endpoint | `http://localhost:8545` |
| `PRIVATE_KEY` | Private key for signing (no 0x prefix) | `your_server_private_key_here` |
| `IDENTITY_REGISTRY_ADDRESS` | Deployed contract address | `0x5FbDB...` |
| `AGENT_DOMAIN` | RFC 8615 compliant domain | `server.localhost` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `GAS_MULTIPLIER` | Gas estimation safety margin | `1.2` |
| `TX_TIMEOUT` | Transaction timeout (seconds) | `120` |
| `AGENT_NAME` | Custom agent name for AgentCard | `ERC-8004 Agent {id}` |
| `AGENT_DESCRIPTION` | Custom agent description | Auto-generated |
| `AGENT_VERSION` | Agent version (semantic versioning) | `1.0.0` |
| `API_PORT` | Port for API server | `8001` |

## Architecture

```
src/
   main.py                    # Application entry point
   agent.py                   # Main orchestrator
   config.py                  # Pydantic configuration
   api_server.py              # FastAPI server
```

### Key Components

- **Web3Utility**: Abstraction for Web3 contract interactions, ABI loading, message signing (from common package)
- **Plugin System**: Modular registry integrations (Identity, Reputation, Validation)
- **Agent**: Orchestrates registration, lifecycle, state persistence
- **Config**: Type-safe Pydantic configuration with validation

## AgentCard Generation

After successful registration, the agent automatically generates an **A2A Protocol v0.3.0 and ERC-8004 compliant AgentCard** saved to `/app/data/agent-card.json`.

### AgentCard Features

- **A2A Protocol Compliance**: Implements protocolVersion 0.3.0 with all required fields
- **ERC-8004 Extensions**: Includes blockchain registrations with CAIP-10 formatted addresses
- **Cryptographic Signatures**: Proves ownership of agent address via Ethereum personal_sign
- **Trust Models**: Declares supported trust mechanisms (feedback, tee-attestation)
- **Skills Definition**: Structured list of agent capabilities
- **RFC 8615 Ready**: Designed for hosting at `/.well-known/agent-card.json`

### AgentCard Structure

```json
{
  "protocolVersion": "0.3.0",
  "name": "ERC-8004 Agent 2",
  "description": "ERC-8004 compliant autonomous agent server with identity registration capabilities",
  "version": "1.0.0",
  "url": "https://server.localhost/api/v1",
  "preferredTransport": "JSONRPC",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true,
    "extensions": [
      {
        "uri": "https://erc8004.ethereum.org/extensions/validation",
        "description": "ERC-8004 Validation Registry support"
      }
    ]
  },
  "skills": [
    {
      "id": "identity.register",
      "name": "Identity Registration",
      "description": "Register agent in ERC-8004 Identity Registry",
      "tags": ["identity", "registration", "blockchain"]
    },
    {
      "id": "identity.resolve",
      "name": "Identity Resolution",
      "description": "Resolve agent identities by ID, address, or domain",
      "tags": ["identity", "discovery", "blockchain"]
    },
    {
      "id": "price.fetch",
      "name": "Cryptocurrency Price Fetching",
      "description": "Fetch real-time cryptocurrency prices from Binance",
      "tags": ["price", "cryptocurrency", "binance", "market-data"]
    }
  ],
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  "registrations": [
    {
      "agentId": 2,
      "agentAddress": "eip155:31337:0x789...",
      "signature": "0xabcdef..."
    }
  ],
  "trustModels": ["feedback", "tee-attestation"],
  "provider": {
    "organization": "Oasis Protocol",
    "url": "https://oasisprotocol.org"
  },
  "metadata": {
    "blockchain": "ethereum",
    "network": "chain-31337",
    "erc8004_version": "1.0"
  }
}
```

### CAIP-10 Address Format

Agent addresses follow [CAIP-10](https://github.com/ChainAgnostic/CAIPs/blob/master/CAIPs/caip-10.md) chain-agnostic format:

```
eip155:{chainId}:{address}
```

Examples:
- Mainnet: `eip155:1:0x1234...5678`
- Hardhat: `eip155:31337:0x1234...5678`
- Oasis Sapphire: `eip155:23294:0x1234...5678`

## API Server

The agent automatically starts a **FastAPI server** on port 8001 to serve the AgentCard and provide API endpoints.

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | RFC 8615 compliant AgentCard (A2A Protocol v0.3.0) |
| `/health` | GET | Health check endpoint for monitoring |
| `/api/v1/agent` | GET | Agent registration information |
| `/api/v1/skills/price` | POST | Fetch cryptocurrency price from Binance |
| `/` | GET | API metadata and available endpoints |
| `/api/docs` | GET | Interactive API documentation (Swagger UI) |

### Accessing the AgentCard

Once the agent is running, access the AgentCard via:

```bash
# Using curl
curl http://localhost:8001/.well-known/agent-card.json

# Or visit in browser
open http://localhost:8001/.well-known/agent-card.json
```

### API Examples

**Get Agent Information:**
```bash
curl http://localhost:8001/api/v1/agent
```

**Response:**
```json
{
  "agent_id": 2,
  "domain": "server.localhost",
  "address": "0x789...",
  "registered_at": 1234567890.123
}
```

**Health Check:**
```bash
curl http://localhost:8001/health
```

**Response:**
```json
{
  "status": "healthy"
}
```

**Get Cryptocurrency Price:**
```bash
# BTC-USD format
curl -X POST http://localhost:8001/api/v1/skills/price \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC-USD"}'

# BTCUSDT format (native Binance format)
curl -X POST http://localhost:8001/api/v1/skills/price \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT"}'

# ETH-USD
curl -X POST http://localhost:8001/api/v1/skills/price \
  -H "Content-Type: application/json" \
  -d '{"symbol": "ETH-USD"}'
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "price": 45000.50,
  "timestamp": "2025-10-07T12:34:56.789Z"
}
```

**Error Responses:**

Invalid symbol (400):
```json
{
  "detail": "Symbol INVALIDUSD not found on Binance. Check symbol format (e.g., BTC-USD, ETHUSDT)."
}
```

Rate limit exceeded (429):
```json
{
  "detail": "Binance API rate limit exceeded. Please try again later."
}
```

Network error (503):
```json
{
  "detail": "Failed to connect to Binance API: Connection timeout"
}
```

### CORS Support

The API server includes CORS middleware allowing cross-origin requests for agent discovery. This enables other agents to discover and interact with your agent from any domain.

### Interactive Documentation

FastAPI provides automatic interactive documentation:
- Swagger UI: http://localhost:8001/api/docs
- ReDoc: http://localhost:8001/api/redoc

## Docker Details

### Image Structure

- **Base**: `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`
- **ABIs**: Bundled from hardhat artifacts at build time
- **User**: Runs as non-root user `agent` (UID 1000)
- **Workdir**: `/app`
- **Health Check**: HTTP-based check via API server

### Build Context

The build context is the parent directory to access compiled contracts:

```
parent/
   contracts/
      artifacts/          # Copied into image
   agent-server/
       Dockerfile
       docker-compose.yml
       src/                # Copied into image
```

### State Persistence

Agent state and AgentCard are saved to `/app/data/`:
- `agent_state.json` - Agent ID, domain, address, timestamp
- `agent-card.json` - A2A and ERC-8004 compliant AgentCard

To persist across rebuilds:

1. Add volume to `docker-compose.yml`:
   ```yaml
   volumes:
     - ./data:/app/data
   ```

2. Restart service:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

The agent-card.json file is automatically regenerated after registration if missing.

## Running Multiple Agents

You can run both agent-client and agent-server simultaneously:

```bash
# Start both agents (from parent directory)
docker-compose -f agent-client/docker-compose.yml up -d
docker-compose -f agent-server/docker-compose.yml up -d

# View logs
docker-compose -f agent-client/docker-compose.yml logs -f
docker-compose -f agent-server/docker-compose.yml logs -f

# Stop both
docker-compose -f agent-client/docker-compose.yml down
docker-compose -f agent-server/docker-compose.yml down
```

Each agent will:
- Register with a unique agent ID
- Use its own private key and address
- Run on its own port (8000 for client, 8001 for server)
- Maintain separate state files

## Troubleshooting

### "Connection refused" Error

**Cause**: Cannot connect to RPC endpoint

**Solution**:
- Verify hardhat node is running
- Check `RPC_URL` in `.env`
- Ensure Docker network connectivity

### "Contract not found" Error

**Cause**: Invalid contract address or wrong network

**Solution**:
- Verify `IDENTITY_REGISTRY_ADDRESS` matches deployed contract
- Ensure hardhat node has contract deployed
- Check network matches (chain ID)

### "Transaction reverted" Error

**Cause**: Contract rejected transaction

**Solution**:
- Check agent isn't already registered with same domain
- Verify private key has sufficient balance
- Check contract state and permissions

### ABIs Not Found

**Cause**: Docker image built without compiled artifacts

**Solution**:
1. Compile contracts: `cd ../contracts && npx hardhat compile`
2. Rebuild image: `docker-compose build --no-cache`

### Container Exits Immediately

**Cause**: Configuration error or initialization failure

**Solution**:
- Check logs: `docker-compose logs agent-server`
- Verify all required env vars are set
- Ensure `.env` file exists

### Port 8001 Already in Use

**Cause**: Another service is using port 8001

**Solution**:
1. Change port in docker-compose.yml:
   ```yaml
   ports:
     - "8002:8001"  # Map host port 8002 to container port 8001
   ```
2. Or set `API_PORT=8002` in `.env` and update docker-compose.yml:
   ```yaml
   ports:
     - "8002:8002"
   ```

### AgentCard Not Accessible

**Cause**: API server failed to start or AgentCard file missing

**Solution**:
- Check logs for API server startup messages
- Verify AgentCard exists: `docker exec erc8004-agent-server ls -la /app/data/`
- Test health endpoint: `curl http://localhost:8001/health`
- If agent not registered, AgentCard won't exist yet

## Development

### Local Execution

This application is designed for Docker-only deployment. For local development:

1. Install dependencies:
   ```bash
   uv sync --dev
   ```

2. Run directly (requires compiled contracts at `../contracts/artifacts/`):
   ```bash
   uv run python -m src.main
   ```

   Or:
   ```bash
   uv run agent-server
   ```

### Updating Contracts

When contracts change:

1. Recompile contracts
2. Rebuild Docker image: `docker-compose build`
3. Restart container: `docker-compose up -d`

## Future Extensions

### Phase 2: Reputation Registry
- Implement `ReputationRegistryPlugin`
- Add feedback authorization and submission
- Display reputation metrics

### Phase 3: Validation Registry
- Implement `ValidationRegistryPlugin`
- Support validation requests and responses
- Track validation state
- Accept task submissions from clients

### Phase 4: ROFL Integration
- TEE attestation support
- Off-chain compute integration
- Cryptographic proof generation

## Security Notes

� **Development Only**: Current setup uses plaintext private keys in `.env`

For production:
- Use hardware wallets or key management services
- Implement secret management (HashiCorp Vault, AWS Secrets Manager)
- Enable TLS for RPC connections
- Rotate keys regularly

## Resources

- [ERC-8004 Specification](https://eips.ethereum.org/EIPS/eip-8004)
- [RFC 8615: Well-Known URIs](https://tools.ietf.org/html/rfc8615)
- [Web3.py Documentation](https://web3py.readthedocs.io/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

## License

See parent repository for license information.
