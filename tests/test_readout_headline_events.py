"""Recorded evidence supplies arithmetic and chronology before composition."""

from copy import deepcopy

import pytest
from argus.api.chat.breakdown import _result_breakdown_llm_messages
from argus.domain.result_readout_headlines import (
    headline_readout_facts,
    headline_request_lines,
)

from tests.test_result_readout_fact_sheet import CASES, projection, sheet


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_headlines_supply_unrounded_drawdown_difference_at_card_precision(language):
    raw = projection(CASES["docn_buyhold_recorded"])
    raw["chart"]["series"] = [
        {"time": "2025-02-18", "value": 1038.57},
        {"time": "2025-08-01", "value": 988.47},
        {"time": "2026-06-15", "value": 1100.25},
    ]
    raw["chart"]["value_summary"]["peak_value"] = 1100.25
    raw["metrics"]["aggregate"]["performance"]["portfolio_value_range"]["peak_value"] = (
        1100.25
    )
    raw["metrics"]["aggregate"]["performance"]["benchmark_coverage"]["target_points"] = 3
    raw["metrics"]["aggregate"]["risk"]["max_drawdown_pct"] = (988.47 / 1038.57 - 1) * 100
    facts = sheet(raw)
    loss = facts["facts"]["portfolio.drawdown.dollar_loss"]
    assert loss["value"] == pytest.approx(50.10)
    headlines = headline_readout_facts(facts)
    assert any(row is loss for row in headlines["facts"].values())
    request = _result_breakdown_llm_messages(facts=facts, language=language)[1]["content"]
    assert "$50" in request and "$51" not in request
    assert "$1,039" in request and "$988" in request
    assert "50.10" not in request


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_recorded_peak_date_and_drawdown_events_enter_request_in_time_order(language):
    facts = sheet(projection(CASES["docn_buyhold_recorded"]))
    before = deepcopy(facts)
    points = facts["series"]["portfolio_equity"]["points"]
    peak = max(points, key=lambda point: point["value"])
    assert facts["facts"]["portfolio.peak_date"]["value"] == peak["time"]
    request = _result_breakdown_llm_messages(facts=facts, language=language)[1]["content"]
    assert request.index("Worst drop began") < request.index("Worst drop ended")
    assert request.index("Worst drop ended") < request.index(
        "Highest portfolio value reached"
    )
    assert "chronological" in request.lower()
    assert "series" not in request and "markers" not in request
    assert len(request) < 2500
    assert facts == before


@pytest.mark.parametrize("defect", ["no_series", "peak_missing", "unordered"])
def test_peak_date_is_unavailable_without_matching_ordered_evidence(defect):
    raw = projection(CASES["docn_buyhold_recorded"])
    if defect == "no_series":
        raw["chart"].pop("series")
    elif defect == "peak_missing":
        points = raw["chart"]["series"]
        points.remove(max(points, key=lambda point: point["value"]))
    else:
        raw["chart"]["series"].reverse()
    facts = sheet(raw)
    assert facts["facts"]["portfolio.peak_date"]["value"] is None


def test_intraday_events_sort_by_instant_including_mixed_timezone_offsets():
    facts = sheet(projection(CASES["docn_buyhold_recorded"]))
    dates = {
        "portfolio.peak_date": "2025-02-18T09:30:00-05:00",
        "portfolio.drawdown.peak_date": "2025-02-18T15:00:00Z",
        "portfolio.drawdown.trough_date": "2025-02-18T16:00:00",
    }
    for key, value in dates.items():
        facts["facts"][key]["value"] = value
    request = "\n".join(headline_request_lines(headline_readout_facts(facts)))
    assert (
        request.index("Highest portfolio value reached")
        < request.index("Worst drop began")
        < request.index("Worst drop ended")
    )
