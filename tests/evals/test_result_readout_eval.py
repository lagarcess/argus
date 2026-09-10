"""Free safety/provenance tests for the explicitly paid readout probe."""

import json
from pathlib import Path

import pytest

from tests.evals.result_readout_eval import (
    MAX_INPUT_BYTES,
    CostGuard,
    build_schedule,
    estimate_ceiling,
    invoke_probe,
    load_fixture_set,
    retained_case_evidence,
)


def test_schedule_interleaves_both_languages_and_pairs_both_frames() -> None:
    schedule = build_schedule(["buyhold", "dca", "sparse"])
    assert len(schedule) == 24
    for offset in range(0, len(schedule), 4):
        block = schedule[offset : offset + 4]
        assert [row["variant"] for row in block] == [
            "baseline",
            "candidate",
            "candidate",
            "baseline",
        ]
        assert {row["language"] for row in block} <= {"en", "es-419"}
        assert [row["replicate"] for row in block] == [1, 1, 2, 2]


def test_paid_fixtures_refuse_authored_test_numbers() -> None:
    path = Path(__file__).with_name("result_readout_fixtures.json")
    assert len(load_fixture_set(path, live=False)["cases"]) == 3
    with pytest.raises(ValueError, match="recorded_run_required"):
        load_fixture_set(path, live=True)


def test_cost_guard_reserves_before_request_and_cannot_overspend() -> None:
    guard = CostGuard(
        budget_usd=0.001,
        rates={"fixture-model": {"input_per_million": 1, "output_per_million": 2}},
        max_input_bytes=MAX_INPUT_BYTES,
        max_attempts=4,
    )
    payload = {"model": "fixture-model", "max_tokens": 700, "messages": []}
    with pytest.raises(ValueError, match="budget_exceeded"):
        guard.reserve(payload, task="result_summary")
    assert guard.attempts == 0
    assert guard.reserved_usd == 0


