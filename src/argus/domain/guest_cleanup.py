from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from loguru import logger

from argus.observability.guest_funnel import capture_guest_funnel_event


class GuestCleanupGateway(Protocol):
    def claim_expired_guest_workspaces(
        self,
        *,
        limit: int,
        dry_run: bool,
    ) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class GuestCleanupResult:
    dry_run: bool
    selected: int
    auth_deleted: int
    auth_preserved: int
    auth_delete_failed: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def cleanup_expired_guest_workspaces(
    gateway: GuestCleanupGateway,
    *,
    limit: int,
    dry_run: bool,
) -> GuestCleanupResult:
    if limit < 1 or limit > 100:
        raise ValueError("cleanup limit must be between 1 and 100")
    candidates = gateway.claim_expired_guest_workspaces(
        limit=limit,
        dry_run=dry_run,
    )
    if dry_run:
        return GuestCleanupResult(
            dry_run=True,
            selected=len(candidates),
            auth_deleted=0,
            auth_preserved=0,
            auth_delete_failed=0,
        )

    deleted = 0
    preserved = 0
    failed = 0
    for candidate in candidates:
        user_id = str(candidate.get("user_id") or "")
        if not user_id:
            failed += 1
        elif candidate.get("auth_deleted") is True:
            deleted += 1
            if candidate.get("cleanup_reason") != "expired_workspace":
                continue
            try:
                capture_guest_funnel_event(
                    "guest_session_expired",
                    user_id=user_id,
                    surface="cleanup",
                    capability_category="account",
                    terminal_outcome="expired",
                )
            except Exception:
                logger.opt(exception=True).warning(
                    "Guest expiry event emission failed",
                    product_event="guest_session_expired",
                )
        else:
            preserved += 1
    return GuestCleanupResult(
        dry_run=False,
        selected=len(candidates),
        auth_deleted=deleted,
        auth_preserved=preserved,
        auth_delete_failed=failed,
    )
