"""Pending-response-option selection helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

import json
from typing import Any

from argus.agent_runtime.interpreter.audits import PendingResponseOptionSelectionAudit
from argus.agent_runtime.interpreter.dca_audits import _dca_contract_missing_fields
from argus.agent_runtime.interpreter.shared import (
    _field_path_base,
    _llm_strategy_draft_has_extractable_fields,
    _supported_dca_cadence_value,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMRiskRule,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_contract import canonical_strategy_type


def _response_needs_pending_response_option_selection_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> bool:
    if not request.current_user_message.strip():
        return False
    response_intent = request.selected_thread_metadata.get("response_intent")
    if not isinstance(response_intent, dict):
        return False
    if response_intent.get("kind") != "unsupported_recovery":
        return False
    semantic_needs = response_intent.get("semantic_needs")
    if not isinstance(semantic_needs, list) or "simplification_choice" not in {
        str(need) for need in semantic_needs
    }:
        return False
    if not _pending_response_intent_options(request):
        return False
    if response.artifact_target == "latest_result":
        return False
    if response.semantic_turn_act in {
        "result_followup",
        "retry_failed_action",
    }:
        return False
    snapshot = request.latest_task_snapshot
    return bool(snapshot and snapshot.pending_strategy_summary is not None)


def _pending_response_intent_options(
    request: InterpretationRequest,
) -> list[dict[str, Any]]:
    response_intent = request.selected_thread_metadata.get("response_intent")
    if not isinstance(response_intent, dict):
        return []
    raw_options = response_intent.get("options")
    if not isinstance(raw_options, list):
        return []
    options: list[dict[str, Any]] = []
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            continue
        replacement_values = raw_option.get("replacement_values")
        if not isinstance(replacement_values, dict):
            continue
        options.append(
            {
                "label": str(raw_option.get("label") or "").strip(),
                "replacement_values": dict(replacement_values),
            }
        )
    return options


def _pending_response_option_selection_audit_messages(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    options: list[dict[str, Any]],
) -> list[dict[str, str]]:
    pending_strategy = None
    if (
        request.latest_task_snapshot
        and request.latest_task_snapshot.pending_strategy_summary
    ):
        pending_strategy = (
            request.latest_task_snapshot.pending_strategy_summary.model_dump(
                mode="json"
            )
        )
    return [
        {
            "role": "system",
            "content": (
                "You are Argus's pending response option selection audit. The "
                "previous assistant turn asked the user to choose among structured "
                "recovery options. Decide whether the current user message "
                "semantically selects one of those options. Use meaning, not "
                "keywords. Return only the zero-based option index when the user "
                "selects an option. Return no selection when the user provides a "
                "fresh investing idea, changes fields outside the offered options, "
                "or asks an unrelated question. Do not invent a new option."
            ),
        },
        {
            "role": "system",
            "content": f"Pending strategy JSON: {pending_strategy or 'none'}",
        },
        {
            "role": "system",
            "content": (
                "Pending options JSON: "
                f"{json.dumps(options, sort_keys=True, default=str)}"
            ),
        },
        {
            "role": "system",
            "content": (
                "Primary structured interpretation: "
                f"{response.model_dump(mode='json', exclude_none=True)}"
            ),
        },
        {"role": "user", "content": request.current_user_message},
    ]


def _response_from_pending_response_option_selection_audit(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
    audit: Any,
    options: list[dict[str, Any]],
) -> LLMInterpretationResponse | None:
    if (
        not isinstance(audit, PendingResponseOptionSelectionAudit)
        or not audit.is_selection
        or audit.confidence < 0.7
        or audit.selected_option_index is None
    ):
        return None
    option_index = audit.selected_option_index
    if option_index < 0 or option_index >= len(options):
        return None
    draft = _pending_strategy_draft_from_request_or_response(
        response=response,
        request=request,
    )
    if draft is None:
        return None
    replacement_values = options[option_index].get("replacement_values")
    if not isinstance(replacement_values, dict):
        return None
    replacement_result = _apply_pending_response_option_replacement(
        draft=draft,
        replacement_values=replacement_values,
        current_missing=response.missing_required_fields,
    )
    missing_fields = replacement_result["missing_fields"]
    return response.model_copy(
        update={
            "intent": "strategy_drafting"
            if missing_fields
            else "backtest_execution",
            "task_relation": "continue",
            "requires_clarification": bool(missing_fields),
            "candidate_strategy_draft": replacement_result["draft"],
            "missing_required_fields": missing_fields,
            "assistant_response": None,
            "semantic_turn_act": "answer_pending_need",
            "capability_question_focus": None,
            "context_question_focus": None,
            "artifact_target": "none",
            "unsupported_constraints": [],
            "reason_codes": list(
                dict.fromkeys(
                    [
                        *response.reason_codes,
                        "pending_response_option_selected",
                    ]
                )
            ),
        }
    )


def _pending_strategy_draft_from_request_or_response(
    *,
    response: LLMInterpretationResponse,
    request: InterpretationRequest,
) -> LLMStrategyDraft | None:
    snapshot = request.latest_task_snapshot
    if snapshot and snapshot.pending_strategy_summary is not None:
        return _llm_draft_from_strategy_summary(snapshot.pending_strategy_summary)
    draft = response.candidate_strategy_draft
    if _llm_strategy_draft_has_extractable_fields(draft):
        return draft.model_copy(deep=True)
    return None


def _llm_draft_from_strategy_summary(strategy: StrategySummary) -> LLMStrategyDraft:
    extra_parameters = dict(strategy.extra_parameters or {})
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        field_provenance = {}
    indicator_parameters = extra_parameters.get("indicator_parameters")
    if not isinstance(indicator_parameters, dict):
        indicator_parameters = {}
    date_range_intent = extra_parameters.get("date_range_intent")
    return LLMStrategyDraft(
        raw_user_phrasing=strategy.raw_user_phrasing,
        strategy_type=strategy.strategy_type,
        strategy_thesis=strategy.strategy_thesis,
        asset_universe=list(strategy.asset_universe),
        asset_class=strategy.asset_class,
        timeframe=strategy.timeframe,
        cadence=strategy.cadence,
        entry_logic=strategy.entry_logic,
        exit_logic=strategy.exit_logic,
        entry_rule=strategy.entry_rule,
        exit_rule=strategy.exit_rule,
        rule_spec=strategy.rule_spec,
        indicator=indicator_parameters.get("indicator"),
        indicator_period=indicator_parameters.get("indicator_period"),
        entry_threshold=indicator_parameters.get("entry_threshold"),
        exit_threshold=indicator_parameters.get("exit_threshold"),
        date_range=strategy.date_range,
        date_range_intent=(
            LLMDateRangeIntent.model_validate(date_range_intent)
            if isinstance(date_range_intent, dict)
            else None
        ),
        sizing_mode=strategy.sizing_mode,
        capital_amount=strategy.capital_amount,
        recurring_contribution=extra_parameters.get("recurring_contribution"),
        initial_capital=extra_parameters.get("initial_capital"),
        total_capital=extra_parameters.get("total_capital")
        or extra_parameters.get("total_budget"),
        position_size=strategy.position_size,
        risk_rules=[LLMRiskRule.model_validate(rule) for rule in strategy.risk_rules],
        assumptions=list(strategy.assumptions),
        comparison_baseline=strategy.comparison_baseline,
        refinement_of=strategy.refinement_of,
        field_provenance={
            str(key): str(value) for key, value in field_provenance.items()
        },
        extra_parameters=extra_parameters,
    )


def _apply_pending_response_option_replacement(
    *,
    draft: LLMStrategyDraft,
    replacement_values: dict[str, Any],
    current_missing: list[str],
) -> dict[str, Any]:
    repaired = draft.model_copy(deep=True)
    requested_field = replacement_values.get("requested_field")
    if replacement_values.get("ignore_initial_capital") is True:
        _clear_dca_total_budget_fields(repaired)
    if "strategy_type" in replacement_values:
        repaired.strategy_type = str(replacement_values["strategy_type"])
    if "initial_capital" in replacement_values:
        value = replacement_values.get("initial_capital")
        if value is not None:
            repaired.initial_capital = float(value)
            repaired.capital_amount = float(value)
            field_provenance = dict(repaired.field_provenance or {})
            field_provenance["capital_amount"] = "starting_capital"
            field_provenance["initial_capital"] = "starting_capital"
            repaired.field_provenance = field_provenance
    if "capital_amount" in replacement_values:
        value = replacement_values.get("capital_amount")
        if value is not None:
            repaired.capital_amount = float(value)
    if "date_range" in replacement_values:
        repaired.date_range = replacement_values["date_range"]
    if "cadence" in replacement_values:
        repaired.cadence = _supported_dca_cadence_value(
            replacement_values.get("cadence")
        )
    if "timeframe" in replacement_values:
        repaired.timeframe = str(replacement_values["timeframe"])
    if "comparison_baseline" in replacement_values:
        repaired.comparison_baseline = str(
            replacement_values["comparison_baseline"]
        ).strip()
    strategy_type = canonical_strategy_type(repaired.strategy_type)
    if strategy_type in {
        "buy_and_hold",
        "dca_accumulation",
    }:
        _clear_rule_or_indicator_fields(repaired)
    if strategy_type == "buy_and_hold":
        _clear_rule_strategy_text(repaired)
    if strategy_type != "dca_accumulation":
        _clear_dca_recurring_fields(repaired)

    missing_fields = _missing_fields_after_pending_option(
        repaired,
        requested_field=requested_field,
        current_missing=current_missing,
    )
    return {"draft": repaired, "missing_fields": missing_fields}


def _clear_dca_total_budget_fields(draft: LLMStrategyDraft) -> None:
    draft.initial_capital = None
    draft.total_capital = None
    field_provenance = dict(draft.field_provenance or {})
    for key in ("initial_capital", "total_capital"):
        field_provenance.pop(key, None)
    draft.field_provenance = field_provenance
    extra_parameters = dict(draft.extra_parameters or {})
    for key in (
        "initial_capital",
        "total_capital",
        "total_budget",
        "max_budget",
        "investment_budget",
        "cap",
    ):
        extra_parameters.pop(key, None)
    if field_provenance:
        extra_parameters["field_provenance"] = field_provenance
    else:
        extra_parameters.pop("field_provenance", None)
    draft.extra_parameters = extra_parameters


def _clear_dca_recurring_fields(draft: LLMStrategyDraft) -> None:
    draft.cadence = None
    draft.recurring_contribution = None
    field_provenance = dict(draft.field_provenance or {})
    for key in ("cadence", "recurring_contribution"):
        field_provenance.pop(key, None)
    draft.field_provenance = field_provenance
    extra_parameters = dict(draft.extra_parameters or {})
    for key in ("recurring_contribution", "recurring_cadence"):
        extra_parameters.pop(key, None)
    if field_provenance:
        extra_parameters["field_provenance"] = field_provenance
    else:
        extra_parameters.pop("field_provenance", None)
    draft.extra_parameters = extra_parameters


def _clear_rule_strategy_text(draft: LLMStrategyDraft) -> None:
    draft.raw_user_phrasing = None
    draft.strategy_thesis = None


def _clear_rule_or_indicator_fields(draft: LLMStrategyDraft) -> None:
    draft.entry_logic = None
    draft.exit_logic = None
    draft.entry_rule = None
    draft.exit_rule = None
    draft.rule_spec = None
    draft.indicator = None
    draft.indicator_period = None
    draft.entry_threshold = None
    draft.exit_threshold = None
    extra_parameters = dict(draft.extra_parameters or {})
    for key in (
        "indicator",
        "indicator_parameters",
        "indicator_period",
        "entry_threshold",
        "exit_threshold",
        "entry_rule",
        "exit_rule",
        "rule_spec",
        "simplify_logic",
    ):
        extra_parameters.pop(key, None)
    draft.extra_parameters = extra_parameters


def _missing_fields_after_pending_option(
    draft: LLMStrategyDraft,
    *,
    requested_field: Any,
    current_missing: list[str],
) -> list[str]:
    missing = list(current_missing)
    if isinstance(requested_field, str) and requested_field.strip():
        missing = list(dict.fromkeys([*missing, requested_field.strip()]))
    if canonical_strategy_type(draft.strategy_type) != "dca_accumulation":
        present_fields: set[str] = set()
        if draft.asset_universe:
            present_fields.add("asset_universe")
        if draft.date_range not in (None, "", [], {}):
            present_fields.add("date_range")
        stale_fields = {
            "cadence",
            "capital_amount",
            "entry_logic",
            "exit_logic",
            "recurring_contribution",
            "strategy_type",
        }
        return [
            field
            for field in missing
            if _field_path_base(field) not in present_fields
            and _field_path_base(field) not in stale_fields
        ]
    return _dca_contract_missing_fields(missing, draft=draft)
