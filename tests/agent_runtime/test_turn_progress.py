from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from enum import Enum

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


def test_stage_outcome_only_change_is_not_semantic_progress() -> None:
    before_state = semantic_state()
    before_state["stage_outcome"] = "needs_clarification"
    after_state = deepcopy(before_state)
    after_state["stage_outcome"] = "await_user_reply"

    before = semantic_progress_snapshot(before_state)
    after = semantic_progress_snapshot(after_state)

    assert semantic_progress_fingerprint(before_state) == (
        semantic_progress_fingerprint(after_state)
    )
    assert assess_progress(before, after, terminal=None) == ProgressAssessment(
        outcome="no_progress",
        changed_fields=(),
    )


def test_explicit_terminals_win_when_semantic_state_is_unchanged() -> None:
    snapshot = semantic_progress_snapshot(semantic_state())

    for terminal in ("clarification", "redirected", "finished"):
        assessment = assess_progress(snapshot, snapshot, terminal=terminal)

        assert assessment.outcome == terminal
        assert assessment.changed_fields == ()


def test_confirmed_only_task_snapshot_model_and_dict_are_equivalent() -> None:
    task_snapshot = TaskSnapshot(confirmed_strategy_summary=_strategy())
    model_snapshot = semantic_progress_snapshot(task_snapshot)

    assert model_snapshot is not None
    assert model_snapshot.projection["strategy"]["asset_universe"] == ["AAPL"]
    assert model_snapshot == semantic_progress_snapshot(
        {
            "confirmed_strategy_summary": _strategy().model_dump(mode="python"),
        }
    )


def test_different_confirmed_strategies_have_different_fingerprints() -> None:
    aapl = TaskSnapshot(confirmed_strategy_summary=_strategy())
    msft_strategy = _strategy().model_copy(
        update={"asset_universe": ["MSFT"]},
    )
    msft = TaskSnapshot(confirmed_strategy_summary=msft_strategy)

    assert semantic_progress_fingerprint({"latest_task_snapshot": aapl}) != (
        semantic_progress_fingerprint({"latest_task_snapshot": msft})
    )


def test_empty_candidate_does_not_eclipse_confirmed_strategy() -> None:
    confirmed = TaskSnapshot(confirmed_strategy_summary=_strategy())
    confirmed_only = {"latest_task_snapshot": confirmed}
    blank_candidate = {
        "run_state": RunState(
            current_user_message="Explain the result",
            candidate_strategy_draft=StrategySummary(),
        ),
        "latest_task_snapshot": confirmed,
    }

    snapshot = semantic_progress_snapshot(blank_candidate)

    assert snapshot is not None
    assert snapshot.projection["strategy"]["asset_universe"] == ["AAPL"]
    assert snapshot == semantic_progress_snapshot(confirmed_only)


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
                    "right": 30,
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
    ] = 25

    assert semantic_progress_fingerprint(daily) != semantic_progress_fingerprint(hourly)
    assert semantic_progress_fingerprint(first_rule) != semantic_progress_fingerprint(
        second_rule
    )


def test_nested_rule_and_risk_presentation_fields_are_not_material() -> None:
    baseline = semantic_state()
    strategy = baseline["pending_strategy"]["strategy"]
    strategy["entry_rule"] = {
        "indicator": "rsi",
        "operator": "below",
        "threshold": 30,
        "period": 14,
    }
    strategy["rule_spec"] = {
        "entry": {
            "combinator": "all",
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi", "period": 14},
                    "operator": "lt",
                    "right": 30,
                }
            ],
        },
        "exit": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi", "period": 14},
                    "operator": "gt",
                    "right": 70,
                }
            ]
        },
    }
    strategy["risk_rules"] = [
        {"type": "stop_loss", "value_pct": 5.0, "mode": "close"}
    ]
    decorated = deepcopy(baseline)
    decorated_strategy = decorated["pending_strategy"]["strategy"]
    decorated_strategy["entry_rule"].update(
        {
            "explanation": "Buy when RSI is low.",
            "label": "Oversold entry",
            "unknown": "presentation-only",
        }
    )
    decorated_entry = decorated_strategy["rule_spec"]["entry"]
    decorated_entry["provider"] = "internal-provider"
    decorated_condition = decorated_entry["conditions"][0]
    decorated_condition["explanation"] = "Localized explanation"
    decorated_condition["left"]["timestamp"] = "2026-07-23T10:00:00Z"
    decorated_strategy["risk_rules"][0].update(
        {
            "label": "Five percent stop",
            "explanation": "Limit losses.",
            "provider": "internal-provider",
            "timestamp": "2026-07-23T10:00:00Z",
            "unknown": {"localized": "ignored"},
        }
    )

    assert semantic_progress_fingerprint(baseline) == (
        semantic_progress_fingerprint(decorated)
    )


