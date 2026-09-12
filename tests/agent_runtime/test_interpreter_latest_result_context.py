"""The interpreter reads the latest run's configuration and headline facts,
never the stored card's chart series, markers, tool cards or trades."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.interpreter.latest_result_context import (
    LATEST_RESULT_FACT_IDS,
    latest_result_interpreter_context,
)
from argus.agent_runtime.interpreter.run_field_audits import (
    _latest_result_fact_bank_for_routing,
)
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import ArtifactReference, TaskSnapshot, UserState
from argus.api.schemas import BacktestRun
from argus.domain.backtest_message_projection import result_fact_bank

FIXTURES = Path(__file__).resolve().parents[1] / "evals" / "result_readout_fixtures.json"
CASES = ("docn_buyhold_test_only", "dca_costs_test_only", "indicator_sparse_test_only")
BULK_KEYS = frozenset({"chart", "series", "markers", "trades", "tool_result_cards"})
LATEST_RESULT_LABEL = "Latest result fact bank JSON, if any: "
# Bounded by construction: configuration plus reader-word facts, whatever the run's length.
MAX_CONTEXT_CHARS = 4000


def _stored_reference(case_id: str) -> ArtifactReference:
    cases = json.loads(FIXTURES.read_text())["cases"]
    run = BacktestRun.model_validate(next(c["run"] for c in cases if c["id"] == case_id))
    metadata = result_fact_bank(run)
    # A stored card also carries the chat tool cards, which repeat the chart.
    metadata["result_card"] = {
        **(metadata.get("result_card") or {}),
        "tool_result_cards": [{"chart": metadata.get("chart")}],
    }
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id=str(run.id),
        artifact_status="completed",
        metadata=metadata,
    )


def _request(reference: ArtifactReference | None) -> InterpretationRequest:
    return InterpretationRequest(
        current_user_message="Why did it fall so much along the way?",
        latest_task_snapshot=TaskSnapshot(
            latest_task_type="results_explanation",
            completed=True,
            latest_backtest_result_reference=reference,
        ),
        user=UserState(user_id="u-latest-result", language_preference="en"),
    )


def _context_message(request: InterpretationRequest) -> str:
    interpreter = OpenRouterStructuredInterpreter(
        contract=build_default_capability_contract()
    )
    return str(interpreter._messages(request)[1].content)


def _embedded_latest_result(request: InterpretationRequest) -> Any:
    context = _context_message(request)
    start = context.index(LATEST_RESULT_LABEL) + len(LATEST_RESULT_LABEL)
    return json.loads(context[start : context.index("\n", start)])


def _keys(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


@pytest.mark.parametrize("case_id", CASES)
def test_the_interpreter_reads_configuration_and_headline_facts_not_the_stored_card(
    case_id: str,
) -> None:
    reference = _stored_reference(case_id)

    embedded = _embedded_latest_result(_request(reference))

    assert embedded == latest_result_interpreter_context(reference)
    assert not BULK_KEYS & set(_keys(embedded))
    assert len(json.dumps(embedded)) < MAX_CONTEXT_CHARS
    assert set(embedded["facts"]) <= set(LATEST_RESULT_FACT_IDS)
    assert embedded["facts"]["total_return"]
    assert embedded["configuration"]["asset_universe"] == [
        symbol.upper() for symbol in reference.metadata["symbols"]
    ]


def test_the_routing_audit_reads_the_same_facts() -> None:
    reference = _stored_reference("dca_costs_test_only")

    assert (
        _latest_result_fact_bank_for_routing(_request(reference))
        == latest_result_interpreter_context(reference)["facts"]
    )


def test_a_malformed_reference_still_reads_its_facts() -> None:
    reference = _stored_reference("docn_buyhold_test_only")
    reference.metadata["config_snapshot"] = "not a snapshot"

    context = latest_result_interpreter_context(reference)

    assert isinstance(context["configuration"], dict)
    assert context["facts"]["symbols"]


def test_without_a_result_the_interpreter_reads_none() -> None:
    assert f"{LATEST_RESULT_LABEL}none" in _context_message(_request(None))
