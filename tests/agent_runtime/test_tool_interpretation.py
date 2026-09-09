"""The catalog owns tool arguments; task intent never selects a question form."""

from __future__ import annotations

from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter_types
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import ResponseIntent, RunState, TaskSnapshot
from faker import Faker
from pydantic import BaseModel, ConfigDict, ValidationError

fake = Faker()


@pytest.mark.parametrize("model", [LLMInterpretationResponse, StructuredInterpretation])
def test_fresh_interpretation_schema_has_four_general_intents(
    model: type[BaseModel],
) -> None:
    assert model.model_json_schema()["properties"]["intent"]["enum"] == [
        "explain",
        "calculate",
        "follow_up",
        "cannot",
    ]


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("beginner_guidance", "explain"),
        ("strategy_drafting", "calculate"),
        ("backtest_execution", "calculate"),
        ("results_explanation", "explain"),
        ("collection_management", "cannot"),
        ("conversation_followup", "follow_up"),
        ("unsupported_or_out_of_scope", "cannot"),
    ],
)
def test_persisted_intents_read_as_canonical_values(legacy: str, canonical: str) -> None:
    snapshot = TaskSnapshot.model_validate({"latest_task_type": legacy})
    run = RunState.model_validate(
        {"current_user_message": fake.sentence(), "intent": legacy}
    )
    assert snapshot.latest_task_type == canonical
    assert run.intent == canonical
    assert snapshot.model_dump()["latest_task_type"] == canonical


def test_presentation_intent_is_not_a_task_intent() -> None:
    assert ResponseIntent(kind="beginner_guidance").kind == "beginner_guidance"


class NumberArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


class LabelArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str


def _number_echo(arguments: NumberArguments) -> NumberArguments:
    return arguments


def _label_echo(arguments: LabelArguments) -> LabelArguments:
    return arguments


def _schema_catalog() -> Any:
    from argus.domain.tool_contracts import LocalizedText, ToolCardPresentation
    from argus.domain.tool_declaration import (
        ToolCardBinding,
        ToolCatalog,
        ToolDeclaration,
        ToolPolicy,
        ToolProgressTemplate,
    )

    return ToolCatalog(
        tuple(
            ToolDeclaration(
                name=name,
                description=f"Return the supplied {name} fact unchanged.",
                handler=handler,
                policy=ToolPolicy(),
                progress=ToolProgressTemplate(locale_key="tools.working"),
                card=ToolCardBinding(
                    card_type="echo",
                    version=1,
                    presenter=lambda _arguments, _outcome: ToolCardPresentation(
                        title=LocalizedText(locale_key="tools.echo.title")
                    ),
                ),
            )
            for name, handler in (
                ("number_echo", _number_echo),
                ("label_echo", _label_echo),
            )
        )
    )


def _response_payload(calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "intent": "calculate" if calls else "explain",
        "task_relation": "new_task",
        "user_goal_summary": fake.sentence(),
        "assistant_response": fake.sentence(),
        "tool_calls": calls,
    }


def _calls(names: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {
            "tool_name": name,
            "call_id": fake.uuid4(),
            "arguments": {"value": index}
            if name == "number_echo"
            else {"label": fake.word()},
        }
        for index, name in enumerate(names)
    ]


@pytest.mark.parametrize(
    "names", [(), ("number_echo", "label_echo"), ("number_echo", "number_echo")]
)
def test_catalog_schema_preserves_zero_multiple_and_repeated_calls(
    names: tuple[str, ...],
) -> None:
    model = llm_interpreter_types.interpretation_response_model(_schema_catalog())
    calls = _calls(names)
    response = model.model_validate(_response_payload(calls))
    assert response.model_dump()["tool_calls"] == calls
    properties = model.model_json_schema()["properties"]
    assert "research_query" not in properties
    assert "asset_discovery" not in properties
    assert "context_question_focus" not in properties
    assert "uses_tool_catalog" not in properties


@pytest.mark.parametrize(
    "bad_arguments", [{"label": "wrong type"}, {"value": 0, "asset_universe": ["AAPL"]}]
)
def test_each_tool_has_only_its_own_typed_arguments(
    bad_arguments: dict[str, Any],
) -> None:
    model = llm_interpreter_types.interpretation_response_model(_schema_catalog())
    calls = _calls(("number_echo",))
    calls[0]["arguments"] = bad_arguments
    with pytest.raises(ValidationError):
        model.model_validate(_response_payload(calls))


