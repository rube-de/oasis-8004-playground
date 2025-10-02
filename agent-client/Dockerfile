# ERC-8004 Agent Client Dockerfile
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

# Copy dependency declarations
COPY agent-client/pyproject.toml agent-client/uv.lock /app/

# Install dependencies using pre-installed uv
# --frozen ensures reproducible builds from uv.lock (fails if lock is out of sync)
# --no-dev excludes development dependencies
RUN uv sync --frozen --no-dev

# Copy application source code
COPY agent-client/src/ /app/src/

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash agent && \
    chown -R agent:agent /app

# Switch to non-root user
USER agent

# Add health check
# Verifies Python can import main module (using uv's virtual environment)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python -c "import src.main" || exit 1

# Configure signal handling for graceful shutdown
STOPSIGNAL SIGTERM

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Run application using uv run (activates virtual environment automatically)
CMD ["uv", "run", "python", "-m", "src.main"]
