"""Web evidence stays separate from immutable backtest facts."""

from copy import deepcopy

import pytest
from argus.domain.research.contracts import ResearchSource
from argus.domain.result_readout_sources import accepted_breakdown_text


@pytest.fixture
def source_draft():
    return {
        "language": "en",
        "text": "Reported revenue grew 18%. Holding through the decline required patience.",
        "figures": [],
        "source_figures": [
            {
                "value": 18.0,
                "unit": "percent",
                "currency": None,
                "quote": "18%",
                "occurrence": 1,
                "citation_index": 0,
            }
        ],
        "citations": [
            {
                "quote": "Reported revenue grew 18%.",
                "occurrence": 1,
                "source_url": "https://example.com/earnings",
                "as_of": "2025-08-01",
            }
        ],
    }


def accept(draft, facts=None):
    return accepted_breakdown_text(
        draft,
        facts=facts or {},
        language=draft["language"],
        sources=(ResearchSource(url="https://example.com/earnings"),),
    )


@pytest.mark.parametrize(
    "language,text,claim",
    [
        ("en", "Reported revenue grew 18%.", "Reported revenue grew 18%."),
        (
            "es-419",
            "Los ingresos reportados crecieron 18%.",
            "Los ingresos reportados crecieron 18%.",
        ),
    ],
)
def test_cited_dated_web_figure_renders_without_mutating_run_facts(
    source_draft, language, text, claim
):
    source_draft.update(language=language, text=text)
    source_draft["citations"][0]["quote"] = claim
    facts = {"facts": {"portfolio.ending_value": {"value": 1000.0, "unit": "currency"}}}
    before = deepcopy(facts)
    rendered, failure = accept(source_draft, facts)
    assert failure is None
    assert text in rendered
    assert "](https://example.com/earnings)" in rendered
    assert "2025" in rendered
    assert facts == before


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda d: d.update(source_figures=[]), "unreferenced_figure"),
        (lambda d: d.update(citations=[]), "invalid_source_reference"),
        (
            lambda d: d["citations"][0].update(source_url="https://["),
            "invalid_source_reference",
        ),
        (
            lambda d: d["citations"][0].update(
                source_url="https://invented.example/news"
            ),
            "invalid_source_reference",
        ),
        (lambda d: d["citations"][0].update(as_of=""), "invalid_source_reference"),
        (
            lambda d: d["citations"][0].update(as_of="2025-02-31"),
            "invalid_source_reference",
        ),
        (
            lambda d: d["citations"][0].update(
                quote="Holding through the decline required patience."
            ),
            "invalid_source_reference",
        ),
        (lambda d: d["source_figures"][0].update(value=19.0), "invalid_figure_reference"),
        (
            lambda d: d["source_figures"][0].update(unit="currency"),
            "invalid_figure_reference",
        ),
        (
            lambda d: d["source_figures"][0].update(citation_index=4),
            "invalid_source_reference",
        ),
    ],
)
def test_bad_web_evidence_falls_back_as_a_whole(source_draft, mutation, expected):
    mutation(source_draft)
    assert accept(source_draft) == (None, expected)


def test_source_cannot_supply_a_missing_run_fact(source_draft):
    source_draft["figures"] = [
        {"fact_key": "invented_return", "value": 18.0, "quote": "18%", "occurrence": 1}
    ]
    source_draft["source_figures"] = []
    assert accept(source_draft) == (None, "invalid_figure_reference")


def test_source_and_run_cannot_cover_same_figure(source_draft):
    source_draft["figures"] = [
        {
            "fact_key": "portfolio.total_return",
            "value": 18.0,
            "quote": "18%",
            "occurrence": 1,
        }
    ]
    facts = {"facts": {"portfolio.total_return": {"value": 18.0, "unit": "percent"}}}
    assert accept(source_draft, facts) == (None, "invalid_figure_reference")


@pytest.mark.parametrize(
    "text,failure",
    [
        ("DOCN lagged SPY.", "contradicting_benchmark_claim"),
        ("The ending_value matters.", "internal_field_name"),
        ("ReadoutCitation supplies the context.", "internal_field_name"),
        ("ReadoutSourceFigure supplies the context.", "internal_field_name"),
        ("Read [here](https://invented.example/news).", "invalid_source_reference"),
    ],
)
def test_kept_checks_apply_to_web_enabled_breakdown(text, failure):
    draft = {
        "language": "en",
        "text": text,
        "figures": [],
        "source_figures": [],
        "citations": [],
    }
    facts = {
        "benchmark_comparison_claim": "beat_benchmark",
        "symbols": ["DOCN"],
        "benchmark_symbol": "SPY",
    }
    assert accept(draft, facts) == (None, failure)


def test_reported_language_mismatch_still_falls_back(source_draft):
    assert accepted_breakdown_text(
        source_draft, facts={}, language="es-419", sources=()
    ) == (None, "language_mismatch")
