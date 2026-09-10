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
from argus.domain.tool_contracts import ToolCall
from argus.domain.tool_declaration import ToolPolicy
from faker import Faker

from tests.agent_runtime.test_registered_tool_execution import _catalog
from tests.evals import measurement_eval_harness as harness
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
    assert retained["contract_version"] == "argus-selection-evidence/v1"
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
def test_validated_candidate_requires_its_own_source_link(
    monkeypatch, selection_case, linked
):
    patch = _selection_patch(figures=False, discovery=True)
    patch["discovery"]["sources"] = _selection_patch()["research"]["sources"]
    patch["discovery"]["candidates"][0]["source_indices"] = [0] if linked else []
    _wire_delivery(monkeypatch, patches=[patch], names=("deliver_candidates",))

    result = harness.run_eval_case(selection_case)

    assert (result["status"] == "passed") is linked
    if not linked:
        assert any("current-source" in check for check in result["failed_checks"])
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
