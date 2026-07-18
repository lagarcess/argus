from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger

from argus.api import state as api_state
from argus.api.schemas import (
    BacktestRun,
    Conversation,
    DecisionNote,
    DecisionNoteCreate,
    EvidenceArtifact,
    Idea,
    IdeaVersion,
    User,
)
from argus.domain.backtest_finalization import (
    BacktestFinalizationError,
    BacktestFinalizationInput,
    FinalizedBacktest,
    MemoryBacktestFinalizationGateway,
    cache_finalized_backtest,
    finalize_backtest_completion,
    prepare_backtest_finalization,
    validate_finalized_backtest,
)
from argus.domain.evidence import (
    CapturedEvidence,
    attach_decision_to_result_card,
    build_decision_note,
)
from argus.domain.store import utcnow
from argus.observability.product_events import capture_product_event


def _emit_product_event(kind: str, **kwargs: object) -> None:
    """Emit a product event without stalling the chat stream.

    These capture calls run inside the async SSE generator; ``capture_event``
    does a blocking ``httpx.post``, so calling it inline would hold the event
    loop for the PostHog round-trip (up to the configured timeout) and freeze
    every concurrent request on the worker. When a loop is running the blocking
    capture is offloaded to a worker thread (mirroring the measurement-event
    path); with no loop (sync callers, tests) it runs inline. Failures are
    swallowed so emission can never surface into a user turn.
    """

    def _run() -> None:
        try:
            capture_product_event(kind, **kwargs)
        except Exception as exc:
            logger.warning(
                "Product event emission failed",
                error=str(exc),
                product_event=kind,
            )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _run()
        return
    loop.run_in_executor(None, _run)


class EvidenceArtifactNotFoundError(LookupError):
    """Raised when an evidence artifact is absent or not owned by the user."""


class EvidenceDecisionCaptureError(RuntimeError):
    """Raised when a decision cannot be durably captured."""


def auto_capture_completed_backtest(
    *,
    user: User,
    conversation: Conversation,
    run: BacktestRun,
) -> CapturedEvidence:
    finalized = finalize_completed_backtest(
        user_id=user.id,
        conversation_id=conversation.id,
        run=run,
        execution_identity=f"legacy_evidence_capture:{run.id}",
    )
    run.conversation_result_card = dict(finalized.run.conversation_result_card)
    return finalized.captured


def _finalization_input(
    *,
    user_id: str,
    run: BacktestRun,
    execution_identity: str,
) -> BacktestFinalizationInput:
    return BacktestFinalizationInput(
        user_id=user_id,
        execution_identity=execution_identity,
        run=run,
        result_card=dict(run.conversation_result_card),
        idea_id=api_state.store.new_id(),
        idea_version_id=api_state.store.new_id(),
        evidence_artifact_id=api_state.store.new_id(),
        finalized_at=utcnow(),
    )


def _publish_finalized_backtest(
    *,
    user_id: str,
    conversation_id: str | None,
    finalized: FinalizedBacktest,
) -> None:
    if api_state.supabase_gateway is not None:
        try:
            cache_finalized_backtest(
                api_state.store,
                user_id=user_id,
                finalized=finalized,
            )
        except Exception as exc:
            logger.warning(
                "Durable backtest finalized but memory cache refresh failed",
                error=str(exc),
                run_id=finalized.run.id,
            )
    _emit_product_event(
        "evidence_capture",
        user_id=user_id,
        conversation_id=conversation_id,
        backtest_run_id=finalized.run.id,
        status="completed",
        attributes={
            "asset_class": finalized.run.asset_class,
            "symbol_count": len(finalized.run.symbols),
            "benchmark_present": bool(finalized.run.benchmark_symbol),
            "persistence": (
                "supabase" if api_state.supabase_gateway is not None else "memory"
            ),
        },
    )


def finalize_completed_backtest(
    *,
    user_id: str,
    conversation_id: str | None,
    run: BacktestRun,
    execution_identity: str,
) -> FinalizedBacktest:
    gateway = api_state.supabase_gateway or MemoryBacktestFinalizationGateway(
        api_state.store
    )
    finalized = finalize_backtest_completion(
        gateway,
        _finalization_input(
            user_id=user_id,
            run=run,
            execution_identity=execution_identity,
        ),
    )
    _publish_finalized_backtest(
        user_id=user_id,
        conversation_id=conversation_id,
        finalized=finalized,
    )
    return finalized


