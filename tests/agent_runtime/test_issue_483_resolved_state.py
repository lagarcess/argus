from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest
from argus.agent_runtime.artifacts.patch_policy import (
    executable_artifact_patch_missing_fields,
)
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.asset_resolution_context import (
    provider_asset_resolution_context_for_request,
)
from argus.agent_runtime.interpreter.provider_context_assets import (
    response_with_provider_context_assets,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMAssetMentionExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.clarify import clarify_stage
from argus.agent_runtime.stages.interpret import (
    StructuredInterpretation,
    interpret_stage,
    interpret_stage_async,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)
from argus.agent_runtime.strategy_requirements import (
    missing_required_fields_for_strategy,
)


@dataclass(frozen=True)
class ResolvedAssetStub:
    canonical_symbol: str
    asset_class: str
    name: str = ""
    raw_symbol: str = ""


class StaticInterpreter:
    def __init__(self, response: StructuredInterpretation) -> None:
        self.response = response

    def __call__(self, _request: InterpretationRequest) -> StructuredInterpretation:
        return self.response


class RecordingClarifier:
    def __init__(self) -> None:
        self.requests: list[Any] = []

    def __call__(self, request: Any) -> str:
        self.requests.append(request)
        return "Please provide the remaining field."


def _complete_dca_strategy() -> StrategySummary:
    return StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy Coca-Cola every month for five years.",
        asset_universe=["KO"],
        asset_class="equity",
        date_range={"start": "2021-08-12", "end": "2026-08-12"},
        cadence="monthly",
        capital_amount=13_000,
        extra_parameters={
            "field_provenance": {
                "capital_amount": "recurring_contribution",
            }
        },
    )


def _canonical_dca_required_fields() -> tuple[str, ...]:
    contract = build_default_capability_contract()
    return tuple(
        executable_artifact_patch_missing_fields(
            strategy=_complete_dca_strategy(),
            missing_fields=missing_required_fields_for_strategy(
                StrategySummary(strategy_type="dca_accumulation"),
                contract=contract,
            ),
        )
    )


def _structured_response(
    response: LLMInterpretationResponse,
) -> StructuredInterpretation:
    return StructuredInterpretation(
        intent=response.intent,
        task_relation=response.task_relation,
        requires_clarification=response.requires_clarification,
        user_goal_summary=response.user_goal_summary,
        detected_user_language=response.detected_user_language,
        candidate_strategy_draft=StrategySummary.model_validate(
            response.candidate_strategy_draft.model_dump(mode="python")
        ),
        missing_required_fields=list(response.missing_required_fields),
        assistant_response=response.assistant_response,
        confidence=response.confidence,
        reason_codes=list(response.reason_codes),
        semantic_turn_act=response.semantic_turn_act,
    )


def _resolve_ko(symbol: str, **_: Any) -> ResolvedAssetStub:
    assert symbol == "KO"
    return ResolvedAssetStub(
        canonical_symbol="KO",
        asset_class="equity",
        name="The Coca-Cola Company",
        raw_symbol="KO",
    )


