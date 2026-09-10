"""Both structured reads share canonical money roles and evidence ownership."""

from __future__ import annotations

import json
import socket
from itertools import permutations
from pathlib import Path
from typing import Any

import pytest
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph import workflow
from argus.agent_runtime.interpreter.focused_extraction import (
    _accept_focused_capital_roles,
)
from argus.agent_runtime.llm_interpreter_types import FocusedStrategyExtraction
from argus.agent_runtime.runtime import build_workflow_input
from argus.agent_runtime.semantic_integrity import canonical_capital_role
from argus.agent_runtime.stages import confirm
from argus.agent_runtime.state.models import UserState
from langgraph.checkpoint.memory import MemorySaver

ROLE_FIELDS = {
    field.json_schema_extra["x-argus-capital-role"]: name
    for name, field in BacktestStrategyInput.model_fields.items()
    if isinstance(field.json_schema_extra, dict)
    and "x-argus-capital-role" in field.json_schema_extra
}


@pytest.fixture(autouse=True)
def provider_free_projection(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_ENABLE_PERSONALIZATION_MEMORY", "false")
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")
    monkeypatch.setenv("OPENROUTER_API_KEY", "dummy-scripted-financial-projection")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", "scripted-financial-model")
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "")
    attempts = []

    def forbidden_network(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("A replay must use only its scripted replies")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(confirm, "_market_clock_for_strategy", lambda _: None)
    yield
    assert attempts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fixture_name",
    ["financial_role_replies_31b20baf", "financial_role_audit_replies_31b20baf"],
)
async def test_actual_sparse_call_and_focused_reply_reach_real_confirmation(
    monkeypatch: pytest.MonkeyPatch, faker: Any, fixture_name: str
) -> None:
    # These are retained provider bodies, not a reconstruction from a verdict.
    fixture = json.loads(
        (Path(__file__).parent / f"fixtures/{fixture_name}.json").read_text()
    )
    replies = fixture["replies"]
    primary = replies["LLMInterpretationResponse"]
    call = primary["tool_calls"][0]
    focused = replies["FocusedStrategyExtraction"]
    assert "capital_amount" not in call["arguments"]["strategy"]
    assert focused["capital_amount"] == focused["initial_capital"]
    assert focused.get("evidence_spans", {}).get("initial_capital") is None
    quoted_alias = bool(focused.get("evidence_spans", {}).get("capital_amount"))
    calls = []

    async def recorded_reply(*, schema_name, schema_model, **kwargs):
        calls.append(schema_name)
        assert schema_name in replies
        return schema_model.model_validate(replies[schema_name])

    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", recorded_reply)
    graph = workflow.build_workflow(
        tool=object(),
        structured_interpreter=llm_interpreter.OpenRouterStructuredInterpreter(
            contract=build_default_capability_contract()
        ),
        checkpointer=MemorySaver(),
    )

    result = await graph.ainvoke(
        build_workflow_input(
            user=UserState(user_id=faker.uuid4()),
            message=call["arguments"]["strategy"]["raw_user_phrasing"],
        ),
        {"configurable": {"thread_id": faker.uuid4()}},
    )

    assert result["stage_outcome"] == "await_approval"
    state = result["run_state"]
    assert not state.requires_clarification
    assert state.missing_required_fields == []
    assert state.optional_parameter_status.get("ambiguous_fields", []) == []
    assert [item.call_id for item in state.tool_calls] == [call["call_id"]]
    assert state.candidate_strategy_draft.capital_amount == focused["capital_amount"]
    extras = state.candidate_strategy_draft.extra_parameters
    # Independent audit settles an alias; it does not restore the rejected slot.
    assert extras.get("initial_capital") == (
        focused["initial_capital"] if quoted_alias else None
    )
    audit = replies["StatedRunFieldFidelityAudit"]
    for name, audit_name in (("fee_rate", "fee"), ("slippage", "slippage")):
        assert extras[name] == audit[audit_name]["rate"]
        assert extras["field_provenance"][name] == "explicit_user"
    assert state.confirmation_payload is not None
    launch = state.confirmation_payload.model_dump(mode="json")["launch_payload"]
    assert launch["_execution_realism"] == {
        "enabled": True,
        "fee_bps": audit["fee"]["rate"] * 10_000,
        "slippage_bps": audit["slippage"]["rate"] * 10_000,
    }
    assert calls == list(replies)


def _authored_projection(
    *, strategy_type: str, value: float, alias_value: float, span: str | None
) -> tuple[FocusedStrategyExtraction, str, str]:
    """Authored controls are separate from the retained provider fixture."""
    field_name = ROLE_FIELDS[canonical_capital_role(None, strategy_type=strategy_type)]
    message = f"Use {value} for this strategy."
    extraction = FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary=message,
        strategy_type=strategy_type,
        capital_amount=value,
        field_provenance={"capital_amount": "explicit_user"},
        evidence_spans={"capital_amount": span} if span is not None else {},
        **{field_name: alias_value},
    )
    return extraction, message, field_name


@pytest.mark.parametrize("strategy_type", ["buy_and_hold", "dca_accumulation"])
@pytest.mark.parametrize("value", [0, 250])
def test_new_same_role_alias_uses_the_canonical_carriers_quote(strategy_type, value):
    extraction, message, field_name = _authored_projection(
        strategy_type=strategy_type,
        value=value,
        alias_value=value,
        span=f"Use {value}",
    )

    accepted, ambiguities = _accept_focused_capital_roles(
        extraction, base_response=None, current_message=message
    )

    assert getattr(accepted, field_name) == value
    assert accepted.capital_amount == value
    assert ambiguities == []


@pytest.mark.parametrize("strategy_type", ["buy_and_hold", "dca_accumulation"])
@pytest.mark.parametrize("value", [0, 250])
@pytest.mark.parametrize("invalid", ["different_value", "missing_quote", "other_turn"])
def test_alias_needs_the_same_value_and_a_current_quote(strategy_type, value, invalid):
    extraction, message, field_name = _authored_projection(
        strategy_type=strategy_type,
        value=value,
        alias_value=value + 1 if invalid == "different_value" else value,
        span=(
            None
            if invalid == "missing_quote"
            else "A quote from a different turn"
            if invalid == "other_turn"
            else f"Use {value}"
        ),
    )

    accepted, ambiguities = _accept_focused_capital_roles(
        extraction, base_response=None, current_message=message
    )

    assert accepted.capital_amount == value
    assert getattr(accepted, field_name) is None
    assert [(item.field_name, float(item.raw_value)) for item in ambiguities] == [
        (field_name, getattr(extraction, field_name))
    ]


@pytest.mark.parametrize(("source_role", "target_role"), permutations(ROLE_FIELDS, 2))
@pytest.mark.parametrize("value", [0, 250])
def test_new_role_cannot_borrow_an_equal_valued_other_roles_quote(
    source_role, target_role, value
):
    quote = f"Use {value} for the stated role"
    target_field = ROLE_FIELDS[target_role]
    extraction = FocusedStrategyExtraction(
        is_testable_strategy=True,
        user_goal_summary=quote,
        strategy_type="dca_accumulation",
        capital_amount=value,
        field_provenance={"capital_amount": source_role},
        evidence_spans={"capital_amount": quote},
        **{target_field: value},
    )

    accepted, ambiguities = _accept_focused_capital_roles(
        extraction, base_response=None, current_message=quote
    )

    assert accepted.capital_amount == value
    assert getattr(accepted, target_field) is None
    assert [(item.field_name, float(item.raw_value)) for item in ambiguities] == [
        (target_field, value)
    ]
