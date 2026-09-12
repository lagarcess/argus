"""What a person has shown interest in, read only from typed records they own.

Never from message text and never from personalization memory.
"""

from __future__ import annotations

from argus.api.chat.persistence import count_completed_runs_for_user
from argus.api.schemas import DemonstratedInterest


def demonstrated_interest(user_id: str) -> DemonstratedInterest:
    return DemonstratedInterest(markets=count_completed_runs_for_user(user_id) > 0)
