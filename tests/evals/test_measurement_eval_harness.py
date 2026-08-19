from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.evals import measurement_eval_harness as harness
from tests.evals.measurement_eval_harness import (
    FIXTURE_DIR,
    LOCKED_EVAL_CATEGORIES,
    PROSE_JUDGE_RUBRIC_VERSION,
    load_eval_cases,
)
from tests.evals.measurement_eval_scorecard import measurement_fixture_case_ids
from tests.evals.measurement_outcome import offered_to_user

EXPECTED_LOCKED_CATEGORIES = {
    "messy_english",
    "messy_spanish",
    "ui_user_language_mismatch",
    "action_chip_semantics",
    "capability_honesty",
    "backtest_metric_correctness",
    "graceful_recovery",
    "asset_discovery_routing",
    "dca_capital_semantics",
}

PHRASE_ASSERTION_KEYS = {
    "expected_phrase",
    "expected_phrasing",
    "expected_response",
    "expected_text",
    "must_include",
    "must_not_include",
}


def _walk(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        pairs = list(value.items())
        for nested in value.values():
            pairs.extend(_walk(nested))
        return pairs
    if isinstance(value, list):
        pairs: list[tuple[str, Any]] = []
        for nested in value:
            pairs.extend(_walk(nested))
        return pairs
    return []


def test_measurement_fixtures_cover_locked_categories_as_data() -> None:
    cases = load_eval_cases()

    assert tuple(case.id for case in cases) == measurement_fixture_case_ids()
    assert LOCKED_EVAL_CATEGORIES == EXPECTED_LOCKED_CATEGORIES
    assert {case.category for case in cases} == EXPECTED_LOCKED_CATEGORIES
    assert {path.stem for path in FIXTURE_DIR.glob("*.yaml")} == (
        EXPECTED_LOCKED_CATEGORIES
    )

    for category in EXPECTED_LOCKED_CATEGORIES:
        category_cases = [case for case in cases if case.category == category]
        assert category_cases, category
        for case in category_cases:
            assert case.id
            assert case.prompt or case.action is not None
            assert case.expected.intent
            assert case.expected.capability_verdict


def test_measurement_fixtures_do_not_assert_expected_prose() -> None:
    for path in sorted(Path(FIXTURE_DIR).glob("*.yaml")):
        raw = path.read_text(encoding="utf-8")
        assert "expected phrasing" not in raw.lower()

    cases = load_eval_cases()
    offending_keys: list[str] = []
    for case in cases:
        raw_case = case.raw
        for key, _value in _walk(raw_case):
            if key in PHRASE_ASSERTION_KEYS:
                offending_keys.append(f"{case.id}:{key}")

    assert offending_keys == []
    assert PROSE_JUDGE_RUBRIC_VERSION == "argus-prose-quality-v1"


def test_expected_fail_baselines_are_issue_tagged() -> None:
    expected_failures = [case for case in load_eval_cases() if case.expected_fail]

    for case in expected_failures:
        assert case.expected_fail is not None
        assert case.expected_fail.issue.startswith("#")
        assert case.expected_fail.reason
        assert case.expected_fail.allowed_failures


def test_expected_fail_only_masks_allowed_failure_prefixes() -> None:
    expected_fail = harness.ExpectedFail(
        issue="#142",
        reason="Known company-name asset drop.",
        allowed_failures=("assets:", "stage_outcomes:"),
    )

    assert (
        harness._result_status(
            [
                "assets: expected ['TGT', 'WMT', 'COST'], got []",
                "stage_outcomes: expected ['ready_for_confirmation'], got ['needs']",
            ],
            expected_fail=expected_fail,
        )
        == "expected_failed"
    )
    assert (
        harness._result_status(
            [
                "assets: expected ['TGT', 'WMT', 'COST'], got []",
                "benchmark_symbol: expected 'SPY', got 'QQQ'",
            ],
            expected_fail=expected_fail,
        )
        == "failed"
    )
    assert harness._result_status([], expected_fail=expected_fail) == "unexpected_pass"


def _asset_discovery_case(
    expected_asset_discovery: dict[str, Any] | None,
    *,
    semantic_turn_act: str | None = "asset_discovery",
) -> harness.EvalCase:
    return harness.EvalCase(
        id="asset-discovery-routing-check",
        category="asset_discovery_routing",
        prompt="what cybersecurity stocks could I test?",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="conversation_followup",
            capability_verdict="answer_only",
            semantic_turn_act=semantic_turn_act,
            asset_discovery=expected_asset_discovery,
        ),
    )


def _asset_discovery_outcome(
    *,
    semantic_turn_act: str | None,
    asset_discovery: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "intent": "conversation_followup",
        "capability_verdict": "answer_only",
        "semantic_turn_act": semantic_turn_act,
        "asset_discovery": asset_discovery,
    }


