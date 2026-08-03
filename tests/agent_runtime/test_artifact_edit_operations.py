from __future__ import annotations

import pytest
from argus.agent_runtime import artifact_edit_planner
from argus.agent_runtime.artifact_edit_planner import (
    ArtifactAssumptionEditPlan,
    EditOperation,
    apply_edit_operations,
    plan_artifact_assumption_edit,
)
from argus.agent_runtime.llm_interpreter_types import (
    LLMDateRangeIntent,
    LLMStrategyDraft,
)
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import (
    ArtifactReference,
    StrategySummary,
    TaskSnapshot,
    UserState,
)


def test_add_and_remove_in_one_turn():
    resolved = apply_edit_operations(
        [
            EditOperation(op="add", target="asset", symbols=["amzn"]),
            EditOperation(op="remove", target="asset", symbols=["tsla"]),
        ],
        current_asset_universe=["AAPL", "TSLA"],
    )
    assert resolved.asset_universe == ["AAPL", "AMZN"]
    assert resolved.asset_universe_operation == "replace"
    assert "add.asset" in resolved.applied
    assert "remove.asset" in resolved.applied


def test_compound_date_and_asset_edit_is_not_dropped():
    # The canonical failing case: "change the start date and add AMZN".
    intent = LLMDateRangeIntent(kind="calendar_year", year=2026)
    resolved = apply_edit_operations(
        [
            EditOperation(op="add", target="asset", symbols=["AMZN"]),
            EditOperation(op="set", target="date_window", date_window=intent),
        ],
        current_asset_universe=["AAPL"],
    )
    assert resolved.asset_universe == ["AAPL", "AMZN"]
    assert resolved.date_window is intent
    assert "add.asset" in resolved.applied
    assert "set.date_window" in resolved.applied
    assert resolved.unsupported == []


def test_replace_asset_universe():
    resolved = apply_edit_operations(
        [EditOperation(op="replace", target="asset", symbols=["QQQ", "SPY"])],
        current_asset_universe=["AAPL", "TSLA"],
    )
    assert resolved.asset_universe == ["QQQ", "SPY"]
    assert resolved.asset_universe_operation == "replace"


def test_benchmark_and_scalars_in_one_turn():
    resolved = apply_edit_operations(
        [
            EditOperation(op="set", target="benchmark", value="qqq"),
            EditOperation(op="set", target="capital", number=5000),
            EditOperation(op="set", target="fees", number=0.001),
            EditOperation(op="set", target="slippage", number=0.0005),
        ],
    )
    assert resolved.comparison_baseline == "QQQ"
    assert resolved.initial_capital == 5000
    assert resolved.fee_rate == 0.001
    assert resolved.slippage == 0.0005
    assert resolved.asset_universe is None  # untouched


def test_rsi_threshold_edits_are_typed_artifact_operations():
    resolved = apply_edit_operations(
        [
            EditOperation(
                op="set",
                target="indicator_entry_threshold",
                number=35,
            ),
            EditOperation(
                op="set",
                target="indicator_exit_threshold",
                number=65,
            ),
        ],
    )

    assert resolved.indicator_parameters == {
        "entry_threshold": 35.0,
        "exit_threshold": 65.0,
    }
    assert "set.indicator_entry_threshold" in resolved.applied
    assert "set.indicator_exit_threshold" in resolved.applied
    assert resolved.unsupported == []


def test_moving_average_family_edit_is_a_typed_artifact_operation():
    entry_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    resolved = apply_edit_operations(
        [
            EditOperation(
                op="replace",
                target="strategy_family",
                strategy_template="moving_average_crossover",
                entry_rule=entry_rule,
            )
        ]
    )

    assert resolved.requested_strategy_template == "moving_average_crossover"
    assert resolved.strategy_type == "signal_strategy"
    assert resolved.entry_rule == entry_rule
    assert resolved.exit_rule == {**entry_rule, "direction": "bearish"}
    assert resolved.rule_spec is not None
    assert resolved.applied == ["replace.strategy_family"]
    assert resolved.unsupported == []


def test_compound_strategy_family_and_benchmark_are_both_required_targets():
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _required_edit_targets_from_primary_draft,
    )

    crossover_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    draft = LLMStrategyDraft(
        requested_strategy_template="moving_average_crossover",
        strategy_type="signal_strategy",
        comparison_baseline="QQQ",
        entry_rule=crossover_rule,
        exit_rule={**crossover_rule, "direction": "bearish"},
        field_provenance={
            "requested_strategy_template": "explicit_user",
            "strategy_type": "explicit_user",
            "entry_rule": "explicit_user",
            "exit_rule": "explicit_user",
            "comparison_baseline": "explicit_user",
        },
    )

    targets = _required_edit_targets_from_primary_draft(
        draft,
        current_strategy=StrategySummary(
            requested_strategy_template="buy_and_hold",
            strategy_type="buy_and_hold",
            comparison_baseline="SPY",
        ),
    )

    assert targets == {"strategy_family", "benchmark"}


def test_role_separated_asset_inclusion_is_a_required_target():
    from argus.agent_runtime.interpreter.artifact_assumption_edit import (
        _required_edit_targets_from_primary_draft,
    )

    targets = _required_edit_targets_from_primary_draft(
        LLMStrategyDraft(
            asset_universe=["AAPL", "MSFT"],
            asset_universe_operation="replace",
            asset_inclusions=["AAPL", "MSFT", "GOOGL"],
            field_provenance={"asset_universe": "explicit_user"},
        ),
        current_strategy=StrategySummary(asset_universe=["AAPL", "MSFT"]),
    )

    assert targets == {"asset"}


