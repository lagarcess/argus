from __future__ import annotations

from collections.abc import Callable
from typing import Any

from argus.api.schemas import BacktestRun, Message
from argus.domain.backtest_message_projection import (
    hydrate_completed_backtest_job_messages,
)
from argus.domain.store import utcnow


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
    load_job, job_calls = _loader(job)
    load_run, run_calls = _loader(_completed_run())

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
        load_job=load_job,
        load_run=load_run,
    )

    assert job_calls == ["job-1"]
    assert run_calls == ["run-1"]
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
    load_job, _ = _loader(
        {
            "id": "job-1",
            "conversation_id": "conversation-1",
            "status": "running",
            "result_run_id": None,
        }
    )
    load_run, run_calls = _loader(_completed_run())

    projected = hydrate_completed_backtest_job_messages(
        [message],
        load_job=load_job,
        load_run=load_run,
    )

    assert projected == [message]
    assert run_calls == []


def test_completed_workflow_job_without_readout_clears_stale_queued_copy() -> None:
    load_job, _ = _loader(
        {
            "id": "job-1",
            "conversation_id": "conversation-1",
            "status": "succeeded",
            "result_run_id": "run-1",
            "execution_metadata": {"workflow_backtest": {}},
        }
    )
    load_run, _ = _loader(_completed_run())

    [projected] = hydrate_completed_backtest_job_messages(
        [_queued_message()],
        load_job=load_job,
        load_run=load_run,
    )

    assert projected.content == ""
    assert projected.metadata["result_run_id"] == "run-1"