def test_asset_discovery_expectations_pass_on_correct_route() -> None:
    case = _asset_discovery_case(
        {
            "relationship": "category",
            "anchor_symbols": [],
            "category_description_includes_any": ["cybersecurity"],
        }
    )

    failures = harness.typed_expectation_failures(
        case=case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="asset_discovery",
            asset_discovery={
                "relationship": "category",
                "category_description": "cybersecurity stocks",
                "anchor_symbols": [],
                "asset_class_hint": None,
            },
        ),
    )

    assert failures == []


def test_asset_discovery_expectations_flag_misroutes() -> None:
    category_case = _asset_discovery_case(
        {
            "relationship": "category",
            "anchor_symbols": [],
            "category_description_includes_any": ["cybersecurity"],
        }
    )

    act_misroute = harness.typed_expectation_failures(
        case=category_case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="new_idea",
            asset_discovery=None,
        ),
    )
    assert any(failure.startswith("semantic_turn_act:") for failure in act_misroute)
    assert any(failure.startswith("asset_discovery:") for failure in act_misroute)

    wrong_relationship = harness.typed_expectation_failures(
        case=category_case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="asset_discovery",
            asset_discovery={
                "relationship": "peer",
                "category_description": "cybersecurity stocks",
                "anchor_symbols": [],
                "asset_class_hint": None,
            },
        ),
    )
    assert any(
        failure.startswith("asset_discovery.relationship:")
        for failure in wrong_relationship
    )

    missing_terms = harness.typed_expectation_failures(
        case=category_case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="asset_discovery",
            asset_discovery={
                "relationship": "category",
                "category_description": "electric vehicle makers",
                "anchor_symbols": [],
                "asset_class_hint": None,
            },
        ),
    )
    assert any(
        failure.startswith("asset_discovery.category_description:")
        for failure in missing_terms
    )

    anchor_case = _asset_discovery_case(
        {"relationship": "peer", "anchor_symbols": ["NVDA"]}
    )
    wrong_anchor = harness.typed_expectation_failures(
        case=anchor_case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="asset_discovery",
            asset_discovery={
                "relationship": "peer",
                "category_description": None,
                "anchor_symbols": ["amd"],
                "asset_class_hint": "equity",
            },
        ),
    )
    assert any(
        failure.startswith("asset_discovery.anchor_symbols:") for failure in wrong_anchor
    )

    negative_case = _asset_discovery_case(None, semantic_turn_act="result_followup")
    discovery_leak = harness.typed_expectation_failures(
        case=negative_case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="asset_discovery",
            asset_discovery={
                "relationship": "category",
                "category_description": "anything",
                "anchor_symbols": [],
                "asset_class_hint": None,
            },
        ),
    )
    assert any(failure.startswith("semantic_turn_act:") for failure in discovery_leak)


def test_asset_discovery_expectations_compare_current_fact_requirement() -> None:
    case = _asset_discovery_case(
        {
            "relationship": "category",
            "anchor_symbols": [],
            "needs_current_facts": True,
        }
    )

    failures = harness.typed_expectation_failures(
        case=case,
        outcome=_asset_discovery_outcome(
            semantic_turn_act="asset_discovery",
            asset_discovery={
                "relationship": "category",
                "category_description": "recent IPO stocks",
                "anchor_symbols": [],
                "asset_class_hint": "equity",
                "needs_current_facts": False,
            },
        ),
    )

    assert failures == ["asset_discovery.needs_current_facts: expected True, got False"]


def test_typed_outcome_extracts_discovery_route_fields() -> None:
    case = _asset_discovery_case({"relationship": "peer", "anchor_symbols": ["NVDA"]})
    interpret_result = SimpleNamespace(
        outcome="ready_to_respond",
        patch={
            "intent": "conversation_followup",
            "semantic_turn_act": "asset_discovery",
            "asset_discovery": {
                "relationship": "peer",
                "category_description": None,
                "anchor_symbols": ["NVDA"],
                "asset_class_hint": "equity",
            },
        },
    )

    outcome = harness._typed_outcome(
        case=case,
        interpret_result=interpret_result,
        confirm_result=None,
        clarify_result=None,
    )

    assert outcome["semantic_turn_act"] == "asset_discovery"
    assert outcome["asset_discovery"]["anchor_symbols"] == ["NVDA"]
    assert outcome["capability_verdict"] == "answer_only"
    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []


def test_date_range_expectations_compare_iso_interval_and_dict_equivalently() -> None:
    dict_window = {"start": "2024-01-01", "end": "2024-12-31"}
    interval_window = "2024-01-01T00:00:00Z/2024-12-31T00:00:00Z"

    for expected_date_range, actual_date_range in (
        (dict_window, interval_window),
        (interval_window, dict_window),
    ):
        case = harness.EvalCase(
            id="date-range-normalization",
            category="messy_english",
            prompt="test Target, Walmart, and Costco in 2024",
            user_language="en",
            ui_language="en",
            expected=harness.TypedExpectations(
                intent="backtest_execution",
                capability_verdict="executable",
                date_range=expected_date_range,
            ),
        )

        failures = harness.typed_expectation_failures(
            case=case,
            outcome={
                "intent": "backtest_execution",
                "capability_verdict": "executable",
                "date_range": actual_date_range,
            },
        )

        assert failures == []


