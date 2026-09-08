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
    assert answer.startswith("I found sources, but couldn't verify the figures")
    assert sidecar["rows"] == []
    assert [source["url"] for source in sidecar["sources"]] == [PUBLISHER]
    # The subject the user named stays testable; nothing else is offered.
    assert sidecar["anchor_symbols"] == ["NVDA"]
    assert sidecar["peers"] == []

    _run("Why is NVDA moving this week?")
    assert len(transport.requests) == 2, "a withheld packet is never served from cache"


def test_a_rejected_row_withholds_the_thorough_answer_too() -> None:
    """Both composition paths share the one judgment."""
    from argus.domain.research.cache import cache_get, research_cache_key
    from argus.domain.research.perplexity_agent import _packet_from_response

    packet = _packet_from_response(
        _typed_document(
            _rows_with_one_rejected(),
            answer="NVIDIA fell **4.3%** and analysts now target **$250**.",
        ),
        latency_ms=1,
        on_unpriced=lambda _: None,
    )
    assert packet.uncited_rows == 1
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
        "question_kind": "current_external",
        "subjects": [{"symbol": "NVDA", "name": "NVIDIA", "asset_class": "equity"}],
        "requires_publisher_sources": True,
        "cache_key": key,
    }

    composed = grounded.compose_completed_research(job_request=job_request, packet=packet)
    grounded.store_research_packet_for_job(job_request, packet)

    assert composed["research"]["degraded"] == {"code": "research_figures_unverified"}
    assert composed["research"]["rows"] == []
    assert "250" not in composed["answer"] and "4.3" not in composed["answer"]
    assert composed["answer"].startswith("Encontré fuentes, pero no pude verificar")
    assert cache_get(key) is None, "a withheld packet is never stored for the job"


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
    figureless["output"].insert(
        1,
        search_results_item({"url": PUBLISHER, "title": "Movers", "date": "2026-09-08"}),
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
                            label="ZZZZFAKE change today",
                            value=9.1,
                            symbol="ZZZZFAKE",
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
                        [retrieved_row(label="x", value=4.3, symbol="ZZZZFAKE")],
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
                        [retrieved_row(label="AAPL", value=4.3, symbol="AAPL")],
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
                        [retrieved_row(label="NVDA", value=4.3)],
                    ),
                    invocations=0,
                ),
                agent_response(
                    text=typed_answer_text(
                        "NVDA (NVDA) rose **4.3%**.",
                        [retrieved_row(label="NVDA", value=4.3)],
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
    every shape, not only on surveys, and is never cached."""
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

    _run("What is Apple at?")
    assert len(transport.requests) == 2, "a withheld packet is never served from cache"


def test_a_rowless_typed_answer_without_retrieval_is_not_grounded(monkeypatch) -> None:
    set_research_query(
        monkeypatch, globals(), question_kind="live_quote", symbols=["AAPL"]
    )
    _wire(
        monkeypatch,
        [
            agent_response(
                text=typed_answer_text("AAPL is **$200** today.", []), invocations=0
            )
        ],
    )

    result = _run("What is Apple at?")

    assert result is not None
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "research_not_grounded"}
    answer = result.stage_patch["assistant_response"]
    assert "200" not in answer
    assert answer.startswith("I couldn't complete the data lookup")
    assert sidecar["rows"] == [] and sidecar["sources"] == []


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
                    [retrieved_row(label="AAPL price", value=200.0, symbol="AAPL")],
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
            "NVDA (NVDA) rose **4.3%**.", [retrieved_row(label="NVDA", value=4.3)]
        ),
        invocations=0,
    )
    transport = _wire(monkeypatch, [document, document])

    result = _run("anything interesting moving today")

    assert result is not None
    assert len(transport.requests) == 2, "the concrete retry still fires once"
    sidecar = result.stage_patch["research"]
    assert sidecar["degraded"] == {"code": "survey_not_grounded"}
    assert result.stage_patch["assistant_response"] == (
        "I couldn't retrieve today's market movers."
    )
