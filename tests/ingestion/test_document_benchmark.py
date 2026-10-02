from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from argus.domain.ingestion.contract import ImportCandidate, SourceRef

from scripts.documents.benchmark import (
    receipt_cost,
    row_score,
    run_live,
)
from scripts.documents.budget import BenchmarkBudget, PriceEnvelope


def candidate(amount="10", direction="outflow", evidence="transaction"):
    return ImportCandidate(
        source=SourceRef(
            source="statement",
            connection_id="benchmark",
            external_id="row",
            observed_at=datetime.now(timezone.utc),
        ),
        amount=amount,
        currency="DOP",
        direction=direction,
        evidence=evidence,
        balance_scope="current" if evidence == "balance" else None,
    )


def test_multiset_scoring_detects_duplicates_wrong_direction_and_balance_leak():
    sample = dict(
        expected_rows=[dict(amount="10.00", currency="DOP", date=None, kind="expense")]
        * 2,
        excluded_balances=dict(opening="100", currency="DOP"),
    )
    score = row_score(
        sample,
        (
            candidate(),
            candidate(direction="inflow"),
            candidate(amount="100"),
            candidate(amount="100", evidence="balance"),
        ),
    )
    assert score["exact_matches"] == 1
    assert score["missing_or_mismatched"] == 1
    assert score["invented_or_mismatched"] == 2
    assert score["field_multiset_matches"]["amount"] == 2
    assert score["field_multiset_matches"]["direction"] == 2
    assert score["balances_as_transactions"] == 1
    assert score["balance_candidates"] == 1


@pytest.mark.parametrize(
    "receipts",
    [
        [],
        [{}],
        [dict(usage_cost_usd=None)],
        [dict(usage_cost_usd="NaN")],
        [dict(usage_cost_usd=0.1)] * 2,
    ],
)
def test_unknown_cost_or_multiple_dispatches_is_not_zero_cost(receipts):
    with pytest.raises(ValueError):
        receipt_cost(dict(route_receipts=receipts))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cost,expected_calls,reason",
    [
        (None, 1, "unknown_cost_or_multiple_attempts"),
        (1, 1, "request_price_bound_exceeded"),
        (0.1, 2, None),
    ],
)
async def test_serial_benchmark_stops_without_retry(
    tmp_path, cost, expected_calls, reason
):
    (tmp_path / "test.png").write_bytes(b"fixture")
    sample = dict(
        id="one",
        file="test.png",
        sha256="hash",
        expected_rows=[],
        expected_status="review_required",
    )
    calls = []

    class Extractor:
        async def extract(self, *args):
            calls.append(args)
            return SimpleNamespace(
                candidates=(), metadata=dict(route_receipts=[dict(usage_cost_usd=cost)])
            )

    budget = BenchmarkBudget(
        PriceEnvelope("fixture", "provider", 1, 1, Decimal("0.1"), Decimal("0.1")),
        Decimal("1"),
        2,
    )

    report = dict(results=[])
    saves = []
    await run_live(
        [sample, sample | {"id": "two"}],
        tmp_path,
        Extractor(),
        budget,
        report,
        lambda value: saves.append(dict(value)),
    )
    assert len(calls) == expected_calls
    assert report.get("stop_reason") == reason
    assert report["complete"] == (reason is None)
    assert saves
    if cost is None:
        assert report["actual_cost_usd"] is None
        assert report["known_cost_usd"] == "0"
