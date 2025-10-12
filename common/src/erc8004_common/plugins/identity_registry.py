"""Identity Registry plugin for ERC-8004 v1.0 agent registration.

ERC-8004 v1.0 implements agent identities as ERC-721 NFTs with optional metadata.
Agents are registered with tokenURIs pointing to off-chain registration JSON files.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from web3.exceptions import ContractLogicError, TimeExhausted
from hexbytes import HexBytes

from .base import (
    BaseRegistryPlugin,
    PluginInitializationError,
    TransactionError,
    ContractCallError,
)

logger = logging.getLogger(__name__)


class IdentityRegistryPlugin(BaseRegistryPlugin):
    """Plugin for Identity Registry: ERC-721 based agent registration.

    ERC-8004 v1.0 Features:
    - Agents are ERC-721 NFTs (transferable, tradeable)
    - TokenURI points to registration JSON (IPFS/HTTPS)
    - On-chain key-value metadata storage
    - Three registration variants: register(), register(tokenURI), register(tokenURI, metadata)
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2  # seconds

    @property
    def name(self) -> str:
        return "IdentityRegistry"

    @property
    def contract_address(self) -> str:
        if not self.config.identity_registry_address:
            raise ValueError("Identity Registry address not configured")
        return self.config.identity_registry_address

    def initialize(self) -> None:
        """Load Identity Registry contract."""
        try:
            logger.info(f"Initializing {self.name} at {self.contract_address}")
            self._contract = self.web3_utility.get_contract(
                contract_name="IdentityRegistry",
                address=self.contract_address,
            )

            # Verify contract by checking ERC-721 interface
            try:
                total = self._contract.functions.totalAgents().call()
                logger.info(f"Connected to IdentityRegistry with {total} registered agents")
            except Exception as e:
                logger.warning(f"Could not verify registry state: {e}")

            self._initialized = True
            logger.info(f"{self.name} initialized")
        except Exception as e:
            raise PluginInitializationError(
                f"Failed to initialize {self.name}: {str(e)}"
            ) from e

    # ============ Registration Functions (v1.0) ============

    def register(
        self,
        token_uri: str = "",
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """Register agent with optional tokenURI and metadata.

        Supports three registration variants:
        1. register() - No tokenURI (can be set later)
        2. register(tokenURI) - With tokenURI only
        3. register(tokenURI, metadata) - With tokenURI and metadata array

        Args:
            token_uri: Optional URI pointing to registration JSON (IPFS/HTTPS)
            metadata: Optional list of {key: str, value: bytes} metadata entries

        Returns:
            Agent ID (ERC-721 tokenId)

        Raises:
            TransactionError: If registration fails

        Example:
            >>> # Simple registration
            >>> agent_id = plugin.register()

            >>> # With tokenURI
            >>> agent_id = plugin.register("ipfs://QmXYZ.../agent.json")

            >>> # With tokenURI and metadata
            >>> metadata = [
            ...     {"key": "agentName", "value": b"MyAgent"},
            ...     {"key": "version", "value": b"1.0.0"}
            ... ]
            >>> agent_id = plugin.register("ipfs://QmXYZ.../agent.json", metadata)
        """
        self._ensure_initialized()

        logger.info(
            f"Registering agent: "
            f"tokenURI={'yes' if token_uri else 'no'}, "
            f"metadata={len(metadata) if metadata else 0} entries"
        )

        # Execute registration with retry logic
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                tx_hash = self._send_registration_transaction(token_uri, metadata)
                agent_id = self._wait_for_registration(tx_hash)

                logger.info(
                    f"Agent registered successfully: "
                    f"ID={agent_id}, tokenURI={token_uri or '(none)'}, tx={tx_hash.hex()}"
                )

                return agent_id

            except TransactionError as e:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        f"Registration attempt {attempt} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Registration failed after {self.MAX_RETRIES} attempts")
                    raise

    def _send_registration_transaction(
        self,
        token_uri: str,
        metadata: Optional[List[Dict[str, Any]]]
    ) -> HexBytes:
        """Build and send registration transaction. Returns tx hash."""
        try:
            # Choose registration variant based on parameters
            if metadata and len(metadata) > 0:
                # Variant 3: register(tokenURI, metadata[])
                metadata_tuples = [
                    (entry["key"], entry["value"])
                    for entry in metadata
                ]
                tx_hash = self.contract.functions.register(
                    token_uri,
                    metadata_tuples
                ).transact()
                logger.debug(f"Registration variant: register(tokenURI, metadata)")

            elif token_uri:
                # Variant 2: register(tokenURI)
                tx_hash = self.contract.functions.register(token_uri).transact()
                logger.debug(f"Registration variant: register(tokenURI)")

            else:
                # Variant 1: register()
                tx_hash = self.contract.functions.register().transact()
                logger.debug(f"Registration variant: register()")

            logger.debug(f"Transaction submitted: {tx_hash.hex()}")
            return tx_hash

        except ContractLogicError as e:
            # Contract-level errors (reverts)
            error_msg = str(e)
            raise TransactionError(f"Contract error during registration: {error_msg}") from e

        except Exception as e:
            raise TransactionError(f"Failed to send registration transaction: {str(e)}") from e

    def _wait_for_registration(self, tx_hash: HexBytes) -> int:
        """Wait for transaction and extract agent ID from Registered event."""
        try:
            # Wait for transaction receipt
            logger.debug(f"Waiting for transaction confirmation (timeout: {self.config.tx_timeout}s)")
            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            # Check transaction status
            if receipt["status"] != 1:
                raise TransactionError(f"Transaction reverted: {tx_hash.hex()}")

            # Parse Registered event (v1.0 event name)
            agent_id = self._parse_registered_event(receipt)

            return agent_id

        except TimeExhausted:
            raise TransactionError(
                f"Transaction confirmation timeout after {self.config.tx_timeout}s: {tx_hash.hex()}"
            )
        except Exception as e:
            if isinstance(e, TransactionError):
                raise
            raise TransactionError(
                f"Failed to confirm registration transaction: {str(e)}"
            ) from e

    def _parse_registered_event(self, receipt: Dict[str, Any]) -> int:
        """Parse Registered event and return agent ID.

        v1.0 Event: Registered(uint256 indexed agentId, string tokenURI, address indexed owner)
        """
        try:
            # Get event signature
            event = self.contract.events.Registered()

            # Process logs to find Registered event
            logs = event.process_receipt(receipt)

            if not logs:
                raise TransactionError("Registered event not found in transaction logs")

            # Extract agent ID from first matching event
            agent_id = logs[0]["args"]["agentId"]

            logger.debug(f"Parsed Registered event: agentId={agent_id}")
            return agent_id

        except Exception as e:
            if isinstance(e, TransactionError):
                raise
            raise TransactionError(f"Failed to parse Registered event: {str(e)}") from e

    # ============ Metadata Functions (v1.0) ============

    def set_metadata(self, agent_id: int, key: str, value: bytes) -> str:
        """Set on-chain metadata for agent.

        Only the owner or approved operator can set metadata.

        Args:
            agent_id: Agent ID (ERC-721 tokenId)
            key: Metadata key
            value: Metadata value as bytes

        Returns:
            Transaction hash

        Raises:
            TransactionError: If metadata setting fails
        """
        self._ensure_initialized()

        logger.info(f"Setting metadata: agentId={agent_id}, key={key}")

        try:
            tx_hash = self.contract.functions.setMetadata(
                agent_id, key, value
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Metadata setting failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Metadata set: agentId={agent_id}, key={key}, tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            raise TransactionError(f"Contract error setting metadata: {e}") from e
        except Exception as e:
            raise TransactionError(f"Failed to set metadata: {e}") from e

    def get_metadata(self, agent_id: int, key: str) -> bytes:
        """Get on-chain metadata for agent.

        Args:
            agent_id: Agent ID
            key: Metadata key

        Returns:
            Metadata value as bytes

        Raises:
            ContractCallError: If metadata retrieval fails
        """
        self._ensure_initialized()

        try:
            value = self.contract.functions.getMetadata(agent_id, key).call()
            logger.debug(f"Retrieved metadata: agentId={agent_id}, key={key}")
            return value

        except ContractLogicError as e:
            if "Agent does not exist" in str(e):
                raise ContractCallError(f"Agent ID {agent_id} does not exist") from e
            raise ContractCallError(f"Failed to get metadata: {e}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to get metadata: {e}") from e

    # ============ ERC-721 Query Functions ============

    def token_uri(self, agent_id: int) -> str:
        """Get agent tokenURI (IPFS/HTTPS URI).

        Args:
            agent_id: Agent ID

        Returns:
            TokenURI string

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            uri = self.contract.functions.tokenURI(agent_id).call()
            logger.debug(f"Retrieved tokenURI: agentId={agent_id}, uri={uri}")
            return uri

        except ContractLogicError as e:
            if "nonexistent token" in str(e).lower():
                raise ContractCallError(f"Agent ID {agent_id} does not exist") from e
            raise ContractCallError(f"Failed to get tokenURI: {e}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to get tokenURI: {e}") from e

    def owner_of(self, agent_id: int) -> str:
        """Get agent owner address (ERC-721 ownership).

        Args:
            agent_id: Agent ID

        Returns:
            Owner address (checksummed)

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            owner = self.contract.functions.ownerOf(agent_id).call()
            logger.debug(f"Retrieved owner: agentId={agent_id}, owner={owner}")
            return owner

        except ContractLogicError as e:
            if "nonexistent token" in str(e).lower():
                raise ContractCallError(f"Agent ID {agent_id} does not exist") from e
            raise ContractCallError(f"Failed to get owner: {e}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to get owner: {e}") from e

    def agent_exists(self, agent_id: int) -> bool:
        """Check if agent exists.

        Args:
            agent_id: Agent ID to check

        Returns:
            True if agent exists, False otherwise
        """
        self._ensure_initialized()

        try:
            exists = self.contract.functions.agentExists(agent_id).call()
            return exists
        except Exception as e:
            raise ContractCallError(f"Failed to check agent existence: {e}") from e

    def total_agents(self) -> int:
        """Get total number of registered agents.

        Returns:
            Total agent count
        """
        self._ensure_initialized()

        try:
            total = self.contract.functions.totalAgents().call()
            return total
        except Exception as e:
            raise ContractCallError(f"Failed to get total agents: {e}") from e

    # ============ ERC-721 Transfer Functions (Optional) ============

    def transfer_from(self, from_addr: str, to_addr: str, agent_id: int) -> str:
        """Transfer agent ownership (ERC-721 transfer).

        Must be called by owner or approved operator.

        Args:
            from_addr: Current owner address
            to_addr: New owner address
            agent_id: Agent ID to transfer

        Returns:
            Transaction hash

        Raises:
            TransactionError: If transfer fails
        """
        self._ensure_initialized()

        logger.info(f"Transferring agent: agentId={agent_id}, from={from_addr}, to={to_addr}")

        try:
            # Convert addresses to checksum format
            from_checksum = self.web3_utility.w3.to_checksum_address(from_addr)
            to_checksum = self.web3_utility.w3.to_checksum_address(to_addr)

            tx_hash = self.contract.functions.transferFrom(
                from_checksum, to_checksum, agent_id
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Transfer failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Agent transferred: agentId={agent_id}, tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            raise TransactionError(f"Contract error during transfer: {e}") from e
        except Exception as e:
            raise TransactionError(f"Failed to transfer agent: {e}") from e
