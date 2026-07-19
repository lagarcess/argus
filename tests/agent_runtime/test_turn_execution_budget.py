"""#239 — one turn-wide execution budget with typed semantic progress.

The controller owns: one monotonic absolute deadline, one shared provider-call
allowance, the entry/exit semantic fingerprint, and exactly one internal
terminal outcome per accepted runtime turn. Nested components and fallback
candidates can never restart either allowance, and task-local provider
timeouts remain valid but are bounded by the remaining turn deadline.
"""

from __future__ import annotations

import asyncio

from argus.agent_runtime import turn_execution


def _begin(
    *,
    deadline_seconds: float = 120.0,
    call_allowance: int = 6,
    entry_fingerprint: str | None = None,
    now: float = 1000.0,
):
    turn_execution.set_monotonic_for_testing(lambda: now)
    return turn_execution.begin_turn_execution(
        deadline_seconds=deadline_seconds,
        call_allowance=call_allowance,
        entry_fingerprint=entry_fingerprint,
    )


def teardown_function(function) -> None:
    turn_execution.set_monotonic_for_testing(None)


def test_reservation_consumes_one_shared_allowance() -> None:
    token = _begin(call_allowance=2)
    try:
        context = turn_execution.active_turn_execution()
        assert context is not None
        first = turn_execution.reserve_provider_call("interpretation")
        second = turn_execution.reserve_provider_call("clarification")
        third = turn_execution.reserve_provider_call("chat_composer")
        assert first is not None
        assert second is not None
        assert third is None
        assert context.calls_reserved == 2
        assert context.calls_exhausted is True
    finally:
        turn_execution.reset_turn_execution(token)


def test_deadline_is_monotonic_and_never_resets() -> None:
    """Red 3: a provider timeout consuming most of the deadline leaves only
    the remainder for the next component — nothing restarts the clock."""

    clock = {"now": 1000.0}
    turn_execution.set_monotonic_for_testing(lambda: clock["now"])
    token = turn_execution.begin_turn_execution(
        deadline_seconds=100.0,
        call_allowance=6,
        entry_fingerprint=None,
    )
    try:
        first = turn_execution.reserve_provider_call(
            "interpretation", task_timeout_seconds=30.0
        )
        assert first is not None
        assert first.timeout_seconds == 30.0  # task-local stays tighter

        # The first call burned 70 seconds of the turn.
        clock["now"] = 1070.0
        second = turn_execution.reserve_provider_call(
            "interpretation", task_timeout_seconds=45.0
        )
        assert second is not None
        # Remaining turn deadline (30s) now bounds the task timeout.
        assert second.timeout_seconds == 30.0

        clock["now"] = 1101.0  # past the deadline
        third = turn_execution.reserve_provider_call(
            "clarification", task_timeout_seconds=5.0
        )
        assert third is None
        context = turn_execution.active_turn_execution()
        assert context is not None and context.deadline_exhausted is True
    finally:
        turn_execution.reset_turn_execution(token)
        turn_execution.set_monotonic_for_testing(None)


def test_task_local_timeout_stays_tighter_below_remaining_deadline() -> None:
    token = _begin(deadline_seconds=100.0)
    try:
        permit = turn_execution.reserve_provider_call(
            "interpretation", task_timeout_seconds=12.0
        )
        assert permit is not None
        assert permit.timeout_seconds == 12.0
    finally:
        turn_execution.reset_turn_execution(token)


def test_terminal_claim_is_idempotent_first_wins() -> None:
    token = _begin()
    try:
        first = turn_execution.claim_turn_terminal(
            "completed", reason="artifact_persisted"
        )
        second = turn_execution.claim_turn_terminal(
            "recoverable_failed", reason="late_failure"
        )
        context = turn_execution.active_turn_execution()
        assert first is True
        assert second is False
        assert context is not None
        assert context.terminal == "completed"
        assert context.terminal_reason == "artifact_persisted"
    finally:
        turn_execution.reset_turn_execution(token)


