"""Validation Registry plugin for ERC-8004 v1.0 independent verification.

ERC-8004 v1.0 implements independent work validation with URI-based evidence.
Supports various validation methods: stake-secured, zkML, TEE attestations.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from web3.exceptions import ContractLogicError, TimeExhausted
from hexbytes import HexBytes

from .base import (
    BaseRegistryPlugin,
    PluginInitializationError,
    TransactionError,
    ContractCallError,
)

logger = logging.getLogger(__name__)


class ValidationRegistryPlugin(BaseRegistryPlugin):
    """Plugin for Validation Registry: independent work verification.

    ERC-8004 v1.0 Features:
    - URI-based evidence (IPFS recommended)
    - Progressive validation: multiple responses per request
    - Tag-based categorization (e.g., 'soft-finality', 'hard-finality')
    - Response range: 0-100
    - Support for various validation methods (TEE, zkML, stake-secured)
    - Self-validation prevention
    """

    @property
    def name(self) -> str:
        return "ValidationRegistry"

    @property
    def contract_address(self) -> str:
        if not self.config.validation_registry_address:
            raise ValueError("Validation Registry address not configured")
        return self.config.validation_registry_address

    def initialize(self) -> None:
        """Load Validation Registry contract."""
        try:
            logger.info(f"Initializing {self.name} at {self.contract_address}")
            self._contract = self.web3_utility.get_contract(
                contract_name="ValidationRegistry",
                address=self.contract_address,
            )

            # Verify contract by checking identity registry reference
            try:
                identity_registry = self._contract.functions.getIdentityRegistry().call()
                logger.info(f"Connected to ValidationRegistry (identity registry: {identity_registry})")
            except Exception as e:
                logger.warning(f"Could not verify registry: {e}")

            self._initialized = True
            logger.info(f"{self.name} initialized")
        except Exception as e:
            raise PluginInitializationError(
                f"Failed to initialize {self.name}: {str(e)}"
            ) from e

    # ============ Core Functions ============

    def validation_request(
        self,
        validator_address: str,
        agent_id: int,
        request_uri: str,
        request_hash: bytes = b'\x00' * 32
    ) -> str:
        """Create validation request for agent's work.

        Must be called by the owner or operator of the agent.
        The contract prevents self-validation for integrity.

        Args:
            validator_address: Address of validator (EOA or contract)
            agent_id: Agent requesting validation
            request_uri: URI pointing to off-chain validation data (required)
            request_hash: KECCAK-256 hash of request data (optional for IPFS)

        Returns:
            Transaction hash

        Raises:
            TransactionError: If validation request fails

        Example:
            >>> # Request TEE attestation validation
            >>> tx_hash = plugin.validation_request(
            ...     validator_address="0x123...",  # TEE validator contract
            ...     agent_id=1,
            ...     request_uri="ipfs://QmXYZ.../validation-request.json"
            ... )
        """
        self._ensure_initialized()

        if not request_uri:
            raise ValueError("request_uri is required")

        logger.info(
            f"Creating validation request: agentId={agent_id}, "
            f"validator={validator_address}, uri={request_uri}"
        )

        try:
            # Convert validator address to checksum format
            validator_checksum = self.web3_utility.w3.to_checksum_address(validator_address)

            tx_hash = self.contract.functions.validationRequest(
                validator_checksum,
                agent_id,
                request_uri,
                request_hash
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Validation request failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Validation request created: tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            error_msg = str(e)
            if "Invalid validator address" in error_msg:
                raise TransactionError("Validator address cannot be zero address") from e
            elif "Empty request URI" in error_msg:
                raise TransactionError("Request URI cannot be empty") from e
            elif "Agent does not exist" in error_msg:
                raise TransactionError(f"Agent ID {agent_id} does not exist") from e
            elif "Not authorized" in error_msg:
                raise TransactionError("Not authorized to create validation request") from e
            elif "Self-validation not allowed" in error_msg:
                raise TransactionError("Cannot validate your own work") from e
            elif "Request hash already exists" in error_msg:
                raise TransactionError("Request hash collision (already exists)") from e
            else:
                raise TransactionError(f"Contract error: {error_msg}") from e
        except TimeExhausted:
            raise TransactionError(
                f"Transaction timeout after {self.config.tx_timeout}s: {tx_hash.hex()}"
            )
        except Exception as e:
            raise TransactionError(f"Failed to create validation request: {str(e)}") from e

    def validation_response(
        self,
        request_hash: bytes,
        response: int,
        response_uri: str = "",
        response_hash: bytes = b'\x00' * 32,
        tag: bytes = b'\x00' * 32
    ) -> str:
        """Provide validation response (progressive validation supported).

        Must be called by the validator address specified in the request.
        Can be called multiple times with different tags for progressive validation.

        Args:
            request_hash: Hash of the validation request
            response: Validation result (0-100)
            response_uri: URI pointing to validation evidence (optional)
            response_hash: KECCAK-256 hash of response data (optional for IPFS)
            tag: Custom tag for categorization (optional, e.g., 'soft-finality')

        Returns:
            Transaction hash

        Raises:
            TransactionError: If validation response fails

        Example:
            >>> # Progressive validation: first response with soft finality
            >>> tx1 = plugin.validation_response(
            ...     request_hash=b'0x123...',
            ...     response=100,
            ...     response_uri="ipfs://QmABC.../soft-finality.json",
            ...     tag=b"soft-finality"
            ... )
            >>>
            >>> # Second response with hard finality
            >>> tx2 = plugin.validation_response(
            ...     request_hash=b'0x123...',
            ...     response=100,
            ...     response_uri="ipfs://QmDEF.../hard-finality.json",
            ...     tag=b"hard-finality"
            ... )
        """
        self._ensure_initialized()

        if response > 100:
            raise ValueError(f"Response must be 0-100, got {response}")

        logger.info(
            f"Submitting validation response: requestHash={request_hash.hex()}, "
            f"response={response}, tag={tag.hex() if tag != b'\\x00' * 32 else '(none)'}"
        )

        try:
            tx_hash = self.contract.functions.validationResponse(
                request_hash,
                response,
                response_uri,
                response_hash,
                tag
            ).transact()

            receipt = self.web3_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            if receipt["status"] != 1:
                raise TransactionError(f"Validation response failed: tx_hash={tx_hash.hex()}")

            logger.info(f"Validation response submitted: tx={tx_hash.hex()}")
            return tx_hash.hex()

        except ContractLogicError as e:
            error_msg = str(e)
            if "Response must be 0-100" in error_msg:
                raise TransactionError(f"Invalid response value: {response}") from e
            elif "Request not found" in error_msg:
                raise TransactionError("Validation request not found") from e
            elif "Not authorized validator" in error_msg:
                raise TransactionError("Not authorized to respond (not the designated validator)") from e
            else:
                raise TransactionError(f"Contract error: {error_msg}") from e
        except TimeExhausted:
            raise TransactionError(
                f"Transaction timeout after {self.config.tx_timeout}s: {tx_hash.hex()}"
            )
        except Exception as e:
            raise TransactionError(f"Failed to submit validation response: {str(e)}") from e

    # ============ Read Functions ============

    def get_validation_status(self, request_hash: bytes) -> Dict[str, Any]:
        """Get validation status for a request.

        Returns default values for pending requests (no response yet).

        Args:
            request_hash: Request hash

        Returns:
            Dict with keys:
            - validatorAddress: Validator address (address(0) if no response)
            - agentId: Agent ID (0 if no response)
            - response: Validation response 0-100 (0 if no response)
            - tag: Response tag (bytes32(0) if no response)
            - lastUpdate: Timestamp of last update (0 if no response)

        Raises:
            ContractCallError: If query fails

        Example:
            >>> status = plugin.get_validation_status(request_hash)
            >>> if status['validatorAddress'] == '0x' + '0' * 40:
            ...     print("Validation pending (no response yet)")
            >>> else:
            ...     print(f"Validation complete: {status['response']}/100")
        """
        self._ensure_initialized()

        try:
            result = self.contract.functions.getValidationStatus(request_hash).call()

            # Result: (validatorAddress, agentId, response, tag, lastUpdate)
            return {
                "validatorAddress": result[0],
                "agentId": int(result[1]),
                "response": int(result[2]),
                "tag": result[3],
                "lastUpdate": int(result[4])
            }

        except Exception as e:
            raise ContractCallError(f"Failed to get validation status: {str(e)}") from e

    def get_summary(
        self,
        agent_id: int,
        validator_addresses: Optional[List[str]] = None,
        tag: bytes = b'\x00' * 32
    ) -> Tuple[int, int]:
        """Get aggregated validation summary for agent.

        WARNING: For agents with many validations, this may exceed gas limits.
        Always use validator_addresses filter for popular agents.

        Args:
            agent_id: Agent ID
            validator_addresses: Filter by validators (recommended for popular agents)
            tag: Filter by tag (optional, bytes32(0) to skip)

        Returns:
            Tuple of (count, average_response)

        Raises:
            ContractCallError: If query fails

        Example:
            >>> # Get summary from all validators
            >>> count, avg = plugin.get_summary(agent_id=1)
            >>>
            >>> # Filter by specific trusted validators
            >>> trusted = ["0x123...", "0x456..."]
            >>> count, avg = plugin.get_summary(agent_id=1, validator_addresses=trusted)
            >>>
            >>> # Filter by tag (e.g., only hard finality validations)
            >>> count, avg = plugin.get_summary(agent_id=1, tag=b"hard-finality")
        """
        self._ensure_initialized()

        try:
            # Convert addresses to checksum format
            validators = []
            if validator_addresses:
                validators = [
                    self.web3_utility.w3.to_checksum_address(addr)
                    for addr in validator_addresses
                ]

            count, avg_response = self.contract.functions.getSummary(
                agent_id,
                validators,
                tag
            ).call()

            logger.debug(
                f"Retrieved validation summary: agentId={agent_id}, "
                f"count={count}, avgResponse={avg_response}"
            )

            return (int(count), int(avg_response))

        except Exception as e:
            raise ContractCallError(f"Failed to get validation summary: {str(e)}") from e

    def get_agent_validations(self, agent_id: int) -> List[bytes]:
        """Get all validation request hashes for agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of request hashes (bytes32)

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            request_hashes = self.contract.functions.getAgentValidations(agent_id).call()
            return request_hashes
        except Exception as e:
            raise ContractCallError(f"Failed to get agent validations: {str(e)}") from e

    def get_validator_requests(self, validator_address: str) -> List[bytes]:
        """Get all validation request hashes for validator.

        Args:
            validator_address: Validator address

        Returns:
            List of request hashes (bytes32)

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            validator_checksum = self.web3_utility.w3.to_checksum_address(validator_address)
            request_hashes = self.contract.functions.getValidatorRequests(validator_checksum).call()
            return request_hashes
        except Exception as e:
            raise ContractCallError(f"Failed to get validator requests: {str(e)}") from e

    def request_exists(self, request_hash: bytes) -> bool:
        """Check if validation request exists.

        Args:
            request_hash: Request hash

        Returns:
            True if request exists, False otherwise

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            exists = self.contract.functions.requestExists(request_hash).call()
            return exists
        except Exception as e:
            raise ContractCallError(f"Failed to check request existence: {str(e)}") from e

    # ============ Helper Functions ============

    def get_request_details(self, request_hash: bytes) -> Dict[str, Any]:
        """Get detailed request information.

        Args:
            request_hash: Request hash

        Returns:
            Dict with request details

        Raises:
            ContractCallError: If query fails
        """
        self._ensure_initialized()

        try:
            # Call getRequest function
            result = self.contract.functions.getRequest(request_hash).call()

            # Result: (validatorAddress, agentId, requestUri, requestHash, timestamp)
            return {
                "validatorAddress": result[0],
                "agentId": int(result[1]),
                "requestUri": result[2],
                "requestHash": result[3],
                "timestamp": int(result[4])
            }

        except Exception as e:
            raise ContractCallError(f"Failed to get request details: {str(e)}") from e
