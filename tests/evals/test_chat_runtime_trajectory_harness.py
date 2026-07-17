from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from tests.evals.chat_runtime_eval_harness import (
    ALPHA_TRAJECTORY_PATH,
    StepObservation,
    TrajectoryAdapters,
    load_alpha_trajectories,
    run_alpha_trajectory,
    trajectory_scorecard_for_results,
    write_trajectory_scorecard,
)

EXPECTED_ALPHA_LABELS = {f"alpha_session_{index:02d}" for index in range(1, 8)}
EXPECTED_OWNING_ISSUES = {"#230", "#238", "#239", "#240", "#241", "#242", "#251"}
EXPECTED_OPERATIONS = {
    "stream",
    "action",
    "disconnect",
    "reload",
    "retry",
    "persistence",
}


def _matching_observation(step: Any) -> StepObservation:
    expectation = step.expectation
    raw_sse = None
    if expectation.canonical_sse:
        outcome = expectation.stage_outcome or "ready_to_respond"
        raw_sse = "\n\n".join(
            [
                'data: {"type":"stage_start","stage":"interpret"}',
                f'data: {{"type":"stage_outcome","outcome":"{outcome}"}}',
                f'data: {{"type":"final","payload":{{"stage_outcome":"{outcome}"}}}}',
                "data: [DONE]",
            ]
        )
    route_receipts: tuple[dict[str, Any], ...] = ()
    if expectation.route_budget is not None:
        route_receipts = (
            {
                "task": "interpretation",
                "latency_ms": min(expectation.route_budget.max_latency_ms or 1, 100),
                "usage_cost_usd": min(
                    expectation.route_budget.max_cost_usd or 0.0,
                    0.001,
                ),
            },
        )
    return StepObservation(
        raw_sse=raw_sse,
        visible_response_category=expectation.visible_response_category,
        stage_outcome=expectation.stage_outcome,
        artifact_identity=expectation.artifact_identity,
        action_identity=expectation.action_identity,
        persistence_state=expectation.persistence_state,
        reload_state=expectation.reload_state,
        recovery_code=expectation.recovery_code,
        route_receipts=route_receipts,
        typed_terminal=expectation.typed_terminal,
        fingerprint=step.step_id,
        checkpoints=dict(expectation.checkpoints),
    )


def _recording_adapters(
    calls: list[tuple[str, str]],
    *,
    overrides: dict[str, StepObservation] | None = None,
) -> TrajectoryAdapters:
    resolved_overrides = overrides or {}

    def handler(*, trajectory: Any, step: Any, history: Any) -> StepObservation:
        del trajectory, history
        calls.append((step.operation, step.step_id))
        return resolved_overrides.get(step.step_id, _matching_observation(step))

    return TrajectoryAdapters(
        stream=handler,
        action=handler,
        disconnect=handler,
        reload=handler,
        retry=handler,
        persistence=handler,
    )


def test_alpha_trajectory_fixtures_are_complete_sanitized_and_issue_tagged() -> None:
    raw = ALPHA_TRAJECTORY_PATH.read_text(encoding="utf-8")
    trajectories = load_alpha_trajectories()

    assert {trajectory.label for trajectory in trajectories} == EXPECTED_ALPHA_LABELS
    assert {trajectory.locale for trajectory in trajectories} == {"en", "es-419"}
    assert {trajectory.expected_fail.issue for trajectory in trajectories} == (
        EXPECTED_OWNING_ISSUES
    )
    assert {
        step.operation for trajectory in trajectories for step in trajectory.steps
    } == EXPECTED_OPERATIONS

    covered_expectations = {
        key
        for trajectory in trajectories
        for step in trajectory.steps
        for key, value in step.expectation.as_dict().items()
        if value not in (None, {}, ())
    }
    assert {
        "visible_response_category",
        "stage_outcome",
        "canonical_sse",
        "artifact_identity",
        "action_identity",
        "persistence_state",
        "reload_state",
        "recovery_code",
        "route_budget",
        "typed_terminal",
        "checkpoints",
    }.issubset(covered_expectations)

    for trajectory in trajectories:
        assert trajectory.purpose
        assert len(trajectory.steps) >= 3
        assert trajectory.expected_fail.reason
        assert trajectory.expected_fail.allowed_failures
        assert re.fullmatch(r"#\d+", trajectory.expected_fail.issue)
        assert all(
            prefix.endswith(":") for prefix in trajectory.expected_fail.allowed_failures
        )
        assert [step.index for step in trajectory.steps] == list(
            range(1, len(trajectory.steps) + 1)
        )
        assert all(
            step.step_id.startswith(f"{trajectory.label}:step:")
            for step in trajectory.steps
        )

    data_window = next(
        trajectory
        for trajectory in trajectories
        if trajectory.expected_fail.issue == "#251"
    )
    assert "retail" in data_window.tags
    assert "effective_window:" in data_window.expected_fail.allowed_failures

    orphan_reconciliation = next(
        trajectory
        for trajectory in trajectories
        if trajectory.expected_fail.issue == "#240"
    )
    assert orphan_reconciliation.steps[0].request == {
        "message": "Backtest holding MSFT for the past year."
    }
    assert (
        orphan_reconciliation.steps[0].expectation.artifact_identity
        == "alpha_session_07:confirmation:1"
    )
    assert orphan_reconciliation.steps[1].request == {
        "message": "Change the active test to the last six months."
    }

    assert (
        re.search(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
            raw,
        )
        is None
    )
    assert re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", raw) is None
    assert not any(
        forbidden_key in raw
        for forbidden_key in (
            "raw_conversation_id",
            "source_conversation_id",
            "provider_secret",
            "api_key",
            "access_token",
        )
    )


