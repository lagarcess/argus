"""Discovery declarations admit exactly the targets the existing executor can use."""

from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime.discovery.composer import _search_query
from argus.agent_runtime.interpreter.discovery_act_guard import (
    _payload_owns_discovery_route,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMInterpretationResponse,
    interpretation_response_model,
)
from argus.agent_runtime.research_tools import (
    PeerExpansionArguments,
    get_research_declarations,
)
from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest
from argus.domain.tool_declaration import ToolCatalog
from faker import Faker
from jsonschema import Draft202012Validator
from pydantic import ValidationError

fake = Faker()


@pytest.fixture
def declaration():
    return next(
        item
        for item in get_research_declarations()
        if item.handler.__name__ == "peer_expansion"
    )


TARGET_CASES = [
    ("category", {"anchor_symbols": ["COST"]}, False),
    ("category", {"category_description": None, "anchor_symbols": ["COST"]}, False),
    ("category", {"category_description": " \n\t", "anchor_symbols": ["COST"]}, False),
    ("category", {"category_description": "warehouse clubs"}, True),
    (
        "category",
        {"category_description": "warehouse clubs", "anchor_symbols": ["COST"]},
        True,
    ),
    *(
        (relationship, facts, valid)
        for relationship in ("peer", "comparison")
        for facts, valid in (
            ({}, False),
            ({"category_description": None, "anchor_symbols": []}, False),
            ({"category_description": " \n\t", "anchor_symbols": ["", " "]}, False),
            ({"anchor_symbols": ["", "COST"]}, True),
            ({"category_description": "warehouse clubs"}, True),
        )
    ),
]


@pytest.mark.parametrize(("relationship", "facts", "valid"), TARGET_CASES)
def test_discovery_target_has_one_admission_contract(
    declaration, relationship, facts, valid
):
    payload = {"relationship": relationship, **facts}
    legacy = AssetDiscoveryRequest.model_validate(payload)
    assert AssetDiscoveryRequest.model_validate_json(legacy.model_dump_json()) == legacy
    assert legacy.has_executable_target() is valid
    assert (_search_query(legacy) is not None) is valid
    response = LLMInterpretationResponse(
        intent="follow_up",
        task_relation="new_task",
        user_goal_summary=fake.sentence(),
        asset_discovery=legacy,
    )
    assert _payload_owns_discovery_route(response) is valid

    arguments = {"request": fake.sentence(), **payload}
    catalog = ToolCatalog((declaration,))
    schema = json.loads(catalog.capability_text())[0]["parameters"]
    response_model = interpretation_response_model(catalog)
    model_call = {
        "intent": "calculate",
        "task_relation": "new_task",
        "user_goal_summary": fake.sentence(),
        "tool_calls": [
            {
                "tool_name": declaration.name,
                "call_id": fake.uuid4(),
                "arguments": arguments,
            }
        ],
    }
    assert Draft202012Validator(schema).is_valid(arguments) is valid
    assert (
        Draft202012Validator(response_model.model_json_schema()).is_valid(model_call)
        is valid
    )
    if valid:
        typed = declaration.validate_arguments(arguments)
        assert typed.relationship == relationship
        assert typed.anchor_symbols == legacy.anchor_symbols
        assert (
            response_model.model_validate(model_call).tool_calls[0].arguments.relationship
            == relationship
        )
    else:
        with pytest.raises(ValueError):
            PeerExpansionArguments.model_validate(arguments)
        with pytest.raises(ValueError):
            declaration.validate_arguments(arguments)
        with pytest.raises(ValidationError):
            response_model.model_validate(model_call)


def test_exact_costco_call_is_rejected_without_rewriting_its_relationship(declaration):
    arguments: dict[str, Any] = {
        "request": "what else in Costco's category could I compare it against?",
        "relationship": "category",
        "anchor_symbols": ["COST"],
        "asset_class_hint": "equity",
        "needs_current_facts": False,
    }
    with pytest.raises(ValueError):
        declaration.validate_arguments(arguments)
    assert arguments["relationship"] == "category"
    assert arguments["anchor_symbols"] == ["COST"]
    assert "category_description" not in arguments


@pytest.mark.asyncio
@pytest.mark.parametrize(("relationship", "facts", "valid"), TARGET_CASES)
async def test_focused_read_uses_the_same_target_admission(
    monkeypatch, relationship, facts, valid
):
    from argus.agent_runtime.interpreter import discovery_focused_read

    from tests.agent_runtime.test_discovery_focused_read import (
        _educational_response,
        _request,
        _wire_read,
    )

    read = discovery_focused_read.FocusedAssetDiscoveryRead(
        asks_argus_to_find_assets=True, relationship=relationship, **facts
    )
    calls = _wire_read(monkeypatch, read)
    result = await discovery_focused_read.focused_discovery_payload_response(
        response=_educational_response(), request=_request()
    )
    assert len(calls) == 1
    assert (result is not None) is valid
    if result is not None:
        assert result.asset_discovery.relationship == relationship
        assert result.asset_discovery.has_executable_target()
