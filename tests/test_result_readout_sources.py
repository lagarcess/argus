"""Provider sources accompany Breakdown without claim-level bookkeeping."""

from copy import deepcopy

import pytest
from argus.domain.result_readout_sources import accepted_breakdown_text


@pytest.fixture
def source_draft():
    return {
        "language": "en",
        "text": "Reported revenue grew 18%. Holding through the decline required patience.",
        "figures": [],
    }


@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "Reported revenue grew 18%."),
        ("es-419", "Los ingresos reportados crecieron 18%."),
    ],
)
def test_in_text_citations_remain_without_appending_a_source_list(
    source_draft, language, text
):
    text += " [Quarterly report](https://example.com/earnings)"
    source_draft.update(language=language, text=text)
    facts = {"facts": {"portfolio.ending_value": {"value": 1000.0, "unit": "currency"}}}
    before = deepcopy(facts)
    rendered, failure = accepted_breakdown_text(
        source_draft, facts=facts, language=language
    )
    assert failure is None
    assert rendered == text
    assert facts == before


def test_no_returned_sources_preserves_complete_text(source_draft):
    assert accepted_breakdown_text(source_draft, facts={}, language="en") == (
        source_draft["text"],
        None,
    )


def test_external_figure_does_not_require_quote_occurrence_or_date(source_draft):
    rendered, failure = accepted_breakdown_text(
        source_draft,
        facts={},
        language="en",
    )
    assert failure is None
    assert source_draft["text"] in rendered
    assert rendered == source_draft["text"]


@pytest.mark.parametrize(
    "reference",
    [
        {"fact_key": "invented_return", "value": 18.0},
        {"fact_key": "portfolio.total_return", "value": 18.0},
    ],
)
def test_source_cannot_override_invalid_run_reference(source_draft, reference):
    source_draft["figures"] = [reference]
    facts = {"facts": {"portfolio.total_return": {"value": 9.0, "unit": "percent"}}}
    assert accepted_breakdown_text(
        source_draft,
        facts=facts,
        language="en",
    ) == (None, "invalid_figure_reference")


def test_run_reference_and_web_figures_keep_separate_owners(source_draft):
    source_draft["text"] = "The run returned 9%. " + source_draft["text"]
    source_draft["figures"] = [{"fact_key": "portfolio.total_return", "value": 9.0}]
    facts = {"facts": {"portfolio.total_return": {"value": 9.0, "unit": "percent"}}}
    rendered, failure = accepted_breakdown_text(
        source_draft,
        facts=facts,
        language="en",
    )
    assert failure is None
    assert rendered.startswith(source_draft["text"])


def test_reported_language_mismatch_still_falls_back(source_draft):
    assert accepted_breakdown_text(source_draft, facts={}, language="es-419") == (
        None,
        "language_mismatch",
    )
