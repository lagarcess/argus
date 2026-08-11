"""The unauthenticated read path, proven by construction.

The public route resolves one id to one frozen row and can reach nothing else.
These assert that narrowness against the query the gateway actually issues, and
that the path answers honestly when the row it finds cannot be read.
"""

from __future__ import annotations

from typing import Any

import pytest
from argus.domain.public_excerpts import (
    PublicExcerptUnreadableError,
    build_public_excerpt_payload,
)
from argus.domain.supabase_public_excerpts import (
    OWNER_COLUMNS,
    PUBLIC_VIEW_COLUMNS,
    TABLE,
    SupabasePublicExcerptMixin,
)

from tests.public_excerpt_factories import (
    BUY_AND_HOLD_CONFIG_SNAPSHOT,
    build_artifact,
    build_chart,
    utc,
)


def _payload(**overrides: Any):
    kwargs: dict[str, Any] = {
        "artifact": build_artifact(),
        "run_chart": build_chart(),
        "run_config_snapshot": BUY_AND_HOLD_CONFIG_SNAPSHOT,
        "owner_note": None,
        "content_language": "en",
    }
    kwargs.update(overrides)
    return build_public_excerpt_payload(**kwargs)


# ── Construction proof for the public read path ───────────────────────────────


class _RecordingQuery:
    def __init__(self, log: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        self._log = log
        self._rows = rows

    def select(self, columns: str) -> _RecordingQuery:
        self._log["selects"].append(columns)
        return self

    def eq(self, column: str, value: Any) -> _RecordingQuery:
        self._log["filters"].append((column, value))
        return self

    def is_(self, column: str, value: Any) -> _RecordingQuery:
        self._log["filters"].append((column, value))
        return self

    def limit(self, count: int) -> _RecordingQuery:
        return self

    def order(self, column: str, desc: bool = False) -> _RecordingQuery:
        return self

    def execute(self) -> Any:
        class _Result:
            data = self._rows

        return _Result()


class _RecordingClient:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.log: dict[str, Any] = {"tables": [], "selects": [], "filters": [], "rpc": []}
        self._rows = rows or []

    def table(self, name: str) -> _RecordingQuery:
        self.log["tables"].append(name)
        return _RecordingQuery(self.log, self._rows)

    def rpc(self, name: str, params: dict[str, Any]) -> Any:
        self.log["rpc"].append(name)
        raise AssertionError("The public read must not call an RPC.")


class _Gateway(SupabasePublicExcerptMixin):
    def __init__(self, client: _RecordingClient) -> None:
        self.client = client


def test_public_read_touches_one_table_with_a_fixed_column_list() -> None:
    payload = _payload()
    client = _RecordingClient(
        rows=[
            {
                "public_id": "abcdefghijklmnopqrstuvwx",
                "payload": payload.model_dump(mode="json"),
                "created_at": utc().isoformat(),
                "revoked_at": None,
            }
        ]
    )
    view = _Gateway(client).read_public_excerpt_view(public_id="abcdefghijklmnopqrstuvwx")

    assert view.status == "available"
    assert client.log["tables"] == [TABLE]
    assert client.log["selects"] == [",".join(PUBLIC_VIEW_COLUMNS)]
    assert client.log["filters"] == [("public_id", "abcdefghijklmnopqrstuvwx")]
    assert client.log["rpc"] == []


def test_public_read_column_list_excludes_every_ownership_reference() -> None:
    assert PUBLIC_VIEW_COLUMNS == ("public_id", "payload", "created_at", "revoked_at")
    forbidden = {
        "owner_id",
        "evidence_artifact_id",
        "source_conversation_id",
        "source_run_id",
        "title",
        "payload_digest",
        "revocation_reason",
    }
    assert forbidden.isdisjoint(PUBLIC_VIEW_COLUMNS)
    assert forbidden.issubset(set(OWNER_COLUMNS))


def test_unknown_public_id_answers_a_tombstone_rather_than_an_oracle() -> None:
    client = _RecordingClient(rows=[])
    view = _Gateway(client).read_public_excerpt_view(public_id="unknown-public-id-xxxx")
    assert view.status == "revoked"
    assert view.payload is None


def test_a_payload_this_build_cannot_read_is_temporary_not_a_tombstone() -> None:
    """A stranger's first Argus page must not answer with a crash or with a lie.

    The stored payload is validated with extra="forbid", so a row written by a
    different shape raises rather than degrades. Raising uncaught answers a public
    link with a 500. Answering with the tombstone would be worse in a quieter way:
    it says gone for good about a receipt that is intact and will read fine again.
    """
    client = _RecordingClient(
        rows=[
            {
                "public_id": "abcdefghijklmnopqrstuvwx",
                "payload": {"schema_version": 1, "from_some_other_shape": True},
                "created_at": utc().isoformat(),
                "revoked_at": None,
            }
        ]
    )
    with pytest.raises(PublicExcerptUnreadableError):
        _Gateway(client).read_public_excerpt_view(public_id="abcdefghijklmnopqrstuvwx")


def test_a_revoked_row_is_still_a_tombstone_without_reading_its_payload() -> None:
    """Revocation is decided by the column, so an unreadable payload cannot mask it."""
    client = _RecordingClient(
        rows=[
            {
                "public_id": "abcdefghijklmnopqrstuvwx",
                "payload": {"from_some_other_shape": True},
                "created_at": utc().isoformat(),
                "revoked_at": utc().isoformat(),
            }
        ]
    )
    view = _Gateway(client).read_public_excerpt_view(public_id="abcdefghijklmnopqrstuvwx")
    assert view.status == "revoked"
    assert view.payload is None
