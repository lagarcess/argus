"""Free contract tests for the single-candidate Luna readout measurement."""

import json
import sys
from pathlib import Path

import pytest

from tests.evals.result_readout_eval import (
    MAX_INPUT_BYTES,
    CostGuard,
    build_schedule,
    estimate_ceiling,
    estimate_payload_and_tools,
    invoke_probe,
    load_fixture_set,
)


@pytest.fixture
def task_configuration():
    return {
        "result_summary": {
            "provider": "openrouter",
            "model": "fixture-luna",
            "tier": "readout",
            "max_output_tokens": 700,
            "timeout_seconds": 30,
        },
        "result_breakdown": {
            "provider": "perplexity_agent",
            "model": "fixture-luna",
            "max_output_tokens": 2200,
            "timeout_seconds": 75,
            "request_limits": {
                "models": ["fixture-luna"],
                "max_steps": 3,
                "max_output_tokens": 2200,
                "max_tool_calls": 4,
                "parallel_tool_calls": False,
                "tools": [
                    {
                        "type": "web_search",
                        "max_tokens": 8000,
                        "max_tokens_per_page": 2000,
                        "max_results": 4,
                    },
                    {"type": "fetch_url", "max_urls": 2, "total_budget_tokens": 8000},
                ],
            },
        },
    }


@pytest.fixture
def provider_rates():
    return {
        "openrouter": {
            "model": "fixture-luna",
            "input_per_million": 0.4,
            "output_per_million": 2.4,
        },
        "perplexity_agent": {
            "model": "fixture-luna",
            "input_per_million": 0.4,
            "output_per_million": 1.8,
            "context_window_tokens": 1050000,
            "tool_per_call": {"web_search": 0.0025, "fetch_url": 0.0005},
        },
    }


def test_schedule_is_exactly_six_visits_and_twelve_drafts():
    cases = ["buyhold", "dca", "rsi"]
    schedule = build_schedule(cases)
    assert len(schedule) == 6
    assert [(row["case_id"], row["language"]) for row in schedule] == [
        (case, language) for case in cases for language in ("en", "es-419")
    ]
    assert {row["replicate"] for row in schedule} == {1}
    assert {row["variant"] for row in schedule} == {"candidate"}


def test_estimate_reserves_one_primary_request_and_agent_tool_work(
    task_configuration, provider_rates
):
    probe = {
        "configuration": {"max_input_bytes": MAX_INPUT_BYTES, "tasks": task_configuration}
    }
    # The remote model-context envelope includes all three loop steps plus a
    # final generation; it does not pretend initial bytes bound later inputs.
    expected_quick = (MAX_INPUT_BYTES * 0.4 + 700 * 2.4) / 1_000_000
    expected_deep = 4 * (1050000 * 0.4 + 2200 * 1.8) / 1_000_000 + 4 * 0.0025
    assert estimate_ceiling([probe], provider_rates) == pytest.approx(
        expected_quick + expected_deep
    )


def test_cost_guard_blocks_second_dispatch_and_unexpected_provider(
    task_configuration, provider_rates
):
    guard = CostGuard(budget_usd=4, rates=provider_rates, tasks=task_configuration)
    payload = {"model": "fixture-luna", "max_tokens": 700, "messages": []}
    guard.reserve(payload, task="result_summary")
    with pytest.raises(ValueError, match="attempt_limit"):
        guard.reserve(payload, task="result_summary")
    assert guard.attempts == 1
    assert guard.by_task == {"result_summary": 1}
    with pytest.raises(ValueError, match="unexpected_provider_task"):
        guard.reserve(payload, task="interpretation")


def test_planning_estimate_uses_measured_request_tools_and_prior_outputs(
    task_configuration, provider_rates
):
    quick_bytes, deeper_bytes = 10000, 16000
    probe = {
        "configuration": {"tasks": task_configuration},
        "preflight_payloads": [
            {
                "task": "result_summary",
                "bytes_with_prior_quick_take_allowance": quick_bytes,
            },
            {
                "task": "result_breakdown",
                "bytes_with_prior_quick_take_allowance": deeper_bytes,
            },
        ],
    }
    expected = (quick_bytes * 0.4 + 700 * 2.4) / 1_000_000
    expected += (
        4 * ((deeper_bytes + 4 * 8000 + 3 * 2200) * 0.4 + 2200 * 1.8) / 1_000_000
        + 4 * 0.0025
    )
    assert estimate_payload_and_tools([probe], provider_rates) == pytest.approx(expected)
    assert expected < estimate_ceiling([probe], provider_rates)


