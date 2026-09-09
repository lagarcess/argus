"""Actual catalog dispatch and its evidence for the measurement harness."""

from __future__ import annotations

import asyncio
from typing import Any

from argus.agent_runtime.stages.interpret_types import StageResult
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import (
    RunState,
    TaskSnapshot,
    UserState,
    normalize_task_intent,
)
from argus.domain.tool_contracts import ToolOutcome, ToolResultCard
from pydantic import ValidationError

from tests.evals.measurement_assertions import _compare


def dispatch_requested_calls(
    *,
    state: RunState,
    interpreted: Any,
    user: UserState,
    latest_task_snapshot: TaskSnapshot | None,
    selected_thread_metadata: dict[str, Any],
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
            latest_task_snapshot=latest_task_snapshot,
            selected_thread_metadata=selected_thread_metadata,
        )
    )


def followup_thread_metadata(
    patch: dict[str, Any],
    *,
    last_stage_outcome: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"last_stage_outcome": last_stage_outcome}
    for key in (
        "requested_field",
        "missing_required_fields",
        "response_intent",
        "clarification",
    ):
        value = patch.get(key)
        if value not in (None, "", [], {}):
            metadata[key] = value
    return metadata


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
    # Confirmation owns missing-field validation. An incoming readiness event
    # is only its handoff when the actual confirm stage requests clarification.
    milestones = [
        entry
        for index, entry in enumerate(milestones)
        if not (
            entry["outcome"] == "ready_for_confirmation"
            and index + 1 < len(milestones)
            and milestones[index + 1]
            == {"stage": "confirm", "outcome": "needs_clarification"}
        )
    ]
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
        "tool_usage": _usage_evidence(patch),
    }


def _usage_evidence(patch: dict[str, Any]) -> list[dict[str, Any]]:
    observations = []
    for effect in patch.get("tool_effects", []):
        research = (effect.get("stage_patch") or {}).get("research") or {}
        usage = research.get("usage")
        if isinstance(usage, dict):
            observations.append(
                {
                    "call_id": effect["call_id"],
                    "tool_name": effect["tool_name"],
                    "usage": {
                        key: value
                        for key, value in usage.items()
                        if key
                        in {"cost_usd", "latency_ms", "invocations", "cache_status"}
                    },
                }
            )
    return observations


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
    effective_patch: dict[str, Any] = {}
    calls: dict[str, list] = {
        "tool_calls": [],
        "tool_call_records": [],
        "tool_result_cards": [],
        "tool_usage": [],
    }
    for interpreted, dispatched, confirmed, clarified in turns:
        for result in (interpreted, dispatched, confirmed, clarified):
            if result is not None:
                effective_patch.update(result.patch)
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
        "primary_intent": normalize_task_intent(turns[-1][0].patch.get("intent")),
        "intent": normalize_task_intent(effective_patch.get("intent")),
        "stage_outcomes": [entry["outcome"] for entry in trace],
        "acceptance_stage_outcomes": milestones,
        "execution_trace": trace,
        **calls,
    }


def compare_dispatch(
    expected: bool | None,
    outcome: dict[str, Any],
    failures: list[str],
    *,
    requires_answer: bool = True,
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
    if requires_answer and not _has_delivered_answer(
        records, outcome.get("tool_result_cards") or []
    ):
        failures.append(
            "tool_dispatch: expected a completed answer from an executed call"
        )


def _has_delivered_answer(records: list[dict], cards: list[dict]) -> bool:
    """A successful invocation may only have queued work; its card owns delivery."""
    for raw_card in cards:
        try:
            card = ToolResultCard.model_validate(raw_card)
        except (ValidationError, TypeError):
            continue
        if card.outcome.status != "succeeded" or not (
            card.presentation.answer is not None
            or (card.presentation.narrative or "").strip()
        ):
            continue
        for record in records:
            if (
                record.get("call_id") != card.call_id
                or record.get("outcome") != "succeeded"
            ):
                continue
            try:
                returned = ToolOutcome.model_validate(record.get("tool_outcome"))
            except (ValidationError, TypeError):
                continue
            if returned == card.outcome:
                return True
    return False


def compare_stage_outcomes(
    expected: tuple[str, ...], outcome: dict[str, Any], failures: list[str]
) -> None:
    if not expected:
        return
    expected_milestones = list(expected)
    if "execution_trace" in outcome:
        # The old harness could expose the same confirmation handoff. Compare
        # that scheduling edge identically on both sides of measured traces.
        expected_milestones = [
            item
            for index, item in enumerate(expected)
            if not (
                item == "ready_for_confirmation"
                and index + 1 < len(expected)
                and expected[index + 1] == "needs_clarification"
            )
        ]
    _compare(
        "stage_outcomes",
        expected_milestones,
        outcome.get("acceptance_stage_outcomes", outcome.get("stage_outcomes")),
        failures,
    )
