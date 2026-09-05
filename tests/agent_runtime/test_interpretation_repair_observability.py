from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter as interpreter_module
from argus.agent_runtime.interpreter.repair_observability import repair_effect_metadata
from argus.agent_runtime.llm_interpreter_types import (
    FocusedDateWindowExtraction,
    FocusedStrategyExtraction,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from argus.llm import openrouter
from faker import Faker


def _response(*, goal: str, symbol: str = "") -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=True,
        user_goal_summary=goal,
        candidate_strategy_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold" if symbol else None,
            strategy_thesis=goal,
            asset_universe=[symbol] if symbol else [],
        ),
        missing_required_fields=["asset_universe"] if not symbol else [],
        semantic_turn_act="new_idea",
    )


def _record_successful_repair_receipt(schema_name: str) -> None:
    openrouter.record_openrouter_route_receipt(
        task="interpretation_repair",
        model_name="test/model",
        mode="json_schema",
        schema_name=schema_name,
        latency_ms=17,
        outcome="succeeded",
    )


def test_repair_effect_metadata_exposes_no_typed_values() -> None:
    fake = Faker()
    goal = fake.sentence()
    symbol = fake.lexify(text="????").upper()
    before = _response(goal=goal)
    after = _response(goal=goal, symbol=symbol)

    effect = repair_effect_metadata(
        before=before,
        after=after,
        trigger_reason="required_strategy_shape_missing",
        repair_applied=True,
    )

    encoded = json.dumps(effect, sort_keys=True)
    assert goal not in encoded
    assert symbol not in encoded
    assert effect["changed_fields"] == [
        "candidate_strategy_draft.asset_universe",
        "candidate_strategy_draft.strategy_type",
        "missing_required_fields",
    ]
    assert len(str(effect["before_fingerprint"])) == 64
    assert len(str(effect["after_fingerprint"])) == 64


@pytest.mark.asyncio
async def test_focused_strategy_repair_receipt_records_applied_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = Faker()
    goal = fake.sentence()
    before = _response(goal=goal)
    after = _response(goal=goal, symbol=fake.lexify(text="????").upper())

    async def invoke_schema(**kwargs: Any) -> FocusedStrategyExtraction:
        _record_successful_repair_receipt(str(kwargs["schema_name"]))
        return FocusedStrategyExtraction(
            is_testable_strategy=True,
            user_goal_summary=goal,
        )

    monkeypatch.setattr(
        interpreter_module,
        "_strategy_extraction_repair_is_allowed",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_unique_repair_models",
        lambda *_args, **_kwargs: ["test/model"],
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", invoke_schema)
    monkeypatch.setattr(
        interpreter_module,
        "_focused_strategy_extraction_has_material_fields",
        lambda _extraction: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_response_from_focused_strategy_extraction",
        lambda **_kwargs: after,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_normalize_response_for_runtime_context",
        lambda response, **_kwargs: response,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_augment_strategy_assets_from_resolvable_context",
        lambda **kwargs: kwargs["response"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "_response_can_skip_optional_runtime_readiness_audits",
        lambda **_kwargs: True,
    )

    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        repaired = await interpreter_module._repair_incomplete_strategy_extraction(
            failed_response=before,
            preferred_model="test/model",
            request=InterpretationRequest(
                current_user_message=goal,
                user=UserState(user_id=f"guest:{fake.uuid4()}"),
            ),
        )
        receipts = openrouter.end_openrouter_route_receipt_capture(token)
    except BaseException:
        openrouter.end_openrouter_route_receipt_capture(token)
        raise

    assert repaired == after
    assert receipts[0].repair_effect["trigger_reason"] == (
        "required_strategy_shape_missing"
    )
    assert receipts[0].repair_effect["repair_applied"] is True
    assert receipts[0].repair_effect["changed_fields"]


@pytest.mark.asyncio
async def test_focused_date_repair_receipt_records_authoritative_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = Faker()
    before = _response(goal=fake.sentence())

    async def invoke_schema(**kwargs: Any) -> FocusedDateWindowExtraction:
        _record_successful_repair_receipt(str(kwargs["schema_name"]))
        return FocusedDateWindowExtraction(has_date_window=False)

    monkeypatch.setattr(
        interpreter_module,
        "_response_needs_focused_date_window_intent_repair",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        interpreter_module,
        "_unique_repair_models",
        lambda *_args, **_kwargs: ["test/model"],
    )
    monkeypatch.setattr(interpreter_module, "invoke_openrouter_json_schema", invoke_schema)

    token = openrouter.begin_openrouter_route_receipt_capture()
    try:
        repaired = await interpreter_module._focused_date_window_audited_response(
            response=before,
            preferred_model="test/model",
            request=InterpretationRequest(
                current_user_message=fake.sentence(),
                user=UserState(user_id=f"guest:{fake.uuid4()}"),
            ),
        )
        receipts = openrouter.end_openrouter_route_receipt_capture(token)
    except BaseException:
        openrouter.end_openrouter_route_receipt_capture(token)
        raise

    assert repaired is None
    assert receipts[0].repair_effect["trigger_reason"] == (
        "date_window_intent_uncertain"
    )
    assert receipts[0].repair_effect["repair_applied"] is False
    assert receipts[0].repair_effect["no_op_reason"] == "no_date_window"
