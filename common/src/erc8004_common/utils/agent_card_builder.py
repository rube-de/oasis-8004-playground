"""AgentCard builder with agent_config.json support.

This module provides AgentCardBuilder that constructs A2A Protocol v0.3.0
and ERC-8004 compliant AgentCards by combining:
- Static configuration from agent_config.json (skills, capabilities)
- Runtime state (agent_id, address, signatures)

"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from eth_account import Account
from eth_utils import to_checksum_address

from .agent_card import (
    AgentCard,
    Capabilities,
    Extension,
    Provider,
    Registration,
    Skill,
    format_caip10_address,
    sign_agent_registration,
)

logger = logging.getLogger(__name__)


class AgentConfigError(Exception):
    """Raised when agent_config.json is invalid or missing."""
    pass


class AgentCardBuilder:
    """Build AgentCards from agent_config.json + runtime state.

    Loads static agent configuration from agent_config.json and combines
    with runtime state (agent_id, address, chain_id) to generate complete
    A2A Protocol v0.3.0 and ERC-8004 compliant AgentCard.

    Example:
        >>> builder = AgentCardBuilder(
        ...     agent_id=1,
        ...     agent_address="0x1234...",
        ...     agent_domain="agent.local",
        ...     chain_id=31337,
        ...     account=account,
        ... )
        >>> builder.override_trust_models(["feedback"])  # Disable TEE for local mode
        >>> agent_card = builder.build()
    """

    def __init__(
        self,
        agent_id: int,
        agent_address: str,
        agent_domain: str,
        chain_id: int,
        account: Account,
        config_path: Optional[Path] = None,
    ):
        """Initialize builder with runtime state.

        Args:
            agent_id: Agent ID from Identity Registry
            agent_address: Agent's Ethereum address (will be checksummed)
            agent_domain: Agent domain (e.g., "agent.local")
            chain_id: Current chain ID
            account: Web3 Account for signature generation
            config_path: Path to agent_config.json (auto-detected if None)

        Raises:
            AgentConfigError: If agent_config.json not found or invalid
        """
        self.agent_id = agent_id
        self.agent_address = to_checksum_address(agent_address)
        self.agent_domain = agent_domain
        self.chain_id = chain_id
        self.account = account

        # Load agent_config.json
        if config_path is None:
            config_path = self._auto_detect_config_path()

        self.config = self._load_config(config_path)

        # Overrides (optional, can be set via methods)
        self._override_trust_models: Optional[List[str]] = None
        self._override_infrastructure: Optional[Dict[str, Any]] = None

        logger.debug(
            f"AgentCardBuilder initialized: "
            f"agent_id={agent_id}, domain={agent_domain}, chain_id={chain_id}"
        )

    def _auto_detect_config_path(self) -> Path:
        """Auto-detect agent_config.json location.

        Checks in order:
        1. /app/agent_config.json (Docker production)
        2. ./agent_config.json (local development)
        3. ../agent_config.json (running from subdirectory)

        Returns:
            Path to agent_config.json

        Raises:
            AgentConfigError: If file not found in any location
        """
        search_paths = [
            Path("/app/agent_config.json"),
            Path("./agent_config.json"),
            Path("../agent_config.json"),
        ]

        for path in search_paths:
            if path.exists():
                logger.info(f"Found agent_config.json at {path}")
                return path

        raise AgentConfigError(
            "agent_config.json not found. Searched: " +
            ", ".join(str(p) for p in search_paths)
        )

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load and validate agent_config.json.

        Args:
            config_path: Path to agent_config.json

        Returns:
            Parsed JSON configuration

        Raises:
            AgentConfigError: If file doesn't exist or has invalid format
        """
        if not config_path.exists():
            raise AgentConfigError(
                f"agent_config.json not found at {config_path}. "
                "Create this file to configure agent capabilities."
            )

        try:
            with open(config_path) as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise AgentConfigError(
                f"Invalid JSON in agent_config.json: {e}"
            ) from e
        except Exception as e:
            raise AgentConfigError(
                f"Failed to load agent_config.json: {e}"
            ) from e

        # Validate required fields
        required = ["name", "description", "skills", "capabilities"]
        missing = [field for field in required if field not in config]
        if missing:
            raise AgentConfigError(
                f"agent_config.json missing required fields: {', '.join(missing)}"
            )

        logger.info(
            f"Loaded agent config: name='{config['name']}', "
            f"skills={len(config['skills'])}"
        )

        return config

    def override_trust_models(self, models: List[str]) -> 'AgentCardBuilder':
        """Override trust models from config (for runtime adaptation).

        Use case: Disable tee-attestation when running in local mode.

        Args:
            models: List of trust models (e.g., ["feedback"], ["tee-attestation"])

        Returns:
            self for method chaining

        Example:
            >>> builder.override_trust_models(["feedback"])  # Local mode, no TEE
        """
        self._override_trust_models = models
        logger.debug(f"Trust models overridden: {models}")
        return self

    def override_infrastructure(
        self,
        hosting: str,
        tee_enabled: bool,
        attestation_provider: Optional[str] = None
    ) -> 'AgentCardBuilder':
        """Override infrastructure metadata (for runtime adaptation).

        Use case: Mark as local hosting when running in development mode.

        Args:
            hosting: Hosting provider (e.g., "oasis-sapphire", "local")
            tee_enabled: Whether TEE is enabled
            attestation_provider: TEE attestation provider (e.g., "rofl", None)

        Returns:
            self for method chaining

        Example:
            >>> builder.override_infrastructure("local", False, None)
        """
        self._override_infrastructure = {
            "hosting": hosting,
            "teeEnabled": tee_enabled,
            "attestationProvider": attestation_provider,
        }
        logger.debug(
            f"Infrastructure overridden: hosting={hosting}, tee={tee_enabled}"
        )
        return self

    def build(self) -> AgentCard:
        """Build complete AgentCard from config + runtime state.

        Combines static configuration from agent_config.json with runtime
        state to produce A2A Protocol v0.3.0 and ERC-8004 compliant AgentCard.

        Returns:
            Complete AgentCard instance ready for JSON serialization

        Example:
            >>> agent_card = builder.build()
            >>> agent_card_json = agent_card.to_dict()
        """
        logger.info(
            f"Building AgentCard for agent_id={self.agent_id}, "
            f"domain={self.agent_domain}"
        )

        # Parse capabilities from config
        capabilities = self._build_capabilities()

        # Parse skills from config
        skills = self._build_skills()

        # Build registration with signature
        registration = self._build_registration()

        # Determine trust models (override or from config)
        trust_models = (
            self._override_trust_models
            or self.config.get("supportedTrust", ["feedback"])
        )

        # Build provider (optional)
        provider = self._build_provider()

        # Build metadata (including infrastructure)
        metadata = self._build_metadata()

        # Construct AgentCard
        agent_card = AgentCard(
            protocolVersion=self.config.get("protocolVersion", "0.3.0"),
            name=self.config["name"],
            description=self.config["description"],
            version=self.config.get("version", "1.0.0"),
            url=f"http://{self.agent_domain}/api/v1",
            preferredTransport="JSONRPC",
            capabilities=capabilities,
            skills=skills,
            defaultInputModes=self.config.get("defaultInputModes", ["text"]),
            defaultOutputModes=self.config.get("defaultOutputModes", ["text"]),
            registrations=[registration],
            trustModels=trust_models,
            provider=provider,
            metadata=metadata,
        )

        logger.info(
            f"AgentCard built successfully: "
            f"skills={len(skills)}, trust={trust_models}"
        )

        return agent_card

    def _build_capabilities(self) -> Capabilities:
        """Build Capabilities from config.

        Returns:
            Capabilities instance with extensions
        """
        cap_config = self.config["capabilities"]

        extensions = []
        for ext_data in cap_config.get("extensions", []):
            extensions.append(Extension(
                uri=ext_data["uri"],
                description=ext_data["description"],
                required=ext_data.get("required", False),
                params=ext_data.get("params", {}),
            ))

        return Capabilities(
            streaming=cap_config.get("streaming", False),
            pushNotifications=cap_config.get("pushNotifications", False),
            stateTransitionHistory=cap_config.get("stateTransitionHistory", True),
            extensions=extensions,
        )

    def _build_skills(self) -> List[Skill]:
        """Build Skills from config.

        Returns:
            List of Skill instances
        """
        skills = []
        for skill_data in self.config["skills"]:
            skills.append(Skill(
                id=skill_data["id"],
                name=skill_data["name"],
                description=skill_data["description"],
                tags=skill_data.get("tags", []),
                inputModes=skill_data.get("inputModes", ["text"]),
                outputModes=skill_data.get("outputModes", ["text"]),
            ))

        logger.debug(f"Built {len(skills)} skills from config")
        return skills

    def _build_registration(self) -> Registration:
        """Build Registration with cryptographic signature.

        Generates CAIP-10 formatted address and EIP-191 signature proving
        ownership of the agent address.

        Returns:
            Registration instance with signature
        """
        caip10_address = format_caip10_address(self.chain_id, self.agent_address)

        signature = sign_agent_registration(
            self.agent_id,
            self.agent_address,
            self.agent_domain,
            self.account,
        )

        return Registration(
            agentId=self.agent_id,
            agentAddress=caip10_address,
            signature=signature,
        )

    def _build_provider(self) -> Optional[Provider]:
        """Build Provider from config (optional).

        Returns:
            Provider instance if configured, None otherwise
        """
        if "provider" not in self.config:
            return None

        p = self.config["provider"]
        return Provider(
            organization=p["organization"],
            url=p["url"]
        )

    def _build_metadata(self) -> Dict[str, Any]:
        """Build metadata dictionary including infrastructure details.

        Returns:
            Metadata dict with blockchain info and infrastructure
        """
        metadata = {
            "blockchain": "ethereum",
            "network": f"chain-{self.chain_id}",
            "erc8004_version": "1.0",
        }

        # Add infrastructure metadata (override or from config)
        infra = (
            self._override_infrastructure
            or self.config.get("infrastructure", {})
        )
        if infra:
            metadata["infrastructure"] = infra

        return metadata
