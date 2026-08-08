from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from argus.domain.guest_cleanup import cleanup_expired_guest_workspaces


@dataclass
class _CleanupGateway:
    candidates: list[dict[str, object]]
    claims: list[tuple[int, bool]] = field(default_factory=list)
    purges: list[str] = field(default_factory=list)

    def claim_expired_guest_workspaces(
        self,
        *,
        limit: int,
        dry_run: bool,
    ) -> list[dict[str, object]]:
        self.claims.append((limit, dry_run))
        return list(self.candidates)

    def purge_expired_visitor_usage(self, *, before: datetime | None = None) -> int:
        self.purges.append("visitor_usage")
        return 3

    def purge_expired_guest_funnel_milestones(
        self,
        *,
        before: datetime | None = None,
    ) -> int:
        self.purges.append("funnel_milestones")
        return 2


def test_cleanup_dry_run_never_calls_auth_admin_or_deletes_retained_rows() -> None:
    gateway = _CleanupGateway(candidates=[{"user_id": "guest-1"}])

    result = cleanup_expired_guest_workspaces(gateway, limit=25, dry_run=True)

    assert result.as_dict() == {
        "dry_run": True,
        "selected": 1,
        "auth_deleted": 0,
        "auth_preserved": 0,
        "auth_delete_failed": 0,
        "visitor_usage_purged": 0,
        "funnel_milestones_purged": 0,
        "purge_failed": 0,
    }
    assert gateway.claims == [(25, True)]
    assert gateway.purges == []


def test_cleanup_reports_transactional_auth_deletion_results() -> None:
    gateway = _CleanupGateway(
        candidates=[
            {"user_id": "anonymous-user", "auth_deleted": True},
            {"user_id": "converted-user", "auth_deleted": False},
        ]
    )

    result = cleanup_expired_guest_workspaces(gateway, limit=2, dry_run=False)

    assert result.as_dict() == {
        "dry_run": False,
        "selected": 2,
        "auth_deleted": 1,
        "auth_preserved": 1,
        "auth_delete_failed": 0,
        "visitor_usage_purged": 3,
        "funnel_milestones_purged": 2,
        "purge_failed": 0,
    }
    assert set(result.as_dict()) == {
        "dry_run",
        "selected",
        "auth_deleted",
        "auth_preserved",
        "auth_delete_failed",
        "visitor_usage_purged",
        "funnel_milestones_purged",
        "purge_failed",
    }


def test_cleanup_purges_expired_unowned_rows_on_a_real_run() -> None:
    """The visitor-keyed tables have no owner to cascade from, so this job is
    the only thing that deletes them."""
    gateway = _CleanupGateway(candidates=[])

    cleanup_expired_guest_workspaces(gateway, limit=1, dry_run=False)

    assert gateway.purges == ["visitor_usage", "funnel_milestones"]


def test_cleanup_rejects_unbounded_limit() -> None:
    gateway = _CleanupGateway(candidates=[])

    for limit in (0, 101):
        try:
            cleanup_expired_guest_workspaces(gateway, limit=limit, dry_run=False)
        except ValueError as exc:
            assert "between 1 and 100" in str(exc)
        else:
            raise AssertionError("unbounded cleanup limit was accepted")
