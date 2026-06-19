from __future__ import annotations

import pytest
from argus.agent_runtime.artifacts.continuity import (
    apply_patch_to_anchor,
    patched_draft_from_candidate,
    resolve_artifact_anchor,
)
from argus.agent_runtime.artifacts.drafts import (
    draft_from_confirmation_payload,
    draft_from_failed_launch_payload,
    draft_from_result_metadata,
)
from argus.agent_runtime.artifacts.lifecycle import (
    RetryLifecycleDecision,
    retry_lifecycle_after_artifact_event,
)
from argus.agent_runtime.artifacts.strategy_edits import (
    ArtifactPatch,
    apply_artifact_patch,
)
from argus.agent_runtime.stages.interpret_actions import (
    structured_action_stage_result_if_applicable,
)
from argus.agent_runtime.state.models import (
    ArtifactReference,
    RunState,
    StrategySummary,
    TaskSnapshot,
)


def test_result_draft_preserves_dca_money_cadence_timeframe_and_benchmark() -> None:
    draft = draft_from_result_metadata(
        {
            "asset_class": "equity",
            "symbols": ["AAPL", "GOOG"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "dca_accumulation",
                "symbols": ["AAPL", "GOOG"],
                "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                "resolved_strategy": {
                    "strategy_type": "dca_accumulation",
                    "strategy_thesis": "Buy AAPL and GOOG every month.",
                    "asset_universe": ["AAPL", "GOOG"],
                    "asset_class": "equity",
                    "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                    "capital_amount": 200,
                    "cadence": "monthly",
                    "comparison_baseline": "SPY",
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "capital_amount": 200,
                    "recurring_contribution": 200,
                    "cadence": "monthly",
                    "benchmark_symbol": "SPY",
                },
            },
        }
    )

    assert draft.strategy_type == "dca_accumulation"
    assert draft.asset_universe == ["AAPL", "GOOG"]
    assert draft.asset_class == "equity"
    assert draft.date_range == {"start": "2021-01-01", "end": "2024-01-31"}
    assert draft.capital_amount == 200
    assert draft.cadence == "monthly"
    assert draft.timeframe == "1D"
    assert draft.comparison_baseline == "SPY"


def test_confirmation_edit_action_carries_product_language_to_response_intent() -> None:
    state = RunState.new(
        current_user_message="Cambiar fechas",
        recent_thread_history=[],
        action_context={
            "type": "change_dates",
            "label": "Cambiar fechas",
            "presentation": "confirmation",
            "payload": {"confirmation_id": "confirmation-1"},
        },
    )
    pending = StrategySummary(
        strategy_type="buy_and_hold",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2025-06-14", "end": "2026-06-12"},
        capital_amount=100000,
    )

    result = structured_action_stage_result_if_applicable(
        state=state,
        snapshot=TaskSnapshot(pending_strategy_summary=pending),
        selected_thread_metadata={},
        language="es-419",
    )

    assert result is not None
    assert result.outcome == "needs_clarification"
    assert result.stage_patch["response_intent"]["semantic_needs"] == ["period"]
    assert result.stage_patch["response_intent"]["facts"]["language"] == "es-419"


def test_result_draft_preserves_buy_hold_defaults_from_config_snapshot() -> None:
    draft = draft_from_result_metadata(
        {
            "asset_class": "crypto",
            "symbols": ["btc"],
            "benchmark_symbol": "BTC",
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["btc"],
                "date_range": {"start": "2023-01-01", "end": "2023-12-31"},
                "resolved_strategy": {},
                "resolved_parameters": {
                    "timeframe": "1D",
                    "capital_amount": 500,
                    "benchmark_symbol": "BTC",
                },
            },
        }
    )

    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["BTC"]
    assert draft.asset_class == "crypto"
    assert draft.date_range == {"start": "2023-01-01", "end": "2023-12-31"}
    assert draft.capital_amount == 500
    assert draft.timeframe == "1D"
    assert draft.comparison_baseline == "BTC"


