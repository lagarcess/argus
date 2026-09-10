"""Retained selected calls and repairs keep their source and execution facts."""

from __future__ import annotations

import json
import socket
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
import yaml
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.backtest_input import BacktestStrategyInput
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter import backtest_calls, provider_context_assets
from argus.agent_runtime.interpreter.asset_resolution_context import (
    provider_asset_resolution_context_from_extraction,
)
from argus.agent_runtime.llm_interpreter_types import LLMAssetMentionExtraction
from argus.agent_runtime.resolution import resolve_asset_candidate
from argus.agent_runtime.stages import interpret
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.state.models import RunState, TaskSnapshot, UserState
from argus.domain.market_data.assets import ResolvedAsset, resolve_asset
from argus.domain.tool_contracts import ToolCall

_BENCHMARK_CASE = "metric_correctness_eth_default_crypto_benchmark"
_DCA_CASE = "dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run"


@lru_cache
def _captured_cases():
    return json.loads(
        Path(__file__)
        .with_name("fixtures")
        .joinpath("declared_call_repairs_c6c28fef.json")
        .read_text()
    )["cases"]


@pytest.fixture(autouse=True)
def provider_free(monkeypatch):
    monkeypatch.setenv("ARGUS_ASSET_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_MARKET_DATA_PROVIDER_MODE", "synthetic_unit_fixture")
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    monkeypatch.setenv("ARGUS_ENABLE_EXECUTION_REALISM", "true")

    def forbidden(*args, **kwargs):
        raise AssertionError("Network is forbidden in retained-response tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def _retained_provider(monkeypatch, records):
    consumed = []

    async def respond(*, schema_name, schema_model, **kwargs):
        assert len(consumed) < len(records), f"Unexpected read: {schema_name}"
        row = records[len(consumed)]
        assert schema_name == row["schema_name"]
        consumed.append(row["source_line"])
        return schema_model.model_validate(row["body"])

    monkeypatch.setattr(llm_interpreter, "invoke_openrouter_json_schema", respond)
    return consumed


@pytest.mark.asyncio
async def test_retained_dca_audit_keeps_selected_pending_call_scope(monkeypatch, faker):
    rows = deepcopy(_captured_cases()[_DCA_CASE])
    primary = next(
        row
        for row in rows
        if row["schema_name"] == "LLMInterpretationResponse"
        and row["body"].get("tool_calls")
    )
    audits = [
        row
        for row in rows
        if row["source_line"] > primary["source_line"]
        and row["schema_name"] != "ClarificationResponse"
    ]
    consumed = _retained_provider(monkeypatch, audits)
    cases = yaml.safe_load(
        Path(__file__)
        .parents[1]
        .joinpath("evals/measurement_cases/dca_capital_semantics.yaml")
        .read_text()
    )["cases"]
    fixture = next(case for case in cases if case["id"] == _DCA_CASE)
    snapshot_payload = deepcopy(fixture["snapshot"])
    snapshot_payload["pending_strategy_summary"] = snapshot_payload.pop(
        "pending_strategy"
    )
    snapshot = TaskSnapshot.model_validate(snapshot_payload)
    call = ToolCall.model_validate(primary["body"]["tool_calls"][0])
    original = call.model_dump(mode="json")
    clarification = next(
        row["body"] for row in rows if row["schema_name"] == "ClarificationResponse"
    )
    state = RunState(
        current_user_message=fixture["followup_prompt"],
        recent_thread_history=[
            {"role": "assistant", "content": clarification["question"]}
        ],
        intent=primary["body"]["intent"],
        task_relation=primary["body"]["task_relation"],
        semantic_turn_act=primary["body"]["semantic_turn_act"],
        tool_calls=[call],
    )
    original_resolver = llm_interpreter.resolve_asset

    def resolver(symbol, **kwargs):
        # These are the distinct provider identities in the captured request
        # and its existing fixture, not aliases of each other.
        identities = {
            *call.arguments["strategy"]["asset_universe"],
            *snapshot.pending_strategy_summary.asset_universe,
        }
        if symbol.upper() in identities:
            return ResolvedAsset(symbol.upper(), "equity", symbol, symbol)
        return original_resolver(symbol, **kwargs)

    for module in (llm_interpreter, interpret):
        monkeypatch.setattr(module, "resolve_asset", resolver)
    result = await backtest_calls.prepare_backtest_tool_input(
        BacktestStrategyInput.model_validate(call.arguments["strategy"]),
        state=state,
        user=UserState(user_id=faker.uuid4()),
        latest_task_snapshot=snapshot,
        selected_thread_metadata={
            "last_stage_outcome": "await_user_reply",
            "requested_field": "capital_amount",
        },
        call=call,
    )
    assert result.outcome == "ready_for_confirmation"
    assert result.decision.task_relation == state.task_relation
    assert result.decision.semantic_turn_act == state.semantic_turn_act
    assert (
        result.decision.candidate_strategy_draft.asset_universe
        == snapshot.pending_strategy_summary.asset_universe
    )
    assert result.decision.ambiguous_fields == []
    assert (
        result.decision.candidate_strategy_draft.capital_amount
        == call.arguments["strategy"]["capital_amount"]
    )
    assert call.model_dump(mode="json") == original
    assert consumed == [row["source_line"] for row in audits]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "variant,expected",
    [
        ("captured", "ready_for_confirmation"),
        ("compact_pair", "ready_for_confirmation"),
        ("slash_pair", "ready_for_confirmation"),
        ("dash_pair", "ready_for_confirmation"),
        ("provider_name", "ready_for_confirmation"),
        ("case_only", "ready_for_confirmation"),
        ("ambiguous_reference", "ready_for_confirmation"),
        ("different_asset", "needs_clarification"),
        ("invented_reference", "needs_clarification"),
        ("invented_quote", "needs_clarification"),
        ("incidental_reference", "needs_clarification"),
        ("unbound_quote", "needs_clarification"),
        ("reference_prefix", "needs_clarification"),
        ("missing_original_quote", "needs_clarification"),
        ("other_call_source", "needs_clarification"),
        ("different_fallback", "needs_clarification"),
        ("provider_failure", "needs_clarification"),
        ("changed_dates", "needs_clarification"),
    ],
)
async def test_retained_benchmark_repair_preserves_identity_or_disclosure(
    monkeypatch, faker, variant, expected
):
    rows = deepcopy(_captured_cases()[_BENCHMARK_CASE])
    primary = next(
        row["body"] for row in rows if row["schema_name"] == "LLMInterpretationResponse"
    )
    call = ToolCall.model_validate(primary["tool_calls"][0])
    before = call.arguments["strategy"]
    audits = [
        row
        for row in rows
        if row["schema_name"]
        in {"FocusedStrategyExtraction", "FocusedDateWindowExtraction"}
    ]
    focused = audits[0]["body"]
    message = before["raw_user_phrasing"]
    reference = resolve_asset(before["comparison_baseline"])
    alias_values = {
        "compact_pair": reference.raw_symbol.replace("/", ""),
        "slash_pair": reference.raw_symbol,
        "dash_pair": reference.raw_symbol.replace("/", "-"),
        "provider_name": reference.name,
        "case_only": reference.canonical_symbol.casefold(),
    }
    if variant in alias_values:
        focused["comparison_baseline"] = alias_values[variant]
    elif variant == "different_asset":
        focused["comparison_baseline"] = before["asset_universe"][0]
    elif variant in {"invented_reference", "invented_quote", "incidental_reference"}:
        focused["comparison_baseline"] = "Samsung"
        if variant != "invented_reference":
            focused["evidence_spans"]["comparison_baseline"] = "Samsung"
        if variant == "incidental_reference":
            message += "; Samsung is unrelated background."
    elif variant == "unbound_quote":
        focused["evidence_spans"]["comparison_baseline"] = (
            "against a default crypto benchmark"
        )
    elif variant == "reference_prefix":
        # A string prefix inside the quote is not the complete stated reference.
        focused["comparison_baseline"] = focused["comparison_baseline"][:-1]
    elif variant == "missing_original_quote":
        before["evidence_spans"].pop("comparison_baseline")
    elif variant == "other_call_source":
        message = message[: message.index(" against ")]
    elif variant == "different_fallback":
        before["comparison_baseline"] = before["asset_universe"][0]
    elif variant == "changed_dates":
        for audit in audits:
            audit["body"]["date_range_intent"]["end"] = "2024-04-30"
            audit["body"]["date_range"] = {"start": "2024-01-01", "end": "2024-04-30"}
    if variant == "changed_dates":
        # This control supplies a complete typed replacement, so readiness
        # correctly needs no additional date read.
        audits = audits[:1]
    original = call.model_dump(mode="json")
    consumed = _retained_provider(monkeypatch, audits)
    preflight = next(
        row["body"] for row in rows if row["schema_name"] == "LLMAssetMentionExtraction"
    )
    context = provider_asset_resolution_context_from_extraction(
        LLMAssetMentionExtraction.model_validate(preflight),
        resolve_asset_candidate=resolve_asset_candidate,
    )
    state = RunState(
        current_user_message=message,
        intent=primary["intent"],
        task_relation=primary["task_relation"],
        semantic_turn_act=primary["semantic_turn_act"],
        tool_calls=[call],
        normalized_signals={provider_context_assets.TOOL_ASSET_CONTEXT_SIGNAL: context},
    )
    original_resolver = interpret._resolve_asset_candidate
    resolutions = []

    def record_resolution(query, **kwargs):
        if kwargs.get("field") == "comparison_baseline":
            resolutions.append(query.upper())
            if (
                variant == "provider_failure"
                and query.casefold() == focused["comparison_baseline"].casefold()
            ):
                raise ValueError("provider unavailable")
        resolved = original_resolver(query, **kwargs)
        if (
            variant == "ambiguous_reference"
            and query.casefold() == focused["comparison_baseline"].casefold()
        ):
            return replace(
                resolved,
                status="ambiguous",
                provenance=resolved.provenance.model_copy(
                    update={"resolution_status": "ambiguous"}
                ),
            )
        return resolved

    monkeypatch.setattr(interpret, "_resolve_asset_candidate", record_resolution)
    result = await backtest_calls.prepare_backtest_tool_input(
        BacktestStrategyInput.model_validate(before),
        state=state,
        user=UserState(user_id=faker.uuid4()),
        call=call,
    )
    assert result.outcome == expected
    assert call.model_dump(mode="json") == original
    assert consumed == [row["source_line"] for row in audits]
    assert all(count == 1 for count in Counter(resolutions).values())
    if expected == "needs_clarification":
        field = "date_range" if variant == "changed_dates" else "comparison_baseline"
        assert field in {item.field_name for item in result.decision.ambiguous_fields}
        return
    assert (
        result.decision.candidate_strategy_draft.comparison_baseline
        == reference.canonical_symbol
    )
    if variant in {"captured", "ambiguous_reference"}:
        ready = state.model_copy(
            update={
                "candidate_strategy_draft": result.decision.candidate_strategy_draft,
                "optional_parameter_status": result.patch.get(
                    "optional_parameter_status", {}
                ),
            }
        )
        confirmed = confirm_stage(
            state=ready, contract=build_default_capability_contract()
        )
        assert confirmed.outcome == "await_approval"
        payload = confirmed.patch["confirmation_payload"]
        assert payload["launch_payload"]["benchmark_symbol"] == reference.canonical_symbol
        disclosure = next(
            item
            for item in payload["strategy"]["resolution_provenance"]
            if item["field"] == "comparison_baseline"
        )
        assert disclosure["resolution_status"] == (
            "ambiguous" if variant == "ambiguous_reference" else "unsupported"
        )
        assert (
            disclosure["raw_text"].casefold() == focused["comparison_baseline"].casefold()
        )