def test_measurement_outcome_keeps_requested_effective_and_reason_independent() -> None:
    requested = {"start": "2024-01-01", "end": "2024-01-05"}
    effective = {"start": "2024-01-03", "end": "2024-01-05"}
    case = harness.EvalCase(
        id="calendar-materiality",
        category="backtest_metric_correctness",
        prompt="Test AAPL from January 1 through January 5",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            date_range=requested,
            requested_date_range=requested,
            effective_date_range=effective,
            adjustment_reason="provider_coverage_adjustment",
        ),
    )
    interpret_result = SimpleNamespace(
        outcome="ready_for_confirmation",
        patch={
            "intent": "backtest_execution",
            "candidate_strategy_draft": {
                "strategy_type": "buy_and_hold",
                "asset_universe": ["AAPL"],
                "asset_class": "equity",
                "date_range": requested,
            },
        },
    )
    confirm_result = SimpleNamespace(
        outcome="await_approval",
        patch={
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": effective,
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": effective,
                    "requested_date_range": requested,
                    "coverage_preflight": {
                        "outcome": "adjusted_coverage",
                        "requested_date_range": requested,
                        "effective_date_range": effective,
                        "adjustment_reason": "provider_coverage_adjustment",
                    },
                    "benchmark_symbol": "SPY",
                },
                "validation": {"executable": True},
            }
        },
    )

    outcome = harness._typed_outcome(
        case=case,
        interpret_result=interpret_result,
        confirm_result=confirm_result,
        clarify_result=None,
    )

    assert outcome["date_range"] == requested
    assert outcome["requested_date_range"] == requested
    assert outcome["effective_date_range"] == effective
    assert outcome["adjustment_reason"] == "provider_coverage_adjustment"
    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []


def test_strategy_transition_expectations_assert_typed_rules_not_prose() -> None:
    rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    case = harness.EvalCase(
        id="issue-270-typed-rule",
        category="messy_english",
        prompt="Use a 50/200 SMA crossover with SPY as benchmark.",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            requested_strategy_template="moving_average_crossover",
            strategy_type="signal_strategy",
            entry_rule=rule,
            benchmark_symbol="SPY",
        ),
    )
    truthful = {
        "intent": "backtest_execution",
        "capability_verdict": "executable",
        "requested_strategy_template": "moving_average_crossover",
        "strategy_type": "signal_strategy",
        "entry_rule": rule,
        "benchmark_symbol": "SPY",
    }

    assert harness.typed_expectation_failures(case=case, outcome=truthful) == []
    buy_and_hold = {
        **truthful,
        "requested_strategy_template": "buy_and_hold",
        "strategy_type": "buy_and_hold",
        "entry_rule": {"type": "start_of_period"},
    }
    failures = harness.typed_expectation_failures(
        case=case,
        outcome=buy_and_hold,
    )
    assert any(item.startswith("requested_strategy_template:") for item in failures)
    assert any(item.startswith("strategy_type:") for item in failures)
    assert any(item.startswith("entry_rule:") for item in failures)


def test_modeled_cost_expectations_assert_canonical_and_launch_truth() -> None:
    expected_provenance = {
        "fee_rate": "explicit_user",
        "slippage": "explicit_user",
    }
    expected_realism = {
        "enabled": True,
        "fee_bps": 10.0,
        "slippage_bps": 5.0,
    }
    case = harness.EvalCase(
        id="issue-271-modeled-cost-preservation",
        category="action_chip_semantics",
        prompt="Add AAPL and keep my modeled costs.",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            fee_rate=0.001,
            slippage=0.0005,
            cost_provenance=expected_provenance,
            launch_execution_realism=expected_realism,
        ),
    )
    truthful = {
        "intent": "backtest_execution",
        "capability_verdict": "executable",
        "fee_rate": 0.001,
        "slippage": 0.0005,
        "cost_provenance": expected_provenance,
        "launch_execution_realism": expected_realism,
    }

    assert harness.typed_expectation_failures(case=case, outcome=truthful) == []

    failures = harness.typed_expectation_failures(
        case=case,
        outcome={
            **truthful,
            "fee_rate": None,
            "slippage": None,
            "cost_provenance": {},
            "launch_execution_realism": None,
        },
    )

    assert any(item.startswith("fee_rate:") for item in failures)
    assert any(item.startswith("slippage:") for item in failures)
    assert any(item.startswith("cost_provenance.") for item in failures)
    assert any(item.startswith("launch_execution_realism") for item in failures)


