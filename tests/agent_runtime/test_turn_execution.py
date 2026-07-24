from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class _Schema(BaseModel):
    accepted: bool


def _typed_state() -> dict[str, Any]:
    return {
        "response_intent": {
            "kind": "clarification",
            "requested_fields": ["date_range"],
            "semantic_needs": ["period"],
        },
        "pending_strategy": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
            },
            "requested_field": "date_range",
        },
    }


def test_primary_and_fallback_share_one_call_allowance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.turn_execution import (
        reserve_provider_call,
        turn_budget_block_reason,
        turn_execution_scope,
    )

    monkeypatch.setenv("ARGUS_TURN_CALL_ALLOWANCE", "1")

    with turn_execution_scope(entry_state=_typed_state()) as execution:
        primary = reserve_provider_call(
            "interpretation",
            task_timeout_seconds=20,
        )
        fallback = reserve_provider_call(
            "interpretation",
            task_timeout_seconds=20,
        )

        assert primary is not None
        assert primary.timeout_seconds == 20
        assert fallback is None
        assert execution.calls_reserved == 1
        assert execution.blocked_tasks == ["interpretation"]
        assert turn_budget_block_reason() == "turn_call_allowance_exhausted"


@pytest.mark.asyncio
async def test_exhausted_reservation_records_skipped_receipt_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.turn_execution import (
        reserve_provider_call,
        turn_execution_scope,
    )
    from argus.llm import openrouter

    monkeypatch.setenv("ARGUS_TURN_CALL_ALLOWANCE", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "primary/model")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "fallback/model")
    clients_created = 0

    class _ForbiddenAsyncClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            nonlocal clients_created
            clients_created += 1
            raise AssertionError("provider client must not be created")

    monkeypatch.setattr(openrouter.httpx, "AsyncClient", _ForbiddenAsyncClient)

    with turn_execution_scope(entry_state=_typed_state()):
        assert (
            reserve_provider_call(
                "interpretation",
                task_timeout_seconds=20,
            )
            is not None
        )
        receipt_token = openrouter.begin_openrouter_route_receipt_capture()
        try:
            result = await openrouter.invoke_openrouter_json_schema(
                task="interpretation",
                messages=[{"role": "user", "content": "test"}],
                schema_model=_Schema,
                schema_name="_Schema",
            )
        finally:
            receipts = openrouter.end_openrouter_route_receipt_capture(receipt_token)

    assert result is None
    assert clients_created == 0
    assert len(receipts) == 1
    assert receipts[0].outcome == "skipped"
    assert receipts[0].failure_mode == "turn_call_allowance_exhausted"
    assert receipts[0].model == "primary/model"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("missing_key", "missing_model", "expected_reason"),
    [
        (True, False, "missing_api_key"),
        (False, True, "missing_model"),
    ],
)
async def test_missing_provider_configuration_does_not_reserve_call(
    monkeypatch: pytest.MonkeyPatch,
    missing_key: bool,
    missing_model: bool,
    expected_reason: str,
) -> None:
    from argus.agent_runtime.turn_execution import turn_execution_scope
    from argus.llm import openrouter

    if missing_key:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    else:
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    if missing_model:
        monkeypatch.delenv("ARGUS_STRUCTURED_MODEL", raising=False)
        monkeypatch.delenv("ARGUS_STRUCTURED_FALLBACK_MODEL", raising=False)
    else:
        monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "primary/model")

    with turn_execution_scope(entry_state=_typed_state()) as execution:
        receipt_token = openrouter.begin_openrouter_route_receipt_capture()
        try:
            result = await openrouter.invoke_openrouter_json_schema(
                task="interpretation",
                messages=[{"role": "user", "content": "test"}],
                schema_model=_Schema,
                schema_name="_Schema",
            )
        finally:
            receipts = openrouter.end_openrouter_route_receipt_capture(receipt_token)

        assert execution.calls_reserved == 0

    assert result is None
    assert len(receipts) == 1
    assert receipts[0].failure_mode == expected_reason


def test_first_terminal_claim_wins() -> None:
    from argus.agent_runtime.turn_execution import (
        claim_turn_terminal,
        turn_execution_scope,
    )

    with turn_execution_scope(entry_state=_typed_state()) as execution:
        assert claim_turn_terminal("advanced", "normal_final") is True
        assert claim_turn_terminal("recoverable_failed", "late_failure") is False
        assert execution.terminal == "advanced"
        assert execution.terminal_reason == "normal_final"


def test_same_typed_state_becomes_no_progress() -> None:
    from argus.agent_runtime.turn_execution import (
        record_exit_progress,
        turn_execution_scope,
        turn_execution_summary,
    )

    state = _typed_state()
    with turn_execution_scope(entry_state=state) as execution:
        assessment = record_exit_progress(state, terminal=None)
        summary = turn_execution_summary(())

        assert assessment.outcome == "no_progress"
        assert assessment.changed_fields == ()
        assert execution.progress_outcome == "no_progress"
        assert execution.terminal == "no_progress"
        assert summary["input_fingerprint"] == summary["output_fingerprint"]
        assert summary["progress_outcome"] == "no_progress"
        assert "entry_state" not in summary
        assert "exit_state" not in summary


@pytest.mark.asyncio
async def test_background_title_work_has_no_parent_turn_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.turn_execution import (
        active_turn_execution,
        turn_execution_scope,
    )
    from argus.api.chat import title_finalization

    observed_contexts: list[object | None] = []
    completed = asyncio.Event()

    async def _fake_to_thread(_function: Any, **_kwargs: Any) -> None:
        observed_contexts.append(active_turn_execution())
        completed.set()

    monkeypatch.setattr(
        title_finalization,
        "_artifact_naming_disabled_for_pytest",
        lambda: False,
    )
    monkeypatch.setattr(title_finalization.asyncio, "to_thread", _fake_to_thread)

    with turn_execution_scope(entry_state=_typed_state()):
        title_finalization.schedule_artifact_naming_after_stream(
            user_id="user-1",
            conversation_id="conversation-1",
            language="en",
        )
        await asyncio.wait_for(completed.wait(), timeout=1)

    assert observed_contexts == [None]


def test_provider_permit_uses_remaining_absolute_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import turn_execution

    clock = _Clock()
    monkeypatch.setattr(turn_execution, "_monotonic", clock)
    monkeypatch.setenv("ARGUS_TURN_DEADLINE_SECONDS", "0.25")

    with turn_execution.turn_execution_scope(entry_state=_typed_state()):
        clock.advance(0.1)
        permit = turn_execution.reserve_provider_call(
            "interpretation",
            task_timeout_seconds=20,
        )

    assert permit is not None
    assert permit.timeout_seconds == pytest.approx(0.15)
