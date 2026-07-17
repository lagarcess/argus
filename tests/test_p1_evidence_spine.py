from __future__ import annotations

from threading import Event, Thread

from argus.api import state as api_state
from argus.api.schemas import BacktestRun, Conversation, DecisionNoteCreate, User
from argus.domain.backtest_finalization import (
    BacktestFinalizationInput,
    MemoryBacktestFinalizationGateway,
    PreparedBacktestFinalization,
    finalize_backtest_completion,
)
from argus.domain.evidence import (
    build_backtest_evidence_capture,
    evidence_preview_from_artifact,
)
from argus.domain.store import AlphaStore, utcnow


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
            "assumptions": ["**Benchmark:** SPY", "- No fees"],
            "quick_take": (
                "**Quick take**\n\n"
                "AAPL, MSFT, and TSLA beat SPY in this window.\n\n"
                "- This is evidence, not advice."
            ),
            "breakdown": {
                "summary": "**The equal-weight basket led the benchmark.**",
                "sections": ["Setup", "Benchmark comparison"],
            },
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
    assert (
        captured.evidence_artifact.digest
        == "Quick take AAPL, MSFT, and TSLA beat SPY in this window. "
        "This is evidence, not advice."
    )
    assert captured.idea.summary == captured.evidence_artifact.digest
    assert captured.idea_version.summary == captured.evidence_artifact.digest
    assert (
        captured.evidence_artifact.payload["quick_take"]
        == "Quick take AAPL, MSFT, and TSLA beat SPY in this window. "
        "This is evidence, not advice."
    )
    assert captured.evidence_artifact.payload["breakdown"] == {
        "summary": "The equal-weight basket led the benchmark.",
        "sections": ["Setup", "Benchmark comparison"],
    }
    assert captured.evidence_artifact.payload["assumptions"] == [
        "Benchmark: SPY",
        "No fees",
    ]
    assert captured.evidence_artifact.payload["metrics"] == run.metrics
    assert "context_packets" not in captured.evidence_artifact.payload["result_card"]
    assert "actions" not in captured.evidence_artifact.payload["result_card"]
    preview = evidence_preview_from_artifact(captured.evidence_artifact)
    assert (
        preview["quick_take"]
        == "Quick take AAPL, MSFT, and TSLA beat SPY in this window. "
        "This is evidence, not advice."
    )
    assert "**" not in preview["quick_take"]
    assert preview["breakdown"] == {
        "summary": "The equal-weight basket led the benchmark.",
        "sections": ["Setup", "Benchmark comparison"],
    }
    assert preview["assumptions"] == ["Benchmark: SPY", "No fees"]
    assert preview["metrics_summary"] == {"total_return_pct": 12.3}
    assert preview["symbols"] == ["AAPL", "MSFT", "TSLA"]
    assert preview["benchmark_symbol"] == "SPY"
    assert not any(key.endswith("_id") for key in preview)
    assert (
        run.conversation_result_card["evidence_artifact_id"]
        == captured.evidence_artifact.id
    )
    assert run.conversation_result_card["idea_id"] == captured.idea.id
    assert run.conversation_result_card["idea_version_id"] == captured.idea_version.id


def test_evidence_provenance_preserves_requested_and_effective_data_windows() -> None:
    run = _run().model_copy(
        update={
            "config_snapshot": {
                **_run().config_snapshot,
                "requested_date_range": {
                    "start": "2023-01-01",
                    "end": "2026-06-19",
                },
                "effective_date_range": {
                    "start": "2023-03-15",
                    "end": "2026-06-18",
                },
                "data_coverage": {
                    "schema_version": "market_data_coverage_v1",
                    "dataset_id": "sha256:fixture",
                },
            }
        }
    )

    captured = build_backtest_evidence_capture(
        run=run,
        idea_id="idea-window",
        idea_version_id="version-window",
        evidence_artifact_id="evidence-window",
        now=utcnow(),
    )

    assert captured.evidence_artifact.payload["provenance"]["data_window"] == {
        "requested": {"start": "2023-01-01", "end": "2026-06-19"},
        "effective": {"start": "2023-03-15", "end": "2026-06-18"},
        "dataset_id": "sha256:fixture",
    }


