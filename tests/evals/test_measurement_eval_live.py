# ruff: noqa: E402, I001 -- live-eval env must load before Argus imports
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import pytest

# Imports no Argus code, so it may load before the environment does.
from tests.evals.measurement_eval_scorecard import (
    assert_eval_env_file_untracked,
    build_scorecard_provenance,
    write_scorecard,
)

_EVAL_ENV_FILE = os.getenv("ARGUS_EVAL_ENV_FILE")
if _EVAL_ENV_FILE:
    # Argus imports load the shared project environment. Preload the explicit
    # live-eval environment so override=False preserves this suite's provider.
    # A tracked file is refused: evidence identity compares the tree, never
    # the eval's environment.
    assert_eval_env_file_untracked(Path(_EVAL_ENV_FILE))
    load_dotenv(Path(_EVAL_ENV_FILE), override=False)

from argus.domain.market_data.assets import clear_asset_cache
from argus.llm.openrouter import openrouter_request_guard
from tests.evals.live_eval_budget import (
    PINNED,
    BudgetLedger,
    budget_summary,
    case_bound,
    live_eval_budget_usd,
    refuse_unbounded_rails,
    run_budgeted_cases,
)
from argus.domain.research.config import research_rail_enabled
from tests.evals.measurement_eval_harness import (
    EvalCase,
    blocking_eval_results,
    expected_fail_issue_for_result,
    load_eval_cases,
)
from tests.evals.measurement_eval_scorecard import FIXTURE_SETS
from tests.evals.measurement_surface import live_eval_fixture_set, run_case_on_its_surface


def _assert_requested_live_eval_credentials() -> None:
    if not (os.getenv("OPENROUTER_API_KEY") or "").strip():
        raise RuntimeError("OPENROUTER_API_KEY is required for requested live evals")


def test_measurement_live_eval_suite_writes_scorecard(monkeypatch) -> None:
    if os.getenv("ARGUS_RUN_LIVE_EVALS") != "1":
        pytest.skip("set ARGUS_RUN_LIVE_EVALS=1 to spend live LLM eval calls")
    # Every refusal that needs no provider traffic comes before any traffic:
    # the budget, the credentials, the rails the bound cannot cover, and a
    # price for every model a bounded task can resolve to.
    ledger = BudgetLedger(live_eval_budget_usd(os.environ))
    fixture_set = live_eval_fixture_set(os.environ)
    _assert_requested_live_eval_credentials()
    refuse_unbounded_rails(os.environ)
    turn_usd = PINNED.turn_bound_usd(
        PINNED.task_candidates_from_env(), research_reachable=research_rail_enabled()
    )
    judge_usd = PINNED.judge_bound_usd(
        PINNED.judge_candidates_from_env(os.getenv("ARGUS_EVAL_JUDGE_MODEL"))
    )

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

    provenance = build_scorecard_provenance(
        evaluation_mode="live", fixture_set=fixture_set
    )

    def bound_for(case: EvalCase):
        return case_bound(
            turns=2 if case.followup_prompt else 1,
            judged=bool(case.prose_judge_criteria),
            turn_usd=turn_usd,
            judge_usd=judge_usd,
        )

    # The guard sees every OpenRouter post any case makes before it is sent.
    with openrouter_request_guard(PINNED.request_guard()):
        results = run_budgeted_cases(
            load_eval_cases(FIXTURE_SETS[fixture_set]),
            run_case=run_case_on_its_surface,
            bound_for=bound_for,
            ledger=ledger,
        )
    scorecard_path = write_scorecard(
        results,
        provenance=provenance,
        budget=budget_summary(ledger, results),
    )
    failures = [
        {
            "id": result["id"],
            "category": result["category"],
            "status": result["status"],
            "expected_fail_issue": expected_fail_issue_for_result(result),
            "failed_checks": result["failed_checks"],
            "infrastructure_errors": result["infrastructure_errors"],
        }
        for result in blocking_eval_results(results)
    ]

    assert failures == [], f"Argus eval failures; scorecard: {scorecard_path}\n{failures}"
