from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from argus.api.schemas import BacktestRun, Message
from argus.domain.backtest_message_projection import (
    completed_backtest_run_ids,
    hydrate_backtest_job_action_messages,
    hydrate_completed_backtest_job_messages,
)
from argus.domain.store import utcnow
from argus.domain.supabase_gateway import SupabaseGateway


def _completed_run() -> BacktestRun:
    return BacktestRun(
        id="run-1",
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.3}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "Apple buy and hold",
            "status_label": "Simulacion completa",
            "rows": [{"label": "Retorno total", "value": "+12.3%"}],
            "assumptions": ["Referencia: SPY"],
            "actions": [],
            "date_range": {
                "start": "2025-01-01",
                "end": "2026-06-05",
                "display": "1 ene 2025 - 5 jun 2026",
            },
            "evidence_artifact_id": "evidence-1",
            "decision_note_id": "decision-1",
            "decision_state": "promising",
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )


def _queued_message() -> Message:
    return Message(
        id="message-1",
        conversation_id="conversation-1",
        role="assistant",
        content="Tu prueba esta en cola.",
        metadata={
            "backtest_job_id": "job-1",
            "backtest_job": {
                "id": "job-1",
                "conversation_id": "conversation-1",
                "status": "queued",
            },
        },
        created_at=utcnow(),
    )


def _loader(value: Any) -> tuple[Callable[[str], Any], list[str]]:
    calls: list[str] = []

    def load(identifier: str) -> Any:
        calls.append(identifier)
        return value

    return load, calls


class _ProjectionBatchClient:
    def __init__(self, rows_by_table: dict[str, list[dict[str, Any]]]) -> None:
        self.rows_by_table = rows_by_table
        self.queries: list[_ProjectionBatchQuery] = []

    def table(self, table_name: str) -> _ProjectionBatchQuery:
        query = _ProjectionBatchQuery(self, table_name)
        self.queries.append(query)
        return query

    def executed_queries(self, table_name: str) -> list[_ProjectionBatchQuery]:
        return [
            query
            for query in self.queries
            if query.table_name == table_name and query.executed
        ]


