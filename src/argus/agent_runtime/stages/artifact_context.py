from __future__ import annotations

from typing import Any

from argus.agent_runtime.artifacts.drafts import (
    draft_from_confirmation_payload,
    draft_from_result_metadata,
)
from argus.agent_runtime.artifacts.drafts import (
    draft_from_failed_launch_payload as canonical_failed_launch_draft,
)
from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.confirmation_facts import confirmation_display_facts
from argus.agent_runtime.recovery_messages import recovery_message
from argus.agent_runtime.stages.interpret_types import InterpretDecision
from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConfirmationPayload,
    RunState,
    StrategySummary,
    StructuredActionContext,
    TaskSnapshot,
)

RESULT_EXPLANATION_TARGET_INFERRED = "result_explanation_target_inferred"
RESULT_FOLLOWUP_TARGET_INFERRED = "result_followup_target_inferred"
RESULT_TARGET_INFERENCE_CODES = frozenset(
    {
        RESULT_EXPLANATION_TARGET_INFERRED,
        RESULT_FOLLOWUP_TARGET_INFERRED,
    }
)


def decision_targets_result_artifact(
    *,
    decision: InterpretDecision,
    snapshot: TaskSnapshot | None,
) -> bool:
    if snapshot is None or snapshot.latest_backtest_result_reference is None:
        return False
    if decision.artifact_target is not None:
        return decision.artifact_target == "latest_result"
    if decision.semantic_turn_act == "result_followup":
        return True
    return decision.intent == "results_explanation"


def decision_allows_result_artifact_patch(
    *,
    decision: InterpretDecision,
) -> bool:
    if decision.artifact_target != "latest_result":
        return False
    return not bool(set(decision.reason_codes) & RESULT_TARGET_INFERENCE_CODES)


def stale_confirmation_action_response(
    *,
    action: StructuredActionContext,
    snapshot: TaskSnapshot | None,
    language: str | None = None,
) -> str | None:
    reference = snapshot.active_confirmation_reference if snapshot is not None else None
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
        return recovery_message("confirmation_action_stale_card", language=language)
    clicked_hash = str(payload.get("launch_payload_hash") or "").strip()
    active_hash = str(reference.metadata.get("launch_payload_hash") or "").strip()
    if clicked_hash and active_hash and clicked_hash != active_hash:
        return recovery_message("confirmation_action_stale_payload", language=language)
    return None


# The one liveness vocabulary. "consumed" is stamped on the card row at run
# admission: pressing Run is a commitment, so a card whose run was admitted
# is no longer pending, whatever the job later does; a run that dies without
# a result restores the card to "active" through the same guarded writer.
_DEAD_CONFIRMATION_STATES = frozenset({"cancelled", "canceled", "superseded", "consumed"})
CONSUMED_CONFIRMATION_STATE = "consumed"
ACTIVE_CONFIRMATION_STATE = "active"


def _confirmation_state_is_dead(value: Any) -> bool:
    return str(value or "").strip().casefold() in _DEAD_CONFIRMATION_STATES


def confirmation_card_is_dead(metadata: dict[str, Any] | None) -> bool:
    """The liveness oracle, read from the card message's own row.

    Every reader that judges whether a pending confirmation is live derives
    from this function; no code path may re-implement the predicate. The
    card row is the single source of consumption truth: run admission
    stamps it, terminal-without-result restores it, and cancellation or
    supersession stamp their own states through the same guarded writer.
    """
    if not isinstance(metadata, dict):
        return False
    card = metadata.get("confirmation_card")
    if isinstance(card, dict) and _confirmation_state_is_dead(
        card.get("confirmation_state")
    ):
        return True
    reference = metadata.get("active_confirmation_reference")
    if isinstance(reference, dict) and _confirmation_state_is_dead(
        reference.get("artifact_status")
    ):
        return True
    return False


def _metadata_is_latest_result_fact_reply_marker(metadata: dict[str, Any]) -> bool:
    """Typed latest-result fact replies carry run continuity ids without
    superseding an active confirmation."""
    response_intent = metadata.get("response_intent")
    if not isinstance(response_intent, dict):
        return False
    if response_intent.get("kind") not in {"beginner_guidance", "unsupported_recovery"}:
        return False
    facts = response_intent.get("facts")
    return isinstance(facts, dict) and bool(
        facts.get("fact_key") or facts.get("requested_metric")
    )


