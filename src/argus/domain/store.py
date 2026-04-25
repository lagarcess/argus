from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from argus.api.schemas import (
    Collection,
    Conversation,
    Message,
    OnboardingState,
    Strategy,
    User,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AlphaStore:
    users: dict[str, User] = field(default_factory=dict)
    conversations: dict[str, Conversation] = field(default_factory=dict)
    messages: dict[str, list[Message]] = field(default_factory=dict)
    strategies: dict[str, Strategy] = field(default_factory=dict)
    collections: dict[str, Collection] = field(default_factory=dict)
    collection_strategies: dict[str, set[str]] = field(default_factory=dict)
    backtest_runs: dict[str, Any] = field(default_factory=dict)
    backtest_run_owners: dict[str, str] = field(default_factory=dict)
    idempotency: dict[tuple[str, str, str], Any] = field(default_factory=dict)
    feedback: list[dict[str, Any]] = field(default_factory=list)

    def reset(self) -> None:
        self.users.clear()
        self.conversations.clear()
        self.messages.clear()
        self.strategies.clear()
        self.collections.clear()
        self.collection_strategies.clear()
        self.backtest_runs.clear()
        self.backtest_run_owners.clear()
        self.idempotency.clear()
        self.feedback.clear()

    def get_or_create_dev_user(self) -> User:
        user_id = "00000000-0000-0000-0000-000000000001"
        if user_id not in self.users:
            now = utcnow()
            self.users[user_id] = User(
                id=user_id,
                email="developer@argus.local",
                username="mock-developer",
                display_name="Mock Developer",
                language="en",
                locale="en-US",
                theme="dark",
                is_admin=True,
                onboarding=OnboardingState(),
                created_at=now,
                updated_at=now,
            )
        return self.users[user_id]

    def new_id(self) -> str:
        return str(uuid4())