def test_result_draft_preserves_position_sizing_from_config_snapshot() -> None:
    draft = draft_from_result_metadata(
        {
            "asset_class": "equity",
            "symbols": ["NVDA"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "buy_and_hold",
                "symbols": ["NVDA"],
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "resolved_strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["NVDA"],
                    "asset_class": "equity",
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "sizing_mode": "position_size",
                    "position_size": 10,
                    "benchmark_symbol": "SPY",
                },
            },
        }
    )

    assert draft.sizing_mode == "position_size"
    assert draft.position_size == 10


def test_confirmation_draft_prefers_visible_strategy_and_fills_launch_defaults() -> None:
    draft = draft_from_confirmation_payload(
        {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "strategy_thesis": "Buy and hold NVDA.",
                "asset_universe": ["NVDA"],
                "asset_class": "equity",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "comparison_baseline": "QQQ",
            },
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbol": "NVDA",
                "symbols": ["NVDA"],
                "timeframe": "1D",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "sizing_mode": "capital_amount",
                "capital_amount": 500,
                "benchmark_symbol": "QQQ",
            },
            "validation": {"executable": True},
        }
    )

    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["NVDA"]
    assert draft.asset_class == "equity"
    assert draft.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert draft.capital_amount == 500
    assert draft.timeframe == "1D"
    assert draft.comparison_baseline == "QQQ"


def test_confirmation_draft_ignores_launch_fields_outside_strategy_contract() -> None:
    draft = draft_from_confirmation_payload(
        {
            "strategy": {
                "strategy_type": "rsi_threshold",
                "strategy_thesis": "Test TSLA with RSI.",
                "asset_universe": ["TSLA"],
                "asset_class": "equity",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "entry_logic": "Buy when RSI drops below 30",
                "exit_logic": "Sell when RSI rises above 55",
            },
            "launch_payload": {
                "strategy_type": "rsi_threshold",
                "symbols": ["TSLA"],
                "timeframe": "1D",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                "entry_rule": "rsi_below",
                "exit_rule": "rsi_above",
                "benchmark_symbol": "SPY",
            },
        }
    )

    assert draft.strategy_type == "rsi_threshold"
    assert draft.asset_universe == ["TSLA"]
    assert draft.entry_logic == "Buy when RSI drops below 30"
    assert draft.exit_logic == "Sell when RSI rises above 55"
    assert draft.entry_rule is None
    assert draft.exit_rule is None
    assert draft.timeframe == "1D"
    assert draft.comparison_baseline == "SPY"


def test_failed_action_draft_preserves_launch_payload_fields() -> None:
    draft = draft_from_failed_launch_payload(
        {
            "strategy_type": "buy_and_hold",
            "symbols": ["msft"],
            "asset_class": "equity",
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "timeframe": "1D",
            "capital_amount": 750,
            "benchmark_symbol": "SPY",
        }
    )

    assert draft.strategy_type == "buy_and_hold"
    assert draft.asset_universe == ["MSFT"]
    assert draft.asset_class == "equity"
    assert draft.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert draft.timeframe == "1D"
    assert draft.capital_amount == 750
    assert draft.comparison_baseline == "SPY"


def test_date_patch_preserves_canonical_dca_fields() -> None:
    base = StrategySummary(
        strategy_type="dca_accumulation",
        strategy_thesis="Buy AAPL and GOOG monthly.",
        asset_universe=["AAPL", "GOOG"],
        asset_class="equity",
        date_range={"start": "2021-01-01", "end": "2024-01-31"},
        capital_amount=200,
        cadence="monthly",
        timeframe="1D",
        comparison_baseline="SPY",
    )

    merged = apply_artifact_patch(
        base,
        ArtifactPatch(
            source="user_patch",
            date_range={"start": "2019-10-01", "end": "2025-10-31"},
        ),
    )

    assert merged.date_range == {"start": "2019-10-01", "end": "2025-10-31"}
    assert merged.asset_universe == ["AAPL", "GOOG"]
    assert merged.asset_class == "equity"
    assert merged.capital_amount == 200
    assert merged.cadence == "monthly"
    assert merged.timeframe == "1D"
    assert merged.comparison_baseline == "SPY"


