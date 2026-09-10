"""Typed field-fidelity ownership regressions for issue #271."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.audits import StatedRunFieldFidelityAudit
from argus.agent_runtime.interpreter.execution_cost_fidelity import (
    apply_cost_fidelity,
)
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.llm_interpreter_types import (
    LLMDateRangeIntent,
    LLMInterpretationResponse,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.stages.interpret import interpret_stage_async
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    RunState,
    StrategySummary,
    TaskSnapshot,
    UserState,
)

from tests.agent_runtime._llm_interpreter_common import ResolvedAssetStub


def _primary_cost_response(
    *,
    fee_rate: float = 0.001,
    slippage: float = 0.0005,
) -> LLMInterpretationResponse:
    return LLMInterpretationResponse(
        intent="strategy_drafting",
        task_relation="new_task",
        requires_clarification=False,
        user_goal_summary="Test MSFT with modeled execution costs.",
        candidate_strategy_draft=LLMStrategyDraft(
            raw_user_phrasing="Test MSFT with modeled execution costs.",
            strategy_type="buy_and_hold",
            strategy_thesis="Buy and hold MSFT.",
            asset_universe=["MSFT"],
            asset_class="equity",
            timeframe="1D",
            date_range={"start": "2022-01-01", "end": "2022-12-31"},
            capital_amount=12000,
            comparison_baseline="SPY",
            field_provenance={
                "capital_amount": "starting_capital",
                "comparison_baseline": "explicit_user",
                "timeframe": "explicit_user",
            },
            extra_parameters={
                "fee_rate": fee_rate,
                "slippage": slippage,
            },
        ),
        semantic_turn_act="new_idea",
    )


def _request(message: str, *, language: str = "en") -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message=message,
        recent_thread_history=[],
        latest_task_snapshot=None,
        user=UserState(user_id="u-271", language_preference=language),
    )


def _audit_payload(
    *,
    fee_rate: float | None = 0.001,
    fee_span: str | None = "10 bps fee",
    slippage: float | None = 0.0005,
    slippage_span: str | None = "5 bps slippage",
) -> dict[str, Any]:
    return {
        "fee": (
            None
            if fee_rate is None or fee_span is None
            else {"rate": fee_rate, "evidence_span": fee_span}
        ),
        "slippage": (
            None
            if slippage is None or slippage_span is None
            else {"rate": slippage, "evidence_span": slippage_span}
        ),
        "confidence": 0.98,
    }


def test_cost_fidelity_schema_rejects_non_numeric_rate_shape() -> None:
    with pytest.raises(ValueError):
        StatedRunFieldFidelityAudit.model_validate(
            {
                "fee": {
                    "rate": "0.001",
                    "evidence_span": "10 bps fee",
                }
            }
        )


def test_cost_fidelity_cannot_enable_costs_while_kill_switch_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "false")
    response = _primary_cost_response()
    audit = StatedRunFieldFidelityAudit.model_validate(_audit_payload())
    message = "Test MSFT with a 10 bps fee and 5 bps slippage."

    changed = apply_cost_fidelity(response, audit, message, None)

    assert changed is False
    strategy = _strategy_from_llm(
        response.candidate_strategy_draft,
        current_user_message=message,
    )
    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
    provenance = strategy.extra_parameters["field_provenance"]
    assert "fee_rate" not in provenance
    assert "slippage" not in provenance


@pytest.mark.asyncio
@pytest.mark.parametrize("primary_rate", ["0.001", True], ids=["string", "boolean"])
async def test_cost_fidelity_rejects_non_numeric_primary_rate_shape(
    monkeypatch: pytest.MonkeyPatch,
    primary_rate: object,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = _primary_cost_response()
    response.candidate_strategy_draft.extra_parameters["fee_rate"] = primary_rate

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(_audit_payload())

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    message = "Test MSFT with a 10 bps fee and 5 bps slippage."
    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=_request(message),
    )

    assert repaired is not None
    assert repaired.requires_clarification is True
    assert "fee_rate" not in repaired.candidate_strategy_draft.extra_parameters


@pytest.mark.asyncio
async def test_fidelity_audit_owns_fresh_costs_before_confirmation_and_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    message = (
        "Test MSFT with $12,000 for calendar year 2022 using daily data, "
        "SPY as benchmark, a 10 bps fee and 5 bps slippage."
    )
    calls: list[tuple[str, str]] = []

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del messages, model_name
        calls.append((task, schema_name))
        return schema_model.model_validate(_audit_payload())

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_primary_cost_response(),
        preferred_model="test-model",
        request=_request(message),
    )

    assert calls == [("field_fidelity", "StatedRunFieldFidelityAudit")]
    assert repaired is not None
    assert repaired.requires_clarification is False
    draft = repaired.candidate_strategy_draft
    assert draft.extra_parameters["fee_rate"] == 0.001
    assert draft.extra_parameters["slippage"] == 0.0005
    assert draft.evidence_spans["fee_rate"] == "10 bps fee"
    assert draft.evidence_spans["slippage"] == "5 bps slippage"
    assert draft.field_provenance["fee_rate"] == "explicit_user"
    assert draft.field_provenance["slippage"] == "explicit_user"

    strategy = _strategy_from_llm(draft, current_user_message=message)
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    assert strategy.extra_parameters["field_provenance"]["fee_rate"] == "explicit_user"
    assert (
        strategy.extra_parameters["field_provenance"]["slippage"] == "explicit_user"
    )

    state = RunState.new(current_user_message=message, recent_thread_history=[])
    state.candidate_strategy_draft = strategy
    confirmation = confirm_stage(
        state=state,
        contract=build_default_capability_contract(),
    )
    assert confirmation.outcome == "await_approval"
    payload = confirmation.patch["confirmation_payload"]
    assert payload["optional_parameters"]["fees"]["value"] == 0.001
    assert payload["optional_parameters"]["slippage"]["value"] == 0.0005
    assert payload["launch_payload"]["_execution_realism"] == {
        "enabled": True,
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
    }


@pytest.mark.asyncio
async def test_valid_audit_owns_matching_primary_spans_without_trusting_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    response = _primary_cost_response()
    response.candidate_strategy_draft.evidence_spans.update(
        {
            "fee_rate": "10 bps fee",
            "slippage": "5 bps slippage",
        }
    )
    response.candidate_strategy_draft.field_provenance.update(
        {
            "fee_rate": "explicit_user",
            "slippage": "explicit_user",
        }
    )

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(_audit_payload())

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    message = "Test MSFT with a 10 bps fee and 5 bps slippage."
    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=_request(message),
    )

    assert repaired is not None
    strategy = _strategy_from_llm(
        repaired.candidate_strategy_draft,
        current_user_message=message,
    )
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    provenance = strategy.extra_parameters["field_provenance"]
    assert provenance["fee_rate"] == "explicit_user"
    assert provenance["slippage"] == "explicit_user"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("audit_payload", "message", "expected_slippage"),
    [
        (
            _audit_payload(
                fee_rate=None,
                fee_span=None,
                slippage=None,
                slippage_span=None,
            ),
            "Test MSFT with a 10 bps fee and 5 bps slippage.",
            None,
        ),
        (
            _audit_payload(fee_rate=0.002),
            "Test MSFT with a 10 bps fee and 5 bps slippage.",
            0.0005,
        ),
        (
            _audit_payload(
                fee_span="20 bps fee",
                slippage_span="2 bps slippage",
            ),
            "Test MSFT with a 10 bps fee and 5 bps slippage.",
            None,
        ),
    ],
    ids=["missing-evidence", "rate-mismatch", "invented-spans"],
)
async def test_unowned_current_turn_costs_require_clarification(
    monkeypatch: pytest.MonkeyPatch,
    audit_payload: dict[str, Any],
    message: str,
    expected_slippage: float | None,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(audit_payload)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_primary_cost_response(),
        preferred_model="test-model",
        request=_request(message),
    )

    assert repaired is not None
    assert repaired.requires_clarification is True
    assert "assumption" in repaired.missing_required_fields
    assert "execution_cost_evidence_unresolved" in repaired.reason_codes
    strategy = _strategy_from_llm(
        repaired.candidate_strategy_draft,
        current_user_message=message,
    )
    assert "fee_rate" not in strategy.extra_parameters
    if expected_slippage is None:
        assert "slippage" not in strategy.extra_parameters
    else:
        assert strategy.extra_parameters["slippage"] == expected_slippage


@pytest.mark.asyncio
async def test_grounded_rate_conflict_with_replayed_prior_cost_requires_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    prior = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["MSFT"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2022-01-01", "end": "2022-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
        },
    )
    response = _primary_cost_response()
    response.task_relation = "refine"
    response.semantic_turn_act = "refine_current_idea"
    request = _request("Set the fee to 20 bps.").model_copy(
        update={
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=prior,
            )
        }
    )

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(
            _audit_payload(
                fee_rate=0.002,
                fee_span="20 bps",
                slippage=None,
                slippage_span=None,
            )
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert repaired is not None
    assert repaired.requires_clarification is True
    assert "execution_cost_evidence_unresolved" in repaired.reason_codes
    assert "fee_rate" not in repaired.candidate_strategy_draft.extra_parameters


@pytest.mark.asyncio
async def test_unavailable_cost_fidelity_audit_requires_clarification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(**kwargs):
        del kwargs
        raise RuntimeError("field fidelity unavailable")

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_primary_cost_response(),
        preferred_model="test-model",
        request=_request("Test MSFT with a 10 bps fee and 5 bps slippage."),
    )

    assert repaired is not None
    assert repaired.requires_clarification is True
    assert "assumption" in repaired.missing_required_fields
    assert "execution_cost_evidence_unresolved" in repaired.reason_codes


@pytest.mark.asyncio
async def test_unowned_zero_costs_require_clarification_instead_of_silent_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(
            _audit_payload(
                fee_rate=None,
                fee_span=None,
                slippage=None,
                slippage_span=None,
            )
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_primary_cost_response(fee_rate=0.0, slippage=0.0),
        preferred_model="test-model",
        request=_request("Test MSFT."),
    )

    assert repaired is not None
    assert repaired.requires_clarification is True
    assert "assumption" in repaired.missing_required_fields
    strategy = _strategy_from_llm(
        repaired.candidate_strategy_draft,
        current_user_message="Test MSFT.",
    )
    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fee_rate", "slippage", "audit_payload"),
    [
        (
            -0.001,
            0.0,
            _audit_payload(
                fee_rate=-0.001,
                slippage=None,
                slippage_span=None,
            ),
        ),
        (
            float("inf"),
            0.0,
            _audit_payload(
                fee_rate=float("inf"),
                slippage=None,
                slippage_span=None,
            ),
        ),
        (
            0.0,
            0.06,
            _audit_payload(
                fee_rate=None,
                fee_span=None,
                slippage=0.06,
            ),
        ),
    ],
    ids=["negative", "non-finite", "slippage-above-supported-bound"],
)
async def test_invalid_audited_cost_rates_never_gain_ownership(
    monkeypatch: pytest.MonkeyPatch,
    fee_rate: float,
    slippage: float,
    audit_payload: dict[str, Any],
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(audit_payload)

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_primary_cost_response(
            fee_rate=fee_rate,
            slippage=slippage,
        ),
        preferred_model="test-model",
        request=_request("Test MSFT with a 10 bps fee and 5 bps slippage."),
    )

    assert repaired is not None
    assert repaired.requires_clarification is True
    strategy = _strategy_from_llm(
        repaired.candidate_strategy_draft,
        current_user_message="Test MSFT with a 10 bps fee and 5 bps slippage.",
    )
    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "language", "fee_span", "slippage_span"),
    [
        (
            "Set a 0 bps fee and 0 bps slippage.",
            "en",
            "0 bps fee",
            "0 bps slippage",
        ),
        (
            "Usa 0 bps de comisión y 0 bps de deslizamiento.",
            "es-419",
            "0 bps de comisión",
            "0 bps de deslizamiento",
        ),
    ],
    ids=["english", "spanish"],
)
async def test_fidelity_audit_owns_explicit_zero_without_phrase_tables(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    language: str,
    fee_span: str,
    slippage_span: str,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(
            _audit_payload(
                fee_rate=0.0,
                fee_span=fee_span,
                slippage=0.0,
                slippage_span=slippage_span,
            )
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=_primary_cost_response(fee_rate=0.0, slippage=0.0),
        preferred_model="test-model",
        request=_request(message, language=language),
    )

    assert repaired is not None
    assert repaired.requires_clarification is False
    strategy = _strategy_from_llm(
        repaired.candidate_strategy_draft,
        current_user_message=message,
    )
    assert strategy.extra_parameters["fee_rate"] == 0.0
    assert strategy.extra_parameters["slippage"] == 0.0
    provenance = strategy.extra_parameters["field_provenance"]
    assert provenance["fee_rate"] == "explicit_user"
    assert provenance["slippage"] == "explicit_user"


def test_primary_model_cost_spans_are_not_authoritative_without_typed_audit() -> None:
    message = "Test MSFT with a 10 bps fee and 5 bps slippage."
    draft = _primary_cost_response().candidate_strategy_draft
    draft.evidence_spans = {
        "fee_rate": "10 bps fee",
        "slippage": "5 bps slippage",
    }
    draft.field_provenance.update(
        {
            "fee_rate": "explicit_user",
            "slippage": "explicit_user",
        }
    )

    strategy = _strategy_from_llm(draft, current_user_message=message)

    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
    provenance = strategy.extra_parameters["field_provenance"]
    assert "fee_rate" not in provenance
    assert "slippage" not in provenance


def test_cost_fidelity_prompt_requests_typed_rates_spans_and_zero() -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    message = "Test MSFT with a 10 bps fee and 5 bps slippage."
    prompt = interpreter_module._stated_run_field_fidelity_messages(
        response=_primary_cost_response(),
        request=_request(message),
    )[0]["content"]

    assert "typed fee or slippage object" in prompt
    assert "canonical decimal rate" in prompt
    assert "exact bounded evidence_span" in prompt
    assert "10 bps is 0.001" in prompt
    assert "Preserve 0.0" in prompt


@pytest.mark.asyncio
async def test_unrelated_edit_omits_replayed_cost_patch_and_preserves_prior_truth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    prior = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold MSFT.",
        asset_universe=["MSFT"],
        asset_class="equity",
        timeframe="1D",
        date_range={"start": "2022-01-01", "end": "2022-12-31"},
        capital_amount=12000,
        comparison_baseline="SPY",
        extra_parameters={
            "fee_rate": 0.001,
            "slippage": 0.0005,
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
        },
    )
    response = _primary_cost_response()
    response.task_relation = "refine"
    response.semantic_turn_act = "refine_current_idea"
    response.candidate_strategy_draft.date_range = {
        "start": "2023-02-01",
        "end": "2023-11-30",
    }
    message = "Change only the dates to February 1 through November 30, 2023."
    request = _request(message).model_copy(
        update={
            "latest_task_snapshot": TaskSnapshot(
                pending_strategy_summary=prior,
            )
        }
    )

    async def fake_json_schema(
        *, task, messages, schema_model, schema_name, model_name=None
    ):
        del task, messages, schema_name, model_name
        return schema_model.model_validate(
            _audit_payload(
                fee_rate=None,
                fee_span=None,
                slippage=None,
                slippage_span=None,
            )
        )

    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    repaired = await interpreter_module._audit_stated_run_field_fidelity(
        response=response,
        preferred_model="test-model",
        request=request,
    )

    assert repaired is not None
    assert repaired.requires_clarification is False
    assert "fee_rate" not in repaired.candidate_strategy_draft.extra_parameters
    assert "slippage" not in repaired.candidate_strategy_draft.extra_parameters
    runtime = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )._to_runtime_interpretation(repaired, request=request)
    result = await interpret_stage_async(
        state=RunState.new(
            current_user_message=message,
            recent_thread_history=[],
        ),
        user=request.user,
        latest_task_snapshot=request.latest_task_snapshot,
        selected_thread_metadata={"last_stage_outcome": "await_approval"},
        structured_interpreter=lambda _: runtime,
    )
    assert result.outcome == "ready_for_confirmation"
    strategy = result.decision.candidate_strategy_draft
    assert strategy.date_range == {
        "start": "2023-02-01",
        "end": "2023-11-30",
    }
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005


@pytest.mark.asyncio
async def test_runtime_readiness_cannot_skip_cost_fidelity_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    message = (
        "Test MSFT with $12,000 for calendar year 2022 using daily data, "
        "SPY as benchmark, a 10 bps fee and 5 bps slippage."
    )
    calls: list[str] = []

    async def fake_json_schema(*, schema_name, schema_model, **kwargs):
        del kwargs
        calls.append(schema_name)
        if schema_name == "LLMInterpretationResponse":
            response = _primary_cost_response()
            response.candidate_strategy_draft.date_range_raw_text = (
                "calendar year 2022"
            )
            response.candidate_strategy_draft.date_range_intent = LLMDateRangeIntent(
                kind="calendar_year",
                year=2022,
                confidence=0.98,
                evidence="calendar year 2022",
            )
            response.candidate_strategy_draft.evidence_spans["date_range"] = (
                "calendar year 2022"
            )
            return response
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model.model_validate(_audit_payload())
        if schema_name == "FocusedDateWindowExtraction":
            return schema_model(
                has_date_window=True,
                date_range_raw_text="calendar year 2022",
                date_range_intent=LLMDateRangeIntent(
                    kind="calendar_year",
                    year=2022,
                    confidence=0.98,
                    evidence="calendar year 2022",
                ),
                confidence=0.98,
                evidence="calendar year 2022",
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol, **_: ResolvedAssetStub(symbol.strip().upper(), "equity"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    result = await OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    ).ainvoke(_request(message))

    assert calls == [
        "LLMInterpretationResponse",
        "StatedRunFieldFidelityAudit",
        "FocusedDateWindowExtraction",
    ]
    assert result is not None
    strategy = result.candidate_strategy_draft
    assert strategy.extra_parameters["fee_rate"] == 0.001
    assert strategy.extra_parameters["slippage"] == 0.0005
    assert strategy.extra_parameters["field_provenance"]["fee_rate"] == "explicit_user"
    assert (
        strategy.extra_parameters["field_provenance"]["slippage"] == "explicit_user"
    )


@pytest.mark.asyncio
async def test_runtime_blocks_confirmation_when_cost_audit_cannot_ground_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module

    message = (
        "Test MSFT with $12,000 for calendar year 2022 using daily data, "
        "SPY as benchmark, a 10 bps fee and 5 bps slippage."
    )

    async def fake_json_schema(*, schema_name, schema_model, **kwargs):
        del kwargs
        if schema_name == "LLMInterpretationResponse":
            response = _primary_cost_response()
            response.candidate_strategy_draft.date_range_raw_text = (
                "calendar year 2022"
            )
            response.candidate_strategy_draft.date_range_intent = LLMDateRangeIntent(
                kind="calendar_year",
                year=2022,
                confidence=0.98,
                evidence="calendar year 2022",
            )
            response.candidate_strategy_draft.evidence_spans["date_range"] = (
                "calendar year 2022"
            )
            return response
        if schema_name == "StatedRunFieldFidelityAudit":
            return schema_model.model_validate(
                _audit_payload(
                    fee_rate=None,
                    fee_span=None,
                    slippage=None,
                    slippage_span=None,
                )
            )
        if schema_name == "FocusedDateWindowExtraction":
            return schema_model(
                has_date_window=True,
                date_range_raw_text="calendar year 2022",
                date_range_intent=LLMDateRangeIntent(
                    kind="calendar_year",
                    year=2022,
                    confidence=0.98,
                    evidence="calendar year 2022",
                ),
                confidence=0.98,
                evidence="calendar year 2022",
            )
        raise AssertionError(f"unexpected schema: {schema_name}")

    monkeypatch.setattr(
        interpreter_module,
        "openrouter_structured_model_candidates",
        lambda **_: ["test-model"],
    )
    monkeypatch.setattr(
        interpreter_module,
        "resolve_asset",
        lambda symbol, **_: ResolvedAssetStub(symbol.strip().upper(), "equity"),
    )
    monkeypatch.setattr(
        interpreter_module,
        "invoke_openrouter_json_schema",
        fake_json_schema,
    )

    result = await OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    ).ainvoke(_request(message))

    assert result is not None
    assert result.requires_clarification is True
    assert "assumption" in result.missing_required_fields
    assert "execution_cost_evidence_unresolved" in result.reason_codes
    assert "fee_rate" not in result.candidate_strategy_draft.extra_parameters
    assert "slippage" not in result.candidate_strategy_draft.extra_parameters


def test_validated_cost_evidence_channel_is_unforgeable_from_model_output() -> None:
    draft = LLMStrategyDraft.model_validate(
        {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["MSFT"],
            "extra_parameters": {"fee_rate": 0.001, "slippage": 0.0005},
            "field_provenance": {
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
            "_validated_execution_cost_evidence": {
                "fee_rate": (0.001, None),
                "slippage": (0.0005, None),
            },
        }
    )

    assert draft._validated_execution_cost_evidence == {}
    strategy = _strategy_from_llm(
        draft,
        current_user_message="Use a 10 bps fee and 5 bps slippage.",
    )
    assert "fee_rate" not in strategy.extra_parameters
    assert "slippage" not in strategy.extra_parameters
