"""Agent discovery utilities for ERC-8004 A2A protocol.

Implements ERC-8004 v1.0 agent discovery workflow:
1. Resolve agent ID to tokenURI via IdentityRegistry (points to registration JSON)
2. Fetch registration JSON from tokenURI (/agent.json) - registration-v1 format
3. Extract A2A endpoint from registration JSON
4. Fetch AgentCard from A2A endpoint (/.well-known/agent-card.json)
5. Parse and validate AgentCard structure

This two-step process ensures proper separation between:
- Registration metadata (minimal, for on-chain identity)
- Agent card (full capabilities, for A2A protocol discovery)
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


async def fetch_registration_json(url: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch ERC-8004 registration JSON from tokenURI.

    Fetches registration-v1 format from tokenURI endpoint.
    This is the first step in the ERC-8004 v1.0 discovery workflow.

    Args:
        url: Full tokenURI URL (e.g., "http://agent-server:80/agent.json")
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Parsed registration JSON dictionary

    Raises:
        AgentCardFetchError: If fetch fails (network error, 404, timeout)
        AgentCardParseError: If response is not valid JSON

    Example:
        >>> registration = await fetch_registration_json("http://domain/agent.json")
        >>> print(registration["type"])
        "https://eips.ethereum.org/EIPS/eip-8004#registration-v1"
    """
    logger.debug(f"Fetching registration JSON from: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)

            # Check for HTTP errors
            if response.status_code == 404:
                raise AgentCardFetchError(
                    f"Registration metadata not found at {url} (404). "
                    f"Agent may not be registered or tokenURI is incorrect."
                )

            response.raise_for_status()

            # Parse JSON
            try:
                registration_json = response.json()
                logger.debug(
                    f"Successfully fetched registration JSON: "
                    f"type={registration_json.get('type', 'unknown')}"
                )
                return registration_json

            except Exception as e:
                raise AgentCardParseError(
                    f"Invalid JSON in registration response from {url}: {e}"
                ) from e

    except httpx.TimeoutException as e:
        raise AgentCardFetchError(
            f"Timeout fetching registration from {url} (timeout={timeout}s)"
        ) from e

    except httpx.NetworkError as e:
        raise AgentCardFetchError(
            f"Network error fetching registration from {url}: {e}. "
            f"Check that the URL is reachable."
        ) from e

    except httpx.HTTPStatusError as e:
        raise AgentCardFetchError(
            f"HTTP error fetching registration from {url}: {e.response.status_code}"
        ) from e

    except AgentCardFetchError:
        # Re-raise our custom exceptions
        raise

    except Exception as e:
        raise AgentCardFetchError(
            f"Unexpected error fetching registration: {e}"
        ) from e


def extract_agent_card_url(registration_json: dict[str, Any]) -> str:
    """Extract agent card URL from registration JSON.

    Parses registration-v1 format and finds the A2A endpoint.
    This is the second step in the ERC-8004 v1.0 discovery workflow.

    Args:
        registration_json: Parsed registration JSON (registration-v1 format)

    Returns:
        Agent card URL (e.g., "http://domain/.well-known/agent-card.json")

    Raises:
        AgentCardParseError: If A2A endpoint not found or registration format invalid

    Example:
        >>> registration = {
        ...     "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        ...     "endpoints": [
        ...         {"name": "A2A", "endpoint": "http://domain/.well-known/agent-card.json"},
        ...         {"name": "agentWallet-Sepolia", "endpoint": "eip155:11155111:0x..."}
        ...     ]
        ... }
        >>> url = extract_agent_card_url(registration)
        >>> print(url)
        'http://domain/.well-known/agent-card.json'
    """
    try:
        endpoints = registration_json.get("endpoints", [])

        if not endpoints:
            raise AgentCardParseError(
                "Registration JSON missing 'endpoints' field. "
                "Cannot discover agent card URL."
            )

        # Find endpoint with name="A2A"
        for endpoint in endpoints:
            if endpoint.get("name") == "A2A":
                agent_card_url = endpoint.get("endpoint")

                if not agent_card_url:
                    raise AgentCardParseError(
                        "A2A endpoint found but 'endpoint' field is missing or empty"
                    )

                logger.debug(f"Extracted A2A endpoint: {agent_card_url}")
                return agent_card_url

        # No A2A endpoint found
        endpoint_names = [ep.get("name", "unknown") for ep in endpoints]
        raise AgentCardParseError(
            f"No A2A endpoint found in registration metadata. "
            f"Available endpoints: {endpoint_names}. "
            f"Registration may be incomplete or malformed."
        )

    except AgentCardParseError:
        # Re-raise our custom exceptions
        raise

    except Exception as e:
        raise AgentCardParseError(
            f"Failed to extract agent card URL from registration: {e}"
        ) from e


async def fetch_agent_card_from_url(url: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch AgentCard from full URL.

    Fetches AgentCard directly from a complete URL.
    This is the third step in the ERC-8004 v1.0 discovery workflow.

    Args:
        url: Full agent card URL (e.g., "http://domain/.well-known/agent-card.json")
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Parsed AgentCard dictionary

    Raises:
        AgentCardFetchError: If fetch fails (network error, 404, timeout)
        AgentCardParseError: If response is not valid JSON

    Example:
        >>> card = await fetch_agent_card_from_url("http://domain/.well-known/agent-card.json")
        >>> print(card["name"])
        "My Agent"
    """
    logger.debug(f"Fetching AgentCard from URL: {url}")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)

            # Check for HTTP errors
            if response.status_code == 404:
                raise AgentCardFetchError(
                    f"AgentCard not found at {url} (404). "
                    f"Agent may not have published their agent card yet."
                )

            response.raise_for_status()

            # Parse JSON
            try:
                agent_card = response.json()
                logger.debug(
                    f"Successfully fetched AgentCard: name={agent_card.get('name', 'unknown')}"
                )
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
            f"Network error fetching AgentCard from {url}: {e}"
        ) from e

    except httpx.HTTPStatusError as e:
        raise AgentCardFetchError(
            f"HTTP error fetching AgentCard from {url}: {e.response.status_code}"
        ) from e

    except AgentCardFetchError:
        # Re-raise our custom exceptions
        raise

    except Exception as e:
        raise AgentCardFetchError(
            f"Unexpected error fetching AgentCard: {e}"
        ) from e


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
    """Discover agent by ID using v1.0 two-step tokenURI flow.

    ERC-8004 v1.0 discovery workflow:
    1. Get tokenURI from IdentityRegistry (points to registration JSON)
    2. Fetch registration JSON from tokenURI (/agent.json)
    3. Extract A2A endpoint from registration JSON
    4. Fetch AgentCard from A2A endpoint (/.well-known/agent-card.json)
    5. Parse and validate AgentCard

    Args:
        agent_id: Agent ID from IdentityRegistry
        identity_plugin: Initialized IdentityRegistryPlugin instance

    Returns:
        Parsed and validated AgentCard

    Raises:
        AgentNotFoundError: If agent ID doesn't exist
        AgentCardFetchError: If fetching registration or AgentCard fails
        AgentCardParseError: If parsing fails or A2A endpoint missing

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

    # Step 1: Get tokenURI from IdentityRegistry
    try:
        token_uri = identity_plugin.token_uri(agent_id)

        if not token_uri:
            raise AgentNotFoundError(
                f"Agent {agent_id} has no tokenURI set. "
                f"Agent may not be fully registered or discovery info unavailable."
            )

        logger.info(f"✅ Step 1: Found tokenURI: {token_uri}")

    except ContractCallError as e:
        raise AgentNotFoundError(
            f"Agent ID {agent_id} not found in IdentityRegistry"
        ) from e

    # Step 2: Fetch registration JSON from tokenURI
    try:
        logger.debug(f"Step 2: Fetching registration JSON from tokenURI")
        registration_json = await fetch_registration_json(token_uri)
        logger.info(
            f"✅ Step 2: Fetched registration JSON "
            f"(type: {registration_json.get('type', 'unknown')})"
        )

    except Exception as e:
        raise AgentCardFetchError(
            f"Failed to fetch registration from tokenURI '{token_uri}': {e}"
        ) from e

    # Step 3: Extract A2A endpoint from registration
    try:
        logger.debug(f"Step 3: Extracting A2A endpoint from registration")
        agent_card_url = extract_agent_card_url(registration_json)
        logger.info(f"✅ Step 3: Extracted A2A endpoint: {agent_card_url}")

    except Exception as e:
        raise AgentCardParseError(
            f"Failed to extract A2A endpoint from registration: {e}"
        ) from e

    # Step 4: Fetch AgentCard from A2A endpoint
    try:
        logger.debug(f"Step 4: Fetching AgentCard from A2A endpoint")
        agent_card_json = await fetch_agent_card_from_url(agent_card_url)
        logger.info(
            f"✅ Step 4: Fetched AgentCard "
            f"(name: {agent_card_json.get('name', 'unknown')})"
        )

    except Exception as e:
        raise AgentCardFetchError(
            f"Failed to fetch AgentCard from A2A endpoint '{agent_card_url}': {e}"
        ) from e

    # Step 5: Parse AgentCard
    try:
        logger.debug(f"Step 5: Parsing AgentCard structure")
        agent_card = parse_agent_card(agent_card_json)
        logger.info(
            f"✅ Step 5: Successfully discovered agent: {agent_card.name} (ID: {agent_id})"
        )

    except Exception as e:
        raise AgentCardParseError(
            f"Failed to parse AgentCard: {e}"
        ) from e

    return agent_card


