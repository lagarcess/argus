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
from argus.agent_runtime.state.models import StrategySummary, TaskSnapshot, UserState


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
async def test_issue_339_provider_grounded_replacement_can_remove_current_asset(
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
        lambda *_args, **_kwargs: {"BRK.B"},
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
                EditOperation(op="replace", target="asset", symbols=["BRK.B"]),
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
            current_user_message=(
                "switch the asset to Berkshire Hathaway Class B and benchmark to QQQ"
            ),
            recent_thread_history=[],
            latest_task_snapshot=TaskSnapshot(
                pending_strategy_summary=StrategySummary(
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
            comparison_baseline="QQQ",
            field_provenance={"comparison_baseline": "explicit_user"},
        ),
    )

    assert seen_models == ["primary-model"]
    assert response is not None
    assert response.candidate_strategy_draft.asset_universe == ["BRK.B"]
    assert response.candidate_strategy_draft.comparison_baseline == "QQQ"


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
