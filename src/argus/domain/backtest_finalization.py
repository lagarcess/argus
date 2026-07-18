from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from argus.api.schemas import BacktestRun
from argus.domain.evidence import CapturedEvidence, build_backtest_evidence_capture
from argus.domain.store import AlphaStore


class BacktestFinalizationError(RuntimeError):
    """Raised when a computed run cannot become a complete product artifact."""


@dataclass(frozen=True)
class BacktestFinalizationInput:
    user_id: str
    execution_identity: str
    run: BacktestRun
    result_card: dict[str, Any]
    idea_id: str
    idea_version_id: str
    evidence_artifact_id: str
    finalized_at: datetime


@dataclass(frozen=True)
class BacktestFinalizedIdentity:
    run_id: str
    idea_id: str
    idea_version_id: str
    evidence_artifact_id: str


@dataclass(frozen=True)
class FinalizedBacktest:
    run: BacktestRun
    captured: CapturedEvidence

    @property
    def identity(self) -> BacktestFinalizedIdentity:
        return BacktestFinalizedIdentity(
            run_id=self.run.id,
            idea_id=self.captured.idea.id,
            idea_version_id=self.captured.idea_version.id,
            evidence_artifact_id=self.captured.evidence_artifact.id,
        )


@dataclass(frozen=True)
class PreparedBacktestFinalization:
    user_id: str
    execution_identity: str
    run: BacktestRun
    captured: CapturedEvidence


class BacktestFinalizationGateway(Protocol):
    def finalize_backtest_completion(
        self,
        *,
        finalization: PreparedBacktestFinalization,
    ) -> FinalizedBacktest:
        """Commit or replay one complete backtest evidence tuple."""


def stable_backtest_run_id(user_id: str, execution_identity: str) -> str:
    clean_user_id = user_id.strip()
    clean_execution_identity = execution_identity.strip()
    if not clean_user_id or not clean_execution_identity:
        raise ValueError("Backtest owner and execution identity must not be blank.")
    return str(
        uuid5(
            NAMESPACE_URL,
            f"https://argus.app/backtest-finalization/{clean_user_id}/"
            f"{clean_execution_identity}",
        )
    )


def finalize_backtest_completion(
    gateway: BacktestFinalizationGateway,
    finalization: BacktestFinalizationInput,
) -> FinalizedBacktest:
    prepared = _prepare_finalization(finalization)
    try:
        finalized = gateway.finalize_backtest_completion(finalization=prepared)
    except BacktestFinalizationError:
        raise
    except Exception as exc:
        raise BacktestFinalizationError("Backtest finalization failed.") from exc
    _validate_finalized_backtest(finalized)
    return finalized


def prepare_backtest_finalization(
    finalization: BacktestFinalizationInput,
) -> PreparedBacktestFinalization:
    """Public preparation boundary for finalizers that commit elsewhere
    (#230's one-transaction direct success RPC)."""

    return _prepare_finalization(finalization)


