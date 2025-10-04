"""Contract interaction utilities for ERC-8004 applications.

Provides simple abstraction layer for Web3 contract interactions:
- ABI loading from Hardhat compiled artifacts
- Web3 connection management
- Transaction signing middleware
- Contract instance creation

Use contract.functions.myFunction().transact() for transactions.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Any

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract
from web3.middleware import SignAndSendRawMiddlewareBuilder

logger = logging.getLogger(__name__)


class ContractUtilityError(Exception):
    """Base exception for ContractUtility errors."""
    pass


class ABILoadError(ContractUtilityError):
    """Raised when ABI loading fails."""
    pass


class ConnectionError(ContractUtilityError):
    """Raised when Web3 connection fails."""
    pass


class ContractUtility:
    """Utility class for Web3 contract interactions.

    Manages Web3 connections, ABI loading, and contract instance creation.
    Signing middleware automatically handles transaction signing.

    Example:
        >>> config = Config()
        >>> utility = ContractUtility(config)
        >>> contract = utility.get_contract("IdentityRegistry", "0x123...")
        >>> tx_hash = contract.functions.newAgent("example.com", account).transact()
        >>> receipt = utility.w3.eth.wait_for_transaction_receipt(tx_hash)
    """

    ABI_DIR = Path("/app/abis")

    def __init__(self, config: Any):
        """Initialize ContractUtility with configuration.

        Args:
            config: Configuration object with rpc_url and optional private_key

        Raises:
            ConnectionError: If Web3 connection fails
        """
        self.config = config
        self.account: Optional[LocalAccount] = None

        logger.info(f"Initializing ContractUtility with RPC: {config.rpc_url}")

        # Initialize Web3 connection
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))

        if not self.w3.is_connected():
            raise ConnectionError(f"Failed to connect to RPC: {config.rpc_url}")

        # Setup signing middleware
        if hasattr(config, 'private_key') and config.private_key:
            self._add_signing_middleware()

        chain_id = self.w3.eth.chain_id
        logger.info(f"Connected to chain ID: {chain_id}")

    def _add_signing_middleware(self) -> None:
        """Add transaction signing middleware to Web3 instance."""
        try:
            private_key_hex = f"0x{self.config.private_key}"
            self.account = Account.from_key(private_key_hex)

            logger.info(f"Signing account: {self.account.address}")

            self.w3.middleware_onion.add(
                SignAndSendRawMiddlewareBuilder.build(self.account)
            )
            self.w3.eth.default_account = self.account.address

        except Exception as e:
            raise ContractUtilityError(
                f"Failed to setup signing middleware: {str(e)}"
            ) from e

    def _load_abi(self, contract_name: str) -> list:
        """Load contract ABI from Hardhat compiled artifacts.

        Args:
            contract_name: Name of the contract (e.g., "IdentityRegistry")

        Returns:
            Contract ABI as a list

        Raises:
            ABILoadError: If ABI file not found or invalid format
        """
        abi_file = self.ABI_DIR / f"{contract_name}.json"

        try:
            if not abi_file.exists():
                raise ABILoadError(
                    f"ABI file not found: {abi_file}. "
                    f"Ensure contracts are compiled and artifacts copied to Docker image."
                )

            with open(abi_file, "r") as f:
                artifact = json.load(f)

            if "abi" not in artifact:
                raise ABILoadError(
                    f"Invalid artifact format: 'abi' field not found in {abi_file}"
                )

            abi = artifact["abi"]

            if not isinstance(abi, list):
                raise ABILoadError(
                    f"Invalid ABI format: expected list, got {type(abi).__name__}"
                )

            logger.debug(f"Loaded ABI with {len(abi)} entries for {contract_name}")
            return abi

        except json.JSONDecodeError as e:
            raise ABILoadError(f"Failed to parse ABI JSON: {str(e)}") from e
        except Exception as e:
            if isinstance(e, ABILoadError):
                raise
            raise ABILoadError(f"Unexpected error loading ABI: {str(e)}") from e

    def get_contract(self, contract_name: str, address: str) -> Contract:
        """Create a Web3 contract instance.

        Args:
            contract_name: Name of the contract (must match artifact filename)
            address: Deployed contract address

        Returns:
            Web3 Contract instance ready for interaction

        Raises:
            ABILoadError: If ABI loading fails
            ValueError: If address is invalid

        Example:
            >>> contract = utility.get_contract("IdentityRegistry", "0x5FbDB2...")
            >>> # Call function: contract.functions.getAgent(1).call()
            >>> # Send tx: contract.functions.newAgent("x.com", addr).transact()
        """
        if not self.w3.is_address(address):
            raise ValueError(f"Invalid contract address: {address}")

        checksum_address = self.w3.to_checksum_address(address)
        abi = self._load_abi(contract_name)
        contract = self.w3.eth.contract(address=checksum_address, abi=abi)

        logger.debug(f"Contract instance created: {contract_name} at {address}")
        return contract
