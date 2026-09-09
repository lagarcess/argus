"""Declared objects reject lost facts while declared maps retain their own keys."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from argus.domain.tool_contracts import LocalizedText, ToolCardPresentation
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolCatalog,
    ToolDeclaration,
    ToolPolicy,
    ToolProgressTemplate,
)
from faker import Faker
from pydantic import BaseModel, Field, ValidationError, field_validator

fake = Faker()


class LooseValue(BaseModel):
    amount: float | None = Field(default=0, ge=0)
    extra_parameters: dict[str, Any] = Field(default_factory=dict)


class NamedValue(BaseModel):
    label: str

    @field_validator("label")
    @classmethod
    def strip_label(cls, value: str) -> str:
        return value.strip()


class BoundaryArguments(BaseModel):
    detail: LooseValue | None = None
    items: list[LooseValue] = Field(default_factory=list)
    choice: LooseValue | NamedValue | None = None
    by_name: dict[str, LooseValue] = Field(default_factory=dict)
    extra_parameters: dict[str, Any] = Field(default_factory=dict)


def echo_arguments(arguments: BoundaryArguments) -> BoundaryArguments:
    return arguments


@pytest.fixture
def declaration() -> ToolDeclaration:
    return ToolDeclaration(
        name="boundary_echo",
        description="Return declared input facts unchanged.",
        handler=echo_arguments,
        policy=ToolPolicy(),
        progress=ToolProgressTemplate(locale_key="tools.echo.progress"),
        card=ToolCardBinding(
            card_type="facts",
            version=1,
            presenter=lambda _arguments, _outcome: ToolCardPresentation(
                title=LocalizedText(locale_key="tools.echo.title")
            ),
        ),
    )


def _parse(boundary: str, declaration: ToolDeclaration, arguments: dict[str, Any]):
    if boundary == "runtime":
        return declaration.validate_arguments(arguments)
    from argus.agent_runtime.llm_interpreter_types import interpretation_response_model

    response = interpretation_response_model(ToolCatalog((declaration,))).model_validate(
        {
            "intent": "calculate",
            "task_relation": "new_task",
            "user_goal_summary": fake.sentence(),
            "assistant_response": fake.sentence(),
            "tool_calls": [
                {
                    "tool_name": declaration.name,
                    "call_id": fake.uuid4(),
                    "arguments": arguments,
                }
            ],
        }
    )
    return response.tool_calls[0].arguments


@pytest.mark.parametrize("boundary", ["runtime", "interpreter"])
@pytest.mark.parametrize(
    "arguments",
    [
        {"detail": {"amount": 0, "unknown": 0}},
        {"items": [{"amount": None, "unknown": 0}]},
        {"choice": {"label": "named", "unknown": 0}},
        {"by_name": {"item": {"amount": 0, "unknown": 0}}},
    ],
    ids=["optional", "list", "union", "typed-map-value"],
)
def test_unknown_nested_typed_fields_are_rejected_before_discard(
    declaration, boundary, arguments
):
    with pytest.raises(ValidationError) as rejected:
        _parse(boundary, declaration, arguments)
    assert any(error["type"] == "extra_forbidden" for error in rejected.value.errors())


@pytest.mark.parametrize("boundary", ["runtime", "interpreter"])
def test_declared_maps_zero_null_defaults_and_validators_survive(declaration, boundary):
    maps = {"arbitrary": {"unknown": [0, None]}}
    arguments = {
        "detail": {"amount": None, "extra_parameters": maps},
        "items": [{"amount": 0}],
        "choice": {"label": "  named  "},
        "by_name": {"defaulted": {}},
        "extra_parameters": maps,
    }
    parsed = _parse(boundary, declaration, arguments)
    assert isinstance(parsed, BoundaryArguments)
    assert parsed.detail.amount is None
    assert parsed.items[0].amount == 0
    assert parsed.by_name["defaulted"].amount == 0
    assert parsed.choice.label == "named"
    assert parsed.extra_parameters == parsed.detail.extra_parameters == maps
    with pytest.raises(ValidationError):
        _parse(boundary, declaration, {"detail": {"amount": -1}})


@pytest.mark.asyncio
async def test_invocation_withholds_result_for_undeclared_nested_fact(declaration):
    outcome = await declaration.invoke({"detail": {"amount": 0, "unknown": 0}})
    assert outcome.status == "invalid"
    assert outcome.result is None


@pytest.mark.parametrize("boundary", ["runtime", "interpreter"])
def test_tool_schemas_close_typed_objects_and_keep_open_map_contracts(
    declaration, boundary
):
    if boundary == "runtime":
        schema = declaration.tool_schema()["parameters"]
        argument_schema = schema
    else:
        from argus.agent_runtime.llm_interpreter_types import (
            interpretation_response_model,
        )

        schema = interpretation_response_model(
            ToolCatalog((declaration,))
        ).model_json_schema()
        call_ref = schema["properties"]["tool_calls"]["items"]["$ref"]
        call_schema = schema["$defs"][call_ref.rsplit("/", 1)[-1]]
        arguments_ref = call_schema["properties"]["arguments"]["$ref"]
        argument_schema = schema["$defs"][arguments_ref.rsplit("/", 1)[-1]]
    assert argument_schema["additionalProperties"] is False
    assert (
        argument_schema["properties"]["extra_parameters"]["additionalProperties"] is True
    )
    nested = [
        value
        for value in schema["$defs"].values()
        if value.get("title") in {"LooseValue", "NamedValue"}
    ]
    assert len(nested) == 2
    assert all(value.get("additionalProperties") is False for value in nested)


def test_tool_model_derivation_does_not_change_legacy_model_reads(declaration):
    replacement = replace(declaration, name="other_boundary_echo")
    for tool in (declaration, replacement):
        with pytest.raises(ValidationError):
            tool.validate_arguments({"detail": {"unknown": 0}})
    assert LooseValue.model_validate({"unknown": 0}).amount == 0
    assert BoundaryArguments.model_validate({"unknown": 0}).detail is None


@pytest.mark.parametrize("boundary", ["runtime", "interpreter"])
@pytest.mark.parametrize("nested", [False, True], ids=["strategy", "date-intent"])
def test_real_backtest_call_rejects_unknown_typed_financial_and_temporal_keys(
    boundary, nested
):
    from argus.agent_runtime.tools.registered_backtest import get_backtest_declaration

    tool = get_backtest_declaration()
    strategy = {
        "strategy_type": "dca_accumulation",
        "initial_capital": 0,
        "recurring_contribution": 0,
        "cadence": "monthly",
        "date_range_intent": {"kind": "calendar_year", "year": 2024},
        "extra_parameters": {"context": {"unknown": 0}},
    }
    parsed = _parse(boundary, tool, {"strategy": strategy})
    assert parsed.strategy.initial_capital == 0
    assert parsed.strategy.recurring_contribution == 0
    assert parsed.strategy.date_range_intent.year == 2024
    assert parsed.strategy.extra_parameters == strategy["extra_parameters"]
    target = strategy["date_range_intent"] if nested else strategy
    target["unknown"] = 0
    with pytest.raises(ValidationError) as rejected:
        _parse(boundary, tool, {"strategy": strategy})
    assert any(error["type"] == "extra_forbidden" for error in rejected.value.errors())