class MemoryBacktestFinalizationGateway:
    def __init__(self, store: AlphaStore) -> None:
        self.store = store

    def finalize_backtest_completion(
        self,
        *,
        finalization: PreparedBacktestFinalization,
    ) -> FinalizedBacktest:
        run_id = finalization.run.id
        execution_key = (
            finalization.user_id,
            finalization.execution_identity,
        )
        with self.store.backtest_finalization_lock:
            known_run_id = self.store.backtest_finalizations.get(execution_key)
            if known_run_id is not None and known_run_id != run_id:
                raise BacktestFinalizationError(
                    "Backtest execution identity is already bound to another run."
                )

            existing_owner = self.store.backtest_run_owners.get(run_id)
            if existing_owner is not None and existing_owner != finalization.user_id:
                raise BacktestFinalizationError(
                    "Backtest run is owned by another user."
                )

            stored_run = self.store.backtest_runs.get(run_id)
            if stored_run is not None and not _same_immutable_run(
                stored_run,
                finalization.run,
            ):
                raise BacktestFinalizationError(
                    "Backtest run identity collided with different immutable payload."
                )

            existing = self._existing_finalization(
                user_id=finalization.user_id,
                run_id=run_id,
            )
            if existing is not None:
                self.store.backtest_finalizations[execution_key] = run_id
                return existing

            self._reject_conflicting_sidecar_ids(finalization)

            captured = finalization.captured
            finalized_run = _run_with_capture(finalization.run, captured)
            finalized = FinalizedBacktest(run=finalized_run, captured=captured)
            cache_finalized_backtest(
                self.store,
                user_id=finalization.user_id,
                finalized=finalized,
            )
            self.store.backtest_finalizations[execution_key] = run_id
            return finalized

    def _reject_conflicting_sidecar_ids(
        self,
        finalization: PreparedBacktestFinalization,
    ) -> None:
        captured = finalization.captured
        candidates = (
            (
                "idea",
                captured.idea.id,
                self.store.ideas,
                self.store.idea_owners,
            ),
            (
                "idea version",
                captured.idea_version.id,
                self.store.idea_versions,
                self.store.idea_version_owners,
            ),
            (
                "evidence artifact",
                captured.evidence_artifact.id,
                self.store.evidence_artifacts,
                self.store.evidence_artifact_owners,
            ),
        )
        for label, object_id, objects, owners in candidates:
            owner = owners.get(object_id)
            if owner is not None and owner != finalization.user_id:
                raise BacktestFinalizationError(
                    f"Backtest finalization {label} is owned by another user."
                )
            if object_id in objects or owner is not None:
                raise BacktestFinalizationError(
                    f"Backtest finalization {label} identity is already in use."
                )

    def _existing_finalization(
        self,
        *,
        user_id: str,
        run_id: str,
    ) -> FinalizedBacktest | None:
        matching_artifacts = [
            artifact
            for artifact_id, artifact in self.store.evidence_artifacts.items()
            if artifact.source_run_id == run_id
            and self.store.evidence_artifact_owners.get(artifact_id) == user_id
        ]
        if not matching_artifacts:
            return None
        if len(matching_artifacts) != 1:
            raise BacktestFinalizationError(
                "Existing backtest finalization is not unique."
            )

        artifact = matching_artifacts[0]
        run = self.store.backtest_runs.get(run_id)
        idea = self.store.ideas.get(artifact.idea_id)
        version = self.store.idea_versions.get(artifact.idea_version_id)
        if run is None or idea is None or version is None:
            raise BacktestFinalizationError(
                "Existing backtest finalization tuple is incomplete."
            )
        if (
            self.store.backtest_run_owners.get(run_id) != user_id
            or self.store.idea_owners.get(idea.id) != user_id
            or self.store.idea_version_owners.get(version.id) != user_id
        ):
            raise BacktestFinalizationError(
                "Existing backtest finalization tuple has inconsistent ownership."
            )

        captured = CapturedEvidence(
            idea=idea,
            idea_version=version,
            evidence_artifact=artifact,
        )
        canonical_run = _run_with_capture(run, captured)
        self.store.backtest_runs[run_id] = canonical_run
        return FinalizedBacktest(run=canonical_run, captured=captured)


def cache_finalized_backtest(
    store: AlphaStore,
    *,
    user_id: str,
    finalized: FinalizedBacktest,
) -> None:
    with store.backtest_finalization_lock:
        captured = finalized.captured
        # Publish the run last while finalization-aware readers hold the same lock.
        # Roll every write back if any publication step fails so the lock never
        # releases a partial tuple to subsequent readers.
        writes: list[tuple[Any, str, Any]] = [
            (store.ideas, captured.idea.id, captured.idea),
            (store.idea_owners, captured.idea.id, user_id),
            (
                store.idea_versions,
                captured.idea_version.id,
                captured.idea_version,
            ),
            (store.idea_version_owners, captured.idea_version.id, user_id),
            (
                store.evidence_artifacts,
                captured.evidence_artifact.id,
                captured.evidence_artifact,
            ),
            (
                store.evidence_artifact_owners,
                captured.evidence_artifact.id,
                user_id,
            ),
            (store.backtest_runs, finalized.run.id, finalized.run),
            (store.backtest_run_owners, finalized.run.id, user_id),
        ]
        missing = object()
        previous = [
            (mapping, key, mapping.get(key, missing)) for mapping, key, _ in writes
        ]
        try:
            for mapping, key, value in writes:
                mapping[key] = value
        except Exception:
            for mapping, key, prior in reversed(previous):
                if prior is missing:
                    mapping.pop(key, None)
                else:
                    mapping[key] = prior
            raise


