from __future__ import annotations

from argus.agent_runtime.state.models import ConversationMessage, RunState
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
