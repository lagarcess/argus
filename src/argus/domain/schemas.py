"""
Domain Schemas for Argus.

Minimal schema definitions for the backtesting engine.
These will be expanded as the API and web app are built.
"""

from enum import Enum

from pydantic import BaseModel


class AssetClass(str, Enum):
    """Asset class classification for trading instruments."""

    CRYPTO = "CRYPTO"
    EQUITY = "EQUITY"


class User(BaseModel):
    """User profile and identity."""

    user_id: str
    email: str
    subscription_tier: str = "free"
