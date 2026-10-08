from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from argus.agent_runtime.turn_execution import reserve_provider_call
from argus.llm import openrouter

from tests.evals import live_eval_budget as budget
from tests.evals import measurement_eval_harness as harness
from tests.evals import measurement_eval_scorecard as scorecards
from tests.evals.live_eval_budget import (
    PINNED,
    BoundTable,
    BudgetLedger,
    CaseBound,
    LiveEvalRequestRefused,
    TokenPrice,
    UnpricedCallError,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

# One dollar per million tokens in and out, and a thousand-byte cap, so every
# bound below is the token arithmetic written out.
FLAT = BoundTable(
    prices={
        "m": TokenPrice(Decimal("1"), Decimal("1"), "test"),
        "n": TokenPrice(Decimal("1"), Decimal("1"), "test"),
    },
    input_cap_bytes=1000,
)


@pytest.mark.parametrize("raw", ["", "   ", "0", "-1", "abc", "inf", "nan"])
def test_budget_env_refuses_missing_or_invalid(raw: str) -> None:
    with pytest.raises(RuntimeError, match="ARGUS_LIVE_EVAL_BUDGET_USD"):
        budget.live_eval_budget_usd({"ARGUS_LIVE_EVAL_BUDGET_USD": raw} if raw else {})


def test_budget_env_reads_a_positive_decimal() -> None:
    assert budget.live_eval_budget_usd({"ARGUS_LIVE_EVAL_BUDGET_USD": "5.00"}) == Decimal(
        "5.00"
    )


def test_post_bound_prices_every_input_byte_and_the_full_output_cap() -> None:
    table = BoundTable(
        prices={"x-ai/grok-4.3": TokenPrice(Decimal("1.25"), Decimal("2.50"), "test")},
        input_cap_bytes=1000,
    )
    # 1000 input tokens at 1.25 plus 3200 output tokens at 2.50, per million.
    assert table.post_bound_usd("interpretation", "x-ai/grok-4.3") == Decimal("0.00925")


def test_post_bound_refuses_an_unlisted_task_or_unpriced_model() -> None:
    with pytest.raises(UnpricedCallError, match="document_extraction"):
        FLAT.post_bound_usd("document_extraction", "m")
    with pytest.raises(UnpricedCallError, match="vendor/unpriced"):
        FLAT.post_bound_usd("interpretation", "vendor/unpriced")


def test_turn_bound_counts_the_research_reservations_only_when_research_is_reachable() -> (
    None
):
    candidates: dict[str, tuple[str, ...]] = {
        task: ("m",) for task in budget.BOUNDED_TASKS
    }

    # 7 x (1000 + 3200) + 2 x (1000 + 2200) + (1000 + 350) + (1000 + 600), per million.
    assert FLAT.turn_bound_usd(candidates, research_reachable=True) == Decimal("0.03875")
    # Research off grants neither knowledge_route nor knowledge_voicing.
    assert FLAT.turn_bound_usd(candidates, research_reachable=False) == Decimal("0.0358")


def test_judge_bound_is_the_candidate_ladder_posts() -> None:
    # Two candidates, two posts each, at 1000 + 1200 tokens per post.
    assert FLAT.judge_bound_usd(("m", "n")) == Decimal("0.0088")
    assert FLAT.judge_bound_usd(("m",)) == Decimal("0.0044")


def test_case_bound_counts_turns_and_the_judge_only_when_judged() -> None:
    judged = budget.case_bound(
        turns=2, judged=True, turn_usd=Decimal("1.5"), judge_usd=Decimal("0.25")
    )
    unjudged = budget.case_bound(
        turns=1, judged=False, turn_usd=Decimal("1.5"), judge_usd=Decimal("0.25")
    )

    assert judged.total_usd == Decimal("3.25")
    assert unjudged.total_usd == Decimal("1.5")
    assert judged.as_dict() == {
        "turns": 2,
        "turn_usd": "1.500000",
        "judge_usd": "0.250000",
        "total_usd": "3.250000",
    }


def test_guard_refuses_what_the_bound_does_not_cover() -> None:
    guard = BoundTable(prices=FLAT.prices, input_cap_bytes=64).request_guard()
    small: dict[str, object] = {
        "model": "m",
        "messages": [{"role": "user", "content": "hi"}],
    }

    assert guard("interpretation", small) is small
    with pytest.raises(LiveEvalRequestRefused, match="document_extraction"):
        guard("document_extraction", small)
    with pytest.raises(LiveEvalRequestRefused, match="vendor/unpriced"):
        guard("interpretation", {**small, "model": "vendor/unpriced"})
    with pytest.raises(LiveEvalRequestRefused, match="exceeds the 64 byte input cap"):
        guard(
            "interpretation",
            {**small, "messages": [{"role": "user", "content": "x" * 64}]},
        )


def test_receipt_charge_is_the_reported_cost_else_the_bound_else_nothing() -> None:
    reported = {
        "task": "interpretation",
        "model": "m",
        "outcome": "succeeded",
        "usage_cost_usd": 0.0123,
    }
    unreported = {
        "task": "interpretation",
        "model": "m",
        "outcome": "failed",
        "usage_cost_usd": None,
    }
    skipped = {
        "task": "interpretation",
        "model": "m",
        "outcome": "skipped",
        "usage_cost_usd": None,
    }
    refused = {**unreported, "failure_mode": "LiveEvalRequestRefused"}

    assert FLAT.receipt_charge_usd(reported) == Decimal("0.0123")
    assert FLAT.receipt_charge_usd(unreported) == Decimal("0.0042")
    assert FLAT.receipt_charge_usd(skipped) == Decimal("0")
    assert FLAT.receipt_charge_usd(refused) == Decimal("0")


def test_receipt_bound_violation_names_each_broken_assumption() -> None:
    base = {
        "task": "clarification",
        "model": "m",
        "outcome": "succeeded",
        "token_usage": {"prompt_tokens": 900, "completion_tokens": 300},
        "usage_cost_usd": 0.0012,
    }

    assert FLAT.receipt_bound_violation(base) is None
    assert (
        FLAT.receipt_bound_violation(
            {**base, "token_usage": {"prompt_tokens": 1001, "completion_tokens": 1}}
        )
        == "prompt_tokens 1001 exceeds the 1000 input cap"
    )
    assert (
        FLAT.receipt_bound_violation(
            {**base, "token_usage": {"prompt_tokens": 1, "completion_tokens": 361}}
        )
        == "completion_tokens 361 exceeds max_tokens 360"
    )
    assert FLAT.receipt_bound_violation({**base, "usage_cost_usd": 0.0013}) == (
        "cost 0.0013 exceeds the pinned rate's 0.001200"
    )
    assert FLAT.receipt_bound_violation({**base, "model": "vendor/unpriced"}) == (
        "model 'vendor/unpriced' billed without a pinned price"
    )


def _evidence_receipts() -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "usage_cost_usd" in node and "token_usage" in node and "model" in node:
                receipts.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in sorted((REPOSITORY_ROOT / "docs/reports/evidence").rglob("*.json")):
        try:
            walk(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return receipts


def test_pinned_rates_dominate_every_committed_receipt() -> None:
    """The table is a ceiling: no receipt in the committed evidence, for any
    model it prices, bills more than the pinned rates say it could."""
    # Prompt size was not capped when the evidence was recorded.
    uncapped = BoundTable(prices=PINNED.prices, input_cap_bytes=10**9)
    receipts = [
        receipt
        for receipt in _evidence_receipts()
        if receipt.get("model") in PINNED.prices
        and receipt.get("usage_cost_usd") is not None
        and receipt.get("token_usage")
    ]
    # Profile max_tokens moved since the older scorecards were recorded, so
    # the replay checks the rates alone: an unlisted task skips the output cap.
    violations = {
        receipt["model"]: reason
        for receipt in receipts
        if (reason := uncapped.receipt_bound_violation({**receipt, "task": "historic"}))
        is not None
    }

    assert len(receipts) > 300
    assert violations == {}


def _case(case_id: str, *, followup: bool = False) -> harness.EvalCase:
    return harness.EvalCase(
        id=case_id,
        category="messy_english",
        prompt="Explain this simply",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="conversation_followup", capability_verdict="answer_only"
        ),
        followup_prompt="and then?" if followup else None,
    )


def _result(case: harness.EvalCase, *, status: str, cost: float | None) -> dict[str, Any]:
    return {
        "id": case.id,
        "category": case.category,
        "status": status,
        "failed_checks": ["intent: expected x, got y"] if status == "failed" else [],
        "expected_fail": None,
        "typed_outcome": {},
        "prose_judge": None,
        "infrastructure_errors": [],
        # No token counts, so a reported cost is taken as the provider's word.
        "route_receipts": [
            {
                "task": "interpretation",
                "model": "m",
                "outcome": "succeeded" if cost is not None else "failed",
                "usage_cost_usd": cost,
                "token_usage": None,
            }
        ],
    }


def _bound(case: harness.EvalCase) -> CaseBound:
    return CaseBound(turns=1, turn_usd=Decimal("0.60"), judge_usd=Decimal(0))


def test_a_case_starts_only_while_the_remaining_budget_covers_its_bound() -> None:
    ledger = BudgetLedger(Decimal("1.00"))

    results = budget.run_budgeted_cases(
        [_case("first"), _case("second")],
        run_case=lambda case: _result(case, status="passed", cost=0.5),
        bound_for=_bound,
        ledger=ledger,
        table=FLAT,
    )

    assert [(r["id"], r["status"]) for r in results] == [
        ("first", "passed"),
        ("second", "skipped_budget"),
    ]
    assert results[1]["failed_checks"] == [
        "budget:remaining 0.500000 USD does not cover the 0.600000 USD bound"
    ]
    assert results[0]["budget"] == {
        "bound": {
            "turns": 1,
            "turn_usd": "0.600000",
            "judge_usd": "0.000000",
            "total_usd": "0.600000",
        },
        "charged_usd": "0.500000",
        "attempts": 1,
        "bound_violation": None,
    }
    summary = budget.budget_summary(ledger, results, table=FLAT)
    assert summary["spent_usd"] == "0.500000"
    assert summary["remaining_usd"] == "0.500000"
    assert summary["complete"] is False
    assert summary["cases"] == {
        "completed": 1,
        "failed": 0,
        "rerun": 0,
        "skipped_budget": 1,
    }
    assert summary["sum_of_case_bounds_usd"] == "1.200000"
    assert summary["input_cap_bytes"] == 1000
    assert harness.blocking_eval_results(results) == [results[1]]


def test_an_unreported_cost_is_charged_at_the_post_bound() -> None:
    ledger = BudgetLedger(Decimal("1.00"))

    results = budget.run_budgeted_cases(
        [_case("only")],
        run_case=lambda case: _result(case, status="passed", cost=None),
        bound_for=_bound,
        ledger=ledger,
        table=FLAT,
    )

    # One interpretation post at 1000 + 3200 tokens, per million.
    assert results[0]["budget"]["charged_usd"] == "0.004200"
    assert ledger.spent_usd == Decimal("0.0042")


def test_a_failed_case_reruns_once_and_only_while_the_budget_covers_it() -> None:
    calls: list[str] = []

    def always_fails(case: harness.EvalCase) -> dict[str, Any]:
        calls.append(case.id)
        return _result(case, status="failed", cost=0.10)

    covered = BudgetLedger(Decimal("2.00"))
    results = budget.run_budgeted_cases(
        [_case("flaky")],
        run_case=always_fails,
        bound_for=_bound,
        ledger=covered,
        table=FLAT,
    )
    assert calls == ["flaky", "flaky"]
    assert results[0]["status"] == "failed"
    assert results[0]["budget"]["attempts"] == 2
    assert results[0]["budget"]["first_attempt"] == {
        "status": "failed",
        "failed_checks": ["intent: expected x, got y"],
        "infrastructure_errors": [],
        "charged_usd": "0.100000",
    }
    assert covered.spent_usd == Decimal("0.20")
    assert budget.budget_summary(covered, results, table=FLAT)["cases"] == {
        "completed": 1,
        "failed": 1,
        "rerun": 1,
        "skipped_budget": 0,
    }

    calls.clear()
    tight = BudgetLedger(Decimal("0.65"))
    results = budget.run_budgeted_cases(
        [_case("flaky")],
        run_case=always_fails,
        bound_for=_bound,
        ledger=tight,
        table=FLAT,
    )
    assert calls == ["flaky"]
    assert results[0]["budget"]["attempts"] == 1
    assert "first_attempt" not in results[0]["budget"]


def test_a_receipt_outside_the_bound_stops_the_run() -> None:
    ledger = BudgetLedger(Decimal("10.00"))

    def overbilled(case: harness.EvalCase) -> dict[str, Any]:
        result = _result(case, status="passed", cost=0.5)
        result["route_receipts"][0]["token_usage"] = {
            "prompt_tokens": 10,
            "completion_tokens": 10,
        }
        return result

    results = budget.run_budgeted_cases(
        [_case("first"), _case("second")],
        run_case=overbilled,
        bound_for=_bound,
        ledger=ledger,
        table=FLAT,
    )

    # 10 + 10 tokens at a dollar per million can never bill 0.5.
    assert (
        results[0]["budget"]["bound_violation"]
        == "cost 0.5 exceeds the pinned rate's 0.000020"
    )
    assert results[0]["budget"]["charged_usd"] == "0.600000"
    assert results[1]["status"] == "skipped_budget"
    assert results[1]["failed_checks"] == [
        "budget:first: cost 0.5 exceeds the pinned rate's 0.000020"
    ]
    assert ledger.stopped_reason == "first: cost 0.5 exceeds the pinned rate's 0.000020"
    assert budget.budget_summary(ledger, results, table=FLAT)["complete"] is False


def test_refuse_unbounded_rails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARGUS_RESEARCH_RAIL_ENABLED", raising=False)
    budget.refuse_unbounded_rails({})
    with pytest.raises(RuntimeError, match="PERPLEXITY_API_KEY must be unset"):
        budget.refuse_unbounded_rails({"PERPLEXITY_API_KEY": "pplx-fixture"})
    with pytest.raises(RuntimeError, match="openrouter_web_search"):
        budget.refuse_unbounded_rails(
            {"ARGUS_DISCOVERY_SEARCH_PROVIDER": "openrouter_web_search"}
        )
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    with pytest.raises(RuntimeError, match="ARGUS_RESEARCH_RAIL_ENABLED must be off"):
        budget.refuse_unbounded_rails({})


def test_task_candidates_from_env_refuse_an_unpriced_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in {
        "ARGUS_STRUCTURED_MODEL": "x-ai/grok-4.3",
        "ARGUS_STRUCTURED_FALLBACK_MODEL": "anthropic/claude-haiku-4.5",
        "ARGUS_CHAT_MODEL": "deepseek/deepseek-v4-flash",
        "ARGUS_CHAT_FALLBACK_MODEL": "qwen/qwen3.5-9b",
        "ARGUS_CONTEXT_MODEL": "openai/gpt-oss-120b",
        "ARGUS_CONTEXT_FALLBACK_MODEL": "deepseek/deepseek-v4-flash",
    }.items():
        monkeypatch.setenv(name, value)

    candidates = PINNED.task_candidates_from_env()
    assert candidates["interpretation"] == ("x-ai/grok-4.3", "anthropic/claude-haiku-4.5")
    assert candidates["capability_conflict"] == (
        "openai/gpt-oss-120b",
        "deepseek/deepseek-v4-flash",
    )
    assert PINNED.judge_candidates_from_env(None) == (
        "deepseek/deepseek-v4-flash",
        "qwen/qwen3.5-9b",
    )
    assert PINNED.judge_candidates_from_env("x-ai/grok-4.3") == ("x-ai/grok-4.3",)

    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", "vendor/unpriced")
    with pytest.raises(UnpricedCallError, match="vendor/unpriced"):
        PINNED.task_candidates_from_env()
    with pytest.raises(UnpricedCallError, match="vendor/unpriced"):
        PINNED.judge_candidates_from_env("vendor/unpriced")


def test_run_eval_case_measures_inside_the_runtime_call_corridor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """During a case the runtime's own corridor refuses the eighth permit, and
    an installed guard refuses an unpriced post before it leaves the process."""
    permits: list[bool] = []
    refusals: list[str] = []

    def interpret_stage(**_kwargs: Any) -> Any:
        permits.extend(
            reserve_provider_call("interpretation", 1.0) is not None for _ in range(8)
        )
        try:
            openrouter._guard_request("interpretation", {"model": "vendor/unpriced"})
        except LiveEvalRequestRefused as exc:
            refusals.append(str(exc))
        return SimpleNamespace(
            outcome="ready_to_respond",
            patch={"intent": "conversation_followup", "assistant_response": "ok"},
        )

    monkeypatch.setattr(harness, "interpret_stage", interpret_stage)
    with openrouter.openrouter_request_guard(FLAT.request_guard()):
        result = harness.run_eval_case(_case("corridor"), run_prose_judge=False)

    assert permits == [True] * 7 + [False]
    assert refusals == ["model 'vendor/unpriced' has no pinned price"]
    assert result["status"] == "passed"
    # Outside a case there is no corridor.
    assert reserve_provider_call("interpretation", 1.0) is not None


def _live_scorecard(
    results: list[dict[str, Any]], budget_block: dict[str, Any] | None
) -> dict[str, Any]:
    provenance = scorecards.EvalScorecardProvenance(
        evaluation_mode="live",
        market_data_provider_mode="live_provider",
        asset_provider_mode="live_provider",
        candidate_sha="a" * 40,
        python_version="3.10.20",
        fixture_sha256="b" * 64,
        fixture_case_ids=tuple(result["id"] for result in results),
        worktree_clean=True,
        release_configuration={"ARGUS_CHAT_MODEL": "test/model"},
        live_market_data_probe=scorecards.LiveMarketDataProbe(
            symbol="SPY",
            requested_date_range={"start": "2024-01-01", "end": "2024-01-10"},
            effective_date_range={"start": "2024-01-02", "end": "2024-01-10"},
            adjustment_reason="calendar_alignment",
        ),
    )
    return scorecards.scorecard_for_results(
        results, provenance=provenance, budget=budget_block
    )


def test_an_incomplete_run_is_never_a_complete_scorecard() -> None:
    passed = {"id": "a", "category": "messy_english", "status": "passed"}
    skipped = {"id": "b", "category": "messy_english", "status": "skipped_budget"}
    complete_block = {"budget_usd": "5.000000", "spent_usd": "1.000000", "complete": True}

    complete = _live_scorecard([passed], complete_block)
    assert complete["schema_version"] == 4
    assert complete["totals"]["skipped_budget"] == 0
    scorecards.assert_scorecard_complete(complete)

    incomplete = _live_scorecard([passed, skipped], {**complete_block, "complete": False})
    assert incomplete["totals"] == {
        "passed": 1,
        "failed": 0,
        "expected_failed": 0,
        "unexpected_pass": 0,
        "skipped": 0,
        "infrastructure_error": 0,
        "skipped_budget": 1,
    }
    assert incomplete["category_pass_rates"]["messy_english"]["pass_rate"] == 1.0
    with pytest.raises(ValueError, match=r"incomplete_run skipped_for_budget=\['b'\]"):
        scorecards.assert_scorecard_complete(incomplete)

    with pytest.raises(ValueError, match="live_run_requires_budget"):
        _live_scorecard([passed], None)
    with pytest.raises(ValueError, match="incomplete_run stopped_reason='a: over'"):
        scorecards.assert_scorecard_complete(
            {
                **complete,
                "budget": {
                    **complete_block,
                    "complete": False,
                    "stopped_reason": "a: over",
                },
            }
        )
    # A schema 3 scorecard could not skip for budget and stands as written.
    scorecards.assert_scorecard_complete(
        {**complete, "schema_version": 3, "budget": None}
    )


def _judge_payload(content: str) -> dict[str, object]:
    return {
        "model": "m",
        "messages": [{"role": "user", "content": content}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": budget.JUDGE_SCHEMA_NAME, "schema": {}},
        },
    }


def test_the_judge_has_its_own_cap_and_the_turn_keeps_its_own() -> None:
    table = BoundTable(
        prices=FLAT.prices, input_cap_bytes=1000, judge_input_cap_bytes=400
    )
    guard = table.request_guard()

    assert guard("chat_composer", _judge_payload("x" * 200))
    with pytest.raises(LiveEvalRequestRefused, match="exceeds the 400 byte input cap"):
        guard("chat_composer", _judge_payload("x" * 500))
    # The in-turn composer shares the task but not the judge's schema.
    composer = {"model": "m", "messages": [{"role": "user", "content": "x" * 500}]}
    assert guard("chat_composer", composer) is composer
    # Two candidates, two posts each, at 400 + 1200 tokens per post.
    assert table.judge_bound_usd(("m", "n")) == Decimal("0.0064")
    unreported = {
        "task": "chat_composer",
        "schema_name": budget.JUDGE_SCHEMA_NAME,
        "model": "m",
        "outcome": "failed",
    }
    assert table.receipt_charge_usd(unreported) == Decimal("0.0016")


def test_a_refused_post_makes_the_case_incomplete_not_failed_and_never_rerun() -> None:
    calls: list[str] = []

    def refused(case: harness.EvalCase) -> dict[str, Any]:
        calls.append(case.id)
        result = _result(case, status="failed", cost=None)
        result["route_receipts"][0]["failure_mode"] = LiveEvalRequestRefused.__name__
        return result

    ledger = BudgetLedger(Decimal("5.00"))
    results = budget.run_budgeted_cases(
        [_case("long")], run_case=refused, bound_for=_bound, ledger=ledger, table=FLAT
    )

    assert calls == ["long"]
    assert results[0]["status"] == "skipped_budget"
    assert results[0]["failed_checks"][-1] == "budget:request_refused:interpretation"
    assert ledger.spent_usd == Decimal(0)
    assert budget.budget_summary(ledger, results, table=FLAT)["complete"] is False
