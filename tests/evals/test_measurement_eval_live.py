from __future__ import annotations

import os
from pathlib import Path

import pytest
from argus.domain.market_data.assets import clear_asset_cache
from dotenv import load_dotenv

from tests.evals.measurement_eval_harness import (
    blocking_eval_results,
    expected_fail_issue_for_result,
    load_eval_cases,
    run_eval_case,
    write_scorecard,
)


def test_measurement_live_eval_suite_writes_scorecard(monkeypatch) -> None:
    env_file = os.getenv("ARGUS_EVAL_ENV_FILE")
    if env_file:
        load_dotenv(Path(env_file), override=False)

    if os.getenv("ARGUS_RUN_LIVE_EVALS") != "1":
        pytest.skip("set ARGUS_RUN_LIVE_EVALS=1 to spend live LLM eval calls")
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is required for live evals")

    if not (os.getenv("ARGUS_ASSET_PROVIDER_MODE") or "").strip():
        asset_provider_mode = (
            "recorded_provider_fixture"
            if (os.getenv("ARGUS_ASSET_FIXTURE_PATH") or "").strip()
            else "live_provider"
        )
        monkeypatch.setenv("ARGUS_ASSET_PROVIDER_MODE", asset_provider_mode)
    if os.getenv("ARGUS_ASSET_PROVIDER_MODE") == "live_provider" and not all(
        (os.getenv(name) or "").strip()
        for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY")
    ):
        pytest.fail(
            "live eval company-name grounding requires Alpaca asset-catalog keys "
            "or a recorded ARGUS_ASSET_FIXTURE_PATH"
        )
    clear_asset_cache()

    results = [run_eval_case(case) for case in load_eval_cases()]
    scorecard_path = write_scorecard(results)
    failures = [
        {
            "id": result["id"],
            "category": result["category"],
            "status": result["status"],
            "expected_fail_issue": expected_fail_issue_for_result(result),
            "failed_checks": result["failed_checks"],
        }
        for result in blocking_eval_results(results)
    ]

    assert failures == [], f"Argus eval failures; scorecard: {scorecard_path}\n{failures}"
