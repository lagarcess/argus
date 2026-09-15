"""Research offers keep catalog identity when an ETF and crypto share BTC."""

from __future__ import annotations

import json
from datetime import date

import pytest
from argus.agent_runtime import research_answer, resolution
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.research_rows import (
    research_next_experiment_rows,
    verified_peers,
)
from argus.domain.market_data import assets
from argus.domain.research.contracts import ResearchNamePair


@pytest.fixture
def collision_catalog(monkeypatch, tmp_path):
    listings = [
        ("BTC", "Grayscale Bitcoin Mini Trust ETF", "us_equity"),
        ("IBIT", "iShares Bitcoin Trust ETF", "us_equity"),
        ("AAPL", "Apple Inc.", "us_equity"),
        ("MSFT", "Microsoft Corporation", "us_equity"),
        ("BTC/USD", "Bitcoin", "crypto"),
        ("ETH/USD", "Ethereum", "crypto"),
        ("SPY", "SPDR S&P 500 ETF Trust", "us_equity"),
    ]
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "alpaca_assets": [
                    {
                        "symbol": symbol,
                        "name": name,
                        "asset_class": cls,
                        "status": "active",
                    }
                    for symbol, name, cls in listings
                ],
                "kraken_asset_pairs": {},
            }
        )
    )
    monkeypatch.setenv("ARGUS_ASSET_PROVIDER_MODE", "recorded_provider_fixture")
    monkeypatch.setenv("ARGUS_ASSET_FIXTURE_PATH", str(path))
    assets.clear_asset_cache()
    from argus.domain.market_data import tradability

    monkeypatch.setattr(
        tradability, "_probe", lambda symbol, cls: tradability.TradableHistory("tradable")
    )
    tradability.clear_tradable_history_cache()
    etf = assets.ResolvedAsset("BTC", "equity", listings[0][1], "BTC", "alpaca")
    # The exact provider lookup is the external boundary that favors the ETF.
    monkeypatch.setattr(
        assets,
        "_resolve_live_provider_ticker",
        lambda symbol: etf if symbol == "BTC" else None,
    )
    yield
    assets.clear_asset_cache()
    tradability.clear_tradable_history_cache()


def _subjects(symbols, hint):
    return research_answer._resolved_subjects(
        ResearchQueryExtraction(
            question_kind="company_lookup",
            symbols=symbols,
            asset_class_hint=hint,
        )
    )


def _rows(subjects, peers=(), language="en", **kwargs):
    return research_next_experiment_rows(
        subjects=subjects,
        peers=list(peers),
        language=language,
        coverage_probe=lambda symbol, cls: date(2020, 1, 2),
        **kwargs,
    )


@pytest.mark.parametrize(
    "hint,name", [("crypto", "Bitcoin"), ("equity", "Grayscale Bitcoin Mini Trust ETF")]
)
@pytest.mark.parametrize("language", ["en", "es-419"])
def test_explicit_class_owns_research_label(collision_catalog, hint, name, language):
    subjects = _subjects(["BTC"], hint)
    assert subjects == [{"symbol": "BTC", "name": name, "asset_class": hint}]
    row = _rows(subjects, language=language)["rows"][0]
    assert row["label"].startswith(
        ("Test " if language == "en" else "Probar ") + name + " (BTC)"
    )


def test_bare_cross_class_symbol_offers_no_row(collision_catalog):
    assert _rows(_subjects(["BTC"], None)) is None


@pytest.mark.parametrize(
    "symbol,name,expected",
    [
        ("IBIT", "iShares Bitcoin Trust ETF", []),
        ("ETH", "Ethereum", ["ETH"]),
    ],
)
def test_bitcoin_peers_keep_only_crypto(collision_catalog, symbol, name, expected):
    subjects = _subjects(["BTC"], "crypto")
    peers = verified_peers(
        [ResearchNamePair(symbol=symbol, name=name)],
        exclude={"BTC"},
        asset_class_hint="crypto",
    )
    assert [p["symbol"] for p in peers] == expected
    rows = _rows(subjects, peers)["rows"]
    assert rows[0]["label"].startswith("Test Bitcoin (BTC)")
    assert len(rows) == 1 + bool(expected)
    if expected:
        assert "vs Ethereum (ETH)" in rows[1]["label"]


@pytest.mark.parametrize("other_is_peer", [True, False])
def test_mixed_class_inputs_never_share_comparison(collision_catalog, other_is_peer):
    bitcoin = _subjects(["BTC"], "crypto")
    apple = _subjects(["AAPL"], "equity")
    rows = _rows(
        bitcoin if other_is_peer else bitcoin + apple, apple if other_is_peer else []
    )["rows"]
    assert all(" vs " not in row["label"] for row in rows)
    assert rows[0]["label"].startswith("Test Bitcoin (BTC)")


def test_equity_comparison_still_offered(collision_catalog):
    peers = verified_peers(
        [ResearchNamePair(symbol="MSFT", name="Microsoft")],
        exclude={"AAPL"},
        asset_class_hint="equity",
    )
    rows = _rows(_subjects(["AAPL"], "equity"), peers)["rows"]
    assert rows[1]["label"].startswith("Test Apple (AAPL) vs Microsoft (MSFT)")


def test_research_ambiguity_policy_does_not_change_chat_default(collision_catalog):
    kwargs = dict(field="asset_universe[0]", source="llm_extraction")
    assert (
        resolution.resolve_asset_candidate("BTC", **kwargs).asset.asset_class == "equity"
    )
    strict = resolution.resolve_asset_candidate(
        "BTC", **kwargs, require_unambiguous_class=True
    )
    assert strict.status == "ambiguous"
    assert strict.asset is None
    assert {a.asset_class for a in strict.candidates} == {"equity", "crypto"}


