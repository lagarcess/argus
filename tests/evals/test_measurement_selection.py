"""Selection acceptance follows delivered evidence, not a callable's name."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from argus.agent_runtime.discovery.contracts import ValidatedCandidate
from argus.agent_runtime.research_grounded import build_research_sidecar
from argus.agent_runtime.research_rows import research_next_experiment_rows
from argus.agent_runtime.research_tools import (
    CitedResearchFiguresResult,
    ResearchToolResult,
    ScreeningArguments,
    get_research_declarations,
    research_result_from_patch,
)
from argus.agent_runtime.stages.interpret_types import StageResult
from argus.domain.market_data.assets import SYNTHETIC_UNIT_ASSETS
from argus.domain.research.cache import DATA_CLASS_TTL_SECONDS
from argus.domain.research.evidence_policy import build_research_evidence_policy
from argus.domain.tool_contracts import ToolCall
from argus.domain.tool_declaration import ToolPolicy
from faker import Faker

from tests.agent_runtime.test_registered_tool_execution import _catalog
from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_selection import SELECTION_CONTRACT_VERSION
from tests.research.conftest import retrieved_row

fake = Faker()


@pytest.fixture
def selection_case():
    return next(
        case
        for case in harness.load_eval_cases()
        if case.id == "asset_discovery_trending_crypto_exact_issue_344"
    )


def _selection_patch(*, figures=True, discovery=False, action=True, symbol="BTC"):
    asset_class, name, _ = SYNTHETIC_UNIT_ASSETS[symbol]
    asset = {"symbol": symbol, "name": name, "asset_class": asset_class}
    observed = datetime.now(timezone.utc)
    source = {
        "url": "https://www.coingecko.com/en/highlights/trending-crypto",
        "title": "Current trending assets",
        "source_date": observed.date().isoformat(),
    }
    row = retrieved_row(
        subject=name,
        symbol=asset["symbol"],
        label="trending search rank",
        value=1.0,
        kind="count",
        unit="rank",
        as_of=observed.date().isoformat(),
        source_url=source["url"],
    )
    patch = {
        "intent": "follow_up",
        "assistant_response": f"{name} is among the current trending cryptocurrencies.",
        "research": build_research_sidecar(
            capability_class="screening",
            shape="balanced",
            sources=[source] if figures else [],
            retrieved_at=observed.isoformat(),
            subjects=[asset] if action and not discovery else [],
            peers=[asset] if discovery else [],
            usage={},
            period_of_interest=None,
            retrieved_rows=[row] if figures else [],
            evidence_policy=build_research_evidence_policy(
                question_kind="screening", question_as_of_date=observed.date()
            ),
        ),
    }
    if discovery:
        candidate = ValidatedCandidate(**asset, reason_text="A verified candidate.")
        patch["discovery"] = {
            "schema_version": "argus_discovery/v1",
            "kind": "asset_discovery",
            "relationship": "category",
            "query_summary": "Trending cryptocurrencies",
            "candidates": [candidate.model_dump(mode="json")],
            "sources": [],
            "retrieved_at": observed.isoformat(),
            "unverified_names": [],
        }
    elif action:
        patch["next_experiments"] = research_next_experiment_rows(
            subjects=[asset],
            peers=[],
            language="en",
            coverage_probe=lambda *_: observed.date() - timedelta(days=365 * 4),
        )
    return patch


def _wire_delivery(monkeypatch, *, patches, names, judge_pass=True, cited_result=False):
    pending = iter(patches)
    declarations = []
    template = next(
        item for item in get_research_declarations() if item.name == "screening"
    )

    def delivered(arguments: ScreeningArguments, *, context) -> ResearchToolResult:
        patch = deepcopy(next(pending))
        context.stage_result = StageResult(outcome="ready_to_respond", stage_patch=patch)
        return research_result_from_patch(patch)

    def delivered_figures(
        arguments: ScreeningArguments, *, context
    ) -> CitedResearchFiguresResult:
        result = delivered(arguments, context=context)
        return CitedResearchFiguresResult.model_validate(result.model_dump())

    for name in dict.fromkeys(names):
        declarations.append(
            replace(
                template,
                name=name,
                handler=delivered_figures if cited_result else delivered,
                policy=ToolPolicy(),
            )
        )
    monkeypatch.setattr(
        "argus.domain.capability_registry.get_tool_catalog",
        lambda **_: _catalog(*declarations),
    )
    calls = [
        ToolCall(
            tool_name=name,
            call_id=fake.uuid4(),
            # Input prose is deliberately unrelated: evidence must come from returns.
            arguments={"request": fake.sentence(), "criteria": [fake.word()]},
        )
        for name in names
    ]
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_: StageResult(
            outcome="approved_for_execution",
            stage_patch={"intent": "calculate", "tool_calls": calls},
        ),
    )
    judged = []

    async def capture_judge(**kwargs):
        judged.append(json.loads(kwargs["messages"][1]["content"]))
        return harness.ProseJudgeResponse.model_validate(
            {
                "pass": judge_pass,
                "failed_criteria": [] if judge_pass else ["selection_relevance"],
                "notes": "Authored judge result; no provider call.",
            }
        )

    monkeypatch.setattr(harness, "invoke_openrouter_json_schema", capture_judge)
    return calls, judged


@pytest.mark.parametrize(
    "names,cited_result",
    [
        (("screening",), False),
        (("cited_figures",), True),
        (("read_figures", "select_candidates"), False),
        (("read", "read"), False),
    ],
)
def test_alternate_and_composed_delivery_preserve_the_same_acceptance(
    monkeypatch, selection_case, names, cited_result
):
    patches = (
        [_selection_patch()]
        if len(names) == 1
        else [
            _selection_patch(action=False),
            _selection_patch(figures=False, discovery=True),
        ]
    )
    calls, judged = _wire_delivery(
        monkeypatch, patches=patches, names=names, cited_result=cited_result
    )

    result = harness.run_eval_case(selection_case)

    assert result["failed_checks"] == [], result["failed_checks"]
    assert result["typed_outcome"]["tool_calls"] == [
        call.model_dump(mode="json") for call in calls
    ]
    assert result["typed_outcome"]["offered"]["discovery_symbols"] == ["BTC"]
    assert len(judged) == 1
    assert judged[0]["selection_expectations"] == selection_case.expected.asset_discovery
    assert judged[0]["criteria"] == [
        *selection_case.prose_judge_criteria,
        "selection_relevance",
    ]
    retained = result["prose_judge"]["selection_evidence"]
    assert retained["contract_version"] == SELECTION_CONTRACT_VERSION
    assert retained["assets"][0]["asset_class"] == "crypto"
    assert all(call.call_id not in json.dumps(judged) for call in calls)
    assert all(call.arguments["request"] not in json.dumps(retained) for call in calls)


@pytest.mark.parametrize(
    "case_id,symbol",
    [
        ("asset_discovery_peer_anchor_english_issue_244", "AMD"),
        ("asset_discovery_trending_crypto_exact_issue_344", "BTC"),
    ],
)
def test_unsourced_candidate_reasons_reach_the_judge_without_becoming_current_facts(
    monkeypatch, case_id, symbol
):
    case = next(case for case in harness.load_eval_cases() if case.id == case_id)
    patch = _selection_patch(figures=False, discovery=True, symbol=symbol)
    patch["discovery"]["relationship"] = case.expected.asset_discovery["relationship"]
    candidate = patch["discovery"]["candidates"][0]
    _wire_delivery(monkeypatch, patches=[patch], names=("deliver_candidates",))

    result = harness.run_eval_case(case)

    facts = result["prose_judge"]["selection_evidence"]["assets"][0]["facts"]
    assert len(facts) == 1
    assert facts[0]["reason"] == candidate["reason_text"]
    assert facts[0]["source"] is None
    assert "figure" not in facts[0]
    rendered = json.loads(result["prose_judge"]["judged_rendered_context"]["text"])
    assert rendered["discovery_grounding"] == "general_knowledge_not_current_search"
    assert rendered.get("discovery_sources", []) == []
    assert result["prose_judge"]["requested_criteria"] == [
        *case.prose_judge_criteria,
        "selection_relevance",
    ]
    if case.expected.asset_discovery.get("needs_current_facts"):
        assert any("current-source" in check for check in result["failed_checks"])
        assert result["status"] == "failed"
    else:
        assert result["failed_checks"] == []


@pytest.mark.parametrize(
    "missing,reason",
    [
        ("source", "current-source"),
        ("timestamp", "currentness"),
        ("stale", "currentness"),
        ("old_source", "currentness"),
        ("future_source", "currentness"),
        ("malformed_source", "currentness"),
        ("identity", "identity"),
        ("class", "asset_class"),
    ],
)
def test_missing_structural_evidence_cannot_be_rescued_by_the_judge(
    monkeypatch, selection_case, missing, reason
):
    patch = _selection_patch()
    research = patch["research"]
    if missing == "source":
        research["sources"] = []
        research["rows"][0]["source_url"] = None
    elif missing == "timestamp":
        research["retrieved_at"] = None
    elif missing == "stale":
        research["retrieved_at"] = (
            datetime.now(timezone.utc)
            - timedelta(seconds=DATA_CLASS_TTL_SECONDS["movers"] + 1)
        ).isoformat()
    elif missing == "identity":
        research["rows"][0]["subject"] = "A different named entity"
    elif missing.endswith("_source"):
        offset = -1 if missing == "old_source" else 1
        research["sources"][0]["source_date"] = (
            "not-a-date"
            if missing == "malformed_source"
            else (datetime.now(timezone.utc).date() + timedelta(days=offset)).isoformat()
        )
    else:
        del research["follow_up"]["subjects"][0]["asset_class"]
    _wire_delivery(monkeypatch, patches=[patch], names=("screening",))

    result = harness.run_eval_case(selection_case)

    assert result["status"] == "failed"
    assert any(
        check.startswith("asset_discovery:") and reason in check
        for check in result["failed_checks"]
    )
    assert result["prose_judge"]["pass"] is True


@pytest.mark.parametrize(
    "data_class,source_before_period,expected_current",
    [
        ("fundamentals", False, True),
        ("movers", False, False),
        ("fundamentals", True, False),
    ],
)
def test_current_selection_preserves_the_runtime_data_and_source_period_policy(
    monkeypatch, selection_case, data_class, source_before_period, expected_current
):
    patch = _selection_patch()
    research = patch["research"]
    observed = datetime.now(timezone.utc)
    period_start = observed.date() - timedelta(days=14)
    policy = build_research_evidence_policy(
        question_kind=None,
        data_class=data_class,
        period_start_date=period_start,
        question_as_of_date=observed.date(),
    )
    research["evidence_policy"] = policy.model_dump(mode="json")
    research["retrieved_at"] = (observed - timedelta(minutes=10)).isoformat()
    research["sources"][0]["source_date"] = (
        period_start - timedelta(days=int(source_before_period))
    ).isoformat()
    _wire_delivery(monkeypatch, patches=[patch], names=("read",))

    result = harness.run_eval_case(selection_case)

    assert (result["failed_checks"] == []) is expected_current
    if not expected_current:
        assert any("currentness unproven" in check for check in result["failed_checks"])
    fact = result["typed_outcome"]["asset_discovery"]["assets"][0]["facts"][0]
    assert fact["evidence_policy"] == policy.model_dump(mode="json")


@pytest.mark.parametrize("figures", [False, True])
def test_serialized_judge_payload_keeps_semantic_evidence_without_cache_policy(
    monkeypatch, selection_case, figures
):
    patch = _selection_patch(figures=figures, discovery=not figures)
    observed = datetime.now(timezone.utc)
    policy = build_research_evidence_policy(
        question_kind="find_assets",
        period_start_date=observed.date() - timedelta(days=14),
        question_as_of_date=observed.date(),
    ).model_dump(mode="json")
    patch["research"]["evidence_policy"] = policy
    _, judged = _wire_delivery(monkeypatch, patches=[patch], names=("read",))

    result = harness.run_eval_case(selection_case)

    # The scorecard keeps the complete runtime policy; only the model's view changes.
    recorded = json.loads(json.dumps(result))["typed_outcome"]["asset_discovery"]
    fact = recorded["assets"][0]["facts"][0]
    assert fact["evidence_policy"] == policy
    context = judged[0]["selection_evidence"]
    projected = context["assets"][0]["facts"][0]
    semantic_keys = {
        "symbol",
        "name",
        "asset_class",
        "reason",
        "figure",
        "source",
        "citation_url",
        "citation_origin",
        "retrieved_at",
    }
    assert set(projected) == (set(fact) & semantic_keys) | {"source_period"}
    assert {key: projected[key] for key in semantic_keys & fact.keys()} == {
        key: fact[key] for key in semantic_keys & fact.keys()
    }
    assert projected["source_period"] == {
        key: policy[key]
        for key in (
            "period_start_date",
            "question_as_of_date",
            "current_survey",
            "closed_period",
        )
    }
    assert not {"data_class", "max_age_seconds", "question_kind"} & set(
        projected["source_period"]
    )
    assert context["observed_at"] == recorded["observed_at"]
    assert context["assets"][0] == {
        **recorded["assets"][0]["identity"],
        "facts": [projected],
        "deliveries": [
            {
                "retrieved_at": recorded["assets"][0]["deliveries"][0]["retrieved_at"],
                "sources": recorded["assets"][0]["deliveries"][0]["sources"],
                "answer": recorded["assets"][0]["deliveries"][0]["answer"],
                "source_period": projected["source_period"],
            }
        ],
    }
    assert result["prose_judge"]["selection_evidence"] == context
    assert judged[0]["selection_expectations"] == selection_case.expected.asset_discovery


def test_a_model_citation_outside_the_retrieved_drawer_is_retained_as_such(
    monkeypatch, selection_case
):
    patch = _selection_patch()
    citation_url = "https://www.coingecko.com/en/coins/bitcoin"
    patch["research"]["rows"][0]["source_url"] = citation_url
    _, judged = _wire_delivery(monkeypatch, patches=[patch], names=("read",))

    result = harness.run_eval_case(selection_case)

    fact = result["typed_outcome"]["asset_discovery"]["assets"][0]["facts"][0]
    assert fact["citation_url"] == citation_url
    assert fact["citation_origin"] == "model"
    assert fact["source"] is None
    projected = judged[0]["selection_evidence"]["assets"][0]["facts"][0]
    assert projected["citation_origin"] == "model"
    assert projected["citation_url"] == citation_url
    assert projected["source"] is None
    assert projected["source_period"] == {
        key: fact["evidence_policy"][key]
        for key in (
            "period_start_date",
            "question_as_of_date",
            "current_survey",
            "closed_period",
        )
    }
    assert result["failed_checks"] == []


@pytest.mark.parametrize("broken", [None, "return", "effect", "peer_class"])
def test_subject_and_peer_actions_require_the_same_completed_delivery(
    monkeypatch, broken
):
    case = next(
        case
        for case in harness.load_eval_cases()
        if case.id == "asset_discovery_recent_ipo_exact_issue_344"
    )
    patch = _selection_patch(symbol="AAPL")
    peer_patch = _selection_patch(symbol="MSFT")
    research = patch["research"]
    subjects = research["follow_up"]["subjects"]
    peers = peer_patch["research"]["follow_up"]["subjects"]
    patch["research"] = build_research_sidecar(
        capability_class="screening",
        shape="balanced",
        sources=research["sources"],
        retrieved_at=research["retrieved_at"],
        subjects=subjects,
        peers=peers,
        usage={},
        period_of_interest=None,
        retrieved_rows=[*research["rows"], *peer_patch["research"]["rows"]],
        evidence_policy=build_research_evidence_policy(
            question_kind="screening",
            question_as_of_date=datetime.now(timezone.utc).date(),
        ),
    )
    patch["next_experiments"] = research_next_experiment_rows(
        subjects=subjects,
        peers=peers,
        language="en",
        coverage_probe=lambda *_: datetime.now(timezone.utc).date()
        - timedelta(days=365 * 4),
    )
    _wire_delivery(monkeypatch, patches=[patch], names=("read",))
    actual = harness.dispatch_requested_calls

    def dispatch(**kwargs):
        result = actual(**kwargs)
        delivered = result.stage_patch
        effect = delivered["tool_effects"][0]
        if broken == "return":
            card = delivered["final_response_payload"]["tool_result_cards"][0]
            card["outcome"]["result"]["peers"] = []
            delivered["tool_call_records"][0]["tool_outcome"] = deepcopy(card["outcome"])
        elif broken == "effect":
            effect["artifact_id"] = fake.uuid4()
        elif broken == "peer_class":
            del effect["stage_patch"]["research"]["peers"][0]["asset_class"]
        return result

    monkeypatch.setattr(harness, "dispatch_requested_calls", dispatch)

    result = harness.run_eval_case(case)

    evidence = result["typed_outcome"]["asset_discovery"]
    if broken is None:
        assert result["failed_checks"] == []
        assert [asset["identity"] for asset in evidence["assets"]] == [*subjects, *peers]
    else:
        assert any("identity unproven" in check for check in result["failed_checks"])
        assert peers[0] not in [asset["identity"] for asset in evidence["assets"]]


def test_same_ticker_wrong_asset_action_fails(monkeypatch, selection_case):
    patch = _selection_patch()
    action_asset = {"symbol": "VVV", "name": "Valvoline Inc.", "asset_class": "equity"}
    patch["research"]["rows"][0].update(symbol="VVV", subject="Venice Token")
    patch["research"]["follow_up"]["subjects"] = [action_asset]
    patch["next_experiments"] = research_next_experiment_rows(
        subjects=[action_asset],
        peers=[],
        language="en",
        coverage_probe=lambda *_: datetime.now(timezone.utc).date()
        - timedelta(days=1460),
    )
    _wire_delivery(monkeypatch, patches=[patch], names=("screening",))

    result = harness.run_eval_case(selection_case)

    assert any("identity" in check for check in result["failed_checks"])
    assert result["typed_outcome"]["offered"]["actionable"] is False


@pytest.mark.parametrize("linked", [False, True])
def test_candidate_link_is_retained_separately_from_its_delivery_source_drawer(
    monkeypatch, selection_case, linked
):
    patch = _selection_patch(figures=False, discovery=True)
    patch["discovery"]["sources"] = _selection_patch()["research"]["sources"]
    patch["discovery"]["candidates"][0]["source_indices"] = [0] if linked else []
    _wire_delivery(monkeypatch, patches=[patch], names=("deliver_candidates",))

    result = harness.run_eval_case(selection_case)

    assert result["status"] == "passed"
    if not linked:
        facts = result["prose_judge"]["selection_evidence"]["assets"][0]["facts"]
        assert facts[0]["reason"] == patch["discovery"]["candidates"][0]["reason_text"]
        assert facts[0]["source"] is None
    rendered = json.loads(result["prose_judge"]["judged_rendered_context"]["text"])
    assert "discovery_grounding" not in rendered


@pytest.mark.parametrize(
    "broken",
    [
        "record",
        "tool_name",
        "arguments",
        "effect",
        "card",
        "card_type",
        "card_version",
        "declared_return",
        "pending",
    ],
)
def test_unbound_or_incomplete_results_do_not_supply_selection_facts(
    monkeypatch, selection_case, broken
):
    _wire_delivery(
        monkeypatch,
        patches=[_selection_patch()],
        names=("screening",),
        cited_result=broken == "declared_return",
    )
    actual = harness.dispatch_requested_calls

    def dispatch(**kwargs):
        result = actual(**kwargs)
        patch = result.stage_patch
        card = patch["final_response_payload"]["tool_result_cards"][0]
        if broken == "record":
            patch["tool_call_records"] = []
        elif broken == "tool_name":
            patch["tool_call_records"][0]["tool_name"] = "different_operation"
        elif broken == "arguments":
            card["arguments"]["request"] = fake.sentence()
        elif broken == "effect":
            patch["tool_effects"][0]["artifact_id"] = fake.uuid4()
        elif broken == "card":
            card["call_id"] = fake.uuid4()
        elif broken == "card_type":
            card["card_type"] = "unbound_presentation"
        elif broken == "card_version":
            card["card_version"] += 1
        elif broken == "declared_return":
            # Valid in the compatibility envelope, forbidden by this callable's
            # actual CitedResearchFiguresResult return contract.
            card["outcome"]["result"]["relationship"] = "category"
            ResearchToolResult.model_validate(card["outcome"]["result"])
            patch["tool_call_records"][0]["tool_outcome"] = deepcopy(card["outcome"])
        else:
            card["outcome"]["result"] = {"status": "pending"}
            card["presentation"].update(answer=None, narrative=None, rows=[], sources=[])
            patch["tool_call_records"][0]["tool_outcome"] = deepcopy(card["outcome"])
        return result

    monkeypatch.setattr(harness, "dispatch_requested_calls", dispatch)

    result = harness.run_eval_case(selection_case)

    assert result["status"] == "failed"
    assert result["typed_outcome"]["asset_discovery"]["assets"] == []


def test_only_final_selectable_actions_count(monkeypatch, selection_case):
    _wire_delivery(
        monkeypatch,
        patches=[_selection_patch(symbol="BTC"), _selection_patch(symbol="ETH")],
        names=("read", "read"),
    )

    result = harness.run_eval_case(selection_case)

    assert result["failed_checks"] == []
    assert result["typed_outcome"]["offered"]["discovery_symbols"] == ["ETH"]
    assert len(result["typed_outcome"]["tool_result_cards"]) == 2


@pytest.mark.parametrize("judge", ["rejects", "disabled"])
def test_selection_relevance_remains_required(monkeypatch, selection_case, judge):
    _wire_delivery(
        monkeypatch, patches=[_selection_patch()], names=("screening",), judge_pass=False
    )

    result = harness.run_eval_case(selection_case, run_prose_judge=judge != "disabled")

    assert result["status"] == "failed"
    assert any("selection_relevance" in check for check in result["failed_checks"])


def test_unavailable_relevance_judge_blocks_the_gate(monkeypatch, selection_case):
    _wire_delivery(monkeypatch, patches=[_selection_patch()], names=("screening",))

    async def unavailable(**_):
        raise RuntimeError("Authored judge outage")

    monkeypatch.setattr(harness, "invoke_openrouter_json_schema", unavailable)

    result = harness.run_eval_case(selection_case)

    assert result["status"] == "infrastructure_error"
    assert result["prose_judge"]["status"] == "unavailable"
    assert "selection_relevance" in result["prose_judge"]["requested_criteria"]
    assert harness.blocking_eval_results([result]) == [result]


def test_zero_calls_cannot_invent_selection_evidence(monkeypatch, selection_case):
    _wire_delivery(monkeypatch, patches=[], names=())
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_: StageResult(
            outcome="ready_to_respond",
            stage_patch={"intent": "follow_up", "assistant_response": fake.sentence()},
        ),
    )

    result = harness.run_eval_case(selection_case)

    assert result["status"] == "failed"
    assert result["typed_outcome"]["tool_calls"] == []
    assert result["typed_outcome"]["asset_discovery"]["assets"] == []


def test_legacy_no_call_discovery_keeps_its_original_contract(selection_case):
    expected = selection_case.expected.asset_discovery
    failures = []
    harness._compare_asset_discovery(
        expected,
        {**expected, "category_description": "Trending crypto"},
        failures,
    )
    assert failures == []


@pytest.mark.parametrize("has_figure", [False, True])
def test_current_selection_uses_bound_delivery_sources_without_inventing_row_citations(
    monkeypatch, selection_case, has_figure
):
    patch = _selection_patch()
    if has_figure:
        patch["research"]["rows"][0]["source_url"] = None
    else:
        patch["research"]["rows"] = []
    _, judged = _wire_delivery(monkeypatch, patches=[patch], names=("read",))

    result = harness.run_eval_case(selection_case)

    assert result["failed_checks"] == [], result["failed_checks"]
    asset = result["typed_outcome"]["asset_discovery"]["assets"][0]
    assert asset["deliveries"][0]["sources"] == patch["research"]["sources"]
    assert asset["deliveries"][0]["answer"] == patch["assistant_response"]
    if has_figure:
        assert asset["facts"][0]["citation_url"] is None
        assert asset["facts"][0]["source"] is None
    else:
        assert asset["facts"] == []
    context = judged[0]["selection_evidence"]["assets"][0]
    assert context["deliveries"][0]["sources"] == patch["research"]["sources"]
    assert "selection_relevance" in judged[0]["criteria"]


def test_source_drawer_from_an_unrelated_completed_delivery_cannot_supply_currentness(
    monkeypatch, selection_case
):
    current_other_asset = _selection_patch(symbol="ETH")
    unsourced_action = _selection_patch(figures=False, discovery=True)
    _wire_delivery(
        monkeypatch,
        patches=[current_other_asset, unsourced_action],
        names=("read", "read"),
    )

    result = harness.run_eval_case(selection_case)

    assert any("current-source" in check for check in result["failed_checks"])
    assert result["typed_outcome"]["offered"]["discovery_symbols"] == ["BTC"]
