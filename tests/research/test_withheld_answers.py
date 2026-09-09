"""A withheld answer: one owner at the composition seam.

Codex rounds 1 to 3 on PR #562 found the same defect at successive layers: a
packet was judged publishable in several places by several rules, so the
prose, the survey acceptance, the sidecar and the note could each disagree
with the row rejection. These locks pin the one rule: a typed answer is
publishable only with at least one cited row and no rejected one, a
never-retrieved answer is not grounded whatever it wrote, and a degraded
turn states no figure, carries no row, and offers no peer.
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
_rows_with_one_rejected = rows_with_one_rejected


def test_a_rejected_row_withholds_the_whole_answer(monkeypatch) -> None:
    """The prose states the figure the row was dropped for, and prose cannot
    be trimmed of one claim, so nothing of it is published."""
    set_research_query(
        monkeypatch, globals(), question_kind="current_external", symbols=["NVDA"]
    )
    prose = "NVIDIA fell **4.3%** and analysts now target **$250**."
    transport = _wire(
        monkeypatch,
        [
            _typed_document(_rows_with_one_rejected(), answer=prose),
            _typed_document(_rows_with_one_rejected(), answer=prose),
        ],
    )

    result = _run("Why is NVDA moving this week?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_figures_unverified"}
    answer = result.stage_patch["assistant_response"]
    assert "250" not in answer and "4.3" not in answer
    assert answer.startswith(
        "I found sources, but couldn't verify NVIDIA analyst target price against them"
    )
    assert sidecar["rows"] == []
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]
    # The subject the user named stays testable; nothing else is offered.
    assert sidecar["anchor_symbols"] == ["NVDA"]
    assert sidecar["peers"] == []

    served = _run("Why is NVDA moving this week?")
    assert len(transport.requests) == 1, "the withheld record serves the same question"
    assert served is not None
    again = served.stage_patch["research"]
    assert again["usage"]["cache_status"] == "hit"
    assert again["degraded"] == sidecar["degraded"]
    assert again["sources"] == sidecar["sources"]
    assert served.stage_patch["assistant_response"] == answer


def test_a_rejected_row_withholds_the_thorough_answer_too(monkeypatch) -> None:
    """Both composition paths share the one judgment, and the one cache rule:
    the withheld record is stored for its class TTL capped at a day."""
    from argus.domain.research import cache as research_cache
    from argus.domain.research.cache import (
        WITHHELD_TTL_SECONDS,
        cache_get,
        research_cache_key,
    )
    from argus.domain.research.perplexity_agent import _packet_from_response

    packet = _packet_from_response(
        _typed_document(
            _rows_with_one_rejected(),
            answer="NVIDIA fell **4.3%** and analysts now target **$250**.",
        ),
        latency_ms=1,
        on_unpriced=lambda _: None,
    )
    assert [row.label for row in packet.rejected_rows] == ["analyst target price"]
    key = research_cache_key(
        capability_class="thorough_research",
        shape="thorough",
        symbols=("NVDA",),
        period_key="current",
        question_fingerprint="why",
        language="es-419",
    )
    job_request = {
        "capability_class": "thorough_research",
        "language": "es-419",
        # A quarterly class: the day cap is what bounds this record, not
        # the class's ninety days.
        "question_kind": "company_lookup",
        "subjects": [{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
        "requires_publisher_sources": True,
        "cache_key": key,
    }

    composed = grounded.compose_completed_research(job_request=job_request, packet=packet)
    grounded.store_research_packet_for_job(job_request, packet)

    assert composed["research"]["degraded"] == {"code": "research_figures_unverified"}
    assert composed["research"]["rows"] == []
    assert "250" not in composed["answer"] and "4.3" not in composed["answer"]
    assert composed["answer"].startswith(
        "Encontré fuentes, pero no pude verificar con ellas NVIDIA analyst target price"
    )
    assert [source["url"] for source in composed["research"]["sources"]] == [PUBLISHER]
    assert cache_get(key) is packet, "the withheld record is stored for the job"
    real_monotonic = time.monotonic
    monkeypatch.setattr(
        research_cache.time,
        "monotonic",
        lambda: real_monotonic() + WITHHELD_TTL_SECONDS + 1,
    )
    assert cache_get(key) is None, "an absence outlives no day, whatever its class"


def test_a_survey_that_names_a_ticker_but_states_no_figure_is_degraded(
    monkeypatch,
) -> None:
    """Retrieval plus a resolvable name in the prose is not a grounded survey;
    a figure is. Accepted only with both, after the one concrete retry."""
    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    figureless = agent_response(
        text=typed_answer_text(
            "I could not retrieve current figures for NVIDIA (NVDA).", []
        ),
        invocations=0,
        web_search_invocations=1,
    )
    # A movers page is dated the day it is asked about; the survey's
    # freshness bound is the question date, so a fixed date would be a
    # fiction that fails selection the next day.
    today = datetime.now(timezone.utc).date().isoformat()
    figureless["output"].insert(
        1,
        search_results_item({"url": PUBLISHER, "title": "Movers", "date": today}),
    )
    transport = _wire(monkeypatch, [figureless, figureless])

    result = _run("anything interesting moving today")

    assert result is not None
    assert len(transport.requests) == 2
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "survey_synthesis_incomplete"}
    assert sidecar["anchor_symbols"] == []
    assert sidecar["peers"] == []
    assert "next_experiments" not in result.stage_patch
    assert "NVDA" not in result.stage_patch["assistant_response"]
    # The pages it read are where Argus looked, and the record serves again.
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]
    served = _run("anything interesting moving today")
    assert served is not None
    assert len(transport.requests) == 2, "a survey that retrieved is not asked twice"
    assert served.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert served.stage_patch["research"]["sources"] == sidecar["sources"]


def test_a_survey_with_figures_but_no_verified_name_persists_no_rows(
    monkeypatch,
) -> None:
    """A degraded sidecar carries no rows, whatever the packet parsed."""
    set_research_query(monkeypatch, globals(), question_kind="market_pulse", symbols=[])
    _wire(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "ZZZZFAKE led the gainers, up 9.1%.",
                    [
                        retrieved_row(
                            subject="ZZZZFAKE",
                            symbol="ZZZZFAKE",
                            label="change today",
                            value=9.1,
                        )
                    ],
                ),
                tickers=["ZZZZFAKE"],
                sources=[PROVIDER_PAGE],
            )
        ],
    )

    result = _run("what is moving today")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "survey_synthesis_incomplete"}
    assert sidecar["rows"] == []


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


@pytest.mark.parametrize(
    ("question_kind", "documents"),
    [
        (
            "current_external",
            lambda: [
                _typed_document(_rows_with_one_rejected(), answer="Fell **4.3%**."),
                _typed_document(_rows_with_one_rejected(), answer="Fell **4.3%**."),
            ],
        ),
        (
            "market_pulse",
            lambda: [
                agent_response(
                    text=typed_answer_text("NVDA (NVDA) fell **4.3%**.", []),
                    sources=[PROVIDER_PAGE],
                ),
                agent_response(
                    text=typed_answer_text("NVDA (NVDA) fell **4.3%**.", []),
                    sources=[PROVIDER_PAGE],
                ),
            ],
        ),
        (
            "market_pulse",
            lambda: [
                agent_response(
                    text=typed_answer_text(
                        "ZZZZFAKE fell **4.3%**.",
                        [
                            retrieved_row(
                                subject="ZZZZFAKE",
                                symbol="ZZZZFAKE",
                                label="change",
                                value=-4.3,
                            )
                        ],
                    ),
                    tickers=["ZZZZFAKE"],
                    sources=[PROVIDER_PAGE],
                ),
            ],
        ),
        (
            "live_quote",
            lambda: [
                agent_response(text=typed_answer_text("AAPL is **$4.3** today.", []))
            ],
        ),
        (
            "live_quote",
            lambda: [
                agent_response(
                    text=typed_answer_text("AAPL is **$4.3** today.", []), invocations=0
                )
            ],
        ),
        (
            "live_quote",
            lambda: [
                agent_response(
                    text=typed_answer_text(
                        "AAPL is **$4.3** today.",
                        [
                            retrieved_row(
                                subject="Apple",
                                symbol="AAPL",
                                label="price",
                                value=4.3,
                                kind="currency",
                                unit="USD",
                            )
                        ],
                    ),
                    invocations=0,
                )
            ],
        ),
        (
            "market_pulse",
            lambda: [
                agent_response(
                    text=typed_answer_text(
                        "NVDA (NVDA) rose **4.3%**.",
                        [retrieved_row(label="change", value=4.3)],
                    ),
                    invocations=0,
                ),
                agent_response(
                    text=typed_answer_text(
                        "NVDA (NVDA) rose **4.3%**.",
                        [retrieved_row(label="change", value=4.3)],
                    ),
                    invocations=0,
                ),
            ],
        ),
    ],
)
def test_no_degraded_turn_asserts_a_figure_or_carries_a_row(
    monkeypatch, question_kind: str, documents
) -> None:
    """The invariant behind all three review findings: whatever withheld the
    answer, the turn states no figure from the packet, carries no row, and
    offers no peer."""
    set_research_query(
        monkeypatch,
        globals(),
        question_kind=question_kind,
        symbols={"current_external": ["NVDA"], "live_quote": ["AAPL"]}.get(
            question_kind, []
        ),
    )
    _wire(monkeypatch, documents())

    result = _run("what about it")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" in sidecar
    assert sidecar["rows"] == []
    assert sidecar["peers"] == []
    assert "4.3" not in result.stage_patch["assistant_response"]


def test_a_rowless_typed_quote_is_withheld(monkeypatch) -> None:
    """Round 2: the model's word that its prose states no figure is never
    trusted. A typed quote that retrieved and wrote no row is withheld on
    every shape, not only on surveys; the record serves the same question
    for the quote class's two minutes, the bound that keeps a model fault on
    a volatile class from outliving a retry."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    rowless = agent_response(text=typed_answer_text("AAPL is **$200** today.", []))
    transport = _wire(monkeypatch, [rowless, rowless])

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_figures_unverified"}
    answer = result.stage_patch["assistant_response"]
    assert "200" not in answer
    assert answer.startswith("I found sources, but couldn't verify the figures")
    assert sidecar["rows"] == []
    assert sidecar["anchor_symbols"] == ["AAPL"], "the named subject stays testable"
    assert result.stage_patch["next_experiments"]["rows"]

    served = _run("What is Apple at?")
    assert len(transport.requests) == 1, "the withheld record serves the same question"
    assert served is not None
    assert served.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert served.stage_patch["research"]["degraded"] == sidecar["degraded"]


