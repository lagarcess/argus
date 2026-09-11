"""Regressions from the founder's actual DOCN app demo."""

import json

import pytest
from argus.api.chat.breakdown import _result_breakdown_llm_messages
from argus.domain.result_readout_grounding import accepted_readout_text


def test_repeated_number_does_not_require_occurrence_bookkeeping():
    text = "There were 13 executed fills, not 13 completed round trips."
    facts = {"facts": {"Executed fills": {"value": 13, "unit": "count"}}}
    assert accepted_readout_text(
        {
            "language": "en",
            "text": text,
            "figures": [{"fact_key": "Executed fills", "value": 13}],
        },
        facts=facts,
        language="en",
    ) == (text, None)


@pytest.mark.parametrize("value,accepted", [(42.1, True), (42.2, False)])
def test_referenced_number_must_match_with_display_rounding(value, accepted):
    text = f"The drop was {value}%."
    result = accepted_readout_text(
        {
            "language": "en",
            "text": text,
            "figures": [{"fact_key": "Worst drop", "value": value}],
        },
        facts={"facts": {"Worst drop": {"value": 42.096, "unit": "percent"}}},
        language="en",
    )
    assert result == ((text, None) if accepted else (None, "invalid_figure_reference"))


def test_breakdown_request_is_plain_and_does_not_transport_series():
    facts = {
        "symbols": ["DOCN"],
        "benchmark_symbol": "SPY",
        "facts": {
            "portfolio.total_return": {
                "value": 15.126,
                "unit": "percent",
                "basis": "return_on_fixed_capital",
            },
            "window.start": {"value": "2023-09-01", "unit": "date"},
            "window.end": {"value": "2026-09-09", "unit": "date"},
        },
        "series": {"portfolio_equity": {"points": [{"value": n} for n in range(1000)]}},
    }
    messages = _result_breakdown_llm_messages(facts=facts, language="en")
    request = "\n".join(message["content"] for message in messages)
    assert len(request) < 2500
    assert "search" in request.lower()
    assert "sources" in request.lower()
    assert "DOCN" in request and "SPY" in request
    assert "2023-09-01" in request and "15.126" in request
    assert "portfolio.total_return" not in request
    assert "portfolio_equity" not in request
    assert "points" not in json.dumps(messages)


def test_returned_source_titles_obey_readout_punctuation_without_changing_url():
    from argus.domain.research.contracts import ResearchSource
    from argus.domain.result_readout_sources import accepted_breakdown_text

    text, failure = accepted_breakdown_text(
        {"language": "en", "text": "An uneven ride.", "figures": []},
        facts={},
        language="en",
        sources=(
            ResearchSource(title="Company — results", url="https://example.com/results"),
        ),
    )
    assert failure is None
    assert "—" not in text
    assert "Company, results" in text
    assert "https://example.com/results" in text


def test_breakdown_schema_offers_the_actual_headline_labels():
    from argus.domain.result_readout_sources import result_breakdown_schema
    from pydantic import ValidationError

    facts = {
        "facts": {
            "Executed fills": {"value": 13, "unit": "count"},
            "Contribution schedule": {"value": "monthly", "unit": "text"},
            "Completed round trips": {"value": None, "unit": "count"},
        }
    }
    schema = result_breakdown_schema(facts)
    draft = {
        "language": "en",
        "text": "There were 13 fills.",
        "figures": [{"fact_key": "Executed fills", "value": 13}],
    }
    assert schema.model_validate(draft).figures[0].fact_key == "Executed fills"
    draft["figures"][0]["fact_key"] = "executed_fills"
    with pytest.raises(ValidationError):
        schema.model_validate(draft)
    draft["figures"][0] = {"fact_key": "Contribution schedule", "value": "monthly"}
    with pytest.raises(ValidationError):
        schema.model_validate(draft)
