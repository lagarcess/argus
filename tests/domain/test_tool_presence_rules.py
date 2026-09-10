"""Presence requirements preserve known zero and do not select an unknown."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

import pytest
from argus.domain.tool_contracts import (
    LocalizedText,
    ToolCall,
    ToolCardPresentation,
    ToolInputFact,
    ToolOutcome,
)
from argus.domain.tool_declaration import (
    ToolCardBinding,
    ToolDeclaration,
    ToolPolicy,
    ToolProgressTemplate,
)
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, create_model


class PresenceArguments(BaseModel):
    mode: Literal["ordinary", "named"]
    amount: float | None = None
    enabled: bool | None = None
    text: str | None = None
    labels: list[str] = Field(default_factory=list)


def echo(arguments: PresenceArguments) -> PresenceArguments:
    return arguments


def card(arguments: PresenceArguments, outcome: ToolOutcome) -> ToolCardPresentation:
    return ToolCardPresentation(
        title=LocalizedText(locale_key="tools.echo.title"),
        inputs=[
            ToolInputFact(
                name=name, label=LocalizedText(locale_key="tools.echo.title"), value=value
            )
            for name, value in arguments.model_dump(include={"amount", "text"}).items()
        ],
    )


@pytest.fixture
def declaration():
    from argus.domain.tool_declaration import RequireAnyPresent

    return ToolDeclaration(
        name="echo",
        description="Retain the original typed facts.",
        handler=echo,
        policy=ToolPolicy(editable_fields=("text",)),
        progress=ToolProgressTemplate(locale_key="tools.echo.progress"),
        card=ToolCardBinding(card_type="facts", version=1, presenter=card),
        rules=(
            RequireAnyPresent(("amount", "enabled", "text", "labels")),
            RequireAnyPresent(("text",), when=("mode", "named")),
        ),
    )


@pytest.mark.parametrize(
    ("facts", "valid"),
    [
        ({}, False),
        ({"amount": None, "text": None, "labels": []}, False),
        ({"text": " \n\t", "labels": ["", " "]}, False),
        ({"amount": 0}, True),
        ({"enabled": False}, True),
        ({"labels": [" ", "a"]}, True),
        ({"text": "named"}, True),
    ],
)
def test_presence_schema_and_runtime_agree_without_truthiness_fallbacks(
    declaration, facts, valid
):
    payload = {"mode": "ordinary", **facts}
    assert (
        Draft202012Validator(declaration.tool_schema()["parameters"]).is_valid(payload)
        is valid
    )
    if valid:
        arguments = declaration.validate_arguments(payload)
        assert arguments.model_dump(include=set(facts)) == facts
    else:
        with pytest.raises(ValueError):
            declaration.validate_arguments(payload)


def test_conditional_requirement_uses_the_typed_discriminator(declaration):
    payload = {"mode": "named", "amount": 0}
    with pytest.raises(ValueError):
        declaration.validate_arguments(payload)
    assert not Draft202012Validator(declaration.tool_schema()["parameters"]).is_valid(
        payload
    )


def test_presence_rules_do_not_lock_recompute_or_mark_blanks_as_unknown(declaration):
    arguments = {"mode": "ordinary", "amount": 0}
    revised = declaration.recompute_arguments(arguments, {"text": "caption"})
    assert revised.amount == 0
    assert revised.text == "caption"
    result = declaration.result_card(
        call=ToolCall(tool_name=declaration.name, call_id="echo_1", arguments=arguments),
        outcome=ToolOutcome(
            status="succeeded", result=PresenceArguments(**arguments).model_dump()
        ),
        artifact_id="artifact_1",
    )
    assert not any(fact.unknown for fact in result.presentation.inputs)


@pytest.mark.parametrize("fields", [(), ("text", "text"), ("missing",)])
def test_presence_rule_rejects_undeclared_or_ambiguous_fields(declaration, fields):
    from argus.domain.tool_declaration import RequireAnyPresent

    with pytest.raises(ValueError):
        replace(declaration, rules=(RequireAnyPresent(fields),))


@pytest.mark.parametrize(
    "when", [("missing", "named"), ("mode", "missing"), ("text", "named")]
)
def test_presence_condition_must_reference_a_required_declared_literal(declaration, when):
    from argus.domain.tool_declaration import RequireAnyPresent

    with pytest.raises(ValueError):
        replace(declaration, rules=(RequireAnyPresent(("text",), when=when),))


@pytest.mark.parametrize("default", [0, False, "default"])
def test_presence_fields_cannot_silently_supply_a_populated_default(default):
    from argus.domain.tool_declaration import RequireAnyPresent

    model = create_model("DefaultPresence", value=(float | bool | str | None, default))
    with pytest.raises(ValueError):
        RequireAnyPresent(("value",)).validate_definition(model)
