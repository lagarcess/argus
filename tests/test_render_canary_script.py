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
        "Test an equal-weight AAPL and MSFT strategy from 2025 to 2026 to date"
        in source
    )
    assert '"type":"run_backtest"' in source
    assert "/api/v1/backtest-jobs" in source
    assert "conversation did not persist async backtest_job metadata" in source
    assert "backtest_run" in source
    assert "backtest_jobs" in source
    assert "route_receipts" in source
    assert "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in source


def test_canary_passes_json_arguments_after_python_stdin_marker() -> None:
    source = _source(".github/canary-render.sh")

    assert 'python3 - "$MESSAGES_JSON" <<' in source
    assert 'python3 - "$BACKTEST_ROWS" "$RECEIPT_ROWS" "$JOB_ROWS" "$BACKTEST_JOB_ID" <<' in source
    assert 'python3 - <<\'PY\' "$MESSAGES_JSON"' not in source
    assert 'python3 - <<\'PY\' "$BACKTEST_ROWS" "$RECEIPT_ROWS"' not in source