def test_asset_patch_preserves_period_money_timeframe_and_benchmark() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=500,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    merged = apply_artifact_patch(
        base,
        ArtifactPatch(
            source="user_patch",
            asset_universe=["nvda"],
            asset_universe_operation="replace",
            asset_class="equity",
        ),
    )

    assert merged.asset_universe == ["NVDA"]
    assert merged.asset_class == "equity"
    assert merged.date_range == {"start": "2024-01-01", "end": "2024-12-31"}
    assert merged.capital_amount == 500
    assert merged.timeframe == "1D"
    assert merged.comparison_baseline == "SPY"


def test_asset_patch_requires_explicit_operation() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=500,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    with pytest.raises(ValueError, match="asset_universe_operation"):
        apply_artifact_patch(
            base,
            ArtifactPatch(
                source="user_patch",
                asset_universe=["nvda"],
            ),
        )


def test_asset_append_patch_preserves_canonical_setup_and_explicit_benchmark() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-15"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="QQQ",
    )

    merged = apply_artifact_patch(
        base,
        ArtifactPatch(
            source="user_patch",
            asset_universe=["googl", "NVDA"],
            asset_universe_operation="append",
        ),
    )

    assert merged.asset_universe == ["AAPL", "MSFT", "TSLA", "GOOGL", "NVDA"]
    assert merged.date_range == {"start": "2023-01-01", "end": "2026-06-15"}
    assert merged.capital_amount == 100000
    assert merged.timeframe == "1D"
    assert merged.comparison_baseline == "QQQ"


def test_asset_replace_patch_preserves_explicit_benchmark() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-15"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="QQQ",
        extra_parameters={"asset_universe_operation": "append"},
    )

    merged = apply_artifact_patch(
        base,
        ArtifactPatch(
            source="user_patch",
            asset_universe=["amd", "intc"],
            asset_universe_operation="replace",
        ),
    )

    assert merged.asset_universe == ["AMD", "INTC"]
    assert merged.date_range == {"start": "2023-01-01", "end": "2026-06-15"}
    assert merged.capital_amount == 100000
    assert merged.timeframe == "1D"
    assert merged.comparison_baseline == "QQQ"
    assert merged.extra_parameters["artifact_patch"][
        "asset_universe_operation"
    ] == "replace"
    assert "asset_universe_operation" not in merged.extra_parameters


def test_explicit_benchmark_patch_never_enters_asset_universe() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-15"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    merged = apply_artifact_patch(
        base,
        ArtifactPatch(source="user_patch", comparison_baseline="qqq"),
    )

    assert merged.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert merged.comparison_baseline == "QQQ"
    assert merged.date_range == {"start": "2023-01-01", "end": "2026-06-15"}
    assert merged.capital_amount == 100000


def test_crypto_asset_append_preserves_default_btc_benchmark() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold ETH.",
        asset_universe=["ETH"],
        asset_class="crypto",
        date_range={"start": "2024-01-01", "end": "2026-06-15"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="BTC",
    )

    merged = apply_artifact_patch(
        base,
        ArtifactPatch(
            source="user_patch",
            asset_universe=["sol"],
            asset_universe_operation="append",
        ),
    )

    assert merged.asset_universe == ["ETH", "SOL"]
    assert merged.comparison_baseline == "BTC"
    assert merged.asset_class == "crypto"