def newer_message_supersedes_confirmation(metadata: dict[str, Any]) -> bool:
    """Whether a message NEWER than a card closes the confirmation surface.

    The compatibility half of the oracle: durable transcripts written before
    run admission stamped the card row carry consumption only as later
    result messages, and cancellations and clarifications append their own
    markers. New writers must stamp the card row; this clause exists so old
    transcripts and turn-based supersession read identically everywhere.
    """
    if metadata.get("result_card"):
        return True
    if metadata.get("result_run_id") and not _metadata_is_latest_result_fact_reply_marker(
        metadata
    ):
        return True
    action = metadata.get("chat_action")
    if isinstance(action, dict) and action.get("type") == "cancel_confirmation":
        return True
    pending_strategy = metadata.get("pending_strategy")
    if not isinstance(pending_strategy, dict):
        return False
    requested_field = pending_strategy.get("requested_field")
    stage_outcome = str(metadata.get("agent_runtime_stage_outcome") or "")
    return (
        isinstance(requested_field, str)
        and bool(requested_field.strip())
        and stage_outcome in {"await_user_reply", "needs_clarification"}
    )


class LivePendingConfirmation:
    """A pending confirmation a turn may honestly speak for.

    Existence is not liveness: a snapshot can carry a leftover draft whose
    card was cancelled or superseded, or an emptied draft beside a stale
    reference. Constructing this type is the only way recovery paths obtain
    pending confirmation state, so none can invite the user to a card that is
    not there. Argus never contradicts its own card.
    """

    __slots__ = ("pending", "reference")

    def __init__(self, pending: StrategySummary, reference: ArtifactReference) -> None:
        self.pending = pending
        self.reference = reference


def live_pending_confirmation(
    snapshot: TaskSnapshot | None,
) -> LivePendingConfirmation | None:
    if snapshot is None:
        return None
    pending = snapshot.pending_strategy_summary
    if pending is None or pending == StrategySummary():
        return None
    reference = snapshot.active_confirmation_reference
    if reference is None:
        return None
    if _reference_confirmation_is_dead(reference):
        return None
    return LivePendingConfirmation(pending=pending, reference=reference)


def _reference_confirmation_is_dead(reference: ArtifactReference) -> bool:
    if _confirmation_state_is_dead(reference.artifact_status):
        return True
    card = reference.metadata.get("confirmation_card")
    if isinstance(card, dict) and _confirmation_state_is_dead(
        card.get("confirmation_state")
    ):
        return True
    return False


def has_pending_confirmation_context(snapshot: TaskSnapshot | None) -> bool:
    """Whether a turn has live pending confirmation context to speak about."""
    return live_pending_confirmation(snapshot) is not None or bool(
        snapshot is not None
        and snapshot.active_confirmation_reference is None
        and snapshot.pending_strategy_summary is not None
        and snapshot.pending_strategy_summary != StrategySummary()
    )


def draft_assumptions_response(snapshot: TaskSnapshot | None) -> dict[str, Any] | None:
    """Project the same typed facts as the card; never read saved assumption prose."""
    if snapshot is None or not has_pending_confirmation_context(snapshot):
        return None
    reference = snapshot.active_confirmation_reference
    metadata = reference.metadata if reference is not None else {}
    strategy = snapshot.pending_strategy_summary or StrategySummary()
    payload = confirmation_payload_dict(metadata.get("confirmation_payload"))
    strategy_values = payload.get("strategy")
    if not isinstance(strategy_values, dict):
        strategy_values = strategy.model_dump(mode="json")
    display_facts = None
    card_asset_class = None
    for key in ("confirmation_card", "card", "presentation"):
        card = metadata.get(key)
        if isinstance(card, dict) and isinstance(card.get("display_facts"), dict):
            display_facts = dict(card["display_facts"])
            card_asset_class = card.get("asset_class")
            break
    if display_facts is None:
        optional_parameters = payload.get("optional_parameters")
        launch_payload = payload.get("launch_payload")
        display_facts = confirmation_display_facts(
            strategy=strategy_values,
            optional_parameters=optional_parameters
            if isinstance(optional_parameters, dict)
            else {},
            launch_payload=launch_payload if isinstance(launch_payload, dict) else {},
        )
    return {
        "kind": "artifact_assumptions",
        "facts": {
            "artifact_kind": "confirmation" if reference is not None else "current_idea",
            "asset_class": card_asset_class or strategy_values.get("asset_class"),
            "display_facts": display_facts,
        },
    }


def active_confirmation_effective_strategy(
    *,
    snapshot: TaskSnapshot,
    fallback: StrategySummary,
) -> StrategySummary:
    reference = snapshot.active_confirmation_reference
    if reference is None:
        return fallback.model_copy(deep=True)
    payload = confirmation_payload_dict(reference.metadata.get("confirmation_payload"))
    strategy_payload = payload.get("strategy")
    if isinstance(strategy_payload, dict):
        allowed_fields = set(StrategySummary.model_fields)
        strategy_values = {
            key: value for key, value in strategy_payload.items() if key in allowed_fields
        }
        try:
            strategy = StrategySummary.model_validate(strategy_values)
        except Exception:
            strategy = fallback.model_copy(deep=True)
    else:
        strategy = fallback.model_copy(deep=True)
    launch_payload = payload.get("launch_payload")
    if isinstance(launch_payload, dict):
        strategy = _strategy_with_launch_defaults(
            strategy=strategy,
            launch_payload=launch_payload,
        )
    return strategy