def test_expected_fail_prefixes_are_emitted_by_the_trajectory_contract() -> None:
    direct_expectation_prefixes = {
        "visible_response_category": "visible_response:",
        "stage_outcome": "stage_outcome:",
        "artifact_identity": "artifact_identity:",
        "action_identity": "action_identity:",
        "persistence_state": "persistence:",
        "reload_state": "reload:",
        "recovery_code": "recovery:",
        "typed_terminal": "terminal:",
    }

    for trajectory in load_alpha_trajectories():
        supported = {"stale_action:", "orphan_turn:", "fingerprint:"}
        for step in trajectory.steps:
            expectation = step.expectation
            for field_name, prefix in direct_expectation_prefixes.items():
                if getattr(expectation, field_name) is not None:
                    supported.add(prefix)
            if expectation.canonical_sse:
                supported.add("sse:")
            if expectation.route_budget is not None:
                supported.update({"budget.calls:", "budget.cost:", "budget.latency:"})
            supported.update(
                f"{checkpoint.split('.', 1)[0]}:"
                for checkpoint in expectation.checkpoints
            )

        assert set(trajectory.expected_fail.allowed_failures).issubset(supported), (
            trajectory.label,
            set(trajectory.expected_fail.allowed_failures) - supported,
        )


def test_trajectory_runner_dispatches_every_step_through_typed_adapters() -> None:
    trajectories = load_alpha_trajectories()
    calls: list[tuple[str, str]] = []
    adapters = _recording_adapters(calls)

    results = [
        run_alpha_trajectory(trajectory=trajectory, adapters=adapters)
        for trajectory in trajectories
    ]

    assert calls == [
        (step.operation, step.step_id)
        for trajectory in trajectories
        for step in trajectory.steps
    ]
    assert all(
        len(result.step_results) == len(trajectory.steps)
        for result, trajectory in zip(results, trajectories, strict=True)
    )
    assert {result.status for result in results} == {"unexpected_pass"}
    assert all(result.failed_checks == () for result in results)


def test_expected_fail_allows_only_its_exact_failure_prefixes() -> None:
    trajectory = next(
        item for item in load_alpha_trajectories() if item.expected_fail.issue == "#251"
    )
    first_step = trajectory.steps[0]
    matching = _matching_observation(first_step)
    allowed_failure = replace(
        matching,
        checkpoints={
            **matching.checkpoints,
            "effective_window.visible_before_approval": False,
        },
    )

    expected_failed = run_alpha_trajectory(
        trajectory=trajectory,
        adapters=_recording_adapters(
            [],
            overrides={first_step.step_id: allowed_failure},
        ),
    )
    assert expected_failed.status == "expected_failed"
    assert expected_failed.failed_checks[0].startswith("effective_window:")

    unrelated_failure = replace(allowed_failure, stage_outcome="needs_clarification")
    failed = run_alpha_trajectory(
        trajectory=trajectory,
        adapters=_recording_adapters(
            [],
            overrides={first_step.step_id: unrelated_failure},
        ),
    )
    assert failed.status == "failed"
    assert any(check.startswith("stage_outcome:") for check in failed.failed_checks)