class _ProjectionBatchQuery:
    def __init__(self, client: _ProjectionBatchClient, table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.equal_filters: list[tuple[str, object]] = []
        self.in_filters: list[tuple[str, tuple[object, ...]]] = []
        self.limit_count: int | None = None
        self.executed = False

    def select(self, *_args: object) -> _ProjectionBatchQuery:
        return self

    def eq(self, key: str, value: object) -> _ProjectionBatchQuery:
        self.equal_filters.append((key, value))
        return self

    def in_(self, key: str, values: list[object]) -> _ProjectionBatchQuery:
        self.in_filters.append((key, tuple(values)))
        return self

    def or_(self, *_args: object) -> _ProjectionBatchQuery:
        return self

    def order(self, *_args: object, **_kwargs: object) -> _ProjectionBatchQuery:
        return self

    def limit(self, count: int) -> _ProjectionBatchQuery:
        self.limit_count = count
        return self

    def execute(self) -> SimpleNamespace:
        self.executed = True
        rows = [
            row
            for row in self.client.rows_by_table[self.table_name]
            if all(row.get(key) == value for key, value in self.equal_filters)
            and all(
                row.get(key) in values for key, values in self.in_filters
            )
        ]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return SimpleNamespace(data=rows)


def _projection_gateway_fixture(
    candidate_count: int,
) -> tuple[SupabaseGateway, _ProjectionBatchClient]:
    messages: list[dict[str, Any]] = []
    jobs: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    for index in range(candidate_count):
        job_id = f"job-{index}"
        run_id = f"run-{index}"
        messages.append(
            _queued_message()
            .model_copy(
                update={
                    "id": f"message-{index}",
                    "metadata": {
                        "backtest_job_id": job_id,
                        "backtest_job": {
                            "id": job_id,
                            "conversation_id": "conversation-1",
                            "status": "queued",
                        },
                    },
                }
            )
            .model_dump(mode="json")
            | {"user_id": "user-1"}
        )
        jobs.append(
            {
                "id": job_id,
                "user_id": "user-1",
                "conversation_id": "conversation-1",
                "status": "succeeded",
                "result_run_id": run_id,
                "execution_metadata": {
                    "workflow_backtest": {
                        "result_readout": f"Completed readout {index}"
                    }
                },
            }
        )
        runs.append(
            _completed_run()
            .model_copy(
                update={
                    "id": run_id,
                    "conversation_result_card": {
                        **_completed_run().conversation_result_card,
                        "evidence_artifact_id": f"evidence-{index}",
                        "decision_note_id": f"decision-{index}",
                    },
                }
            )
            .model_dump(mode="json")
            | {"user_id": "user-1"}
        )
    client = _ProjectionBatchClient(
        {
            "messages": messages,
            "backtest_jobs": jobs,
            "backtest_runs": runs,
        }
    )
    return SupabaseGateway(client=client), client  # type: ignore[arg-type]


def test_completed_job_and_run_query_count_does_not_grow_with_message_count() -> None:
    observed_counts: list[tuple[int, int]] = []
    observed_clients: list[tuple[int, _ProjectionBatchClient]] = []

    for candidate_count in (1, 6):
        gateway, client = _projection_gateway_fixture(candidate_count)

        messages = gateway.list_messages(
            user_id="user-1",
            conversation_id="conversation-1",
            limit=10,
            page=True,
        )

        observed_counts.append(
            (
                len(client.executed_queries("backtest_jobs")),
                len(client.executed_queries("backtest_runs")),
            )
        )
        assert {
            message.metadata["result_run_id"] for message in messages
        } == {f"run-{index}" for index in range(candidate_count)}
        observed_clients.append((candidate_count, client))

    assert observed_counts == [(1, 1), (1, 1)]
    for candidate_count, client in observed_clients:
        job_queries = client.executed_queries("backtest_jobs")
        run_queries = client.executed_queries("backtest_runs")
        assert job_queries[0].equal_filters[:2] == [
            ("user_id", "user-1"),
            ("conversation_id", "conversation-1"),
        ]
        assert run_queries[0].equal_filters[:2] == [
            ("user_id", "user-1"),
            ("conversation_id", "conversation-1"),
        ]
        assert job_queries[0].in_filters == [
            ("id", tuple(f"job-{index}" for index in range(candidate_count)))
        ]
        assert run_queries[0].in_filters == [
            ("id", tuple(f"run-{index}" for index in range(candidate_count)))
        ]


def test_run_batch_ids_include_only_eligible_succeeded_jobs() -> None:
    running_message = _queued_message().model_copy(
        update={
            "id": "message-running",
            "metadata": {
                "backtest_job_id": "job-running",
                "backtest_job": {
                    "id": "job-running",
                    "conversation_id": "conversation-1",
                    "status": "queued",
                },
            },
        }
    )

    run_ids = completed_backtest_run_ids(
        [_queued_message(), running_message],
        jobs_by_id={
            "job-1": {
                "id": "job-1",
                "conversation_id": "conversation-1",
                "status": "succeeded",
                "result_run_id": "run-1",
            },
            "job-running": {
                "id": "job-running",
                "conversation_id": "conversation-1",
                "status": "running",
                "result_run_id": "run-running",
            },
        },
    )

    assert run_ids == ["run-1"]


def test_completed_workflow_job_projects_canonical_result_for_reload() -> None:
    job = {
        "id": "job-1",
        "conversation_id": "conversation-1",
        "status": "succeeded",
        "result_run_id": "run-1",
        "finished_at": "2026-07-13T02:00:00+00:00",
        "launch_payload": {"must_not": "leak"},
        "execution_metadata": {
            "workflow_backtest": {
                "result_readout": "**Lectura rapida**\n\nApple rindio 12.3%.",
                "result_readout_source": "llm_explain_stage",
            }
        },
    }
    decision_persisted_message = _queued_message().model_copy(
        update={
            "id": "message-2",
            "metadata": {
                **(_queued_message().metadata or {}),
                "result_card": {
                    "evidence_artifact_id": "evidence-1",
                    "decision_note_id": "decision-1",
                    "decision_state": "promising",
                },
            },
        }
    )
    projected = hydrate_completed_backtest_job_messages(
        [_queued_message(), decision_persisted_message],
        jobs_by_id={"job-1": job},
        runs_by_id={"run-1": _completed_run()},
    )

    assert all(item.content.startswith("**Lectura rapida**") for item in projected)
    for item in projected:
        metadata = item.metadata or {}
        assert metadata["result_card"]["evidence_artifact_id"] == "evidence-1"
        assert metadata["result_card"]["decision_note_id"] == "decision-1"
        assert metadata["result_card"]["decision_state"] == "promising"
        assert metadata["result_run_id"] == "run-1"
        assert metadata["latest_run_id"] == "run-1"
        assert metadata["result_conversation_id"] == "conversation-1"
        assert metadata["result_fact_bank"]["run_id"] == "run-1"
        assert metadata["backtest_job"]["status"] == "succeeded"
        assert "launch_payload" not in metadata["backtest_job"]
        assert "execution_metadata" not in metadata["backtest_job"]


def test_incomplete_workflow_job_leaves_queued_message_unchanged() -> None:
    message = _queued_message()
    jobs_by_id = {
        "job-1": {
            "id": "job-1",
            "conversation_id": "conversation-1",
            "status": "running",
            "result_run_id": None,
        }
    }

    projected = hydrate_completed_backtest_job_messages(
        [message],
        jobs_by_id=jobs_by_id,
        runs_by_id={"run-1": _completed_run()},
    )

    assert projected == [message]


def test_invalid_completed_records_never_project() -> None:
    valid_job = {
        "id": "job-1",
        "conversation_id": "conversation-1",
        "status": "succeeded",
        "result_run_id": "run-1",
    }
    cases: list[
        tuple[str, dict[str, dict[str, Any]], dict[str, BacktestRun]]
    ] = [
        ("missing-job", {}, {}),
        (
            "foreign-job-conversation",
            {
                "job-1": {
                    "id": "job-1",
                    "conversation_id": "conversation-2",
                    "status": "succeeded",
                    "result_run_id": "run-1",
                }
            },
            {"run-1": _completed_run()},
        ),
        ("missing-run", {"job-1": valid_job}, {}),
        (
            "mismatched-run-id",
            {"job-1": valid_job},
            {"run-1": _completed_run().model_copy(update={"id": "run-other"})},
        ),
        (
            "foreign-run-conversation",
            {"job-1": valid_job},
            {
                "run-1": _completed_run().model_copy(
                    update={"conversation_id": "conversation-2"}
                )
            },
        ),
    ]
    message = _queued_message()

    for label, jobs_by_id, runs_by_id in cases:
        projected = hydrate_completed_backtest_job_messages(
            [message],
            jobs_by_id=jobs_by_id,
            runs_by_id=runs_by_id,
        )

        assert projected == [message], label


def test_completed_workflow_job_without_readout_clears_stale_queued_copy() -> None:
    jobs_by_id = {
        "job-1": {
            "id": "job-1",
            "conversation_id": "conversation-1",
            "status": "succeeded",
            "result_run_id": "run-1",
            "execution_metadata": {"workflow_backtest": {}},
        }
    }

    [projected] = hydrate_completed_backtest_job_messages(
        [_queued_message()],
        jobs_by_id=jobs_by_id,
        runs_by_id={"run-1": _completed_run()},
    )

    assert projected.content == ""
    assert projected.metadata["result_run_id"] == "run-1"


def test_missing_assistant_job_message_projects_owner_scoped_action_job() -> None:
    request = Message(
        id="request-message-1",
        conversation_id="conversation-1",
        role="user",
        content="Run backtest",
        metadata={
            "chat_action": {
                "type": "run_backtest",
                "payload": {"confirmation_id": "confirmation-1"},
            }
        },
        created_at=utcnow(),
    )
    job = {
        "id": "job-hard-loss",
        "conversation_id": "conversation-1",
        "request_message_id": "request-message-1",
        "confirmation_message_id": "confirmation-message-1",
        "status": "failed",
        "failure_code": "workflow_dispatch_missing",
        "failure_detail": "Backtest workflow did not record a task run.",
        "retryable": True,
        "launch_payload": {"must_not": "leak"},
        "execution_metadata": {"must_not": "leak"},
    }
    load_job, calls = _loader(job)

    [projected] = hydrate_backtest_job_action_messages(
        [request],
        load_job_by_action=load_job,
    )

    assert calls == ["confirmation-1"]
    assert projected.id == request.id
    assert projected.role == "user"
    assert projected.metadata["backtest_job_id"] == "job-hard-loss"
    assert projected.metadata["backtest_job"]["status"] == "failed"
    assert projected.metadata["backtest_job"]["retryable"] is True
    assert "launch_payload" not in projected.metadata["backtest_job"]
    assert "execution_metadata" not in projected.metadata["backtest_job"]
