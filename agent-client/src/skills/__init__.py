"""Skill clients for calling ROFL-based agent servers.

This package provides trustless verification for agent-to-agent skill calls.
All skills use the same verification pattern:
1. Server discovery
2. HTTP call
3. Signature verification
4. Identity registry check
5. ROFL attestation verification
"""

from .verified_call import call_verified_skill, VerifiedCallError
from .price_client import get_verified_price

__all__ = [
    "call_verified_skill",
    "VerifiedCallError",
    "get_verified_price",
]
