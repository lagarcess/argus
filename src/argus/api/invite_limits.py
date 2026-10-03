"""Rate limits for looking up invites by code or link (#789).

Applies to household preview and accept and to beta preview and redeem, for a
code or a token alike, per client IP (``resolve_client_ip``) and per account.
There is no founder or admin bypass.

- Every lookup spends one request from ``SlidingWindowLimiter``.
- A lookup that names no invitation (unknown or malformed code or token) also
  spends from a separate failure budget, ``WeightedWindow``, hourly and daily.
  A found invitation, even an expired or used one, costs nothing there, so
  failed guesses weigh far more than real use.
- Once a budget is spent the answer is ``429 invite_rate_limited`` with
  ``Retry-After``, checked before the lookup so a blocked caller learns nothing.

Like every limiter in this API the counts are process-local. Production runs
one Render instance with one Uvicorn worker, and the code space (60 bits) is
sized so the limit is defense in depth, not the only protection. With N
processes an attacker gets at most N times the budget; see the "Invite code
security" section of docs/API_CONTRACT.md for the numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException, Request

from argus.api.client_ip import resolve_client_ip
from argus.api.dependencies import problem
from argus.api.rate_limits import SlidingWindowLimiter
from argus.api.shortcuts_limits import WeightedWindow
from argus.domain.household.errors import InvitationNotFound

HOUR = 3600
DAY = 86400
# Lookups of any outcome, per IP and per account.
REQUESTS_PER_MINUTE = 30
# Lookups that named no invitation. (limit, window, counter); one window per
# counter, as WeightedWindow expects.
FAILED_PER_IP = ((20, HOUR, WeightedWindow()), (60, DAY, WeightedWindow()))
FAILED_PER_ACCOUNT = ((10, HOUR, WeightedWindow()), (30, DAY, WeightedWindow()))

_requests = SlidingWindowLimiter()

T = TypeVar("T")


def reset() -> None:
    _requests.reset()
    for _, _, counter in FAILED_PER_IP + FAILED_PER_ACCOUNT:
        counter.reset()


def _keys(request: Request, user_id: str) -> tuple[str, str]:
    return f"invite-code:ip:{resolve_client_ip(request)}", f"invite-code:user:{user_id}"


def _budgets(request: Request, user_id: str):  # noqa: ANN202
    ip_key, user_key = _keys(request, user_id)
    for limit, window, counter in FAILED_PER_IP:
        yield ip_key, limit, window, counter
    for limit, window, counter in FAILED_PER_ACCOUNT:
        yield user_key, limit, window, counter


def rate_limited_problem(request: Request, wait: int) -> HTTPException:
    return problem(
        request,
        status_code=429,
        code="invite_rate_limited",
        title="Too Many Requests",
        detail="Too many invite code attempts. Try again later.",
        headers={"Retry-After": str(wait)},
    )


def check(request: Request, user_id: str) -> None:
    """Refuse before the lookup when a failure or request budget is spent."""
    waits = [
        counter.blocked(key, limit=limit, window=window)
        for key, limit, window, counter in _budgets(request, user_id)
    ]
    blocked = [w for w in waits if w is not None]
    if blocked:
        raise rate_limited_problem(request, max(blocked))
    wait = _requests.record_or_retry_after(
        keys=_keys(request, user_id), limit=REQUESTS_PER_MINUTE, window_seconds=60
    )
    if wait is not None:
        raise rate_limited_problem(request, wait)


def record_failure(request: Request, user_id: str) -> None:
    for key, limit, window, counter in _budgets(request, user_id):
        counter.spend(key, 1, limit=limit, window=window)


def guarded(request: Request, user_id: str, action: Callable[[], T]) -> Callable[[], T]:
    """Check the budgets now; charge a failure if the lookup finds nothing."""
    check(request, user_id)

    def run() -> T:
        try:
            return action()
        except InvitationNotFound:
            record_failure(request, user_id)
            raise

    return run
