from __future__ import annotations

from typing import Any

from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.stages.interpret_types import InterpretDecision
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConfirmationPayload,
    RunState,
    StrategySummary,
    StructuredActionContext,
    TaskSnapshot,
)


def decision_targets_result_artifact(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> bool:
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return False
    if decision.semantic_turn_act == "result_followup":
        return True
    return decision.intent == "results_explanation"


def stale_confirmation_action_response(
    *,
    action: StructuredActionContext,
    snapshot: TaskSnapshot | None,
) -> str | None:
    reference = (
        snapshot.active_confirmation_reference if snapshot is not None else None
    )
    if reference is None:
        return None
    payload = dict(action.payload or {})
    clicked_id = str(
        payload.get("artifact_id") or payload.get("confirmation_id") or ""
    ).strip()
    active_id = str(
        reference.metadata.get("confirmation_id") or reference.artifact_id
    ).strip()
    if clicked_id and active_id and clicked_id != active_id:
        return (
            "That confirmation was updated. Use the latest visible card and I will "
            "keep the current draft intact."
        )
    clicked_hash = str(payload.get("launch_payload_hash") or "").strip()
    active_hash = str(reference.metadata.get("launch_payload_hash") or "").strip()
    if clicked_hash and active_hash and clicked_hash != active_hash:
        return (
            "That confirmation payload is stale. Use the latest visible card and I "
            "will keep the current draft intact."
        )
    return None


def has_pending_confirmation_context(snapshot: TaskSnapshot | None) -> bool:
    return bool(
        snapshot is not None
        and (
            snapshot.active_confirmation_reference is not None
            or snapshot.pending_strategy_summary is not None
        )
    )


def draft_assumptions_response(snapshot: TaskSnapshot | None) -> str | None:
    if snapshot is None:
        return None
    assumptions = active_confirmation_assumptions(snapshot)
    if not assumptions and snapshot.pending_strategy_summary is not None:
        assumptions = list(snapshot.pending_strategy_summary.assumptions)
    if not assumptions and snapshot.pending_strategy_summary is not None:
        assumptions = inferred_strategy_assumptions(snapshot.pending_strategy_summary)
    if not assumptions:
        return None
    return "For the visible draft, I am using: " + "; ".join(assumptions) + "."


def active_confirmation_assumptions(snapshot: TaskSnapshot) -> list[str]:
    reference = snapshot.active_confirmation_reference
    if reference is None:
        return []
    metadata = dict(reference.metadata)
    for key in ("confirmation_card", "card", "presentation"):
        card = metadata.get(key)
        if isinstance(card, dict):
            assumptions = card.get("assumptions")
            if isinstance(assumptions, list):
                return [str(item) for item in assumptions if str(item).strip()]
    assumptions = metadata.get("assumptions")
    if isinstance(assumptions, list):
        return [str(item) for item in assumptions if str(item).strip()]
    return []


def inferred_strategy_assumptions(strategy: StrategySummary) -> list[str]:
    assumptions = ["Long-only", "Equal weight"]
    if strategy.comparison_baseline:
        assumptions.append(f"Benchmark: {strategy.comparison_baseline}")
    elif strategy.asset_class == "crypto":
        assumptions.append("Benchmark: BTC")
    elif strategy.asset_class == "equity":
        assumptions.append("Benchmark: SPY")
    if strategy.timeframe:
        assumptions.append(f"Timeframe: {strategy.timeframe}")
    return assumptions


def validated_approval_confirmation_payload_from_state(
    *,
    state: RunState,
    approved_strategy: StrategySummary,
) -> dict[str, Any] | None:
    payload = confirmation_payload_dict(state.confirmation_payload)
    return validated_approval_confirmation_payload(
        payload=payload,
        approved_strategy=approved_strategy,
    )


def validated_approval_confirmation_payload_from_snapshot(
    *,
    snapshot: TaskSnapshot | None,
    approved_strategy: StrategySummary,
) -> dict[str, Any] | None:
    if snapshot is None or snapshot.active_confirmation_reference is None:
        return None
    payload = confirmation_payload_dict(
        snapshot.active_confirmation_reference.metadata.get("confirmation_payload")
    )
    return validated_approval_confirmation_payload(
        payload=payload,
        approved_strategy=approved_strategy,
    )


def validated_approval_confirmation_payload(
    *,
    payload: dict[str, Any],
    approved_strategy: StrategySummary,
) -> dict[str, Any] | None:
    if not confirmation_payload_matches_visible_strategy(payload, approved_strategy):
        return None
    if not confirmation_payload_is_validated_executable(payload):
        return None
    return payload


def confirmation_payload_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, ConfirmationPayload):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return dict(value)
    return {}


