"""Analysis invariants using authored fixtures, never real-run timing evidence."""

from copy import deepcopy

from faker import Faker

from scripts.benchmarks.summarize_turn_latency import summarize
from scripts.benchmarks.turn_latency import typed_outcome

fake = Faker()


def row():
    return {
        "sample_id": fake.uuid4(),
        "requested_category": "ordinary_chat",
        "language": "en",
        "status": "stream_complete",
        "outcome": typed_outcome({}),
        "events": [],
        "timings": {"first_token_ms": 10},
        "completion_ms": 30,
        "receipts": [],
    }


def test_thorough_acknowledgement_is_not_grounded_answer_time():
    sample = row()
    sample.update(requested_category="research_thorough", status="succeeded")
    sample["job"] = {
        "status": "succeeded",
        "operation_scope": "chat.research",
        "answer_observed_ms": 90,
        "result": {"research_shape": "thorough"},
    }
    group = summarize([sample])["groups"]["research_thorough"]
    assert group["metrics"]["first_token_ms"]["p50"] == 10
    assert group["metrics"]["first_grounded_answer_ms"]["p50"] == 90


def test_grouping_uses_observed_type_and_discloses_requested_type():
    sample = row()
    sample["requested_category"] = "research_balanced"
    sample["outcome"]["research_shape"] = "fast"
    group = summarize([sample])["groups"]["research_fast"]
    assert group["requested_categories"] == {"research_balanced": 1}


def test_repeated_provider_calls_do_not_inflate_turn_share():
    sample = row()
    receipt = {
        "task": "interpretation",
        "schema_name": "LLMInterpretationResponse",
        "mode": "json_schema",
        "tier": "structured",
        "outcome": "succeeded",
        "latency_ms": 3,
    }
    sample["receipts"] = [receipt, deepcopy(receipt)]
    group = summarize([sample])["groups"]["ordinary_chat"]
    assert group["turns_with_positive_latency_tier"] == {"structured": 1}
    assert group["receipt_rows_by_tier"] == {"structured": 2}


def test_degraded_result_is_separate_and_never_a_grounded_speed_win():
    sample = row()
    sample["outcome"].update(
        research_shape="balanced", research_degraded="missing_sources"
    )
    group = summarize([sample])["groups"]["research_balanced__degraded"]
    assert group["metrics"]["first_grounded_answer_ms"] == {"n": 0, "missing": 1}
    assert group["metrics"]["first_token_ms"]["p50"] == 10


def test_compute_intent_probe_never_becomes_compute_execution():
    sample = row()
    sample["requested_category"] = "compute_intent_probe"
    assert list(summarize([sample])["groups"]) == ["compute_intent_probe__ordinary_chat"]


def test_clarification_is_not_counted_as_an_answer_or_confirmation():
    sample = row()
    sample["requested_category"] = "confirmation"
    sample["outcome"]["stage_outcome"] = "await_user_reply"
    assert list(summarize([sample])["groups"]) == ["clarification"]