def test_issue_271_cases_are_on_the_live_measurement_surface() -> None:
    cases = {case.id: case for case in load_eval_cases()}
    establishment = cases["natural_language_establishes_modeled_costs_issue_271"]
    preservation = cases["action_chip_add_asset_preserves_modeled_costs_issue_271"]

    for case in (establishment, preservation):
        assert case.expected.fee_rate == 0.001
        assert case.expected.slippage == 0.0005
        assert case.expected.cost_provenance == {
            "fee_rate": "explicit_user",
            "slippage": "explicit_user",
        }
        assert case.expected.launch_execution_realism == {
            "enabled": True,
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
        }


def test_issue_272_cases_run_the_real_two_stage_measurement_topology(
    monkeypatch: Any,
) -> None:
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
    from argus.domain.backtesting import coverage as coverage_module
    from argus.domain.backtesting.coverage import (
        CoverageDateRange,
        PreparedMarketData,
    )

    cases = {case.id: case for case in load_eval_cases()}
    issue_272_cases = [
        cases["ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_en"],
        cases["ordinary_turn_edits_owned_confirmation_after_failed_action_issue_272_es"],
    ]
    canonical_launch = issue_272_cases[0].confirmation_payload["launch_payload"]
    canonical_coverage = canonical_launch["coverage_preflight"]
    assert all(
        case.confirmation_payload["launch_payload"]["coverage_preflight"]
        == canonical_coverage
        for case in issue_272_cases
    )

    def prepared_owned_coverage(_config: dict[str, Any]) -> PreparedMarketData:
        return PreparedMarketData(
            requested_date_range=CoverageDateRange.model_validate(
                canonical_coverage["requested_date_range"]
            ),
            effective_date_range=CoverageDateRange.model_validate(
                canonical_coverage["effective_date_range"]
            ),
            outcome=str(canonical_coverage["outcome"]),
            adjustment_reason=canonical_coverage["adjustment_reason"],
            dataset_id="issue-272-owned-confirmation-coverage",
            bars_by_symbol={},
            observations_by_symbol=dict(
                canonical_coverage.get("observations_by_symbol") or {}
            ),
        )

    class CapitalEditInterpreter:
        async def ainvoke(self, request: Any) -> StructuredInterpretation:
            snapshot = request.latest_task_snapshot
            assert snapshot is not None
            assert snapshot.active_confirmation_reference is not None
            assert snapshot.latest_backtest_result_reference is not None
            assert snapshot.latest_failed_action_reference is not None
            assert snapshot.pending_strategy_summary is not None
            edited = snapshot.pending_strategy_summary.model_copy(
                update={"capital_amount": 30000},
                deep=True,
            )
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="Change only the active setup capital.",
                candidate_strategy_draft=edited,
                semantic_turn_act="refine_current_idea",
                artifact_target="active_confirmation",
                reason_codes=["artifact_assumption_edit_planned"],
            )

    monkeypatch.setattr(
        harness,
        "OpenRouterStructuredInterpreter",
        lambda **_kwargs: CapitalEditInterpreter(),
    )
    monkeypatch.setattr(
        coverage_module,
        "prepare_market_data",
        prepared_owned_coverage,
    )

    for case in issue_272_cases:
        assert case.followup_prompt is None

        result = harness.run_eval_case(case, run_prose_judge=False)

        assert result["typed_outcome"]["stage_outcomes"] == [
            "ready_for_confirmation",
            "await_approval",
        ]
        assert result["failed_checks"] == []
        assert result["status"] == "passed"