@pytest.mark.asyncio
async def test_issue_339_legacy_strategy_fields_require_compound_planner_coverage(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter

    crossover_rule = {
        "type": "moving_average_crossover",
        "fast_indicator": "sma",
        "fast_period": 50,
        "slow_indicator": "sma",
        "slow_period": 200,
        "direction": "bullish",
    }
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        operations = [EditOperation(op="set", target="benchmark", value="QQQ")]
        if model_name == "fallback-model":
            operations.append(
                EditOperation(
                    op="replace",
                    target="strategy_family",
                    strategy_template="moving_average_crossover",
                    entry_rule=crossover_rule,
                )
            )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=operations,
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="use a 50/200 crossover and benchmark QQQ",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    requested_strategy_template="buy_and_hold",
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            strategy_type="signal_strategy",
            entry_rule=crossover_rule,
            exit_rule={**crossover_rule, "direction": "bearish"},
            comparison_baseline="QQQ",
            field_provenance={
                "strategy_type": "explicit_user",
                "entry_rule": "explicit_user",
                "exit_rule": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert (
        response.candidate_strategy_draft.requested_strategy_template
        == "moving_average_crossover"
    )
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"


@pytest.mark.parametrize(
    "entry_rule",
    [
        None,
        {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 200,
            "slow_indicator": "sma",
            "slow_period": 50,
            "direction": "bullish",
        },
        {
            "type": "moving_average_crossover",
            "fast_indicator": "sma",
            "fast_period": 50,
            "slow_indicator": "sma",
            "slow_period": 200,
            "direction": "sideways",
        },
    ],
)
def test_invalid_moving_average_family_edit_fails_closed(entry_rule):
    resolved = apply_edit_operations(
        [
            EditOperation(
                op="replace",
                target="strategy_family",
                strategy_template="moving_average_crossover",
                entry_rule=entry_rule,
            )
        ]
    )

    assert resolved.requested_strategy_template is None
    assert resolved.strategy_type is None
    assert resolved.applied == []
    assert resolved.unsupported == ["replace.strategy_family"]


def test_unsupported_operation_is_named_not_dropped():
    resolved = apply_edit_operations(
        [
            EditOperation(op="add", target="asset", symbols=["AMZN"]),
            EditOperation(op="remove", target="capital"),  # nonsensical → unsupported
        ],
        current_asset_universe=["AAPL"],
    )
    assert resolved.asset_universe == ["AAPL", "AMZN"]
    assert "add.asset" in resolved.applied
    assert "remove.capital" in resolved.unsupported


def test_clear_assets():
    resolved = apply_edit_operations(
        [EditOperation(op="clear", target="asset")],
        current_asset_universe=["AAPL", "TSLA"],
    )
    assert resolved.asset_universe == []
    assert resolved.asset_universe_operation == "replace"
    assert "clear.asset" in resolved.applied


def test_empty_operations_makes_no_changes():
    resolved = apply_edit_operations([], current_asset_universe=["AAPL"])
    assert not resolved.has_changes()
    assert resolved.asset_universe is None


def test_remove_asset_name_uses_symbol_resolver():
    resolved = apply_edit_operations(
        [EditOperation(op="remove", target="asset", symbols=["Microsoft"])],
        current_asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_symbol_resolver=lambda raw: (
            "MSFT" if raw.casefold() == "microsoft" else None
        ),
    )

    assert resolved.asset_universe == ["AAPL", "TSLA"]
    assert resolved.asset_universe_operation == "replace"
    assert resolved.applied == ["remove.asset"]
    assert resolved.unsupported == []


def test_unresolved_remove_asset_name_is_unsupported_not_silent_noop():
    resolved = apply_edit_operations(
        [EditOperation(op="remove", target="asset", symbols=["Microsoft"])],
        current_asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_symbol_resolver=lambda _raw: None,
    )

    assert resolved.asset_universe is None
    assert resolved.asset_universe_operation is None
    assert resolved.applied == []
    assert resolved.unsupported == ["remove.asset"]


def test_slash_pair_resolving_as_one_asset_is_not_split_into_legs():
    # "trade BTC/USD instead": a pair the provider resolves as a single asset
    # must not also append its legs as separate assets.
    resolved = apply_edit_operations(
        [EditOperation(op="replace", target="asset", symbols=["BTC/USD"])],
        current_asset_universe=["AAPL"],
        asset_symbol_resolver=lambda raw: raw.strip().upper(),
    )

    assert resolved.asset_universe == ["BTC/USD"]
    assert resolved.asset_universe_operation == "replace"
    assert resolved.applied == ["replace.asset"]


def test_unresolvable_slash_pair_still_splits_into_resolved_legs():
    resolved = apply_edit_operations(
        [EditOperation(op="replace", target="asset", symbols=["AAPL/MSFT"])],
        current_asset_universe=["TSLA"],
        asset_symbol_resolver=lambda raw: (None if "/" in raw else raw.strip().upper()),
    )

    assert resolved.asset_universe == ["AAPL", "MSFT"]
    assert resolved.asset_universe_operation == "replace"


@pytest.mark.asyncio
async def test_planner_keeps_company_name_asset_remove_for_later_resolution(
    monkeypatch,
):
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: [],
    )

    async def invoke_stub(*, model_name, **kwargs):
        del model_name, kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="remove",
                    target="asset",
                    symbols=["Microsoft"],
                )
            ],
            confidence=0.91,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await plan_artifact_assumption_edit(
        current_user_message="remove Microsoft",
        prior_strategy={
            "asset_universe": ["AAPL", "MSFT", "TSLA"],
            "capital_amount": 100000,
        },
        active_confirmation=None,
        preferred_model="preferred-model",
    )

    assert plan is not None
    assert [
        (operation.op, operation.target, operation.symbols)
        for operation in plan.operations
    ] == [("remove", "asset", ["Microsoft"])]


@pytest.mark.asyncio
async def test_required_benchmark_accepts_materialized_legacy_flat_plan(monkeypatch):
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: [],
    )

    async def invoke_stub(**kwargs):
        del kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            comparison_baseline="QQQ",
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    plan = await plan_artifact_assumption_edit(
        current_user_message="change the benchmark to QQQ",
        prior_strategy={
            "strategy_type": "buy_and_hold",
            "asset_universe": ["LOW", "HD"],
            "comparison_baseline": "SPY",
        },
        active_confirmation=None,
        preferred_model="legacy-model",
        required_targets={"benchmark"},
    )

    assert plan is not None
    assert plan.operations == []
    assert plan.comparison_baseline == "QQQ"