def confirmation_payload_matches_visible_strategy(
    payload: dict[str, Any],
    strategy: StrategySummary,
) -> bool:
    payload_strategy = payload.get("strategy")
    if not isinstance(payload_strategy, dict):
        return False
    visible_strategy = strategy.model_dump(mode="python")
    fields_that_bind_launch_truth = {
        "strategy_type",
        "asset_universe",
        "asset_class",
        "date_range",
        "entry_logic",
        "exit_logic",
        "entry_rule",
        "exit_rule",
        "rule_spec",
        "cadence",
        "capital_amount",
    }
    for field in fields_that_bind_launch_truth:
        if normalized_launch_binding_value(payload_strategy.get(field)) != (
            normalized_launch_binding_value(visible_strategy.get(field))
        ):
            return False
    return True


def confirmation_payload_is_validated_executable(payload: dict[str, Any]) -> bool:
    validation = payload.get("validation")
    return (
        isinstance(validation, dict)
        and validation.get("executable") is True
        and validate_confirmation_execution_payload(payload).executable
    )


def normalized_launch_binding_value(value: Any) -> Any:
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    if isinstance(value, str):
        return value.strip()
    if value in (None, "", [], {}):
        return None
    return value


def strategy_from_result_action_snapshot(
    *,
    snapshot: TaskSnapshot | None,
) -> StrategySummary:
    if snapshot is not None and snapshot.confirmed_strategy_summary is not None:
        return snapshot.confirmed_strategy_summary.model_copy(deep=True)
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return strategy_from_result_reference(snapshot.latest_backtest_result_reference)
    return StrategySummary()


def latest_run_id_for_action(
    *,
    action_payload: dict[str, Any],
    reference: ArtifactReference,
) -> str:
    raw_run_id = action_payload.get("run_id") or action_payload.get("runId")
    if raw_run_id is not None:
        run_id = str(raw_run_id).strip()
        if run_id:
            return run_id
    return reference.artifact_id


def strategy_from_result_reference(reference: ArtifactReference) -> StrategySummary:
    metadata = dict(reference.metadata)
    config = metadata.get("config_snapshot")
    config_snapshot = dict(config) if isinstance(config, dict) else {}
    resolved_strategy = config_snapshot.get("resolved_strategy")
    payload = dict(resolved_strategy) if isinstance(resolved_strategy, dict) else {}
    resolved_parameters = config_snapshot.get("resolved_parameters")
    parameters = (
        dict(resolved_parameters) if isinstance(resolved_parameters, dict) else {}
    )

    if not payload.get("strategy_type") and config_snapshot.get("template"):
        payload["strategy_type"] = config_snapshot["template"]
    if not payload.get("asset_class") and metadata.get("asset_class"):
        payload["asset_class"] = metadata["asset_class"]
    if not payload.get("asset_universe"):
        symbols = payload.get("symbols") or config_snapshot.get("symbols")
        if isinstance(symbols, list):
            payload["asset_universe"] = [str(symbol) for symbol in symbols if symbol]
    if not payload.get("date_range"):
        payload["date_range"] = parameters.get("date_range") or config_snapshot.get(
            "date_range"
        )

    allowed_fields = set(StrategySummary.model_fields)
    strategy_payload = {
        key: value
        for key, value in payload.items()
        if key in allowed_fields and value not in (None, "", [], {})
    }
    try:
        return StrategySummary.model_validate(strategy_payload)
    except Exception:
        return StrategySummary()


def prior_stage_was_await_approval(metadata: dict[str, Any]) -> bool:
    return str(metadata.get("last_stage_outcome") or "") == "await_approval"


def semantic_need_for_action(action_type: str) -> str:
    mapping = {
        "change_asset": "asset_target",
        "change_dates": "period",
        "adjust_assumptions": "assumption",
    }
    return mapping[action_type]


def launch_payload_from_failed_action(
    reference: ArtifactReference | None,
) -> dict[str, Any] | None:
    if reference is None or reference.artifact_kind != "failed_action":
        return None
    metadata = dict(reference.metadata)
    if metadata.get("action_type") != "run_backtest":
        return None
    launch_payload = metadata.get("launch_payload")
    if not isinstance(launch_payload, dict) or not launch_payload:
        return None
    return dict(launch_payload)


def failed_action_is_retryable(reference: ArtifactReference | None) -> bool:
    if reference is None or reference.artifact_kind != "failed_action":
        return False
    retryable = dict(reference.metadata).get("retryable")
    return retryable is not False


def non_retryable_failed_action_response(reference: ArtifactReference | None) -> str:
    metadata = dict(reference.metadata) if reference is not None else {}
    message = metadata.get("user_safe_message") or metadata.get("error")
    if isinstance(message, str) and message.strip():
        return (
            f"I still have the failed setup, but rerunning the same payload will "
            f"hit the same blocker: {message.strip()} Adjust the rule, asset, or "
            "date range and I will keep the idea intact."
        )
    return (
        "I still have the failed setup, but rerunning the same payload will hit "
        "the same blocker. Adjust the rule, asset, or date range and I will keep "
        "the idea intact."
    )
