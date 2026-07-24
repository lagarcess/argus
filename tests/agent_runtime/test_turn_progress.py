from __future__ import annotations

from copy import deepcopy

from argus.agent_runtime.state.models import (
    ArtifactReference,
    ResponseIntent,
    RunState,
    StrategySummary,
    TaskSnapshot,
)
from argus.agent_runtime.turn_progress import (
    ProgressAssessment,
    ProgressSnapshot,
    assess_progress,
    semantic_progress_fingerprint,
    semantic_progress_snapshot,
)


def _strategy() -> StrategySummary:
    return StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2022-01-01", "end": "2025-01-01"},
        capital_amount=10_000,
    )


def production_shaped_checkpoint() -> dict[str, object]:
    strategy = _strategy()
    intent = ResponseIntent(
        kind="clarification",
        semantic_needs=["period"],
        requested_fields=["date_range"],
    )
    return {
        "stage_outcome": "await_user_reply",
        "run_state": RunState(
            current_user_message="test AAPL",
            candidate_strategy_draft=strategy,
            missing_required_fields=["date_range"],
            response_intent=intent,
        ),
        "latest_task_snapshot": TaskSnapshot(
            pending_strategy_summary=strategy,
            pending_needs=["period"],
            active_draft_reference=ArtifactReference(
                artifact_kind="draft",
                artifact_id="draft-1",
                artifact_status="active",
            ),
        ),
    }


def equivalent_public_payload() -> dict[str, object]:
    strategy = _strategy()
    return {
        "stage_outcome": "await_user_reply",
        "pending_strategy": {
            "strategy": strategy.model_dump(mode="python"),
            "missing_required_fields": ["date_range"],
        },
        "response_intent": {
            "kind": "clarification",
            "semantic_needs": ["period"],
            "requested_fields": ["date_range"],
        },
        "artifact_references": [
            {
                "artifact_kind": "draft",
                "artifact_id": "draft-1",
                "artifact_status": "active",
                "metadata": {},
            }
        ],
    }


def semantic_state(
    *,
    pending_needs: list[str] | None = None,
    artifact_id: str = "draft-1",
    assistant_response: str | None = None,
    evidence_spans: list[dict[str, str]] | None = None,
    language: str | None = None,
) -> dict[str, object]:
    payload = equivalent_public_payload()
    intent = dict(payload["response_intent"])
    intent["semantic_needs"] = list(pending_needs or ["period"])
    payload["response_intent"] = intent
    payload["artifact_references"] = [
        {
            "artifact_kind": "draft",
            "artifact_id": artifact_id,
            "artifact_status": "active",
            "metadata": {},
        }
    ]
    payload["assistant_response"] = assistant_response
    payload["evidence_spans"] = list(evidence_spans or [])
    payload["language"] = language
    return payload


def test_model_and_public_dict_normalize_to_same_snapshot() -> None:
    checkpoint = production_shaped_checkpoint()
    public = equivalent_public_payload()
    checkpoint_snapshot = semantic_progress_snapshot(checkpoint)

    assert isinstance(checkpoint_snapshot, ProgressSnapshot)
    assert checkpoint_snapshot == semantic_progress_snapshot(public)


def test_prose_and_provenance_do_not_change_fingerprint() -> None:
    left = semantic_state(
        assistant_response="Test AAPL.",
        evidence_spans=[{"text": "AAPL"}],
        language="en",
    )
    right = semantic_state(
        assistant_response="Probemos AAPL.",
        evidence_spans=[{"text": "Apple"}],
        language="es-419",
    )

    assert semantic_progress_fingerprint(left) == semantic_progress_fingerprint(right)


def test_pending_need_and_artifact_identity_are_material() -> None:
    period = semantic_state(pending_needs=["period"], artifact_id="draft-1")
    asset = semantic_state(pending_needs=["asset_target"], artifact_id="draft-1")
    replacement = semantic_state(pending_needs=["period"], artifact_id="draft-2")

    assert semantic_progress_fingerprint(period) != semantic_progress_fingerprint(asset)
    assert semantic_progress_fingerprint(period) != semantic_progress_fingerprint(
        replacement
    )


def test_equivalent_state_with_actionable_terminal_is_no_progress() -> None:
    snapshot = semantic_progress_snapshot(semantic_state(pending_needs=["period"]))

    assert assess_progress(snapshot, snapshot, terminal="no_progress") == (
        ProgressAssessment(outcome="no_progress", changed_fields=())
    )