def test_unchanged_fingerprint_transition_is_no_progress() -> None:
    token = _begin(entry_fingerprint="fp-1")
    try:
        transition = turn_execution.record_exit_fingerprint("fp-1")
        assert transition == "unchanged"
        assert turn_execution.no_progress_detected() is True
    finally:
        turn_execution.reset_turn_execution(token)


def test_advanced_fingerprint_transition_is_progress() -> None:
    token = _begin(entry_fingerprint="fp-1")
    try:
        transition = turn_execution.record_exit_fingerprint("fp-2")
        assert transition == "advanced"
        assert turn_execution.no_progress_detected() is False
    finally:
        turn_execution.reset_turn_execution(token)


def test_initial_turn_without_entry_fingerprint_is_initial() -> None:
    token = _begin(entry_fingerprint=None)
    try:
        transition = turn_execution.record_exit_fingerprint("fp-1")
        assert transition == "initial"
        assert turn_execution.no_progress_detected() is False
    finally:
        turn_execution.reset_turn_execution(token)


def test_reset_cleans_up_and_never_leaks_into_the_next_turn() -> None:
    """Red 11: cancellation/teardown removes the context; a later turn starts
    fresh with its own allowance and no inherited terminal."""

    token = _begin(call_allowance=1)
    turn_execution.reserve_provider_call("interpretation")
    turn_execution.claim_turn_terminal("recoverable_failed", reason="boom")
    turn_execution.reset_turn_execution(token)

    assert turn_execution.active_turn_execution() is None
    next_token = _begin(call_allowance=1)
    try:
        context = turn_execution.active_turn_execution()
        assert context is not None
        assert context.terminal is None
        assert context.calls_reserved == 0
        assert turn_execution.reserve_provider_call("interpretation") is not None
    finally:
        turn_execution.reset_turn_execution(next_token)


def test_concurrent_turns_do_not_share_budget_or_terminals() -> None:
    """Red 12: two concurrent conversations own independent contexts."""

    async def _turn(allowance: int, terminal: str) -> tuple[int, str | None]:
        token = turn_execution.begin_turn_execution(
            deadline_seconds=60.0,
            call_allowance=allowance,
            entry_fingerprint=None,
        )
        try:
            reserved = 0
            while turn_execution.reserve_provider_call("interpretation") is not None:
                reserved += 1
            turn_execution.claim_turn_terminal(terminal, reason="test")
            await asyncio.sleep(0)
            context = turn_execution.active_turn_execution()
            assert context is not None
            return reserved, context.terminal
        finally:
            turn_execution.reset_turn_execution(token)

    async def _both() -> list[tuple[int, str | None]]:
        return list(
            await asyncio.gather(
                _turn(1, "completed"),
                _turn(3, "answered"),
            )
        )

    results = asyncio.run(_both())
    assert (1, "completed") in results
    assert (3, "answered") in results


def test_turn_summary_exposes_evidence_without_prose() -> None:
    """Red 9: the receipt-facing summary carries counts, latency, transition,
    exhaustion, and the terminal — never user content."""

    from argus.llm.openrouter import OpenRouterRouteReceipt

    token = _begin(entry_fingerprint="fp-1", call_allowance=2)
    try:
        turn_execution.reserve_provider_call("interpretation")
        turn_execution.record_exit_fingerprint("fp-1")
        turn_execution.claim_turn_terminal(
            "no_progress", reason="unchanged_fingerprint"
        )
        receipts = [
            OpenRouterRouteReceipt(
                task="interpretation",
                tier="structured",
                model="stub-model",
                fallback_model="stub-fallback",
                mode="json_schema",
                schema_name="LLMInterpretationResponse",
                latency_ms=1200,
                outcome="succeeded",
                failure_mode=None,
                token_usage=None,
                usage_cost_usd=None,
                context_packet_ids=[],
                fallback_used=False,
                created_at="2026-07-18T00:00:00+00:00",
            )
        ]
        summary = turn_execution.turn_execution_summary(receipts)
    finally:
        turn_execution.reset_turn_execution(token)

    assert summary["call_count"] == 1
    assert summary["calls_reserved"] == 1
    assert summary["total_latency_ms"] == 1200
    assert summary["per_call_latency_ms"] == [1200]
    assert summary["tasks"] == ["interpretation"]
    assert summary["outcomes"] == ["succeeded"]
    assert summary["fingerprint_transition"] == "unchanged"
    assert summary["terminal"] == "no_progress"
    assert summary["terminal_reason"] == "unchanged_fingerprint"
    assert summary["deadline_exhausted"] is False
    assert summary["calls_exhausted"] is False
    flattened = str(summary)
    assert "AAPL" not in flattened  # no strategy/user prose of any kind
    assert "user" not in flattened.lower() or "user" not in summary


