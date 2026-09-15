"""A cancelled response keeps its budget reservation without ending measurement."""

import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest

from tests.evals.measurement_budget import MeasurementBudget, MeasurementBudgetStop
from tests.evals.measurement_budget_runner import run_budgeted_cases
from tests.evals.measurement_eval_harness import load_eval_cases


@dataclass
class Provenance:
    candidate_sha: str = "offline"


def test_cancelled_response_continues_and_retained_reservation_stops_admission(
    tmp_path, monkeypatch
):
    budget = MeasurementBudget(
        tmp_path / "costs.jsonl", {c.id for c in load_eval_cases()}
    )
    budget.install(monkeypatch)
    budget._settled["openrouter"] = Decimal("14.75")
    cases = [
        SimpleNamespace(id=cid, category="test") for cid in sorted(budget.case_ids)[:3]
    ]
    received = []

    class CutOff(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"choices":'
            await asyncio.Event().wait()

    async def call():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: received.append(req) or httpx.Response(200, stream=CutOff())
            )
        ) as client:
            await asyncio.wait_for(
                client.post("https://openrouter.ai/api/v1/chat/completions"), 0.01
            )

    def run(case):
        try:
            asyncio.run(call())
        except asyncio.TimeoutError:
            return {
                "id": case.id,
                "status": "failed",
                "failed_checks": ["runtime_timeout"],
            }
        pytest.fail("Expected response deadline")

    progress = tmp_path / "progress.json"
    with pytest.raises(MeasurementBudgetStop, match="total_admission_budget"):
        run_budgeted_cases(
            cases,
            run_case=run,
            budget=budget,
            provenance=Provenance(),
            progress_path=progress,
        )
    result = json.loads(progress.read_text())
    assert [r["status"] for r in result["results"]] == ["failed", "failed"]
    assert len(received) == 2
    assert budget.snapshot()["reserved_usd"]["openrouter"] == "0.20"
    assert budget.snapshot()["committed_usd"] == "14.95"
    budget.close()


def test_prior_ledger_is_counted_without_reusing_it(tmp_path):
    prior = tmp_path / "prior.jsonl"
    prior.write_text(
        "\n".join(
            json.dumps(e)
            for e in [
                {
                    "event": "send",
                    "send_id": 1,
                    "case_id": "old",
                    "provider": "openrouter",
                    "reservation_usd": "0.10",
                },
                {
                    "event": "invoice",
                    "send_id": 1,
                    "case_id": "old",
                    "provider": "openrouter",
                    "cost_usd": "0.093172736",
                },
                {
                    "event": "send",
                    "send_id": 2,
                    "case_id": "old",
                    "provider": "openrouter",
                    "reservation_usd": "0.10",
                },
            ]
        )
        + "\n"
    )
    before = prior.read_bytes()
    budget = MeasurementBudget(
        tmp_path / "new.jsonl", {c.id for c in load_eval_cases()}, prior_ledger=prior
    )
    assert budget.snapshot()["committed_usd"] == "0.193172736"
    assert budget.snapshot()["reserved_usd"]["openrouter"] == "0.10"
    assert prior.read_bytes() == before
    budget.assert_complete()
    budget.close()


@pytest.mark.parametrize(
    "error,status,code",
    [
        (TimeoutError, "failed", "runtime_timeout"),
        (asyncio.TimeoutError, "failed", "runtime_timeout"),
        (httpx.ConnectError, "infrastructure_error", "ConnectError"),
    ],
)
def test_escaped_call_failure_is_scored_and_next_case_runs(tmp_path, error, status, code):
    cases = [SimpleNamespace(id=c.id, category=c.category) for c in load_eval_cases()[:2]]
    budget = MeasurementBudget(
        tmp_path / "ledger.jsonl", {c.id for c in load_eval_cases()}
    )

    def run(case):
        if case == cases[0]:
            sid = budget.admit("openrouter")
            budget.uncertain(sid)
            raise error("sensitive details")
        return {"id": case.id, "status": "passed"}

    progress = tmp_path / "progress.json"
    results = run_budgeted_cases(
        cases,
        run_case=run,
        budget=budget,
        provenance=Provenance(),
        progress_path=progress,
    )
    assert [r["status"] for r in results] == [status, "passed"]
    if status == "failed":
        assert results[0]["failed_checks"] == [code]
    else:
        assert results[0]["infrastructure_errors"][0]["code"] == code
    assert "sensitive details" not in progress.read_text()
    assert results[0]["failure_trace"][-1]["function"] == "run"
    assert json.loads(progress.read_text())["status"] == "completed"
    assert budget.snapshot()["reserved_usd"]["openrouter"] == "0.10"
    budget.close()


def test_late_invoice_replaces_reservation_once(tmp_path):
    budget = MeasurementBudget(
        tmp_path / "ledger.jsonl", {c.id for c in load_eval_cases()}
    )
    with budget.case(next(iter(budget.case_ids))):
        sid = budget.admit("openrouter")
        budget.uncertain(sid)
        budget.uncertain(sid)
    assert budget.snapshot()["committed_usd"] == "0.10"
    budget.settle(sid, ".04")
    assert budget.snapshot()["committed_usd"] == "0.04"
    assert budget.snapshot()["reserved_usd"]["openrouter"] == "0"
    budget.close()


def test_unknown_agent_bills_keep_counting_toward_eight_dollars(tmp_path):
    budget = MeasurementBudget(
        tmp_path / "ledger.jsonl", {c.id for c in load_eval_cases()}
    )
    cases = sorted(budget.agent_cases)
    for case in cases[:5]:
        with budget.case(case):
            budget.uncertain(budget.admit("agent"))
    assert budget.snapshot()["reserved_usd"]["agent"] == "7.50"
    with pytest.raises(MeasurementBudgetStop, match="provider_admission_budget"):
        with budget.case(cases[5]):
            budget.admit("agent")
    assert sum(row["count"] for row in budget.snapshot()["sends"]) == 5
    budget.close()
