"""Typed `retest_run` admission, receipt projection, and turn completion.

The client submits identity and policy only. Everything executable is reloaded
from the owner-scoped stored run, so a tampered payload cannot change or expose
canonical state, and no provider is consulted before the user confirms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import Request

from argus.agent_runtime.confirmation_artifacts import confirmation_artifact_reference
from argus.agent_runtime.recovery_messages import recovery_message, recovery_state
from argus.agent_runtime.retest_confirmation import (
    retest_confirmation_payload,
    retest_runtime_result,
)
from argus.api.chat import retry as chat_retry
from argus.api.chat.confirmation import (
    public_confirmation_projection,
    runtime_confirmation_card,
)
from argus.api.chat.recovery import _run_by_id_for_user
from argus.api.chat.turn_lifecycle_hooks import ChatTurnLifecycleHooks
from argus.api.dependencies import problem
from argus.api.schemas import ChatStreamRequest, Message
from argus.domain.retest_setup import (
    RETEST_CONTRACT_VERSION,
    RETEST_WINDOW_POLICY,
    RetestSetup,
    has_finalized_evidence_identity,
    retest_setup_from_run,
)

RETEST_ACTION_TYPE = "retest_run"
RETEST_ACTION_LABEL_KEY = "command_palette.retest_current_data"
_ENVELOPE_KEYS = frozenset({"source_run_id", "window_policy", "contract_version"})
# The canonical finalizer refuses to complete a run whose result card lacks
# these, so their presence is the durable marker of a finalized artifact.
_DAYS_PER_YEAR = 365
_DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class RetestTurn:
    """Everything the accepted turn needs, resolved before the turn is admitted."""

    source_run_id: str
    setup: RetestSetup
    confirmation_payload: dict[str, Any]
    receipt: dict[str, Any]


def is_retest_action(payload: ChatStreamRequest) -> bool:
    return payload.action is not None and payload.action.type == RETEST_ACTION_TYPE


def retest_action_source_run_id(action_payload: Mapping[str, Any]) -> str | None:
    """Accept only the bounded v1 envelope; anything else is client authority."""
    if set(action_payload) - _ENVELOPE_KEYS:
        return None
    if action_payload.get("contract_version") != RETEST_CONTRACT_VERSION:
        return None
    if action_payload.get("window_policy") != RETEST_WINDOW_POLICY:
        return None
    source_run_id = action_payload.get("source_run_id")
    if not isinstance(source_run_id, str):
        return None
    try:
        # Run ids are UUIDs in both storage modes. Rejecting other shapes here
        # keeps a tampered id on the uniform invalid-state path instead of
        # reaching Postgres and surfacing a cast error as a 500. The canonical
        # form is what is returned: the parser also accepts URN, braced,
        # hyphenless, and uppercase spellings that Postgres rejects or stores
        # canonically, and the memory store keys runs by exact string.
        return str(UUID(source_run_id.strip()))
    except ValueError:
        return None


def sanitized_retest_action(source_run_id: str) -> dict[str, Any]:
    """Backend-owned action record; client display copy never reaches storage."""
    return {
        "type": RETEST_ACTION_TYPE,
        "label": None,
        "labelKey": RETEST_ACTION_LABEL_KEY,
        "payload": {
            "source_run_id": source_run_id,
            "window_policy": RETEST_WINDOW_POLICY,
            "contract_version": RETEST_CONTRACT_VERSION,
        },
        "presentation": None,
    }


def retest_receipt(setup: RetestSetup) -> dict[str, Any]:
    """Structured display context; the transcript localizes it on render."""
    receipt: dict[str, Any] = {
        "contract_version": RETEST_CONTRACT_VERSION,
        "window_policy": RETEST_WINDOW_POLICY,
        "source_run_id": setup.source_run_id,
        "symbols": list(setup.symbols),
        "strategy_family": setup.strategy_type,
        "timeframe": setup.timeframe,
        "duration_days": setup.duration_days,
        "duration": _duration_descriptor(setup.duration_days),
    }
    if setup.cadence is not None:
        receipt["cadence"] = setup.cadence
    return receipt


def prepare_retest_turn(
    *,
    payload: ChatStreamRequest,
    request: Request,
    user_id: str,
    conversation_id: str,
    language: str | None,
    today: date | None = None,
    confirmation_id: str | None = None,
) -> RetestTurn | None:
    """Resolve canonical truth before admission, or reject as invalid state."""
    if not is_retest_action(payload) or payload.action is None:
        return None
    source_run_id = retest_action_source_run_id(payload.action.payload)
    setup = (
        _owned_retest_setup(
            user_id=user_id,
            conversation_id=conversation_id,
            source_run_id=source_run_id,
            today=today or date.today(),
        )
        if source_run_id is not None
        else None
    )
    confirmation_payload = (
        retest_confirmation_payload(
            setup,
            language=language or "en",
            confirmation_id=confirmation_id,
        )
        if setup is not None
        else None
    )
    if setup is None or confirmation_payload is None:
        raise problem(
            request,
            status_code=409,
            code="artifact_action_invalid_state",
            title="Action No Longer Active",
            detail=recovery_message("artifact_action_invalid_state", language=language),
        )
    return RetestTurn(
        source_run_id=setup.source_run_id,
        setup=setup,
        confirmation_payload=confirmation_payload,
        receipt=retest_receipt(setup),
    )


def complete_retest_turn(
    *,
    turn: RetestTurn,
    lifecycle_hooks: ChatTurnLifecycleHooks,
    conversation_id: str,
    language: str,
    settle_usage: Any = None,
) -> dict[str, Any]:
    """Persist the confirmation artifact and stop; the user still approves."""
    payload = turn.confirmation_payload
    confirmation_id = str(payload["confirmation_id"])
    card = runtime_confirmation_card(
        retest_runtime_result(payload),
        confirmation_id=confirmation_id,
        conversation_id=conversation_id,
        language=language,
    )
    if card is None:
        raise RuntimeError("retest_confirmation_card_unavailable")
    reference = confirmation_artifact_reference(
        confirmation_id=confirmation_id,
        confirmation_payload=payload,
        confirmation_card=card,
    ).model_dump(mode="python")
    metadata: dict[str, Any] = {
        "conversation_mode": "confirm",
        "agent_runtime_stage_outcome": "await_approval",
        "chat_action": sanitized_retest_action(turn.source_run_id),
        "retest_receipt": dict(turn.receipt),
        "confirmation_card": card,
        "confirmation_payload": payload,
        "active_confirmation_reference": reference,
        "artifact_references": [reference],
    }
    assistant_message = lifecycle_hooks.complete(
        content=str(card["summary"]),
        metadata=metadata,
        settle_usage=settle_usage,
    )
    return public_confirmation_projection(
        {
            "stage_outcome": "await_approval",
            "message_id": assistant_message.id,
            "confirmation": card,
            "confirmation_payload": payload,
            "active_confirmation_reference": reference,
            "artifact_references": [reference],
            "retest_receipt": dict(turn.receipt),
        }
    )


def failed_retest_turn(
    *,
    turn: RetestTurn,
    lifecycle_hooks: ChatTurnLifecycleHooks,
    request_message: Message,
    language: str,
) -> dict[str, Any]:
    """Map a transient materialization failure onto the shipped amber retry."""
    assistant_text = recovery_message("runtime_failure", language=language)
    recovery = recovery_state("runtime_failure", language=language, retryable=True)
    failure_metadata: dict[str, Any] = {
        "conversation_mode": "recovery",
        "agent_runtime_stage_outcome": "agent_runtime_failure",
        "failure_code": "agent_runtime_failure",
        "retryable": True,
        "recovery": recovery,
        "retest_receipt": dict(turn.receipt),
        **chat_retry.durable_retry_last_turn_metadata(request_message),
    }
    assistant_message = lifecycle_hooks.recoverable_failure(
        content=assistant_text,
        metadata=failure_metadata,
        failure_code="agent_runtime_failure",
        retryable=True,
    )
    durable_retry = (
        assistant_message.metadata.get("retry_last_turn")
        if isinstance(assistant_message.metadata, dict)
        else None
    )
    payload: dict[str, Any] = {
        # `ready_to_respond` keeps an unrelated open confirmation intact; the
        # failure belongs to this turn only.
        "stage_outcome": "ready_to_respond",
        "assistant_response": assistant_text,
        "message_id": assistant_message.id,
        "recovery": recovery,
        "retest_receipt": dict(turn.receipt),
    }
    if isinstance(durable_retry, dict):
        # Live frame carries the message-shaped retry so the amber assistant
        # recovery block owns it; hydration rebuilds the anchored shape from
        # the persisted request-linked metadata.
        payload["retry_last_turn"] = {
            key: durable_retry[key]
            for key in ("message", "action")
            if key in durable_retry
        }
    return payload


def _owned_retest_setup(
    *,
    user_id: str,
    conversation_id: str,
    source_run_id: str,
    today: date,
) -> RetestSetup | None:
    run = _run_by_id_for_user(user_id=user_id, run_id=source_run_id)
    if (
        run is None
        or run.conversation_id != conversation_id
        or run.status != "completed"
        or not has_finalized_evidence_identity(run.conversation_result_card)
    ):
        # One uniform outcome for missing, foreign, unfinished, and
        # cross-conversation runs so the caller cannot probe object existence.
        return None
    return retest_setup_from_run(run.model_dump(mode="python"), today=today)


def _duration_descriptor(duration_days: int) -> dict[str, Any]:
    if duration_days >= _DAYS_PER_YEAR and duration_days % _DAYS_PER_YEAR == 0:
        return {"unit": "year", "count": duration_days // _DAYS_PER_YEAR}
    if duration_days >= _DAYS_PER_MONTH and duration_days % _DAYS_PER_MONTH == 0:
        return {"unit": "month", "count": duration_days // _DAYS_PER_MONTH}
    return {"unit": "day", "count": duration_days}
