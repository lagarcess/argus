from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from argus.api.memory_run_dossiers import list_memory_run_dossier_source_rows
from argus.api.schemas import Message, PaginatedRunDossiers
from argus.domain.postgres_run_dossier_reader import (
    PostgresRunDossierReader,
    RunDossierCursorError,
    RunDossierSourcePage,
)
from argus.domain.run_dossiers import project_run_dossier
from argus.domain.store import AlphaStore

OWNER_ID = "00000000-0000-0000-0000-000000000001"
CONVERSATION_ID = "00000000-0000-0000-0000-000000000101"
RUN_ID = "00000000-0000-0000-0000-000000000401"
SECOND_RUN_ID = "00000000-0000-0000-0000-000000000402"
COMPLETED_AT = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.result_sets = result_sets
        self.executions: list[tuple[str, dict[str, Any]]] = []

    def __enter__(self) -> _Cursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: str, params: dict[str, Any]) -> None:
        self.executions.append((query, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self.result_sets.pop(0)


class _Connection:
    def __init__(self, cursor: _Cursor) -> None:
        self._cursor = cursor

    def cursor(self, **_kwargs: Any) -> _Cursor:
        return self._cursor


class _Pool:
    def __init__(self, result_sets: list[list[dict[str, Any]]]) -> None:
        self.cursor = _Cursor(result_sets)
        self.timeouts: list[float] = []

    @contextmanager
    def connection(self, *, timeout: float):
        self.timeouts.append(timeout)
        yield _Connection(self.cursor)


def _source_row() -> dict[str, Any]:
    return {
        "run_payload": {
            "id": RUN_ID,
            "conversation_id": CONVERSATION_ID,
            "status": "completed",
            "asset_class": "equity",
            "symbols": ["TSLA"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {"template": "buy_and_hold"},
            "conversation_result_card": {"title": "TSLA run"},
            "created_at": COMPLETED_AT,
            "completed_at": COMPLETED_AT,
        },
        "artifact_payload": {
            "id": "00000000-0000-0000-0000-000000000301",
            "source_conversation_id": CONVERSATION_ID,
            "source_run_id": RUN_ID,
            "title": "TSLA evidence",
            "digest": "TSLA result",
            "payload": {},
            "created_at": COMPLETED_AT,
            "updated_at": COMPLETED_AT,
        },
        "decision_payload": None,
        "result_message_id": "00000000-0000-0000-0000-000000000201",
    }


@pytest.fixture
def shared_adapter_rows() -> list[dict[str, Any]]:
    older_at = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)
    return [
        {
            "run_payload": _source_row()["run_payload"],
            "artifact_payload": _source_row()["artifact_payload"],
            "decision_payload": {
                "id": "00000000-0000-0000-0000-000000000501",
                "evidence_artifact_id": (
                    "00000000-0000-0000-0000-000000000301"
                ),
                "source_conversation_id": CONVERSATION_ID,
                "decision_state": "watching",
                "note": "Watch this result.",
                "created_at": COMPLETED_AT,
                "updated_at": COMPLETED_AT,
            },
            "result_message_id": (
                "00000000-0000-0000-0000-000000000201"
            ),
        },
        {
            "run_payload": {
                **_source_row()["run_payload"],
                "id": SECOND_RUN_ID,
                "created_at": older_at,
                "completed_at": older_at,
            },
            "artifact_payload": {
                **_source_row()["artifact_payload"],
                "id": "00000000-0000-0000-0000-000000000302",
                "source_run_id": SECOND_RUN_ID,
                "created_at": older_at,
                "updated_at": older_at,
            },
            "decision_payload": None,
            "result_message_id": None,
        },
    ]


def _serialized_response(page: RunDossierSourcePage) -> dict[str, Any]:
    response = PaginatedRunDossiers(
        items=[
            project_run_dossier(
                run=row.run,
                artifact=row.artifact,
                decision=row.decision,
                result_message_id=row.result_message_id,
                decision_action_availability="available",
                language="en",
            )
            for row in page.rows
        ],
        next_cursor=None,
        total_runs=page.total_runs,
        decided_runs=page.decided_runs,
    )
    return response.model_dump(mode="json")


def test_postgres_reader_uses_scalar_counts_and_one_bounded_page_query() -> None:
    pool = _Pool(
        [
            [{"total_runs": 7, "decided_runs": 5}],
            [_source_row()],
        ]
    )

    page = PostgresRunDossierReader(pool).list_source_rows(
        user_id=OWNER_ID,
        conversation_id=CONVERSATION_ID,
        limit=21,
        cursor_completed_at=None,
        cursor_run_id=None,
    )

    assert page.total_runs == 7
    assert page.decided_runs == 5
    assert [row.run["id"] for row in page.rows] == [RUN_ID]
    assert page.rows[0].result_message_id
    assert len(pool.cursor.executions) == 2
    page_sql, page_params = pool.cursor.executions[-1]
    assert "limit %(limit)s" in page_sql
    assert page_params["limit"] == 21
    assert "message.metadata->'result_card'" in page_sql
    assert page_sql.index("message.metadata->'result_card'") < page_sql.index(
        "message.created_at desc"
    )
    assert "order by coalesce(br.updated_at, br.created_at) desc, br.id desc" in page_sql
    assert pool.timeouts == [2.0]


def test_postgres_reader_validates_cursor_pivot_before_counts_or_page() -> None:
    pool = _Pool([[]])

    with pytest.raises(RunDossierCursorError):
        PostgresRunDossierReader(pool).list_source_rows(
            user_id=OWNER_ID,
            conversation_id=CONVERSATION_ID,
            limit=21,
            cursor_completed_at=COMPLETED_AT,
            cursor_run_id=RUN_ID,
        )

    assert len(pool.cursor.executions) == 1


def test_postgres_reader_accepts_only_canonical_uuid_cursor_ids() -> None:
    pool = _Pool([])

    with pytest.raises(RunDossierCursorError):
        PostgresRunDossierReader(pool).list_source_rows(
            user_id=OWNER_ID,
            conversation_id=CONVERSATION_ID,
            limit=21,
            cursor_completed_at=COMPLETED_AT,
            cursor_run_id="not-a-uuid",
        )

    assert pool.cursor.executions == []


def test_memory_and_postgres_adapters_serialize_the_same_complete_page(
    shared_adapter_rows: list[dict[str, Any]],
) -> None:
    store = AlphaStore()
    for row in shared_adapter_rows:
        run = row["run_payload"]
        artifact = row["artifact_payload"]
        store.backtest_runs[run["id"]] = run
        store.backtest_run_owners[run["id"]] = OWNER_ID
        store.evidence_artifacts[artifact["id"]] = artifact
        store.evidence_artifact_owners[artifact["id"]] = OWNER_ID
        decision = row["decision_payload"]
        if decision is not None:
            store.decision_notes[decision["id"]] = decision
            store.decision_note_owners[decision["id"]] = OWNER_ID
        if row["result_message_id"] is not None:
            store.messages.setdefault(CONVERSATION_ID, []).append(
                Message(
                    id=row["result_message_id"],
                    conversation_id=CONVERSATION_ID,
                    role="assistant",
                    content="Result",
                    created_at=run["completed_at"],
                    metadata={
                        "result_run_id": run["id"],
                        "result_card": run["conversation_result_card"],
                    },
                )
            )
            store.messages[CONVERSATION_ID].append(
                Message(
                    id="00000000-0000-0000-0000-000000000209",
                    conversation_id=CONVERSATION_ID,
                    role="assistant",
                    content="Later follow-up",
                    created_at=run["completed_at"] + timedelta(minutes=1),
                    metadata={"latest_run_id": run["id"]},
                )
            )

    memory_page = list_memory_run_dossier_source_rows(
        store=store,
        user_id=OWNER_ID,
        conversation_id=CONVERSATION_ID,
        limit=20,
        cursor_completed_at=None,
        cursor_run_id=None,
    )
    postgres_page = PostgresRunDossierReader(
        _Pool(
            [
                [{"total_runs": 2, "decided_runs": 1}],
                shared_adapter_rows,
            ]
        )
    ).list_source_rows(
        user_id=OWNER_ID,
        conversation_id=CONVERSATION_ID,
        limit=20,
        cursor_completed_at=None,
        cursor_run_id=None,
    )

    memory_response = _serialized_response(memory_page)
    postgres_response = _serialized_response(postgres_page)

    assert memory_response == postgres_response
    assert memory_response["items"][1]["decision"] is None
    assert memory_response["items"][1]["result_message_id"] is None
