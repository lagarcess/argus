"""The Business live run, offline: its fixture set, its budget and its scorecard.

A fake transport stands in for OpenRouter; nothing here reaches a provider.
Both suites share one per-post ledger. A complete Business run writes a
scorecard marked as the Business set; a run the budget cuts short is
incomplete and refused.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from tests.evals import measurement_eval_scorecard as scorecards
from tests.evals import test_measurement_eval_live as live
from tests.evals.live_eval_budget import (
    SpendLedger,
    budget_summary,
    metered_openrouter,
    post_reservation_usd,
    run_metered_cases,
)
from tests.evals.measurement_eval_harness import load_eval_cases
from tests.evals.measurement_surface import (
    BUSINESS_FIXTURE_DIR,
    live_eval_fixture_sets,
)
from tests.release_promotion_evidence_support import assert_personal_measurement

BUSINESS_CASES = load_eval_cases(BUSINESS_FIXTURE_DIR)
URL = "https://openrouter.ai/api/v1/chat/completions"
POST = {
    "model": "deepseek/deepseek-v4-flash",
    "messages": [{"role": "user", "content": "x" * 4000}],
    "max_tokens": 1200,
}


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"sent": [], "cost": 0.0002}

    def send(self: httpx.Client, request: httpx.Request, **_: Any) -> httpx.Response:
        state["sent"].append(json.loads(request.content))
        usage = {} if state["cost"] is None else {"cost": state["cost"]}
        return httpx.Response(200, json={"choices": [], "usage": usage}, request=request)

    monkeypatch.setattr(httpx.Client, "send", send)
    return state


def test_the_live_run_names_its_fixture_sets() -> None:
    assert live_eval_fixture_sets({}) == ("personal",)
    assert live_eval_fixture_sets({"ARGUS_EVAL_FIXTURE_SET": "business"}) == ("business",)
    assert live_eval_fixture_sets({"ARGUS_EVAL_FIXTURE_SET": "all"}) == (
        "personal",
        "business",
    )
    with pytest.raises(RuntimeError, match="ARGUS_EVAL_FIXTURE_SET"):
        live_eval_fixture_sets({"ARGUS_EVAL_FIXTURE_SET": "Business"})


def test_a_live_run_is_refused_without_a_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_RUN_LIVE_EVALS", "1")
    monkeypatch.setenv("ARGUS_EVAL_FIXTURE_SET", "all")
    monkeypatch.delenv("ARGUS_LIVE_EVAL_BUDGET_USD", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "never-sent")

    with pytest.raises(RuntimeError, match="ARGUS_LIVE_EVAL_BUDGET_USD"):
        live.test_measurement_live_eval_suite_writes_scorecard(monkeypatch)


def _posting_case(case: Any) -> dict[str, Any]:
    with httpx.Client() as client:
        for _ in range(2):
            try:
                client.post(URL, json=POST)
            except RuntimeError:
                break
    return {
        "id": case.id,
        "category": case.category,
        "status": "passed",
        "failed_checks": [],
        "expected_fail": None,
        "typed_outcome": {},
        "prose_judge": None,
        "infrastructure_errors": [],
        "route_receipts": [],
    }


def _business_scorecard(results: list[dict[str, Any]], ledger: SpendLedger):  # noqa: ANN202
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
    network: dict[str, Any],
) -> None:
    ledger = SpendLedger(Decimal("5.00"))
    with metered_openrouter(ledger):
        results = run_metered_cases(BUSINESS_CASES, run_case=_posting_case, ledger=ledger)

    scorecard = _business_scorecard(results, ledger)

    scorecards.assert_scorecard_complete(scorecard)
    assert scorecard["provenance"]["fixture_set"] == "business"
    assert scorecard["totals"]["passed"] == 14
    assert len(network["sent"]) == 28
    # Each post's reservation was replaced by its reported 0.0002 USD.
    assert scorecard["budget"]["spent_usd"] == "0.005600"
    assert {post["charged_usd"] for post in scorecard["budget"]["posts"]} == {"0.000200"}


def test_a_business_run_the_budget_cut_short_is_incomplete_and_refused(
    network: dict[str, Any],
) -> None:
    body = json.dumps(POST, ensure_ascii=False, separators=(",", ":")).encode()
    _, each = post_reservation_usd(body)
    # No reported cost, so each post keeps its reservation: three fit.
    network["cost"] = None
    ledger = SpendLedger(each * Decimal("3.5"))
    with metered_openrouter(ledger):
        results = run_metered_cases(BUSINESS_CASES, run_case=_posting_case, ledger=ledger)

    statuses = [result["status"] for result in results]
    assert statuses[:2] == ["passed", "skipped_budget"]
    assert set(statuses[1:]) == {"skipped_budget"}
    assert len(network["sent"]) == 3
    assert ledger.committed_usd <= ledger.budget_usd
    scorecard = _business_scorecard(results, ledger)
    assert scorecard["budget"]["complete"] is False
    with pytest.raises(ValueError, match="incomplete_run"):
        scorecards.assert_scorecard_complete(scorecard)


def test_a_business_scorecard_is_never_the_promotion_measurement(
    network: dict[str, Any],
) -> None:
    ledger = SpendLedger(Decimal("5.00"))
    with metered_openrouter(ledger):
        results = run_metered_cases(BUSINESS_CASES, run_case=_posting_case, ledger=ledger)
    scorecard = _business_scorecard(results, ledger)

    with pytest.raises(AssertionError, match="not the promotion measurement"):
        assert_personal_measurement(scorecard["provenance"])
    personal = {**scorecard["provenance"]}
    personal.pop("fixture_set")
    assert_personal_measurement(personal)
