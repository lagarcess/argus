from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel

ProgressOutcome = Literal[
    "advanced",
    "clarification",
    "redirected",
    "finished",
    "no_progress",
    "recoverable_failed",
    "terminal_failed",
]

_EXPLICIT_TERMINALS: frozenset[ProgressOutcome] = frozenset(
    {
        "clarification",
        "redirected",
        "finished",
        "no_progress",
        "recoverable_failed",
        "terminal_failed",
    }
)
_STRATEGY_SCALAR_FIELDS = (
    "requested_strategy_template",
    "strategy_type",
    "asset_class",
    "timeframe",
    "cadence",
    "sizing_mode",
    "capital_amount",
    "position_size",
    "comparison_baseline",
)
_SIGNAL_RULE_FIELDS = (
    "type",
    "indicator",
    "operator",
    "threshold",
    "period",
    "indicator_period",
    "direction",
    "fast_indicator",
    "fast_period",
    "slow_indicator",
    "slow_period",
    "signal_period",
    "fast",
    "slow",
    "signal",
    "cadence",
)
_RISK_RULE_FIELDS = (
    "type",
    "value_pct",
    "mode",
)
_SERIES_REF_FIELDS = (
    "kind",
    "key",
    "field",
    "output",
    "period",
)
_INDICATOR_PARAMETER_FIELDS = (
    "period",
    "fast",
    "slow",
    "signal",
    "length",
    "std",
    "indicator_period",
)
_TASK_ARTIFACT_FIELDS = (
    "active_draft_reference",
    "active_confirmation_reference",
    "latest_backtest_result_reference",
    "latest_collection_action_reference",
    "latest_failed_action_reference",
    "saved_strategy_reference",
)
_CONSTRAINT_IDENTITY_FIELDS = (
    "category",
    "constraint_id",
    "code",
    "reason_code",
    "status",
)
_ACTION_TARGET_FIELDS = (
    "confirmation_id",
    "run_id",
    "strategy_id",
    "failed_action_id",
    "conversation_id",
    "source_assistant_id",
    "option_id",
    "request_message_id",
)
_UNSUPPORTED_LEAF = object()


@dataclass(frozen=True)
class ProgressSnapshot:
    projection: dict[str, Any]


@dataclass(frozen=True)
class ProgressAssessment:
    outcome: ProgressOutcome
    changed_fields: tuple[str, ...]


def semantic_progress_snapshot(state: Any) -> ProgressSnapshot | None:
    """Project material typed state without treating prose or diagnostics as progress."""

    root = _as_mapping(state)
    if not root:
        return None

    run_state = _run_state(root)
    task_snapshot = _task_snapshot(root)
    response_intent = _first_mapping(
        root.get("response_intent"),
        run_state.get("response_intent"),
    )
    pending_strategy = _as_mapping(root.get("pending_strategy"))

    projection: dict[str, Any] = {}
    _set_string(projection, "response_intent_kind", response_intent.get("kind"))
    _set_string(
        projection,
        "semantic_turn_act",
        _first_value(root.get("semantic_turn_act"), run_state.get("semantic_turn_act")),
    )

    pending_needs = _sorted_strings(
        response_intent.get("semantic_needs"),
        task_snapshot.get("pending_needs"),
    )
    if pending_needs:
        projection["pending_needs"] = pending_needs

    requested_fields = _sorted_strings(
        response_intent.get("requested_fields"),
        root.get("missing_required_fields"),
        root.get("requested_field"),
        run_state.get("missing_required_fields"),
        run_state.get("requested_field"),
        pending_strategy.get("missing_required_fields"),
    )
    if requested_fields:
        projection["requested_fields"] = requested_fields

    strategy = _project_strategy(
        _working_strategy(
            root=root,
            run_state=run_state,
            task_snapshot=task_snapshot,
            pending_strategy=pending_strategy,
        )
    )
    if strategy:
        projection["strategy"] = strategy

    constraints = _constraint_identities(
        root=root,
        run_state=run_state,
        response_intent=response_intent,
    )
    if constraints:
        projection["constraints"] = constraints

    artifacts = _artifact_identities(root=root, task_snapshot=task_snapshot)
    if artifacts:
        projection["artifacts"] = artifacts

    confirmation = _confirmation_identity(root=root, run_state=run_state)
    if confirmation:
        projection["confirmation"] = confirmation

    job = _job_identity(root=root, run_state=run_state)
    if job:
        projection["job"] = job

    result_ids = _result_identities(root=root, run_state=run_state)
    if result_ids:
        projection["result_ids"] = result_ids

    action = _action_identity(root=root, run_state=run_state)
    if action:
        projection["action"] = action

    retry_target = _retry_target(root)
    if retry_target:
        projection["retry_target"] = retry_target

    return ProgressSnapshot(projection=projection) if projection else None