def test_call_identity_must_be_distinct_even_for_repeated_tools() -> None:
    model = llm_interpreter_types.interpretation_response_model(_schema_catalog())
    calls = _calls(("number_echo", "number_echo"))
    calls[1]["call_id"] = calls[0]["call_id"]
    with pytest.raises(ValidationError):
        model.model_validate(_response_payload(calls))


def test_call_list_is_bounded_by_the_shared_resource_limit() -> None:
    from argus.domain.tool_contracts import MAX_TOOL_CALLS

    model = llm_interpreter_types.interpretation_response_model(_schema_catalog())
    calls = _calls(("number_echo",) * MAX_TOOL_CALLS)
    assert (
        len(model.model_validate(_response_payload(calls)).tool_calls) == MAX_TOOL_CALLS
    )
    calls.extend(_calls(("label_echo",)))
    with pytest.raises(ValidationError):
        model.model_validate(_response_payload(calls))


@pytest.mark.asyncio
async def test_tool_calls_bypass_strategy_readiness_and_prior_strategy_merge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as module
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import StrategySummary, UserState

    async def forbidden_audit(**_kwargs: Any) -> None:
        raise AssertionError("A tool call cannot enter strategy readiness audits")

    monkeypatch.setattr(module, "_audited_response_ready_for_runtime", forbidden_audit)
    request = InterpretationRequest(
        current_user_message=fake.sentence(),
        user=UserState(user_id=fake.uuid4()),
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(
                strategy_type="dca_accumulation", capital_amount=42
            )
        ),
    )
    calls = _calls(("number_echo", "number_echo"))
    response = LLMInterpretationResponse.model_validate(_response_payload(calls))
    prepared = await module._response_ready_for_runtime(
        response=response, preferred_model="test", request=request
    )
    interpreter = module.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(), tool_catalog=_schema_catalog()
    )
    result = interpreter._to_runtime_interpretation(prepared, request=request)
    assert [call.model_dump() for call in result.tool_calls] == calls
    assert result.candidate_strategy_draft == StrategySummary()
    assert result.unsupported_constraints == []


@pytest.mark.asyncio
async def test_real_interpret_stage_routes_tool_calls_before_strategy_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.stages import interpret as module
    from argus.agent_runtime.state.models import StrategySummary, UserState

    calls = _calls(("number_echo", "label_echo"))
    interpretation = StructuredInterpretation.model_validate(_response_payload(calls))

    def forbidden_merge(**_kwargs: Any) -> None:
        raise AssertionError("A tool call cannot merge a strategy draft")

    monkeypatch.setattr(module, "_strategy_with_contextual_merge", forbidden_merge)
    result = await module.interpret_stage_async(
        state=RunState(current_user_message=fake.sentence()),
        user=UserState(user_id=fake.uuid4()),
        latest_task_snapshot=TaskSnapshot(
            pending_strategy_summary=StrategySummary(strategy_type="buy_and_hold")
        ),
        structured_interpreter=lambda _request: interpretation,
    )
    assert result.outcome == "approved_for_execution"
    assert result.patch["tool_calls"] == calls
    assert result.patch["candidate_strategy_draft"] == StrategySummary().model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize("intent", ["explain", "calculate", "follow_up", "cannot"])
async def test_catalog_zero_calls_do_not_inherit_strategy_or_dispatch_legacy_research(
    monkeypatch: pytest.MonkeyPatch,
    intent: str,
) -> None:
    from argus.agent_runtime import llm_interpreter as interpreter_module
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages import interpret as stage_module
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import StrategySummary, UserState

    async def forbidden_legacy_work(**_kwargs: Any) -> None:
        raise AssertionError("The catalog selected zero tools")

    monkeypatch.setattr(
        interpreter_module, "_audited_response_ready_for_runtime", forbidden_legacy_work
    )
    monkeypatch.setattr(
        stage_module, "knowledge_answer_stage_result", forbidden_legacy_work
    )
    user = UserState(user_id=fake.uuid4())
    snapshot = TaskSnapshot(
        pending_strategy_summary=StrategySummary(strategy_type="buy_and_hold")
    )
    request = InterpretationRequest(
        current_user_message=fake.sentence(), user=user, latest_task_snapshot=snapshot
    )
    interpreter = interpreter_module.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(), tool_catalog=_schema_catalog()
    )
    response = interpreter.response_model.model_validate(
        {**_response_payload([]), "intent": intent}
    )
    prepared = await interpreter_module._response_ready_for_runtime(
        response=response, preferred_model="test", request=request
    )
    interpretation = interpreter._to_runtime_interpretation(prepared, request=request)
    assert interpretation.uses_tool_catalog is True
    result = await stage_module.interpret_stage_async(
        state=RunState(current_user_message=request.current_user_message),
        user=user,
        latest_task_snapshot=snapshot,
        structured_interpreter=lambda _request: interpretation,
    )
    assert result.outcome == "ready_to_respond"
    assert result.patch["assistant_response"] == response.assistant_response
    assert result.patch["candidate_strategy_draft"] == StrategySummary().model_dump()


