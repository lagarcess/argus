"""
Domain Schemas for Argus.

Minimal schema definitions for the backtesting engine.
These will be expanded as the API and web app are built.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class AssetClass(str, Enum):
    """Asset class classification for trading instruments."""

    CRYPTO = "CRYPTO"
    EQUITY = "EQUITY"

    @classmethod
    def from_alpaca(cls, alpaca_class: str) -> "AssetClass":
        """Map Alpaca asset class strings to internal enum."""
        mapping = {
            "crypto": cls.CRYPTO,
            "us_equity": cls.EQUITY,
        }
        return mapping.get(alpaca_class.lower(), cls.EQUITY)

    @classmethod
    def from_symbol(cls, symbol: str) -> "AssetClass":
        """
        Heuristic to determine asset class from symbol.
        Crypto symbols typically contain '/' or specific coin identifiers in Alpaca.
        """
        s = symbol.upper()
        # Alpaca crypto format 'BTC/USD' or 'USDT'
        is_crypto = "/" in s or any(
            coin in s for coin in ["BTC", "ETH", "SOL", "USDT", "DOGE"]
        )
        return cls.CRYPTO if is_crypto else cls.EQUITY


class UserResponse(BaseModel):
    """User profile and identity response."""

    id: str = Field(
        alias="user_id"
    )  # Keeping user_id mapping for internal use if needed, but returning id
    email: str
    is_admin: bool = False
    subscription_tier: str = "free"
    theme: str = "dark"
    lang: str = "en"
    backtest_quota: int = 50
    remaining_quota: int = 50
    ai_draft_quota: int = 5
    remaining_ai_draft_quota: int = 5
    onboarding_completed: bool = False
    onboarding_step: str = "profile"
    onboarding_intent: Optional[str] = None
    last_quota_reset: Optional[datetime] = None
    feature_flags: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
