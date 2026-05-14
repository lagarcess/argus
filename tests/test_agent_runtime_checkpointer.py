from __future__ import annotations

from argus.agent_runtime.state.models import (
    ArtifactReference,
    ConfirmationPayload,
    ConversationMessage,
    RunState,
    StrategySummary,
    TaskSnapshot,
)
from argus.api import state as api_state


def test_agent_runtime_checkpointer_serializes_runtime_state() -> None:
    checkpointer = api_state.build_agent_runtime_checkpointer()
    run_state = RunState.new(
        current_user_message="Run backtest",
        recent_thread_history=[
            ConversationMessage(
                role="user",
                content="try dca on BTC over the last 6 months",
            ),
        ],
    )

    serialized = checkpointer.serde.dumps_typed(run_state)
    restored = checkpointer.serde.loads_typed(serialized)

    assert restored.current_user_message == "Run backtest"
    assert restored.recent_thread_history[0].content.startswith("try dca")


def test_agent_runtime_checkpointer_serializes_artifact_spine() -> None:
    checkpointer = api_state.build_agent_runtime_checkpointer()
    snapshot = TaskSnapshot(
        latest_backtest_result_reference=ArtifactReference(
            artifact_kind="backtest_result",
            artifact_id="run-1",
            artifact_status="completed",
            metadata={"symbols": ["TSLA"], "benchmark_symbol": "SPY"},
        ),
        artifact_references=[
            ArtifactReference(
                artifact_kind="confirmation",
                artifact_id="confirmation-1",
                artifact_status="active",
            )
        ],
    )

    serialized = checkpointer.serde.dumps_typed(snapshot)
    restored = checkpointer.serde.loads_typed(serialized)

    assert restored.latest_backtest_result_reference is not None
    assert restored.latest_backtest_result_reference.artifact_id == "run-1"
    assert restored.artifact_references[0].artifact_kind == "confirmation"


def test_confirmation_payload_preserves_validated_launch_payload() -> None:
    payload = ConfirmationPayload(
        strategy=StrategySummary(
            strategy_type="buy_and_hold",
            asset_universe=["AAPL"],
            date_range="past year",
        ),
        optional_parameters={},
        launch_payload={
            "strategy_type": "buy_and_hold",
            "symbol": "AAPL",
            "symbols": ["AAPL"],
            "timeframe": "1D",
            "date_range": {"start": "2025-05-13", "end": "2026-05-13"},
            "sizing_mode": "capital_amount",
            "capital_amount": 1000,
            "benchmark_symbol": "SPY",
        },
        validation={"status": "ready_to_run", "executable": True},
    )

    restored = ConfirmationPayload.model_validate(payload.model_dump(mode="python"))

    assert restored.launch_payload is not None
    assert restored.launch_payload["symbol"] == "AAPL"
    assert restored.validation["executable"] is True