@pytest.mark.asyncio
async def test_issue_339_compound_edit_retries_partial_plan_and_applies_both_changes(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["complete-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, messages, **kwargs):
        del kwargs
        seen_models.append(model_name)
        prompt = "\n".join(message["content"] for message in messages)
        assert "Required typed targets for this turn: benchmark, date_window." in prompt
        benchmark = EditOperation(op="set", target="benchmark", value="QQQ")
        if model_name == "partial-model":
            return ArtifactAssumptionEditPlan(
                outcome="ready_to_confirm",
                operations=[benchmark],
                confidence=0.9,
            )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                benchmark,
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="endpoint_patch",
                        endpoint="start",
                        start="2026-04-01",
                    ),
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and change the beginning of the period "
                "to April 1, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="partial-model",
        primary_draft=LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range={"start": "2026-04-01"},
            date_range_intent=LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="start",
                start="2026-04-01",
            ),
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == ["partial-model", "complete-model"]
    assert response is not None
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert response.candidate_strategy_draft.date_range == {"start": "2026-04-01"}


@pytest.mark.asyncio
async def test_issue_339_flat_benchmark_leak_does_not_create_false_asset_target(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"QQQ"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        operations = [
            EditOperation(op="set", target="benchmark", value="QQQ"),
            EditOperation(
                op="set",
                target="date_window",
                date_window=LLMDateRangeIntent(
                    kind="endpoint_patch",
                    endpoint="start",
                    start="2026-04-01",
                ),
            ),
        ]
        if model_name == "primary-model":
            operations.insert(
                0,
                EditOperation(op="add", target="asset", symbols=["QQQ"]),
            )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=operations,
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and change the beginning of the period "
                "to April 1, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["LOW", "HD", "QQQ"],
            asset_universe_operation="replace",
            comparison_baseline="QQQ",
            date_range={"start": "2026-04-01", "end": "2026-07-30"},
            date_range_intent=LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="start",
                start="2026-04-01",
            ),
            field_provenance={
                "asset_universe": "explicit_user",
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert "QQQ" not in response.candidate_strategy_draft.asset_universe
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert response.candidate_strategy_draft.date_range == {"start": "2026-04-01"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("date_range_intent", "date_range"),
    [
        pytest.param(
            LLMDateRangeIntent(
                kind="explicit_range",
                start="2026-03-02",
                end="2026-07-30",
            ),
            {"start": "2026-03-02", "end": "2026-07-30"},
            id="equivalent-explicit-range",
        ),
        pytest.param(
            LLMDateRangeIntent(kind="same_as_latest_result"),
            None,
            id="same-as-latest-result",
        ),
    ],
)
async def test_issue_339_equivalent_date_intent_is_not_a_required_target(
    monkeypatch,
    date_range_intent,
    date_range,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="set", target="benchmark", value="QQQ"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    current_range = {"start": "2026-03-02", "end": "2026-07-30"}
    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="change the benchmark to QQQ and keep the same dates",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range=current_range,
                    comparison_baseline="SPY",
                ),
                latest_backtest_result_reference=ArtifactReference(
                    artifact_kind="backtest_result",
                    artifact_id="run-339",
                    artifact_status="completed",
                    metadata={
                        "config_snapshot": {
                            "date_range": current_range,
                            "resolved_parameters": {"date_range": current_range},
                        }
                    },
                ),
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range=date_range,
            date_range_intent=date_range_intent,
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("date_range_intent", "date_range", "expects_date_change"),
    [
        pytest.param(
            None,
            {"start": "2026-03-02"},
            False,
            id="flat-unchanged-start",
        ),
        pytest.param(
            None,
            {"end": "2026-07-30"},
            False,
            id="flat-unchanged-end",
        ),
        pytest.param(
            LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="start",
                start="2026-03-02",
            ),
            {"start": "2026-03-02"},
            False,
            id="patch-unchanged-start",
        ),
        pytest.param(
            LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="end",
                end="2026-07-30",
            ),
            {"end": "2026-07-30"},
            False,
            id="patch-unchanged-end",
        ),
        pytest.param(
            None,
            {"start": "2026-04-01"},
            True,
            id="flat-changed-start",
        ),
        pytest.param(
            None,
            {"end": "2026-08-01"},
            True,
            id="flat-changed-end",
        ),
        pytest.param(
            LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="start",
                start="2026-04-01",
            ),
            {"start": "2026-04-01"},
            True,
            id="patch-changed-start",
        ),
        pytest.param(
            LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="end",
                end="2026-08-01",
            ),
            {"end": "2026-08-01"},
            True,
            id="patch-changed-end",
        ),
    ],
)
async def test_issue_339_partial_date_requires_only_changed_endpoints(
    monkeypatch,
    date_range_intent,
    date_range,
    expects_date_change,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="set", target="benchmark", value="QQQ")],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and keep one date endpoint"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range=date_range,
            date_range_intent=date_range_intent,
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == (
        ["primary-model", "fallback-model"] if expects_date_change else ["primary-model"]
    )
    if expects_date_change:
        assert response is None
    else:
        assert response is not None
        assert response.candidate_strategy_draft.comparison_baseline == "QQQ"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("date_range_intent", "date_range"),
    [
        pytest.param(None, {}, id="empty-flat-range"),
        pytest.param(
            LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="start",
                start=None,
            ),
            None,
            id="unresolved-start-patch",
        ),
        pytest.param(
            LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="end",
                end=None,
            ),
            None,
            id="unresolved-end-patch",
        ),
    ],
)
async def test_issue_339_malformed_explicit_date_stays_required(
    monkeypatch,
    date_range_intent,
    date_range,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="set", target="benchmark", value="QQQ")],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and change the start date to "
                "April 1, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range=date_range,
            date_range_intent=date_range_intent,
            date_range_raw_text="change the start date to April 1, 2026",
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is None


