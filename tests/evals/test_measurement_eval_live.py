from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from tests.evals.measurement_eval_harness import (
    load_eval_cases,
    run_eval_case,
    write_scorecard,
)


def test_measurement_live_eval_suite_writes_scorecard() -> None:
    env_file = os.getenv("ARGUS_EVAL_ENV_FILE")
    if env_file:
        load_dotenv(Path(env_file), override=False)

    if os.getenv("ARGUS_RUN_LIVE_EVALS") != "1":
        pytest.skip("set ARGUS_RUN_LIVE_EVALS=1 to spend live LLM eval calls")
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY is required for live evals")

    results = [run_eval_case(case) for case in load_eval_cases()]
    scorecard_path = write_scorecard(results)
    failures = [
        {
            "id": result["id"],
            "category": result["category"],
            "failed_checks": result["failed_checks"],
        }
        for result in results
        if result["status"] == "failed"
    ]

    assert failures == [], (
        f"Argus eval failures; scorecard: {scorecard_path}\n{failures}"
    )
