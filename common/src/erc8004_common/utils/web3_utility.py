"""Web3 utilities for ERC-8004 applications.

Provides comprehensive Web3 abstraction layer:
- ABI loading from Hardhat compiled artifacts
- Web3 connection management
- Transaction signing middleware
- Contract instance creation
- Message signing and verification (EIP-191)

Use contract.functions.myFunction().transact() for transactions.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Any

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract
from web3.middleware import SignAndSendRawMiddlewareBuilder

logger = logging.getLogger(__name__)


class Web3UtilityError(Exception):
    """Base exception for Web3Utility errors."""
    pass


class ABILoadError(Web3UtilityError):
    """Raised when ABI loading fails."""
    pass


class ConnectionError(Web3UtilityError):
    """Raised when Web3 connection fails."""
    pass


class SigningError(Web3UtilityError):
    """Raised when message signing fails."""
    pass


class Web3Utility:
    """Utility class for Web3 operations.

    Manages Web3 connections, ABI loading, contract interactions,
    and message signing/verification.

    Example:
        >>> config = Config()
        >>> utility = Web3Utility(config)
        >>>
        >>> # Contract interaction
        >>> contract = utility.get_contract("IdentityRegistry", "0x123...")
        >>> tx_hash = contract.functions.newAgent("example.com", addr).transact()
        >>>
        >>> # Message signing
        >>> signed = utility.sign_data({"price": 45000, "symbol": "BTC"})
        >>> is_valid, signer = utility.verify_signature(signed)
    """

    ABI_DIR = Path("/app/abis")

    def __init__(self, config: Any):
        """Initialize Web3Utility with configuration.

        Args:
            config: Configuration object with rpc_url and optional private_key

        Raises:
            ConnectionError: If Web3 connection fails
        """
        self.config = config
        self.account: Optional[LocalAccount] = None

        logger.info(f"Initializing Web3Utility with RPC: {config.rpc_url}")

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
            raise Web3UtilityError(
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

    def sign_data(self, data: dict) -> dict:
        """Sign data with EIP-191 (Ethereum Signed Message).

        Creates a deterministic message from dict, hashes it, and signs
        with the configured private key. Returns signed data package.

        Args:
            data: Dictionary of data to sign (will be JSON serialized)

        Returns:
            Dictionary with original data, signature, and signer address:
            {
                "data": {...original data...},
                "signature": "0x...",
                "signer": "0x..."
            }

        Raises:
            SigningError: If signing fails or no account configured

        Example:
            >>> utility = Web3Utility(config_with_private_key)
            >>> signed = utility.sign_data({"price": 45000, "timestamp": "2025-10-09"})
            >>> print(signed["signature"])
            "0x1a8bbe6eab8c72a219385681efefe565..."
        """
        if not self.account:
            raise SigningError(
                "Cannot sign data: no private key configured. "
                "Provide private_key in config to enable signing."
            )

        try:
            # Create deterministic message from data
            # Sort keys to ensure consistency
            message_str = json.dumps(data, sort_keys=True)

            # Encode message using EIP-191 (Ethereum Signed Message)
            message = encode_defunct(text=message_str)

            # Sign message
            signed_message = self.account.sign_message(message)

            # Return signed package
            return {
                "data": data,
                "signature": signed_message.signature.hex(),
                "signer": self.account.address,
            }

        except Exception as e:
            raise SigningError(f"Failed to sign data: {str(e)}") from e

    def verify_signature(self, signed_data: dict) -> tuple[bool, str]:
        """Verify signature and recover signer address.

        Verifies that the signature is valid and matches the claimed signer.
        Uses EIP-191 message encoding.

        Args:
            signed_data: Dictionary with 'data', 'signature', and 'signer' fields

        Returns:
            Tuple of (is_valid, recovered_address):
            - is_valid: True if signature matches data and signer
            - recovered_address: Address recovered from signature

        Raises:
            SigningError: If verification fails due to invalid format

        Example:
            >>> is_valid, recovered = utility.verify_signature(signed_data)
            >>> if is_valid:
            ...     print(f"Valid signature from {recovered}")
            ... else:
            ...     print("Invalid signature!")
        """
        try:
            # Extract fields
            data = signed_data.get("data")
            signature = signed_data.get("signature")
            claimed_signer = signed_data.get("signer")

            if not all([data, signature, claimed_signer]):
                raise SigningError(
                    "Invalid signed_data format: missing 'data', 'signature', or 'signer'"
                )

            # Reconstruct message (same as signing)
            message_str = json.dumps(data, sort_keys=True)
            message = encode_defunct(text=message_str)

            # Recover address from signature
            recovered_address = Account.recover_message(message, signature=signature)

            # Check if recovered address matches claimed signer
            is_valid = recovered_address.lower() == claimed_signer.lower()

            return is_valid, recovered_address

        except Exception as e:
            raise SigningError(f"Failed to verify signature: {str(e)}") from e
