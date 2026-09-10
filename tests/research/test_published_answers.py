"""A retrieved answer publishes: one owner at the composition seam.

PR #562 withheld a whole answer whenever one typed row cited a page the
response had not retrieved, or a typed answer wrote no row. Perplexity's
finance tool answers a price with its own page as the source, the model often
cites a different plausible page instead, and every such quote was paid for
and thrown away. These locks pin the reverse: a row keeps the citation the
model wrote, a figure written with no citation is named under the answer, the
answer itself is never withheld for a row, and the only withholding left is a
survey that did not retrieve or names nothing the resolver verifies.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from argus.agent_runtime import research_grounded as grounded

from tests.research.conftest import (
    PROVIDER_PAGE,
    PUBLISHER,
    agent_response,
    retrieved_row,
    rows_with_one_rejected,
    run_research_turn,
    search_results_item,
    set_research_query,
    typed_answer_text,
    typed_document,
    wire_grounded_client,
)

_wire = wire_grounded_client
_run = run_research_turn
_typed_document = typed_document
INVENTED = "https://invented.example/target"


def _unsourced_price_rows() -> list[dict]:
    """One row cited to the provider's finance data, one the model wrote
    with no citation at all."""
    return [
        retrieved_row(
            subject="Apple",
            symbol="AAPL",
            label="share price",
            value=200.0,
            kind="currency",
            unit="USD",
            source_url=PROVIDER_PAGE,
        ),
        retrieved_row(
            subject="Apple",
            symbol="AAPL",
            label="analyst target price",
            value=250.0,
            kind="currency",
            unit="USD",
            source_url=None,
        ),
    ]


def test_a_row_citing_a_page_outside_the_retrieval_record_publishes(monkeypatch) -> None:
    """The defect this lane exists for: the model cited a plausible page the
    response had not retrieved, the row was rejected for it, and the whole
    answer was withheld. The citation is the model's own and the answer
    publishes with it."""
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=["NVDA"]
    )
    prose = "NVIDIA fell **4.3%** and analysts now target **$250**."
    transport = _wire(
        monkeypatch, [_typed_document(rows_with_one_rejected(), answer=prose)]
    )

    result = _run("Why is NVDA moving this week?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert result.stage_patch["assistant_response"] == prose
    assert [row["source_url"] for row in sidecar["rows"]] == [PUBLISHER, INVENTED]
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]
    assert sidecar["anchor_symbols"] == ["NVDA"]
    assert result.stage_patch["next_experiments"]["rows"]

    served = _run("Why is NVDA moving this week?")
    assert served is not None
    assert len(transport.requests) == 1, "a published answer serves for its class TTL"
    assert served.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert served.stage_patch["research"]["rows"] == sidecar["rows"]


@pytest.mark.parametrize(
    ("language", "note"),
    [
        ("en", "I couldn't tie Apple analyst target price to a source."),
        ("es-419", "No pude vincular Apple analyst target price a una fuente."),
    ],
)
def test_a_figure_written_without_a_citation_is_named_under_the_answer(
    monkeypatch, language: str, note: str
) -> None:
    """The row the model left uncited stays in the answer and in the rows;
    the turn says, beneath the answer, that it could not tie that figure to
    a source, named from the row's own typed subject and label."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    prose = "AAPL is **$200** today and analysts target **$250**."
    _wire(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(prose, _unsourced_price_rows()),
                sources=[PROVIDER_PAGE],
            )
        ],
    )

    result = _run("What is Apple at?", language=language)

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert result.stage_patch["assistant_response"].startswith(prose)
    assert result.stage_patch["assistant_response"].endswith(note)
    assert [(row["label"], row["source_url"]) for row in sidecar["rows"]] == [
        ("share price", None),
        ("analyst target price", None),
    ]
    assert sidecar["anchor_symbols"] == ["AAPL"]