def test_nonmaterial_unknown_and_diagnostic_fields_are_ignored() -> None:
    left = semantic_state()
    right = deepcopy(left)
    strategy = dict(right["pending_strategy"]["strategy"])
    strategy["extra_parameters"] = {
        "unknown": "diagnostic",
        "date_range_raw_text": "desde enero",
        "provider": "internal-provider",
        "created_at": "2026-07-23T10:00:00Z",
    }
    right["pending_strategy"] = {
        **right["pending_strategy"],
        "strategy": strategy,
    }
    right["provider_context"] = {"provider": "internal-provider", "model": "model-1"}
    right["labels"] = {"status": "Listo"}
    right["created_at"] = "2026-07-23T10:00:00Z"
    right["artifact_references"][0]["metadata"] = {
        "label": "Borrador",
        "provider": "internal-provider",
        "updated_at": "2026-07-23T10:00:00Z",
    }

    assert semantic_progress_fingerprint(left) == semantic_progress_fingerprint(right)


def test_raw_date_wording_does_not_change_fingerprint() -> None:
    english = semantic_state()
    english["pending_strategy"]["strategy"]["date_range"] = "past year"
    spanish = deepcopy(english)
    spanish["pending_strategy"]["strategy"]["date_range"] = "el año pasado"

    assert semantic_progress_fingerprint(english) == (
        semantic_progress_fingerprint(spanish)
    )


def test_known_executable_fields_and_rule_spec_are_material() -> None:
    daily = semantic_state()
    hourly = deepcopy(daily)
    hourly_strategy = dict(hourly["pending_strategy"]["strategy"])
    hourly_strategy["timeframe"] = "1h"
    hourly["pending_strategy"] = {
        **hourly["pending_strategy"],
        "strategy": hourly_strategy,
    }

    first_rule = deepcopy(daily)
    first_rule_strategy = dict(first_rule["pending_strategy"]["strategy"])
    first_rule_strategy["rule_spec"] = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi", "period": 14},
                    "operator": "below",
                    "right": {"kind": "constant", "value": 30},
                }
            ]
        }
    }
    first_rule["pending_strategy"] = {
        **first_rule["pending_strategy"],
        "strategy": first_rule_strategy,
    }
    second_rule = deepcopy(first_rule)
    second_rule["pending_strategy"]["strategy"]["rule_spec"]["entry"]["conditions"][0][
        "right"
    ]["value"] = 25

    assert semantic_progress_fingerprint(daily) != semantic_progress_fingerprint(hourly)
    assert semantic_progress_fingerprint(first_rule) != semantic_progress_fingerprint(
        second_rule
    )


def test_confirmation_job_and_result_identity_and_status_are_material() -> None:
    queued = semantic_state()
    queued["confirmation_payload"] = {
        "confirmation_id": "confirmation-1",
        "validation": {"status": "ready_to_run"},
    }
    queued["backtest_job"] = {"id": "job-1", "status": "queued"}
    queued["result_run_id"] = "run-1"

    running = deepcopy(queued)
    running["backtest_job"]["status"] = "running"
    superseded = deepcopy(queued)
    superseded["confirmation_payload"]["validation"]["status"] = "superseded"
    replacement = deepcopy(queued)
    replacement["result_run_id"] = "run-2"

    assert semantic_progress_fingerprint(queued) != semantic_progress_fingerprint(running)
    assert semantic_progress_fingerprint(queued) != semantic_progress_fingerprint(
        superseded
    )
    assert semantic_progress_fingerprint(queued) != semantic_progress_fingerprint(
        replacement
    )


def test_typed_constraint_identity_is_material_but_raw_copy_is_not() -> None:
    unsupported = semantic_state()
    unsupported["optional_parameter_status"] = {
        "unsupported_constraints": [
            {
                "category": "unsupported_strategy_logic",
                "raw_value": "trailing stop",
                "explanation": "Not supported.",
            }
        ]
    }
    translated = deepcopy(unsupported)
    translated["optional_parameter_status"]["unsupported_constraints"][0].update(
        {
            "raw_value": "stop dinámico",
            "explanation": "No es compatible.",
        }
    )
    different_constraint = deepcopy(unsupported)
    different_constraint["optional_parameter_status"]["unsupported_constraints"][0][
        "category"
    ] = "unsupported_time_granularity"

    assert semantic_progress_fingerprint(unsupported) == (
        semantic_progress_fingerprint(translated)
    )
    assert semantic_progress_fingerprint(unsupported) != (
        semantic_progress_fingerprint(different_constraint)
    )


def test_artifact_reference_order_does_not_change_fingerprint() -> None:
    left = semantic_state()
    left["artifact_references"].append(
        {
            "artifact_kind": "confirmation",
            "artifact_id": "confirmation-1",
            "artifact_status": "active",
            "metadata": {},
        }
    )
    right = deepcopy(left)
    right["artifact_references"].reverse()

    assert semantic_progress_fingerprint(left) == semantic_progress_fingerprint(right)


def test_material_change_is_assessed_as_advanced() -> None:
    before = semantic_progress_snapshot(semantic_state(pending_needs=["period"]))
    after = semantic_progress_snapshot(semantic_state(pending_needs=["asset_target"]))

    assessment = assess_progress(before, after, terminal=None)

    assert assessment.outcome == "advanced"
    assert assessment.changed_fields
