"""Reputation Registry plugin for ERC-8004 v1.0 feedback system.

ERC-8004 v1.0 implements cryptographic feedback authorization using EIP-191/ERC-1271 signatures.
Feedback is stored on-chain with scores and tags for composability, while detailed data uses URIs.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from web3.exceptions import ContractLogicError, TimeExhausted
from hexbytes import HexBytes
from eth_account.messages import encode_defunct

from .base import (
    BaseRegistryPlugin,
    PluginInitializationError,
    TransactionError,
    ContractCallError,
)

logger = logging.getLogger(__name__)


class ReputationRegistryPlugin(BaseRegistryPlugin):
    """Plugin for Reputation Registry: cryptographic feedback system.

    ERC-8004 v1.0 Features:
    - Cryptographic feedback authorization (EIP-191 for EOAs, ERC-1271 for contracts)
    - On-chain scores (0-100) and tags for composability
    - Off-chain detailed feedback via URIs (IPFS recommended)
    - Feedback revocation by clients
    - Response mechanism for disputes
    - On-chain aggregation with filtering
    """

    @property
    def name(self) -> str:
        return "ReputationRegistry"

    @property
    def contract_address(self) -> str:
        if not self.config.reputation_registry_address:
            raise ValueError("Reputation Registry address not configured")
        return self.config.reputation_registry_address

    def initialize(self) -> None:
        """Load Reputation Registry contract."""
        try:
            logger.info(f"Initializing {self.name} at {self.contract_address}")
            self._contract = self.web3_utility.get_contract(
                contract_name="ReputationRegistry",
                address=self.contract_address,
            )

            # Verify contract by checking identity registry reference
            try:
                identity_registry = self._contract.functions.getIdentityRegistry().call()
                logger.info(f"Connected to ReputationRegistry (identity registry: {identity_registry})")
            except Exception as e:
                logger.warning(f"Could not verify registry: {e}")

            self._initialized = True
            logger.info(f"{self.name} initialized")
        except Exception as e:
            raise PluginInitializationError(
                f"Failed to initialize {self.name}: {str(e)}"
            ) from e

    # ============ Core Functions ============

    def give_feedback(
        self,
        agent_id: int,
        score: int,
        tag1: bytes = b'\x00' * 32,
        tag2: bytes = b'\x00' * 32,
        file_uri: str = "",
        file_hash: bytes = b'\x00' * 32,
        feedback_auth: bytes = None
    ) -> str:
        """Give feedback for an agent with cryptographic authorization.

        Args:
            agent_id: Agent receiving feedback
            score: Feedback score (0-100)
            tag1: First tag for categorization (optional, 32 bytes)
            tag2: Second tag for categorization (optional, 32 bytes)
            file_uri: URI pointing to off-chain feedback data (optional)
            file_hash: KECCAK-256 hash of file content (optional for IPFS)
            feedback_auth: Signed authorization from agent (required)

        Returns:
            Transaction hash

        Raises:
            TransactionError: If feedback submission fails

        Example:
            >>> # Create and sign authorization (see create_feedback_auth)
            >>> auth = plugin.create_feedback_auth(
            ...     agent_id=1,
            ...     client_address="0x123...",
            ...     index_limit=5,
            ...     expiry=int(time.time()) + 86400
            ... )
            >>>
            >>> # Submit feedback
            >>> tx_hash = plugin.give_feedback(
            ...     agent_id=1,
            ...     score=95,
            ...     tag1=b"quality",
            ...     file_uri="ipfs://QmXYZ.../feedback.json",
            ...     feedback_auth=auth
            ... )
        """
        self._ensure_initialized()

        if not feedback_auth:
            raise ValueError("feedback_auth is required (signed authorization from agent)")

        if score > 100:
            raise ValueError(f"Score must be 0-100, got {score}")

        logger.info(
            f"Submitting feedback: agentId={agent_id}, score={score}, "
            f"fileUri={file_uri or '(none)'}"
        )

        try:
            tx_hash = self.contract.functions.giveFeedback(
                agent_id,
                score,
                tag1,
                tag2,
                file_uri,
                file_hash,
                feedback_auth
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Feedback submission failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Feedback submitted: agentId={agent_id}, tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            error_msg = str(e)
            if "Score must be 0-100" in error_msg:
                raise TransactionError(f"Invalid score: {score}") from e
            elif "Agent does not exist" in error_msg:
                raise TransactionError(f"Agent ID {agent_id} does not exist") from e
            elif "Invalid signature" in error_msg:
                raise TransactionError("Feedback authorization signature invalid") from e
            elif "Authorization expired" in error_msg:
                raise TransactionError("Feedback authorization expired") from e
            elif "Self-feedback not allowed" in error_msg:
                raise TransactionError("Cannot give feedback to yourself") from e
            else:
                raise TransactionError(f"Contract error: {error_msg}") from e
        except TimeExhausted:
            raise TransactionError(
                f"Transaction timeout after {self.config.tx_timeout}s: {tx_hash.hex()}"
            )
        except Exception as e:
            raise TransactionError(f"Failed to submit feedback: {str(e)}") from e

    def revoke_feedback(self, agent_id: int, feedback_index: int) -> str:
        """Revoke previously given feedback.

        Args:
            agent_id: Agent ID
            feedback_index: Feedback index to revoke (1-indexed)

        Returns:
            Transaction hash

        Raises:
            TransactionError: If revocation fails
        """
        self._ensure_initialized()

        logger.info(f"Revoking feedback: agentId={agent_id}, index={feedback_index}")

        try:
            tx_hash = self.contract.functions.revokeFeedback(
                agent_id, feedback_index
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Feedback revocation failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Feedback revoked: agentId={agent_id}, index={feedback_index}, tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            error_msg = str(e)
            if "Invalid index" in error_msg:
                raise TransactionError(f"Invalid feedback index: {feedback_index}") from e
            elif "Already revoked" in error_msg:
                raise TransactionError(f"Feedback already revoked") from e
            else:
                raise TransactionError(f"Contract error: {error_msg}") from e
        except Exception as e:
            raise TransactionError(f"Failed to revoke feedback: {str(e)}") from e

    def append_response(
        self,
        agent_id: int,
        client_address: str,
        feedback_index: int,
        response_uri: str,
        response_hash: bytes = b'\x00' * 32
    ) -> str:
        """Append response to feedback (anyone can respond).

        Args:
            agent_id: Agent ID
            client_address: Client who gave the feedback
            feedback_index: Feedback index
            response_uri: URI pointing to response data (required)
            response_hash: KECCAK-256 hash of response (optional for IPFS)

        Returns:
            Transaction hash

        Raises:
            TransactionError: If response appending fails
        """
        self._ensure_initialized()

        if not response_uri:
            raise ValueError("response_uri is required")

        logger.info(
            f"Appending response: agentId={agent_id}, client={client_address}, "
            f"index={feedback_index}"
        )

        try:
            # Convert address to checksum format
            client_checksum = self.web3_utility.w3.to_checksum_address(client_address)

            tx_hash = self.contract.functions.appendResponse(
                agent_id,
                client_checksum,
                feedback_index,
                response_uri,
                response_hash
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Response appending failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Response appended: tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            error_msg = str(e)
            if "Invalid index" in error_msg:
                raise TransactionError(f"Invalid feedback index") from e
            elif "Empty URI" in error_msg:
                raise TransactionError("Response URI cannot be empty") from e
            else:
                raise TransactionError(f"Contract error: {error_msg}") from e
        except Exception as e:
            raise TransactionError(f"Failed to append response: {str(e)}") from e

    # ============ Read Functions ============

    def get_summary(
        self,
        agent_id: int,
        client_addresses: Optional[List[str]] = None,
        tag1: bytes = b'\x00' * 32,
        tag2: bytes = b'\x00' * 32
    ) -> Tuple[int, int]:
        """Get aggregated reputation summary for agent.

        Args:
            agent_id: Agent ID
            client_addresses: Filter by specific clients (recommended for popular agents)
            tag1: Filter by tag1 (optional, bytes32(0) to skip)
            tag2: Filter by tag2 (optional, bytes32(0) to skip)

        Returns:
            Tuple of (count, average_score)

        Raises:
            ContractCallError: If query fails

        Example:
            >>> # Get summary from all clients (may be expensive for popular agents)
            >>> count, avg = plugin.get_summary(agent_id=1)
            >>>
            >>> # Filter by specific trusted clients
            >>> trusted = ["0x123...", "0x456..."]
            >>> count, avg = plugin.get_summary(agent_id=1, client_addresses=trusted)
        """
        self._ensure_initialized()

        try:
            # Convert addresses to checksum format
            clients = []
            if client_addresses:
                clients = [
                    self.web3_utility.w3.to_checksum_address(addr)
                    for addr in client_addresses
                ]

            count, avg_score = self.contract.functions.getSummary(
                agent_id,
                clients,
                tag1,
                tag2
            ).call()

            logger.debug(
                f"Retrieved summary: agentId={agent_id}, count={count}, avgScore={avg_score}"
            )

            return (int(count), int(avg_score))

        except Exception as e:
            raise ContractCallError(f"Failed to get summary: {str(e)}") from e

    def read_feedback(
        self,
        agent_id: int,
        client_address: str,
        index: int
    ) -> Dict[str, Any]:
        """Read specific feedback entry.

        Args:
            agent_id: Agent ID
            client_address: Client address
            index: Feedback index (1-indexed)

        Returns:
            Dict with keys: score, tag1, tag2, isRevoked

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            client_checksum = self.web3_utility.w3.to_checksum_address(client_address)

            score, tag1, tag2, is_revoked = self.contract.functions.readFeedback(
                agent_id, client_checksum, index
            ).call()

            return {
                "score": int(score),
                "tag1": tag1,
                "tag2": tag2,
                "isRevoked": is_revoked
            }

        except ContractLogicError as e:
            if "Invalid index" in str(e):
                raise ContractCallError(f"Invalid feedback index: {index}") from e
            raise ContractCallError(f"Failed to read feedback: {str(e)}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to read feedback: {str(e)}") from e

    def read_all_feedback(
        self,
        agent_id: int,
        client_addresses: Optional[List[str]] = None,
        tag1: bytes = b'\x00' * 32,
        tag2: bytes = b'\x00' * 32,
        include_revoked: bool = False
    ) -> Dict[str, Any]:
        """Read all feedback for agent with filtering.

        WARNING: For agents with many feedback entries, this may exceed gas limits.
        Always use client_addresses filter for popular agents.

        Args:
            agent_id: Agent ID
            client_addresses: Filter by clients (recommended for popular agents)
            tag1: Filter by tag1 (optional, bytes32(0) to ignore)
            tag2: Filter by tag2 (optional, bytes32(0) to ignore)
            include_revoked: Whether to include revoked feedback

        Returns:
            Dict with keys: clients, scores, tag1s, tag2s, revokedStatuses (all as lists)

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            # Convert addresses to checksum format
            clients = []
            if client_addresses:
                clients = [
                    self.web3_utility.w3.to_checksum_address(addr)
                    for addr in client_addresses
                ]

            result = self.contract.functions.readAllFeedback(
                agent_id,
                clients,
                tag1,
                tag2,
                include_revoked
            ).call()

            # Result is tuple: (clients[], scores[], tag1s[], tag2s[], revokedStatuses[])
            return {
                "clients": result[0],
                "scores": [int(s) for s in result[1]],
                "tag1s": result[2],
                "tag2s": result[3],
                "revokedStatuses": result[4]
            }

        except Exception as e:
            raise ContractCallError(f"Failed to read all feedback: {str(e)}") from e

    def get_clients(self, agent_id: int) -> List[str]:
        """Get all clients who gave feedback to agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of client addresses

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            clients = self.contract.functions.getClients(agent_id).call()
            return clients
        except Exception as e:
            raise ContractCallError(f"Failed to get clients: {str(e)}") from e

    def get_last_index(self, agent_id: int, client_address: str) -> int:
        """Get last feedback index for client-agent pair.

        Args:
            agent_id: Agent ID
            client_address: Client address

        Returns:
            Last feedback index (0 if no feedback)

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            client_checksum = self.web3_utility.w3.to_checksum_address(client_address)
            last_index = self.contract.functions.getLastIndex(agent_id, client_checksum).call()
            return int(last_index)
        except Exception as e:
            raise ContractCallError(f"Failed to get last index: {str(e)}") from e

    # ============ Signature Helper Functions ============

    def create_feedback_auth(
        self,
        agent_id: int,
        client_address: str,
        index_limit: int,
        expiry: int
    ) -> bytes:
        """Create and sign FeedbackAuth struct using EIP-191.

        This method signs the authorization using the Web3Utility's private key.
        The resulting bytes can be passed to give_feedback().

        Args:
            agent_id: Agent receiving feedback
            client_address: Client who will give feedback
            index_limit: Maximum feedback index allowed (prevents replay)
            expiry: Unix timestamp when authorization expires

        Returns:
            Signed feedback authorization (289 bytes: 224 struct + 65 signature)

        Raises:
            ValueError: If Web3Utility has no account (no private key)
            TransactionError: If signing fails

        Example:
            >>> import time
            >>> auth = plugin.create_feedback_auth(
            ...     agent_id=1,
            ...     client_address="0x123...",
            ...     index_limit=5,  # Allow up to index 5
            ...     expiry=int(time.time()) + 86400  # Valid for 24 hours
            ... )
            >>> # Now client can call give_feedback() with this auth
        """
        if not self.web3_utility.account:
            raise ValueError("Web3Utility has no account (private key not configured)")

        try:
            # Get identity registry address and chain ID
            identity_registry = self._contract.functions.getIdentityRegistry().call()
            chain_id = self.web3_utility.w3.eth.chain_id
            signer_address = self.web3_utility.account.address

            # Convert client address to checksum format
            client_checksum = self.web3_utility.w3.to_checksum_address(client_address)

            # Encode FeedbackAuth struct (7 fields × 32 bytes = 224 bytes)
            struct_hash = self.web3_utility.w3.keccak(
                self.web3_utility.w3.codec.encode(
                    ['uint256', 'address', 'uint64', 'uint256', 'uint256', 'address', 'address'],
                    [agent_id, client_checksum, index_limit, expiry, chain_id, identity_registry, signer_address]
                )
            )

            # Create EIP-191 message hash: "\x19Ethereum Signed Message:\n32" + struct_hash
            message = encode_defunct(primitive=struct_hash)

            # Sign message
            signed_message = self.web3_utility.account.sign_message(message)

            # Combine struct (ABI-encoded) + signature (65 bytes: r, s, v)
            struct_bytes = self.web3_utility.w3.codec.encode(
                ['uint256', 'address', 'uint64', 'uint256', 'uint256', 'address', 'address'],
                [agent_id, client_checksum, index_limit, expiry, chain_id, identity_registry, signer_address]
            )

            # Signature is 65 bytes: r (32) + s (32) + v (1)
            signature_bytes = signed_message.signature

            # Feedback auth = struct (224 bytes) + signature (65 bytes)
            feedback_auth = struct_bytes + signature_bytes

            logger.debug(
                f"Created feedback auth: agentId={agent_id}, client={client_address}, "
                f"indexLimit={index_limit}, expiry={expiry}"
            )

            return feedback_auth

        except Exception as e:
            raise TransactionError(f"Failed to create feedback authorization: {str(e)}") from e
