# ERC-8004 Agent Server Dockerfile
# Base image with pre-installed uv package manager
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set working directory
WORKDIR /app

# Create abis directory for contract artifacts
RUN mkdir -p /app/abis

# Copy hardhat compiled artifacts from build context
# These will be copied from ../contracts/artifacts/contracts/*/ContractName.json
COPY contracts/artifacts/contracts/IdentityRegistry.sol/IdentityRegistry.json /app/abis/
COPY contracts/artifacts/contracts/ReputationRegistry.sol/ReputationRegistry.json /app/abis/
COPY contracts/artifacts/contracts/ValidationRegistry.sol/ValidationRegistry.json /app/abis/

# Copy common package (dependency) BEFORE pyproject.toml
COPY common/ /app/common/

# Copy dependency declarations
COPY agent-server/pyproject.toml /app/

# Generate lock file in Docker environment with correct paths
RUN uv lock

# Install dependencies from generated lock file
RUN uv sync --frozen --no-dev

# Copy application source code
COPY agent-server/src/ /app/src/

# Copy agent configuration
COPY agent-server/agent_config.json /app/agent_config.json

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash agent && \
    chown -R agent:agent /app

# Switch to non-root user
USER agent

# Expose API server port (8001 for server)
EXPOSE 8001

# Configure signal handling for graceful shutdown
STOPSIGNAL SIGTERM

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Run application using uv run (activates virtual environment automatically)
CMD ["uv", "run", "python", "-m", "src.main"]