def finalize_direct_backtest_success(
    *,
    user_id: str,
    conversation_id: str | None,
    run: BacktestRun,
    execution_identity: str,
    job_id: str,
) -> tuple[FinalizedBacktest | None, dict | None]:
    """#230 gateway path: one database transaction locks the owner-scoped
    direct job and either creates/replays the Run/evidence tuple and succeeds
    the job, replays the terminal job with no Run when reconciliation already
    won, or fails closed when the job is missing. The returned final job is
    validated before any Run is exposed."""

    gateway = api_state.supabase_gateway
    if gateway is None:
        raise BacktestFinalizationError(
            "Direct success finalization requires the Supabase gateway."
        )
    prepared = prepare_backtest_finalization(
        _finalization_input(
            user_id=user_id,
            run=run,
            execution_identity=execution_identity,
        )
    )
    try:
        outcome = gateway.finalize_direct_backtest_success(
            job_id=job_id,
            finalization=prepared,
        )
    except Exception as exc:
        raise BacktestFinalizationError("Backtest finalization failed.") from exc

    kind = outcome.get("outcome") if isinstance(outcome, dict) else None
    if kind == "superseded":
        job = outcome.get("job")
        if not isinstance(job, dict):
            raise BacktestFinalizationError(
                "Superseded finalization returned no terminal job."
            )
        return None, dict(job)
    if kind != "finalized":
        # "missing" and any unknown outcome fail closed: no Run exists.
        raise BacktestFinalizationError(
            "Direct backtest job was missing at finalization time."
        )

    try:
        finalized = FinalizedBacktest(
            run=BacktestRun.model_validate(outcome["run"]),
            captured=CapturedEvidence(
                idea=Idea.model_validate(outcome["idea"]),
                idea_version=IdeaVersion.model_validate(outcome["idea_version"]),
                evidence_artifact=EvidenceArtifact.model_validate(
                    outcome["evidence_artifact"]
                ),
            ),
        )
    except Exception as exc:
        raise BacktestFinalizationError(
            "Backtest finalization returned an incomplete tuple."
        ) from exc
    validate_finalized_backtest(finalized)

    final_job = outcome.get("job")
    if (
        not isinstance(final_job, dict)
        or final_job.get("status") != "succeeded"
        or str(final_job.get("result_run_id") or "") != finalized.run.id
    ):
        raise BacktestFinalizationError(
            "Finalized job state does not link the finalized run."
        )

    _publish_finalized_backtest(
        user_id=user_id,
        conversation_id=conversation_id,
        finalized=finalized,
    )
    return finalized, None


def create_decision_for_evidence_artifact(
    *,
    user: User,
    artifact_id: str,
    payload: DecisionNoteCreate,
) -> tuple[DecisionNote, EvidenceArtifact]:
    artifact = _evidence_artifact_for_user(user_id=user.id, artifact_id=artifact_id)
    now = utcnow()
    existing_decision = _decision_for_artifact(
        user_id=user.id,
        artifact_id=artifact.id,
    )
    decision = build_decision_note(
        evidence_artifact=artifact,
        decision_id=existing_decision.id if existing_decision else api_state.store.new_id(),
        decision_state=payload.decision_state,
        note=payload.note,
        now=now,
    )

    artifact = artifact.model_copy(update={"lifecycle": "decided", "updated_at": now})
    idea: Idea | None = None
    idea_version: IdeaVersion | None = None

    if api_state.supabase_gateway is not None:
        try:
            (
                decision,
                artifact,
                idea,
                idea_version,
            ) = api_state.supabase_gateway.capture_current_decision_note(
                user_id=user.id,
                decision=decision,
            )
        except Exception as exc:
            raise EvidenceDecisionCaptureError(
                "Decision capture failed before the decision could be committed."
            ) from exc

    _store_decision_in_memory(
        user_id=user.id,
        decision=decision,
        artifact=artifact,
        idea=idea,
        idea_version=idea_version,
        now=now,
    )
    _attach_decision_to_cached_result_surfaces(
        artifact=artifact,
        decision=decision,
    )

    if api_state.supabase_gateway is not None and artifact.source_run_id:
        try:
            api_state.supabase_gateway.mark_result_card_decision_for_run(
                user_id=user.id,
                run_id=artifact.source_run_id,
                evidence_artifact_id=artifact.id,
                decision_id=decision.id,
                decision_state=decision.decision_state,
            )
        except Exception as exc:
            logger.warning(
                "Supabase decision card enrichment failed after decision commit",
                error=str(exc),
                run_id=artifact.source_run_id,
                evidence_artifact_id=artifact.id,
            )

    _emit_product_event(
        "decision_capture",
        user_id=user.id,
        conversation_id=artifact.source_conversation_id,
        backtest_run_id=artifact.source_run_id,
        status=decision.decision_state,
        attributes={
            "decision_state": decision.decision_state,
            "artifact_lifecycle": artifact.lifecycle,
            "note_present": bool(decision.note),
        },
    )
    return decision, artifact


