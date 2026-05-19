from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(__file__).with_name("chat_runtime_scenarios.json")
EXPECTED_QA_IDS = {f"QA {index}" for index in range(1, 15)}
EXPECTED_WORKSTREAMS = {f"workstream_{index}" for index in range(1, 9)}
VALID_PRIORITIES = {"must_pass", "should_pass", "watch"}
EXPECTED_EVAL_CATEGORIES = {
    "messy_beginner_investing_prompts",
    "partial_strategy_ideas",
    "unsupported_requests",
    "contradictory_requests",
    "recovery_scenarios",
    "reload_refinement_continuity",
    "result_followup_groundedness",
    "why_did_this_happen_contextual_synthesis",
    "next_experiment_usefulness",
    "hallucination_prevention",
    "no_unsupported_investment_advice",
}


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_chat_runtime_eval_manifest_covers_release_matrix() -> None:
    manifest = _load_manifest()
    scenarios = manifest["scenarios"]

    qa_ids = {scenario["qa_id"] for scenario in scenarios}
    assert qa_ids == EXPECTED_QA_IDS

    covered_workstreams = {
        bucket
        for scenario in scenarios
        for bucket in scenario["buckets"]
        if bucket.startswith("workstream_")
    }
    assert covered_workstreams == EXPECTED_WORKSTREAMS


def test_chat_runtime_eval_manifest_has_judge_and_hard_checks() -> None:
    manifest = _load_manifest()
    scenario_ids: set[str] = set()

    for scenario in manifest["scenarios"]:
        assert scenario["id"] not in scenario_ids
        scenario_ids.add(scenario["id"])
        assert scenario["priority"] in VALID_PRIORITIES
        assert scenario["purpose"]
        assert len(scenario["natural_prompt_variants"]) >= 3
        assert scenario["conversation_steps"]
        assert scenario["artifact_checks"]
        assert scenario["action_checks"]
        assert scenario["reload_checks"]
        assert scenario["forbidden_outcomes"]
        assert scenario["judge_rubric"]

        for step in scenario["conversation_steps"]:
            assert step["semantic_target"]
            assert step["hard_checks"]


def test_chat_runtime_eval_manifest_separates_hard_checks_from_llm_judgment() -> None:
    manifest = _load_manifest()
    assert manifest["scoring"]["must_pass"].startswith("Hard runtime")

    must_pass = [
        scenario
        for scenario in manifest["scenarios"]
        if scenario["priority"] == "must_pass"
    ]
    assert len(must_pass) >= 10

    for scenario in must_pass:
        hard_check_text = " ".join(
            check
            for step in scenario["conversation_steps"]
            for check in step["hard_checks"]
        )
        assert "judge" not in hard_check_text.lower()
        assert "rubric" not in hard_check_text.lower()


def test_chat_runtime_eval_layer_tracks_semantic_groundedness_and_receipts() -> None:
    manifest = _load_manifest()
    layer = manifest["production_readiness_eval_layer"]

    assert layer["assertion_style"] == "semantic_contracts_not_exact_wording"
    assert set(layer["exact_strings_reserved_for"]) == {
        "protocol",
        "static_ui",
        "safety_fallback",
    }
    assert set(layer["categories"]) == EXPECTED_EVAL_CATEGORIES
    assert set(layer["receipt_fields"]) >= {
        "task",
        "tier",
        "model",
        "fallback_model",
        "latency_ms",
        "outcome",
        "failure_mode",
    }