@pytest.mark.asyncio
async def test_catalog_zero_calls_without_an_answer_are_rejected() -> None:
    from argus.agent_runtime import llm_interpreter as module
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import UserState

    response = llm_interpreter_types.interpretation_response_model(
        _schema_catalog()
    ).model_validate(
        {
            **_response_payload([]),
            "assistant_response": None,
        }
    )
    with pytest.raises(llm_interpreter_types.InterpretationContractError):
        await module._response_ready_for_runtime(
            response=response,
            preferred_model="test",
            request=InterpretationRequest(
                current_user_message=fake.sentence(), user=UserState(user_id=fake.uuid4())
            ),
        )


def test_call_and_strategy_draft_cannot_be_two_executable_inputs() -> None:
    model = llm_interpreter_types.interpretation_response_model(_schema_catalog())
    payload = _response_payload(_calls(("number_echo",)))
    payload["candidate_strategy_draft"] = {"capital_amount": 0}
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_capability_answer_uses_injected_catalog_facts() -> None:
    from argus.agent_runtime.capabilities.answers import capability_fact_packet
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )

    catalog = _schema_catalog()
    answer = capability_fact_packet(
        focus="general",
        contract=build_default_capability_contract(),
        tool_catalog=catalog,
    )
    for declaration in catalog.declarations:
        assert declaration.description in answer
    assert "bank" not in answer.casefold()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "names", [(), ("number_echo", "label_echo"), ("number_echo", "number_echo")]
)
async def test_real_interpreter_consumes_its_generated_catalog_schema(
    monkeypatch: pytest.MonkeyPatch, names: tuple[str, ...]
) -> None:
    from argus.agent_runtime import llm_interpreter as module
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import UserState

    catalog = _schema_catalog()
    calls = _calls(names)
    observed_schemas = []

    async def invoke_schema(**kwargs: Any) -> BaseModel:
        observed_schemas.append(kwargs["schema_model"])
        return kwargs["schema_model"].model_validate(_response_payload(calls))

    async def no_asset_context(**_kwargs: Any) -> None:
        return None

    async def forbidden_audit(**_kwargs: Any) -> None:
        raise AssertionError(
            "Tool/standalone interpretation must not enter strategy audit"
        )

    monkeypatch.setattr(module, "invoke_openrouter_json_schema", invoke_schema)
    monkeypatch.setattr(
        module, "openrouter_structured_model_candidates", lambda: ["test"]
    )
    monkeypatch.setattr(
        module, "provider_asset_resolution_context_for_request", no_asset_context
    )
    monkeypatch.setattr(module, "_audited_response_ready_for_runtime", forbidden_audit)
    interpreter = module.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(), tool_catalog=catalog
    )
    request = InterpretationRequest(
        current_user_message=fake.sentence(), user=UserState(user_id=fake.uuid4())
    )
    result = await interpreter.ainvoke(request)
    assert result is not None
    assert [call.model_dump() for call in result.tool_calls] == calls
    assert observed_schemas == [interpreter.response_model]
    assert catalog.capability_text() in interpreter._system_prompt()