@pytest.mark.parametrize("background", [False, True])
@pytest.mark.parametrize(
    "hint,peer,expected_count",
    [
        ("crypto", "IBIT", 1),
        ("crypto", "ETH", 2),
        (None, "IBIT", 0),
    ],
)
def test_published_answer_keeps_subject_class_and_honest_empty_rows(
    collision_catalog,
    monkeypatch,
    background,
    hint,
    peer,
    expected_count,
):
    from argus.agent_runtime import research_grounded as grounded
    from argus.agent_runtime import research_rows
    from argus.agent_runtime.research_rows import honest_no_next_line
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
    from argus.agent_runtime.state.models import StrategySummary, UserState
    from argus.domain.research.contracts import ResearchPacket, ResearchSource

    monkeypatch.setattr(
        research_rows, "_earliest_available", lambda symbol, cls: date(2020, 1, 2)
    )
    query = ResearchQueryExtraction(
        question_kind="company_lookup", symbols=["BTC"], asset_class_hint=hint
    )
    packet = ResearchPacket(
        answer_markdown="Bitcoin and related assets have different exposures.",
        name_pairs=(ResearchNamePair(symbol=peer, name=peer),),
        sources=(
            ResearchSource(
                title="Report", url="https://example.com/report", domain="example.com"
            ),
        ),
        tool_results=("web_search",),
    )
    subjects = research_answer._resolved_subjects(query)
    if background:
        output = grounded.compose_completed_research(
            job_request={
                "subjects": subjects,
                "requested_symbols": list(query.symbols),
                "asset_class_hint": query.asset_class_hint,
                "language": "en",
                "question_kind": query.question_kind,
            },
            packet=packet,
        )
        rows, answer = output.get("next_experiments"), output["answer"]
    else:
        interpretation = StructuredInterpretation(
            intent="unsupported_or_out_of_scope",
            task_relation="new_task",
            user_goal_summary="question",
            semantic_turn_act="educational_question",
            requires_clarification=False,
            candidate_strategy_draft=StrategySummary(),
            research_query=query,
        )
        result = grounded._packet_stage_result(
            packet=packet,
            subjects=subjects,
            shape="balanced",
            capability_class="balanced_lookup",
            language="en",
            interpretation=interpretation,
            user=UserState(user_id="test"),
            cache_status="miss",
            question_kind=query.question_kind,
        )
        rows, answer = (
            result.stage_patch.get("next_experiments"),
            result.stage_patch["assistant_response"],
        )
    assert len(rows["rows"] if rows else []) == expected_count
    if expected_count:
        assert rows["rows"][0]["label"].startswith("Test Bitcoin (BTC)")
    else:
        assert honest_no_next_line("en") in answer


@pytest.mark.parametrize("asset_class,expected", [("crypto", True), ("equity", False)])
def test_result_try_next_checks_the_available_class(
    collision_catalog, asset_class, expected
):
    from argus.agent_runtime.next_experiments import _peer_is_grounded

    assert (
        _peer_is_grounded(
            "ETH",
            asset_class=asset_class,
            start="2023-01-03",
            end="2023-12-29",
            prebake_probe=None,
        )
        is expected
    )


def test_named_bitcoin_and_apple_question_never_offers_mixed_comparison(
    collision_catalog,
):
    subjects = _subjects(["Bitcoin", "Apple"], None)
    assert {s["asset_class"] for s in subjects} == {"crypto", "equity"}
    rows = _rows(subjects)["rows"]
    assert rows[0]["label"].startswith("Test Bitcoin (BTC)")
    assert all(" vs " not in row["label"] for row in rows)


@pytest.mark.parametrize("hint", ["crypto", "equity"])
def test_research_identity_reaches_confirmation_with_controlled_interpretation(
    collision_catalog,
    hint,
):
    """The model's class read is controlled; resolution and confirmation are real."""
    from argus.agent_runtime.capabilities.contract import (
        build_default_capability_contract,
    )
    from argus.agent_runtime.stages.confirm import confirm_stage
    from argus.agent_runtime.state.models import RunState, StrategySummary

    subject = _subjects(["BTC"], hint)[0]
    row = _rows([subject])["rows"][0]
    # This is the existing chat owner's input after the structured model read.
    interpreted = resolution.resolve_asset_candidate(
        subject["symbol"],
        field="asset_universe[0]",
        source="llm_extraction",
        asset_class_hint=hint,
    ).asset
    assert interpreted is not None
    state = RunState.new(current_user_message=row["send_text"], recent_thread_history=[])
    state.candidate_strategy_draft = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=[interpreted.canonical_symbol],
        asset_class=interpreted.asset_class,
        date_range={"start": "2025-01-02", "end": "2025-12-31"},
        capital_amount=10000,
    )
    result = confirm_stage(state=state, contract=build_default_capability_contract())
    assert result.outcome == "await_approval", result.stage_patch
    payload = result.stage_patch["confirmation_payload"]
    assert payload["strategy"]["asset_class"] == subject["asset_class"]
    assert payload["strategy"]["asset_universe"] == [subject["symbol"]]
    assert payload["launch_payload"]["asset_class"] == subject["asset_class"]
    assert interpreted.name in row["label"]


@pytest.mark.parametrize("hint", ["crypto", "equity"])
def test_crossover_offer_keeps_research_identity(collision_catalog, hint):
    subjects = _subjects(["BTC"], hint)
    rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "slow_indicator": "sma",
        "fast_period": 50,
        "slow_period": 200,
        "direction": "bullish",
    }
    rows = _rows(subjects, entry_rule=rule)["rows"]
    assert [row["kind"] for row in rows] == ["research_test_rule", "research_test_single"]
    assert all(subjects[0]["name"] in row["label"] for row in rows)