def test_executable_rule_and_risk_leaves_are_material() -> None:
    baseline = semantic_state()
    strategy = baseline["pending_strategy"]["strategy"]
    strategy["entry_rule"] = {
        "indicator": "rsi",
        "operator": "below",
        "threshold": 30,
        "period": 14,
    }
    strategy["rule_spec"] = {
        "entry": {
            "conditions": [
                {
                    "left": {"kind": "indicator", "key": "rsi", "period": 14},
                    "operator": "lt",
                    "right": 30,
                }
            ]
        }
    }
    strategy["risk_rules"] = [
        {"type": "stop_loss", "value_pct": 5.0, "mode": "close"}
    ]

    operator_change = deepcopy(baseline)
    operator_change["pending_strategy"]["strategy"]["rule_spec"]["entry"][
        "conditions"
    ][0]["operator"] = "gt"
    indicator_change = deepcopy(baseline)
    indicator_change["pending_strategy"]["strategy"]["rule_spec"]["entry"][
        "conditions"
    ][0]["left"]["key"] = "sma"
    period_change = deepcopy(baseline)
    period_change["pending_strategy"]["strategy"]["rule_spec"]["entry"][
        "conditions"
    ][0]["left"]["period"] = 20
    threshold_change = deepcopy(baseline)
    threshold_change["pending_strategy"]["strategy"]["entry_rule"]["threshold"] = 25
    risk_change = deepcopy(baseline)
    risk_change["pending_strategy"]["strategy"]["risk_rules"][0]["value_pct"] = 8.0

    baseline_fingerprint = semantic_progress_fingerprint(baseline)
    for changed in (
        operator_change,
        indicator_change,
        period_change,
        threshold_change,
        risk_change,
    ):
        assert semantic_progress_fingerprint(changed) != baseline_fingerprint


def test_accepted_typed_rule_and_date_leaves_are_json_stable() -> None:
    class RuleOperator(Enum):
        BELOW = "below"

    typed = semantic_state()
    strategy = typed["pending_strategy"]["strategy"]
    strategy["date_range"] = {
        "start": date(2022, 1, 1),
        "end": datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc),
    }
    strategy["entry_rule"] = {
        "indicator": "rsi",
        "operator": RuleOperator.BELOW,
        "threshold": 30,
        "period": 14,
    }
    serialized = deepcopy(typed)
    serialized_strategy = serialized["pending_strategy"]["strategy"]
    serialized_strategy["date_range"] = {
        "start": "2022-01-01",
        "end": "2025-01-01T12:30:00Z",
    }
    serialized_strategy["entry_rule"]["operator"] = "below"
    typed_strategy = StrategySummary(
        strategy_type="indicator_threshold",
        asset_universe=["AAPL"],
        date_range={
            "start": date(2022, 1, 1),
            "end": datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc),
        },
        entry_rule=strategy["entry_rule"],
    )
    typed_task = TaskSnapshot(confirmed_strategy_summary=typed_strategy)

    typed_fingerprint = semantic_progress_fingerprint(typed)
    model_fingerprint = semantic_progress_fingerprint(typed_task)

    assert isinstance(typed_fingerprint, str)
    assert typed_fingerprint == semantic_progress_fingerprint(serialized)
    assert model_fingerprint == semantic_progress_fingerprint(
        typed_task.model_dump(mode="python")
    )
    assert model_fingerprint == semantic_progress_fingerprint(
        typed_task.model_dump(mode="json")
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
