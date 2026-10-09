"""The per-post spend guard, offline: a fake transport stands in for the network."""

from __future__ import annotations

import asyncio
import json
import math
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from argus.llm import openrouter
from pydantic import BaseModel

from tests.evals import live_eval_budget as budget
from tests.evals import measurement_eval_harness as harness
from tests.evals import measurement_eval_scorecard as scorecards
from tests.evals.live_eval_budget import (
    LiveEvalRequestRefused,
    SpendLedger,
    metered_openrouter,
    post_reservation_usd,
    record_task,
    run_metered_cases,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
URL = "https://openrouter.ai/api/v1/chat/completions"
GROK = "x-ai/grok-4.3"
HAIKU = "anthropic/claude-haiku-4.5"
DEEPSEEK = "deepseek/deepseek-v4-flash"
ACCEPTED = (
    REPOSITORY_ROOT
    / "docs/reports/evidence/current-reason-date-range/accepted-measurement"
    / "live-measurement.json"
)
PAIRS = (
    REPOSITORY_ROOT
    / "docs/reports/evidence/live-eval-per-call-guard/input-bound-pairs.json"
)

Responder = Callable[[httpx.Request], httpx.Response]


def _body(
    model: str = GROK, *, max_tokens: int = 100, text: str = "hi"
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": text}],
        "max_tokens": max_tokens,
    }


def _bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def _reply(cost: float | None = 0.0001, status: int = 200) -> Responder:
    def respond(request: httpx.Request) -> httpx.Response:
        usage: dict[str, Any] = {"prompt_tokens": 10, "completion_tokens": 5}
        if cost is not None:
            usage["cost"] = cost
        content = {"choices": [{"message": {"content": "{}"}}], "usage": usage}
        return httpx.Response(status, json=content, request=request)

    return respond


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The transport the guard wraps; it records what actually left."""
    state: dict[str, Any] = {"sent": [], "respond": _reply()}

    def send(self: httpx.Client, request: httpx.Request, **_: Any) -> httpx.Response:
        if request.url.host == "openrouter.ai":
            state["sent"].append(json.loads(request.content))
            return state["respond"](request)
        return httpx.Response(200, json={}, request=request)

    async def asend(
        self: httpx.AsyncClient, request: httpx.Request, **_: Any
    ) -> httpx.Response:
        return send(self, request)

    monkeypatch.setattr(httpx.Client, "send", send)
    monkeypatch.setattr(httpx.AsyncClient, "send", asend)
    return state


def _post(payload: dict[str, Any]) -> httpx.Response:
    with httpx.Client() as client:
        return client.post(URL, json=payload)


@pytest.mark.parametrize("raw", ["", "   ", "0", "-1", "abc", "inf", "nan"])
def test_budget_env_refuses_missing_or_invalid(raw: str) -> None:
    with pytest.raises(RuntimeError, match="ARGUS_LIVE_EVAL_BUDGET_USD"):
        budget.live_eval_budget_usd({"ARGUS_LIVE_EVAL_BUDGET_USD": raw} if raw else {})


def test_budget_env_reads_a_positive_decimal() -> None:
    assert budget.live_eval_budget_usd({"ARGUS_LIVE_EVAL_BUDGET_USD": "5.00"}) == Decimal(
        "5.00"
    )


def test_a_reservation_is_the_request_bytes_and_its_output_cap_at_the_models_ceiling() -> (
    None
):
    payload = _body(GROK, max_tokens=3200, text="x" * 1000)
    size = len(_bytes(payload))
    # Every body byte at 1.25 per million, 3,200 output tokens at 2.50.
    assert post_reservation_usd(_bytes(payload)) == (
        GROK,
        (Decimal(size) * Decimal("1.25") + Decimal(3200) * Decimal("2.50")) / 1_000_000,
    )
    # deepseek once billed past max_tokens, so its output is reserved twice over.
    _, deepseek = post_reservation_usd(_bytes(_body(DEEPSEEK, max_tokens=900)))
    size = len(_bytes(_body(DEEPSEEK, max_tokens=900)))
    assert (
        deepseek == (Decimal(size) * Decimal("0.50") + 1800 * Decimal("2.00")) / 1_000_000
    )
    document = {**_body(HAIKU), "max_completion_tokens": 50}
    del document["max_tokens"]
    assert post_reservation_usd(_bytes(document))[0] == HAIKU


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (_body("vendor/unpriced"), "has no pinned price"),
        ({"model": GROK, "messages": []}, "no max_tokens"),
        ({**_body(), "plugins": [{"id": "web"}]}, "web search"),
        (_body(f"{GROK}:online"), "has no pinned price"),
        ({**_body(), "stream": True}, "streamed"),
    ],
)
def test_a_post_that_cannot_be_reserved_is_refused(
    payload: dict[str, Any], reason: str
) -> None:
    with pytest.raises(LiveEvalRequestRefused, match=reason):
        post_reservation_usd(_bytes(payload))


def test_a_190_kb_prompt_is_reserved_at_its_real_size_and_sent(
    network: dict[str, Any],
) -> None:
    # The largest committed receipt: grok interpretation, 39,522 prompt tokens
    # billed 0.0519384 USD. At the evidence's 4.9 bytes per token its request
    # was about 193,658 bytes.
    payload = _body(GROK, max_tokens=3200, text="x" * 193_500)
    size = len(_bytes(payload))
    ledger = SpendLedger(Decimal("5.00"))

    with metered_openrouter(ledger):
        _post(payload)

    (post,) = ledger.posts
    assert size > 190_000
    assert post["body_bytes"] == size
    assert Decimal(post["reserved_usd"]) == Decimal("0.249981")
    assert Decimal(post["reserved_usd"]) > Decimal("0.0519384") * 4
    assert len(network["sent"]) == 1


def test_a_post_the_budget_cannot_cover_is_refused_before_it_is_sent(
    network: dict[str, Any],
) -> None:
    ledger = SpendLedger(Decimal("0.0001"))

    with metered_openrouter(ledger), pytest.raises(LiveEvalRequestRefused):
        _post(_body(max_tokens=3200))

    assert network["sent"] == []
    assert ledger.spent_usd == Decimal(0)
    assert ledger.posts[0]["refused"] is True
    assert ledger.stopped_reason is not None
    # Once stopped, even a post the budget could cover is refused.
    ledger.budget_usd = Decimal("10")
    with metered_openrouter(ledger), pytest.raises(LiveEvalRequestRefused):
        _post(_body(max_tokens=1))
    assert network["sent"] == []


@pytest.mark.parametrize(
    ("respond", "charged"),
    [
        (_reply(cost=0.000123), "0.000123"),
        (_reply(cost=None), "reserved"),
        (_reply(cost=0.000123, status=500), "reserved"),
    ],
)
def test_settlement_charges_the_reported_cost_else_the_whole_reservation(
    network: dict[str, Any], respond: Responder, charged: str
) -> None:
    network["respond"] = respond
    ledger = SpendLedger(Decimal("1.00"))

    with metered_openrouter(ledger):
        _post(_body())

    (post,) = ledger.posts
    expected = post["reserved_usd"] if charged == "reserved" else charged
    assert post["charged_usd"] == expected
    assert ledger.spent_usd.quantize(Decimal("0.000001")) == Decimal(expected)
    assert ledger.committed_usd == ledger.spent_usd


def test_a_post_that_never_answers_keeps_its_reservation_charged(
    network: dict[str, Any],
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    network["respond"] = timeout
    ledger = SpendLedger(Decimal("1.00"))

    with metered_openrouter(ledger), pytest.raises(httpx.ReadTimeout):
        _post(_body())

    assert ledger.spent_usd == post_reservation_usd(_bytes(_body()))[1]


def test_a_bill_above_its_reservation_stops_the_run(network: dict[str, Any]) -> None:
    network["respond"] = _reply(cost=1.0)
    ledger = SpendLedger(Decimal("5.00"))

    with metered_openrouter(ledger):
        _post(_body())

    assert ledger.stopped_reason is not None
    assert "over its" in ledger.stopped_reason


def test_concurrent_reservations_never_overshoot_the_budget(
    network: dict[str, Any],
) -> None:
    payload = _body(max_tokens=3200)
    _, each = post_reservation_usd(_bytes(payload))
    ledger = SpendLedger(each * 10 + each / 2)
    in_flight = threading.Semaphore(0)
    peaks: list[Decimal] = []

    def slow(request: httpx.Request) -> httpx.Response:
        peaks.append(ledger.committed_usd)
        in_flight.release()
        return _reply(cost=None)(request)

    network["respond"] = slow

    def thread_post(_: int) -> str:
        try:
            _post(payload)
            return "sent"
        except LiveEvalRequestRefused:
            return "refused"

    async def async_posts() -> list[str]:
        async def one() -> str:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(URL, json=payload)
                return "sent"
            except LiveEvalRequestRefused:
                return "refused"

        return list(await asyncio.gather(*(one() for _ in range(12))))

    with metered_openrouter(ledger), ThreadPoolExecutor(max_workers=12) as pool:
        threaded = pool.map(thread_post, range(12))
        outcomes = [*asyncio.run(async_posts()), *threaded]

    assert outcomes.count("sent") == 10
    assert len(network["sent"]) == 10
    assert max(peaks) <= ledger.budget_usd
    assert ledger.spent_usd == each * 10 <= ledger.budget_usd


class _Answer(BaseModel):
    answer: str


def test_every_fallback_and_reasoning_retry_is_its_own_reservation(
    network: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline")
    monkeypatch.setenv("ARGUS_STRUCTURED_MODEL", GROK)
    monkeypatch.setenv("ARGUS_STRUCTURED_FALLBACK_MODEL", HAIKU)
    replies = iter(
        [
            httpx.Response(400, json={"error": "reasoning"}),
            httpx.Response(500, json={"error": "upstream"}),
        ]
    )

    def respond(request: httpx.Request) -> httpx.Response:
        try:
            reply = next(replies)
            return httpx.Response(reply.status_code, json=reply.json(), request=request)
        except StopIteration:
            content = {
                "choices": [{"message": {"content": json.dumps({"answer": "ok"})}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 3, "cost": 0.0002},
            }
            return httpx.Response(200, json=content, request=request)

    network["respond"] = respond
    ledger = SpendLedger(Decimal("5.00"))

    with openrouter.openrouter_request_guard(record_task), metered_openrouter(ledger):
        answer = asyncio.run(
            openrouter.invoke_openrouter_json_schema(
                task="interpretation",
                messages=[{"role": "user", "content": "hello"}],
                schema_model=_Answer,
                schema_name="Answer",
            )
        )

    assert isinstance(answer, _Answer)
    assert [(post["task"], post["model"]) for post in ledger.posts] == [
        ("interpretation", GROK),
        ("interpretation", GROK),
        ("interpretation", HAIKU),
    ]
    assert "reasoning" in network["sent"][0] and "reasoning" not in network["sent"][1]
    charged = [post["charged_usd"] for post in ledger.posts]
    assert charged[:2] == [post["reserved_usd"] for post in ledger.posts[:2]]
    assert charged[2] == "0.000200"


def test_the_prose_judge_reserves_its_post(
    network: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline")
    monkeypatch.setenv("ARGUS_CHAT_MODEL", DEEPSEEK)

    def respond(request: httpx.Request) -> httpx.Response:
        verdict = {"pass": True, "failed_criteria": [], "notes": ""}
        content = {
            "choices": [{"message": {"content": json.dumps(verdict)}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 3, "cost": 0.00001},
        }
        return httpx.Response(200, json=content, request=request)

    network["respond"] = respond
    ledger = SpendLedger(Decimal("5.00"))
    case = _case("judged")

    with openrouter.openrouter_request_guard(record_task), metered_openrouter(ledger):
        verdict = harness.judge_prose_quality(
            case=case, assistant_text="An answer.", rendered_beside_reply={}
        )

    assert verdict["pass"] is True
    assert [(post["task"], post["model"]) for post in ledger.posts] == [
        ("chat_composer", DEEPSEEK)
    ]


def test_a_post_to_another_host_passes_unmetered(network: dict[str, Any]) -> None:
    ledger = SpendLedger(Decimal("0.0000001"))

    with metered_openrouter(ledger), httpx.Client() as client:
        client.get("https://data.alpaca.markets/v2/clock")

    assert ledger.posts == []


def _case(case_id: str) -> harness.EvalCase:
    return harness.EvalCase(
        id=case_id,
        category="messy_english",
        prompt="Explain this simply",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="conversation_followup", capability_verdict="answer_only"
        ),
        prose_judge_criteria=("honesty",),
    )


def _posting_case(
    posts: int, *, status: str = "passed"
) -> Callable[[Any], dict[str, Any]]:
    def run(case: harness.EvalCase) -> dict[str, Any]:
        for _ in range(posts):
            try:
                _post(_body(max_tokens=3200))
            except LiveEvalRequestRefused:
                break
        return {
            "id": case.id,
            "category": case.category,
            "status": status,
            "failed_checks": ["intent: expected x, got y"] if status == "failed" else [],
            "expected_fail": None,
            "typed_outcome": {},
            "prose_judge": None,
            "infrastructure_errors": [],
            "route_receipts": [],
        }

    return run


def test_the_run_stops_at_the_first_refusal_and_is_incomplete(
    network: dict[str, Any],
) -> None:
    _, each = post_reservation_usd(_bytes(_body(max_tokens=3200)))
    network["respond"] = _reply(cost=None)
    ledger = SpendLedger(each * 5)

    with metered_openrouter(ledger):
        results = run_metered_cases(
            [_case("a"), _case("b"), _case("c")],
            run_case=_posting_case(3, status="failed"),
            ledger=ledger,
        )

    # a fails and reruns (6 posts would pass 5), so the rerun is refused.
    assert [(r["id"], r["status"]) for r in results] == [
        ("a", "skipped_budget"),
        ("b", "skipped_budget"),
        ("c", "skipped_budget"),
    ]
    assert results[0]["budget"]["attempts"] == 2
    assert len(network["sent"]) == 5
    assert ledger.spent_usd == each * 5
    summary = budget.budget_summary(ledger, results)
    assert summary["complete"] is False
    assert summary["cases"]["skipped_budget"] == 3
    assert [post["refused"] for post in summary["posts"]] == [False] * 5 + [True]


def test_a_failed_case_reruns_once_while_the_run_goes_on(
    network: dict[str, Any],
) -> None:
    calls: list[str] = []

    def failing(case: harness.EvalCase) -> dict[str, Any]:
        calls.append(case.id)
        return _posting_case(1, status="failed")(case)

    ledger = SpendLedger(Decimal("5.00"))
    with metered_openrouter(ledger):
        results = run_metered_cases([_case("flaky")], run_case=failing, ledger=ledger)

    assert calls == ["flaky", "flaky"]
    assert results[0]["status"] == "failed"
    assert results[0]["budget"]["first_attempt"]["status"] == "failed"
    assert budget.budget_summary(ledger, results)["complete"] is True


def _live_scorecard(results: list[dict[str, Any]], budget_block: dict[str, Any]):  # noqa: ANN202
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


def test_promotion_and_prompt_freeze_consumers_reject_an_incomplete_run(
    network: dict[str, Any],
) -> None:
    from tests.test_interpreter_prompt_freeze import assert_scorecard_measures_the_prompt

    _, each = post_reservation_usd(_bytes(_body(max_tokens=3200)))
    network["respond"] = _reply(cost=None)
    ledger = SpendLedger(each * 2)
    with metered_openrouter(ledger):
        results = run_metered_cases(
            [_case("a"), _case("b")], run_case=_posting_case(3), ledger=ledger
        )
    scorecard = _live_scorecard(results, budget.budget_summary(ledger, results))

    with pytest.raises(ValueError, match="incomplete_run"):
        scorecards.assert_scorecard_complete(scorecard)
    with pytest.raises(ValueError, match="incomplete_run"):
        assert_scorecard_measures_the_prompt(scorecard, measured_commit="a" * 40)


def test_replaying_the_accepted_run_at_maximum_cost_never_passes_the_budget(
    network: dict[str, Any],
) -> None:
    """Every recorded post, sized at four bytes per billed prompt token, bills
    its whole reservation: the run stops before the budget, incomplete."""
    accepted = json.loads(ACCEPTED.read_text(encoding="utf-8"))
    recorded = {
        result["id"]: [
            receipt
            for receipt in result.get("route_receipts") or []
            if receipt.get("outcome") != "skipped"
            and receipt.get("model") in budget.PRICE_TABLE_USD_PER_MILLION
        ]
        for result in accepted["results"]
    }

    def at_maximum(request: httpx.Request) -> httpx.Response:
        _, reserved = post_reservation_usd(request.content)
        return _reply(cost=float(reserved) * 0.999999)(request)

    network["respond"] = at_maximum

    def replay(case: Any) -> dict[str, Any]:
        for receipt in recorded[case.id]:
            tokens = (receipt.get("token_usage") or {}).get("prompt_tokens") or 1000
            try:
                _post(_body(receipt["model"], max_tokens=3200, text="x" * (4 * tokens)))
            except LiveEvalRequestRefused:
                break
        return _posting_case(0)(case)

    ledger = SpendLedger(Decimal("5.00"))
    cases = [_case(case_id) for case_id in recorded]
    with metered_openrouter(ledger):
        results = run_metered_cases(cases, run_case=replay, ledger=ledger)

    assert ledger.committed_usd <= Decimal("5.00")
    assert ledger.spent_usd <= Decimal("5.00")
    assert ledger.stopped_reason is not None
    assert budget.budget_summary(ledger, results)["complete"] is False
    assert sum(1 for r in results if r["status"] == "skipped_budget") > 0
    assert len(cases) == 73


def test_the_input_bound_covers_every_paired_committed_receipt() -> None:
    """Regenerate with `python -m tests.evals.input_bound_proof <path>`."""
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    ratios = [pair["body_bytes"] / pair["billed_prompt_tokens"] for pair in pairs]

    assert len(pairs) == 173
    assert all(pair["body_bytes"] >= pair["billed_prompt_tokens"] for pair in pairs)
    assert math.floor(min(ratios) * 100) / 100 == 3.62
    assert {pair["model"] for pair in pairs} == {
        GROK,
        HAIKU,
        DEEPSEEK,
        "qwen/qwen3.5-9b",
    }


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
    """The table is a ceiling: no committed receipt, for any model it prices,
    bills more than its prompt and completion tokens at the pinned rates, so
    the completion count carries every billed reasoning token."""
    tolerance = Decimal("0.00001")
    receipts = [
        receipt
        for receipt in _evidence_receipts()
        if receipt.get("model") in budget.PRICE_TABLE_USD_PER_MILLION
        and receipt.get("usage_cost_usd") is not None
        and receipt.get("token_usage")
    ]
    over = [
        receipt
        for receipt in receipts
        if Decimal(str(receipt["usage_cost_usd"]))
        > budget.priced_usd(
            receipt["model"],
            prompt_tokens=int(receipt["token_usage"].get("prompt_tokens") or 0),
            completion_tokens=int(receipt["token_usage"].get("completion_tokens") or 0),
        )
        + tolerance
    ]

    assert len(receipts) > 300
    assert over == []


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


def test_rail_refusal_reads_the_switch_inside_a_business_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.domain.chat_surface import turn_surface_scope

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    with turn_surface_scope("business"):
        with pytest.raises(RuntimeError, match="ARGUS_RESEARCH_RAIL_ENABLED must be off"):
            budget.refuse_unbounded_rails({})