def test_issue_339_compound_edit_materializes_complete_confirmation(
    monkeypatch: Any,
) -> None:
    from argus.agent_runtime.stages import interpret as interpret_module
    from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
    from argus.domain.backtesting import coverage as coverage_module
    from argus.domain.backtesting.coverage import (
        CoverageDateRange,
        PreparedMarketData,
    )
    from argus.domain.market_data import ResolvedAsset

    case = {case.id: case for case in load_eval_cases()}[
        "compound_benchmark_start_date_preserves_confirmation_issue_339"
    ]

    class CompoundEditInterpreter:
        async def ainvoke(self, request: Any) -> StructuredInterpretation:
            snapshot = request.latest_task_snapshot
            assert snapshot is not None
            assert snapshot.active_confirmation_reference is not None
            assert snapshot.pending_strategy_summary is not None
            edited = snapshot.pending_strategy_summary.model_copy(
                update={
                    "comparison_baseline": "QQQ",
                    "date_range": {
                        "start": "2026-04-01",
                        "end": "2026-07-30",
                    },
                    "extra_parameters": {
                        "field_provenance": {
                            "comparison_baseline": "explicit_user",
                            "date_range": "explicit_user",
                        }
                    },
                },
                deep=True,
            )
            return StructuredInterpretation(
                intent="backtest_execution",
                task_relation="continue",
                requires_clarification=False,
                user_goal_summary="Change the benchmark and start date.",
                candidate_strategy_draft=edited,
                semantic_turn_act="refine_current_idea",
                artifact_target="active_confirmation",
                reason_codes=["artifact_assumption_edit_planned"],
            )

    monkeypatch.setattr(
        harness,
        "OpenRouterStructuredInterpreter",
        lambda **_kwargs: CompoundEditInterpreter(),
    )

    def resolve_asset(symbol: str) -> ResolvedAsset:
        canonical = symbol.strip().upper()
        if canonical not in {"LOW", "HD", "QQQ"}:
            raise ValueError("unsupported_symbol")
        return ResolvedAsset(
            canonical_symbol=canonical,
            asset_class="equity",
            name=canonical,
            raw_symbol=canonical,
            provider="issue-339-test",
        )

    monkeypatch.setattr(interpret_module, "resolve_asset", resolve_asset)

    def prepared_coverage(config: dict[str, Any]) -> PreparedMarketData:
        assert config["symbols"] == ["LOW", "HD"]
        assert config["benchmark_symbol"] == "QQQ"
        expected_window = CoverageDateRange(
            start="2026-04-01",
            end="2026-07-30",
        )
        return PreparedMarketData(
            requested_date_range=expected_window,
            effective_date_range=expected_window,
            outcome="full_coverage",
            adjustment_reason=None,
            dataset_id="issue-339-full-turn-coverage",
            bars_by_symbol={},
            observations_by_symbol={"LOW": 84, "HD": 84, "QQQ": 84},
        )

    monkeypatch.setattr(
        coverage_module,
        "prepare_market_data",
        prepared_coverage,
    )

    result = harness.run_eval_case(case, run_prose_judge=False)

    assert result["failed_checks"] == []
    assert result["status"] == "passed"
    assert result["typed_outcome"]["assets"] == ["LOW", "HD"]
    assert result["typed_outcome"]["benchmark_symbol"] == "QQQ"
    assert result["typed_outcome"]["date_range"] == {
        "start": "2026-04-01",
        "end": "2026-07-30",
    }


def test_issue_271_establishment_accepts_truthful_strategy_drafting_route() -> None:
    case = {case.id: case for case in load_eval_cases()}[
        "natural_language_establishes_modeled_costs_issue_271"
    ]
    truthful = {
        "intent": "strategy_drafting",
        "capability_verdict": "executable",
        "assets": ["MSFT"],
        "asset_class": "equity",
        "strategy_type": "buy_and_hold",
        "date_range": {"start": "2023-01-03", "end": "2024-12-31"},
        "effective_date_range": {"start": "2023-01-03", "end": "2024-12-31"},
        "benchmark_symbol": "SPY",
        "capital_amount": 12000,
        "fee_rate": 0.001,
        "slippage": 0.0005,
        "cost_provenance": {
            "fee_rate": "explicit_user",
            "slippage": "explicit_user",
        },
        "launch_execution_realism": {
            "enabled": True,
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
        },
        "stage_outcomes": ["ready_for_confirmation", "await_approval"],
    }

    assert harness.typed_expectation_failures(case=case, outcome=truthful) == []


def test_issue_271_tolerant_intent_keeps_executable_contract_strict() -> None:
    case = {case.id: case for case in load_eval_cases()}[
        "natural_language_establishes_modeled_costs_issue_271"
    ]
    truthful = {
        "intent": "strategy_drafting",
        "capability_verdict": "executable",
        "assets": ["MSFT"],
        "asset_class": "equity",
        "strategy_type": "buy_and_hold",
        "date_range": {"start": "2023-01-03", "end": "2024-12-31"},
        "effective_date_range": {"start": "2023-01-03", "end": "2024-12-31"},
        "benchmark_symbol": "SPY",
        "capital_amount": 12000,
        "fee_rate": 0.001,
        "slippage": 0.0005,
        "cost_provenance": {
            "fee_rate": "explicit_user",
            "slippage": "explicit_user",
        },
        "launch_execution_realism": {
            "enabled": True,
            "fee_bps": 10.0,
            "slippage_bps": 5.0,
        },
        "stage_outcomes": ["ready_for_confirmation", "await_approval"],
    }
    mutations = {
        "missing costs": (
            {"fee_rate": None, "slippage": None},
            ("fee_rate:", "slippage:"),
        ),
        "missing provenance": (
            {"cost_provenance": {}},
            ("cost_provenance.fee_rate:", "cost_provenance.slippage:"),
        ),
        "missing launch realism": (
            {"launch_execution_realism": None},
            ("launch_execution_realism",),
        ),
        "wrong facts": (
            {
                "assets": ["AAPL"],
                "asset_class": "crypto",
                "strategy_type": "signal_strategy",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "effective_date_range": {
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                },
                "benchmark_symbol": "QQQ",
                "capital_amount": 5000,
            },
            (
                "assets:",
                "asset_class:",
                "strategy_type:",
                "date_range:",
                "effective_date_range:",
                "benchmark_symbol:",
                "capital_amount:",
            ),
        ),
        "clarification": (
            {
                "capability_verdict": "needs_clarification",
                "stage_outcomes": ["needs_clarification", "await_user_reply"],
                "clarification": {"kind": "clarification"},
            },
            ("capability_verdict:", "stage_outcomes:"),
        ),
        "unsupported verdict": (
            {"capability_verdict": "unsupported"},
            ("capability_verdict:",),
        ),
        "non-confirmation outcome": (
            {"stage_outcomes": ["ready_to_respond"]},
            ("stage_outcomes:",),
        ),
    }

    for label, (patch, expected_prefixes) in mutations.items():
        failures = harness.typed_expectation_failures(
            case=case,
            outcome={**truthful, **patch},
        )
        for prefix in expected_prefixes:
            assert any(item.startswith(prefix) for item in failures), (
                label,
                prefix,
                failures,
            )