def test_a_rowless_typed_answer_without_retrieval_is_not_grounded(monkeypatch) -> None:
    """A model that did not look is evidence about the model, not the world:
    nothing is stored, and the next identical question is asked afresh."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    unretrieved = agent_response(
        text=typed_answer_text("AAPL is **$200** today.", []), invocations=0
    )
    transport = _wire(monkeypatch, [unretrieved, unretrieved])

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_not_grounded"}
    answer = result.stage_patch["assistant_response"]
    assert "200" not in answer
    assert answer.startswith("I couldn't complete the data lookup")
    assert sidecar["rows"] == [] and sidecar["sources"] == []

    _run("What is Apple at?")
    assert len(transport.requests) == 2, "an unretrieved answer is never served again"


def test_the_thorough_job_withholds_a_rowless_typed_answer_too() -> None:
    from argus.domain.research.perplexity_agent import _packet_from_response

    packet = _packet_from_response(
        agent_response(text=typed_answer_text("Netflix grew **16%**.", [])),
        latency_ms=1,
        on_unpriced=lambda _: None,
    )
    composed = grounded.compose_completed_research(
        job_request={
            "capability_class": "thorough_research",
            "language": "en",
            "question_kind": "cross_company",
            "subjects": [{"symbol": "NFLX", "name": "Netflix", "asset_class": "equity"}],
            "cache_key": "k",
        },
        packet=packet,
    )
    assert composed["research"]["degraded"] == {"code": "research_figures_unverified"}
    assert "16" not in composed["answer"]
    assert composed["research"]["rows"] == []


def test_rows_without_any_retrieval_are_not_grounded_not_unverified(monkeypatch) -> None:
    """Round 3: a typed answer that never retrieved has every row rejected by
    construction. Absence of retrieval is the stronger fact, so the turn says
    the lookup did not complete rather than that sources were found."""
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    _wire(
        monkeypatch,
        [
            agent_response(
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
            )
        ],
    )

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_not_grounded"}
    answer = result.stage_patch["assistant_response"]
    assert answer.startswith("I couldn't complete the data lookup")
    assert "found sources" not in answer and "200" not in answer
    assert sidecar["sources"] == [] and sidecar["rows"] == []


def test_a_survey_with_rows_but_no_retrieval_keeps_its_own_code(monkeypatch) -> None:
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
    assert sidecar["sources"] == []

    _run("anything interesting moving today")
    assert len(transport.requests) == 4, "a survey that never retrieved is not stored"


def test_a_broken_typed_answer_never_reaches_the_reader(monkeypatch) -> None:
    """Round 4: JSON-shaped text that is not the schema is a broken contract,
    not prose. The turn says the lookup did not complete, publishes nothing
    of the text, and asks the provider again next time."""
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


def test_prose_whose_every_figure_is_a_row_is_published(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    _wire(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text(
                    "AAPL is **$200** today, up **5%** this week, as of September 8, 2026.",
                    [
                        retrieved_row(
                            subject="Apple",
                            symbol="AAPL",
                            label="price",
                            value=200.0,
                            kind="currency",
                            unit="USD",
                            source_url="https://www.perplexity.ai/finance/AAPL",
                        ),
                        retrieved_row(
                            subject="Apple",
                            symbol="AAPL",
                            label="weekly change",
                            value=5.0,
                            source_url="https://www.perplexity.ai/finance/AAPL",
                        ),
                    ],
                ),
                sources=["https://www.perplexity.ai/finance/AAPL"],
            )
        ],
    )

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert "degraded" not in sidecar
    assert len(sidecar["rows"]) == 2
    assert "200" in result.stage_patch["assistant_response"]


RECORDED_LOCAL_PROBE = (
    Path(__file__).resolve().parents[2]
    / "docs/reports/evidence/545/probes/domain_filtered_local_source.json"
)


def test_the_recorded_local_probe_hands_back_where_argus_looked(monkeypatch) -> None:
    """The live recording behind this lane: eleven pages on the bank's own
    site, no rate on any of them. The turn withholds the figure, keeps the
    site it read as where Argus looked, selected as for any answer (one page
    per publisher, so the bank's first page), and the record serves the next
    identical question instead of paying for it again."""
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
    assert sidecar["degraded"] == {"code": "research_figures_unverified"}
    assert result.stage_patch["assistant_response"].startswith(
        "Encontré fuentes, pero no pude verificar con ellas las cifras"
    )
    assert sidecar["rows"] == []
    assert [source["domain"] for source in sidecar["sources"]] == ["popularenlinea.com"]
    assert sidecar["sources"][0]["title"].startswith("Préstamo Emprendimiento Popular")
    assert sidecar["sources"][0]["url"].startswith("https://popularenlinea.com/")

    served = _run(question, language="es-419")
    assert served is not None
    assert len(transport.requests) == 1, "the unpublished fact is retrieved once"
    assert served.stage_patch["research"]["usage"]["cache_status"] == "hit"
    assert served.stage_patch["research"]["sources"] == sidecar["sources"]
