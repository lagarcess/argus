"""#239 correction reds — four confirmed blockers against the first cut.

1. The deadline must be turn-wide: per-event stall resets cannot extend it.
2. The fingerprint must be canonical across the real checkpoint and public
   payload representations, and typed-only (no structured-action prose).
3. Every persisted accepted path claims exactly one internal typed terminal.
4. After-stream artifact naming runs outside the completed turn's budget.
"""

from __future__ import annotations

import asyncio

import pytest
from argus.agent_runtime import turn_execution


def teardown_function(function) -> None:
    turn_execution.set_monotonic_for_testing(None)


# ── Blocker 1: the deadline is not turn-wide ─────────────────────────────────


@pytest.mark.asyncio
async def test_cumulative_events_hit_the_absolute_turn_deadline() -> None:
    """Events each arrive inside the per-event stall limit, but their sum
    passes the turn deadline — the runtime must cancel at the absolute wall."""

    from argus.api.chat import runtime_events as runtime_events_module

    token = turn_execution.begin_turn_execution(deadline_seconds=0.25)
    received = 0
    try:

        async def steady_events():
            while True:
                await asyncio.sleep(0.03)
                yield {"type": "token", "content": "still working"}

        wrapped = runtime_events_module._runtime_events_with_keepalive(steady_events())
        with pytest.raises(asyncio.TimeoutError) as excinfo:
            async for event in wrapped:
                if event is None:
                    continue
                received += 1
                if received >= 40:
                    pytest.fail(
                        "per-event resets let the turn run far past its "
                        "absolute deadline"
                    )
        diagnostics = getattr(excinfo.value, "diagnostics", None) or {}
        assert diagnostics.get("code") == "turn_deadline_exhausted"
        context = turn_execution.active_turn_execution()
        assert context is not None
        assert context.deadline_exhausted is True
    finally:
        turn_execution.reset_turn_execution(token)


@pytest.mark.asyncio
async def test_per_event_stall_guard_still_fires_inside_a_roomy_turn(
    monkeypatch,
) -> None:
    """The absolute turn wall must not weaken the existing per-event guard."""

    from argus.api.chat import runtime_events as runtime_events_module

    monkeypatch.setattr(runtime_events_module, "RUNTIME_EVENT_TIMEOUT_SECONDS", 0.2)
    token = turn_execution.begin_turn_execution(deadline_seconds=120.0)
    try:

        async def stalled_events():
            yield {"type": "stage_start", "stage": "interpret"}
            await asyncio.sleep(5)
            yield {"type": "final", "payload": {}}

        wrapped = runtime_events_module._runtime_events_with_keepalive(stalled_events())
        first = await anext(wrapped)
        assert first == {"type": "stage_start", "stage": "interpret"}
        with pytest.raises(asyncio.TimeoutError) as excinfo:
            async for event in wrapped:
                if event is None:
                    continue
        diagnostics = getattr(excinfo.value, "diagnostics", None) or {}
        assert diagnostics.get("code") == "agent_runtime_event_timeout"
    finally:
        turn_execution.reset_turn_execution(token)


def _route_client():
    from argus.api.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.post("/api/v1/dev/reset")
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "ready",
                "language_confirmed": True,
                "primary_goal": "test_stock_idea",
                "completed": False,
            }
        },
    )
    return client


def _conversation(client) -> dict:
    return client.post("/api/v1/conversations", json={"language": "en"}).json()[
        "conversation"
    ]


def _deadline_exhaustion_route_case(monkeypatch, *, worker_mode: str) -> dict:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    monkeypatch.setenv("ARGUS_RUNTIME_STREAM_WORKER", worker_mode)
    monkeypatch.setenv("ARGUS_TURN_DEADLINE_SECONDS", "0.25")
    monkeypatch.setattr(api_state, "supabase_gateway", None)

    async def _steady_progress_events(**kwargs):
        for _ in range(60):
            await asyncio.sleep(0.03)
            yield {"type": "token", "content": "…"}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "done",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _steady_progress_events)
    persisted: list[dict] = []

    def _capture_receipts(**kwargs):
        persisted.append(dict(kwargs.get("metadata") or {}))

    monkeypatch.setattr(agent_router, "persist_route_receipts", _capture_receipts)

    client = _route_client()
    conversation = _conversation(client)
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200
    assert '"type": "error"' in response.text or '"type":"error"' in response.text
    assert len(persisted) == 1
    summary = persisted[0].get("turn_execution")
    assert isinstance(summary, dict)
    return summary