def test_typed_outcome_projects_modeled_costs_from_confirmation() -> None:
    case = harness.EvalCase(
        id="issue-271-outcome-projection",
        category="action_chip_semantics",
        prompt="Add AAPL and keep my modeled costs.",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            fee_rate=0.001,
            slippage=0.0005,
            cost_provenance={
                "fee_rate": "explicit_user",
                "slippage": "explicit_user",
            },
            launch_execution_realism={
                "enabled": True,
                "fee_bps": 10.0,
                "slippage_bps": 5.0,
            },
        ),
    )
    interpret_result = SimpleNamespace(
        outcome="ready_for_confirmation",
        patch={"intent": "backtest_execution"},
    )
    confirm_result = SimpleNamespace(
        outcome="await_approval",
        patch={
            "confirmation_payload": {
                "strategy": {
                    "extra_parameters": {
                        "fee_rate": 0.001,
                        "slippage": 0.0005,
                        "field_provenance": {
                            "fee_rate": "explicit_user",
                            "slippage": "explicit_user",
                        },
                    }
                },
                "launch_payload": {
                    "_execution_realism": {
                        "enabled": True,
                        "fee_bps": 10.0,
                        "slippage_bps": 5.0,
                    }
                },
                "validation": {"executable": True},
            }
        },
    )

    outcome = harness._typed_outcome(
        case=case,
        interpret_result=interpret_result,
        confirm_result=confirm_result,
        clarify_result=None,
    )

    assert harness.typed_expectation_failures(case=case, outcome=outcome) == []


def test_measurement_comparisons_report_swapped_windows_and_reason_separately() -> None:
    requested = {"start": "2024-01-01", "end": "2024-01-05"}
    effective = {"start": "2024-01-03", "end": "2024-01-05"}
    case = harness.EvalCase(
        id="calendar-materiality-swapped",
        category="backtest_metric_correctness",
        prompt="Test AAPL from January 1 through January 5",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            requested_date_range=requested,
            effective_date_range=effective,
            adjustment_reason="provider_coverage_adjustment",
        ),
    )

    failures = harness.typed_expectation_failures(
        case=case,
        outcome={
            "intent": "backtest_execution",
            "capability_verdict": "executable",
            "requested_date_range": effective,
            "effective_date_range": requested,
            "adjustment_reason": "calendar_alignment",
        },
    )

    assert len(failures) == 3
    assert failures[0].startswith("requested_date_range:")
    assert failures[1].startswith("effective_date_range:")
    assert failures[2].startswith("adjustment_reason:")


def test_tolerant_intent_labels_never_loosen_final_capability_assertions() -> None:
    """A tolerant intent list absorbs model-shape routing variance only; the
    final capability truth checks stay exact for every listed label."""

    case = harness.EvalCase(
        id="tolerant-intent-contract",
        category="capability_honesty",
        prompt="If I invest $10,000 in Bitcoin, what will it be worth in ten years?",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent=(
                "unsupported_or_out_of_scope",
                "backtest_execution",
                "strategy_drafting",
            ),
            capability_verdict="unsupported",
            assets=("BTC",),
            capital_amount=10000,
            clarification={
                "kind": "unsupported_recovery",
                "reason_code": "future_performance",
            },
        ),
    )
    honest_outcome = {
        "intent": "backtest_execution",
        "capability_verdict": "unsupported",
        "assets": ["BTC"],
        "capital_amount": 10000,
        "clarification": {
            "kind": "unsupported_recovery",
            "reason_code": "future_performance",
        },
    }
    assert harness.typed_expectation_failures(case=case, outcome=honest_outcome) == []

    executable_leak = dict(honest_outcome)
    executable_leak["capability_verdict"] = "executable"
    failures = harness.typed_expectation_failures(case=case, outcome=executable_leak)
    assert any(failure.startswith("capability_verdict") for failure in failures)

    missing_recovery = dict(honest_outcome)
    missing_recovery["clarification"] = None
    failures = harness.typed_expectation_failures(case=case, outcome=missing_recovery)
    assert any(failure.startswith("clarification") for failure in failures)

    dropped_conservation = dict(honest_outcome)
    dropped_conservation["assets"] = []
    failures = harness.typed_expectation_failures(case=case, outcome=dropped_conservation)
    assert any(failure.startswith("assets") for failure in failures)

    unknown_label = dict(honest_outcome)
    unknown_label["intent"] = "conversation_followup"
    failures = harness.typed_expectation_failures(case=case, outcome=unknown_label)
    assert any(failure.startswith("intent") for failure in failures)


