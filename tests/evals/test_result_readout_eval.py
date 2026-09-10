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


def test_tier_schedule_has_four_replicates_per_arm_and_96_frame_tasks() -> None:
    schedule = build_schedule(
        ["buyhold", "dca", "rsi"], replicates=4, variants=("current", "structured")
    )
    assert len(schedule) * 2 == 96
    for offset in range(0, len(schedule), 8):
        block = schedule[offset : offset + 8]
        assert [(row["variant"], row["replicate"]) for row in block] == [
            ("current", 1),
            ("structured", 1),
            ("structured", 2),
            ("current", 2),
            ("current", 3),
            ("structured", 3),
            ("structured", 4),
            ("current", 4),
        ]


@pytest.mark.parametrize(
    "mutation", ["none", "profile", "other_task", "comment", "duplicate"]
)
def test_tier_source_proof_allows_only_two_exact_mapping_changes(mutation: str) -> None:
    from tests.evals.result_readout_eval_tiers import validate_tier_sources

    current = b"""PROFILE = {"result_summary": 700}
OPENROUTER_TASK_MODEL_TIERS: dict[str, str] = {
    "result_summary": "chat", "result_breakdown": "context", "interpretation": "structured",
}
"""
    structured = current.replace(b'"chat"', b'"structured"').replace(
        b'"context"', b'"structured"'
    )
    mutations = {
        "profile": (b"700", b"900"),
        "other_task": (b'"interpretation": "structured"', b'"interpretation": "chat"'),
        "comment": (b"PROFILE", b"# extra change\nPROFILE"),
        "duplicate": (
            b'"result_summary": "structured",',
            b'"result_summary": "structured", "result_summary": "structured",',
        ),
    }
    if mutation == "none":
        validate_tier_sources(current, structured)
    else:
        structured = structured.replace(*mutations[mutation])
        with pytest.raises(ValueError):
            validate_tier_sources(current, structured)


def test_tier_tree_proof_rejects_another_changed_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.evals import result_readout_eval_tiers as tiers

    monkeypatch.setattr(
        tiers,
        "committed_tree",
        lambda root: {
            tiers.TASK_PATH: ("100644", str(root)),
            "src/argus/example.py": ("100644", str(root)),
        },
    )
    with pytest.raises(ValueError, match="only_readout_tier_file_may_differ"):
        tiers.validate_tier_checkouts(Path("current"), Path("structured"))


@pytest.mark.parametrize(
    "mode,expected_tasks", [("legacy", 48), ("tiers", 96), ("writing", 12)]
)
def test_runner_report_uses_mode_specific_counts_and_display_roles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
    expected_tasks: int,
) -> None:
    import sys

    from tests.evals import result_readout_eval as runner
    from tests.evals import result_readout_eval_tiers as tiers

    control = tmp_path / "control"
    (control / ".agent").mkdir(parents=True)
    (control / ".agent/interpreter_prompt_fingerprint.json").write_text(
        json.dumps({"last_measured": {"scorecard": "prior.json"}})
    )
    (control / "prior.json").write_text(
        json.dumps({"totals": {"passed": 1, "failed": 0}, "results": []})
    )
    monkeypatch.setattr(
        runner, "checkout_provenance", lambda *args, **kwargs: {"worktree_clean": True}
    )
    monkeypatch.setattr(
        tiers, "validate_tier_checkouts", lambda *args: {"test_only": True}
    )
    probe_calls = []

    def fake_probe(**kwargs):
        probe_calls.append(kwargs)
        return {
            "configuration": {"credential_present": True},
            "preflight_payloads": [],
            "observed_cost_usd": 0,
            "unknown_cost_attempts": 0,
            "unknown_cost_reserved_usd": 0,
            "accounted_upper_bound_usd": 0,
            "cost_complete": False,
        }

    monkeypatch.setattr(runner, "invoke_probe", fake_probe)
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--baseline",
            str(control),
            "--candidate",
            str(tmp_path / "candidate"),
            "--comparison-mode",
            mode,
            "--output",
            str(output),
        ],
    )
    runner.main()
    report = json.loads(output.read_text())
    assert report["scheduled_task_completions"] == expected_tasks
    assert report["totals"]["pending_review"] == expected_tasks
    assert len(report["results"]) * 2 == expected_tasks
    if mode == "writing":
        assert len(probe_calls) == 6
        assert all(call["checkout"] == tmp_path / "candidate" for call in probe_calls)
        assert all(call["single_attempt"] is True for call in probe_calls)
        assert {row["variant"] for row in report["results"]} == {"structured"}
        assert {row["replicate"] for row in report["results"]} == {1}
        assert report["budget"]["max_attempts_per_task"] == 1
        assert report["prior_full_scorecard"] is None
        assert report["fingerprint_authority"]["eligible"] is False
        assert all(
            "Private baseline" not in row["display_evidence_role"]
            for row in report["results"]
        )
    elif mode == "tiers":
        assert {row["variant"] for row in report["results"]} == {"current", "structured"}
        assert all(
            "Private baseline" not in row["display_evidence_role"]
            for row in report["results"]
        )
    else:
        assert report["results"][0]["display_evidence_role"].startswith(
            "Private baseline"
        )


