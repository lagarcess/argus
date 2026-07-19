"""#239 final correction reds — two verified findings.

1. The canonical fingerprint omits typed pending progress: TaskSnapshot
   pending_needs, ResponseIntent kind/semantic_needs/requested_fields, and
   StrategySummary.extra_parameters do not participate, so distinct typed
   clarification states hash identically.
2. The turn-deadline diagnostic reports the per-event timeout and the
   current-event elapsed time instead of the absolute turn duration and the
   total turn elapsed time.
"""

from __future__ import annotations

import asyncio

import pytest
from argus.agent_runtime import turn_execution
from argus.agent_runtime.state.models import (
    ResponseIntent,
    RunState,
    StrategySummary,
    TaskSnapshot,
)


def teardown_function(function) -> None:
    turn_execution.set_monotonic_for_testing(None)


def _draft_strategy(**overrides):
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


def _checkpoint(
    *,
    strategy=None,
    pending_needs=None,
    response_intent=None,
    user_message: str = "quiero probar apple",
    assistant: str = "¿Qué fechas usamos?",
):
    from argus.agent_runtime.graph.workflow import WorkflowStageOutcome

    strategy = strategy if strategy is not None else _draft_strategy()
    run_state = RunState.new(
        current_user_message=user_message,
        recent_thread_history=[],
    )
    run_state.candidate_strategy_draft = strategy
    if response_intent is not None:
        run_state.response_intent = response_intent
    return {
        "stage_outcome": WorkflowStageOutcome("await_user_reply"),
        "run_state": run_state,
        "latest_task_snapshot": TaskSnapshot(
            pending_strategy_summary=strategy,
            pending_needs=list(pending_needs or []),
        ),
        "assistant_response": assistant,
    }


def _fp(state) -> str | None:
    return turn_execution.semantic_turn_fingerprint(state)


# ── Finding 1: typed pending progress must participate ───────────────────────


def test_snapshot_pending_needs_change_the_fingerprint() -> None:
    period = _fp(_checkpoint(pending_needs=["period"]))
    asset_target = _fp(_checkpoint(pending_needs=["asset_target"]))
    assert period is not None
    assert period != asset_target


def test_response_intent_kind_changes_the_fingerprint() -> None:
    clarification = _fp(_checkpoint(response_intent=ResponseIntent(kind="clarification")))
    guidance = _fp(_checkpoint(response_intent=ResponseIntent(kind="beginner_guidance")))
    assert clarification is not None
    assert clarification != guidance


def test_response_intent_needs_and_fields_change_the_fingerprint() -> None:
    period = _fp(
        _checkpoint(
            response_intent=ResponseIntent(
                kind="clarification",
                semantic_needs=["period"],
                requested_fields=["date_range"],
            )
        )
    )
    asset = _fp(
        _checkpoint(
            response_intent=ResponseIntent(
                kind="clarification",
                semantic_needs=["asset_target"],
                requested_fields=["asset_universe"],
            )
        )
    )
    assert period is not None
    assert period != asset


def test_pending_needs_normalize_across_checkpoint_and_public_payload() -> None:
    """The checkpoint carries snapshot.pending_needs plus the run-state
    response intent; the public payload carries response_intent only. The
    same pending progress must normalize to one fingerprint — and it must
    actually participate (differ from the no-pending baseline)."""

    baseline = _fp(_checkpoint())
    checkpoint_fp = _fp(
        _checkpoint(
            pending_needs=["period"],
            response_intent=ResponseIntent(
                kind="clarification",
                semantic_needs=["period"],
                requested_fields=["date_range"],
            ),
        )
    )
    public_fp = _fp(
        {
            "stage_outcome": "await_user_reply",
            "assistant_response": "Which dates should we use?",
            "pending_strategy": {
                "strategy": _draft_strategy().model_dump(mode="python"),
                "requested_field": None,
                "missing_required_fields": [],
            },
            "response_intent": {
                "kind": "clarification",
                "semantic_needs": ["period"],
                "requested_fields": ["date_range"],
            },
        }
    )
    assert checkpoint_fp is not None
    assert checkpoint_fp == public_fp
    assert checkpoint_fp != baseline  # pending progress participates


def test_typed_extra_parameters_change_the_fingerprint() -> None:
    monthly = _fp(
        _checkpoint(
            strategy=_draft_strategy(extra_parameters={"rebalance_frequency": "monthly"})
        )
    )
    weekly = _fp(
        _checkpoint(
            strategy=_draft_strategy(extra_parameters={"rebalance_frequency": "weekly"})
        )
    )
    assert monthly is not None
    assert monthly != weekly


def test_pending_state_models_and_dicts_normalize_identically() -> None:
    checkpoint = _checkpoint(
        pending_needs=["period"],
        response_intent=ResponseIntent(
            kind="clarification",
            semantic_needs=["period"],
            requested_fields=["date_range"],
        ),
    )
    serialized = {
        "stage_outcome": "await_user_reply",
        "run_state": checkpoint["run_state"].model_dump(mode="python"),
        "latest_task_snapshot": checkpoint["latest_task_snapshot"].model_dump(
            mode="python"
        ),
        "assistant_response": checkpoint["assistant_response"],
    }
    model_fp = _fp(checkpoint)
    assert model_fp is not None
    assert model_fp == _fp(serialized)
    assert model_fp != _fp(_checkpoint())  # the pending material participates


def test_intent_prose_carriers_stay_excluded() -> None:
    """facts/options copy and reworded prose must not affect the hash once
    pending progress participates."""

    spanish = _fp(
        _checkpoint(
            user_message="quiero probar apple",
            assistant="¿Qué fechas usamos?",
            response_intent=ResponseIntent(
                kind="clarification",
                semantic_needs=["period"],
                requested_fields=["date_range"],
                facts={"explanation": "Necesito el rango de fechas."},
                options=[{"id": "opt-1", "label": "Usar fechas por defecto"}],
            ),
        )
    )
    english = _fp(
        _checkpoint(
            user_message="i want to test apple",
            assistant="Which dates should we use?",
            response_intent=ResponseIntent(
                kind="clarification",
                semantic_needs=["period"],
                requested_fields=["date_range"],
                facts={"explanation": "I need the date range."},
                options=[{"id": "opt-1", "label": "Use the default dates"}],
            ),
        )
    )
    assert spanish is not None
    assert spanish == english


# ── Finding 2: turn-deadline diagnostics must report turn timing ─────────────


@pytest.mark.asyncio
async def test_turn_deadline_diagnostics_report_turn_timing() -> None:
    """The absolute-wall diagnostic must carry the configured turn duration
    and the total turn elapsed time, not the per-event limit and the
    current-event elapsed."""

    from argus.api.chat import runtime_events as runtime_events_module

    token = turn_execution.begin_turn_execution(deadline_seconds=0.05)
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
        diagnostics = getattr(excinfo.value, "diagnostics", None) or {}
        assert diagnostics.get("code") == "turn_deadline_exhausted"
        assert diagnostics.get("timeout_seconds") == 0.05
        assert diagnostics.get("elapsed_seconds") >= 0.05
    finally:
        turn_execution.reset_turn_execution(token)