def test_candidate_append_patch_preserves_anchor_setup() -> None:
    anchor = resolve_artifact_anchor(
        snapshot=TaskSnapshot(
            active_confirmation_reference=ArtifactReference(
                artifact_kind="confirmation",
                artifact_id="confirmation-test",
                artifact_status="active",
                metadata={
                    "confirmation_id": "confirmation-test",
                    "confirmation_payload": {
                        "strategy": {
                            "strategy_type": "buy_and_hold",
                            "strategy_thesis": "Buy and hold AAPL, MSFT, and TSLA.",
                            "asset_universe": ["AAPL", "MSFT", "TSLA"],
                            "asset_class": "equity",
                            "date_range": {
                                "start": "2023-01-01",
                                "end": "2026-06-15",
                            },
                            "capital_amount": 100000,
                            "timeframe": "1D",
                            "comparison_baseline": "QQQ",
                        },
                        "launch_payload": {
                            "strategy_type": "buy_and_hold",
                            "symbol": "AAPL",
                            "symbols": ["AAPL", "MSFT", "TSLA"],
                            "timeframe": "1D",
                            "date_range": {
                                "start": "2023-01-01",
                                "end": "2026-06-15",
                            },
                            "sizing_mode": "capital_amount",
                            "capital_amount": 100000,
                            "benchmark_symbol": "QQQ",
                        },
                    },
                },
            )
        )
    )

    patched = patched_draft_from_candidate(
        anchor=anchor,
        candidate=StrategySummary(
            asset_universe=["GOOGL", "NVDA"],
            extra_parameters={"asset_universe_operation": "append"},
        ),
    )

    assert patched is not None
    assert patched.asset_universe == ["AAPL", "MSFT", "TSLA", "GOOGL", "NVDA"]
    assert patched.date_range == {"start": "2023-01-01", "end": "2026-06-15"}
    assert patched.capital_amount == 100000
    assert patched.timeframe == "1D"
    assert patched.comparison_baseline == "QQQ"


def test_patched_draft_rejects_asset_universe_without_operation() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-15"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="QQQ",
    )
    anchor = resolve_artifact_anchor(
        snapshot=TaskSnapshot(
            active_confirmation_reference=ArtifactReference(
                artifact_kind="confirmation",
                artifact_id="confirmation-test",
                artifact_status="active",
                metadata={
                    "confirmation_payload": {
                        "strategy": base.model_dump(mode="json"),
                    },
                },
            )
        )
    )

    patched = patched_draft_from_candidate(
        anchor=anchor,
        candidate=StrategySummary(asset_universe=["GOOGL", "NVDA"]),
    )

    assert patched is None


def test_candidate_reordered_assets_do_not_require_asset_operation() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL, MSFT, and TSLA.",
        asset_universe=["AAPL", "MSFT", "TSLA"],
        asset_class="equity",
        date_range={"start": "2023-01-01", "end": "2026-06-15"},
        capital_amount=100000,
        timeframe="1D",
        comparison_baseline="SPY",
    )
    anchor = resolve_artifact_anchor(
        snapshot=TaskSnapshot(
            active_confirmation_reference=ArtifactReference(
                artifact_kind="confirmation",
                artifact_id="confirmation-test",
                artifact_status="active",
                metadata={
                    "confirmation_payload": {
                        "strategy": base.model_dump(mode="json"),
                    },
                },
            )
        )
    )

    patched = patched_draft_from_candidate(
        anchor=anchor,
        candidate=StrategySummary(
            asset_universe=["TSLA", "AAPL", "MSFT"],
            comparison_baseline="QQQ",
        ),
    )

    assert patched is not None
    assert patched.asset_universe == ["AAPL", "MSFT", "TSLA"]
    assert patched.comparison_baseline == "QQQ"
    assert patched.date_range == {"start": "2023-01-01", "end": "2026-06-15"}
    assert patched.capital_amount == 100000


