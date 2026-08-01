from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.guest_access import guest_account_context, store_account_context
from argus.api.memory_run_dossiers import list_memory_run_dossier_source_rows
from argus.api.routers.conversations import list_run_dossiers
from argus.api.schemas import Conversation, Message, User
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.postgres_run_dossier_reader import (
    RunDossierCursorError,
    RunDossierSourcePage,
    RunDossierSourceRow,
)
from argus.domain.store import AlphaStore
from fastapi import HTTPException
from starlette.requests import Request


def _run(*, run_id: str, created_at: datetime) -> dict[str, Any]:
    return {
        "id": run_id,
        "conversation_id": "conversation-1",
        "status": "completed",
        "asset_class": "equity",
        "symbols": ["TSLA"],
        "benchmark_symbol": "SPY",
        "config_snapshot": {
            "template": "buy_and_hold",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "timeframe": "1D",
            "starting_capital": 10_000,
            "resolved_strategy": {
                "strategy_type": "buy_and_hold",
                "asset_class": "equity",
            },
            "resolved_parameters": {
                "timeframe": "1D",
                "benchmark_symbol": "SPY",
                "sizing_mode": "capital_amount",
                "capital_amount": 10_000,
            },
        },
        "conversation_result_card": {"title": "TSLA buy and hold"},
        "created_at": created_at,
    }


def _artifact(*, run_id: str, created_at: datetime) -> dict[str, Any]:
    return {
        "id": f"artifact-{run_id}",
        "source_conversation_id": "conversation-1",
        "source_run_id": run_id,
        "title": "TSLA evidence",
        "digest": "TSLA returned 12.5%.",
        "payload": {
            "quick_take": "TSLA returned 12.5%.",
            "benchmark_symbol": "SPY",
            "metrics": {
                "aggregate": {
                    "performance": {
                        "total_return_pct": 12.5,
                        "benchmark_return_pct": 8.0,
                        "delta_vs_benchmark_pct": 4.5,
                        "max_drawdown_pct": -6.0,
                        "ignored_fifth_metric": 99,
                    }
                }
            },
        },
        "created_at": created_at,
        "updated_at": created_at,
    }