def test_prose_judge_cases_fail_when_assistant_text_is_missing(monkeypatch: Any) -> None:
    case = harness.EvalCase(
        id="missing-prose",
        category="messy_spanish",
        prompt="probar apple",
        user_language="es-419",
        ui_language="es-419",
        expected=harness.TypedExpectations(
            intent="backtest_execution",
            capability_verdict="executable",
            assets=("AAPL",),
            asset_class="equity",
            strategy_type="buy_and_hold",
            date_range={"start": "2024-01-01", "end": "2024-12-31"},
            benchmark_symbol="SPY",
            stage_outcomes=("ready_for_confirmation", "await_approval"),
        ),
        prose_judge_criteria=("spanish_language_integrity",),
    )
    interpret_patch = {
        "intent": "backtest_execution",
        "candidate_strategy_draft": {
            "strategy_type": "buy_and_hold",
            "asset_universe": ["AAPL"],
            "asset_class": "equity",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "comparison_baseline": "SPY",
        },
    }
    confirm_patch = {
        "confirmation_payload": {
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbols": ["AAPL"],
                "asset_class": "equity",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "benchmark_symbol": "SPY",
            },
            "validation": {"executable": True},
        }
    }

    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="ready_for_confirmation",
            patch=interpret_patch,
        ),
    )
    monkeypatch.setattr(
        harness,
        "confirm_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="await_approval",
            patch=confirm_patch,
        ),
    )
    monkeypatch.setattr(
        harness,
        "judge_prose_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("missing prose should not call the LLM judge")
        ),
    )

    result = harness.run_eval_case(case)

    assert result["status"] == "failed"
    assert result["failed_checks"] == ["prose_judge:missing_assistant_text"]
    assert result["prose_judge"]["failed_criteria"] == ["missing_assistant_text"]


def test_prose_judge_route_receipt_is_included_in_case_cost_evidence(
    monkeypatch: Any,
) -> None:
    case = harness.EvalCase(
        id="prose-judge-cost",
        category="messy_english",
        prompt="Explain this simply",
        user_language="en",
        ui_language="en",
        expected=harness.TypedExpectations(
            intent="conversation_followup",
            capability_verdict="answer_only",
        ),
        prose_judge_criteria=("plain_language",),
    )
    active_receipts: list[SimpleNamespace] | None = None

    def begin_capture() -> object:
        nonlocal active_receipts
        assert active_receipts is None
        active_receipts = []
        return object()

    def end_capture(_token: object) -> list[SimpleNamespace]:
        nonlocal active_receipts
        assert active_receipts is not None
        captured = active_receipts
        active_receipts = None
        return captured

    def record_receipt(task: str) -> None:
        assert active_receipts is not None
        active_receipts.append(
            SimpleNamespace(as_dict=lambda: {"task": task, "usage_cost_usd": 0.01})
        )

    def interpret_stage(**_kwargs: Any) -> SimpleNamespace:
        record_receipt("interpret")
        return SimpleNamespace(
            outcome="ready_to_respond",
            patch={
                "intent": "conversation_followup",
                "assistant_response": "A short, plain explanation.",
            },
        )

    def judge_prose_quality(**_kwargs: Any) -> dict[str, Any]:
        record_receipt("prose_judge")
        return {
            "pass": True,
            "failed_criteria": [],
            "notes": "",
            "rubric_version": PROSE_JUDGE_RUBRIC_VERSION,
        }

    monkeypatch.setattr(harness, "begin_openrouter_route_receipt_capture", begin_capture)
    monkeypatch.setattr(harness, "end_openrouter_route_receipt_capture", end_capture)
    monkeypatch.setattr(harness, "interpret_stage", interpret_stage)
    monkeypatch.setattr(harness, "judge_prose_quality", judge_prose_quality)

    result = harness.run_eval_case(case)

    assert [receipt["task"] for receipt in result["route_receipts"]] == [
        "interpret",
        "prose_judge",
    ]


