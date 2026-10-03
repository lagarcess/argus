"""PostHog person deletion for account deletion (Lane 6, step 8).

Until Lucas supplies a PostHog key that can delete persons,
``ARGUS_ANALYTICS_DELETION_ENABLED`` stays off and the recording fake is used.
The run then reports the PostHog step as recorded by the fake, not as done at
PostHog.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal, Protocol

AnalyticsDeletionOutcome = Literal["deleted", "recorded_by_fake", "failed"]
FLAG = "ARGUS_ANALYTICS_DELETION_ENABLED"


class AnalyticsDeletion(Protocol):
    def delete_person(self, distinct_id: str) -> AnalyticsDeletionOutcome:
        """Delete the person and their events by distinct id. Never raises."""
        ...


@dataclass
class RecordingAnalyticsDeletion:
    """The default: records the request, contacts nobody."""

    calls: list[dict] = field(default_factory=list)

    def delete_person(self, distinct_id: str) -> AnalyticsDeletionOutcome:
        self.calls.append({"distinct_id": distinct_id, "delete_events": True})
        return "recorded_by_fake"


def analytics_deletion_from_env() -> AnalyticsDeletion:
    if os.getenv(FLAG, "").strip().lower() in {"1", "true", "yes", "on"}:
        # No real adapter ships until a person-deleting key exists. Failing
        # here keeps the flag from silently pointing at the fake.
        raise RuntimeError(f"{FLAG} is on but no PostHog deletion adapter is configured")
    return RecordingAnalyticsDeletion()