def test_patch_clears_fields_only_when_explicitly_requested() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=500,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    omitted = apply_artifact_patch(base, ArtifactPatch(source="user_patch"))
    cleared = apply_artifact_patch(
        base,
        ArtifactPatch(source="user_patch", clear_fields=["comparison_baseline"]),
    )

    assert omitted.comparison_baseline == "SPY"
    assert cleared.comparison_baseline is None
    assert cleared.asset_universe == ["AAPL"]
    assert cleared.date_range == {"start": "2024-01-01", "end": "2024-12-31"}


def test_patch_clear_fields_cannot_clear_asset_universe() -> None:
    base = StrategySummary(
        strategy_type="buy_and_hold",
        strategy_thesis="Buy and hold AAPL.",
        asset_universe=["AAPL"],
        asset_class="equity",
        date_range={"start": "2024-01-01", "end": "2024-12-31"},
        capital_amount=500,
        timeframe="1D",
        comparison_baseline="SPY",
    )

    cleared = apply_artifact_patch(
        base,
        ArtifactPatch(source="user_patch", clear_fields=["asset_universe"]),
    )

    assert cleared.asset_universe == ["AAPL"]
    assert "asset_universe" not in cleared.extra_parameters["artifact_patch"][
        "changed_fields"
    ]


def test_anchor_resolution_prefers_targeted_active_confirmation() -> None:
    confirmation = ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="confirmation-1",
        artifact_status="active",
        metadata={
            "confirmation_id": "confirmation-1",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                    "comparison_baseline": "SPY",
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "capital_amount": 500,
                    "benchmark_symbol": "SPY",
                },
            },
        },
    )
    result = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-1",
        artifact_status="completed",
        metadata={
            "asset_class": "equity",
            "symbols": ["NVDA"],
            "benchmark_symbol": "QQQ",
            "config_snapshot": {"template": "buy_and_hold"},
        },
    )
    snapshot = TaskSnapshot(
        active_confirmation_reference=confirmation,
        latest_backtest_result_reference=result,
    )

    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload={"confirmation_id": "confirmation-1"},
    )

    assert anchor.kind == "confirmation"
    assert anchor.artifact_id == "confirmation-1"
    assert anchor.draft is not None
    assert anchor.draft.asset_universe == ["AAPL"]
    assert anchor.draft.capital_amount == 500
    assert anchor.draft.comparison_baseline == "SPY"


def test_anchor_resolution_uses_historical_confirmation_when_action_targets_older_card() -> None:
    active_confirmation = ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="confirmation-current",
        artifact_status="active",
        metadata={
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["NVDA"],
                    "asset_class": "equity",
                    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbols": ["NVDA"],
                    "timeframe": "1D",
                    "capital_amount": 1000,
                    "benchmark_symbol": "QQQ",
                },
            },
        },
    )
    historical_confirmation = ArtifactReference(
        artifact_kind="confirmation",
        artifact_id="artifact-old-confirmation",
        artifact_status="superseded",
        metadata={
            "confirmation_id": "confirmation-old",
            "confirmation_payload": {
                "strategy": {
                    "strategy_type": "buy_and_hold",
                    "asset_universe": ["AAPL"],
                    "asset_class": "equity",
                    "date_range": {"start": "2023-01-01", "end": "2023-12-31"},
                    "comparison_baseline": "SPY",
                },
                "launch_payload": {
                    "strategy_type": "buy_and_hold",
                    "symbols": ["AAPL"],
                    "timeframe": "1D",
                    "capital_amount": 500,
                    "benchmark_symbol": "SPY",
                },
            },
        },
    )
    snapshot = TaskSnapshot(
        active_confirmation_reference=active_confirmation,
        artifact_references=[historical_confirmation],
    )

    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload={"confirmation_id": "confirmation-old"},
    )

    assert anchor.kind == "confirmation"
    assert anchor.artifact_id == "confirmation-old"
    assert anchor.draft is not None
    assert anchor.draft.asset_universe == ["AAPL"]
    assert anchor.draft.capital_amount == 500
    assert anchor.draft.comparison_baseline == "SPY"