# ── Provider-boundary integration (#239 reds 4-7) ────────────────────────────


def test_fallback_candidates_consume_the_same_turn_allowance(monkeypatch) -> None:
    """Red 6: with one remaining call, a failing primary candidate exhausts
    the allowance and the configured fallback candidate is never attempted."""

    from argus.llm import openrouter

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        openrouter,
        "openrouter_structured_model_candidates",
        lambda model_name=None, task="interpretation": ["model-a", "model-b"],
    )
    posts: list[str] = []

    async def _failing_post(*, client, api_key, payload):
        posts.append(str(payload.get("model")))
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(openrouter, "_post_openrouter_json_schema", _failing_post)

    from pydantic import BaseModel

    class _Schema(BaseModel):
        value: str = "x"

    import pytest

    token = _begin(call_allowance=1)
    capture = openrouter.begin_openrouter_route_receipt_capture()
    try:
        # The real primary failure surfaces (existing caller semantics); the
        # decisive proof is that the fallback candidate never posts.
        with pytest.raises(RuntimeError, match="provider exploded"):
            asyncio.run(
                openrouter.invoke_openrouter_json_schema(
                    task="interpretation",
                    messages=[{"role": "user", "content": "hi"}],
                    schema_model=_Schema,
                    schema_name="TestSchema",
                )
            )
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(capture)
        turn_execution.reset_turn_execution(token)

    assert posts == ["model-a"]  # the fallback candidate never posted
    outcomes = [(receipt.outcome, receipt.failure_mode) for receipt in receipts]
    assert ("failed", "RuntimeError") in outcomes
    assert ("skipped", "turn_call_allowance_exhausted") in outcomes


def test_bounded_repair_uses_allowance_and_no_third_attempt(monkeypatch) -> None:
    """Reds 4+5: primary failure plus one bounded repair fit in the shared
    allowance; a further attempt is blocked with typed exhaustion evidence."""

    from argus.llm import openrouter

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(
        openrouter,
        "openrouter_structured_model_candidates",
        lambda model_name=None, task="interpretation": ["model-a"],
    )
    posts: list[int] = []

    class _FakeResponse:
        def json(self):
            return {
                "choices": [{"message": {"content": '{"value": "repaired"}'}}]
            }

    async def _post(*, client, api_key, payload):
        posts.append(1)
        if len(posts) == 1:
            raise ValueError("malformed primary")
        return _FakeResponse()

    monkeypatch.setattr(openrouter, "_post_openrouter_json_schema", _post)

    from pydantic import BaseModel

    class _Schema(BaseModel):
        value: str

    async def _turn() -> tuple[object, object, object]:
        primary = None
        try:
            primary = await openrouter.invoke_openrouter_json_schema(
                task="interpretation",
                messages=[{"role": "user", "content": "hi"}],
                schema_model=_Schema,
                schema_name="TestSchema",
            )
        except Exception as exc:
            primary = exc
        repair = await openrouter.invoke_openrouter_json_schema(
            task="interpretation",
            messages=[{"role": "user", "content": "repair"}],
            schema_model=_Schema,
            schema_name="TestSchema",
        )
        third = await openrouter.invoke_openrouter_json_schema(
            task="interpretation",
            messages=[{"role": "user", "content": "again"}],
            schema_model=_Schema,
            schema_name="TestSchema",
        )
        return primary, repair, third

    token = _begin(call_allowance=2)
    capture = openrouter.begin_openrouter_route_receipt_capture()
    try:
        primary, repair, third = asyncio.run(_turn())
        context = turn_execution.active_turn_execution()
        assert context is not None
        assert context.calls_reserved == 2
        assert context.calls_exhausted is True
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(capture)
        turn_execution.reset_turn_execution(token)

    assert isinstance(primary, Exception)
    assert getattr(repair, "value", None) == "repaired"
    assert third is None  # no third provider attempt
    assert len(posts) == 2
    assert [(r.outcome, r.failure_mode) for r in receipts][-1] == (
        "skipped",
        "turn_call_allowance_exhausted",
    )


