from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ops.canary_capture_replay import replay_capture


def _capture_payload(language: str = "es-419") -> dict[str, object]:
    return {
        "schema_version": 1,
        "privacy": "no_raw_ids; labels are sha256 prefixes",
        "failure": {
            "stage": "backtest_job",
            "reason": "backtest_job_parse_failed",
            "status": "failed",
        },
        "launch_payload": {
            "language": language,
            "message": "Canary prompt",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL", "MSFT"],
                    "date_range": {"start": "2025-01-01", "end": "2026-06-05"},
                },
                "optional_parameters": {},
            },
        },
        "result_card": {
            "title": "AAPL + MSFT",
            "benchmark_symbol": "SPY",
        },
        "explanation_context": {
            "benchmark_symbol": "SPY",
            "result_card": {
                "title": "AAPL + MSFT",
                "benchmark_symbol": "SPY",
            },
        },
        "final_response_payload": {
            "result": {"total_return": 0.1284, "benchmark_return": 0.2614},
            "explanation_context": {"benchmark_symbol": "SPY"},
        },
        "route_receipt": {
            "task": "result_summary",
            "status": "present",
        },
    }


def test_replay_capture_renders_canonical_quick_take_from_sanitized_payload() -> None:
    report = replay_capture(_capture_payload())

    assert report["language"] == "es-419"
    assert report["failure"] == {
        "stage": "backtest_job",
        "reason": "backtest_job_parse_failed",
        "status": "failed",
    }
    assert report["route_receipt"]["status"] == "present"
    assert "La estrategia rindió 12.8% mientras SPY rindió 26.1%" in report[
        "quick_take"
    ]


def test_replay_capture_accepts_future_locale_shape_through_fallback_language() -> None:
    report = replay_capture(_capture_payload(language="fr-CA"))

    assert report["language"] == "fr-CA"
    assert report["resolved_language"] == "en"
    assert "The strategy returned 12.8% while SPY returned 26.1%" in report[
        "quick_take"
    ]


def test_replay_capture_rejects_raw_ids_or_secret_like_values() -> None:
    payload = _capture_payload()
    payload["conversation_id"] = "453523c4-164c-423f-814c-2afad15d7ce0"

    with pytest.raises(ValueError, match="raw UUID"):
        replay_capture(payload)


def test_replay_capture_rejects_embedded_or_artifact_identifiers() -> None:
    payload = _capture_payload()
    payload["source"] = "result/453523c4-164c-423f-814c-2afad15d7ce0/reload"

    with pytest.raises(ValueError, match="raw UUID"):
        replay_capture(payload)

    payload = _capture_payload()
    payload["artifact_id"] = "artifact-without-a-safe-label"

    with pytest.raises(ValueError, match="raw id-like field"):
        replay_capture(payload)


def test_replay_capture_direct_cli_loads_shared_sanitizer() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "ops" / "canary_capture_replay.py"),
            "--help",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "sanitized canary capture" in result.stdout


def test_replay_capture_accepts_sanitized_labels_and_redactions() -> None:
    payload = _capture_payload()
    payload["job_response"] = {
        "id": "id_abcdef123456",
        "run_id": "run_id_123456abcdef",
        "access_token": "<redacted>",
    }

    report = replay_capture(payload)

    assert report["quick_take"]


def test_replay_capture_rejects_unhashed_id_like_values() -> None:
    payload = _capture_payload()
    payload["job_response"] = {"run_id": "internal-run-123"}

    with pytest.raises(ValueError, match="raw id-like field"):
        replay_capture(payload)