def test_anchor_resolution_uses_result_when_action_targets_run() -> None:
    result = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-1",
        artifact_status="completed",
        metadata={
            "asset_class": "equity",
            "symbols": ["AAPL", "GOOG"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "dca_accumulation",
                "symbols": ["AAPL", "GOOG"],
                "resolved_strategy": {
                    "strategy_type": "dca_accumulation",
                    "asset_universe": ["AAPL", "GOOG"],
                    "asset_class": "equity",
                    "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                    "capital_amount": 200,
                    "cadence": "monthly",
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "benchmark_symbol": "SPY",
                },
            },
        },
    )
    snapshot = TaskSnapshot(latest_backtest_result_reference=result)

    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload={"run_id": "run-1"},
    )

    assert anchor.kind == "result"
    assert anchor.artifact_id == "run-1"
    assert anchor.draft is not None
    assert anchor.draft.asset_universe == ["AAPL", "GOOG"]
    assert anchor.draft.capital_amount == 200
    assert anchor.draft.cadence == "monthly"


def test_anchor_resolution_uses_historical_result_when_action_targets_older_run() -> None:
    latest_result = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-current",
        artifact_status="completed",
        metadata={
            "asset_class": "equity",
            "symbols": ["NVDA"],
            "benchmark_symbol": "QQQ",
            "config_snapshot": {"template": "buy_and_hold"},
        },
    )
    historical_result = ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id="run-old",
        artifact_status="completed",
        metadata={
            "asset_class": "equity",
            "symbols": ["AAPL", "GOOG"],
            "benchmark_symbol": "SPY",
            "config_snapshot": {
                "template": "dca_accumulation",
                "symbols": ["AAPL", "GOOG"],
                "resolved_strategy": {
                    "strategy_type": "dca_accumulation",
                    "asset_universe": ["AAPL", "GOOG"],
                    "asset_class": "equity",
                    "date_range": {"start": "2021-01-01", "end": "2024-01-31"},
                    "capital_amount": 200,
                    "cadence": "monthly",
                },
                "resolved_parameters": {
                    "timeframe": "1D",
                    "benchmark_symbol": "SPY",
                },
            },
        },
    )
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=latest_result,
        artifact_references=[historical_result],
    )

    anchor = resolve_artifact_anchor(
        snapshot=snapshot,
        action_payload={"run_id": "run-old"},
    )

    assert anchor.kind == "result"
    assert anchor.artifact_id == "run-old"
    assert anchor.draft is not None
    assert anchor.draft.asset_universe == ["AAPL", "GOOG"]
    assert anchor.draft.capital_amount == 200
    assert anchor.draft.cadence == "monthly"


def test_anchor_patch_applies_to_failed_action_payload() -> None:
    failed = ArtifactReference(
        artifact_kind="failed_action",
        artifact_id="failed-run-1",
        artifact_status="failed",
        metadata={
            "action_type": "run_backtest",
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbols": ["NU"],
                "asset_class": "equity",
                "date_range": {"start": "2026-01-01", "end": "2026-06-03"},
                "timeframe": "1D",
                "capital_amount": 500,
                "benchmark_symbol": "SPY",
            },
        },
    )
    snapshot = TaskSnapshot(latest_failed_action_reference=failed)
    anchor = resolve_artifact_anchor(snapshot=snapshot, retrying_failed_action=True)

    patched = apply_patch_to_anchor(
        anchor,
        ArtifactPatch(
            source="retry",
            date_range={"start": "2026-01-01", "end": "2026-06-02"},
        ),
    )

    assert anchor.kind == "failed_action"
    assert patched is not None
    assert patched.asset_universe == ["NU"]
    assert patched.capital_amount == 500
    assert patched.date_range == {"start": "2026-01-01", "end": "2026-06-02"}


def test_retry_lifecycle_supersedes_after_new_confirmation() -> None:
    decision = retry_lifecycle_after_artifact_event(
        retry_artifact_id="failed-run-1",
        latest_failed_artifact_id="failed-run-1",
        new_artifact_kind="confirmation",
    )

    assert decision == RetryLifecycleDecision.SUPERSEDED


