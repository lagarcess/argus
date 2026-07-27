from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class GuestWorkspace(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    conversation_id: str | None
    status: Literal["active", "claiming", "claimed", "expired"]
    created_at: datetime
    expires_at: datetime
    claimed_by: str | None
    claimed_at: datetime | None
    updated_at: datetime