def test_the_thorough_path_composes_the_same_published_answer() -> None:
    """Both composition paths share the one seam and the one cache rule: a
    published packet serves for its class TTL, not the withheld day cap."""
    from argus.domain.research import cache as research_cache
    from argus.domain.research.cache import (
        WITHHELD_TTL_SECONDS,
        cache_get,
        research_cache_key,
    )
    from argus.domain.research.perplexity_agent import _packet_from_response

    prose = "Netflix grew **16%** and analysts target **$250**."
    document = agent_response(
        text=typed_answer_text(
            prose,
            [
                retrieved_row(
                    subject="Netflix",
                    symbol="NFLX",
                    label="revenue growth",
                    value=16.0,
                    source_url=INVENTED,
                ),
                retrieved_row(
                    subject="Netflix",
                    symbol="NFLX",
                    label="analyst target price",
                    value=250.0,
                    kind="currency",
                    unit="USD",
                    source_url=None,
                ),
            ],
        ),
        tickers=["NFLX"],
        sources=[PROVIDER_PAGE],
    )
    # A quarterly class: the day cap #568 gave withheld records must not
    # bound a published one, which serves for the class's ninety days.
    for item in document["output"]:
        if item.get("type") == "finance_results":
            item["categories"] = ["financials"]
            for result in item["results"]:
                result["category"] = "financials"
    packet = _packet_from_response(document, latency_ms=1, on_unpriced=lambda _: None)
    key = research_cache_key(
        capability_class="thorough_research",
        shape="thorough",
        symbols=("NFLX",),
        period_key="current",
        question_fingerprint="growth",
        language="es-419",
    )
    job_request = {
        "capability_class": "thorough_research",
        "language": "es-419",
        "question_kind": "company_lookup",
        "subjects": [{"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"}],
        "cache_key": key,
    }

    composed = grounded.compose_completed_research(job_request=job_request, packet=packet)
    grounded.store_research_packet_for_job(job_request, packet, composed)

    assert "degraded" not in composed["research"]
    assert composed["answer"].startswith(prose)
    assert (
        "No pude vincular Netflix analyst target price a una fuente."
        in composed["answer"]
    )
    assert [row["source_url"] for row in composed["research"]["rows"]] == [INVENTED, None]
    assert cache_get(key) is packet
    real_monotonic = time.monotonic
    monkeypatch_clock = lambda: real_monotonic() + WITHHELD_TTL_SECONDS + 1  # noqa: E731
    research_cache.time.monotonic = monkeypatch_clock
    try:
        assert cache_get(key) is packet, "a published answer outlives the withheld cap"
    finally:
        research_cache.time.monotonic = real_monotonic


@pytest.mark.parametrize(
    ("question_kind", "document", "figure"),
    [
        (
            "current_external",
            lambda: _typed_document(rows_with_one_rejected(), answer="Fell **4.3%**."),
            "4.3",
        ),
        (
            "live_quote",
            lambda: agent_response(text=typed_answer_text("AAPL is **$200** today.", [])),
            "200",
        ),
        (
            "live_quote",
            lambda: agent_response(
                text=typed_answer_text("AAPL is **$200** today.", []), invocations=0
            ),
            "200",
        ),
        (
            "live_quote",
            lambda: agent_response(
                text=typed_answer_text(
                    "AAPL is **$200** today.",
                    [
                        retrieved_row(
                            subject="Apple",
                            symbol="AAPL",
                            label="price",
                            value=200.0,
                            kind="currency",
                            unit="USD",
                        )
                    ],
                ),
                invocations=0,
            ),
            "200",
        ),
    ],
)
def test_no_answer_is_withheld_for_its_rows(
    monkeypatch, question_kind: str, document, figure: str
) -> None:
    """Every shape #562 withheld for a row, a missing row, or a missing
    retrieval record now publishes what the provider wrote. The strict
    schema is what keeps a figure from memory unrepresentable; composition
    does not second-guess it."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind=question_kind,
        symbols={"current_external": ["NVDA"], "live_quote": ["AAPL"]}[question_kind],
    )
    _wire(monkeypatch, [document()])

    result = _run("what about it")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert figure in result.stage_patch["assistant_response"]
    assert result.stage_patch["next_experiments"]["rows"]


def test_a_survey_that_never_retrieved_is_still_not_grounded(monkeypatch) -> None:
    """The one withholding that survives is the survey's own, from before
    #562: a model that did not look is evidence about the model, not the
    world, so nothing is stored and the next identical question is asked
    afresh."""
    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    document = agent_response(
        text=typed_answer_text(
            "NVDA (NVDA) rose **4.3%**.", [retrieved_row(label="change", value=4.3)]
        ),
        invocations=0,
    )
    transport = _wire(monkeypatch, [document] * 4)

    result = _run("anything interesting moving today")

    assert result is not None
    assert len(transport.requests) == 2, "the concrete retry still fires once"
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "survey_not_grounded"}
    assert result.stage_patch["assistant_response"] == (
        "I couldn't retrieve today's market movers."
    )
    assert sidecar["rows"] == [] and sidecar["sources"] == []

    _run("anything interesting moving today")
    assert len(transport.requests) == 4, "a survey that never retrieved is not stored"


def test_a_survey_naming_nothing_the_resolver_verifies_is_withheld_for_a_day(
    monkeypatch,
) -> None:
    """A survey with cited rows whose prose names no tradable ticker is
    withheld by composition; the record serves for the day cap, never the
    class's ninety days."""
    from argus.domain.research import cache as research_cache
    from argus.domain.research.cache import WITHHELD_TTL_SECONDS

    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    document = agent_response(
        text=typed_answer_text(
            "ZZZZFAKE led the gainers, up 9.1%.",
            [
                retrieved_row(
                    subject="ZZZZFAKE", symbol="ZZZZFAKE", label="change today", value=9.1
                )
            ],
        ),
        tickers=["ZZZZFAKE"],
        sources=[PROVIDER_PAGE],
    )
    for item in document["output"]:
        if item.get("type") == "finance_results":
            item["categories"] = ["financials"]
            for result in item["results"]:
                result["category"] = "financials"
    transport = _wire(monkeypatch, [document, document])

    result = _run("what is moving today")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "survey_synthesis_incomplete"}
    assert sidecar["rows"] == [] and sidecar["peers"] == []
    assert "next_experiments" not in result.stage_patch
    assert len(transport.requests) == 1

    served = _run("what is moving today")
    assert served is not None
    assert len(transport.requests) == 1, "the withheld record serves the same survey"
    assert served.stage_patch["research"]["usage"]["cache_status"] == "hit"

    real_monotonic = time.monotonic
    monkeypatch.setattr(
        research_cache.time,
        "monotonic",
        lambda: real_monotonic() + WITHHELD_TTL_SECONDS + 1,
    )
    _run("what is moving today")
    assert len(transport.requests) == 2, "the record outlives no day on any class"