def test_retry_lifecycle_expires_when_retry_no_longer_matches_latest_failure() -> None:
    decision = retry_lifecycle_after_artifact_event(
        retry_artifact_id="failed-run-1",
        latest_failed_artifact_id="failed-run-2",
        new_artifact_kind=None,
    )

    assert decision == RetryLifecycleDecision.EXPIRED


def test_retry_lifecycle_remains_active_for_current_failure() -> None:
    decision = retry_lifecycle_after_artifact_event(
        retry_artifact_id="failed-run-1",
        latest_failed_artifact_id="failed-run-1",
        new_artifact_kind=None,
    )

    assert decision == RetryLifecycleDecision.ACTIVE


def test_retry_failed_action_rejects_stale_action_id() -> None:
    failed = ArtifactReference(
        artifact_kind="failed_action",
        artifact_id="failed-new",
        artifact_status="failed",
        metadata={
            "action_type": "run_backtest",
            "retryable": True,
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbols": ["MSFT"],
                "asset_class": "equity",
                "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
                "timeframe": "1D",
                "sizing_mode": "capital_amount",
                "capital_amount": 1000,
                "benchmark_symbol": "SPY",
            },
        },
    )
    state = RunState.new(
        current_user_message="Retry",
        recent_thread_history=[],
        action_context={
            "type": "retry_failed_action",
            "label": "Retry",
            "payload": {"failed_action_id": "failed-old"},
        },
    )

    result = structured_action_stage_result_if_applicable(
        state=state,
        snapshot=TaskSnapshot(latest_failed_action_reference=failed),
        selected_thread_metadata={},
    )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    assert result.decision is not None
    assert "stale_failed_action_retry" in result.decision.reason_codes
    assert "assistant_response" not in result.stage_patch
    assert "candidate_strategy_draft" not in result.stage_patch
    assert result.stage_patch["response_intent"] == {
        "kind": "artifact_action_recovery",
        "facts": {
            "action_type": "retry_failed_action",
            "status": "stale",
            "requested_failed_action_id": "failed-old",
            "latest_failed_action_id": "failed-new",
            "language": "en",
        },
    }


def test_structured_retry_failed_action_requires_artifact_id() -> None:
    failed = ArtifactReference(
        artifact_kind="failed_action",
        artifact_id="failed-new",
        artifact_status="failed",
        metadata={
            "action_type": "run_backtest",
            "retryable": True,
            "launch_payload": {
                "strategy_type": "buy_and_hold",
                "symbols": ["MSFT"],
                "asset_class": "equity",
                "date_range": {"start": "2025-01-01", "end": "2025-12-31"},
                "timeframe": "1D",
                "sizing_mode": "capital_amount",
                "capital_amount": 1000,
                "benchmark_symbol": "SPY",
            },
        },
    )
    state = RunState.new(
        current_user_message="Retry",
        recent_thread_history=[],
        action_context={
            "type": "retry_failed_action",
            "label": "Retry",
            "payload": {},
        },
    )

    result = structured_action_stage_result_if_applicable(
        state=state,
        snapshot=TaskSnapshot(latest_failed_action_reference=failed),
        selected_thread_metadata={},
    )

    assert result is not None
    assert result.outcome == "ready_to_respond"
    assert result.decision is not None
    assert "stale_failed_action_retry" in result.decision.reason_codes
    assert "assistant_response" not in result.stage_patch
    assert "candidate_strategy_draft" not in result.stage_patch
    assert result.stage_patch["response_intent"] == {
        "kind": "artifact_action_recovery",
        "facts": {
            "action_type": "retry_failed_action",
            "status": "missing_artifact_id",
            "requested_failed_action_id": None,
            "latest_failed_action_id": "failed-new",
            "language": "en",
        },
    }
