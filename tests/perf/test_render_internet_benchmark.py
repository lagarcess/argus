from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_SCRIPT = (
    REPO_ROOT / "scripts" / "benchmarks" / "render_internet_benchmark.py"
)


def _load_benchmark_module() -> Any:
    assert BENCHMARK_SCRIPT.exists(), "render internet benchmark script should exist"
    spec = importlib.util.spec_from_file_location(
        "render_internet_benchmark",
        BENCHMARK_SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_outputs_stay_under_temp_render_benchmark_directory() -> None:
    module = _load_benchmark_module()

    output_dir = module.default_output_dir(REPO_ROOT)

    assert output_dir == REPO_ROOT / "temp" / "benchmarks" / "render-internet"


def test_parse_sse_events_accepts_canonical_data_frames() -> None:
    module = _load_benchmark_module()

    parsed = module.parse_sse_events(
        "\n".join(
            [
                'data: {"type":"stage_start","stage":"interpret"}',
                "",
                'data: {"type":"final","payload":{"ok":true}}',
                "",
                "data: [DONE]",
                "",
            ]
        )
    )

    assert parsed.done is True
    assert parsed.events == [
        {"type": "stage_start", "stage": "interpret"},
        {"type": "final", "payload": {"ok": True}},
    ]


def test_stream_phase_timings_capture_first_event_and_token() -> None:
    module = _load_benchmark_module()

    timings = module._stream_phase_timings_from_chunks(
        response_headers_ms=5.0,
        chunks=[
            (10.0, "data: {\"type\":\"stage_start\",\"stage\":\"interpret\"}\n\n"),
            (25.0, "data: {\"type\":\"token\",\"content\":\"Ready\"}\n\n"),
            (40.0, "data: {\"type\":\"final\",\"payload\":{}}\n\n"),
            (45.0, "data: [DONE]\n\n"),
        ],
        total_ms=50.0,
    )

    assert timings == {
        "response_headers": 5.0,
        "first_byte": 10.0,
        "first_sse_event": 10.0,
        "first_token": 25.0,
        "total": 50.0,
    }


def test_stream_phase_timings_are_partial_when_no_token_streams() -> None:
    module = _load_benchmark_module()

    timings = module._stream_phase_timings_from_chunks(
        response_headers_ms=7.0,
        chunks=[
            (15.0, "data: {\"type\":\"final\",\"payload\":{}}\n\n"),
            (20.0, "data: [DONE]\n\n"),
        ],
        total_ms=22.0,
    )

    assert timings == {
        "response_headers": 7.0,
        "first_byte": 15.0,
        "first_sse_event": 15.0,
        "total": 22.0,
    }


def test_extract_confirmation_run_action_uses_backend_action_shape() -> None:
    module = _load_benchmark_module()

    action = module.extract_confirmation_run_action(
        [
            {
                "type": "final",
                "payload": {
                    "final_response_payload": {
                        "confirmation_card": {
                            "actions": [
                                {"type": "edit"},
                                {
                                    "type": "run_backtest",
                                    "payload": {"symbol": "AAPL"},
                                },
                            ]
                        }
                    }
                },
            }
        ]
    )

    assert action == {"type": "run_backtest", "payload": {"symbol": "AAPL"}}


def test_extract_run_reference_prefers_async_backtest_job() -> None:
    module = _load_benchmark_module()

    reference = module.extract_run_reference(
        [
            {
                "type": "final",
                "payload": {
                    "run": {"id": "legacy-run"},
                    "backtest_job": {"id": "job-123"},
                },
            }
        ]
    )

    assert reference.kind == "job"
    assert reference.id == "job-123"


def test_markdown_summary_reports_live_timings_and_unavailable_metrics() -> None:
    module = _load_benchmark_module()
    report = {
        "schema_version": "argus_render_internet_benchmark/v1",
        "generated_at": "2026-06-07T12:00:00+00:00",
        "api_url": "https://argus-ohr5.onrender.com",
        "app_url": "https://argus-app-suz5.onrender.com",
        "runs": [
            {
                "case_id": "golden_path_aapl_msft",
                "iteration": 1,
                "status": "succeeded",
                "conversation_id": "conversation-123",
                "job_id": "job-123",
                "run_id": "run-123",
                "task_run_id": "trn-123",
                "timings_ms": {
                    "warmup_total": 1000.0,
                    "login": 200.0,
                    "conversation_create": 150.0,
                    "confirmation_stream": 2500.0,
                    "run_stream": 900.0,
                    "job_poll_until_terminal": 8000.0,
                    "total": 13000.0,
                    "render_task_duration": 5000.0,
                },
                "stream_timings_ms": {
                    "confirmation": {
                        "response_headers": 100.0,
                        "first_byte": 150.0,
                        "first_sse_event": 180.0,
                        "first_token": 1200.0,
                        "total": 2500.0,
                    },
                    "run": {
                        "response_headers": 80.0,
                        "first_byte": 110.0,
                        "first_sse_event": 140.0,
                        "total": 900.0,
                    },
                },
                "voice": {
                    "result_readout_source": "llm_explain_stage",
                    "result_readout_fallback_used": False,
                },
                "workflow_timings_ms": {
                    "workflow_task_total": 71000.0,
                    "provider_fetch_total": 1400.0,
                    "engine_compute_total": 3000.0,
                    "chart_result_build_total": 500.0,
                    "result_readout_total": 900.0,
                },
            }
        ],
        "metrics_unavailable": ["api_rss_mb", "workflow_peak_rss_mb"],
    }

    markdown = module.render_markdown_summary(report)

    assert "# Argus Render Internet Benchmark" in markdown
    assert "Warmup" in markdown
    assert "Post Warmup" in markdown
    assert "golden_path_aapl_msft" in markdown
    assert "13.00s" in markdown
    assert "12.00s" in markdown
    assert "llm_explain_stage" in markdown
    assert "## Stream Phase Timings" in markdown
    assert "Confirmation" in markdown
    assert "First Byte" in markdown
    assert "First SSE" in markdown
    assert "First Token" in markdown
    assert "1.20s" in markdown
    assert "Run" in markdown
    assert "Workflow Internal Timings" in markdown
    assert "Provider Fetch" in markdown
    assert "1.40s" in markdown
    assert "api_rss_mb" in markdown
    assert "workflow_peak_rss_mb" in markdown


def test_safe_job_summary_extracts_workflow_timestamps_and_durations() -> None:
    module = _load_benchmark_module()

    summary = module.safe_job_summary(
        {
            "id": "job-123",
            "status": "succeeded",
            "result_run_id": "run-123",
            "queued_at": "2026-06-07T21:29:29.000000+00:00",
            "started_at": "2026-06-07T21:29:45.500000+00:00",
            "finished_at": "2026-06-07T21:30:40.000000+00:00",
            "execution_metadata": {
                "workflow_dispatch": {
                    "task_run_id": "trn-123",
                    "status": "pending",
                },
                "workflow_backtest": {
                    "result_readout_source": "llm_explain_stage",
                    "result_readout_fallback_used": False,
                    "timings_ms": {
                        "workflow_task_total": 71000.1234,
                        "provider_fetch_total": 1400.2345,
                        "engine_compute_total": 3000.3456,
                        "chart_result_build_total": 500.4567,
                        "backtest_run_persist": 120.5678,
                        "result_readout_total": 900.6789,
                        "link_result": 80.7891,
                    },
                },
            },
        }
    )

    assert summary["task_run_id"] == "trn-123"
    assert summary["timings_ms"] == {
        "queued_to_started": 16500.0,
        "started_to_finished": 54500.0,
        "queued_to_finished": 71000.0,
    }
    assert summary["workflow_timings_ms"] == {
        "workflow_task_total": 71000.123,
        "provider_fetch_total": 1400.235,
        "engine_compute_total": 3000.346,
        "chart_result_build_total": 500.457,
        "backtest_run_persist": 120.568,
        "result_readout_total": 900.679,
        "link_result": 80.789,
    }