def test_a_survey_that_names_a_verified_ticker_publishes_whatever_its_rows(
    monkeypatch,
) -> None:
    """#562 degraded a survey that retrieved and named a ticker but wrote no
    row. Stating no figure is the model's honesty, not a defect: after the
    one concrete retry the prose publishes with the name the resolver
    verified from the packet's own typed tickers."""
    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    today = datetime.now(timezone.utc).date().isoformat()
    figureless = agent_response(
        text=typed_answer_text(
            "NVIDIA (NVDA) led today's session, but I could not retrieve its figures.",
            [],
        ),
        tickers=["NVDA"],
        sources=[PROVIDER_PAGE],
        web_search_invocations=1,
    )
    figureless["output"].insert(
        1, search_results_item({"url": PUBLISHER, "title": "Movers", "date": today})
    )
    transport = _wire(monkeypatch, [figureless, figureless])

    result = _run("anything interesting moving today")

    assert result is not None
    assert len(transport.requests) == 2, "one concrete retry, never a loop"
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert sidecar["anchor_symbols"] == ["NVDA"]
    assert sidecar["rows"] == []
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]
    assert result.stage_patch["assistant_response"].startswith("NVIDIA (NVDA) led")
    assert result.stage_patch["next_experiments"]["rows"]


def test_a_survey_naming_a_ticker_the_packet_never_typed_stays_degraded(
    monkeypatch,
) -> None:
    """The survey rule that predates #562 and stays: a name only the prose
    carries is not one the resolver verified."""
    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    figureless = agent_response(
        text=typed_answer_text(
            "I could not retrieve current figures for NVIDIA (NVDA).", []
        ),
        invocations=0,
        web_search_invocations=1,
    )
    today = datetime.now(timezone.utc).date().isoformat()
    figureless["output"].insert(
        1, search_results_item({"url": PUBLISHER, "title": "Movers", "date": today})
    )
    _wire(monkeypatch, [figureless, figureless])

    result = _run("anything interesting moving today")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "survey_synthesis_incomplete"}
    assert sidecar["anchor_symbols"] == [] and sidecar["rows"] == []
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]


def test_the_sidecar_builder_owns_the_degraded_shape() -> None:
    sidecar = grounded.build_research_sidecar(
        capability_class="balanced_lookup",
        shape="balanced",
        sources=[],
        retrieved_at="2026-09-08T00:00:00+00:00",
        subjects=[],
        peers=[],
        usage={},
        period_of_interest=None,
        degraded_code="anything",
        retrieved_rows=[retrieved_row()],
    )
    assert sidecar["rows"] == []


def test_a_broken_typed_answer_never_reaches_the_reader(monkeypatch) -> None:
    """JSON-shaped text that is not the schema is a broken contract, not
    prose: the strict schema is the honesty line and stays. The turn says
    the lookup did not complete and asks the provider again next time."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    truncated = '{"answer_markdown": "AAPL is $200 today", "rows": [{"label": "AAPL", "va'
    transport = _wire(
        monkeypatch,
        [agent_response(text=truncated), agent_response(text=truncated)],
    )

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_unavailable_malformed_response"}
    answer = result.stage_patch["assistant_response"]
    assert answer.startswith("I couldn't complete the data lookup")
    assert "200" not in answer and "answer_markdown" not in answer
    assert sidecar["rows"] == [] and sidecar["sources"] == []

    _run("What is Apple at?")
    assert len(transport.requests) == 2, "a broken answer is never served from cache"


RECORDED_LOCAL_PROBE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/545/probes/domain_filtered_local_source.json"
)


def test_the_recorded_local_probe_publishes_what_it_found(monkeypatch) -> None:
    """The live recording #568 replayed: eleven pages on the bank's own site
    and no rate on any of them. The provider's answer says so in its own
    words, states no figure, and is what the reader gets, with the site it
    read as its sources; the record serves the next identical question."""
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=[]
    )
    recorded = json.loads(RECORDED_LOCAL_PROBE.read_text())["exchanges"][-1]["response"]
    transport = _wire(monkeypatch, [recorded])
    question = (
        "¿Qué tasa de interés paga hoy el Banco Popular Dominicano por un "
        "certificado financiero a un año en pesos?"
    )

    result = _run(question, language="es-419")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert sidecar["rows"] == []
    assert "%" not in result.stage_patch["assistant_response"]
    assert [source["domain"] for source in sidecar["sources"]] == ["popularenlinea.com"]

    served = _run(question, language="es-419")
    assert served is not None
    assert len(transport.requests) == 1
    assert served.stage_patch["research"]["usage"]["cache_status"] == "hit"
