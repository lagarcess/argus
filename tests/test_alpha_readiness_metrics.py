from __future__ import annotations

import json
from pathlib import Path

from scripts.ops.alpha_readiness_metrics import summarize_backtest_jobs

ROOT = Path(__file__).resolve().parents[1]


def test_alpha_readiness_metrics_summarizes_jobs_without_identifiers() -> None:
    jobs = [
        {
            "id": "job-should-not-leak",
            "user_id": "user-should-not-leak",
            "conversation_id": "conversation-should-not-leak",
            "status": "succeeded",
            "queued_at": "2026-06-16T12:00:00+00:00",
            "started_at": "2026-06-16T12:00:02+00:00",
            "finished_at": "2026-06-16T12:00:32+00:00",
            "execution_metadata": {
                "workflow_backtest": {
                    "result_readout_source": "llm_explain_stage",
                    "result_readout_fallback_used": False,
                    "timings_ms": {
                        "provider_fetch": 1200,
                        "compute": 8000,
                        "result_summary": 6500,
                    },
                }
            },
        },
        {
            "id": "fallback-job-should-not-leak",
            "status": "succeeded",
            "queued_at": "2026-06-16T12:01:00+00:00",
            "started_at": "2026-06-16T12:01:05+00:00",
            "finished_at": "2026-06-16T12:02:05+00:00",
            "execution_metadata": {
                "workflow_backtest": {
                    "result_readout_source": "deterministic_fallback",
                    "result_readout_fallback_used": True,
                    "timings_ms": {"compute": 10000, "result_summary": 2000},
                }
            },
        },
        {
            "id": "failed-job-should-not-leak",
            "status": "failed",
            "failure_code": "provider_timeout",
            "queued_at": "2026-06-16T12:03:00+00:00",
            "execution_metadata": {},
        },
    ]

    summary = summarize_backtest_jobs(
        jobs,
        window_hours=24,
        generated_at="2026-06-16T12:30:00+00:00",
    )

    assert summary["window_hours"] == 24
    assert summary["job_count"] == 3
    assert summary["status_counts"] == {"failed": 1, "succeeded": 2}
    assert summary["failure_code_counts"] == {"provider_timeout": 1}
    assert summary["readout"] == {
        "llm_explain_stage_count": 1,
        "fallback_count": 1,
        "missing_workflow_metadata_count": 1,
        "source_counts": {
            "deterministic_fallback": 1,
            "llm_explain_stage": 1,
        },
    }
    assert summary["job_timing_ms"]["queued_to_started"] == {
        "count": 2,
        "p50": 3500.0,
        "p95": 4850.0,
        "max": 5000.0,
    }
    assert summary["workflow_timing_ms"]["compute"] == {
        "count": 2,
        "p50": 9000.0,
        "p95": 9900.0,
        "max": 10000.0,
    }
    assert summary["gate_signals"]["deterministic_readout_fallbacks"] == 1
    assert summary["gate_signals"]["terminal_failures"] == 1

    encoded = json.dumps(summary, sort_keys=True)
    assert "should-not-leak" not in encoded
    assert "conversation_id" not in encoded
    assert "user_id" not in encoded


def test_alpha_readiness_metrics_handles_empty_window() -> None:
    summary = summarize_backtest_jobs(
        [],
        window_hours=24,
        generated_at="2026-06-16T12:30:00+00:00",
    )

    assert summary["job_count"] == 0
    assert summary["status_counts"] == {}
    assert summary["readout"]["fallback_count"] == 0
    assert summary["job_timing_ms"] == {}
    assert summary["workflow_timing_ms"] == {}


def test_alpha_readiness_metrics_env_contract_is_documented() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    runbook = (ROOT / "docs/PRIVATE_LAUNCH_RUNBOOK.md").read_text(encoding="utf-8")

    assert "ARGUS_ALPHA_METRICS_SUPABASE_URL=" in env_example
    assert "ARGUS_ALPHA_METRICS_SUPABASE_SERVICE_ROLE_KEY=" in env_example
    assert "scripts/ops/alpha_readiness_metrics.py --json" in runbook
    assert "without emitting user ids, conversation ids, prompt text" in runbook