@pytest.mark.asyncio
async def test_asset_preflight_fallback_is_reserved_for_actual_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.interpreter import asset_resolution_context as context_module

    calls: list[tuple[str, str]] = []

    async def invoke_schema(**kwargs: Any) -> LLMAssetMentionExtraction:
        model_name = str(kwargs["model_name"])
        calls.append((str(kwargs["task"]), model_name))
        if model_name == "primary/model":
            raise TimeoutError("primary extraction timed out")
        return LLMAssetMentionExtraction(
            asset_mentions=[],
            all_traded_asset_mentions_included=True,
        )

    monkeypatch.setattr(
        context_module,
        "_provider_asset_context_preflight_enabled",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        context_module,
        "_asset_mention_preflight_model_candidates",
        lambda _preferred_model: ["primary/model", "fallback/model"],
    )

    context = await provider_asset_resolution_context_for_request(
        request=InterpretationRequest(
            current_user_message="use 13,000 pesos",
            user=UserState(user_id="guest:issue-483"),
        ),
        preferred_model="primary/model",
        invoke_schema=invoke_schema,
        resolve_asset_candidate=lambda *_args, **_kwargs: pytest.fail(
            "an empty extraction must not invoke asset resolution"
        ),
    )

    assert calls == [
        ("asset_mention_preflight", "primary/model"),
        ("asset_mention_preflight", "fallback/model"),
    ]
    assert context is not None
    assert json.loads(context)["all_traded_asset_mentions_accounted_for"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("language", "message", "fallback_span"),
    [
        ("en", "use 13,000 pesos", "use"),
        ("es-419", "usa 13.000 pesos", "usa"),
    ],
)
async def test_issue_483_valid_empty_preflight_cannot_reopen_resolved_asset(
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    message: str,
    fallback_span: str,
) -> None:
    from argus.agent_runtime.interpreter import asset_resolution_context as context_module
    from argus.agent_runtime.stages import interpret as interpret_module

    calls: list[str] = []

    async def invoke_schema(**kwargs: Any) -> LLMAssetMentionExtraction:
        model_name = str(kwargs["model_name"])
        calls.append(model_name)
        if model_name == "primary/model":
            return LLMAssetMentionExtraction(
                asset_mentions=[],
                all_traded_asset_mentions_included=True,
            )
        return LLMAssetMentionExtraction(
            asset_mentions=[
                {
                    "raw_text": fallback_span,
                    "role": "traded_asset",
                    "mention_kind": "unknown",
                    "confidence": 0.51,
                }
            ],
            all_traded_asset_mentions_included=True,
        )

    def reject_fallback_asset(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("ordinary language is not an asset")

    monkeypatch.setattr(
        context_module,
        "_provider_asset_context_preflight_enabled",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        context_module,
        "_asset_mention_preflight_model_candidates",
        lambda _preferred_model: ["primary/model", "fallback/model"],
    )
    monkeypatch.setattr(interpret_module, "resolve_asset", _resolve_ko)

    request = InterpretationRequest(
        current_user_message=message,
        user=UserState(user_id="guest:issue-483", language_preference=language),
    )
    context = await provider_asset_resolution_context_for_request(
        request=request,
        preferred_model="primary/model",
        invoke_schema=invoke_schema,
        resolve_asset_candidate=reject_fallback_asset,
    )

    assert calls == ["primary/model"]
    assert context is not None
    assert json.loads(context)["all_traded_asset_mentions_accounted_for"] is True

    complete = _complete_dca_strategy()
    normalized = response_with_provider_context_assets(
        LLMInterpretationResponse(
            intent="backtest_execution",
            task_relation="continue",
            requires_clarification=False,
            user_goal_summary="Use 13,000 pesos for the recurring contribution.",
            detected_user_language=language,
            candidate_strategy_draft=LLMStrategyDraft.model_validate(
                complete.model_dump(mode="python")
            ),
            missing_required_fields=[],
            semantic_turn_act="answer_pending_need",
        ),
        asset_resolution_context=context,
    )
    assert "provider_context_incomplete_asset_mentions" not in normalized.reason_codes

    pending = complete.model_copy(update={"capital_amount": None})
    result = await interpret_stage_async(
        state=RunState.new(current_user_message=message, recent_thread_history=[]),
        user=request.user,
        latest_task_snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "capital_amount",
        },
        structured_interpreter=StaticInterpreter(_structured_response(normalized)),
    )

    assert result.outcome == "ready_for_confirmation"
    assert result.decision is not None
    assert result.decision.candidate_strategy_draft.asset_universe == ["KO"]
    assert result.decision.missing_required_fields == []
    assert "requested_field" not in result.patch
    assert "response_intent" not in result.patch


@pytest.mark.parametrize(
    "actual_missing_field",
    _canonical_dca_required_fields(),
)
def test_next_question_derives_from_canonical_unresolved_strategy_fields(
    monkeypatch: pytest.MonkeyPatch,
    actual_missing_field: str,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module

    monkeypatch.setattr(interpret_module, "resolve_asset", _resolve_ko)
    strategy = _complete_dca_strategy()
    missing_value: object = [] if actual_missing_field == "asset_universe" else None
    strategy = strategy.model_copy(update={actual_missing_field: missing_value})
    if actual_missing_field == "asset_universe":
        strategy.asset_class = None
    required_fields = _canonical_dca_required_fields()
    interpretation = StructuredInterpretation(
        intent="backtest_execution",
        task_relation="continue",
        requires_clarification=True,
        user_goal_summary="Apply the pending strategy update.",
        candidate_strategy_draft=strategy,
        missing_required_fields=list(required_fields),
        semantic_turn_act="answer_pending_need",
    )

    interpreted = interpret_stage(
        state=RunState.new(
            current_user_message="Apply the pending strategy update.",
            recent_thread_history=[],
        ),
        user=UserState(user_id="guest:invariant"),
        latest_task_snapshot=None,
        structured_interpreter=StaticInterpreter(interpretation),
    )

    assert interpreted.outcome == "needs_clarification"
    assert interpreted.decision is not None
    contract = build_default_capability_contract()
    canonical_missing = missing_required_fields_for_strategy(
        interpreted.decision.candidate_strategy_draft,
        contract=contract,
    )
    assert canonical_missing == [actual_missing_field]
    assert interpreted.decision.missing_required_fields == canonical_missing

    state = RunState.new(
        current_user_message="Apply the pending strategy update.",
        recent_thread_history=[],
    )
    state.intent = interpreted.decision.intent
    state.candidate_strategy_draft = interpreted.decision.candidate_strategy_draft
    state.missing_required_fields = interpreted.decision.missing_required_fields
    state.optional_parameter_status = interpreted.patch.get(
        "optional_parameter_status", {}
    )
    clarifier = RecordingClarifier()
    clarified = clarify_stage(
        state=state,
        contract=contract,
        clarification_generator=clarifier,
    )

    response_intent = clarified.patch["response_intent"]
    requested_fields = response_intent["requested_fields"]
    resolved_fields = set(required_fields).difference(canonical_missing)
    assert requested_fields == canonical_missing
    assert resolved_fields.isdisjoint(requested_fields)
    strategy_facts = response_intent["facts"]["strategy"]
    assert all(
        strategy_facts[field_name] not in (None, "", [], {})
        for field_name in resolved_fields
    )
    if actual_missing_field == "asset_universe":
        assert requested_fields.count("asset_universe") == 1