def semantic_progress_fingerprint(state: Any) -> str | None:
    snapshot = semantic_progress_snapshot(state)
    if snapshot is None:
        return None
    encoded = json.dumps(
        snapshot.projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assess_progress(
    before: ProgressSnapshot | None,
    after: ProgressSnapshot | None,
    terminal: ProgressOutcome | None,
) -> ProgressAssessment:
    before_projection = before.projection if before is not None else {}
    after_projection = after.projection if after is not None else {}
    changed_fields = tuple(
        sorted(
            key
            for key in before_projection.keys() | after_projection.keys()
            if before_projection.get(key) != after_projection.get(key)
        )
    )
    if terminal in _EXPLICIT_TERMINALS:
        return ProgressAssessment(outcome=terminal, changed_fields=changed_fields)
    if changed_fields:
        return ProgressAssessment(outcome="advanced", changed_fields=changed_fields)
    return ProgressAssessment(outcome="no_progress", changed_fields=())


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return value
    return {}


def _run_state(root: dict[str, Any]) -> dict[str, Any]:
    nested = _as_mapping(root.get("run_state"))
    if nested:
        return nested
    if "candidate_strategy_draft" in root or "current_user_message" in root:
        return root
    return {}


def _task_snapshot(root: dict[str, Any]) -> dict[str, Any]:
    nested = _as_mapping(root.get("latest_task_snapshot"))
    if nested:
        return nested
    if (
        "pending_strategy_summary" in root
        or "confirmed_strategy_summary" in root
        or any(field in root for field in _TASK_ARTIFACT_FIELDS)
    ):
        return root
    return {}


def _first_mapping(*values: Any) -> dict[str, Any]:
    for value in values:
        mapping = _as_mapping(value)
        if mapping:
            return mapping
    return {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if _has_value(value):
            return value
    return None


def _clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _set_string(target: dict[str, Any], key: str, value: Any) -> None:
    cleaned = _clean_string(value)
    if cleaned is not None:
        target[key] = cleaned


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _sorted_strings(*values: Any) -> list[str]:
    normalized: set[str] = set()
    for value in values:
        candidates = (
            value if isinstance(value, list | tuple | set | frozenset) else [value]
        )
        for candidate in candidates:
            cleaned = _clean_string(candidate)
            if cleaned is not None:
                normalized.add(cleaned)
    return sorted(normalized)


def _working_strategy(
    *,
    root: dict[str, Any],
    run_state: dict[str, Any],
    task_snapshot: dict[str, Any],
    pending_strategy: dict[str, Any],
) -> dict[str, Any]:
    confirmation_payload = _first_mapping(
        root.get("confirmation_payload"),
        run_state.get("confirmation_payload"),
    )
    candidates = (
        pending_strategy.get("strategy"),
        pending_strategy if "strategy_type" in pending_strategy else None,
        run_state.get("candidate_strategy_draft"),
        root.get("candidate_strategy_draft"),
        task_snapshot.get("pending_strategy_summary"),
        task_snapshot.get("confirmed_strategy_summary"),
        confirmation_payload.get("strategy"),
    )
    for candidate in candidates:
        strategy = _as_mapping(candidate)
        if strategy and _project_strategy(strategy):
            return strategy
    return {}


def _project_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for field in _STRATEGY_SCALAR_FIELDS:
        _set_leaf(projected, field, strategy.get(field))

    symbols = _sorted_strings(strategy.get("asset_universe"))
    if symbols:
        projected["asset_universe"] = symbols

    date_range = _as_mapping(strategy.get("date_range"))
    canonical_date_range: dict[str, Any] = {}
    for key in ("start", "end"):
        _set_leaf(canonical_date_range, key, date_range.get(key))
    if canonical_date_range:
        projected["date_range"] = canonical_date_range

    risk_rules = _project_risk_rules(strategy.get("risk_rules"))
    if risk_rules:
        projected["risk_rules"] = risk_rules

    for field in ("entry_rule", "exit_rule"):
        rule = _project_signal_rule(strategy.get(field))
        if rule:
            projected[field] = rule
    rule_spec = _project_rule_spec(strategy.get("rule_spec"))
    if rule_spec:
        projected["rule_spec"] = rule_spec
    return projected


def _set_leaf(target: dict[str, Any], key: str, value: Any) -> None:
    normalized = _accepted_leaf(value)
    if normalized is _UNSUPPORTED_LEAF:
        return
    if isinstance(normalized, str):
        normalized = _clean_string(normalized)
    if _has_value(normalized):
        target[key] = normalized


def _accepted_leaf(value: Any) -> Any:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, datetime):
        normalized = value.isoformat()
        return f"{normalized[:-6]}Z" if normalized.endswith("+00:00") else normalized
    if isinstance(value, date):
        return value.isoformat()
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return _UNSUPPORTED_LEAF


def _project_leaf_fields(
    value: Any,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    source = _as_mapping(value)
    projected: dict[str, Any] = {}
    for field in fields:
        _set_leaf(projected, field, source.get(field))
    return projected


def _project_signal_rule(value: Any) -> dict[str, Any]:
    return _project_leaf_fields(value, _SIGNAL_RULE_FIELDS)


def _project_risk_rules(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    projected = [
        rule for item in value if (rule := _project_leaf_fields(item, _RISK_RULE_FIELDS))
    ]
    return projected


def _project_rule_spec(value: Any) -> dict[str, Any]:
    source = _as_mapping(value)
    projected: dict[str, Any] = {}
    for side in ("entry", "exit"):
        group = _project_condition_group(source.get(side))
        if group:
            projected[side] = group
    return projected


def _project_condition_group(value: Any) -> dict[str, Any]:
    source = _as_mapping(value)
    projected: dict[str, Any] = {}
    _set_leaf(projected, "combinator", source.get("combinator"))
    raw_conditions = source.get("conditions")
    if isinstance(raw_conditions, list | tuple):
        conditions = [
            condition
            for item in raw_conditions
            if (condition := _project_condition(item))
        ]
        if conditions:
            projected["conditions"] = conditions
    return projected


def _project_condition(value: Any) -> dict[str, Any]:
    source = _as_mapping(value)
    projected: dict[str, Any] = {}
    left = _project_operand(source.get("left"))
    if left is not _UNSUPPORTED_LEAF:
        projected["left"] = left
    _set_leaf(projected, "operator", source.get("operator"))
    right = _project_operand(source.get("right"))
    if right is not _UNSUPPORTED_LEAF:
        projected["right"] = right
    return projected


def _project_operand(value: Any) -> Any:
    source = _as_mapping(value)
    if not source:
        normalized = _accepted_leaf(value)
        return normalized if _has_value(normalized) else _UNSUPPORTED_LEAF

    projected = _project_leaf_fields(source, _SERIES_REF_FIELDS)
    parameters = _project_leaf_fields(
        source.get("parameters"),
        _INDICATOR_PARAMETER_FIELDS,
    )
    if parameters:
        projected["parameters"] = parameters
    return projected or _UNSUPPORTED_LEAF


def _constraint_identities(
    *,
    root: dict[str, Any],
    run_state: dict[str, Any],
    response_intent: dict[str, Any],
) -> list[dict[str, str]]:
    facts = _as_mapping(response_intent.get("facts"))
    status_sources = (
        _as_mapping(root.get("optional_parameter_status")),
        _as_mapping(run_state.get("optional_parameter_status")),
        facts,
    )
    identities: dict[str, dict[str, str]] = {}
    for source in status_sources:
        for collection_name in ("supported_constraints", "unsupported_constraints"):
            raw_constraints = source.get(collection_name)
            if not isinstance(raw_constraints, list | tuple):
                continue
            for raw_constraint in raw_constraints:
                identity = _constraint_identity(raw_constraint)
                if identity:
                    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"))
                    identities[encoded] = identity
    return [identities[key] for key in sorted(identities)]


def _constraint_identity(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        cleaned = _clean_string(value)
        return {"category": cleaned} if cleaned is not None else {}
    mapping = _as_mapping(value)
    identity: dict[str, str] = {}
    for field in _CONSTRAINT_IDENTITY_FIELDS:
        _set_string(identity, field, mapping.get(field))
    return identity


def _artifact_identities(
    *,
    root: dict[str, Any],
    task_snapshot: dict[str, Any],
) -> list[dict[str, str]]:
    raw_references: list[Any] = []
    for source in (root, task_snapshot):
        references = source.get("artifact_references")
        if isinstance(references, list | tuple):
            raw_references.extend(references)
    for field in _TASK_ARTIFACT_FIELDS:
        raw_references.append(task_snapshot.get(field))
    raw_references.append(root.get("latest_failed_action_reference"))

    identities: dict[tuple[str, str, str], dict[str, str]] = {}
    for value in raw_references:
        reference = _as_mapping(value)
        kind = _clean_string(reference.get("artifact_kind"))
        artifact_id = _clean_string(reference.get("artifact_id"))
        if kind is None or artifact_id is None:
            continue
        status = _clean_string(reference.get("artifact_status"))
        identity = {"artifact_kind": kind, "artifact_id": artifact_id}
        if status is not None:
            identity["artifact_status"] = status
        identities[(kind, artifact_id, status or "")] = identity
    return [identities[key] for key in sorted(identities)]


def _confirmation_identity(
    *,
    root: dict[str, Any],
    run_state: dict[str, Any],
) -> dict[str, str]:
    payload = _first_mapping(
        root.get("confirmation_payload"),
        run_state.get("confirmation_payload"),
    )
    if not payload:
        return {}
    validation = _as_mapping(payload.get("validation"))
    identity: dict[str, str] = {}
    _set_string(
        identity,
        "id",
        _first_value(payload.get("confirmation_id"), payload.get("artifact_id")),
    )
    _set_string(
        identity,
        "status",
        _first_value(
            payload.get("confirmation_state"),
            payload.get("status"),
            validation.get("status"),
        ),
    )
    return identity


def _job_identity(
    *,
    root: dict[str, Any],
    run_state: dict[str, Any],
) -> dict[str, str]:
    root_final = _as_mapping(root.get("final_response_payload"))
    run_final = _as_mapping(run_state.get("final_response_payload"))
    job = _first_mapping(
        root.get("backtest_job"),
        root_final.get("backtest_job"),
        run_final.get("backtest_job"),
    )
    identity: dict[str, str] = {}
    _set_string(identity, "id", job.get("id"))
    _set_string(identity, "status", job.get("status"))
    return identity


def _result_identities(
    *,
    root: dict[str, Any],
    run_state: dict[str, Any],
) -> list[str]:
    root_final = _as_mapping(root.get("final_response_payload"))
    run_final = _as_mapping(run_state.get("final_response_payload"))
    root_result = _as_mapping(root_final.get("result"))
    run_result = _as_mapping(run_final.get("result"))
    return _sorted_strings(
        root.get("result_run_id"),
        root.get("latest_run_id"),
        root_result.get("id"),
        run_result.get("id"),
    )


def _action_identity(
    *,
    root: dict[str, Any],
    run_state: dict[str, Any],
) -> dict[str, Any]:
    action = _first_mapping(
        root.get("structured_action"),
        root.get("action"),
        run_state.get("structured_action"),
    )
    action_type = _clean_string(action.get("type"))
    if action_type is None:
        return {}
    identity: dict[str, Any] = {"type": action_type}
    payload = _as_mapping(action.get("payload"))
    target: dict[str, str] = {}
    for field in _ACTION_TARGET_FIELDS:
        _set_string(target, field, payload.get(field))
    if target:
        identity["target"] = target
    return identity


def _retry_target(root: dict[str, Any]) -> dict[str, str]:
    retry = _as_mapping(root.get("retry_last_turn"))
    target: dict[str, str] = {}
    for field in ("request_message_id", "failed_assistant_id"):
        _set_string(target, field, retry.get(field))
    return target
