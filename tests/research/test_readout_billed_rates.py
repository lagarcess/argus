"""Actual Luna invoices reconcile through the existing research billing owner."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from argus.domain.research.perplexity_agent import _usage_from_response

_EVIDENCE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/model-result-readouts/luna-billed-usage.json"
)
_OBSERVATIONS = json.loads(_EVIDENCE.read_text())["observations"]


@pytest.mark.parametrize("observation", _OBSERVATIONS, ids=lambda row: row["capture"])
def test_actual_luna_invoice_reconciles_without_unpriced_callback(observation):
    response = observation["response"]
    unpriced = []
    usage = _usage_from_response(response, latency_ms=0, on_unpriced=unpriced.append)

    assert usage.model == response["model"]
    assert usage.cost_usd == pytest.approx(response["usage"]["cost"]["total_cost"])
    assert usage.input_tokens == response["usage"]["input_tokens"]
    assert usage.output_tokens == response["usage"]["output_tokens"]
    assert unpriced == []


@pytest.mark.parametrize("observation", _OBSERVATIONS, ids=lambda row: row["capture"])
def test_luna_rate_mismatch_remains_unpriced(observation):
    response = deepcopy(observation["response"])
    response["usage"]["cost"]["output_cost"] *= 10
    unpriced = []
    usage = _usage_from_response(response, latency_ms=0, on_unpriced=unpriced.append)

    assert usage.cost_usd is None
    assert len(unpriced) == 1
    assert unpriced[0].reason == "rate_mismatch"