@pytest.mark.asyncio
async def test_repeated_backtest_calls_keep_independent_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime import llm_interpreter as module
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import UserState

    calls = [
        {
            "tool_name": "backtest",
            "call_id": fake.uuid4(),
            "arguments": {
                "strategy": {
                    "strategy_type": "dca_accumulation",
                    "asset_universe": [symbol],
                    "capital_amount": amount,
                    "cadence": cadence,
                    "extra_parameters": {
                        "recurring_contribution": amount,
                        "date_range_intent": {"kind": "calendar_year", "year": year},
                        "field_provenance": {
                            "capital_amount": "explicit_user",
                            "recurring_contribution": "explicit_user",
                            "cadence": "explicit_user",
                        },
                    },
                }
            },
        }
        for symbol, amount, cadence, year in (
            ("AAPL", 0, "weekly", 2022),
            ("MSFT", 200, "monthly", 2023),
        )
    ]

    async def forbidden_audit(**_kwargs: Any) -> None:
        raise AssertionError("A shared question audit cannot rewrite separate tool calls")

    monkeypatch.setattr(module, "_audited_response_ready_for_runtime", forbidden_audit)
    request = InterpretationRequest(
        current_user_message=fake.sentence(), user=UserState(user_id=fake.uuid4())
    )
    response = LLMInterpretationResponse.model_validate(_response_payload(calls))
    prepared = await module._response_ready_for_runtime(
        response=response, preferred_model="test", request=request
    )
    interpreter = module.OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract(), tool_catalog=_schema_catalog()
    )
    result = interpreter._to_runtime_interpretation(prepared, request=request)
    assert [call.call_id for call in result.tool_calls] == [
        call["call_id"] for call in calls
    ]
    assert [
        call.arguments["strategy"]["capital_amount"] for call in result.tool_calls
    ] == [0, 200]
    assert [call.arguments["strategy"]["cadence"] for call in result.tool_calls] == [
        "weekly",
        "monthly",
    ]
    assert [
        call.arguments["strategy"]["asset_universe"] for call in result.tool_calls
    ] == [["AAPL"], ["MSFT"]]
    assert result.candidate_strategy_draft.strategy_type is None

    from argus.agent_runtime.backtest_input import BacktestStrategyInput
    from argus.agent_runtime.interpreter.backtest_calls import prepare_backtest_tool_input

    canonical_dates = []
    for call in result.tool_calls:
        prepared_call = await prepare_backtest_tool_input(
            BacktestStrategyInput.model_validate(call.arguments["strategy"]),
            state=RunState(
                current_user_message=request.current_user_message,
                tool_calls=result.tool_calls,
            ),
            user=request.user,
            call=call,
        )
        canonical_dates.append(
            prepared_call.patch["candidate_strategy_draft"]["date_range"]["start"]
        )
    assert canonical_dates == ["2022-01-01", "2023-01-01"]


class UnknownArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first: float | None = None
    second: float | None = None
    third: float | None = None


def _unknown_echo(arguments: UnknownArguments) -> UnknownArguments:
    return arguments


def _unknown_catalog() -> Any:
    from dataclasses import replace

    from argus.domain.tool_declaration import ExactlyOneUnknown, ToolCatalog

    template = _schema_catalog().declarations[0]
    return ToolCatalog(
        (
            replace(
                template,
                name="unknown_echo",
                handler=_unknown_echo,
                rules=(ExactlyOneUnknown(("first", "second", "third")),),
            ),
        )
    )


@pytest.mark.parametrize("values", [(None, None, 0), (0, 1, 2)])
def test_declared_cross_argument_rules_validate_model_output(
    values: tuple[float | None, ...],
) -> None:
    model = llm_interpreter_types.interpretation_response_model(_unknown_catalog())
    payload = _response_payload(
        [
            {
                "tool_name": "unknown_echo",
                "call_id": fake.uuid4(),
                "arguments": dict(
                    zip(UnknownArguments.model_fields, values, strict=False)
                ),
            }
        ]
    )
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_declared_cross_argument_schema_keeps_zero_distinct_from_unknown() -> None:
    catalog = _unknown_catalog()
    model = llm_interpreter_types.interpretation_response_model(catalog)
    payload = _response_payload(
        [
            {
                "tool_name": "unknown_echo",
                "call_id": fake.uuid4(),
                "arguments": {"first": None, "second": 0, "third": 1},
            }
        ]
    )
    response = model.model_validate(payload)
    assert response.tool_calls[0].arguments.second == 0
    schema = model.model_json_schema()
    argument_schema = next(
        value for name, value in schema["$defs"].items() if name.endswith("ToolArguments")
    )
    assert (
        argument_schema["allOf"]
        == catalog.declarations[0].tool_schema()["parameters"]["allOf"]
    )