class _UncopiedRecord:
    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)

    def model_dump(self, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("unselected history payload must not be copied")


def test_project_run_dossier_keeps_every_fact_and_action_on_one_run() -> None:
    run_dossiers = import_module("argus.domain.run_dossiers")
    created_at = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    run = _run(run_id="run-1", created_at=created_at)
    artifact = _artifact(run_id="run-1", created_at=created_at)

    dossier = run_dossiers.project_run_dossier(
        run=run,
        artifact=artifact,
        decision={
            "evidence_artifact_id": artifact["id"],
            "decision_state": "watching",
            "note": "Keep this line.\n  Preserve this indentation.",
            "created_at": created_at,
            "updated_at": created_at,
        },
        result_message_id="message-1",
        allow_decision_action=True,
        language="en",
    )

    assert dossier.run_id == "run-1"
    assert dossier.result_message_id == "message-1"
    assert dossier.tested.symbols == ["TSLA"]
    assert dossier.tested.strategy_family == "buy_and_hold"
    assert dossier.tested.timeframe == "1D"
    assert dossier.decision is not None
    assert dossier.decision.note == "Keep this line.\n  Preserve this indentation."
    assert len(dossier.outcome.metrics) == 4
    assert dossier.actions[0].type == "retest_run"
    assert dossier.actions[0].source_run_id == dossier.run_id
    # The typed envelope carries identity and policy only; the executable
    # setup is reloaded server-side from the owner-scoped source run.
    assert dossier.actions[0].window_policy == "same_duration_ending_today"
    assert dossier.actions[0].contract_version == "argus_retest_run/v1"
    assert not hasattr(dossier.actions[0], "canonical_setup")
    assert not hasattr(dossier.actions[0], "send_text")
    assert dossier.actions[1].type == "decision"
    assert dossier.actions[1].evidence_artifact_id == artifact["id"]


def test_eligible_runs_exclude_incomplete_failed_and_evidence_less_rows() -> None:
    run_dossiers = import_module("argus.domain.run_dossiers")
    created_at = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    eligible = _run(run_id="eligible", created_at=created_at)
    failed = {**_run(run_id="failed", created_at=created_at), "status": "failed"}
    running = {**_run(run_id="running", created_at=created_at), "status": "running"}
    evidence_less = _run(run_id="evidence-less", created_at=created_at)

    rows = run_dossiers.newest_evidence_backed_completed_runs(
        runs=[eligible, failed, running, evidence_less],
        evidence=[_artifact(run_id="eligible", created_at=created_at)],
    )

    assert [(run["id"], artifact["source_run_id"]) for run, artifact in rows] == [
        ("eligible", "eligible")
    ]


def test_result_message_id_prefers_actual_result_card_over_later_pointer() -> None:
    run_dossiers = import_module("argus.domain.run_dossiers")
    created_at = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    run = _run(run_id="run-1", created_at=created_at)

    result = run_dossiers.result_message_id_for(
        run,
        [
            {
                "id": "older",
                "role": "assistant",
                "metadata": {
                    "result_run_id": "run-1",
                    "result_card": {"title": "Run result"},
                },
                "created_at": created_at,
            },
            {
                "id": "newer",
                "role": "assistant",
                "metadata": {"latest_run_id": "run-1"},
                "created_at": created_at.replace(hour=13),
            },
            {
                "id": "user-pointer",
                "role": "user",
                "metadata": {"result_run_id": "run-1"},
                "created_at": created_at.replace(hour=14),
            },
        ],
    )

    assert result == "older"


def test_result_message_id_uses_latest_pointer_as_legacy_fallback() -> None:
    run_dossiers = import_module("argus.domain.run_dossiers")
    created_at = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)

    result = run_dossiers.result_message_id_for(
        _run(run_id="run-1", created_at=created_at),
        [
            {
                "id": "older",
                "role": "assistant",
                "metadata": {"result_run_id": "run-1"},
                "created_at": created_at,
            },
            {
                "id": "newer",
                "role": "assistant",
                "metadata": {"latest_run_id": "run-1"},
                "created_at": created_at.replace(hour=13),
            },
        ],
    )

    assert result == "newer"


def test_memory_history_prefers_result_card_over_later_pointer() -> None:
    store = AlphaStore()
    owner_id = "owner-1"
    conversation_id = "conversation-1"
    created_at = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    run = _run(run_id="run-1", created_at=created_at)
    artifact = _artifact(run_id="run-1", created_at=created_at)
    store.backtest_runs[run["id"]] = run
    store.backtest_run_owners[run["id"]] = owner_id
    store.evidence_artifacts[artifact["id"]] = artifact
    store.evidence_artifact_owners[artifact["id"]] = owner_id
    store.messages[conversation_id] = [
        Message(
            id="result-card-message",
            conversation_id=conversation_id,
            role="assistant",
            content="Run result",
            created_at=created_at,
            metadata={
                "result_run_id": run["id"],
                "result_card": {"title": "TSLA buy and hold"},
            },
        ),
        Message(
            id="later-pointer-message",
            conversation_id=conversation_id,
            role="assistant",
            content="Follow-up explanation",
            created_at=created_at + timedelta(minutes=1),
            metadata={"latest_run_id": run["id"]},
        ),
    ]

    page = list_memory_run_dossier_source_rows(
        store=store,
        user_id=owner_id,
        conversation_id=conversation_id,
        limit=20,
        cursor_completed_at=None,
        cursor_run_id=None,
    )

    assert page.rows[0].result_message_id == "result-card-message"


