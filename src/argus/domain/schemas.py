"""
Domain Schemas for Argus.

Minimal schema definitions for the backtesting engine.
These will be expanded as the API and web app are built.
"""

from enum import Enum


class AssetClass(str, Enum):
    """Asset class classification for trading instruments."""

    CRYPTO = "CRYPTO"
    EQUITY = "EQUITY"