def _decision_for_artifact(*, user_id: str, artifact_id: str) -> DecisionNote | None:
    for decision in api_state.store.decision_notes.values():
        if (
            decision.evidence_artifact_id == artifact_id
            and api_state.store.decision_note_owners.get(decision.id) == user_id
        ):
            return decision
    if api_state.supabase_gateway is not None:
        decision = api_state.supabase_gateway.get_decision_note_by_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        if decision is not None:
            api_state.store.decision_notes[decision.id] = decision
            api_state.store.decision_note_owners[decision.id] = user_id
            return decision
    return None


def _store_decision_in_memory(
    *,
    user_id: str,
    decision: DecisionNote,
    artifact: EvidenceArtifact,
    idea: Idea | None,
    idea_version: IdeaVersion | None,
    now: datetime,
) -> None:
    api_state.store.decision_notes[decision.id] = decision
    api_state.store.decision_note_owners[decision.id] = user_id
    api_state.store.evidence_artifacts[artifact.id] = artifact
    api_state.store.evidence_artifact_owners[artifact.id] = user_id
    if idea is not None:
        api_state.store.ideas[idea.id] = idea
        api_state.store.idea_owners[idea.id] = user_id
    if idea_version is not None:
        api_state.store.idea_versions[idea_version.id] = idea_version
        api_state.store.idea_version_owners[idea_version.id] = user_id
    if idea is None:
        stored_idea = api_state.store.ideas.get(artifact.idea_id)
        if stored_idea is not None:
            api_state.store.ideas[stored_idea.id] = stored_idea.model_copy(
                update={"lifecycle": "decided", "updated_at": now}
            )
            api_state.store.idea_owners[stored_idea.id] = user_id
    if idea_version is None:
        stored_version = api_state.store.idea_versions.get(artifact.idea_version_id)
        if stored_version is not None:
            api_state.store.idea_versions[stored_version.id] = stored_version.model_copy(
                update={"lifecycle": "decided"}
            )
            api_state.store.idea_version_owners[stored_version.id] = user_id


def _attach_decision_to_cached_result_surfaces(
    *,
    artifact: EvidenceArtifact,
    decision: DecisionNote,
) -> None:
    run_id = artifact.source_run_id
    if run_id:
        run = api_state.store.backtest_runs.get(run_id)
        if run is not None:
            run.conversation_result_card = attach_decision_to_result_card(
                dict(run.conversation_result_card),
                decision_id=decision.id,
                decision_state=decision.decision_state,
            )

    for conversation_id, messages in list(api_state.store.messages.items()):
        updated_messages = []
        changed = False
        for message in messages:
            metadata = dict(message.metadata or {})
            result_card = metadata.get("result_card")
            if not isinstance(result_card, dict):
                updated_messages.append(message)
                continue
            is_matching_run = bool(
                run_id
                and (
                    metadata.get("result_run_id") == run_id
                    or metadata.get("latest_run_id") == run_id
                )
            )
            is_matching_artifact = result_card.get("evidence_artifact_id") == artifact.id
            if not is_matching_run and not is_matching_artifact:
                updated_messages.append(message)
                continue
            metadata["result_card"] = attach_decision_to_result_card(
                result_card,
                decision_id=decision.id,
                decision_state=decision.decision_state,
            )
            metadata["decision_note_id"] = decision.id
            metadata["decision_state"] = decision.decision_state
            updated_messages.append(message.model_copy(update={"metadata": metadata}))
            changed = True
        if changed:
            api_state.store.messages[conversation_id] = updated_messages


def _evidence_artifact_for_user(*, user_id: str, artifact_id: str) -> EvidenceArtifact:
    with api_state.store.backtest_finalization_lock:
        artifact = api_state.store.evidence_artifacts.get(artifact_id)
        if (
            artifact is not None
            and api_state.store.evidence_artifact_owners.get(artifact_id) == user_id
        ):
            return artifact
    if api_state.supabase_gateway is not None:
        fetched = api_state.supabase_gateway.get_evidence_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
        if fetched is not None:
            api_state.store.evidence_artifacts[fetched.id] = fetched
            api_state.store.evidence_artifact_owners[fetched.id] = user_id
            return fetched
    raise EvidenceArtifactNotFoundError(
        "Evidence artifact not found or not owned by user."
    )