def test_runner_enforces_sse_budget_and_session_terminal_invariants() -> None:
    trajectories = load_alpha_trajectories()

    budget_trajectory = next(
        item for item in trajectories if item.expected_fail.issue == "#239"
    )
    budget_step = budget_trajectory.steps[0]
    budget_observation = replace(
        _matching_observation(budget_step),
        route_receipts=tuple(
            {"task": f"call-{index}", "latency_ms": 100, "usage_cost_usd": 0.001}
            for index in range(2)
        ),
    )
    budget_result = run_alpha_trajectory(
        trajectory=budget_trajectory,
        adapters=_recording_adapters(
            [], overrides={budget_step.step_id: budget_observation}
        ),
    )
    assert budget_result.status == "expected_failed"
    assert any(check.startswith("budget.calls:") for check in budget_result.failed_checks)

    stale_trajectory = next(
        item for item in trajectories if item.expected_fail.issue == "#238"
    )
    stale_step = stale_trajectory.steps[2]
    stale_observation = replace(
        _matching_observation(stale_step),
        stale_action_executions=1,
    )
    stale_result = run_alpha_trajectory(
        trajectory=stale_trajectory,
        adapters=_recording_adapters(
            [], overrides={stale_step.step_id: stale_observation}
        ),
    )
    assert stale_result.status == "expected_failed"
    assert any(check.startswith("stale_action:") for check in stale_result.failed_checks)

    orphan_trajectory = next(
        item for item in trajectories if item.expected_fail.issue == "#240"
    )
    orphan_step = orphan_trajectory.steps[3]
    orphan_observation = replace(
        _matching_observation(orphan_step),
        accepted_orphan_turns_after_window=1,
    )
    orphan_result = run_alpha_trajectory(
        trajectory=orphan_trajectory,
        adapters=_recording_adapters(
            [], overrides={orphan_step.step_id: orphan_observation}
        ),
    )
    assert orphan_result.status == "expected_failed"
    assert any(check.startswith("orphan_turn:") for check in orphan_result.failed_checks)

    sse_trajectory = next(
        item for item in trajectories if item.expected_fail.issue == "#251"
    )
    sse_step = sse_trajectory.steps[0]
    invalid_sse = replace(
        _matching_observation(sse_step),
        raw_sse='event: final\ndata: {"type":"final","payload":{}}',
    )
    sse_result = run_alpha_trajectory(
        trajectory=sse_trajectory,
        adapters=_recording_adapters([], overrides={sse_step.step_id: invalid_sse}),
    )
    assert sse_result.status == "failed"
    assert any(check.startswith("sse:") for check in sse_result.failed_checks)


def test_canonical_sse_requires_framed_stage_sequence() -> None:
    trajectory = next(
        item for item in load_alpha_trajectories() if item.expected_fail.issue == "#251"
    )
    step = trajectory.steps[0]
    matching = _matching_observation(step)

    invalid_streams = (
        # A terminal plus [DONE] is not the canonical stage lifecycle.
        'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}\n\ndata: [DONE]',
        # SSE events must be separated by a blank line.
        "\n".join(
            (
                'data: {"type":"stage_start","stage":"interpret"}',
                'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
                'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
                "data: [DONE]",
            )
        ),
        # Canonical stages cannot complete before they start.
        "\n\n".join(
            (
                'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
                'data: {"type":"stage_start","stage":"interpret"}',
                'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
                "data: [DONE]",
            )
        ),
        # A canonical stream needs exactly one typed terminal.
        "\n\n".join(
            (
                'data: {"type":"stage_start","stage":"interpret"}',
                'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
                "data: [DONE]",
            )
        ),
        "\n\n".join(
            (
                'data: {"type":"stage_start","stage":"interpret"}',
                'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
                'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
                'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
                "data: [DONE]",
            )
        ),
        # No data event may follow the typed terminal.
        "\n\n".join(
            (
                'data: {"type":"stage_start","stage":"interpret"}',
                'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
                'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
                'data: {"type":"token","content":"late"}',
                "data: [DONE]",
            )
        ),
    )

    for raw_sse in invalid_streams:
        result = run_alpha_trajectory(
            trajectory=trajectory,
            adapters=_recording_adapters(
                [],
                overrides={step.step_id: replace(matching, raw_sse=raw_sse)},
            ),
        )

        assert result.status == "failed"
        assert any(check.startswith("sse:") for check in result.failed_checks)

    valid_stream = "\n\n".join(
        (
            ": keepalive",
            "retry: 3000",
            'data: {"type":"stage_start","stage":"interpret"}',
            'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
            'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
            "data: [DONE]",
        )
    )
    valid_result = run_alpha_trajectory(
        trajectory=trajectory,
        adapters=_recording_adapters(
            [],
            overrides={step.step_id: replace(matching, raw_sse=valid_stream)},
        ),
    )

    assert not any(check.startswith("sse:") for check in valid_result.failed_checks)

    valid_error_stream = "\n\n".join(
        (
            'data: {"type":"error","code":"agent_runtime_failure","message":"Saved for retry."}',
            "data: [DONE]",
        )
    )
    valid_error_result = run_alpha_trajectory(
        trajectory=trajectory,
        adapters=_recording_adapters(
            [],
            overrides={step.step_id: replace(matching, raw_sse=valid_error_stream)},
        ),
    )

    assert not any(check.startswith("sse:") for check in valid_error_result.failed_checks)


