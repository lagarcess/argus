"""Direct capital and date edits on a pending confirmation, without a turn.

The drawer hands over a typed number or an explicit date window, so no prose is
parsed anywhere on this path: the values become the same typed edit operations
the conversational planner emits, applied by the same application code, and the
result is assembled by the real confirm stage. A direct edit and the equivalent
conversational edit therefore produce the same canonical artifact because they
share the assembler, and the test suite proves it rather than asserting it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from argus.agent_runtime.artifact_edit_planner import (
    EditOperation,
    apply_edit_operations,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.coverage_recovery import coverage_recovery_from_status
from argus.agent_runtime.llm_interpreter_types import LLMDateRangeIntent
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret_internal.confirmation_artifact_edits import (
    apply_resolved_artifact_edit_to_strategy_summary,
)
from argus.agent_runtime.state.models import RunState, StrategySummary
from argus.agent_runtime.strategy_contract import executable_strategy_type


@dataclass(frozen=True)
class DirectEditPreparation:
    confirmation_payload: dict[str, Any] | None = None
    error_code: str | None = None


_COST_EDIT_TARGETS = {"fee_rate": "fees", "slippage": "slippage"}


def direct_edit_confirmation_preparation(
    source_payload: dict[str, Any],
    *,
    capital: float | None,
    date_window: dict[str, str] | None,
    starting_capital: float | None = None,
    recurring_contribution: float | None = None,
    contribution_period: str | None = None,
    fee_rate: float | None = None,
    slippage: float | None = None,
    language: str = "en",
) -> DirectEditPreparation:
    """Patch the canonical strategy with typed values, then re-confirm it."""
    strategy = source_payload.get("strategy")
    launch = source_payload.get("launch_payload")
    if not isinstance(strategy, dict) or not isinstance(launch, dict):
        return DirectEditPreparation(error_code="confirmation_payload_invalid")
    try:
        summary = StrategySummary.model_validate(strategy)
    except ValueError:
        return DirectEditPreparation(error_code="confirmation_payload_invalid")

    is_recurring = executable_strategy_type(summary) == "dca_accumulation"
    operations: list[EditOperation] = []
    money_edits = (
        (capital, "capital"),
        (starting_capital, "starting_capital"),
        (recurring_contribution, "recurring_contribution"),
    )
    if any(value is not None for value, _ in money_edits):
        if str(launch.get("sizing_mode") or "") == "position_size":
            return DirectEditPreparation(error_code="capital_not_applicable")
    # A card edits the money roles its own plan has. The shared bankroll field
    # cannot reach a recurring plan, and the plan's roles cannot reach a
    # one-time position, so no value can arrive in the wrong role.
    for value, target in money_edits:
        if value is None:
            continue
        if is_recurring != (target != "capital"):
            return DirectEditPreparation(error_code="capital_role_not_applicable")
        operations.append(EditOperation(op="set", target=target, number=float(value)))
    if contribution_period is not None:
        if not is_recurring:
            return DirectEditPreparation(error_code="capital_role_not_applicable")
        operations.append(
            EditOperation(op="set", target="cadence", value=contribution_period)
        )
    window_intent: LLMDateRangeIntent | None = None
    if date_window is not None:
        window_intent = _explicit_window_intent(date_window)
        if window_intent is None:
            return DirectEditPreparation(error_code="invalid_date_window")
        operations.append(
            EditOperation(op="set", target="date_window", date_window=window_intent)
        )
    for cost_value, cost_target in (
        (fee_rate, _COST_EDIT_TARGETS["fee_rate"]),
        (slippage, _COST_EDIT_TARGETS["slippage"]),
    ):
        if cost_value is not None:
            operations.append(
                EditOperation(op="set", target=cost_target, number=float(cost_value))
            )
    if not operations:
        return DirectEditPreparation(error_code="confirmation_payload_invalid")

    resolved = apply_edit_operations(
        operations,
        current_asset_universe=summary.asset_universe,
    )
    refused_targets = {entry.split(".", 1)[-1] for entry in resolved.unsupported}
    if refused_targets & set(_COST_EDIT_TARGETS.values()):
        # The shared resolver is the one cost gate; a refused rate surfaces as
        # a typed field error instead of a generic invalid-payload conflict.
        return DirectEditPreparation(error_code="unsupported_cost_value")
    if "cadence" in refused_targets:
        return DirectEditPreparation(error_code="unsupported_dca_cadence")
    if resolved.unsupported or not resolved.has_changes():
        return DirectEditPreparation(error_code="confirmation_payload_invalid")
    field_provenance = _field_provenance_of(summary)
    apply_resolved_artifact_edit_to_strategy_summary(
        resolved,
        candidate=summary,
        field_provenance=field_provenance,
    )
    summary.extra_parameters["field_provenance"] = field_provenance
    if window_intent is not None:
        _drop_stale_date_evidence(summary)

    # The real confirm stage assembles the result, so validation, coverage,
    # materialization, and identity minting cannot drift from the
    # conversational path.
    state = RunState.new(current_user_message="", recent_thread_history=[])
    state = state.model_copy(
        update={
            "candidate_strategy_draft": summary,
            "optional_parameter_status": _parameter_status_with_edits(
                source_payload,
                resolved=resolved,
            ),
        }
    )
    result = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
        language=language,
    )
    if result.outcome != "await_approval":
        # The confirm stage names its refusal; hand the exact code to the
        # endpoint instead of degrading every failure into one conflict.
        launch_code = result.stage_patch.get("launch_validation_code")
        if isinstance(launch_code, str) and launch_code:
            return DirectEditPreparation(error_code=launch_code)
        recovery = coverage_recovery_from_status(
            result.stage_patch.get("optional_parameter_status")
        )
        if recovery is not None:
            return DirectEditPreparation(error_code=recovery["code"])
        return DirectEditPreparation(error_code="confirmation_not_executable")
    candidate = result.stage_patch.get("confirmation_payload")
    if not isinstance(candidate, dict):
        return DirectEditPreparation(error_code="confirmation_not_executable")
    return DirectEditPreparation(confirmation_payload=candidate)


def _explicit_window_intent(
    date_window: dict[str, str],
) -> LLMDateRangeIntent | None:
    try:
        start = date.fromisoformat(str(date_window.get("start") or ""))
        end = date.fromisoformat(str(date_window.get("end") or ""))
    except ValueError:
        return None
    if start > end:
        return None
    return LLMDateRangeIntent(
        kind="explicit_range",
        start=start.isoformat(),
        end=end.isoformat(),
        confidence=1.0,
    )


def _field_provenance_of(summary: StrategySummary) -> dict[str, str]:
    provenance = summary.extra_parameters.get("field_provenance")
    if not isinstance(provenance, dict):
        return {}
    return {str(key): str(value) for key, value in provenance.items()}


def _drop_stale_date_evidence(summary: StrategySummary) -> None:
    # The prior prose evidence described the previous window; the typed edit is
    # its own provenance, so stale spans must not outlive the value they backed.
    summary.extra_parameters.pop("date_range_raw_text", None)
    evidence_spans = summary.extra_parameters.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        cleaned = {
            key: value
            for key, value in evidence_spans.items()
            if str(key).split("[", 1)[0] != "date_range"
        }
        if cleaned:
            summary.extra_parameters["evidence_spans"] = cleaned
        else:
            summary.extra_parameters.pop("evidence_spans", None)


def _parameter_status_with_edits(
    source_payload: dict[str, Any],
    *,
    resolved: Any,
) -> dict[str, Any]:
    """The user-owned parameter state this edit re-confirms against.

    The confirm stage reads a plan's starting capital from here, so an edited
    seed has to arrive here too. Carrying it only on the draft would leave a
    second copy nobody reads, and the run would quietly use the old seed.
    """
    status = _user_owned_parameter_status(source_payload)
    if resolved.initial_capital is not None:
        status["initial_capital"] = float(resolved.initial_capital)
    return status


def _user_owned_parameter_status(source_payload: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the user-owned parameter statuses behind the stored card.

    The stored resolved parameters record which values came from the user;
    re-confirming with those statuses keeps a user-chosen timeframe or cost
    exactly as a conversational edit of the same card would.
    """
    optional_parameters = source_payload.get("optional_parameters")
    if not isinstance(optional_parameters, dict):
        return {}
    status: dict[str, Any] = {}
    for field_name, entry in optional_parameters.items():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("source") or "") != "user":
            continue
        if "value" not in entry:
            continue
        status[str(field_name)] = entry["value"]
    return status
