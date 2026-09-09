"""Actual catalog dispatch and its evidence for the measurement harness."""

from __future__ import annotations

import asyncio
from typing import Any

from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import RunState, UserState


def dispatch_requested_calls(
    *, state: RunState, interpreted: Any, user: UserState
) -> StageResult | None:
    """Follow an explicit call through the production execute owner.

    This harness has always stopped Run-button cases at validated approval.
    Fresh model calls have no fabricated approval: a backtest therefore stops
    at its real confirmation handoff, while unconfirmed research tools run.
    """
    if interpreted.outcome != "approved_for_execution" or not interpreted.patch.get(
        "tool_calls"
    ):
        return None
    call_state = RunState.model_validate({**state.model_dump(), **interpreted.patch})
    return asyncio.run(
        execute_tool_calls_async(
            state=call_state,
            tool=None,
            user=user,
            language=user.language_preference,
        )
    )


def turn_trace(
    *,
    interpreted: Any,
    dispatched: Any = None,
    confirmed: Any = None,
    clarified: Any = None,
) -> tuple[list[dict[str, str]], list[str]]:
    stages = [
        ("interpret", interpreted),
        ("execute", dispatched),
        ("confirm", confirmed),
        ("clarify", clarified),
    ]
    raw = [
        {"stage": name, "outcome": str(result.outcome)}
        for name, result in stages
        if result is not None
    ]
    # The new initial approval is a dispatch scheduling edge. Keep it in the
    # raw trace, but compare the original behavioral milestones at their new
    # owner only after the real execute stage has actually returned.
    has_dispatch_edge = (
        dispatched is not None
        and interpreted.outcome == "approved_for_execution"
        and bool(interpreted.patch.get("tool_calls"))
    )
    milestones = raw[1:] if has_dispatch_edge else raw
    return raw, [entry["outcome"] for entry in milestones]


def declared_tool_evidence(
    *, interpreted: Any, dispatched: Any = None
) -> dict[str, list]:
    calls = [
        call.model_dump(mode="json") if hasattr(call, "model_dump") else dict(call)
        for call in interpreted.patch.get("tool_calls", [])
    ]
    patch = dispatched.patch if dispatched is not None else {}
    return {
        "tool_calls": calls,
        "tool_call_records": list(patch.get("tool_call_records", [])),
        "tool_result_cards": list(
            (patch.get("final_response_payload") or {}).get("tool_result_cards", [])
        ),
    }


def measurement_execution_evidence(
    *,
    interpreted: Any,
    dispatched: Any,
    confirmed: Any,
    clarified: Any,
    followup: dict[str, Any] | None,
) -> dict[str, Any]:
    turns = [(interpreted, dispatched, confirmed, clarified)]
    if followup and followup.get("interpret_result") is not None:
        turns.append(
            tuple(
                followup.get(key)
                for key in (
                    "interpret_result",
                    "dispatch_result",
                    "confirm_result",
                    "clarify_result",
                )
            )
        )
    trace: list[dict[str, str]] = []
    milestones: list[str] = []
    calls: dict[str, list] = {
        "tool_calls": [],
        "tool_call_records": [],
        "tool_result_cards": [],
    }
    for interpreted, dispatched, confirmed, clarified in turns:
        turn_events, turn_milestones = turn_trace(
            interpreted=interpreted,
            dispatched=dispatched,
            confirmed=confirmed,
            clarified=clarified,
        )
        trace.extend(turn_events)
        milestones.extend(turn_milestones)
        evidence = declared_tool_evidence(interpreted=interpreted, dispatched=dispatched)
        for key in calls:
            calls[key].extend(evidence[key])
    return {
        "stage_outcomes": [entry["outcome"] for entry in trace],
        "acceptance_stage_outcomes": milestones,
        "execution_trace": trace,
        **calls,
    }


def compare_dispatch(
    expected: bool | None, outcome: dict[str, Any], failures: list[str]
) -> None:
    if expected is None:
        return
    calls = outcome.get("tool_calls") or []
    records = outcome.get("tool_call_records") or []
    if expected is False:
        if calls or records:
            failures.append("tool_dispatch: expected no declared calls")
        return
    if not calls:
        failures.append("tool_dispatch: expected executed declared calls")
        return
    if [record.get("call_id") for record in records] != [
        call.get("call_id") for call in calls
    ]:
        failures.append(
            "tool_dispatch: every selected call must have its own execution record"
        )
    if any(record.get("outcome") != "succeeded" for record in records):
        failures.append(
            "tool_dispatch: a bounded, invalid, or unavailable call is not an answer"
        )
