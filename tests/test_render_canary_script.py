from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canary_defaults_to_private_launch_urls() -> None:
    source = _source(".github/canary-render.sh")

    assert "https://argus-app-suz5.onrender.com" in source
    assert "https://argus-ohr5.onrender.com" in source


def test_canary_requires_auth_inputs_without_echoing_password() -> None:
    source = _source(".github/canary-render.sh")

    assert "ARGUS_CANARY_EMAIL" in source
    assert "ARGUS_CANARY_PASSWORD" in source
    assert "ARGUS_CANARY_PASSWORD is required" in source
    assert "set -x" not in source


def test_canary_exercises_confirmation_and_run_backtest_action() -> None:
    source = _source(".github/canary-render.sh")

    assert (
        "Test an equal-weight AAPL and MSFT buy-and-hold strategy from January 1, "
        "2025 through June 5, 2026 with 10,000 dollars"
        in source
    )
    assert 'action.get("type") == "run_backtest"' in source
    assert "/api/v1/backtest-jobs" in source
    assert "conversation did not persist async backtest_job metadata" in source
    assert "backtest_run" in source
    assert "backtest_jobs" in source
    assert "route_receipts" in source
    assert "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in source


def test_canary_fails_async_jobs_that_use_result_readout_fallback() -> None:
    source = _source(".github/canary-render.sh")

    assert 'source = payload.get("result_readout_source")' in source
    assert 'fallback_used = payload.get("result_readout_fallback_used")' in source
    assert 'source != "llm_explain_stage" or fallback_used is not False' in source
    assert "backtest job did not preserve LLM result readout voice" in source
    assert "select=id,status,result_run_id,execution_metadata" in source
    assert 'workflow_metadata = execution_metadata.get("workflow_backtest")' in source


def test_canary_requires_result_summary_route_receipt_for_completed_run() -> None:
    source = _source(".github/canary-render.sh")

    assert "task=eq.result_summary" in source
    assert "run_id=eq.${RESULT_RUN_ID}" in source
    assert "did not find canary result_summary route_receipts" in source
    assert 'result_run_id = str(job.get("result_run_id") or "").strip()' in source


def test_canary_uses_confirmation_card_run_action_payload() -> None:
    source = _source(".github/canary-render.sh")

    assert "RUN_ACTION=" in source
    assert "confirmation stream did not include run_backtest action" in source
    assert '"payload": {}' not in source
    assert 'json.loads(os.environ["RUN_ACTION"])' in source


def test_canary_passes_json_arguments_after_python_stdin_marker() -> None:
    source = _source(".github/canary-render.sh")

    assert 'python3 - "$MESSAGES_JSON" <<' in source
    assert (
        'python3 - "$BACKTEST_ROWS" "$RECEIPT_ROWS" "$JOB_ROWS" '
        '"$BACKTEST_JOB_ID" "$RESULT_RUN_ID" <<' in source
    )
    assert 'python3 - <<\'PY\' "$MESSAGES_JSON"' not in source
    assert 'python3 - <<\'PY\' "$BACKTEST_ROWS" "$RECEIPT_ROWS"' not in source