def test_inline_route_turn_deadline_exhaustion_is_recoverable(monkeypatch) -> None:
    """Inline runtime path: cumulative progress past the turn deadline ends as
    recoverable behavior with the internal turn_deadline_exhausted reason."""

    summary = _deadline_exhaustion_route_case(monkeypatch, worker_mode="off")
    assert summary["terminal"] == "recoverable_failed"
    assert summary["terminal_reason"] == "turn_deadline_exhausted"
    assert summary["deadline_exhausted"] is True


def test_threaded_route_turn_deadline_exhaustion_is_recoverable(monkeypatch) -> None:
    """Threaded runtime-worker path: the same absolute wall applies."""

    summary = _deadline_exhaustion_route_case(monkeypatch, worker_mode="on")
    assert summary["terminal"] == "recoverable_failed"
    assert summary["terminal_reason"] == "turn_deadline_exhausted"
    assert summary["deadline_exhausted"] is True


# ── Blocker 2: one canonical fingerprint across real representations ─────────


def _draft_strategy(**overrides):
    from argus.agent_runtime.state.models import StrategySummary

    fields = {
        "strategy_type": "buy_and_hold",
        "asset_universe": ["AAPL"],
        "asset_class": "equity",
        "timeframe": "1D",
        "strategy_thesis": "Hold Apple because earnings look strong.",
        "raw_user_phrasing": "quiero probar apple",
    }
    fields.update(overrides)
    return StrategySummary(**fields)


def _production_checkpoint(
    *,
    strategy=None,
    user_message: str = "quiero probar apple",
    assistant: str = "¿Qué fechas usamos?",
    action=None,
    artifact_references=None,
):
    from argus.agent_runtime.graph.workflow import WorkflowStageOutcome
    from argus.agent_runtime.state.models import RunState, TaskSnapshot

    strategy = strategy if strategy is not None else _draft_strategy()
    run_state = RunState.new(
        current_user_message=user_message,
        recent_thread_history=[],
        action_context=action,
    )
    run_state.candidate_strategy_draft = strategy
    run_state.requested_field = "date_range"
    run_state.missing_required_fields = ["date_range"]
    checkpoint = {
        "stage_outcome": WorkflowStageOutcome("await_user_reply"),
        "run_state": run_state,
        "latest_task_snapshot": TaskSnapshot(pending_strategy_summary=strategy),
        "assistant_response": assistant,
    }
    if artifact_references is not None:
        checkpoint["artifact_references"] = artifact_references
    return checkpoint


def _public_payload(*, strategy=None, assistant: str = "Which dates should we use?"):
    strategy = strategy if strategy is not None else _draft_strategy()
    return {
        "stage_outcome": "await_user_reply",
        "assistant_response": assistant,
        "pending_strategy": {
            "strategy": strategy.model_dump(mode="python"),
            "requested_field": "date_range",
            "missing_required_fields": ["date_range"],
        },
    }


def test_checkpoint_and_public_payload_share_one_canonical_fingerprint() -> None:
    """The checkpoint carries run_state.candidate_strategy_draft and
    latest_task_snapshot.pending_strategy_summary; the public payload carries
    pending_strategy.strategy. Equivalent semantic state must hash equal."""

    checkpoint_fp = turn_execution.semantic_turn_fingerprint(_production_checkpoint())
    payload_fp = turn_execution.semantic_turn_fingerprint(_public_payload())
    assert checkpoint_fp is not None
    assert checkpoint_fp == payload_fp


def test_structured_action_prose_never_enters_the_fingerprint() -> None:
    """Rewording user/assistant prose and the structured action's message text
    keeps the fingerprint; the typed option identity is what matters."""

    from argus.agent_runtime.state.models import StructuredActionContext

    spanish = _production_checkpoint(
        user_message="sí, usa las fechas por defecto",
        assistant="Perfecto, sigo con eso.",
        action=StructuredActionContext(
            type="select_response_option",
            label="Sí",
            payload={
                "option_id": "opt-1",
                "message": "Sí, usa las fechas por defecto",
            },
        ),
    )
    english = _production_checkpoint(
        user_message="yes, use the default dates",
        assistant="Great, continuing with that.",
        action=StructuredActionContext(
            type="select_response_option",
            label="Yes",
            payload={
                "option_id": "opt-1",
                "message": "Yes, use the default dates",
            },
        ),
    )
    assert turn_execution.semantic_turn_fingerprint(
        spanish
    ) == turn_execution.semantic_turn_fingerprint(english)


