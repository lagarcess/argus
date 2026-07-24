from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


class GuestCleanupGateway(Protocol):
    def claim_expired_guest_workspaces(
        self,
        *,
        limit: int,
        dry_run: bool,
    ) -> list[dict[str, object]]: ...

    def delete_anonymous_auth_user(self, user_id: str) -> bool: ...


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
            continue
        try:
            was_deleted = gateway.delete_anonymous_auth_user(user_id)
        except Exception:
            failed += 1
        else:
            if was_deleted:
                deleted += 1
            else:
                preserved += 1
    return GuestCleanupResult(
        dry_run=False,
        selected=len(candidates),
        auth_deleted=deleted,
        auth_preserved=preserved,
        auth_delete_failed=failed,
    )
