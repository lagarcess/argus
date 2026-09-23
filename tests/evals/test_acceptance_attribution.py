"""#653 allowlisted attribution: confirmed capture shape only."""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from faker import Faker

from tests.evals.acceptance_attribution import (
    FAILURE_METADATA_KEYS,
    FORBIDDEN_EXPORT_KEYS,
    STORED_RESEARCH_DECLINED_CODE,
    allowlisted_cost_row,
    allowlisted_failure_metadata,
    allowlisted_route_row,
)

REPO = Path(__file__).resolve().parents[2]
EXPORTERS = (
    REPO / "docs/reports/evidence/2026-09-14-acceptance/drivers/export_replay.py",
    REPO
    / "docs/reports/evidence/2026-09-17-final-acceptance-e8a4ccee"
    / "drivers/export_replay.py",
)

fake = Faker()


def test_declined_reason_code_matches_runtime_owner() -> None:
    tree = ast.parse((REPO / "src/argus/agent_runtime/research_grounded.py").read_text())
    assigned = next(
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "DECLINED_REASON_CODE"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
    )
    assert assigned == STORED_RESEARCH_DECLINED_CODE


def test_export_shape_is_exactly_the_confirmed_keys() -> None:
    exported = allowlisted_failure_metadata({})

    assert tuple(exported) == FAILURE_METADATA_KEYS
    assert set(exported).isdisjoint(FORBIDDEN_EXPORT_KEYS)
    assert "clarification_payload_reason" not in exported
    assert "clarification_kind" not in exported
    assert "unsupported_categories" not in exported
    assert "route_receipt_kinds" not in exported
    assert "recovery_code" not in exported


def test_top_level_clarification_reason_is_exported() -> None:
    exported = allowlisted_failure_metadata(
        {
            "clarification": {
                "reason_code": "unsupported_time_granularity",
                "payload": {},
            }
        }
    )

    assert exported["clarification_reason"] == "unsupported_time_granularity"


def test_top_level_owner_wins_over_nested_payload_reason() -> None:
    exported = allowlisted_failure_metadata(
        {
            "clarification": {
                "reason_code": "unsupported_time_granularity",
                "payload": {"reason_code": "stale_nested_reason"},
            }
        }
    )

    assert exported["clarification_reason"] == "unsupported_time_granularity"
    assert "stale_nested_reason" not in json.dumps(exported)


def test_nested_payload_reason_is_not_the_clarification_owner() -> None:
    exported = allowlisted_failure_metadata(
        {"clarification": {"payload": {"reason_code": "stale_nested_reason"}}}
    )

    assert exported["clarification_reason"] is None
    assert "stale_nested_reason" not in json.dumps(exported)


def test_research_declined_and_capability_footer_booleans() -> None:
    stored_declined = allowlisted_failure_metadata({"research": {"declined": True}})
    stored_footer = allowlisted_failure_metadata(
        {"research": {"capability_footer_appended": False}}
    )
    missing = allowlisted_failure_metadata({"research": {"shape": "balanced"}})

    assert stored_declined["research_declined"] is True
    assert stored_footer["research_capability_footer_appended"] is False
    assert missing["research_declined"] is None
    assert missing["research_capability_footer_appended"] is None


def test_interpreter_reason_and_capability_verdict() -> None:
    stored = allowlisted_failure_metadata(
        {
            "reason_codes": [
                STORED_RESEARCH_DECLINED_CODE,
                "scenario_contract_from_horizon",
            ],
            "capability_verdict": "answer_only",
        }
    )
    harness = allowlisted_failure_metadata(
        {},
        harness_capability_verdict="unsupported",
    )
    missing = allowlisted_failure_metadata({})

    assert stored["interpreter_reason_codes"] == [
        STORED_RESEARCH_DECLINED_CODE,
        "scenario_contract_from_horizon",
    ]
    assert stored["research_declined"] is True
    assert stored["capability_verdict"] == "answer_only"
    assert stored["capability_verdict_measurement_harness_derived"] is False
    assert harness["capability_verdict"] == "unsupported"
    assert harness["capability_verdict_measurement_harness_derived"] is True
    assert missing["interpreter_reason_codes"] is None
    assert missing["capability_verdict"] is None
    assert missing["capability_verdict_measurement_harness_derived"] is False


