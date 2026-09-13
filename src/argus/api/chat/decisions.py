"""Decisions on computed answers, and opening any decision.

A backtest decision is captured through ``argus.api.chat.evidence`` because it
moves an artifact spine. A computed answer is an assistant message that
declares ``metadata.computation``; its decision attaches to that message and
stores the computation, so opening it later re-runs the answer from the
inputs the decision carries. Opening a backtest decision derives its
computation from the artifact and offers the typed retest instead of
executing anything.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from argus.api import state as api_state
from argus.api.chat.evidence import _emit_product_event
from argus.api.decision_contract import (
    DecisionComputation,
    DecisionNote,
    DecisionNoteCreate,
    DecisionRerun,
)
from argus.api.message_store import owned_conversation_message
from argus.api.schemas import EvidenceArtifact, User
from argus.domain.computations import (
    InvalidComputationInputs,
    RerunContext,
    rerun_computation,
    unavailable_rerun,
)
from argus.domain.decision_attachment import (
    computation_from_message_metadata,
    decision_computation,
)
from argus.domain.market_data.new_york_clock import new_york_today
from argus.domain.store import utcnow


class DecisionNotFoundError(LookupError):
    """The decision is absent or not owned by the user."""


class DecisionMessageNotFoundError(LookupError):
    """The message is absent, not owned by the user, or not in the conversation."""


class DecisionAttachmentUnsupportedError(ValueError):
    """The message declares no computation, so there is nothing to decide on."""


class DecisionCaptureError(RuntimeError):
    """The decision could not be durably captured."""


class DecisionRerunInputsError(ValueError):
    """Client-supplied input overrides failed the kernel's typed model."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Re-run inputs are invalid.")
        self.errors = errors


def create_decision_for_message(
    *,
    user: User,
    conversation_id: str,
    message_id: str,
    payload: DecisionNoteCreate,
) -> DecisionNote:
    message = owned_conversation_message(
        user_id=user.id,
        conversation_id=conversation_id,
        message_id=message_id,
    )
    if message is None or message.role != "assistant":
        raise DecisionMessageNotFoundError("Message not found or not owned by user.")
    computation = computation_from_message_metadata(message.metadata)
    if computation is None:
        raise DecisionAttachmentUnsupportedError(
            "This answer carries no computation to decide on."
        )

    now = utcnow()
    existing = _decision_for_message(user_id=user.id, message_id=message.id)
    decision = DecisionNote(
        id=existing.id if existing is not None else api_state.store.new_id(),
        source_conversation_id=conversation_id,
        source_message_id=message.id,
        computation=existing.computation if existing is not None else computation,
        decision_state=payload.decision_state,
        note=payload.note,
        created_at=existing.created_at if existing is not None else now,
        updated_at=now,
    )
    if api_state.supabase_gateway is not None:
        try:
            decision = api_state.supabase_gateway.upsert_message_decision_note(
                user_id=user.id,
                decision=decision,
            )
        except Exception as exc:
            raise DecisionCaptureError(
                "Decision capture failed before the decision could be committed."
            ) from exc
    api_state.store.decision_notes[decision.id] = decision
    api_state.store.decision_note_owners[decision.id] = user.id
    # The transcript read derives the answer's decision from decision_notes,
    # so no second copy is written onto the message.
    api_state.store.bump_search_revision()

    _emit_product_event(
        "decision_capture",
        user_id=user.id,
        conversation_id=conversation_id,
        status=decision.decision_state,
        attributes={
            "decision_state": decision.decision_state,
            "attachment": "message",
            "computation_kind": decision.computation.kind
            if decision.computation is not None
            else None,
            "note_present": bool(decision.note),
        },
    )
    return decision


def open_decision(
    *,
    user: User,
    decision_id: str,
    overrides: Mapping[str, Any] | None = None,
) -> tuple[DecisionNote, DecisionComputation, DecisionRerun]:
    """Load a decision and re-run its computation, with optional overrides.

    Overrides that fail the kernel's typed model are a client error; stored
    inputs that fail it are a typed unavailable state, because the row, not
    the request, is what drifted.
    """
    decision = _decision_by_id(user_id=user.id, decision_id=decision_id)
    if decision is None:
        raise DecisionNotFoundError("Decision not found or not owned by user.")
    artifact = (
        _artifact_for_decision(user_id=user.id, decision=decision)
        if decision.evidence_artifact_id is not None
        else None
    )
    computation = decision_computation(decision, artifact=artifact)
    context = RerunContext(load_run=_run_loader(user.id), today=new_york_today())
    try:
        rerun = rerun_computation(computation, overrides=overrides, context=context)
    except InvalidComputationInputs as exc:
        if overrides:
            raise DecisionRerunInputsError(exc.errors) from exc
        rerun = unavailable_rerun(computation, reason_code="invalid_inputs")
    return decision, computation, rerun


def _decision_by_id(*, user_id: str, decision_id: str) -> DecisionNote | None:
    decision = api_state.store.decision_notes.get(decision_id)
    if (
        decision is not None
        and api_state.store.decision_note_owners.get(decision_id) == user_id
    ):
        return decision
    if api_state.supabase_gateway is not None:
        fetched = api_state.supabase_gateway.get_decision_note(
            user_id=user_id,
            decision_id=decision_id,
        )
        if fetched is not None:
            api_state.store.decision_notes[fetched.id] = fetched
            api_state.store.decision_note_owners[fetched.id] = user_id
            return fetched
    return None


def _decision_for_message(*, user_id: str, message_id: str) -> DecisionNote | None:
    for decision in api_state.store.decision_notes.values():
        if (
            decision.source_message_id == message_id
            and api_state.store.decision_note_owners.get(decision.id) == user_id
        ):
            return decision
    if api_state.supabase_gateway is not None:
        fetched = api_state.supabase_gateway.get_decision_note_by_message(
            user_id=user_id,
            message_id=message_id,
        )
        if fetched is not None:
            api_state.store.decision_notes[fetched.id] = fetched
            api_state.store.decision_note_owners[fetched.id] = user_id
            return fetched
    return None


def _artifact_for_decision(
    *, user_id: str, decision: DecisionNote
) -> EvidenceArtifact | None:
    artifact_id = decision.evidence_artifact_id
    if artifact_id is None:
        return None
    artifact = api_state.store.evidence_artifacts.get(artifact_id)
    if (
        artifact is not None
        and api_state.store.evidence_artifact_owners.get(artifact_id) == user_id
    ):
        return artifact
    if api_state.supabase_gateway is not None:
        return api_state.supabase_gateway.get_evidence_artifact(
            user_id=user_id,
            artifact_id=artifact_id,
        )
    return None


def _run_loader(user_id: str) -> Callable[[str], Mapping[str, Any] | None]:
    def load_run(run_id: str) -> Mapping[str, Any] | None:
        run = api_state.store.backtest_runs.get(run_id)
        if run is not None and api_state.store.backtest_run_owners.get(run_id) == user_id:
            return _run_row(run)
        if api_state.supabase_gateway is not None:
            fetched = api_state.supabase_gateway.get_backtest_run(
                user_id=user_id,
                run_id=run_id,
            )
            if fetched is not None:
                return _run_row(fetched)
        return None

    return load_run


def _run_row(run: object) -> Mapping[str, Any]:
    if isinstance(run, Mapping):
        return run
    model_dump = getattr(run, "model_dump", None)
    dumped = model_dump(mode="python") if callable(model_dump) else {}
    return dumped if isinstance(dumped, Mapping) else {}