def test_typed_state_changes_change_the_fingerprint() -> None:
    from argus.agent_runtime.state.models import (
        ArtifactReference,
        StructuredActionContext,
    )

    base = turn_execution.semantic_turn_fingerprint(_production_checkpoint())

    grown = turn_execution.semantic_turn_fingerprint(
        _production_checkpoint(strategy=_draft_strategy(asset_universe=["AAPL", "MSFT"]))
    )
    assert grown != base

    action_a = turn_execution.semantic_turn_fingerprint(
        _production_checkpoint(
            action=StructuredActionContext(
                type="run_backtest", payload={"confirmation_id": "conf-1"}
            )
        )
    )
    action_b = turn_execution.semantic_turn_fingerprint(
        _production_checkpoint(
            action=StructuredActionContext(
                type="run_backtest", payload={"confirmation_id": "conf-2"}
            )
        )
    )
    assert action_a != action_b

    versioned_1 = turn_execution.semantic_turn_fingerprint(
        _production_checkpoint(
            artifact_references=[
                ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="conf-1",
                    artifact_status="active",
                    metadata={"version": 1},
                )
            ]
        )
    )
    versioned_2 = turn_execution.semantic_turn_fingerprint(
        _production_checkpoint(
            artifact_references=[
                ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="conf-1",
                    artifact_status="active",
                    metadata={"version": 2},
                )
            ]
        )
    )
    assert versioned_1 != versioned_2  # artifact version is typed identity

    superseded = turn_execution.semantic_turn_fingerprint(
        _production_checkpoint(
            artifact_references=[
                ArtifactReference(
                    artifact_kind="confirmation",
                    artifact_id="conf-1",
                    artifact_status="superseded",
                    metadata={"version": 1},
                )
            ]
        )
    )
    assert superseded != versioned_1


def test_model_and_serialized_checkpoints_normalize_identically() -> None:
    checkpoint = _production_checkpoint()
    serialized = {
        "stage_outcome": "await_user_reply",
        "run_state": checkpoint["run_state"].model_dump(mode="python"),
        "latest_task_snapshot": checkpoint["latest_task_snapshot"].model_dump(
            mode="python"
        ),
        "assistant_response": checkpoint["assistant_response"],
    }
    model_fp = turn_execution.semantic_turn_fingerprint(checkpoint)
    dict_fp = turn_execution.semantic_turn_fingerprint(serialized)
    assert model_fp is not None
    assert model_fp == dict_fp


# ── Blocker 3: every persisted accepted path claims one internal terminal ────


def _terminal_claims(monkeypatch) -> list[tuple[str, str | None, bool]]:
    """Record successful internal terminal claims (outcome, reason, in-scope)."""

    from argus.api.routers import agent as agent_router

    claims: list[tuple[str, str | None, bool]] = []
    real_claim = turn_execution.claim_turn_terminal

    def _recording_claim(outcome, *, reason=None):
        claimed = real_claim(outcome, reason=reason)
        if claimed:
            claims.append(
                (outcome, reason, turn_execution.active_turn_execution() is not None)
            )
        return claimed

    monkeypatch.setattr(agent_router, "claim_turn_terminal", _recording_claim)
    monkeypatch.setattr(turn_execution, "claim_turn_terminal", _recording_claim)
    return claims


def test_onboarding_prompt_turn_claims_one_internal_terminal(monkeypatch) -> None:
    from argus.api import state as api_state

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    claims = _terminal_claims(monkeypatch)
    client = _route_client()
    client.patch(
        "/api/v1/me",
        json={
            "onboarding": {
                "stage": "primary_goal_selection",
                "language_confirmed": True,
                "completed": False,
            }
        },
    )
    conversation = _conversation(client)
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "hola, quiero probar una idea",
            "language": "es-419",
        },
    )
    assert response.status_code == 200
    assert claims == [("answered", "onboarding_prompt", True)]