def test_followup_clarification_runs_clarify_stage(monkeypatch: Any) -> None:
    case = harness.EvalCase(
        id="followup-clarifies",
        category="action_chip_semantics",
        prompt="",
        followup_prompt="MSFT",
        user_language="en",
        ui_language="en",
        action=harness.EvalAction(
            type="change_asset",
            label="Change asset",
            presentation="confirmation",
            payload={"confirmation_id": "c1"},
        ),
        expected=harness.TypedExpectations(
            intent="strategy_drafting",
            capability_verdict="needs_clarification",
            stage_outcomes=(
                "needs_clarification",
                "await_user_reply",
                "needs_clarification",
                "await_user_reply",
            ),
            clarification={"direct_question": "Which asset set?"},
        ),
    )
    interpret_results = iter(
        [
            SimpleNamespace(
                outcome="needs_clarification",
                patch={
                    "candidate_strategy_draft": {"asset_universe": ["AAPL", "MSFT"]},
                    "requested_field": "asset_universe",
                    "missing_required_fields": ["asset_universe"],
                    "response_intent": {"kind": "clarification"},
                },
            ),
            SimpleNamespace(
                outcome="needs_clarification",
                patch={
                    "candidate_strategy_draft": {"asset_universe": ["AAPL", "MSFT"]},
                    "requested_field": "asset_universe",
                    "missing_required_fields": ["asset_universe"],
                    "response_intent": {"kind": "clarification"},
                },
            ),
        ]
    )
    clarify_calls: list[Any] = []

    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_kwargs: next(interpret_results),
    )

    def clarify_stub(**_kwargs: Any) -> SimpleNamespace:
        clarify_calls.append(_kwargs)
        return SimpleNamespace(
            outcome="await_user_reply",
            patch={
                "assistant_response": "Which asset set?",
                "clarification": {"direct_question": "Which asset set?"},
            },
        )

    monkeypatch.setattr(harness, "clarify_stage", clarify_stub)

    result = harness.run_eval_case(case)

    assert len(clarify_calls) == 2
    assert result["status"] == "passed"
    assert result["typed_outcome"]["clarification"] == {
        "direct_question": "Which asset set?"
    }


def test_confirmation_payload_snapshot_uses_distinct_artifact_references() -> None:
    case = next(
        case
        for case in load_eval_cases()
        if case.id == "action_chip_change_asset_remove_aapl_issue_188"
    )

    assert case.snapshot is not None
    active = case.snapshot.active_confirmation_reference
    listed = case.snapshot.artifact_references[-1]
    assert active is not None
    assert listed.artifact_id == active.artifact_id
    assert listed is not active


def test_blocking_eval_results_include_failures_and_unexpected_passes() -> None:
    results = [
        {"trajectory_id": "passed", "status": "passed", "failed_checks": []},
        {
            "trajectory_id": "expected-failure",
            "status": "expected_failed",
            "failed_checks": ["artifact: missing"],
        },
        {
            "trajectory_id": "failed",
            "status": "failed",
            "failed_checks": ["sse: invalid"],
        },
        {
            "trajectory_id": "unexpected-pass",
            "status": "unexpected_pass",
            "expected_fail": {
                "issue": "#251",
                "reason": "owner acceptance is pending",
                "allowed_failures": ["effective_window:"],
            },
            "failed_checks": [],
        },
    ]

    blocking = harness.blocking_eval_results(results)

    assert [result["trajectory_id"] for result in blocking] == [
        "failed",
        "unexpected-pass",
    ]
    assert blocking[1]["status"] == "unexpected_pass"
    assert harness.expected_fail_issue_for_result(blocking[1]) == "#251"


class TestOfferedReadsWhatTheUserSaw:
    """Review #522: both offered gates were reading the wrong thing."""

    def test_recovery_options_are_read_as_a_sibling_of_payload(self) -> None:
        # typed_clarification_contract writes options beside payload, not
        # inside it, so the old lookup made recovery_option_ids_include_any
        # impossible to pass. All 60 blocks in the first live run were empty.
        clarification = {
            "kind": "unsupported_recovery",
            "payload": {"raw_value": "options straddle", "strategy": {}},
            "options": [
                {"id": "rsi_threshold"},
                {"id": "buy_and_hold"},
            ],
        }
        offered = offered_to_user(
            final_patch={"clarification": clarification},
            interpret_patch={},
            launch_payload={},
        )
        assert offered["recovery_option_ids"] == ["rsi_threshold", "buy_and_hold"]

    def test_a_reply_that_names_nothing_does_not_pass_names_unavailable(self) -> None:
        # The exact shape that shipped green: the sidecar listed four drops
        # while the reply named none of them.
        discovery = {
            "candidates": [{"symbol": "SOL"}],
            "unverified_names": ["Wiki Cat", "Venice Token", "Bitcoin"],
        }
        silent = offered_to_user(
            final_patch={"discovery": discovery},
            interpret_patch={},
            launch_payload={},
            assistant_text="Here are the trending cryptos I can help you test.",
        )
        assert silent["named_unavailable"] == []
        assert silent["dropped_not_named"] == ["Wiki Cat", "Venice Token", "Bitcoin"]

        naming = offered_to_user(
            final_patch={"discovery": discovery},
            interpret_patch={},
            launch_payload={},
            assistant_text=(
                "Wiki Cat, Venice Token and Bitcoin came back but none could be "
                "confirmed as tradable here."
            ),
        )
        assert naming["named_unavailable"] == ["Wiki Cat", "Venice Token", "Bitcoin"]
        assert naming["dropped_not_named"] == []