def _prepare_finalization(
    finalization: BacktestFinalizationInput,
) -> PreparedBacktestFinalization:
    if not finalization.user_id.strip():
        raise BacktestFinalizationError("Backtest finalization owner must not be blank.")
    if not finalization.execution_identity.strip():
        raise BacktestFinalizationError(
            "Backtest finalization execution identity must not be blank."
        )
    if finalization.run.status != "completed":
        raise BacktestFinalizationError(
            "Backtest finalization requires a completed run."
        )
    if not finalization.run.id.strip():
        raise BacktestFinalizationError("Backtest finalization run id must not be blank.")

    source_run = finalization.run.model_copy(
        update={"conversation_result_card": deepcopy(finalization.result_card)}
    )
    captured = build_backtest_evidence_capture(
        run=source_run,
        idea_id=finalization.idea_id,
        idea_version_id=finalization.idea_version_id,
        evidence_artifact_id=finalization.evidence_artifact_id,
        now=finalization.finalized_at,
    )
    return PreparedBacktestFinalization(
        user_id=finalization.user_id,
        execution_identity=finalization.execution_identity,
        run=_run_with_capture(source_run, captured),
        captured=captured,
    )


def _run_with_capture(
    run: BacktestRun,
    captured: CapturedEvidence,
) -> BacktestRun:
    result_card = dict(run.conversation_result_card)
    result_card.update(
        {
            "idea_id": captured.idea.id,
            "idea_version_id": captured.idea_version.id,
            "evidence_artifact_id": captured.evidence_artifact.id,
            "evidence_lifecycle": captured.evidence_artifact.lifecycle,
            "artifact_type": captured.evidence_artifact.artifact_type,
        }
    )
    actions = result_card.get("actions")
    if isinstance(actions, list):
        enriched_actions: list[dict[str, Any]] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            payload = action.get("payload")
            enriched_payload = dict(payload) if isinstance(payload, dict) else {}
            enriched_payload.update(
                {
                    "idea_id": captured.idea.id,
                    "idea_version_id": captured.idea_version.id,
                    "evidence_artifact_id": captured.evidence_artifact.id,
                }
            )
            enriched_actions.append({**action, "payload": enriched_payload})
        result_card["actions"] = enriched_actions
    return run.model_copy(update={"conversation_result_card": result_card})


def _same_immutable_run(left: BacktestRun, right: BacktestRun) -> bool:
    # Result-card lifecycle metadata can advance after commit, and a retry can
    # rebuild the attempt timestamp. Neither changes the computed run truth.
    ignored = {"conversation_result_card", "created_at"}
    left_payload = left.model_dump(mode="json", exclude=ignored)
    right_payload = right.model_dump(mode="json", exclude=ignored)
    return left_payload == right_payload


def validate_finalized_backtest(finalized: FinalizedBacktest) -> None:
    """Public identity validation for finalizers that commit elsewhere."""

    _validate_finalized_backtest(finalized)


def _validate_finalized_backtest(finalized: FinalizedBacktest) -> None:
    run = finalized.run
    captured = finalized.captured
    artifact = captured.evidence_artifact
    if run.status != "completed" or artifact.source_run_id != run.id:
        raise BacktestFinalizationError(
            "Backtest finalizer returned an inconsistent run/evidence identity."
        )
    if (
        captured.idea_version.idea_id != captured.idea.id
        or artifact.idea_id != captured.idea.id
        or artifact.idea_version_id != captured.idea_version.id
    ):
        raise BacktestFinalizationError(
            "Backtest finalizer returned inconsistent evidence parents."
        )
    required_card_identity = {
        "idea_id": captured.idea.id,
        "idea_version_id": captured.idea_version.id,
        "evidence_artifact_id": artifact.id,
        "evidence_lifecycle": artifact.lifecycle,
        "artifact_type": artifact.artifact_type,
    }
    card = run.conversation_result_card
    if any(card.get(key) != value for key, value in required_card_identity.items()):
        raise BacktestFinalizationError(
            "Backtest finalizer returned incomplete result-card identity."
        )