def test_single_attempt_estimate_prices_only_primary_once() -> None:
    from tests.evals.result_readout_eval import TASK_OUTPUT_LIMITS

    probe = {
        "configuration": {
            "single_attempt": True,
            "max_input_bytes": MAX_INPUT_BYTES,
            "tasks": {
                task: {"models": ["primary", "unpriced-blocked-fallback"]}
                for task in TASK_OUTPUT_LIMITS
            },
        }
    }
    rates = {"primary": {"input_per_million": 1, "output_per_million": 2}}
    expected = sum(
        (MAX_INPUT_BYTES + 2 * output) / 1_000_000
        for output in TASK_OUTPUT_LIMITS.values()
    )
    assert estimate_ceiling([probe], rates) == pytest.approx(expected)


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


def test_explicit_larger_input_ceiling_prices_and_accepts_full_payload() -> None:
    rate = {"fixture-model": {"input_per_million": 0.35, "output_per_million": 0.95}}
    payload = {
        "model": "fixture-model",
        "max_tokens": 2400,
        "messages": [{"content": "x" * 70_000}],
    }
    default = CostGuard(budget_usd=1, rates=rate)
    with pytest.raises(ValueError, match="payload_too_large"):
        default.reserve(payload, task="result_breakdown")
    configured = CostGuard(budget_usd=1, rates=rate, max_input_bytes=90_000)
    reservation = configured.reserve(payload, task="result_breakdown")
    probe = {
        "configuration": {
            "max_input_bytes": 90_000,
            "tasks": {"result_breakdown": {"models": ["fixture-model"]}},
        }
    }
    assert estimate_ceiling([probe], rate) == pytest.approx(reservation * 4)
    assert reservation == pytest.approx((90_000 * 0.35 + 2400 * 0.95) / 1_000_000)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, float("inf"), "90000"])
def test_invalid_input_ceiling_is_refused(limit: object) -> None:
    with pytest.raises(ValueError, match="positive_integer_input_ceiling_required"):
        CostGuard(budget_usd=1, rates={}, max_input_bytes=limit)


def test_live_probe_cannot_change_input_ceiling_after_preflight(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="input_ceiling_changed_after_preflight"):
        invoke_probe(
            python="never-invoked",
            checkout=tmp_path,
            case={},
            language="en",
            live=True,
            budget_usd=1,
            rates={},
            max_input_bytes=100_000,
            preflight={"configuration": {"max_input_bytes": 90_000}},
        )


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
    from tests.evals.result_readout_probe import PRIOR_QUICK_TAKE_ALLOWANCE_BYTES

    for payload in probe["preflight_payloads"]:
        allowance = (
            PRIOR_QUICK_TAKE_ALLOWANCE_BYTES
            if payload["task"] == "result_breakdown"
            else 0
        )
        assert (
            payload["bytes_with_prior_quick_take_allowance"]
            == payload["bytes"] + allowance
        )


@pytest.fixture
def fake_live_probe_request(monkeypatch: pytest.MonkeyPatch) -> dict:
    from argus.llm import openrouter, openrouter_key_policy

    monkeypatch.setattr(openrouter, "resolve_openrouter_api_key", lambda: "test-only")
    monkeypatch.setattr(
        openrouter_key_policy, "resolve_openrouter_api_key", lambda: "test-only"
    )
    for tier in ("CHAT", "CONTEXT", "STRUCTURED"):
        monkeypatch.setenv(f"ARGUS_{tier}_MODEL", "fixture-model")
        monkeypatch.setenv(f"ARGUS_{tier}_FALLBACK_MODEL", "")
    fixture = load_fixture_set(
        Path(__file__).with_name("result_readout_fixtures.json"), live=False
    )
    return {
        "case": fixture["cases"][0],
        "language": "en",
        "live": True,
        "budget_usd": 1,
        "rates": {"fixture-model": {"input_per_million": 0.1, "output_per_million": 0.2}},
    }


