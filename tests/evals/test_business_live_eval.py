"""The Business live run, offline: its fixture set, its bound and its scorecard.

Fake cases and fake receipts only; nothing here reaches a provider. A complete
Business run writes a scorecard marked as the Business set, a run the budget
cuts short is incomplete and refused, and the release profile's bounds are
pinned with research off.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.evals import measurement_eval_scorecard as scorecards
from tests.evals import test_measurement_eval_live as live
from tests.evals.live_eval_budget import (
    PINNED,
    BudgetLedger,
    budget_summary,
    case_bound,
    run_budgeted_cases,
)
from tests.evals.measurement_eval_harness import load_eval_cases
from tests.evals.measurement_surface import (
    BUSINESS_FIXTURE_DIR,
    live_eval_fixture_set,
)
from tests.release_promotion_evidence_support import assert_personal_measurement

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BUSINESS_CASES = load_eval_cases(BUSINESS_FIXTURE_DIR)


@pytest.fixture
def release_models(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = yaml.safe_load((REPOSITORY_ROOT / "render.yaml").read_text())
    (api,) = [svc for svc in profile["services"] if svc["name"] == "argus-api"]
    for item in api["envVars"]:
        if item["key"].endswith("_MODEL") and "value" in item:
            monkeypatch.setenv(item["key"], str(item["value"]))


def _bounds(*, research_reachable: bool) -> tuple[Decimal, Decimal]:
    turn = PINNED.turn_bound_usd(
        PINNED.task_candidates_from_env(), research_reachable=research_reachable
    )
    return turn, PINNED.judge_bound_usd(PINNED.judge_candidates_from_env(None))


def _bound_for(turn: Decimal, judge: Decimal):  # noqa: ANN202
    return lambda case: case_bound(
        turns=2 if case.followup_prompt else 1,
        judged=bool(case.prose_judge_criteria),
        turn_usd=turn,
        judge_usd=judge,
    )


def test_release_profile_bounds_with_research_off(release_models: None) -> None:
    turn, judge = _bounds(research_reachable=False)
    # 7 x 0.13888 (haiku interpretation) + 2 x 0.13388 (haiku repair grant).
    assert turn == Decimal("1.23992")
    # 4 judge posts x 0.018784 (deepseek, 32,768 input + 1,200 output tokens).
    assert judge == Decimal("0.075136")
    assert _bounds(research_reachable=True)[0] == Decimal("1.414902")

    per_case = [_bound_for(turn, judge)(case).total_usd for case in BUSINESS_CASES]
    assert sorted(set(per_case)) == [Decimal("1.23992"), Decimal("1.315056")]
    assert sum(per_case) == Decimal("18.185376")
    # Every case may run once more after a failure.
    assert 2 * sum(per_case) == Decimal("36.370752")
    personal = load_eval_cases()
    personal_total = sum(_bound_for(turn, judge)(case).total_usd for case in personal)
    assert personal_total == Decimal("108.511520")


def test_the_live_run_names_its_fixture_set() -> None:
    assert live_eval_fixture_set({}) == "personal"
    assert live_eval_fixture_set({"ARGUS_EVAL_FIXTURE_SET": "business"}) == "business"
    with pytest.raises(RuntimeError, match="ARGUS_EVAL_FIXTURE_SET"):
        live_eval_fixture_set({"ARGUS_EVAL_FIXTURE_SET": "Business"})


def test_a_business_live_run_is_refused_without_a_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_RUN_LIVE_EVALS", "1")
    monkeypatch.setenv("ARGUS_EVAL_FIXTURE_SET", "business")
    monkeypatch.delenv("ARGUS_LIVE_EVAL_BUDGET_USD", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "never-sent")

    with pytest.raises(RuntimeError, match="ARGUS_LIVE_EVAL_BUDGET_USD"):
        live.test_measurement_live_eval_suite_writes_scorecard(monkeypatch)


def _fake_case(case: Any) -> dict[str, Any]:
    return {
        "id": case.id,
        "category": case.category,
        "status": "passed",
        "failed_checks": [],
        "infrastructure_errors": [],
        "route_receipts": [
            {
                "task": "interpretation",
                "model": "x-ai/grok-4.3",
                "outcome": "succeeded",
                "usage_cost_usd": 0.0002,
                "token_usage": {"prompt_tokens": 100, "completion_tokens": 50},
            }
        ],
    }


def _business_scorecard(results: list[dict[str, Any]], ledger: BudgetLedger):  # noqa: ANN202
    identity = scorecards.measurement_fixture_identity(BUSINESS_FIXTURE_DIR)
    provenance = scorecards.EvalScorecardProvenance(
        evaluation_mode="live",
        market_data_provider_mode="live_provider",
        asset_provider_mode="live_provider",
        candidate_sha="a" * 40,
        python_version="3.10.20",
        fixture_sha256=identity.sha256,
        fixture_case_ids=identity.case_ids,
        worktree_clean=True,
        release_configuration={"ARGUS_CHAT_MODEL": "deepseek/deepseek-v4-flash"},
        live_market_data_probe=scorecards.LiveMarketDataProbe(
            symbol="SPY",
            requested_date_range={"start": "2024-01-01", "end": "2024-01-10"},
            effective_date_range={"start": "2024-01-02", "end": "2024-01-10"},
            adjustment_reason="calendar_alignment",
        ),
        fixture_set="business",
    )
    return scorecards.scorecard_for_results(
        results, provenance=provenance, budget=budget_summary(ledger, results)
    )


def test_a_complete_business_run_is_a_complete_business_scorecard(
    release_models: None,
) -> None:
    ledger = BudgetLedger(Decimal("40.00"))
    results = run_budgeted_cases(
        BUSINESS_CASES,
        run_case=_fake_case,
        bound_for=_bound_for(*_bounds(research_reachable=False)),
        ledger=ledger,
    )

    scorecard = _business_scorecard(results, ledger)

    scorecards.assert_scorecard_complete(scorecard)
    assert scorecard["provenance"]["fixture_set"] == "business"
    assert scorecard["totals"]["passed"] == 14
    assert scorecard["budget"]["spent_usd"] == "0.002800"
    assert scorecard["budget"]["cases"] == {
        "completed": 14,
        "failed": 0,
        "rerun": 0,
        "skipped_budget": 0,
    }


def test_a_business_run_the_budget_cut_short_is_incomplete_and_refused(
    release_models: None,
) -> None:
    # Covers an unjudged case's 1.23992 bound but no judged case's 1.315056.
    ledger = BudgetLedger(Decimal("1.30"))
    results = run_budgeted_cases(
        BUSINESS_CASES,
        run_case=_fake_case,
        bound_for=_bound_for(*_bounds(research_reachable=False)),
        ledger=ledger,
    )

    statuses = [result["status"] for result in results]
    assert statuses.count("passed") == 3
    assert statuses.count("skipped_budget") == 11
    scorecard = _business_scorecard(results, ledger)
    assert scorecard["budget"]["complete"] is False
    with pytest.raises(ValueError, match="incomplete_run skipped_for_budget"):
        scorecards.assert_scorecard_complete(scorecard)


def test_a_business_scorecard_is_never_the_promotion_measurement(
    release_models: None,
) -> None:
    ledger = BudgetLedger(Decimal("40.00"))
    results = run_budgeted_cases(
        BUSINESS_CASES,
        run_case=_fake_case,
        bound_for=_bound_for(*_bounds(research_reachable=False)),
        ledger=ledger,
    )
    scorecard = _business_scorecard(results, ledger)

    with pytest.raises(AssertionError, match="not the promotion measurement"):
        assert_personal_measurement(scorecard["provenance"])
    personal = {**scorecard["provenance"]}
    personal.pop("fixture_set")
    assert_personal_measurement(personal)