def test_memory_history_is_newest_first_bounded_and_counts_only_eligible_rows() -> None:
    store = AlphaStore()
    owner_id = "owner-1"
    conversation_id = "conversation-1"
    newest_first_ids = [f"run-{index}" for index in range(7, 0, -1)]
    for index in range(1, 8):
        created_at = datetime(2026, 7, index, 12, tzinfo=timezone.utc)
        run_id = f"run-{index}"
        store.backtest_runs[run_id] = _run(run_id=run_id, created_at=created_at)
        store.backtest_run_owners[run_id] = owner_id
        artifact = _artifact(run_id=run_id, created_at=created_at)
        store.evidence_artifacts[artifact["id"]] = artifact
        store.evidence_artifact_owners[artifact["id"]] = owner_id
        if index <= 5:
            decision_id = f"decision-{index}"
            store.decision_notes[decision_id] = {
                "id": decision_id,
                "evidence_artifact_id": artifact["id"],
                "source_conversation_id": conversation_id,
                "decision_state": "watching",
                "note": f"Decision {index}",
                "created_at": created_at,
                "updated_at": created_at,
            }
            store.decision_note_owners[decision_id] = owner_id

    for run_id, status in (
        ("failed", "failed"),
        ("running", "running"),
        ("evidence-less", "completed"),
    ):
        created_at = datetime(2026, 7, 20, 12, tzinfo=timezone.utc)
        store.backtest_runs[run_id] = {
            **_run(run_id=run_id, created_at=created_at),
            "status": status,
        }
        store.backtest_run_owners[run_id] = owner_id
    store.messages[conversation_id] = [
        Message(
            id="latest-result",
            conversation_id=conversation_id,
            role="assistant",
            content="Latest result",
            created_at=datetime(2026, 7, 7, 13, tzinfo=timezone.utc),
            metadata={"result_run_id": "run-7"},
        )
    ]

    first = list_memory_run_dossier_source_rows(
        store=store,
        user_id=owner_id,
        conversation_id=conversation_id,
        limit=4,
        cursor_completed_at=None,
        cursor_run_id=None,
    )

    assert [row.run["id"] for row in first.rows] == newest_first_ids[:4]
    assert first.total_runs == 7
    assert first.decided_runs == 5
    assert first.rows[0].result_message_id == "latest-result"

    pivot = first.rows[-1].run
    second = list_memory_run_dossier_source_rows(
        store=store,
        user_id=owner_id,
        conversation_id=conversation_id,
        limit=4,
        cursor_completed_at=pivot["created_at"],
        cursor_run_id=pivot["id"],
    )
    assert [row.run["id"] for row in second.rows] == newest_first_ids[4:]
    assert not {
        row.run["id"] for row in first.rows
    }.intersection(row.run["id"] for row in second.rows)
    assert second.total_runs == 7
    assert second.decided_runs == 5


def test_memory_history_copies_only_selected_page_payload_rows() -> None:
    store = AlphaStore()
    owner_id = "owner-1"
    conversation_id = "conversation-1"
    selected_at = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    unselected_at = datetime(2026, 7, 30, 12, tzinfo=timezone.utc)

    selected_run = _run(run_id="selected-run", created_at=selected_at)
    selected_artifact = _artifact(
        run_id="selected-run",
        created_at=selected_at,
    )
    store.backtest_runs["selected-run"] = selected_run
    store.backtest_run_owners["selected-run"] = owner_id
    store.evidence_artifacts[selected_artifact["id"]] = selected_artifact
    store.evidence_artifact_owners[selected_artifact["id"]] = owner_id

    store.backtest_runs["unselected-run"] = _UncopiedRecord(
        id="unselected-run",
        conversation_id=conversation_id,
        status="completed",
        created_at=unselected_at,
    )
    store.backtest_run_owners["unselected-run"] = owner_id
    store.evidence_artifacts["unselected-artifact"] = _UncopiedRecord(
        id="unselected-artifact",
        source_conversation_id=conversation_id,
        source_run_id="unselected-run",
        created_at=unselected_at,
        updated_at=unselected_at,
    )
    store.evidence_artifact_owners["unselected-artifact"] = owner_id
    store.decision_notes["unselected-decision"] = _UncopiedRecord(
        id="unselected-decision",
        evidence_artifact_id="unselected-artifact",
        source_conversation_id=conversation_id,
        decision_state="watching",
        created_at=unselected_at,
        updated_at=unselected_at,
    )
    store.decision_note_owners["unselected-decision"] = owner_id
    store.messages[conversation_id] = [
        Message(
            id="selected-message",
            conversation_id=conversation_id,
            role="assistant",
            content="Selected result",
            created_at=selected_at,
            metadata={"result_run_id": "selected-run"},
        ),
        _UncopiedRecord(
            id="unselected-message",
            conversation_id=conversation_id,
            role="assistant",
            created_at=unselected_at,
            metadata={"result_run_id": "unselected-run"},
        ),
    ]

    page = list_memory_run_dossier_source_rows(
        store=store,
        user_id=owner_id,
        conversation_id=conversation_id,
        limit=1,
        cursor_completed_at=None,
        cursor_run_id=None,
    )

    assert [row.run["id"] for row in page.rows] == ["selected-run"]
    assert page.rows[0].result_message_id == "selected-message"
    assert page.total_runs == 2
    assert page.decided_runs == 1