def _strategy_with_launch_defaults(
    *,
    strategy: StrategySummary,
    launch_payload: dict[str, Any],
) -> StrategySummary:
    updated = strategy.model_copy(deep=True)
    if launch_payload.get("strategy_type"):
        updated.strategy_type = str(launch_payload["strategy_type"])
    symbols = launch_payload.get("symbols")
    if isinstance(symbols, list) and symbols:
        updated.asset_universe = [str(symbol).strip().upper() for symbol in symbols]
    elif launch_payload.get("symbol"):
        updated.asset_universe = [str(launch_payload["symbol"]).strip().upper()]
    for field_name in (
        "timeframe",
        "date_range",
        "sizing_mode",
        "capital_amount",
        "position_size",
        "cadence",
        "entry_rule",
        "exit_rule",
        "rule_spec",
    ):
        value = launch_payload.get(field_name)
        if value not in (None, "", [], {}):
            setattr(updated, field_name, value)
    benchmark_symbol = launch_payload.get("benchmark_symbol")
    if benchmark_symbol and not updated.comparison_baseline:
        updated.comparison_baseline = str(benchmark_symbol).strip().upper()
    return updated


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
    launch_payload = payload.get("launch_payload")
    if not isinstance(launch_payload, dict) or not isinstance(
        launch_payload.get("coverage_preflight"),
        dict,
    ):
        return None
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
    if not _launch_payload_matches_visible_strategy(payload, visible_strategy):
        return False
    if launch_binding_values_match(
        left=payload_strategy,
        right=visible_strategy,
    ):
        return True
    try:
        effective_payload_strategy = draft_from_confirmation_payload(payload)
    except Exception:
        return False
    return launch_binding_values_match(
        left=effective_payload_strategy.model_dump(mode="python"),
        right=visible_strategy,
    )


def _launch_payload_matches_visible_strategy(
    payload: dict[str, Any],
    visible_strategy: dict[str, Any],
) -> bool:
    validation_payload = dict(payload)
    validation_payload["strategy"] = visible_strategy
    return validate_confirmation_execution_payload(validation_payload).executable


def launch_binding_values_match(
    *,
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
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
        "comparison_baseline",
    }
    for field in fields_that_bind_launch_truth:
        if normalized_launch_binding_value(left.get(field)) != (
            normalized_launch_binding_value(right.get(field))
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
    if snapshot is not None and snapshot.latest_backtest_result_reference is not None:
        return strategy_from_result_reference(snapshot.latest_backtest_result_reference)
    if snapshot is not None and snapshot.confirmed_strategy_summary is not None:
        return snapshot.confirmed_strategy_summary.model_copy(deep=True)
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
    # A malformed reference must never break the anchor path.
    try:
        return draft_from_result_metadata(dict(reference.metadata))
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


def strategy_from_failed_launch_payload(payload: dict[str, Any]) -> StrategySummary:
    strategy = canonical_failed_launch_draft(payload)
    strategy.strategy_thesis = _retry_strategy_thesis(
        payload,
        strategy.asset_universe,
    )
    return strategy


def strategy_from_failed_action_snapshot(
    payload: dict[str, Any],
    snapshot: TaskSnapshot | None,
) -> StrategySummary:
    strategy = strategy_from_failed_launch_payload(payload)
    authoritative = snapshot.pending_strategy_summary if snapshot is not None else None
    if authoritative is None:
        return strategy
    authoritative_parameters = dict(authoritative.extra_parameters)
    modeled_cost_fields = [
        field_name
        for field_name in ("fee_rate", "slippage")
        if field_name in authoritative_parameters
    ]
    if not modeled_cost_fields:
        return strategy

    extra_parameters = dict(strategy.extra_parameters)
    field_provenance = dict(extra_parameters.get("field_provenance") or {})
    authoritative_provenance = dict(
        authoritative_parameters.get("field_provenance") or {}
    )
    for field_name in modeled_cost_fields:
        extra_parameters[field_name] = authoritative_parameters[field_name]
        if field_name in authoritative_provenance:
            field_provenance[field_name] = authoritative_provenance[field_name]
        else:
            field_provenance.pop(field_name, None)
    if field_provenance:
        extra_parameters["field_provenance"] = field_provenance
    else:
        extra_parameters.pop("field_provenance", None)
    return strategy.model_copy(
        update={"extra_parameters": extra_parameters},
        deep=True,
    )


def _retry_strategy_thesis(payload: dict[str, Any], symbols: list[str]) -> str:
    strategy_type = str(payload.get("strategy_type") or "strategy").replace("_", " ")
    asset_text = ", ".join(symbols) if symbols else "the selected asset"
    return f"Retry the previous {asset_text} {strategy_type} setup."


def failed_action_is_retryable(reference: ArtifactReference | None) -> bool:
    if reference is None or reference.artifact_kind != "failed_action":
        return False
    metadata = dict(reference.metadata)
    return metadata.get("retryable") is True