@pytest.mark.parametrize("outcome", ["accepted", "http_400", "malformed"])
def test_single_attempt_blocks_retries_and_fallback_without_losing_other_frame(
    monkeypatch: pytest.MonkeyPatch,
    respx_mock,
    fake_live_probe_request: dict,
    outcome: str,
) -> None:
    import httpx
    from argus.llm import openrouter

    from tests.evals.result_readout_eval import measurement_can_continue
    from tests.evals.result_readout_probe import run_probe

    monkeypatch.setattr(
        openrouter, "openrouter_model_tier_for_task", lambda task: "structured"
    )
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "unpriced-blocked-fallback")

    def completion(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "fixture-model"
        if outcome == "http_400":
            return httpx.Response(
                400, json={"error": {"message": "Reasoning unsupported"}}
            )
        content = (
            "{invalid"
            if outcome == "malformed"
            else json.dumps(
                {
                    "language": "en",
                    "text": "The ending gain came with a rough historical ride.",
                    "figures": [],
                }
            )
        )
        return httpx.Response(
            200,
            json={
                "model": "fixture-model",
                "choices": [{"message": {"content": content}}],
                "usage": {"cost": 0.0001},
            },
        )

    route = respx_mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=completion
    )
    report = run_probe({**fake_live_probe_request, "single_attempt": True})
    assert route.call_count == report["http_attempts"] == 2
    assert [row["task"] for row in report["requests"]] == [
        "result_summary",
        "result_breakdown",
    ]
    assert report["configuration"]["single_attempt"] is True
    assert report["guard_failures"] == []
    assert measurement_can_continue(report)
    assert bool(report["blocked_dispatches"]) is (outcome != "accepted")
    assert all(
        row["reason"] == "single_attempt_policy" for row in report["blocked_dispatches"]
    )
    for surface in ("quick_take", "breakdown"):
        assert report[surface]["fallback_used"] is (outcome != "accepted")
        assert report[surface]["complete_text"]
    if outcome == "http_400":
        assert report["unknown_cost_attempts"] == 2
        assert report["accounted_upper_bound_usd"] == report["reserved_usd"]


def test_single_attempt_probe_requires_structured_tier(
    fake_live_probe_request: dict,
) -> None:
    from tests.evals.result_readout_probe import run_probe

    with pytest.raises(ValueError, match="writing_round_requires_structured_tiers"):
        run_probe({**fake_live_probe_request, "live": False, "single_attempt": True})


@pytest.mark.parametrize("false_figure", [False, True])
@pytest.mark.parametrize("reasoning_rejection", [False, True])
@pytest.mark.parametrize("late_response", [False, True])
def test_probe_retains_raw_drafts_receipts_and_complete_accepted_text(
    monkeypatch: pytest.MonkeyPatch,
    respx_mock,
    false_figure: bool,
    reasoning_rejection: bool,
    late_response: bool,
    fake_live_probe_request: dict,
) -> None:
    import time

    import httpx
    from argus.api.chat import breakdown

    from tests.evals.result_readout_probe import run_probe

    if late_response:
        owner = (
            "_llm_result_breakdown_with_metadata"
            if hasattr(breakdown, "_llm_result_breakdown_with_metadata")
            else "llm_result_breakdown_message"
        )
        actual_breakdown = getattr(breakdown, owner)

        def short_deadline(*args, **kwargs):
            return actual_breakdown(*args, **kwargs, timeout_seconds=0.1)

        monkeypatch.setattr(breakdown, owner, short_deadline)

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
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"text": body, "language": "en", "figures": []}
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 200, "completion_tokens": 30, "cost": 0.0001},
            },
        )

    route = respx_mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
        side_effect=completion
    )
    report = run_probe(fake_live_probe_request)
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


@pytest.mark.parametrize("invalid", ["language", "figures", "json"])
def test_probe_retains_malformed_drafts_and_whole_composition_failures(
    respx_mock,
    fake_live_probe_request: dict,
    invalid: str,
) -> None:
    import httpx
    from argus.api.chat import breakdown

    from tests.evals.result_readout_probe import run_probe

    draft = {"text": "The ride was rough.", "language": "en", "figures": []}
    if invalid == "language":
        draft["language"] = "es-419"
    elif invalid == "figures":
        draft["figures"] = [{"fact_key": "missing_value_and_quote"}]
    raw = '{"text":' if invalid == "json" else json.dumps(draft)
    route = respx_mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "fixture-model",
                "choices": [{"message": {"content": raw}}],
                "usage": {"cost": 0.0001},
            },
        )
    )
    report = run_probe(fake_live_probe_request)
    assert route.call_count == 2
    assert all(
        response["raw_drafts"] == [raw] for response in report["provider_responses"]
    )
    for surface in ("quick_take", "breakdown"):
        assert report[surface]["fallback_used"]
        assert report[surface]["accepted_text"] is None
        assert report[surface]["complete_text"]
        assert report[surface]["failure_mode"]
    if invalid == "language":
        assert report["quick_take"]["failure_mode"] == "language_mismatch"
        if hasattr(breakdown, "_llm_result_breakdown_with_metadata"):
            assert report["breakdown"]["failure_mode"] == "language_mismatch"
    else:
        assert all(
            receipt["failure_mode"] == "ValidationError"
            for receipt in report["route_receipts"]
        )


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
