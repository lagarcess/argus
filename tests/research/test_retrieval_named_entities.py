"""The retrieval result carries named entities without another model read."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from argus.domain.research.contracts import (
    MAX_PEER_PAIRS,
    ResearchNamePair,
    ResearchUnavailableError,
    TypedRetrieval,
    typed_retrieval_json_schema,
)
from argus.domain.research.perplexity_agent import _packet_from_response

from tests.research.conftest import agent_response
from tests.research.test_retrieval_contract_probe import CURRENT_PROBES


def _document(*pairs: ResearchNamePair, lookup_rows=None) -> dict:
    return agent_response(
        text=json.dumps(
            {
                "answer_markdown": "The retrieved answer names these companies.",
                "rows": [],
                "name_pairs": [pair.model_dump() for pair in pairs],
            }
        ),
        lookup_rows=lookup_rows,
    )


def test_named_entities_use_the_same_model_for_request_and_read() -> None:
    pair = ResearchNamePair(symbol="AAPL", name="Apple Inc.")
    result = TypedRetrieval.model_validate(
        {"answer_markdown": pair.name, "rows": [], "name_pairs": [pair.model_dump()]}
    )

    assert result.name_pairs == [pair]
    schema = typed_retrieval_json_schema()
    assert "name_pairs" in schema["required"]
    pair_schema = schema["properties"]["name_pairs"]["items"]
    assert set(pair_schema["required"]) == set(ResearchNamePair.model_fields)
    assert pair_schema["additionalProperties"] is False


def test_typed_names_reach_the_packet_without_financial_figures() -> None:
    pair = ResearchNamePair(symbol="BTC", name="Bitcoin")
    packet = _packet_from_response(_document(pair), latency_ms=0, on_unpriced=lambda _: None)

    assert packet.typed_answer
    assert packet.published_rows == ()
    assert packet.name_pairs == (pair,)


def test_finance_metadata_cannot_erase_a_conflicting_typed_name() -> None:
    names = (
        ResearchNamePair(symbol="VVV", name="Valvoline Inc."),
        ResearchNamePair(symbol="VVV", name="Venice Token"),
    )
    packet = _packet_from_response(
        _document(*names, *names, lookup_rows=[("VVV", "VVV", "VVV")]),
        latency_ms=0,
        on_unpriced=lambda _: None,
    )

    assert {(pair.symbol, pair.name) for pair in packet.name_pairs} == {
        ("VVV", "VVV"),
        *((pair.symbol, pair.name) for pair in names),
    }
    assert len(packet.name_pairs) == len(names) + 1


def test_candidate_limit_does_not_cut_a_retained_symbols_conflicting_names() -> None:
    identities = [
        ResearchNamePair(symbol=f"S{index}", name=f"Company {index}")
        for index in range(MAX_PEER_PAIRS + 1)
    ]
    conflict = identities[0].model_copy(update={"name": "Different named entity"})
    packet = _packet_from_response(
        _document(*identities, conflict), latency_ms=0, on_unpriced=lambda _: None
    )

    assert {pair.symbol for pair in packet.name_pairs} == {
        pair.symbol for pair in identities[:MAX_PEER_PAIRS]
    }
    assert identities[0] in packet.name_pairs
    assert conflict in packet.name_pairs


def test_invalid_named_entity_is_a_malformed_result() -> None:
    document = _document()
    text = next(item for item in document["output"] if item["type"] == "message")
    body = json.loads(text["content"][0]["text"])
    body["name_pairs"] = [{"name": "Missing a symbol"}]
    text["content"][0]["text"] = json.dumps(body)

    with pytest.raises(ResearchUnavailableError, match="malformed_response"):
        _packet_from_response(document, latency_ms=0, on_unpriced=lambda _: None)


@pytest.mark.parametrize(
    "name",
    [
        "fast_quote_typed",
        "typed_rows_current_external",
        "domain_filtered_local_source",
        "thorough_typed_background",
    ],
)
def test_old_recordings_remain_readable_without_declared_names(name: str) -> None:
    recording = json.loads((Path(CURRENT_PROBES) / f"{name}.json").read_text())
    packet = _packet_from_response(
        recording["exchanges"][-1]["response"],
        latency_ms=0,
        on_unpriced=lambda _: None,
    )
    legacy = TypedRetrieval.model_validate(
        {"answer_markdown": packet.answer_markdown, "rows": list(packet.published_rows)}
    )

    assert packet.typed_answer
    assert legacy.name_pairs == []
    assert tuple(legacy.rows) == packet.published_rows
