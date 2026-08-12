"""Focused-strategy extraction message builders and repair-merge helpers.

Behavior-preserving relocation from llm_interpreter.py (issue #131)."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import date
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from argus.agent_runtime.interpreter import simplification_options as _options
from argus.agent_runtime.interpreter.dca_audits import (
    _capability_required_missing_fields_for_canonical_strategy,
)
from argus.agent_runtime.interpreter.shared import _llm_value_is_empty
from argus.agent_runtime.llm_interpreter_types import (
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
    LLMUnsupportedConstraint,
)
from argus.agent_runtime.rule_specs import (
    moving_average_crossover_text,
    opposite_moving_average_crossover_rule,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.strategy_contract import (
    canonical_strategy_type,
    executable_strategy_type_from_extracted_fields,
)
from argus.nlp.natural_time import resolve_date_range_intent

ResolveAssetCandidate = Callable[..., Any]


def _focused_strategy_extraction_messages(
    request: InterpretationRequest,
) -> list[BaseMessage]:
    return [
        SystemMessage(
            content=(
                "Focused strategy extraction repair. The general interpreter under-filled "
                "a current user message that may contain a testable investing idea. "
                "Interpret only the current user message and return all fields needed "
                "to draft an executable backtest. Do not omit a field that appears in "
                "the message. Do not invent fees, slippage, position size, or provider "
                "details. If the current message semantically gives a supported "
                "strategy family, primary asset, benchmark/reference asset, relative "
                "window, capital amount, recurring contribution, or recurring cadence, "
                "returning null or empty for that field is an extraction failure. Do "
                "not ask the user to choose a supported strategy when the current "
                "message already selected one semantically. "
                "Evidence spans are provenance only. Never put a supported "
                "strategy, asset, benchmark, time window, or capital amount only "
                "inside evidence_spans; populate the matching canonical field too. "
                "date_range_intent is the canonical object field, not an "
                "evidence_spans key; if a time window is visible, populate "
                "date_range_raw_text with the exact bounded phrase and "
                "date_range_intent with the canonical intent. "
                "is_testable_strategy means the user is asking for a strategy "
                "or backtest idea; it does not mean Argus can execute every part. For "
                "clear sentiment, news, fundamental, external-data, or other draft-only "
                "strategy requests, set is_testable_strategy=true, preserve the asset, "
                "period, unsupported rule, and raw strategy_type, and let the runtime "
                "route it to unsupported recovery.\n\n"
                "Executable strategy_type values are buy_and_hold, dca_accumulation, "
                "indicator_threshold, and signal_strategy. Treat this as an execution "
                "contract, not a taxonomy for every creative idea. If the user asks for "
                "sentiment, news, fundamentals, custom external data, or any rule you "
                "cannot express with these structured executable fields, do not force "
                "it into signal_strategy or indicator_threshold. Preserve the idea in "
                "user_goal_summary/assistant_response and mark it as needing a supported "
                "executable simplification. Valuation/P/E language is financially valid "
                "context, but it is not an executable rule in the current engine; preserve "
                "the valuation meaning and route toward the closest supported proxy. "
                "Preserve user-stated asset names or symbols "
                "in asset_universe; the provider-backed resolver will validate and "
                "canonicalize assets after interpretation. When the user lists "
                "multiple company or asset names as things to buy, hold, test, or "
                "include, emit each stated traded asset in asset_universe; do not "
                "collapse a same-class basket to one name. Preserve user-stated "
                "benchmark/comparison assets such as QQQ, SPY, BTC, or IWM in "
                "comparison_baseline, not asset_universe. In any language, a request "
                "to buy, hold, or test one primary asset over a window with another "
                "asset as a benchmark, reference, baseline, or comparison target is "
                "an executable buy_and_hold setup with that other asset in "
                "comparison_baseline; it is not unsupported custom logic. Carry "
                "the named comparison target verbatim even when it is a company "
                "name with no known symbol ('compare AAPL with Samsung' means "
                "comparison_baseline='Samsung'); never substitute a default "
                "benchmark for a target the user named — validation owns "
                "reporting unsupported ones. Relative windows such as "
                "'last 8 months' or equivalent phrases in any language must become "
                "date_range_intent with kind=rolling_window, count, unit, "
                "anchor=today, confidence, and evidence; a stated fractional "
                "quantity stays exact (the last 8.5 months means count=8.5, "
                "never 8 or 5). Current-year-to-current-date "
                "windows in any language must become date_range_intent with "
                "kind=year_to_date, confidence, and evidence. Do not ask for exact "
                "endpoint dates when the current message states a relative window. "
                "Use date_range_raw_text only as bounded evidence for the same "
                "window, not as the executable date contract. If the user gives a "
                "start date and says today, preserve the end as 'today' or "
                f"{date.today().isoformat()}, not a stale model date. If the user gives "
                "only a start or only an end, preserve only that endpoint and include "
                "date_range in missing_required_fields; do not infer today. Preserve "
                "language, date_range_raw_text, date_range_intent, and evidence_spans "
                "when available. Use date_range_intent for relative or semantic time "
                "windows so deterministic code receives canonical date math inputs "
                "instead of localized prose. Preserve "
                "user-stated timeframes such as 1 hour candles, hourly bars, 1h, "
                "4 hour candles, 4h, daily candles, or 1D as timeframe. Normalize "
                "one-hour/hourly to 1h, four-hour to 4h, and daily to 1D. Preserve "
                "user-stated capital amounts as capital_amount; "
                "do not silently widen the timeframe, shorten dates, or drop stated "
                "money amounts to make a request look runnable.\n\n"
                "For moving-average crossovers, set strategy_type to signal_strategy "
                "and set entry_rule to {'type':'moving_average_crossover', "
                "'fast_indicator':'sma' or 'ema', 'fast_period':number, "
                "'slow_indicator':'sma' or 'ema', 'slow_period':number, "
                "'direction':'bullish' for crosses above or 'bearish' for crosses "
                "below}. If the user does not state an exit, leave exit_rule null "
                "and set exit_logic to the opposite crossover default. Shorthand "
                "like 'the 50 crosses the 200' or '50/200 cross' is enough to set "
                "a bullish SMA 50/200 crossover unless the user says EMA or bearish.\n\n"
                "For RSI threshold ideas, set strategy_type to indicator_threshold, "
                "indicator to rsi, indicator_period only when supplied, and threshold "
                "overrides as numbers. If the user states only one threshold side, "
                "fill that side and leave only the unstated side null so the runtime "
                "can apply the supported default. Do not ask about RSI period; it has "
                "a supported default.\n\n"
                "A one-time historical acquisition or purchase plus holding through "
                "a period is normal user language for the supported buy_and_hold "
                "simulation, not unsupported manual trade replay. Preserve the asset, "
                "capital_amount, and date_range_intent when present. Do not ask the "
                "user to choose buy-and-hold again when the current message already "
                "semantically selected holding and did not state a separate entry or "
                "exit rule. A recurring fixed-amount purchase over a period is normal "
                "user language for the supported dca_accumulation simulation. Preserve "
                "the asset, recurring_contribution, cadence, capital_amount, and "
                "date_range_intent when present. Do not route recurring fixed-amount "
                "buys to unsupported recovery when those executable fields are stated."
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


def _comparison_baseline_provenance(
    comparison_baseline: str | None,
    *,
    current_message: str,
) -> dict[str, str]:
    del comparison_baseline, current_message
    return {}


def _focused_extraction_field_provenance(
    *,
    extraction: FocusedStrategyExtraction,
    current_message: str,
) -> dict[str, str]:
    provenance = _comparison_baseline_provenance(
        extraction.comparison_baseline,
        current_message=current_message,
    )
    evidence_spans = dict(extraction.evidence_spans or {})
    if (
        extraction.comparison_baseline
        and _llm_value_is_empty(provenance.get("comparison_baseline"))
        and not _llm_value_is_empty(evidence_spans.get("comparison_baseline"))
    ):
        provenance["comparison_baseline"] = "explicit_user"
    if extraction.recurring_contribution is not None:
        provenance["recurring_contribution"] = "explicit_user"
        provenance["capital_amount"] = "recurring_contribution"
    elif extraction.capital_amount is not None:
        if canonical_strategy_type(extraction.strategy_type) == "dca_accumulation":
            provenance["capital_amount"] = "recurring_contribution"
        else:
            provenance["capital_amount"] = "starting_capital"
    if extraction.cadence:
        provenance["cadence"] = "explicit_user"
    return provenance


# The base response's classification metadata, not user-stated executable
# context; carrying it would relabel the repaired strategy. Same exclusion the
# turn-level contextual merge applies when preserving a strategy family.
_REPAIR_MERGE_CLASSIFICATION_KEYS = frozenset({"raw_strategy_type", "template"})

_REPAIR_MERGE_DICT_CHANNELS = ("extra_parameters", "field_provenance", "evidence_spans")


def _merge_focused_repair_with_base(
    *,
    response: LLMInterpretationResponse,
    base_response: LLMInterpretationResponse | None,
) -> LLMInterpretationResponse:
    """Carry every user-stated fact the focused schema could not restate.

    One edit contract owns preservation (spec §3.5/#367): repair holds no
    private list of what survives. Preservation is field-general over the
    whole draft — a gap in the repaired draft is filled from the base, and the
    repair's own statements always win — so a stated cost, contribution, or
    rule parameter cannot be dropped just because the focused schema has no
    field for it. Silent partial application is the defect this guards.
    """
    if base_response is None:
        return response
    repaired = response.model_copy(deep=True)
    draft = repaired.candidate_strategy_draft
    base = base_response.candidate_strategy_draft
    for field_name in LLMStrategyDraft.model_fields:
        if field_name in _REPAIR_MERGE_DICT_CHANNELS:
            continue
        current_value = getattr(draft, field_name)
        base_value = getattr(base, field_name)
        if _llm_value_is_empty(current_value) and not _llm_value_is_empty(base_value):
            setattr(draft, field_name, deepcopy(base_value))
    for channel in _REPAIR_MERGE_DICT_CHANNELS:
        merged = {
            key: deepcopy(value)
            for key, value in getattr(base, channel).items()
            if not _llm_value_is_empty(value)
            and not (
                channel == "extra_parameters" and key in _REPAIR_MERGE_CLASSIFICATION_KEYS
            )
        }
        for key, value in getattr(draft, channel).items():
            if not _llm_value_is_empty(value):
                merged[key] = value
        setattr(draft, channel, merged)
    # The validated-cost channel is deterministic-only, so it re-attaches only
    # where the merged value still equals the validated one.
    for field_name, marker in base._validated_execution_cost_evidence.items():
        if (
            field_name not in draft._validated_execution_cost_evidence
            and draft.extra_parameters.get(field_name) == marker[0]
        ):
            draft._validated_execution_cost_evidence[field_name] = marker
    if not repaired.user_goal_summary and base_response.user_goal_summary:
        repaired.user_goal_summary = base_response.user_goal_summary
    repaired.reason_codes = list(
        dict.fromkeys(
            [
                *base_response.reason_codes,
                *repaired.reason_codes,
                "focused_repair_preserved_structured_context",
                *(
                    ["focused_repair_from_unsupported_context"]
                    if _base_response_was_unsupported(base_response)
                    else []
                ),
            ]
        )
    )
    return repaired


def _base_response_was_unsupported(response: LLMInterpretationResponse) -> bool:
    return bool(
        response.intent == "unsupported_or_out_of_scope"
        or response.semantic_turn_act == "unsupported_request"
        or response.unsupported_constraints
    )


def _focused_artifact_edit_messages(
    request: InterpretationRequest,
) -> list[BaseMessage] | None:
    snapshot = request.latest_task_snapshot
    if snapshot is None:
        return None
    prior = snapshot.pending_strategy_summary or snapshot.confirmed_strategy_summary
    if prior is None and snapshot.active_confirmation_reference is None:
        return None
    active_confirmation = (
        snapshot.active_confirmation_reference.model_dump(mode="json")
        if snapshot.active_confirmation_reference is not None
        else None
    )
    return [
        SystemMessage(
            content=(
                "Focused artifact edit planning. The previous interpretation replayed "
                "or under-filled the active artifact. Interpret only the current user "
                "message against the canonical prior artifact. The current user message "
                "is authoritative. Return a structured edit or answer; do not replay "
                "the prior artifact unchanged. If the user changes the asset, date "
                "range, indicator, thresholds, or assumptions, candidate_strategy_draft "
                "must include the changed field. Preserve unchanged executable context "
                "from the prior artifact only when it is needed for a runnable draft."
            )
        ),
        SystemMessage(
            content=(
                "Prior strategy JSON, if any: "
                f"{prior.model_dump(mode='json') if prior else 'none'}\n"
                "Active confirmation reference JSON, if any: "
                f"{active_confirmation if active_confirmation else 'none'}"
            )
        ),
        HumanMessage(content=request.current_user_message),
    ]


def _openrouter_wire_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    wire_messages: list[dict[str, str]] = []
    for message in messages:
        role = "user"
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, AIMessage):
            role = "assistant"
        elif isinstance(message, HumanMessage):
            role = "user"
        content = message.content
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = "".join(
                item
                if isinstance(item, str)
                else str(item.get("text") or "")
                if isinstance(item, dict)
                else str(item)
                for item in content
            )
        else:
            text = str(content)
        wire_messages.append({"role": role, "content": text})
    if wire_messages:
        wire_messages[0]["content"] = (
            wire_messages[0]["content"]
            + "\n\nReturn only valid JSON matching the supplied schema. "
            "Do not include reasoning, markdown, prose, or fields that are not "
            "defined by the supplied schema. Use the schema descriptions and the "
            "task-specific instructions above as the contract for canonical values."
        )
    return wire_messages


def canonical_asset_universe_from_llm_extraction(
    values: list[str],
    *,
    resolve_asset_candidate: ResolveAssetCandidate,
) -> tuple[list[str], str | None]:
    symbols: list[str] = []
    seen: set[str] = set()
    asset_classes: set[str] = set()
    for index, value in enumerate(values):
        raw_text = str(value or "").strip()
        if not raw_text:
            continue
        symbol = ""
        try:
            resolution = resolve_asset_candidate(
                raw_text,
                field=f"asset_universe[{index}]",
                source="llm_extraction",
            )
        except Exception:
            resolution = None
        if (
            resolution is not None
            and resolution.status == "resolved"
            and resolution.asset is not None
        ):
            symbol = str(resolution.asset.canonical_symbol or "").upper()
            asset_class = str(resolution.asset.asset_class or "").strip()
            if asset_class:
                asset_classes.add(asset_class)
        if not symbol:
            symbol = raw_text.upper()
        if symbol and symbol not in seen:
            seen.add(symbol)
            symbols.append(symbol)
    resolved_asset_class = next(iter(asset_classes)) if len(asset_classes) == 1 else None
    return symbols, resolved_asset_class


def response_from_focused_strategy_extraction(
    *,
    extraction: FocusedStrategyExtraction,
    request: InterpretationRequest,
    base_response: LLMInterpretationResponse | None = None,
    resolve_asset_candidate: ResolveAssetCandidate,
) -> LLMInterpretationResponse:
    snapshot = request.latest_task_snapshot
    is_pending_strategy_answer = bool(
        snapshot
        and (
            snapshot.pending_strategy_summary
            or snapshot.confirmed_strategy_summary
            or snapshot.active_confirmation_reference
        )
        and str(request.selected_thread_metadata.get("requested_field") or "").strip()
    )
    strategy_type = executable_strategy_type_from_extracted_fields(
        extraction.model_dump(mode="python")
    )
    entry_logic = extraction.entry_logic or moving_average_crossover_text(
        extraction.entry_rule
    )
    exit_logic = (
        extraction.exit_logic
        or moving_average_crossover_text(extraction.exit_rule)
        or moving_average_crossover_text(
            opposite_moving_average_crossover_rule(extraction.entry_rule)
        )
    )
    asset_universe, resolved_asset_class = canonical_asset_universe_from_llm_extraction(
        extraction.asset_universe,
        resolve_asset_candidate=resolve_asset_candidate,
    )
    extraction_date_range = extraction.date_range
    if _llm_value_is_empty(extraction_date_range):
        resolved_date_intent = resolve_date_range_intent(extraction.date_range_intent)
        if resolved_date_intent is not None:
            extraction_date_range = resolved_date_intent.payload
    if strategy_type is None:
        return LLMInterpretationResponse(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            requires_clarification=True,
            user_goal_summary=extraction.user_goal_summary,
            candidate_strategy_draft=LLMStrategyDraft(
                raw_user_phrasing=request.current_user_message,
                language=extraction.language,
                strategy_thesis=extraction.strategy_thesis
                or extraction.user_goal_summary,
                asset_universe=asset_universe,
                asset_class=extraction.asset_class or resolved_asset_class,
                timeframe=extraction.timeframe,
                date_range=extraction_date_range,
                date_range_raw_text=extraction.date_range_raw_text,
                date_range_intent=extraction.date_range_intent,
                comparison_baseline=extraction.comparison_baseline,
                capital_amount=extraction.capital_amount,
                recurring_contribution=extraction.recurring_contribution,
                cadence=extraction.cadence,
                entry_logic=entry_logic,
                exit_logic=exit_logic,
                indicator=extraction.indicator,
                indicator_period=extraction.indicator_period,
                entry_threshold=extraction.entry_threshold,
                exit_threshold=extraction.exit_threshold,
                evidence_spans=dict(extraction.evidence_spans or {}),
                field_provenance=_focused_extraction_field_provenance(
                    extraction=extraction,
                    current_message=request.current_user_message,
                ),
                extra_parameters={
                    "raw_strategy_type": extraction.strategy_type,
                }
                if extraction.strategy_type
                else {},
            ),
            unsupported_constraints=[
                LLMUnsupportedConstraint(
                    category="unsupported_strategy_logic",
                    raw_value=(
                        extraction.entry_logic
                        or extraction.strategy_thesis
                        or extraction.strategy_type
                        or extraction.user_goal_summary
                    ),
                    explanation=(
                        extraction.assistant_response
                        or "This idea depends on strategy logic that is not executable yet."
                    ),
                    simplification_options=(
                        _options.unsupported_strategy_logic_simplification_options()
                    ),
                )
            ],
            confidence=extraction.confidence,
            reason_codes=["focused_strategy_extraction_unrecognized_contract"],
            semantic_turn_act="unsupported_request",
        )
    response = LLMInterpretationResponse(
        intent="strategy_drafting"
        if extraction.requires_clarification
        else "backtest_execution",
        task_relation="continue" if is_pending_strategy_answer else "new_task",
        requires_clarification=extraction.requires_clarification,
        user_goal_summary=extraction.user_goal_summary,
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing=request.current_user_message,
            language=extraction.language,
            strategy_type=strategy_type,
            strategy_thesis=extraction.strategy_thesis or extraction.user_goal_summary,
            asset_universe=asset_universe,
            asset_class=extraction.asset_class or resolved_asset_class,
            timeframe=extraction.timeframe,
            date_range=extraction_date_range,
            date_range_raw_text=extraction.date_range_raw_text,
            date_range_intent=extraction.date_range_intent,
            comparison_baseline=extraction.comparison_baseline,
            capital_amount=extraction.capital_amount,
            recurring_contribution=extraction.recurring_contribution,
            cadence=extraction.cadence,
            entry_logic=entry_logic,
            exit_logic=exit_logic,
            entry_rule=extraction.entry_rule,
            exit_rule=extraction.exit_rule,
            rule_spec=extraction.rule_spec,
            indicator=extraction.indicator,
            indicator_period=extraction.indicator_period,
            entry_threshold=extraction.entry_threshold,
            exit_threshold=extraction.exit_threshold,
            evidence_spans=dict(extraction.evidence_spans or {}),
            field_provenance=_focused_extraction_field_provenance(
                extraction=extraction,
                current_message=request.current_user_message,
            ),
        ),
        missing_required_fields=list(extraction.missing_required_fields),
        assistant_response=extraction.assistant_response,
        confidence=extraction.confidence,
        reason_codes=["focused_strategy_extraction_repair"],
        semantic_turn_act=(
            "answer_pending_need" if is_pending_strategy_answer else "new_idea"
        ),
    )
    response = _merge_focused_repair_with_base(
        response=response,
        base_response=base_response,
    )
    # Missing fields derive from the merged draft so already-grounded context is
    # not re-asked.
    response.missing_required_fields = (
        _capability_required_missing_fields_for_canonical_strategy(
            response.missing_required_fields,
            draft=response.candidate_strategy_draft,
        )
    )
    if response.missing_required_fields or response.ambiguous_fields:
        response.intent = "strategy_drafting"
        response.requires_clarification = True
        response.assistant_response = None
    return response


def strategy_extraction_repair_is_allowed(
    response: Any,
    *,
    request: Any,
    has_failed_action_launch_payload: Any,
    noncanonical_text_needs_repair: Any,
    has_active_strategy_context: Any,
    current_turn_has_material_execution_evidence: Any,
) -> bool:
    if response.task_relation == "refine":
        return False
    if response.semantic_turn_act == "asset_discovery":
        # A typed discovery ask has no strategy to extract — payload or not;
        # the deterministic missing-target recovery owns the partial shape.
        return False
    if response.semantic_turn_act == "retry_failed_action":
        return not has_failed_action_launch_payload(request)
    if response.semantic_turn_act == "unsupported_request":
        has_active_context = has_active_strategy_context(request)
        has_material_evidence = current_turn_has_material_execution_evidence(request)
        if has_active_context and (
            not str(request.selected_thread_metadata.get("requested_field") or "").strip()
            or not has_material_evidence
        ):
            return False
        if noncanonical_text_needs_repair(response=response, request=request):
            return True
        if response.intent not in {
            "unsupported_or_out_of_scope",
            "beginner_guidance",
            "conversation_followup",
        }:
            return False
        if not response.unsupported_constraints:
            return has_material_evidence
        if not any(
            item.category == "unsupported_strategy_logic"
            for item in response.unsupported_constraints
        ):
            return False
        return bool(
            response.candidate_strategy_draft.raw_user_phrasing
            or response.candidate_strategy_draft.strategy_thesis
            or request.current_user_message.strip()
        )
    if response.semantic_turn_act == "answer_pending_need":
        return current_turn_has_material_execution_evidence(request)
    return response.semantic_turn_act not in {
        "refine_current_idea",
        "approval",
        "result_followup",
    }