def test_composer_cannot_restart_an_exhausted_allowance(monkeypatch) -> None:
    """Red 7: clarifier/audit/composer tasks share the one turn allowance —
    exhaustion by interpretation blocks them too."""

    from argus.llm import openrouter

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    posts: list[int] = []

    async def _post(*, client, api_key, payload):
        posts.append(1)
        raise RuntimeError("never expected")

    monkeypatch.setattr(openrouter, "_post_openrouter_json_schema", _post)

    token = _begin(call_allowance=0)
    capture = openrouter.begin_openrouter_route_receipt_capture()
    try:
        content = asyncio.run(
            openrouter.invoke_openrouter_chat_completion(
                task="chat_composer",
                messages=[{"role": "user", "content": "compose"}],
                model_name="model-a",
            )
        )
    finally:
        receipts = openrouter.end_openrouter_route_receipt_capture(capture)
        turn_execution.reset_turn_execution(token)

    assert content is None
    assert posts == []
    assert [(r.outcome, r.failure_mode) for r in receipts] == [
        ("skipped", "turn_call_allowance_exhausted")
    ]


def test_direct_interpreter_model_path_reserves_from_the_turn(monkeypatch) -> None:
    """The primary structured interpretation goes through ChatOpenRouter
    directly — its fallback attempt must consume the same shared allowance
    and stop when exhausted."""

    from argus.agent_runtime import llm_interpreter as interpreter_module

    attempts: list[str] = []

    class _ExplodingStructured:
        async def ainvoke(self, messages):
            attempts.append("call")
            raise RuntimeError("primary interpretation failed")

    class _FakeModel:
        def with_structured_output(self, schema):
            return _ExplodingStructured()

    from argus.llm import openrouter as openrouter_module

    monkeypatch.setattr(
        interpreter_module,
        "build_openrouter_model",
        lambda task, model_name=None: _FakeModel(),
    )
    # The fallback path re-imports resolve_openrouter_model from the llm
    # module inside the method; patch the source.
    monkeypatch.setattr(
        openrouter_module,
        "resolve_openrouter_model",
        lambda model_name=None, task=None, fallback=False: (
            "fallback-model" if fallback else "primary-model"
        ),
    )

    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )

    # An explicit model name selects the direct ChatOpenRouter
    # primary+fallback path (the non-wrapper corridor under test).
    interpreter = interpreter_module.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(),
        model_name="primary-model",
    )

    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import UserState

    request = InterpretationRequest(
        current_user_message="test AAPL",
        user=UserState(user_id="u1"),
    )

    token = _begin(call_allowance=1)
    try:
        result = asyncio.run(interpreter.ainvoke(request))
        context = turn_execution.active_turn_execution()
        assert context is not None
        assert context.calls_reserved == 1
        assert context.calls_exhausted is True
    finally:
        turn_execution.reset_turn_execution(token)

    assert result is None
    assert attempts == ["call"]  # the fallback model attempt never ran


# ── Semantic fingerprint (#239) ──────────────────────────────────────────────


def test_fingerprint_ignores_prose_and_hashes_typed_state_only() -> None:
    base = {
        "stage_outcome": "await_user_reply",
        "pending_strategy": {
            "requested_field": "date_range",
            "missing_required_fields": ["date_range"],
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "timeframe": "1D",
                "strategy_thesis": "Hold Apple because I like it.",
                "raw_user_phrasing": "buy apple please",
            },
        },
    }
    reworded = {
        **base,
        "pending_strategy": {
            **base["pending_strategy"],
            "strategy": {
                **base["pending_strategy"]["strategy"],
                "strategy_thesis": "Totally different prose thesis.",
                "raw_user_phrasing": "compra apple por favor",
            },
        },
        "assistant_response": "Different localized copy entirely.",
    }
    advanced = {
        **base,
        "pending_strategy": {
            **base["pending_strategy"],
            "strategy": {
                **base["pending_strategy"]["strategy"],
                "asset_universe": ["AAPL", "MSFT"],
            },
        },
    }

    first = turn_execution.semantic_turn_fingerprint(base)
    second = turn_execution.semantic_turn_fingerprint(reworded)
    third = turn_execution.semantic_turn_fingerprint(advanced)
    assert first is not None
    assert first == second  # prose and localized copy are excluded
    assert third != first  # typed advancement changes the fingerprint