def test_memory_history_rejects_stale_or_foreign_cursor_pivots() -> None:
    store = AlphaStore()
    with pytest.raises(RunDossierCursorError):
        list_memory_run_dossier_source_rows(
            store=store,
            user_id="owner-1",
            conversation_id="conversation-1",
            limit=20,
            cursor_completed_at=datetime(2026, 7, 31, tzinfo=timezone.utc),
            cursor_run_id="foreign-run",
        )


def test_guest_history_is_limited_to_the_active_workspace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 7, 31, 12, tzinfo=timezone.utc)
    user = User(
        id="guest-1",
        email=None,
        created_at=now,
        updated_at=now,
    )
    conversation = Conversation(
        id="conversation-1",
        title="Guest workspace",
        created_at=now,
        updated_at=now,
    )
    workspace = GuestWorkspace(
        user_id=user.id,
        conversation_id=conversation.id,
        status="active",
        created_at=now,
        expires_at=now + timedelta(days=7),
        claimed_by=None,
        claimed_at=None,
        updated_at=now,
    )
    source_row = RunDossierSourceRow(
        run=_run(run_id="run-1", created_at=now),
        artifact=_artifact(run_id="run-1", created_at=now),
        decision=None,
        result_message_id=None,
    )

    class _Gateway:
        def get_conversation(
            self,
            *,
            user_id: str,
            conversation_id: str,
        ) -> Conversation | None:
            if user_id != user.id:
                return None
            if conversation_id == conversation.id:
                return conversation
            if conversation_id == "another-conversation":
                return conversation.model_copy(update={"id": conversation_id})
            return None

        def get_active_guest_workspace(
            self,
            *,
            user_id: str,
            at: datetime,
        ) -> GuestWorkspace | None:
            assert at.tzinfo is not None
            return workspace if user_id == user.id else None

        def list_run_dossier_source_rows(self, **_kwargs: Any) -> RunDossierSourcePage:
            return RunDossierSourcePage(
                rows=(source_row,),
                total_runs=1,
                decided_runs=0,
            )

    monkeypatch.setattr(api_state, "supabase_gateway", _Gateway())
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    request.state.request_id = "run-dossier-guest-test"
    store_account_context(request, guest_account_context(workspace))

    page = list_run_dossiers(
        conversation_id=conversation.id,
        request=request,
        limit=20,
        cursor=None,
        user=user,
    )
    assert page.total_runs == 1
    assert [action.type for action in page.items[0].actions] == ["retest_run"]

    with pytest.raises(HTTPException) as hidden:
        list_run_dossiers(
            conversation_id="another-conversation",
            request=request,
            limit=20,
            cursor=None,
            user=user,
        )
    assert hidden.value.status_code == 404
