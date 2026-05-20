from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from argus.agent_runtime.capabilities.contract import (
    CapabilityContract,
    build_default_capability_contract,
)
from argus.domain.indicators import EXECUTABLE_INDICATORS

MANIFEST_PATH = Path(__file__).with_name("chat_runtime_scenarios.json")


@dataclass(frozen=True)
class ChatRuntimeEvalCase:
    scenario_id: str
    qa_id: str
    priority: str
    prompt: str
    semantic_target: str
    hard_checks: tuple[str, ...]
    forbidden_outcomes: tuple[str, ...]
    judge_rubric: str


def load_eval_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def capability_context_payload(
    contract: CapabilityContract | None = None,
) -> dict[str, Any]:
    resolved_contract = contract or build_default_capability_contract()
    return {
        "contract_version": resolved_contract.version,
        "supported_intents": list(resolved_contract.supported_intents),
        "supported_tool_families": list(resolved_contract.supported_tool_families),
        "required_fields": list(resolved_contract.required_fields),
        "optional_defaults": resolved_contract.optional_defaults,
        "validation_rules": [
            {
                "field_name": rule.field_name,
                "rule_type": rule.rule_type,
                "message": rule.message,
            }
            for rule in resolved_contract.validation_rules
        ],
        "simplification_options": {
            category: [
                option.model_dump(mode="python")
                for option in resolved_contract.get_simplification_options(category)
            ]
            for category in resolved_contract.simplification_templates
        },
        "executable_indicators": [
            {
                "key": key,
                "label": spec.label,
                "default_parameters": dict(spec.default_parameters),
                "support_status": spec.support_status,
                "provider_source": spec.provider_source,
            }
            for key, spec in sorted(EXECUTABLE_INDICATORS.items())
        ],
        "deterministic_boundaries": [
            "asset resolution and provider availability",
            "same-asset-class validation",
            "max symbol limits",
            "benchmark defaults and explicit benchmark metadata",
            "engine run facts and persisted result truth",
        ],
    }


def iter_eval_cases(
    manifest: dict[str, Any] | None = None,
    *,
    priority: str | None = None,
) -> list[ChatRuntimeEvalCase]:
    source = manifest or load_eval_manifest()
    cases: list[ChatRuntimeEvalCase] = []
    for scenario in source["scenarios"]:
        if priority is not None and scenario["priority"] != priority:
            continue
        first_step = scenario["conversation_steps"][0]
        for prompt in scenario["natural_prompt_variants"]:
            cases.append(
                ChatRuntimeEvalCase(
                    scenario_id=scenario["id"],
                    qa_id=scenario["qa_id"],
                    priority=scenario["priority"],
                    prompt=prompt,
                    semantic_target=first_step["semantic_target"],
                    hard_checks=tuple(first_step["hard_checks"]),
                    forbidden_outcomes=tuple(scenario["forbidden_outcomes"]),
                    judge_rubric=scenario["judge_rubric"],
                )
            )
    return cases


def build_semantic_judge_messages(
    *,
    case: ChatRuntimeEvalCase,
    assistant_response: str,
    final_payload: dict[str, Any] | None,
    route_receipts: list[dict[str, Any]],
    capability_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    payload = {
        "case": {
            "scenario_id": case.scenario_id,
            "qa_id": case.qa_id,
            "priority": case.priority,
            "prompt": case.prompt,
            "semantic_target": case.semantic_target,
            "hard_checks": list(case.hard_checks),
            "forbidden_outcomes": list(case.forbidden_outcomes),
            "judge_rubric": case.judge_rubric,
        },
        "capability_context": capability_context or capability_context_payload(),
        "runtime_output": {
            "assistant_response": assistant_response,
            "final_payload": final_payload or {},
            "route_receipts": route_receipts,
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "You are the Argus chat-runtime semantic evaluator. Judge whether "
                "the turn satisfies the hard checks using the capability context "
                "provided here. Do not require exact wording. Do not reward claims "
                "that unsupported behavior is executable. Return compact JSON with "
                "pass, failed_checks, forbidden_outcomes_seen, groundedness_notes, "
                "and route_receipt_notes."
            ),
        },
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]


def parse_sse_events(raw_stream: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in raw_stream.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line.removeprefix("data: ")
        if payload == "[DONE]":
            continue
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            events.append(decoded)
    return events