def test_canonical_sse_rejects_invalid_event_schemas_and_unknown_types() -> None:
    trajectory = next(
        item for item in load_alpha_trajectories() if item.expected_fail.issue == "#251"
    )
    step = trajectory.steps[0]
    matching = _matching_observation(step)
    invalid_events = (
        (
            'data: {"type":"stage_start"}',
            'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
            'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
        ),
        (
            'data: {"type":"stage_start","stage":"interpret"}',
            'data: {"type":"stage_outcome"}',
            'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
        ),
        (
            'data: {"type":"stage_start","stage":"interpret"}',
            'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
            'data: {"type":"final","payload":{}}',
        ),
        (
            'data: {"type":"stage_start","stage":"interpret"}',
            'data: {"type":"bogus"}',
            'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
            'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
        ),
        (
            'data: {"type":"stage_start","stage":"bogus"}',
            'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
            'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
        ),
        (
            'data: {"type":"stage_start","stage":"interpret"}',
            'data: {"type":"stage_outcome","outcome":"bogus"}',
            'data: {"type":"final","payload":{"stage_outcome":"ready_for_confirmation"}}',
        ),
        (
            'data: {"type":"stage_start","stage":"interpret"}',
            'data: {"type":"stage_outcome","outcome":"ready_for_confirmation"}',
            'data: {"type":"final","payload":{"stage_outcome":"bogus"}}',
        ),
    )

    for event_frames in invalid_events:
        raw_sse = "\n\n".join((*event_frames, "data: [DONE]"))
        result = run_alpha_trajectory(
            trajectory=trajectory,
            adapters=_recording_adapters(
                [],
                overrides={step.step_id: replace(matching, raw_sse=raw_sse)},
            ),
        )

        assert result.status == "failed"
        assert any(check.startswith("sse:") for check in result.failed_checks)


def test_route_budget_rejects_missing_or_invalid_measurements() -> None:
    trajectory = next(
        item for item in load_alpha_trajectories() if item.expected_fail.issue == "#251"
    )
    step = trajectory.steps[0]
    malformed = replace(
        _matching_observation(step),
        route_receipts=(
            {
                "task": "interpretation",
                "latency_ms": float("nan"),
            },
        ),
    )

    result = run_alpha_trajectory(
        trajectory=trajectory,
        adapters=_recording_adapters([], overrides={step.step_id: malformed}),
    )

    assert result.status == "failed"
    prefixes = {check.split(":", 1)[0] for check in result.failed_checks}
    assert "budget.cost" in prefixes
    assert "budget.latency" in prefixes

    missing_result = run_alpha_trajectory(
        trajectory=trajectory,
        adapters=_recording_adapters(
            [],
            overrides={
                step.step_id: replace(_matching_observation(step), route_receipts=())
            },
        ),
    )

    assert missing_result.status == "failed"
    assert any(
        check.startswith("budget.calls:") for check in missing_result.failed_checks
    )


def test_trajectory_scorecard_is_privacy_safe_and_marks_unexpected_passes(
    tmp_path: Path,
) -> None:
    trajectories = load_alpha_trajectories()
    results = [
        run_alpha_trajectory(
            trajectory=trajectory,
            adapters=_recording_adapters([]),
        )
        for trajectory in trajectories
    ]

    scorecard = trajectory_scorecard_for_results(results)
    path = write_trajectory_scorecard(results, output_dir=tmp_path)
    stored = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(stored, sort_keys=True)

    assert stored == scorecard | {"generated_at": stored["generated_at"]}
    assert stored["totals"] == {
        "passed": 0,
        "failed": 0,
        "expected_failed": 0,
        "unexpected_pass": 7,
    }
    assert {result["label"] for result in stored["results"]} == EXPECTED_ALPHA_LABELS
    assert all(
        set(result)
        == {
            "label",
            "locale",
            "status",
            "expected_fail_issue",
            "allowed_failure_prefixes",
            "failure_prefixes",
            "steps",
        }
        for result in stored["results"]
    )
    assert all(
        set(step) == {"step_id", "operation", "failure_prefixes"}
        for result in stored["results"]
        for step in result["steps"]
    )
    for trajectory in trajectories:
        for step in trajectory.steps:
            assert all(str(value) not in serialized for value in step.request.values())
    assert "raw_sse" not in serialized
    assert "route_receipts" not in serialized