@pytest.mark.asyncio
async def test_issue_339_unchanged_explicit_strategy_field_is_not_required(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="set", target="benchmark", value="QQQ"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="keep buy and hold and change the benchmark to QQQ",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    requested_strategy_template="buy_and_hold",
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            strategy_type="buy_and_hold",
            comparison_baseline="QQQ",
            field_provenance={
                "strategy_type": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"


@pytest.mark.asyncio
async def test_issue_339_accepts_primary_matching_delta_without_provenance(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="set", target="benchmark", value="QQQ"),
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="endpoint_patch",
                        endpoint="start",
                        start="2026-04-01",
                    ),
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and change the beginning of the period "
                "to April 1, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["LOW", "HD"],
            asset_universe_operation="replace",
            comparison_baseline="QQQ",
            date_range={"start": "2026-04-01", "end": "2026-07-30"},
            date_range_intent=LLMDateRangeIntent(
                kind="explicit_range",
                start="2026-04-01",
                end="2026-07-30",
            ),
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert response.candidate_strategy_draft.date_range == {"start": "2026-04-01"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("primary_draft_payload", "expected_capital"),
    [
        pytest.param(
            {"initial_capital": 5000},
            5000,
            id="initial-capital-without-provenance",
        ),
        pytest.param(
            {
                "total_capital": 5000,
                "field_provenance": {"total_capital": "explicit_user"},
            },
            5000,
            id="grounded-total-capital",
        ),
        pytest.param(
            {
                "initial_capital": 1000,
                "total_capital": 5000,
                "field_provenance": {"total_capital": "explicit_user"},
            },
            5000,
            id="grounded-total-capital-outranks-stale-initial-capital",
        ),
        pytest.param(
            {
                "initial_capital": 1000,
                "total_capital": 5000,
                "field_provenance": {
                    "initial_capital": "explicit_user",
                    "total_capital": "explicit_user",
                },
            },
            None,
            id="conflicting-grounded-capital-aliases-fail-closed",
        ),
    ],
)
async def test_issue_339_audits_primary_capital_delta_without_required_target(
    monkeypatch,
    primary_draft_payload,
    expected_capital,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["matching-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="set",
                    target="capital",
                    number=7000 if model_name == "wrong-model" else 5000,
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="change the starting capital to $5,000",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    capital_amount=1000,
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="wrong-model",
        primary_draft=LLMStrategyDraft(**primary_draft_payload),
    )

    assert seen_models == ["wrong-model", "matching-model"]
    if expected_capital is None:
        assert response is None
        return
    assert response is not None
    assert response.candidate_strategy_draft.initial_capital == expected_capital


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "current_assets",
        "asset_operation",
        "symbols",
        "grounded_symbols",
        "expected_assets",
        "current_user_message",
        "primary_asset_universe",
    ),
    [
        pytest.param(
            ["AAPL"],
            "replace",
            ["BRK.B"],
            {"BRK.B"},
            ["BRK.B"],
            "switch the asset to Berkshire Hathaway Class B and benchmark to QQQ",
            None,
            id="replacement-can-remove-prior-universe",
        ),
        pytest.param(
            ["AAPL", "MSFT"],
            "remove",
            ["Microsoft"],
            {"MSFT"},
            ["AAPL"],
            "remove Microsoft and change the benchmark to QQQ",
            None,
            id="removal-can-resolve-grounded-company-alias",
        ),
        pytest.param(
            ["AAPL", "MSFT"],
            "remove",
            ["Microsoft"],
            {"MSFT"},
            ["AAPL"],
            "remove Microsoft and change the benchmark to QQQ",
            ["AAPL", "MSFT"],
            id="unchanged-primary-replacement-does-not-block-removal",
        ),
    ],
)
async def test_issue_339_provider_grounded_asset_edit_can_remove_current_asset(
    monkeypatch,
    current_assets,
    asset_operation,
    symbols,
    grounded_symbols,
    expected_assets,
    current_user_message,
    primary_asset_universe,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: set(grounded_symbols),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: (
            "MSFT" if symbol.strip().casefold() == "microsoft" else symbol.strip().upper()
        ),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op=asset_operation, target="asset", symbols=symbols),
                EditOperation(op="set", target="benchmark", value="QQQ"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=current_user_message,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=current_assets,
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=primary_asset_universe or [],
            asset_universe_operation=(
                "replace" if primary_asset_universe is not None else None
            ),
            comparison_baseline="QQQ",
            field_provenance={
                "comparison_baseline": "explicit_user",
                **(
                    {"asset_universe": "explicit_user"}
                    if primary_asset_universe is not None
                    else {}
                ),
            },
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == expected_assets
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "current_assets",
        "grounded_symbols",
        "current_user_message",
        "wrong_removals",
        "wrong_additions",
        "correct_removals",
        "correct_additions",
        "expected_assets",
        "primary_draft_payload",
    ),
    [
        pytest.param(
            ["AAPL", "MSFT"],
            {"MSFT", "NVDA"},
            "remove Microsoft and add Nvidia",
            ["Microsoft", "AAPL"],
            ["Nvidia"],
            ["Microsoft"],
            ["Nvidia"],
            ["AAPL", "NVDA"],
            {},
            id="rejects-unrequested-removal",
        ),
        pytest.param(
            ["AAPL", "MSFT", "TSLA"],
            {"MSFT", "TSLA", "NVDA"},
            "remove Microsoft and Tesla, then add Nvidia",
            ["Microsoft", "Tesla"],
            ["Microsoft", "Nvidia"],
            ["Microsoft", "Tesla"],
            ["Nvidia"],
            ["AAPL", "NVDA"],
            {},
            id="rejects-readded-requested-removal",
        ),
        pytest.param(
            ["AAPL", "MSFT", "TSLA"],
            {"MSFT", "TSLA", "NVDA"},
            "remove Microsoft and Tesla, then add Nvidia",
            ["Microsoft", "Tesla"],
            ["Microsoft", "Nvidia"],
            ["Microsoft", "Tesla"],
            ["Nvidia"],
            ["AAPL", "NVDA"],
            {
                "asset_universe": ["AAPL", "NVDA"],
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
            id="rejects-readded-primary-replacement",
        ),
        pytest.param(
            ["AAPL", "MSFT"],
            {"AAPL", "NVDA"},
            "keep AAPL, remove the second one, and add Nvidia",
            ["AAPL"],
            ["Nvidia"],
            ["MSFT"],
            ["Nvidia"],
            ["AAPL", "NVDA"],
            {
                "asset_universe": ["AAPL", "NVDA"],
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
            id="accepts-primary-resolved-ordinal-removal",
        ),
        pytest.param(
            ["AAPL", "MSFT", "TSLA"],
            {"MSFT", "GOOGL"},
            "add GOOGL and remove Microsoft",
            ["AAPL"],
            ["GOOGL"],
            ["Microsoft"],
            ["GOOGL"],
            ["AAPL", "TSLA", "GOOGL"],
            {
                "asset_universe": ["AAPL", "TSLA"],
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
            id="repairs-primary-missing-grounded-addition",
        ),
        pytest.param(
            ["AAPL", "MSFT"],
            {"AAPL", "NVDA", "GOOGL"},
            "keep AAPL, remove the second one, and add NVDA and GOOGL",
            ["AAPL"],
            ["NVDA", "GOOGL"],
            ["MSFT"],
            ["NVDA", "GOOGL"],
            ["AAPL", "NVDA", "GOOGL"],
            {
                "asset_universe": ["AAPL", "NVDA"],
                "asset_universe_operation": "replace",
                "field_provenance": {"asset_universe": "explicit_user"},
            },
            id="preserves-primary-retention-with-missing-grounded-addition",
        ),
    ],
)
async def test_issue_339_retries_mixed_asset_edit_with_unrequested_removal(
    monkeypatch,
    current_assets,
    grounded_symbols,
    current_user_message,
    wrong_removals,
    wrong_additions,
    correct_removals,
    correct_additions,
    expected_assets,
    primary_draft_payload,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["correct-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: set(grounded_symbols),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: {
            "microsoft": "MSFT",
            "nvidia": "NVDA",
            "tesla": "TSLA",
        }.get(symbol.strip().casefold(), symbol.strip().upper()),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        removals = wrong_removals if model_name == "wrong-model" else correct_removals
        additions = wrong_additions if model_name == "wrong-model" else correct_additions
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="remove", target="asset", symbols=removals),
                EditOperation(op="add", target="asset", symbols=additions),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=current_user_message,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=current_assets,
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="wrong-model",
        primary_draft=LLMStrategyDraft(**primary_draft_payload),
    )

    assert seen_models == ["wrong-model", "correct-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == expected_assets


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "grounded_symbols",
        "current_user_message",
        "primary_assets",
        "wrong_assets",
        "correct_assets",
        "expected_models",
        "asset_evidence_span",
        "asset_inclusions",
    ),
    [
        pytest.param(
            {"AAPL", "NVDA", "GOOGL"},
            "replace the basket with AAPL, NVDA, and GOOGL",
            ["AAPL", "NVDA"],
            ["AAPL", "NVDA", "GOOGL"],
            ["AAPL", "NVDA", "GOOGL"],
            ["primary-model"],
            "AAPL, NVDA, and GOOGL",
            ["AAPL", "NVDA", "GOOGL"],
            id="augments-material-primary-replacement",
        ),
        pytest.param(
            {"NVDA", "GOOGL"},
            "replace the basket with NVDA and GOOGL",
            ["AAPL", "MSFT"],
            ["AAPL", "NVDA", "GOOGL"],
            ["NVDA", "GOOGL"],
            ["primary-model", "fallback-model"],
            None,
            [],
            id="rejects-ungrounded-retention-from-unchanged-carrier",
        ),
        pytest.param(
            {"AAPL"},
            "replace the basket with AAPL",
            ["AAPL", "MSFT"],
            ["AAPL"],
            ["AAPL"],
            ["primary-model"],
            None,
            [],
            id="accepts-grounded-subset-only-replacement",
        ),
        pytest.param(
            {"NVDA", "GOOGL"},
            "replace the basket with NVDA and GOOGL",
            ["AAPL", "MSFT"],
            ["NVDA"],
            ["NVDA", "GOOGL"],
            ["primary-model", "fallback-model"],
            None,
            [],
            id="rejects-truncated-grounded-replacement",
        ),
    ],
)
async def test_issue_339_grounded_replace_augments_primary_without_changing_retained_assets(
    monkeypatch,
    grounded_symbols,
    current_user_message,
    primary_assets,
    wrong_assets,
    correct_assets,
    expected_models,
    asset_evidence_span,
    asset_inclusions,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: set(grounded_symbols),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        assets = wrong_assets if model_name == "primary-model" else correct_assets
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="replace",
                    target="asset",
                    symbols=assets,
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=current_user_message,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL", "MSFT"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=primary_assets,
            asset_universe_operation="replace",
            field_provenance={"asset_universe": "explicit_user"},
            evidence_spans=(
                {"asset_universe": asset_evidence_span}
                if asset_evidence_span is not None
                else {}
            ),
            asset_inclusions=asset_inclusions,
        ),
    )

    assert seen_models == expected_models
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == correct_assets


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrong_assets",
    [
        pytest.param(
            ["AAPL", "NVDA", "GOOGL"],
            id="ungrounded-retained-asset",
        ),
        pytest.param(["NVDA"], id="truncated-grounded-replacement"),
    ],
)
async def test_issue_339_clear_then_add_retries_invalid_final_universe(
    monkeypatch,
    wrong_assets,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"NVDA", "GOOGL"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        assets = wrong_assets if model_name == "primary-model" else ["NVDA", "GOOGL"]
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="clear", target="asset"),
                EditOperation(op="add", target="asset", symbols=assets),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace the basket with NVDA and GOOGL",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL", "MSFT"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["AAPL", "MSFT"],
            asset_universe_operation="replace",
            field_provenance={"asset_universe": "explicit_user"},
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["NVDA", "GOOGL"]


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_shape", ["replace", "clear_add"])
async def test_issue_339_primary_asset_exclusions_are_not_reintroduced(
    monkeypatch,
    plan_shape,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda message, **_kwargs: (
            {"MSFT"} if message == "MSFT" else {"AAPL", "MSFT", "NVDA"}
        ),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        assets = ["MSFT", "NVDA"] if model_name == "primary-model" else ["MSFT"]
        operations = (
            [EditOperation(op="replace", target="asset", symbols=assets)]
            if plan_shape == "replace"
            else [
                EditOperation(op="clear", target="asset"),
                EditOperation(op="add", target="asset", symbols=assets),
            ]
        )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=operations,
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace AAPL with MSFT, not NVDA",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["MSFT"],
            asset_universe_operation="replace",
            field_provenance={"asset_universe": "explicit_user"},
            evidence_spans={"asset_universe": "replace AAPL with MSFT, not NVDA"},
            asset_inclusions=["MSFT"],
            asset_exclusions=["NVDA"],
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["MSFT"]


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_shape", ["remove", "replace", "clear_add"])
async def test_issue_339_typed_exclusion_can_become_the_explicit_benchmark(
    monkeypatch,
    plan_shape,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"MSFT"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        asset_operations = {
            "remove": [
                EditOperation(op="remove", target="asset", symbols=["MSFT"]),
            ],
            "replace": [
                EditOperation(op="replace", target="asset", symbols=["AAPL"]),
            ],
            "clear_add": [
                EditOperation(op="clear", target="asset"),
                EditOperation(op="add", target="asset", symbols=["AAPL"]),
            ],
        }
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                *asset_operations[plan_shape],
                EditOperation(op="set", target="benchmark", value="MSFT"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="remove MSFT and use MSFT as benchmark",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL", "MSFT"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_exclusions=["MSFT"],
            comparison_baseline="MSFT",
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.candidate_strategy_draft.comparison_baseline == "MSFT"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation_order", "grounded_symbols"),
    [
        pytest.param(
            "remove_then_replace",
            {"MSFT", "NVDA"},
            id="remove-then-replace",
        ),
        pytest.param(
            "remove_then_clear_add",
            {"MSFT", "NVDA"},
            id="remove-then-clear-add",
        ),
        pytest.param(
            "replace_then_remove",
            {"NVDA"},
            id="replace-then-remove",
        ),
        pytest.param(
            "clear_add_then_remove",
            {"NVDA"},
            id="clear-add-then-remove",
        ),
    ],
)
async def test_issue_339_replacement_boundary_orders_asset_removals(
    monkeypatch,
    operation_order,
    grounded_symbols,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: set(grounded_symbols),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        operations_by_order = {
            "remove_then_replace": [
                EditOperation(op="remove", target="asset", symbols=["MSFT"]),
                EditOperation(op="replace", target="asset", symbols=["NVDA"]),
            ],
            "remove_then_clear_add": [
                EditOperation(op="remove", target="asset", symbols=["MSFT"]),
                EditOperation(op="clear", target="asset"),
                EditOperation(op="add", target="asset", symbols=["NVDA"]),
            ],
            "replace_then_remove": [
                EditOperation(
                    op="replace",
                    target="asset",
                    symbols=["AAPL", "NVDA"],
                ),
                EditOperation(op="remove", target="asset", symbols=["AAPL"]),
            ],
            "clear_add_then_remove": [
                EditOperation(op="clear", target="asset"),
                EditOperation(
                    op="add",
                    target="asset",
                    symbols=["AAPL", "NVDA"],
                ),
                EditOperation(op="remove", target="asset", symbols=["AAPL"]),
            ],
        }
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=operations_by_order[operation_order],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="remove MSFT, then replace the basket with NVDA",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL", "MSFT"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["NVDA"],
            asset_universe_operation="replace",
            field_provenance={"asset_universe": "explicit_user"},
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["NVDA"]


@pytest.mark.asyncio
async def test_issue_339_replacement_asset_can_match_current_benchmark(monkeypatch):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"SPY"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="replace", target="asset", symbols=["SPY"]),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace the basket with SPY",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["AAPL"],
            asset_universe_operation="replace",
            comparison_baseline="SPY",
            field_provenance={
                "asset_universe": "explicit_user",
                "comparison_baseline": "carried_forward",
            },
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["SPY"]


@pytest.mark.asyncio
@pytest.mark.parametrize("plan_shape", ["replace", "clear_add"])
async def test_issue_339_typed_asset_inclusion_can_share_explicit_benchmark_role(
    monkeypatch,
    plan_shape,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"AAPL", "MSFT", "SPY"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        assets = ["MSFT", "SPY"] if model_name == "primary-model" else ["MSFT"]
        asset_operations = (
            [EditOperation(op="replace", target="asset", symbols=assets)]
            if plan_shape == "replace"
            else [
                EditOperation(op="clear", target="asset"),
                EditOperation(op="add", target="asset", symbols=assets),
            ]
        )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                *asset_operations,
                EditOperation(op="set", target="benchmark", value="SPY"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=("replace with MSFT and SPY, and use SPY as benchmark"),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="QQQ",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["MSFT"],
            asset_universe_operation="replace",
            asset_inclusions=["MSFT", "SPY"],
            comparison_baseline="SPY",
            field_provenance={
                "asset_universe": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert set(response.candidate_strategy_draft.asset_universe) == {"MSFT", "SPY"}
    assert response.candidate_strategy_draft.comparison_baseline == "SPY"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "asset_inclusions",
    [
        pytest.param(["AAPL"], id="typed-role"),
        pytest.param([], id="legacy-flat"),
    ],
)
async def test_issue_339_primary_replacement_rejects_flat_benchmark_leak(
    monkeypatch,
    asset_inclusions,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"AAPL", "SPY"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        assets = ["AAPL", "SPY"] if model_name == "primary-model" else ["AAPL"]
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="replace", target="asset", symbols=assets),
                EditOperation(op="set", target="benchmark", value="SPY"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace the basket with AAPL and use SPY as benchmark",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    comparison_baseline="QQQ",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["AAPL", "SPY"],
            asset_universe_operation="replace",
            asset_inclusions=asset_inclusions,
            comparison_baseline="SPY",
            field_provenance={
                "asset_universe": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.candidate_strategy_draft.comparison_baseline == "SPY"


@pytest.mark.asyncio
async def test_issue_339_typed_append_rejects_replacement_that_drops_current_assets(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"SPY"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        asset_operation = EditOperation(
            op="replace" if model_name == "primary-model" else "add",
            target="asset",
            symbols=["SPY"],
        )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                asset_operation,
                EditOperation(op="set", target="benchmark", value="SPY"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="add SPY and use SPY as benchmark",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="QQQ",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["AAPL"],
            asset_universe_operation="append",
            asset_inclusions=["SPY"],
            comparison_baseline="SPY",
            field_provenance={
                "asset_universe": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert set(response.candidate_strategy_draft.asset_universe) == {"AAPL", "SPY"}
    assert response.candidate_strategy_draft.comparison_baseline == "SPY"


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement_shape", ["replace", "clear_add"])
async def test_issue_339_typed_replacement_does_not_preserve_current_assets(
    monkeypatch,
    replacement_shape,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"SPY"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        if model_name == "primary-model":
            asset_operations = [
                EditOperation(op="add", target="asset", symbols=["SPY"]),
            ]
        elif replacement_shape == "replace":
            asset_operations = [
                EditOperation(op="replace", target="asset", symbols=["SPY"]),
            ]
        else:
            asset_operations = [
                EditOperation(op="clear", target="asset"),
                EditOperation(op="add", target="asset", symbols=["SPY"]),
            ]
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                *asset_operations,
                EditOperation(op="set", target="benchmark", value="SPY"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace the basket with SPY and use SPY as benchmark",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="QQQ",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe_operation="replace",
            asset_inclusions=["SPY"],
            comparison_baseline="SPY",
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["SPY"]
    assert response.candidate_strategy_draft.comparison_baseline == "SPY"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_user_message", "grounded_symbols", "wrong_extra_asset"),
    [
        pytest.param(
            "replace the basket with AAPL and change the benchmark to SPY",
            {"AAPL", "SPY"},
            "SPY",
            id="requested-benchmark",
        ),
        pytest.param(
            "replace the basket with AAPL and change the benchmark from QQQ to SPY",
            {"AAPL", "QQQ", "SPY"},
            "QQQ",
            id="prior-benchmark",
        ),
    ],
)
async def test_issue_339_explicit_benchmark_is_not_added_to_traded_assets(
    monkeypatch,
    current_user_message,
    grounded_symbols,
    wrong_extra_asset,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["fallback-model"],
    )
    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: set(grounded_symbols),
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        assets = (
            ["AAPL", wrong_extra_asset] if model_name == "primary-model" else ["AAPL"]
        )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="replace", target="asset", symbols=assets),
                EditOperation(op="set", target="benchmark", value="SPY"),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=current_user_message,
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["MSFT"],
                    asset_class="equity",
                    comparison_baseline="QQQ",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["AAPL"],
            asset_universe_operation="replace",
            comparison_baseline="SPY",
            field_provenance={
                "asset_universe": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == ["primary-model", "fallback-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["AAPL"]
    assert response.candidate_strategy_draft.comparison_baseline == "SPY"


@pytest.mark.asyncio
async def test_issue_339_compound_edit_retries_date_operation_that_cannot_materialize(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["complete-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        benchmark = EditOperation(op="set", target="benchmark", value="QQQ")
        date_window = LLMDateRangeIntent(
            kind="endpoint_patch",
            endpoint="start",
            start=(None if model_name == "malformed-model" else "2026-04-01"),
        )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                benchmark,
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=date_window,
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and change the beginning of the period "
                "to April 1, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="malformed-model",
        primary_draft=LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range={"start": "2026-04-01"},
            date_range_intent=LLMDateRangeIntent(
                kind="endpoint_patch",
                endpoint="start",
                start="2026-04-01",
            ),
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == ["malformed-model", "complete-model"]
    assert response is not None
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert response.candidate_strategy_draft.date_range == {"start": "2026-04-01"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_model",
    ["noop-model", "extra-end-model"],
)
async def test_issue_339_compound_edit_retries_wrong_or_extra_values(
    monkeypatch,
    invalid_model,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["complete-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        is_noop = model_name == "noop-model"
        has_extra_end = model_name == "extra-end-model"
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="set",
                    target="benchmark",
                    value="SPY" if is_noop else "QQQ",
                ),
                EditOperation(
                    op="set",
                    target="date_window",
                    date_window=LLMDateRangeIntent(
                        kind="explicit_range" if has_extra_end else "endpoint_patch",
                        endpoint=None if has_extra_end else "start",
                        start="2026-03-02" if is_noop else "2026-04-01",
                        end="2026-06-30" if has_extra_end else None,
                    ),
                ),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "change the benchmark to QQQ and change the beginning of the period "
                "to April 1, 2026"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["LOW", "HD"],
                    asset_class="equity",
                    date_range={"start": "2026-03-02", "end": "2026-07-30"},
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model=invalid_model,
        primary_draft=LLMStrategyDraft(
            comparison_baseline="QQQ",
            date_range={"start": "2026-04-01", "end": "2026-07-30"},
            date_range_intent=LLMDateRangeIntent(
                kind="explicit_range",
                start="2026-04-01",
                end="2026-07-30",
            ),
            field_provenance={
                "comparison_baseline": "explicit_user",
                "date_range": "explicit_user",
            },
        ),
    )

    assert seen_models == [invalid_model, "complete-model"]
    assert response is not None
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"
    assert response.candidate_strategy_draft.date_range == {"start": "2026-04-01"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_model",
    [
        "invented-capital-model",
        "invented-dca-capital-model",
        "invented-asset-model",
        "wrong-asset-model",
        "wrong-asset-missing-operation-model",
        "append-instead-of-replace-model",
    ],
)
async def test_issue_339_retries_plan_with_ungrounded_materialized_mutation(
    monkeypatch,
    invalid_model,
):
    from argus.agent_runtime import llm_interpreter

    is_asset_request = invalid_model in {
        "wrong-asset-model",
        "wrong-asset-missing-operation-model",
        "append-instead-of-replace-model",
    }
    is_dca_request = invalid_model == "invented-dca-capital-model"
    fallback_model = "requested-asset-model" if is_asset_request else "complete-model"
    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: [fallback_model],
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        if is_asset_request:
            symbol = (
                "TSLA"
                if model_name == invalid_model
                and invalid_model != "append-instead-of-replace-model"
                else "MSFT"
            )
            return ArtifactAssumptionEditPlan(
                outcome="ready_to_confirm",
                operations=[
                    EditOperation(
                        op=(
                            "add"
                            if model_name == invalid_model
                            and invalid_model == "append-instead-of-replace-model"
                            else "replace"
                        ),
                        target="asset",
                        symbols=[symbol],
                    ),
                ],
                confidence=0.9,
            )
        operations = [
            EditOperation(op="set", target="benchmark", value="QQQ"),
        ]
        if model_name in {"invented-capital-model", "invented-dca-capital-model"}:
            operations.append(
                EditOperation(
                    op="set",
                    target="capital",
                    number=100 if is_dca_request else 5000,
                ),
            )
        elif model_name == "invented-asset-model":
            operations.append(
                EditOperation(op="clear", target="asset"),
            )
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=operations,
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message=(
                "replace AAPL with MSFT"
                if is_asset_request
                else "change AAPL's benchmark to QQQ"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type=(
                        "dca_accumulation" if is_dca_request else "buy_and_hold"
                    ),
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    cadence="monthly" if is_dca_request else None,
                    capital_amount=100 if is_dca_request else 1000,
                    comparison_baseline="SPY",
                    extra_parameters=(
                        {"recurring_contribution": 100} if is_dca_request else {}
                    ),
                )
            ),
            selected_thread_metadata={
                "requested_field": (
                    "asset_universe" if is_asset_request else "assumption"
                )
            },
            user=UserState(user_id="u-339"),
        ),
        preferred_model=invalid_model,
        primary_draft=(
            LLMStrategyDraft(
                asset_universe=["MSFT"],
                asset_universe_operation=(
                    None
                    if invalid_model == "wrong-asset-missing-operation-model"
                    else "replace"
                ),
                field_provenance={"asset_universe": "explicit_user"},
            )
            if is_asset_request
            else LLMStrategyDraft(
                comparison_baseline="QQQ",
                field_provenance={"comparison_baseline": "explicit_user"},
            )
        ),
    )

    assert seen_models == [invalid_model, fallback_model]
    assert response is not None
    if is_asset_request:
        assert response.candidate_strategy_draft.asset_universe == ["MSFT"]
    else:
        assert response.candidate_strategy_draft.comparison_baseline == "QQQ"
        assert response.candidate_strategy_draft.initial_capital is None


@pytest.mark.asyncio
async def test_issue_339_primary_replacement_grounds_card_resolved_exclusion(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"AAPL", "NVDA"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )

    async def invoke_stub(**kwargs):
        del kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="replace",
                    target="asset",
                    symbols=["AAPL", "NVDA"],
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="keep AAPL, remove the second one, and add NVDA",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL", "MSFT"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["AAPL", "NVDA"],
            asset_universe_operation="replace",
            asset_exclusions=["MSFT"],
            field_provenance={"asset_universe": "explicit_user"},
        ),
    )

    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["AAPL", "NVDA"]


@pytest.mark.asyncio
async def test_issue_339_typed_inclusion_uses_planner_replacement_boundary(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"AAPL", "MSFT"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )

    async def invoke_stub(**kwargs):
        del kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="replace", target="asset", symbols=["MSFT"]),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace AAPL with MSFT",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_inclusions=["MSFT"],
            field_provenance={"asset_universe": "explicit_user"},
        ),
    )

    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["MSFT"]


@pytest.mark.asyncio
async def test_issue_339_planner_steps_aside_for_explicit_position_size_edit(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter

    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[EditOperation(op="set", target="benchmark", value="QQQ")],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="set position size to 50% and benchmark QQQ",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                    sizing_mode="position_size",
                    position_size=0.25,
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            sizing_mode="position_size",
            position_size=0.5,
            comparison_baseline="QQQ",
            field_provenance={
                "position_size": "explicit_user",
                "comparison_baseline": "explicit_user",
            },
        ),
    )

    assert seen_models == []
    assert response is None


@pytest.mark.asyncio
async def test_issue_339_typed_roles_use_planner_replacement_boundary(
    monkeypatch,
):
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.interpreter import artifact_assumption_edit

    monkeypatch.setattr(
        artifact_assumption_edit,
        "_grounded_asset_symbols_from_message",
        lambda *_args, **_kwargs: {"AAPL", "MSFT", "TSLA"},
    )
    monkeypatch.setattr(
        llm_interpreter,
        "_asset_edit_symbol_resolver",
        lambda _resolve_asset_candidate: lambda symbol: symbol.strip().upper(),
    )

    async def invoke_stub(**kwargs):
        del kwargs
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(op="replace", target="asset", symbols=["MSFT"]),
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="replace AAPL with MSFT, not TSLA",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type="buy_and_hold",
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    comparison_baseline="SPY",
                )
            ),
            selected_thread_metadata={"requested_field": "asset_universe"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="primary-model",
        primary_draft=LLMStrategyDraft(
            asset_universe=["MSFT"],
            asset_inclusions=["MSFT"],
            asset_exclusions=["TSLA"],
            field_provenance={"asset_universe": "explicit_user"},
        ),
    )

    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["MSFT"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_strategy_type", "current_capital", "extra_parameters"),
    [
        pytest.param(
            "dca_accumulation",
            100,
            {"recurring_contribution": 100},
            id="active-dca",
        ),
        pytest.param(
            "buy_and_hold",
            200,
            {},
            id="active-buy-and-hold",
        ),
    ],
)
async def test_issue_339_recurring_capital_respects_role_and_artifact_family(
    monkeypatch,
    current_strategy_type,
    current_capital,
    extra_parameters,
):
    from argus.agent_runtime import llm_interpreter

    monkeypatch.setattr(
        artifact_edit_planner,
        "openrouter_structured_model_candidates",
        lambda: ["recurring-model"],
    )
    seen_models: list[str] = []

    async def invoke_stub(*, model_name, **kwargs):
        del kwargs
        seen_models.append(model_name)
        return ArtifactAssumptionEditPlan(
            outcome="ready_to_confirm",
            operations=[
                EditOperation(
                    op="set",
                    target=(
                        "capital"
                        if model_name == "starting-capital-model"
                        else "recurring_contribution"
                    ),
                    number=200,
                )
            ],
            confidence=0.9,
        )

    monkeypatch.setattr(
        artifact_edit_planner,
        "invoke_openrouter_json_schema",
        invoke_stub,
    )

    response = await llm_interpreter._plan_pending_artifact_assumption_edit(
        request=InterpretationRequest(
            current_user_message="change my monthly contribution to $200",
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
                    strategy_type=current_strategy_type,
                    asset_universe=["AAPL"],
                    asset_class="equity",
                    cadence="monthly",
                    capital_amount=current_capital,
                    comparison_baseline="SPY",
                    extra_parameters=extra_parameters,
                )
            ),
            selected_thread_metadata={"requested_field": "assumption"},
            user=UserState(user_id="u-339"),
        ),
        preferred_model="starting-capital-model",
        primary_draft=LLMStrategyDraft(
            capital_amount=200,
            field_provenance={"capital_amount": "recurring_contribution"},
        ),
    )

    assert seen_models == ["starting-capital-model", "recurring-model"]
    if current_strategy_type != "dca_accumulation":
        assert response is None
        return
    assert response is not None
    assert response.candidate_strategy_draft.initial_capital is None
    assert response.candidate_strategy_draft.recurring_contribution == 200