@pytest.mark.parametrize(
    "mutation,error",
    [
        ({"model": "unknown"}, "unpriced_model"),
        ({"messages": [{"content": "x" * (MAX_INPUT_BYTES + 1)}]}, "payload_too_large"),
        ({"max_tokens": 7000}, "output_limit"),
    ],
)
def test_cost_guard_fails_closed_before_network(mutation: dict, error: str) -> None:
    guard = CostGuard(
        budget_usd=1,
        rates={"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}},
    )
    payload = {"model": "fixture-model", "max_tokens": 700, "messages": []}
    with pytest.raises(ValueError, match=error):
        guard.reserve({**payload, **mutation}, task="result_summary")
    assert guard.attempts == 0


def test_cost_guard_limits_each_task_to_four_actual_http_attempts() -> None:
    guard = CostGuard(
        budget_usd=1,
        rates={"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}},
    )
    payload = {"model": "fixture-model", "max_tokens": 700, "messages": []}
    for _ in range(4):
        guard.reserve(payload, task="result_summary")
    with pytest.raises(ValueError, match="attempt_limit"):
        guard.reserve(payload, task="result_summary")


def test_recorded_chart_sized_request_fits_proposed_input_bound() -> None:
    guard = CostGuard(
        budget_usd=4,
        rates={"fixture-model": {"input_per_million": 0.35, "output_per_million": 0.95}},
    )
    guard.reserve(
        {
            "model": "fixture-model",
            "max_tokens": 2400,
            "messages": [{"content": "x" * 48_815}],
        },
        task="result_breakdown",
    )
    assert guard.attempts == 1


def test_full_comparison_bound_prices_all_configured_fallbacks() -> None:
    probe = {
        "configuration": {
            "tasks": {
                "result_summary": {"models": ["deepseek", "qwen"]},
                "result_breakdown": {"models": ["gptoss", "deepseek"]},
            }
        }
    }
    rates = {
        "deepseek": {"input_per_million": 0.21, "output_per_million": 0.56},
        "qwen": {"input_per_million": 0.17, "output_per_million": 0.25},
        "gptoss": {"input_per_million": 0.35, "output_per_million": 0.95},
    }
    schedule = build_schedule(["buyhold", "dca", "sparse"])
    assert estimate_ceiling([probe for _ in schedule], rates) == pytest.approx(3.482112)


def test_probe_timeout_preserves_the_reserved_visit_upper_bound(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import subprocess
    import sys

    from tests.evals.result_readout_eval import MAX_ATTEMPTS, measurement_can_continue

    configuration = {
        "tasks": {
            "result_summary": {"models": ["fixture-model"], "timeout_seconds": 30},
            "result_breakdown": {"models": ["fixture-model"], "timeout_seconds": 25},
        }
    }
    preflight = {"configuration": configuration}
    rates = {"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}}

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] > MAX_ATTEMPTS * (30 + 25)
        raise subprocess.TimeoutExpired("probe", kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    report = invoke_probe(
        python=sys.executable,
        checkout=tmp_path,
        case={},
        language="en",
        live=True,
        budget_usd=4,
        rates=rates,
        preflight=preflight,
    )
    assert report["reserved_usd"] == estimate_ceiling([preflight], rates)
    assert report["accounted_upper_bound_usd"] == report["reserved_usd"]
    assert report["http_attempts"] is None
    assert report["unknown_cost_attempts"] is None
    assert not report["attempt_receipts_complete"]
    assert not report["cost_complete"]
    assert not measurement_can_continue(report)


def test_retained_scorecard_preserves_old_failed_cases_without_claiming_rerun(
    tmp_path: Path,
) -> None:
    path = tmp_path / "previous.json"
    path.write_text(
        json.dumps(
            {
                "totals": {"passed": 1, "failed": 1},
                "results": [{"case_id": "honest-old-failure", "passed": False}],
            }
        )
    )
    retained = retained_case_evidence(path)
    assert retained["remeasured"] is False
    assert retained["totals"]["failed"] == 1
    assert retained["case_dispositions"][0]["case_id"] == "honest-old-failure"
    assert "results" not in retained
    assert len(retained["sha256"]) == 64


@pytest.mark.parametrize("case_index", range(3))
@pytest.mark.parametrize("language", ["en", "es-419"])
def test_preflight_runs_actual_composers_without_a_provider_call(
    case_index: int,
    language: str,
) -> None:
    import sys

    repository = Path(__file__).resolve().parents[2]
    fixtures = load_fixture_set(
        Path(__file__).with_name("result_readout_fixtures.json"), live=False
    )
    probe = invoke_probe(
        python=sys.executable,
        checkout=repository,
        case=fixtures["cases"][case_index],
        language=language,
        live=False,
        budget_usd=0,
        rates={},
    )
    assert probe["http_attempts"] == 0
    assert probe["guard_failures"] == []
    assert {row["task"] for row in probe["preflight_payloads"]} == {
        "result_summary",
        "result_breakdown",
    }
    assert probe["quick_take"]["fallback_used"] is True
    assert probe["breakdown"]["fallback_used"] is True
    assert probe["quick_take"]["complete_text"]
    assert probe["breakdown"]["complete_text"]


@pytest.mark.parametrize("false_figure", [False, True])
@pytest.mark.parametrize("reasoning_rejection", [False, True])
@pytest.mark.parametrize("late_response", [False, True])
def test_probe_retains_raw_drafts_receipts_and_complete_accepted_text(
    monkeypatch: pytest.MonkeyPatch,
    respx_mock,
    false_figure: bool,
    reasoning_rejection: bool,
    late_response: bool,
) -> None:
    import time

    import httpx
    from argus.api.chat import breakdown
    from argus.llm import openrouter, openrouter_key_policy

    from tests.evals.result_readout_probe import run_probe

    monkeypatch.setattr(openrouter, "resolve_openrouter_api_key", lambda: "test-only")
    monkeypatch.setattr(
        openrouter_key_policy, "resolve_openrouter_api_key", lambda: "test-only"
    )
    for tier in ("CHAT", "CONTEXT"):
        monkeypatch.setenv(f"ARGUS_{tier}_MODEL", "fixture-model")
        monkeypatch.setenv(f"ARGUS_{tier}_FALLBACK_MODEL", "")
    if late_response:
        actual_breakdown = breakdown.llm_result_breakdown_message

        def short_deadline(*args, **kwargs):
            return actual_breakdown(*args, **kwargs, timeout_seconds=0.1)

        monkeypatch.setattr(breakdown, "llm_result_breakdown_message", short_deadline)

    def completion(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        name = payload["response_format"]["json_schema"]["name"]
        if late_response and name == "ResultBreakdownDraft" and "reasoning" in payload:
            time.sleep(0.2)
        if (
            reasoning_rejection
            and name == "ResultBreakdownDraft"
            and "reasoning" in payload
        ):
            return httpx.Response(
                400,
                json={
                    "error": {
                        "code": 400,
                        "message": "Reasoning unsupported; secret-test-value",
                    }
                },
            )
        body = (
            "The ending gain came with a rough historical ride."
            if name == "QuickTakeDraft"
            else "A drawdown measures a decline from a prior peak, rather than the ending loss."
        )
        if false_figure:
            body = "The strategy returned 99876.5%."
        return httpx.Response(
            200,
            json={
                "model": "fixture-model",
                "choices": [{"message": {"content": json.dumps({"text": body})}}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 30, "cost": 0.0001},
            },
        )

    route = respx_mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=completion
    )
    fixture = load_fixture_set(
        Path(__file__).with_name("result_readout_fixtures.json"), live=False
    )
    report = run_probe(
        {
            "case": fixture["cases"][0],
            "language": "en",
            "live": True,
            "budget_usd": 1,
            "rates": {
                "fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}
            },
        }
    )
    expected_attempts = 3 if reasoning_rejection else 2
    assert route.call_count == expected_attempts
    assert report["http_attempts"] == expected_attempts
    assert report["cost_complete"] is (not reasoning_rejection)
    assert report["observed_cost_usd"] == pytest.approx(0.0002)
    assert len(report["route_receipts"]) == 2
    assert len(report["provider_responses"]) == expected_attempts
    assert "secret-test-value" not in json.dumps(report)
    assert report["provider_responses"][0]["raw_drafts"]
    assert report["provider_worker_settled"] is True
    assert all(row["outcome"] != "pending" for row in report["requests"])
    if late_response:
        assert report["receipt_settlement_ms"] > 0
        assert report["breakdown"]["fallback_used"] is True
        assert report["breakdown"]["accepted_text"] is None
    for surface in ("quick_take", "breakdown"):
        expected_fallback = false_figure or (surface == "breakdown" and late_response)
        if expected_fallback:
            assert report[surface]["accepted_text"] is None
            assert "99876.5" not in report[surface]["complete_text"]
            assert report[surface]["complete_text"]
        else:
            assert report[surface]["accepted_text"] == report[surface]["complete_text"]
        assert report[surface]["fallback_used"] is expected_fallback


def test_recorded_fixture_must_match_immutable_source_bytes(tmp_path: Path) -> None:
    from tests.evals.result_readout_eval import sha256

    original = json.loads(
        Path(__file__).with_name("result_readout_fixtures.json").read_text()
    )
    for case in original["cases"]:
        path = tmp_path / f"{case['id']}.json"
        path.write_text(json.dumps(case["run"]))
        case["source"] = {
            "kind": "recorded_run",
            "artifact": path.name,
            "sha256": sha256(path.read_bytes()),
            "provider_mode": "TEST_ONLY_SOURCE_VALIDATION",
            "captured_at": "2026-09-10",
        }
    fixture_path = tmp_path / "fixtures.json"
    fixture_path.write_text(json.dumps(original))
    assert len(load_fixture_set(fixture_path, live=True)["cases"]) == 3
    original["cases"][0]["run"]["metrics"] = {}
    fixture_path.write_text(json.dumps(original))
    with pytest.raises(ValueError, match="fixture_does_not_match_saved_run"):
        load_fixture_set(fixture_path, live=True)