def test_memory_search_waits_for_complete_backtest_finalization(monkeypatch) -> None:
    from argus.api.search_assembly import scored_memory_search_items

    artifact_published = Event()
    release_finalizer = Event()

    class PausingArtifactDict(dict):
        def __setitem__(self, key, value) -> None:
            super().__setitem__(key, value)
            artifact_published.set()
            assert release_finalizer.wait(timeout=2)

    store = AlphaStore()
    store.evidence_artifacts = PausingArtifactDict()
    monkeypatch.setattr(api_state, "store", store)
    run = _run()
    finalization = BacktestFinalizationInput(
        user_id="user-1",
        execution_identity="backtest_job:job-1",
        run=run,
        result_card=dict(run.conversation_result_card),
        idea_id="idea-1",
        idea_version_id="version-1",
        evidence_artifact_id="artifact-1",
        finalized_at=utcnow(),
    )
    finalization_errors: list[BaseException] = []
    search_results: list[tuple[int, object]] = []
    search_finished = Event()

    def finalize() -> None:
        try:
            finalize_backtest_completion(
                MemoryBacktestFinalizationGateway(store),
                finalization,
            )
        except BaseException as exc:  # pragma: no cover - surfaced below
            finalization_errors.append(exc)

    def search() -> None:
        search_results.extend(scored_memory_search_items(user=_user(), query="aapl"))
        search_finished.set()

    finalizer_thread = Thread(target=finalize)
    search_thread = Thread(target=search)
    finalizer_thread.start()
    assert artifact_published.wait(timeout=1)
    search_thread.start()

    try:
        assert not search_finished.wait(timeout=0.1)
    finally:
        release_finalizer.set()
        finalizer_thread.join(timeout=2)
        search_thread.join(timeout=2)

    assert not finalization_errors
    assert search_finished.is_set()
    result_types = {item.type for _, item in search_results}
    assert {"backtest", "idea", "evidence"}.issubset(result_types)


def test_completed_backtest_capture_emits_product_event(monkeypatch) -> None:
    from argus.api.chat.evidence import auto_capture_completed_backtest

    observed: list[dict[str, object]] = []

    def fake_capture(kind: str, **kwargs: object) -> None:
        observed.append({"kind": kind, **kwargs})

    monkeypatch.setattr(
        "argus.api.chat.evidence.capture_product_event",
        fake_capture,
        raising=False,
    )
    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()

    auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )

    assert observed == [
        {
            "kind": "evidence_capture",
            "user_id": user.id,
            "conversation_id": conversation.id,
            "backtest_run_id": run.id,
            "status": "completed",
            "attributes": {
                "asset_class": "equity",
                "symbol_count": 3,
                "benchmark_present": True,
                "persistence": "memory",
            },
        }
    ]


def test_decision_capture_emits_product_event(monkeypatch) -> None:
    from argus.api.chat.evidence import (
        auto_capture_completed_backtest,
        create_decision_for_evidence_artifact,
    )

    observed: list[dict[str, object]] = []

    def fake_capture(kind: str, **kwargs: object) -> None:
        observed.append({"kind": kind, **kwargs})

    monkeypatch.setattr(
        "argus.api.chat.evidence.capture_product_event",
        fake_capture,
        raising=False,
    )
    api_state.store.reset()
    user = _user()
    conversation = _conversation()
    run = _run()
    captured = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )
    observed.clear()

    create_decision_for_evidence_artifact(
        user=user,
        artifact_id=captured.evidence_artifact.id,
        payload=DecisionNoteCreate(decision_state="promising", note="Keep watching."),
    )

    assert observed == [
        {
            "kind": "decision_capture",
            "user_id": user.id,
            "conversation_id": conversation.id,
            "backtest_run_id": run.id,
            "status": "promising",
            "attributes": {
                "decision_state": "promising",
                "artifact_lifecycle": "decided",
                "note_present": True,
            },
        }
    ]


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
        def __init__(self, existing, run: BacktestRun):  # noqa: ANN001
            self.store = AlphaStore()
            self.finalization_calls = 0
            self.store.backtest_runs[run.id] = run
            self.store.backtest_run_owners[run.id] = "user-1"
            self.store.ideas[existing.idea.id] = existing.idea
            self.store.idea_owners[existing.idea.id] = "user-1"
            self.store.idea_versions[existing.idea_version.id] = existing.idea_version
            self.store.idea_version_owners[existing.idea_version.id] = "user-1"
            artifact = existing.evidence_artifact
            self.store.evidence_artifacts[artifact.id] = artifact
            self.store.evidence_artifact_owners[artifact.id] = "user-1"

        def finalize_backtest_completion(
            self,
            *,
            finalization: PreparedBacktestFinalization,
        ):
            self.finalization_calls += 1
            return MemoryBacktestFinalizationGateway(
                self.store
            ).finalize_backtest_completion(finalization=finalization)

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
    gateway = _Gateway(existing, run)
    monkeypatch.setattr(api_state, "supabase_gateway", gateway)

    captured = auto_capture_completed_backtest(
        user=user,
        conversation=conversation,
        run=run,
    )

    assert captured.evidence_artifact.id == existing.evidence_artifact.id
    assert gateway.finalization_calls == 1
    assert (
        run.conversation_result_card["evidence_artifact_id"]
        == existing.evidence_artifact.id
    )
    assert len(api_state.store.evidence_artifacts) == 1
