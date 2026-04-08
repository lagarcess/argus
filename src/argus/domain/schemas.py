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
    last_quota_reset: Optional[datetime] = None
    feature_flags: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)
