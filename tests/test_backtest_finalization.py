from __future__ import annotations

from dataclasses import replace

import pytest
from argus.api.schemas import BacktestRun
from argus.domain.backtest_finalization import (
    BacktestFinalizationError,
    BacktestFinalizationInput,
    MemoryBacktestFinalizationGateway,
    finalize_backtest_completion,
    stable_backtest_run_id,
)
from argus.domain.store import AlphaStore, utcnow


def _run(*, run_id: str = "run-1") -> BacktestRun:
    return BacktestRun(
        id=run_id,
        conversation_id="conversation-1",
        strategy_id=None,
        status="completed",
        asset_class="equity",
        symbols=["AAPL"],
        allocation_method="equal_weight",
        benchmark_symbol="SPY",
        metrics={"aggregate": {"performance": {"total_return_pct": 12.4}}},
        config_snapshot={"template": "buy_and_hold", "symbols": ["AAPL"]},
        conversation_result_card={
            "title": "AAPL buy and hold",
            "quick_take": "AAPL returned 12.4% in this historical test.",
            "assumptions": ["Benchmark: SPY"],
            "actions": [{"type": "save_strategy", "payload": {"run_id": run_id}}],
        },
        created_at=utcnow(),
        chart=None,
        trades=[],
    )


def _input(
    *,
    run_id: str = "run-1",
    idea_id: str = "idea-1",
    idea_version_id: str = "version-1",
    evidence_artifact_id: str = "artifact-1",
) -> BacktestFinalizationInput:
    run = _run(run_id=run_id)
    return BacktestFinalizationInput(
        user_id="user-1",
        execution_identity="backtest_job:job-1",
        run=run,
        result_card=dict(run.conversation_result_card),
        idea_id=idea_id,
        idea_version_id=idea_version_id,
        evidence_artifact_id=evidence_artifact_id,
        finalized_at=utcnow(),
    )


def test_stable_run_id_is_owner_scoped_and_replay_safe() -> None:
    first = stable_backtest_run_id("user-1", "backtest_job:job-1")

    assert first == stable_backtest_run_id("user-1", "backtest_job:job-1")
    assert first != stable_backtest_run_id("user-2", "backtest_job:job-1")
    assert first != stable_backtest_run_id("user-1", "backtest_job:job-2")


@pytest.mark.parametrize(
    ("user_id", "execution_identity"),
    [("", "job:1"), ("user-1", ""), (" ", "job:1"), ("user-1", " ")],
)
def test_stable_run_id_rejects_blank_identity_parts(
    user_id: str,
    execution_identity: str,
) -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        stable_backtest_run_id(user_id, execution_identity)


def test_memory_finalizer_commits_one_complete_tuple_and_reuses_it() -> None:
    store = AlphaStore()
    gateway = MemoryBacktestFinalizationGateway(store)

    first = finalize_backtest_completion(gateway, _input())
    second = finalize_backtest_completion(
        gateway,
        _input(
            idea_id="idea-retry",
            idea_version_id="version-retry",
            evidence_artifact_id="artifact-retry",
        ),
    )

    assert second.identity == first.identity
    assert first.identity.run_id == "run-1"
    assert first.identity.idea_id == "idea-1"
    assert first.identity.idea_version_id == "version-1"
    assert first.identity.evidence_artifact_id == "artifact-1"
    assert len(store.backtest_runs) == 1
    assert len(store.ideas) == 1
    assert len(store.idea_versions) == 1
    assert len(store.evidence_artifacts) == 1
    stored_card = store.backtest_runs["run-1"].conversation_result_card
    assert stored_card["idea_id"] == "idea-1"
    assert stored_card["idea_version_id"] == "version-1"
    assert stored_card["evidence_artifact_id"] == "artifact-1"
    assert stored_card["evidence_lifecycle"] == "captured"
    assert stored_card["artifact_type"] == "backtest"
    assert stored_card["actions"][0]["payload"] == {
        "run_id": "run-1",
        "idea_id": "idea-1",
        "idea_version_id": "version-1",
        "evidence_artifact_id": "artifact-1",
    }


def test_memory_finalizer_rejects_cross_owner_run_replay() -> None:
    store = AlphaStore()
    gateway = MemoryBacktestFinalizationGateway(store)
    first = finalize_backtest_completion(gateway, _input())
    assert first.identity.run_id == "run-1"

    other_owner = replace(_input(), user_id="user-2")

    with pytest.raises(BacktestFinalizationError, match="owned by another user"):
        finalize_backtest_completion(gateway, other_owner)


def test_memory_finalizer_rejects_cross_owner_sidecar_id_reuse() -> None:
    store = AlphaStore()
    gateway = MemoryBacktestFinalizationGateway(store)
    finalize_backtest_completion(gateway, _input())
    other_owner = replace(
        _input(
            run_id="run-2",
            idea_id="idea-1",
            idea_version_id="version-2",
            evidence_artifact_id="artifact-2",
        ),
        user_id="user-2",
        execution_identity="backtest_job:job-2",
    )

    with pytest.raises(BacktestFinalizationError, match="owned by another user"):
        finalize_backtest_completion(gateway, other_owner)

    assert store.idea_owners["idea-1"] == "user-1"
    assert "run-2" not in store.backtest_runs
    assert "version-2" not in store.idea_versions
    assert "artifact-2" not in store.evidence_artifacts


def test_memory_finalizer_rejects_incomplete_existing_evidence_tuple() -> None:
    store = AlphaStore()
    gateway = MemoryBacktestFinalizationGateway(store)
    finalized = finalize_backtest_completion(gateway, _input())
    del store.idea_versions[finalized.identity.idea_version_id]

    with pytest.raises(BacktestFinalizationError, match="incomplete"):
        finalize_backtest_completion(gateway, _input())


def test_memory_finalizer_rolls_back_partial_publication_and_retries() -> None:
    class FailOnceOwnerDict(dict):
        should_fail = True

        def __setitem__(self, key, value) -> None:
            if self.should_fail:
                self.should_fail = False
                raise RuntimeError("injected owner-map failure")
            super().__setitem__(key, value)

    store = AlphaStore()
    store.evidence_artifact_owners = FailOnceOwnerDict()
    gateway = MemoryBacktestFinalizationGateway(store)

    with pytest.raises(BacktestFinalizationError, match="finalization failed"):
        finalize_backtest_completion(gateway, _input())

    assert store.backtest_runs == {}
    assert store.backtest_run_owners == {}
    assert store.ideas == {}
    assert store.idea_owners == {}
    assert store.idea_versions == {}
    assert store.idea_version_owners == {}
    assert store.evidence_artifacts == {}
    assert store.evidence_artifact_owners == {}
    assert store.backtest_finalizations == {}

    finalized = finalize_backtest_completion(gateway, _input())

    assert finalized.identity.evidence_artifact_id == "artifact-1"
    assert len(store.backtest_runs) == 1
    assert len(store.ideas) == 1
    assert len(store.idea_versions) == 1
    assert len(store.evidence_artifacts) == 1


def test_finalizer_rejects_non_completed_run_before_gateway_write() -> None:
    finalization = _input()
    failed_run = finalization.run.model_copy(update={"status": "failed"})
    gateway = MemoryBacktestFinalizationGateway(AlphaStore())

    with pytest.raises(BacktestFinalizationError, match="completed run"):
        finalize_backtest_completion(
            gateway,
            replace(finalization, run=failed_run),
        )

    assert gateway.store.backtest_runs == {}
