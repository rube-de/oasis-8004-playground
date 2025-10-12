"""Agent discovery utilities for ERC-8004 A2A protocol.

Implements agent discovery workflow:
1. Resolve blockchain address to domain via IdentityRegistry
2. Fetch AgentCard from RFC 8615 compliant endpoint
3. Parse and validate AgentCard structure
"""

import logging
from typing import Any

import httpx

from ..plugins.identity_registry import IdentityRegistryPlugin
from ..plugins.base import ContractCallError
from .agent_card import (
    AgentCard,
    Capabilities,
    Skill,
    Registration,
    Provider,
    Extension,
)

logger = logging.getLogger(__name__)


class AgentDiscoveryError(Exception):
    """Base exception for agent discovery errors."""

    pass


class AgentNotFoundError(AgentDiscoveryError):
    """Agent address not found in IdentityRegistry."""

    pass


class AgentCardFetchError(AgentDiscoveryError):
    """Failed to fetch AgentCard from domain."""

    pass


class AgentCardParseError(AgentDiscoveryError):
    """Failed to parse AgentCard JSON."""

    pass


async def fetch_agent_card(domain: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch AgentCard from RFC 8615 compliant endpoint.

    Fetches AgentCard from: http://{domain}/.well-known/agent-card.json

    Args:
        domain: Agent domain (e.g., "agent.example.com" or "agent-server:8001")
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Parsed AgentCard as dictionary

    Raises:
        AgentCardFetchError: If fetch fails (network error, 404, timeout)
        AgentCardParseError: If response is not valid JSON

    Example:
        >>> card = await fetch_agent_card("agent.example.com")
        >>> print(card["name"])
        "My Agent"
    """
    # Construct RFC 8615 compliant URL
    # Use http:// for Docker internal communication
    url = f"http://{domain}/.well-known/agent-card.json"

    logger.debug(f"Fetching AgentCard from: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)

            # Check for HTTP errors
            if response.status_code == 404:
                raise AgentCardFetchError(
                    f"AgentCard not found at {url} (404). "
                    f"Agent may not be registered or domain is incorrect."
                )

            response.raise_for_status()

            # Parse JSON
            try:
                agent_card = response.json()
                logger.debug(f"Successfully fetched AgentCard from {domain}")
                return agent_card

            except Exception as e:
                raise AgentCardParseError(
                    f"Invalid JSON in AgentCard response from {url}: {e}"
                ) from e

    except httpx.TimeoutException as e:
        raise AgentCardFetchError(
            f"Timeout fetching AgentCard from {url} (timeout={timeout}s)"
        ) from e

    except httpx.NetworkError as e:
        raise AgentCardFetchError(
            f"Network error fetching AgentCard from {url}: {e}. "
            f"Check that the domain is reachable and agent is running."
        ) from e

    except httpx.HTTPStatusError as e:
        raise AgentCardFetchError(
            f"HTTP error fetching AgentCard from {url}: {e.response.status_code}"
        ) from e

    except AgentCardFetchError:
        # Re-raise our custom exceptions
        raise

    except Exception as e:
        raise AgentCardFetchError(f"Unexpected error fetching AgentCard: {e}") from e


def parse_agent_card(agent_card_json: dict[str, Any]) -> AgentCard:
    """Parse AgentCard JSON into AgentCard dataclass.

    Args:
        agent_card_json: Raw AgentCard JSON dictionary

    Returns:
        Parsed AgentCard instance

    Raises:
        AgentCardParseError: If required fields are missing or invalid

    Example:
        >>> card_json = {"name": "Agent", "protocolVersion": "0.3.0", ...}
        >>> card = parse_agent_card(card_json)
        >>> print(card.name)
        "Agent"
    """
    try:
        # Parse extensions
        extensions_data = agent_card_json.get("capabilities", {}).get("extensions", [])
        extensions = [
            Extension(
                uri=ext["uri"],
                description=ext.get("description", ""),
                required=ext.get("required", False),
                params=ext.get("params", {}),
            )
            for ext in extensions_data
        ]

        # Parse capabilities
        capabilities_data = agent_card_json.get("capabilities", {})
        capabilities = Capabilities(
            streaming=capabilities_data.get("streaming", False),
            pushNotifications=capabilities_data.get("pushNotifications", False),
            stateTransitionHistory=capabilities_data.get("stateTransitionHistory", False),
            extensions=extensions,
        )

        # Parse skills
        skills_data = agent_card_json.get("skills", [])
        skills = [
            Skill(
                id=skill["id"],
                name=skill["name"],
                description=skill.get("description", ""),
                tags=skill.get("tags", []),
                inputModes=skill.get("inputModes", ["text"]),
                outputModes=skill.get("outputModes", ["text"]),
            )
            for skill in skills_data
        ]

        # Parse registrations
        registrations_data = agent_card_json.get("registrations", [])
        registrations = [
            Registration(
                agentId=reg["agentId"],
                agentAddress=reg["agentAddress"],
                signature=reg["signature"],
            )
            for reg in registrations_data
        ]

        # Parse optional provider
        provider_data = agent_card_json.get("provider")
        provider = None
        if provider_data:
            provider = Provider(
                organization=provider_data["organization"],
                url=provider_data["url"],
            )

        # Create AgentCard
        return AgentCard(
            protocolVersion=agent_card_json["protocolVersion"],
            name=agent_card_json["name"],
            description=agent_card_json["description"],
            version=agent_card_json["version"],
            url=agent_card_json["url"],
            preferredTransport=agent_card_json["preferredTransport"],
            capabilities=capabilities,
            skills=skills,
            defaultInputModes=agent_card_json.get("defaultInputModes", ["text"]),
            defaultOutputModes=agent_card_json.get("defaultOutputModes", ["text"]),
            registrations=registrations,
            trustModels=agent_card_json.get("trustModels", []),
            provider=provider,
            ValidationRequestsURI=agent_card_json.get("ValidationRequestsURI"),
            ValidationResponsesURI=agent_card_json.get("ValidationResponsesURI"),
            metadata=agent_card_json.get("metadata", {}),
        )

    except KeyError as e:
        raise AgentCardParseError(
            f"Missing required field in AgentCard: {e}"
        ) from e

    except Exception as e:
        raise AgentCardParseError(
            f"Failed to parse AgentCard: {e}"
        ) from e


async def discover_agent_by_id(
    agent_id: int,
    identity_plugin: IdentityRegistryPlugin,
) -> AgentCard:
    """Discover agent by ID using v1.0 tokenURI-based flow.

    ERC-8004 v1.0 discovery workflow:
    1. Get tokenURI from IdentityRegistry (points to AgentCard URL)
    2. Fetch AgentCard from tokenURI
    3. Parse and validate AgentCard

    Args:
        agent_id: Agent ID from IdentityRegistry
        identity_plugin: Initialized IdentityRegistryPlugin instance

    Returns:
        Parsed and validated AgentCard

    Raises:
        AgentNotFoundError: If agent ID doesn't exist
        AgentCardFetchError: If fetching AgentCard fails
        AgentCardParseError: If AgentCard parsing fails

    Example:
        >>> plugin = IdentityRegistryPlugin(web3_utility, config)
        >>> plugin.initialize()
        >>> card = await discover_agent_by_id(42, plugin)
        >>> print(card.name)
        "Server Agent"
        >>> print(card.skills[0].name)
        "Price Fetching"
    """
    logger.info(f"🔍 Discovering agent ID: {agent_id}")

    # Step 1: Get tokenURI from IdentityRegistry (v1.0)
    try:
        token_uri = identity_plugin.token_uri(agent_id)

        if not token_uri:
            raise AgentNotFoundError(
                f"Agent {agent_id} has no tokenURI set. "
                f"Agent may not be fully registered or discovery info unavailable."
            )

        logger.info(f"✅ Found tokenURI: {token_uri}")

    except ContractCallError as e:
        raise AgentNotFoundError(
            f"Agent ID {agent_id} not found in IdentityRegistry"
        ) from e

    # Step 2: Extract domain from tokenURI and fetch AgentCard
    # tokenURI format: http://{domain}/.well-known/agent-card.json
    try:
        # Parse domain from tokenURI
        if "://" in token_uri:
            # Remove protocol
            domain_with_path = token_uri.split("://", 1)[1]
            # Extract domain (everything before first /)
            domain = domain_with_path.split("/", 1)[0]
        else:
            # Assume it's already just domain
            domain = token_uri.split("/", 1)[0]

        logger.debug(f"Extracted domain from tokenURI: {domain}")

        # Fetch AgentCard from domain
        agent_card_json = await fetch_agent_card(domain)

    except Exception as e:
        raise AgentCardFetchError(
            f"Failed to fetch AgentCard from tokenURI '{token_uri}': {e}"
        ) from e

    # Step 3: Parse AgentCard
    agent_card = parse_agent_card(agent_card_json)

    logger.info(f"✅ Successfully discovered agent: {agent_card.name} (ID: {agent_id})")

    return agent_card