def test_export_shape_does_not_leak_customer_text() -> None:
    customer_text = fake.paragraph()
    prompt = fake.sentence()
    user_id = fake.uuid4()
    conversation_id = fake.uuid4()
    exported = allowlisted_failure_metadata(
        {
            "assistant_response": customer_text,
            "assistant_prompt": prompt,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "clarification": {
                "reason_code": "missing_period",
                "kind": "clarification",
                "prompt_source": "degraded_fallback",
                "requested_field": "date_range",
                "payload": {
                    "reason_code": "stale_nested_reason",
                    "raw_value": customer_text,
                    "strategy": {"note": prompt},
                },
                "options": [{"label": customer_text}],
            },
            "research": {
                "declined": True,
                "capability_footer_appended": True,
                "answer": customer_text,
            },
            "recovery": {"code": "runtime_failure"},
            "reason_codes": [STORED_RESEARCH_DECLINED_CODE],
            "capability_verdict": "answer_only",
        }
    )
    serialized = json.dumps(exported, default=str)

    assert tuple(exported) == FAILURE_METADATA_KEYS
    assert customer_text not in serialized
    assert prompt not in serialized
    assert user_id not in serialized
    assert conversation_id not in serialized
    assert "stale_nested_reason" not in serialized
    assert set(exported).isdisjoint(FORBIDDEN_EXPORT_KEYS)
    leaked = _string_leaves(exported)
    assert customer_text not in leaked
    assert prompt not in leaked


def test_route_and_cost_rows_drop_identifiers() -> None:
    user_id = fake.uuid4()
    message_id = fake.uuid4()
    route = allowlisted_route_row(
        {
            "task": "clarification",
            "schema_name": "ClarificationResponse",
            "outcome": "skipped",
            "failure_mode": "turn_call_allowance_exhausted",
            "user_id": user_id,
            "message_id": message_id,
            "content": fake.sentence(),
            "metadata": {"request_id": fake.uuid4()},
        }
    )
    cost = allowlisted_cost_row(
        {
            "task": "clarification",
            "status": "recorded",
            "user_id": user_id,
            "message_id": message_id,
            "request_id": fake.uuid4(),
        }
    )

    assert route["task"] == "clarification"
    assert set(route).isdisjoint(FORBIDDEN_EXPORT_KEYS)
    assert user_id not in json.dumps(route)
    assert message_id not in json.dumps(cost)


def test_prose_is_rejected_as_a_reason_code() -> None:
    exported = allowlisted_failure_metadata(
        {
            "clarification": {"reason_code": fake.sentence()},
            "reason_codes": [fake.paragraph(), "missing_period"],
        }
    )

    assert exported["clarification_reason"] is None
    assert exported["interpreter_reason_codes"] == ["missing_period"]


def test_historical_exporters_call_the_durable_owner() -> None:
    for path in EXPORTERS:
        source = path.read_text()
        tree = ast.parse(source)
        imported = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        assert "allowlisted_failure_metadata" in imported
        assert (
            "(meta.get('clarification') or {}).get('payload',{}).get('reason_code')"
            not in source
        )
        assert "payload" not in _clarification_reason_sources(tree)


def _clarification_reason_sources(tree: ast.AST) -> set[str]:
    sources: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(_is_clarification_reason_target(target) for target in node.targets):
            continue
        for child in ast.walk(node.value):
            if isinstance(child, ast.Constant) and child.value == "payload":
                sources.add("payload")
    return sources


def _is_clarification_reason_target(target: ast.AST) -> bool:
    return (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "clarification_reason"
    )


def _string_leaves(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        leaves: list[str] = []
        for item in value.values():
            leaves.extend(_string_leaves(item))
        return leaves
    if isinstance(value, list):
        leaves = []
        for item in value:
            leaves.extend(_string_leaves(item))
        return leaves
    return []
