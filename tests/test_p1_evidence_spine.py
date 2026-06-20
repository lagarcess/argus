from __future__ import annotations

from argus.api import state as api_state
from argus.api.schemas import BacktestRun, Conversation, User
from argus.domain.evidence import build_backtest_evidence_capture
from argus.domain.store import utcnow


def _user() -> User:
    return User(
        id="user-1",
        email="user@example.com",
        username=None,
        display_name=None,
        language="en",
        locale="en-US",
        theme="dark",
        is_admin=False,
        created_at=utcnow(),
        updated_at=utcnow(),
    )


def _conversation() -> Conversation:
    return Conversation(
        id="conv-1",
        title="AAPL MSFT TSLA idea",
        title_source="system_default",
        created_at=utcnow(),
        updated_at=utcnow(),
        last_message_preview="AAPL MSFT TSLA buy and hold",
    )


def _run() -> BacktestRun:
    return BacktestRun(
        id="run-1",
        conversation_id="conv-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL", "MSFT", "TSLA"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={
            "aggregate": {"performance": {"total_return_pct": 12.3}},
            "by_symbol": {},
        },
        config_snapshot={
            "template": "buy_and_hold",
            "symbols": ["AAPL", "MSFT", "TSLA"],
            "benchmark_symbol": "SPY",
            "date_range": {"start": "2023-01-01", "end": "2026-06-19"},
        },
        conversation_result_card={
            "title": "AAPL, MSFT, TSLA Buy and Hold",
            "status_label": "Simulation Complete",
            "rows": [
                {
                    "key": "total_return_pct",
                    "label": "Total Return",
                    "value": "+12.3%",
                }
            ],
            "assumptions": ["Benchmark: SPY", "No fees"],
            "context_packets": [{"provider": "internal", "raw": "not preview-safe"}],
            "actions": [],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )


def test_completed_backtest_auto_captures_idea_version_and_evidence() -> None:
    from argus.api.chat.evidence import auto_capture_completed_backtest

    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()
    api_state.store.users[user.id] = user
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user.id

    captured = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )

    assert captured.idea.lifecycle == "captured"
    assert captured.idea_version.idea_id == captured.idea.id
    assert captured.evidence_artifact.idea_version_id == captured.idea_version.id
    assert captured.evidence_artifact.artifact_type == "backtest"
    assert captured.evidence_artifact.source_run_id == run.id
    assert captured.evidence_artifact.digest
    assert "context_packets" not in captured.evidence_artifact.payload["result_card"]
    assert (
        run.conversation_result_card["evidence_artifact_id"]
        == captured.evidence_artifact.id
    )
    assert run.conversation_result_card["idea_id"] == captured.idea.id
    assert run.conversation_result_card["idea_version_id"] == captured.idea_version.id


def test_completed_backtest_capture_is_idempotent_by_run_id() -> None:
    from argus.api.chat.evidence import auto_capture_completed_backtest

    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()
    api_state.store.conversations[conversation.id] = conversation
    api_state.store.conversation_owners[conversation.id] = user.id
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = user.id

    first = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )
    second = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )

    assert second.idea.id == first.idea.id
    assert second.idea_version.id == first.idea_version.id
    assert second.evidence_artifact.id == first.evidence_artifact.id
    assert len(api_state.store.evidence_artifacts) == 1


def test_completed_backtest_capture_reuses_durable_sidecar_after_restart(
    monkeypatch,
) -> None:
    from argus.api.chat.evidence import auto_capture_completed_backtest

    class _Gateway:
        def __init__(self, existing):
            self.existing = existing
            self.create_calls = 0
            self.updated_cards: list[dict[str, object]] = []

        def get_evidence_capture_by_run(self, *, user_id, run_id):  # noqa: ANN001
            if user_id == "user-1" and run_id == "run-1":
                return self.existing
            return None

        def create_backtest_evidence_capture(self, *, user_id, captured):  # noqa: ANN001
            self.create_calls += 1
            return captured

        def update_backtest_run_result_card(
            self,
            *,
            user_id,  # noqa: ANN001
            run_id,  # noqa: ANN001
            conversation_result_card,  # noqa: ANN001
        ) -> None:
            assert user_id == "user-1"
            assert run_id == "run-1"
            self.updated_cards.append(dict(conversation_result_card))

    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()
    existing = build_backtest_evidence_capture(
        run=run,
        idea_id="00000000-0000-0000-0000-000000000101",
        idea_version_id="00000000-0000-0000-0000-000000000102",
        evidence_artifact_id="00000000-0000-0000-0000-000000000103",
        now=utcnow(),
    )
    gateway = _Gateway(existing)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    captured = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )

    assert captured.evidence_artifact.id == existing.evidence_artifact.id
    assert gateway.create_calls == 0
    assert gateway.updated_cards
    assert (
        gateway.updated_cards[-1]["evidence_artifact_id"]
        == existing.evidence_artifact.id
    )
    assert len(api_state.store.evidence_artifacts) == 1