@pytest.mark.parametrize(
    "mutation", ["tool", "steps", "tool_calls", "model", "output", "budget"]
)
def test_agent_reservation_refuses_unbounded_or_changed_request(
    task_configuration, provider_rates, mutation
):
    import copy

    payload = copy.deepcopy(task_configuration["result_breakdown"]["request_limits"])
    payload["input"] = "Saved run facts"
    if mutation == "tool":
        payload["tools"].append({"type": "finance_search"})
    elif mutation == "steps":
        payload["max_steps"] += 1
    elif mutation == "tool_calls":
        payload.pop("max_tool_calls")
    elif mutation == "model":
        payload["models"].append("weaker-fallback")
    elif mutation == "output":
        payload["max_output_tokens"] += 1
    guard = CostGuard(
        budget_usd=0.001 if mutation == "budget" else 4,
        rates=provider_rates,
        tasks=task_configuration,
    )
    with pytest.raises(ValueError):
        guard.reserve(payload, task="result_breakdown")
    assert guard.attempts == 0


def test_default_input_limit_remains_conservative(task_configuration, provider_rates):
    payload = {"model": "fixture-luna", "max_tokens": 700, "messages": ["x" * 70000]}
    with pytest.raises(ValueError, match="payload_too_large"):
        CostGuard(budget_usd=4, rates=provider_rates, tasks=task_configuration).reserve(
            payload, task="result_summary"
        )
    guard = CostGuard(
        budget_usd=4,
        rates=provider_rates,
        tasks=task_configuration,
        max_input_bytes=90000,
    )
    assert guard.reserve(payload, task="result_summary") > 0


def test_paid_fixture_requires_genuine_source_and_hash(tmp_path):
    source = Path(__file__).with_name("result_readout_fixtures.json")
    data = load_fixture_set(source, live=False)
    with pytest.raises(ValueError, match="recorded_run_required"):
        load_fixture_set(source, live=True)
    from tests.evals.result_readout_eval import sha256

    for case in data["cases"]:
        artifact = tmp_path / f"{case['id']}.json"
        artifact.write_text(json.dumps(case["run"]))
        case["source"] = {
            "kind": "recorded_run",
            "artifact": artifact.name,
            "sha256": sha256(artifact.read_bytes()),
            "captured_at": "TEST ONLY",
            "provider_mode": "TEST ONLY source verifier",
        }
    fixture = tmp_path / "fixtures.json"
    fixture.write_text(json.dumps(data))
    assert len(load_fixture_set(fixture, live=True)["cases"]) == 3
    data["cases"][0]["run"]["metrics"] = {}
    fixture.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="fixture_does_not_match_saved_run"):
        load_fixture_set(fixture, live=True)


def test_lost_child_receipts_charge_whole_visit_and_stop(
    monkeypatch, tmp_path, task_configuration, provider_rates
):
    import subprocess

    from tests.evals.result_readout_eval import measurement_can_continue

    preflight = {
        "configuration": {"max_input_bytes": MAX_INPUT_BYTES, "tasks": task_configuration}
    }

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] > sum(
            task["timeout_seconds"] for task in task_configuration.values()
        )
        raise subprocess.TimeoutExpired("probe", kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    report = invoke_probe(
        python=sys.executable,
        checkout=tmp_path,
        case={},
        language="en",
        live=True,
        budget_usd=4,
        rates=provider_rates,
        preflight=preflight,
    )
    assert report["reserved_usd"] == estimate_ceiling([preflight], provider_rates)
    assert report["unknown_cost_attempts"] is None
    assert not report["cost_complete"]
    assert not measurement_can_continue(report)


def test_single_candidate_runner_probes_six_pairs_only(
    monkeypatch, tmp_path, task_configuration
):
    from tests.evals import result_readout_eval as runner

    calls = []
    monkeypatch.setattr(
        runner,
        "checkout_provenance",
        lambda *a, **k: {"worktree_clean": True, "commit": "test-only"},
    )

    def probe(**kwargs):
        calls.append(kwargs)
        return {
            "configuration": {"credential_present": True, "tasks": task_configuration},
            "preflight_payloads": [],
            "observed_cost_usd": 0,
            "unknown_cost_attempts": 0,
            "unknown_cost_reserved_usd": 0,
            "accounted_upper_bound_usd": 0,
            "cost_complete": False,
        }

    monkeypatch.setattr(runner, "invoke_probe", probe)
    output = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["runner", "--candidate", str(tmp_path / "candidate"), "--output", str(output)],
    )
    runner.main()
    report = json.loads(output.read_text())
    assert len(calls) == len(report["results"]) == 6
    assert (
        report["scheduled_task_completions"] == report["totals"]["pending_review"] == 12
    )
    assert report["budget"]["max_attempts_per_task"] == 1
    assert set(report["checkouts"]) == {"candidate"}
    assert not report["fingerprint_authority"]["eligible"]


@pytest.mark.parametrize("flag", ["--baseline", "--comparison-mode"])
def test_old_paid_comparison_cli_is_retired(monkeypatch, tmp_path, flag):
    from tests.evals import result_readout_eval as runner

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "runner",
            "--candidate",
            str(tmp_path / "candidate"),
            "--output",
            str(tmp_path / "r.json"),
            flag,
            "tiers",
        ],
    )
    with pytest.raises(SystemExit):
        runner.main()
