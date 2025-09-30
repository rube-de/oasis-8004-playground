"""Identity Registry plugin for ERC-8004 agent registration."""

import logging
import time
from typing import Optional, Dict, Any
from web3.exceptions import ContractLogicError, TimeExhausted
from eth_typing import HexStr
from hexbytes import HexBytes

from .base import (
    BaseRegistryPlugin,
    PluginInitializationError,
    PluginExecutionError,
    TransactionError,
    ContractCallError,
)

logger = logging.getLogger(__name__)


class IdentityRegistryPlugin(BaseRegistryPlugin):
    """Plugin for Identity Registry: registration, updates, queries."""

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
            self._contract = self.contract_utility.get_contract(
                contract_name="IdentityRegistry",
                address=self.contract_address,
            )

            try:
                version = self._contract.functions.VERSION().call()
                logger.info(f"Connected to IdentityRegistry v{version}")
            except Exception as e:
                logger.warning(f"Could not verify version: {e}")

            self._initialized = True
            logger.info(f"{self.name} initialized")
        except Exception as e:
            raise PluginInitializationError(f"Failed to initialize {self.name}: {str(e)}") from e

    def register(self) -> int:
        """Register agent. Returns agent ID."""
        self._ensure_initialized()

        agent_domain = self.config.agent_domain
        agent_address = self.contract_utility.account.address

        logger.info(f"Registering agent: domain={agent_domain}, address={agent_address}")

        # Check if already registered
        try:
            existing = self._resolve_by_address_internal(agent_address)
            if existing:
                raise ValueError(
                    f"Agent already registered with ID {existing['agentId']}. "
                    f"Use update() to modify registration."
                )
        except ContractCallError:
            # Not found - proceed with registration
            pass

        # Execute registration with retry logic
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                tx_hash = self._send_registration_transaction(agent_domain, agent_address)
                agent_id = self._wait_for_registration(tx_hash)

                logger.info(
                    f"Agent registered successfully: "
                    f"ID={agent_id}, domain={agent_domain}, tx={tx_hash.hex()}"
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

    def _send_registration_transaction(self, agent_domain: str, agent_address: str) -> HexBytes:
        """Build and send registration transaction. Returns tx hash."""
        try:
            # Build transaction
            tx_function = self.contract.functions.newAgent(agent_domain, agent_address)

            # Estimate gas with safety multiplier
            try:
                estimated_gas = tx_function.estimate_gas(
                    {"from": agent_address}
                )
                gas_limit = int(estimated_gas * self.config.gas_multiplier)
                logger.debug(f"Gas estimate: {estimated_gas}, using: {gas_limit}")
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}. Using default gas limit.")
                gas_limit = 500000  # Fallback gas limit

            # Send transaction
            tx_hash = tx_function.transact({"from": agent_address, "gas": gas_limit})
            logger.debug(f"Transaction submitted: {tx_hash.hex()}")

            return tx_hash

        except ContractLogicError as e:
            # Contract-level errors (reverts)
            error_msg = str(e)
            if "DomainAlreadyRegistered" in error_msg:
                raise TransactionError(
                    f"Domain '{agent_domain}' is already registered"
                ) from e
            elif "AddressAlreadyRegistered" in error_msg:
                raise TransactionError(
                    f"Address '{agent_address}' is already registered"
                ) from e
            elif "UnauthorizedRegistration" in error_msg:
                raise TransactionError(
                    "Cannot register on behalf of another address"
                ) from e
            else:
                raise TransactionError(f"Contract error: {error_msg}") from e

        except Exception as e:
            raise TransactionError(f"Failed to send transaction: {str(e)}") from e

    def _wait_for_registration(self, tx_hash: HexBytes) -> int:
        """Wait for transaction and extract agent ID from event."""
        try:
            # Wait for transaction receipt
            logger.debug(f"Waiting for transaction confirmation (timeout: {self.config.tx_timeout}s)")
            receipt = self.contract_utility.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.config.tx_timeout
            )

            # Check transaction status
            if receipt["status"] != 1:
                raise TransactionError(
                    f"Transaction reverted: {tx_hash.hex()}"
                )

            # Parse AgentRegistered event
            agent_id = self._parse_agent_registered_event(receipt)

            return agent_id

        except TimeExhausted:
            raise TransactionError(
                f"Transaction confirmation timeout after {self.config.tx_timeout}s: {tx_hash.hex()}"
            )
        except Exception as e:
            if isinstance(e, TransactionError):
                raise
            raise TransactionError(
                f"Failed to confirm transaction: {str(e)}"
            ) from e

    def _parse_agent_registered_event(self, receipt: Dict[str, Any]) -> int:
        """Parse AgentRegistered event and return agent ID."""
        try:
            # Get event signature
            event = self.contract.events.AgentRegistered()

            # Process logs to find AgentRegistered event
            logs = event.process_receipt(receipt)

            if not logs:
                raise TransactionError("AgentRegistered event not found in transaction logs")

            # Extract agent ID from first matching event
            agent_id = logs[0]["args"]["agentId"]

            logger.debug(f"Parsed AgentRegistered event: agentId={agent_id}")
            return agent_id

        except Exception as e:
            if isinstance(e, TransactionError):
                raise
            raise TransactionError(f"Failed to parse event: {str(e)}") from e

    def get_agent(self, agent_id: int) -> Dict[str, Any]:
        """Get agent info by ID. Returns dict with agentId, agentDomain, agentAddress."""
        self._ensure_initialized()

        try:
            result = self.contract.functions.getAgent(agent_id).call()

            # Result is a tuple: (agentId, agentDomain, agentAddress)
            return {
                "agentId": result[0],
                "agentDomain": result[1],
                "agentAddress": result[2],
            }

        except ContractLogicError as e:
            if "AgentNotFound" in str(e):
                raise ContractCallError(f"Agent ID {agent_id} not found") from e
            raise ContractCallError(f"Failed to get agent: {str(e)}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to get agent: {str(e)}") from e

    def resolve_by_address(self, address: str) -> Dict[str, Any]:
        """Resolve agent by address."""
        self._ensure_initialized()

        try:
            checksum_address = self.contract_utility.w3.to_checksum_address(address)
            result = self.contract.functions.resolveByAddress(checksum_address).call()

            return {
                "agentId": result[0],
                "agentDomain": result[1],
                "agentAddress": result[2],
            }

        except ContractLogicError as e:
            if "AgentNotFound" in str(e):
                raise ContractCallError(f"No agent found for address {address}") from e
            raise ContractCallError(f"Failed to resolve by address: {str(e)}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to resolve by address: {str(e)}") from e

    def _resolve_by_address_internal(self, address: str) -> Optional[Dict[str, Any]]:
        """Resolve by address, return None if not found (no exception)."""
        try:
            return self.resolve_by_address(address)
        except ContractCallError:
            return None

    def resolve_by_domain(self, domain: str) -> Dict[str, Any]:
        """Resolve agent by domain."""
        self._ensure_initialized()

        try:
            result = self.contract.functions.resolveByDomain(domain).call()

            return {
                "agentId": result[0],
                "agentDomain": result[1],
                "agentAddress": result[2],
            }

        except ContractLogicError as e:
            if "AgentNotFound" in str(e):
                raise ContractCallError(f"No agent found for domain '{domain}'") from e
            raise ContractCallError(f"Failed to resolve by domain: {str(e)}") from e
        except Exception as e:
            raise ContractCallError(f"Failed to resolve by domain: {str(e)}") from e

    def agent_exists(self, agent_id: int) -> bool:
        """Check if agent ID exists."""
        self._ensure_initialized()

        try:
            return self.contract.functions.agentExists(agent_id).call()
        except Exception as e:
            raise ContractCallError(f"Failed to check agent existence: {str(e)}") from e
