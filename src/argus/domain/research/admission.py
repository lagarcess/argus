"""Request-scoped admission for one billable research provider path.

The API owns durable allowance state. Runtime research operations own the
precise point where a cache miss becomes provider work. This context is the
small bridge between them: the first provider path claims capacity, while
later defensive checks in the same turn reuse that result.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable, Iterator


@dataclass(frozen=True)
class ResearchAttemptAdmission:
    """Whether this turn may start billable research provider work."""

    available: bool
    guest_exhausted: bool = False


class ResearchCapacityExhausted(RuntimeError):
    """A provider path lost the atomic capacity claim."""

    def __init__(self, admission: ResearchAttemptAdmission) -> None:
        super().__init__("Research capacity exhausted")
        self.admission = admission


@dataclass
class _AdmissionScope:
    claim: Callable[[], ResearchAttemptAdmission]
    result: ResearchAttemptAdmission | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


_CURRENT_SCOPE: ContextVar[_AdmissionScope | None] = ContextVar(
    "argus_research_attempt_admission",
    default=None,
)


@contextmanager
def research_attempt_admission_context(
    claim: Callable[[], ResearchAttemptAdmission],
) -> Iterator[None]:
    """Install the API's atomic claim for the duration of one chat turn."""

    token = _CURRENT_SCOPE.set(_AdmissionScope(claim=claim))
    try:
        yield
    finally:
        _CURRENT_SCOPE.reset(token)


def claim_current_research_attempt() -> ResearchAttemptAdmission:
    """Claim once per request; non-API callers remain dependency-free."""

    scope = _CURRENT_SCOPE.get()
    if scope is None:
        return ResearchAttemptAdmission(available=True)
    with scope.lock:
        if scope.result is None:
            scope.result = scope.claim()
        return scope.result