def test_onboarding_control_turn_claims_one_internal_terminal(monkeypatch) -> None:
    from argus.api import state as api_state

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    claims = _terminal_claims(monkeypatch)
    client = _route_client()
    conversation = _conversation(client)
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "__ONBOARDING_GOAL__:test_stock_idea",
            "language": "en",
        },
    )
    assert response.status_code == 200
    assert claims == [("answered", "onboarding_control", True)]


def test_deterministic_recovery_turn_claims_one_internal_terminal(
    monkeypatch,
) -> None:
    """A run_backtest action without identity resolves as the deterministic
    typed-recovery early responder — an accepted, persisted turn."""

    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        agent_router, "checkpoint_has_pending_confirmation", lambda values: True
    )
    claims = _terminal_claims(monkeypatch)
    client = _route_client()
    conversation = _conversation(client)
    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "run-attempt-1"},
        json={
            "conversation_id": conversation["id"],
            "message": "Run backtest",
            "language": "en",
            "action": {"type": "run_backtest", "payload": {}},
        },
    )
    assert response.status_code == 200
    assert claims == [("answered", "confirmation_action_missing_identity", True)]


def test_cancel_confirmation_turn_claims_one_internal_terminal(monkeypatch) -> None:
    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    monkeypatch.setattr(
        agent_router, "checkpoint_has_pending_confirmation", lambda values: True
    )
    claims = _terminal_claims(monkeypatch)
    client = _route_client()
    conversation = _conversation(client)
    response = client.post(
        "/api/v1/chat/stream",
        headers={"Idempotency-Key": "conf-cancel-1"},
        json={
            "conversation_id": conversation["id"],
            "message": "Cancel",
            "language": "en",
            "action": {
                "type": "cancel_confirmation",
                "payload": {"confirmation_id": "conf-cancel-1"},
            },
        },
    )
    assert response.status_code == 200
    assert claims == [("completed", "cancel_confirmation", True)]


def test_initialization_failure_turn_claims_one_internal_terminal(
    monkeypatch,
) -> None:
    """Runtime init failure after admission persistence is still an accepted
    turn and must own exactly one internal terminal."""

    from argus.api import state as api_state

    monkeypatch.setattr(api_state, "supabase_gateway", None)
    claims = _terminal_claims(monkeypatch)

    def _broken_workflow(request):
        raise RuntimeError("workflow init exploded")

    monkeypatch.setattr(api_state, "get_agent_runtime_workflow", _broken_workflow)
    client = _route_client()
    conversation = _conversation(client)
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200
    assert claims == [("recoverable_failed", "agent_runtime_init_failure", True)]


# ── Blocker 4: after-stream naming runs outside the completed turn ───────────


@pytest.mark.asyncio
async def test_after_stream_naming_cannot_mutate_the_completed_turn(
    monkeypatch,
) -> None:
    """The naming task is created before the route resets the ContextVar, so
    it inherits the turn context. It must be detached: no reservations against
    the completed turn, no summary drift, naming still fail-open."""

    from argus.api.chat import title_finalization

    monkeypatch.setenv("ARGUS_ENABLE_ARTIFACT_NAMING_IN_TESTS", "1")
    reserved_inside: list = []

    def _fake_finalize_title(**kwargs):
        reserved_inside.append(turn_execution.reserve_provider_call("name_suggestion"))

    monkeypatch.setattr(
        title_finalization,
        "finalize_conversation_title_after_turn",
        _fake_finalize_title,
    )

    token = turn_execution.begin_turn_execution(deadline_seconds=120.0, call_allowance=1)
    try:
        context = turn_execution.active_turn_execution()
        assert context is not None
        title_finalization.schedule_artifact_naming_after_stream(
            user_id="u1",
            conversation_id="c1",
            language="en",
        )
        for _ in range(20):
            await asyncio.sleep(0.01)
            if reserved_inside:
                break
        assert reserved_inside, "after-stream naming never ran"
        # Naming stays fail-open: it got an unconstrained permit of its own.
        assert reserved_inside[0] is not None
        # The completed turn's budget and evidence must not move.
        assert context.calls_reserved == 0
        assert context.blocked_tasks == []
        summary = turn_execution.turn_execution_summary([])
        assert summary["calls_reserved"] == 0
    finally:
        turn_execution.reset_turn_execution(token)
