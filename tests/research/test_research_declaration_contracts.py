"""The catalog promises the result boundaries its callables enforce."""

from __future__ import annotations

import json
from typing import Any

import pytest
from argus.agent_runtime.research_tools import (
    ResearchToolResult,
    get_research_declarations,
)
from argus.domain.tool_declaration import ToolCatalog
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from tests.research.test_registered_research_tools import _packet


@pytest.fixture
def declarations():
    return {item.name: item for item in get_research_declarations()}


def _figures() -> dict[str, Any]:
    packet = _packet()
    row = packet.rows[0].model_copy(update={"value": 0.0})
    return ResearchToolResult(
        answer=f"{row.subject} is {row.value} {row.unit}.",
        rows=(row,),
        sources=packet.sources,
    ).model_dump(mode="json")


def _candidates() -> dict[str, Any]:
    row = _packet().rows[0]
    return ResearchToolResult(
        relationship="peer",
        peers=({"name": row.subject, "symbol": row.symbol},),
    ).model_dump(mode="json")


def _assert_boundary(declaration, payload: dict[str, Any], *, valid: bool) -> None:
    # Capability answers consume this generated schema; dispatch validates
    # against the actual callable's return model.
    catalog_schema = json.loads(ToolCatalog((declaration,)).capability_text())[0]
    schema = Draft202012Validator(catalog_schema["returns"])
    if valid:
        returned = declaration.result_type.model_validate(payload)
        schema.validate(payload)
        assert returned.model_dump(mode="json") == payload
    else:
        with pytest.raises(ValidationError):
            declaration.result_type.model_validate(payload)
        assert not schema.is_valid(payload)


@pytest.mark.parametrize(
    "tool_name", ["fast_quote", "balanced_lookup", "thorough_research", "screening"]
)
def test_completed_figure_returns_require_rows_and_preserve_zero(
    declarations, tool_name: str
) -> None:
    payload = _figures()
    _assert_boundary(declarations[tool_name], payload, valid=True)
    payload["rows"] = []
    _assert_boundary(declarations[tool_name], payload, valid=False)


@pytest.mark.parametrize(
    "tool_name", ["balanced_lookup", "thorough_research", "screening"]
)
def test_sourced_figure_returns_require_retained_public_sources(
    declarations, tool_name: str
) -> None:
    payload = _figures()
    payload["sources"] = []
    _assert_boundary(declarations[tool_name], payload, valid=False)


def test_fast_quote_preserves_provider_grounded_figures_without_public_sources(
    declarations,
) -> None:
    payload = _figures()
    payload["sources"] = []
    payload["rows"][0]["source_url"] = None
    _assert_boundary(declarations["fast_quote"], payload, valid=True)


@pytest.mark.parametrize("missing_field", ["peers", "relationship"])
def test_candidate_return_requires_verified_candidates_and_the_requested_purpose(
    declarations, missing_field: str
) -> None:
    payload = _candidates()
    _assert_boundary(declarations["peer_expansion"], payload, valid=True)
    payload[missing_field] = [] if missing_field == "peers" else None
    _assert_boundary(declarations["peer_expansion"], payload, valid=False)


def test_candidate_return_does_not_promise_numeric_figures(declarations) -> None:
    payload = _candidates()
    payload["rows"] = _figures()["rows"]
    _assert_boundary(declarations["peer_expansion"], payload, valid=False)


@pytest.mark.parametrize(
    "tool_name", ["fast_quote", "balanced_lookup", "screening", "peer_expansion"]
)
def test_inline_result_contract_does_not_admit_pending_receipts(
    declarations, tool_name: str
) -> None:
    pending = ResearchToolResult(status="pending").model_dump(mode="json")
    _assert_boundary(declarations[tool_name], pending, valid=False)


def test_workflow_return_preserves_flat_pending_receipts_without_completed_facts(
    declarations,
) -> None:
    pending = ResearchToolResult(status="pending").model_dump(mode="json")
    _assert_boundary(declarations["thorough_research"], pending, valid=True)
    pending["rows"] = _figures()["rows"]
    _assert_boundary(declarations["thorough_research"], pending, valid=False)


def test_requested_asset_class_semantics_are_exposed_from_the_canonical_argument(
    declarations,
) -> None:
    from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest

    declaration = declarations["peer_expansion"]
    assert issubclass(declaration.arguments_type, AssetDiscoveryRequest)
    schema = declaration.tool_schema()["parameters"]
    assert schema["properties"]["asset_class_hint"].get("description")
    for hint in (None, "equity", "crypto", "currency_pair"):
        arguments = declaration.validate_arguments(
            {
                "request": "Find related assets",
                "relationship": "comparison",
                "anchor_symbols": ["AAPL"],
                "asset_class_hint": hint,
            }
        )
        assert arguments.asset_class_hint == hint
        assert arguments.relationship == "comparison"
