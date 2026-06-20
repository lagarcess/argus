from __future__ import annotations

from datetime import datetime

from loguru import logger

from argus.api import state as api_state
from argus.api.dependencies import dev_memory_fallback_enabled
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
from argus.domain.evidence import (
    CapturedEvidence,
    attach_decision_to_result_card,
    build_backtest_evidence_capture,
    build_decision_note,
)
from argus.domain.store import utcnow


def auto_capture_completed_backtest(
    *,
    user: User,
    conversation: Conversation,
    run: BacktestRun,
) -> CapturedEvidence:
    existing = _existing_capture_for_run(user_id=user.id, run_id=run.id)
    if existing is not None:
        _attach_capture_to_result_card(run=run, captured=existing)
        _persist_result_card_capture(user_id=user.id, run=run)
        return existing

    captured = build_backtest_evidence_capture(
        run=run,
        idea_id=api_state.store.new_id(),
        idea_version_id=api_state.store.new_id(),
        evidence_artifact_id=api_state.store.new_id(),
        now=utcnow(),
    )
    supabase_capture_persisted = False

    if api_state.supabase_gateway is not None:
        try:
            captured = api_state.supabase_gateway.create_backtest_evidence_capture(
                user_id=user.id,
                captured=captured,
            )
            _store_capture_in_memory(user_id=user.id, captured=captured)
            supabase_capture_persisted = True
        except Exception as exc:
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase evidence capture failed; using dev memory fallback",
                error=str(exc),
                run_id=run.id,
            )
            _store_capture_in_memory(user_id=user.id, captured=captured)
    else:
        _store_capture_in_memory(user_id=user.id, captured=captured)

    _attach_capture_to_result_card(run=run, captured=captured)
    if supabase_capture_persisted:
        _persist_result_card_capture(user_id=user.id, run=run)
    return captured


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
        (
            decision,
            artifact,
            idea,
            idea_version,
        ) = api_state.supabase_gateway.capture_current_decision_note(
            user_id=user.id,
            decision=decision,
        )

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
            if not dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase decision card enrichment failed; using in-memory state",
                error=str(exc),
                run_id=artifact.source_run_id,
                evidence_artifact_id=artifact.id,
            )

    return decision, artifact


def _existing_capture_for_run(*, user_id: str, run_id: str) -> CapturedEvidence | None:
    for artifact in api_state.store.evidence_artifacts.values():
        if (
            artifact.source_run_id == run_id
            and api_state.store.evidence_artifact_owners.get(artifact.id) == user_id
        ):
            idea = api_state.store.ideas.get(artifact.idea_id)
            version = api_state.store.idea_versions.get(artifact.idea_version_id)
            if idea is not None and version is not None:
                return CapturedEvidence(
                    idea=idea,
                    idea_version=version,
                    evidence_artifact=artifact,
                )
    if api_state.supabase_gateway is not None:
        captured = api_state.supabase_gateway.get_evidence_capture_by_run(
            user_id=user_id,
            run_id=run_id,
        )
        if captured is not None:
            _store_capture_in_memory(user_id=user_id, captured=captured)
            return captured
    return None


def _store_capture_in_memory(*, user_id: str, captured: CapturedEvidence) -> None:
    api_state.store.ideas[captured.idea.id] = captured.idea
    api_state.store.idea_owners[captured.idea.id] = user_id
    api_state.store.idea_versions[captured.idea_version.id] = captured.idea_version
    api_state.store.idea_version_owners[captured.idea_version.id] = user_id
    api_state.store.evidence_artifacts[captured.evidence_artifact.id] = (
        captured.evidence_artifact
    )
    api_state.store.evidence_artifact_owners[captured.evidence_artifact.id] = user_id


def _persist_result_card_capture(*, user_id: str, run: BacktestRun) -> None:
    if api_state.supabase_gateway is None:
        return
    try:
        api_state.supabase_gateway.update_backtest_run_result_card(
            user_id=user_id,
            run_id=run.id,
            conversation_result_card=run.conversation_result_card,
        )
    except Exception as exc:
        if not dev_memory_fallback_enabled():
            raise
        logger.warning(
            "Supabase evidence card enrichment failed; using in-memory card",
            error=str(exc),
            run_id=run.id,
        )


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


def _attach_capture_to_result_card(
    *, run: BacktestRun, captured: CapturedEvidence
) -> None:
    card = dict(run.conversation_result_card)
    card["idea_id"] = captured.idea.id
    card["idea_version_id"] = captured.idea_version.id
    card["evidence_artifact_id"] = captured.evidence_artifact.id
    card["evidence_lifecycle"] = captured.evidence_artifact.lifecycle
    card["artifact_type"] = "backtest"
    actions = card.get("actions")
    if isinstance(actions, list):
        enriched_actions: list[dict[str, object]] = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            payload = dict(action.get("payload") or {})
            payload.update(
                {
                    "idea_id": captured.idea.id,
                    "idea_version_id": captured.idea_version.id,
                    "evidence_artifact_id": captured.evidence_artifact.id,
                }
            )
            enriched_actions.append({**action, "payload": payload})
        card["actions"] = enriched_actions
    run.conversation_result_card = card


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
    raise ValueError("Evidence artifact not found or not owned by user.")