def test_fingerprint_is_none_without_typed_material() -> None:
    assert turn_execution.semantic_turn_fingerprint(None) is None
    assert turn_execution.semantic_turn_fingerprint({}) is None
    assert (
        turn_execution.semantic_turn_fingerprint(
            {"assistant_response": "hello there"}
        )
        is None
    )


# ── Route wiring (#239 reds 1-2) ─────────────────────────────────────────────


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


def test_normal_turn_persists_one_terminal_in_receipt_metadata(monkeypatch) -> None:
    """Red 1: one accepted turn ends with exactly one internal terminal and
    its turn-execution evidence rides the existing receipt metadata."""

    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(api_state, "supabase_gateway", None)

    async def _success_events(**kwargs):
        yield {"type": "token", "content": "Answer."}
        yield {
            "type": "final",
            "payload": {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "Answer.",
            },
        }

    monkeypatch.setattr(agent_router, "stream_agent_turn_events", _success_events)
    persisted: list[dict] = []

    def _capture_receipts(**kwargs):
        persisted.append(dict(kwargs.get("metadata") or {}))

    monkeypatch.setattr(agent_router, "persist_route_receipts", _capture_receipts)

    client = _route_client()
    conversation = client.post(
        "/api/v1/conversations", json={"language": "en"}
    ).json()["conversation"]
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "test AAPL momentum",
            "language": "en",
        },
    )
    assert response.status_code == 200

    assert len(persisted) == 1
    summary = persisted[0].get("turn_execution")
    assert isinstance(summary, dict)
    assert summary["terminal"] == "answered"
    assert summary["call_count"] == 0  # hermetic: no provider calls
    assert summary["deadline_exhausted"] is False
    assert summary["calls_exhausted"] is False


def test_repeated_equivalent_clarification_is_no_progress(monkeypatch) -> None:
    """Red 2: a turn that exits in the same typed clarification state it
    entered claims the no_progress terminal with an unchanged transition."""

    from argus.api import state as api_state
    from argus.api.routers import agent as agent_router

    monkeypatch.setattr(api_state, "supabase_gateway", None)

    pending_state = {
        "stage_outcome": "await_user_reply",
        "pending_strategy": {
            "requested_field": "date_range",
            "missing_required_fields": ["date_range"],
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
            },
        },
    }

    async def _checkpoint_values(**kwargs):
        return dict(pending_state)

    monkeypatch.setattr(agent_router, "runtime_checkpoint_values", _checkpoint_values)

    async def _same_clarification_events(**kwargs):
        yield {"type": "token", "content": "Which dates?"}
        yield {
            "type": "final",
            "payload": {
                **pending_state,
                "assistant_response": "Which dates should we use?",
            },
        }

    monkeypatch.setattr(
        agent_router, "stream_agent_turn_events", _same_clarification_events
    )
    persisted: list[dict] = []

    def _capture_receipts(**kwargs):
        persisted.append(dict(kwargs.get("metadata") or {}))

    monkeypatch.setattr(agent_router, "persist_route_receipts", _capture_receipts)

    client = _route_client()
    conversation = client.post(
        "/api/v1/conversations", json={"language": "en"}
    ).json()["conversation"]
    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "still not sure",
            "language": "en",
        },
    )
    assert response.status_code == 200

    assert len(persisted) == 1
    summary = persisted[0].get("turn_execution")
    assert isinstance(summary, dict)
    assert summary["fingerprint_transition"] == "unchanged"
    assert summary["terminal"] == "no_progress"
    assert summary["terminal_reason"] == "unchanged_fingerprint"
