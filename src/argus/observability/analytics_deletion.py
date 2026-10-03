"""PostHog person deletion for account deletion (Lane 6, step 8).

Until a real deletion adapter ships (the issue that blocks the Lane 6 flag),
``ARGUS_ANALYTICS_DELETION_ENABLED`` stays off and the recording fake is used.
The fake contacts nobody and returns ``recorded_by_fake``, which the deletion
run counts as done only where the fake is explicitly the adapter (tests, local
dev): anywhere else the PostHog step stays pending.

Note for the real adapter: our events are personless
(``$process_person_profile`` is false in ``envelope.py``), so PostHog's
``persons/bulk_delete`` finds no person (``persons_found: 0``) and its 200
does not mean anything was deleted. Events must be deleted by distinct id.
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
        # PostHog's bulk delete takes a list of distinct ids.
        self.calls.append({"distinct_ids": [distinct_id], "delete_events": True})
        return "recorded_by_fake"


def fake_analytics_allowed() -> bool:
    """Only an explicitly local, dev or test environment may count the fake
    as done. Unset counts as not allowed, so a deploy that forgets to name its
    environment fails safe (the PostHog step stays pending)."""
    for name in ("APP_ENV", "ARGUS_ENV", "ARGUS_APP_ENV", "ENVIRONMENT"):
        value = os.getenv(name, "").strip().lower()
        if value:
            return value in {"local", "development", "dev", "test"}
    return False


def analytics_deletion_from_env() -> AnalyticsDeletion:
    if os.getenv(FLAG, "").strip().lower() in {"1", "true", "yes", "on"}:
        # No real adapter ships until a person-deleting key exists. Failing
        # here keeps the flag from silently pointing at the fake.
        raise RuntimeError(f"{FLAG} is on but no PostHog deletion adapter is configured")
    return RecordingAnalyticsDeletion()
