from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from argus.api import state as api_state
from argus.api.chat.actions import chat_display_message, persisted_chat_action
from argus.api.chat.recovery import _recent_messages_for_conversation
from argus.api.chat.retest import (
    RETEST_ACTION_LABEL_KEY,
    complete_retest_turn,
    failed_retest_turn,
    is_retest_action,
    prepare_retest_turn,
    retest_action_source_run_id,
    retest_receipt,
    sanitized_retest_action,
)
from argus.api.chat.turn_lifecycle_hooks import ChatTurnLifecycleHooks
from argus.api.message_store import create_message, prepare_message
from argus.api.schemas import ChatActionPayload, ChatStreamRequest
from argus.domain.retest_setup import retest_setup_from_run
from fastapi import HTTPException

_USER_ID = "retest-owner"
_OTHER_USER_ID = "retest-intruder"
_CONVERSATION_ID = "retest-conversation"
_TODAY = date(2026, 7, 31)
_SOURCE_RUN_ID = "8f14e45f-ea1c-4b3a-9d2f-1a2b3c4d5e6f"
_MISSING_RUN_ID = "00000000-0000-4000-8000-000000000000"
_BUY_AND_HOLD = {
    "strategy_type": "buy_and_hold",
    "symbol": "TSLA",
    "timeframe": "1D",
    "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
    "entry_rule": None,
    "exit_rule": None,
    "sizing_mode": "capital_amount",
    "capital_amount": 10_000.0,
    "position_size": None,
    "cadence": None,
    "parameters": {},
    "risk_rules": [],
    "benchmark_symbol": "SPY",
}


class _FakeRequest:
    def __init__(self) -> None:
        self.state = type("State", (), {"request_id": "retest-request"})()
        self.url = type("Url", (), {"path": "/api/v1/chat/stream"})()


def _valid_envelope(source_run_id: str = _SOURCE_RUN_ID) -> dict[str, Any]:
    return {
        "source_run_id": source_run_id,
        "window_policy": "preserve_start_ending_latest_available",
        "contract_version": "argus_retest_run/v2",
    }


def _legacy_envelope(source_run_id: str = _SOURCE_RUN_ID) -> dict[str, Any]:
    return {
        "source_run_id": source_run_id,
        "window_policy": "same_duration_ending_today",
        "contract_version": "argus_retest_run/v1",
    }


def _retest_request(
    action_payload: dict[str, Any],
    *,
    conversation_id: str = _CONVERSATION_ID,
    label: str | None = None,
    label_key: str = RETEST_ACTION_LABEL_KEY,
    language: str | None = None,
) -> ChatStreamRequest:
    # `retest_run` joins ChatActionType with the dossier-lane schema
    # reconciliation; the transport shape under test is already final.
    action = ChatActionPayload.model_construct(
        type="retest_run",
        label=label,
        label_key=label_key,
        payload=action_payload,
        presentation=None,
    )
    return ChatStreamRequest.model_construct(
        conversation_id=conversation_id,
        message=None,
        action=action,
        mentions=[],
        language=language,
    )


@pytest.fixture
def stored_run() -> Any:
    from argus.api.chat.persistence import build_runtime_backtest_run
    from argus.domain.engine_launch.adapter import run_launch_backtest
    from argus.domain.engine_launch.models import LaunchBacktestRequest

    launch = run_launch_backtest(LaunchBacktestRequest.model_validate(_BUY_AND_HOLD))
    run = build_runtime_backtest_run(
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        result_card=launch.result_card,
        envelope=launch.envelope.model_dump(mode="python"),
        default_benchmark_func=lambda _asset_class, _symbols: "SPY",
        run_id=_SOURCE_RUN_ID,
    )
    assert run is not None
    run = run.model_copy(
        update={
            "conversation_result_card": {
                **run.conversation_result_card,
                "evidence_artifact_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3301",
                "idea_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3302",
                "idea_version_id": "3f2504e0-4f89-41d3-9a0c-0305e82c3303",
            }
        }
    )
    api_state.store.backtest_runs[run.id] = run
    api_state.store.backtest_run_owners[run.id] = _USER_ID
    yield run
    api_state.store.backtest_runs.pop(run.id, None)
    api_state.store.backtest_run_owners.pop(run.id, None)


def _lifecycle_hooks() -> ChatTurnLifecycleHooks:
    request_message = create_message(
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        role="user",
        content="Retest with current data",
        metadata={
            "chat_action": sanitized_retest_action(_SOURCE_RUN_ID),
            "retest_receipt": {"source_run_id": _SOURCE_RUN_ID},
        },
    )
    return ChatTurnLifecycleHooks(
        owner="message_only",
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        request_id="retest-request",
        request_message=request_message,
    )


def test_exact_legacy_and_current_envelopes_are_accepted() -> None:
    assert retest_action_source_run_id(_valid_envelope()) == _SOURCE_RUN_ID
    assert retest_action_source_run_id(_legacy_envelope()) == _SOURCE_RUN_ID


@pytest.mark.parametrize(
    "action_payload",
    [
        {**_valid_envelope(), "symbols": ["NVDA"]},
        {**_valid_envelope(), "date_range": {"start": "2020-01-01"}},
        {**_valid_envelope(), "window_policy": "since_ipo"},
        {**_valid_envelope(), "contract_version": "argus_retest_run/v3"},
        {
            **_valid_envelope(),
            "contract_version": "argus_retest_run/v1",
        },
        {
            **_legacy_envelope(),
            "contract_version": "argus_retest_run/v2",
        },
    ],
    ids=[
        "extra-symbol-authority",
        "extra-date-authority",
        "unknown-policy",
        "unknown-version",
        "legacy-version-current-policy",
        "current-version-legacy-policy",
    ],
)
def test_unknown_crossed_or_authoritative_envelopes_are_rejected(
    action_payload: dict[str, Any],
) -> None:
    assert retest_action_source_run_id(action_payload) is None


def test_invalid_source_run_ids_are_rejected_or_canonicalized() -> None:
    assert retest_action_source_run_id({**_valid_envelope(), "source_run_id": " "}) is None
    # A non-UUID id would reach Postgres and raise a cast error, breaking the
    # uniform invalid-state contract with a 500.
    for tampered in ("not-a-uuid", "1 OR 1=1", "8f14e45f-ea1c-4b3a-9d2f"):
        assert (
            retest_action_source_run_id(
                {**_valid_envelope(), "source_run_id": tampered}
            )
            is None
        ), tampered
    # Python's UUID parser accepts URN, braced, hyphenless, and uppercase forms
    # that Postgres either rejects outright or stores canonically, so the id
    # handed on must be the canonical form rather than whatever was submitted.
    for variant in (
        f"urn:uuid:{_SOURCE_RUN_ID}",
        "{" + _SOURCE_RUN_ID + "}",
        _SOURCE_RUN_ID.replace("-", ""),
        _SOURCE_RUN_ID.upper(),
    ):
        assert (
            retest_action_source_run_id(
                {**_valid_envelope(), "source_run_id": variant}
            )
            == _SOURCE_RUN_ID
        ), variant


@pytest.mark.parametrize(
    "action_payload",
    [_valid_envelope(), _legacy_envelope()],
    ids=["current", "legacy"],
)
def test_client_display_copy_never_reaches_storage(
    action_payload: dict[str, Any],
) -> None:
    payload = _retest_request(
        action_payload,
        label="Delete everything",
        label_key="chat.result_card.save",
    )

    assert is_retest_action(payload)
    assert persisted_chat_action(payload) == {
        "type": "retest_run",
        "label": None,
        "labelKey": RETEST_ACTION_LABEL_KEY,
        "payload": {
            "source_run_id": _SOURCE_RUN_ID,
            "window_policy": "preserve_start_ending_latest_available",
            "contract_version": "argus_retest_run/v2",
        },
        "presentation": None,
    }
    assert chat_display_message(payload, language="en") == "Retest with current data"
    assert (
        chat_display_message(payload, language="es-419")
        == "Volver a probar con datos actuales"
    )


def test_receipt_carries_structured_values_not_prose(stored_run: Any) -> None:
    setup = retest_setup_from_run(
        stored_run.model_dump(mode="python"),
        today=_TODAY,
    )
    assert setup is not None

    receipt = retest_receipt(setup)

    assert receipt == {
        "contract_version": "argus_retest_run/v2",
        "window_policy": "preserve_start_ending_latest_available",
        "source_run_id": _SOURCE_RUN_ID,
        "symbols": ["TSLA"],
        "strategy_family": "buy_and_hold",
        "timeframe": "1D",
        "duration_days": 365,
        "duration": {"unit": "year", "count": 1},
    }


@pytest.mark.parametrize(
    "action_payload",
    [_valid_envelope(), _legacy_envelope()],
    ids=["current", "legacy"],
)
def test_admission_reloads_canonical_truth_from_the_owned_run(
    stored_run: Any,
    action_payload: dict[str, Any],
) -> None:
    turn = prepare_retest_turn(
        payload=_retest_request(action_payload),
        request=_FakeRequest(),
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        language="en",
        today=_TODAY,
        confirmation_id="confirmation-retest",
    )

    assert turn is not None
    assert turn.setup.start == date(2024, 1, 1)
    assert turn.setup.end == _TODAY
    assert turn.confirmation_payload["confirmation_id"] == "confirmation-retest"
    assert turn.confirmation_payload["launch_payload"]["symbols"] == ["TSLA"]


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("unknown_run", "deleted or unknown source"),
        ("foreign_owner", "another owner's run"),
        ("other_conversation", "cross-conversation replay"),
        ("unfinished_run", "run that never finalized"),
        ("unfinalized_evidence", "completed row whose evidence never finalized"),
        ("tampered_envelope", "client-authored executable fields"),
    ],
)
def test_unusable_sources_reject_as_non_retryable_invalid_state(
    stored_run: Any,
    case: str,
    reason: str,
) -> None:
    user_id = _OTHER_USER_ID if case == "foreign_owner" else _USER_ID
    conversation_id = (
        "another-conversation" if case == "other_conversation" else _CONVERSATION_ID
    )
    action_payload = (
        {**_valid_envelope(_SOURCE_RUN_ID), "symbols": ["NVDA"]}
        if case == "tampered_envelope"
        else _valid_envelope(
            _MISSING_RUN_ID if case == "unknown_run" else _SOURCE_RUN_ID
        )
    )
    if case == "unfinished_run":
        api_state.store.backtest_runs[stored_run.id] = stored_run.model_copy(
            update={"status": "running"}
        )
    if case == "unfinalized_evidence":
        card = {
            key: value
            for key, value in stored_run.conversation_result_card.items()
            if key != "evidence_artifact_id"
        }
        api_state.store.backtest_runs[stored_run.id] = stored_run.model_copy(
            update={"conversation_result_card": card}
        )

    with pytest.raises(HTTPException) as excinfo:
        prepare_retest_turn(
            payload=_retest_request(action_payload, conversation_id=conversation_id),
            request=_FakeRequest(),
            user_id=user_id,
            conversation_id=conversation_id,
            language="en",
            today=_TODAY,
        )

    assert excinfo.value.status_code == 409, reason
    assert excinfo.value.detail["code"] == "artifact_action_invalid_state"


def test_ordinary_turns_are_not_retest_turns() -> None:
    payload = ChatStreamRequest.model_validate(
        {"conversation_id": _CONVERSATION_ID, "message": "test gold again"}
    )

    assert is_retest_action(payload) is False
    assert (
        prepare_retest_turn(
            payload=payload,
            request=_FakeRequest(),
            user_id=_USER_ID,
            conversation_id=_CONVERSATION_ID,
            language="en",
            today=_TODAY,
        )
        is None
    )


def test_completed_turn_persists_a_ready_to_run_confirmation(
    stored_run: Any,
) -> None:
    turn = prepare_retest_turn(
        payload=_retest_request(_valid_envelope(_SOURCE_RUN_ID)),
        request=_FakeRequest(),
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        language="en",
        today=_TODAY,
        confirmation_id="confirmation-retest",
    )
    assert turn is not None

    final_payload = complete_retest_turn(
        turn=turn,
        lifecycle_hooks=_lifecycle_hooks(),
        conversation_id=_CONVERSATION_ID,
        language="en",
    )

    assert final_payload["stage_outcome"] == "await_approval"
    assert final_payload["confirmation"]["status"] == "ready_to_run"
    assert final_payload["retest_receipt"]["symbols"] == ["TSLA"]
    assert "run" not in final_payload and "result_card" not in final_payload
    # Private durable identity stays out of transport.
    assert "canonical_launch_payload_hash" not in final_payload["confirmation"]
    persisted = next(
        message
        for message in _recent_messages_for_conversation(
            user_id=_USER_ID,
            conversation_id=_CONVERSATION_ID,
            limit=20,
        )
        if message.id == final_payload["message_id"]
    )
    assert persisted.metadata["confirmation_card"]["status"] == "ready_to_run"
    assert persisted.metadata["retest_receipt"]["duration_days"] == 365
    assert persisted.metadata["chat_action"]["labelKey"] == RETEST_ACTION_LABEL_KEY
    assert persisted.metadata["confirmation_payload"]["launch_payload"]["symbols"] == [
        "TSLA"
    ]


def test_transient_failure_reuses_amber_recovery_with_a_typed_replay(
    stored_run: Any,
) -> None:
    turn = prepare_retest_turn(
        payload=_retest_request(_valid_envelope(_SOURCE_RUN_ID)),
        request=_FakeRequest(),
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        language="en",
        today=_TODAY,
    )
    assert turn is not None
    request_message = prepare_message(
        conversation_id=_CONVERSATION_ID,
        role="user",
        content="Retest with current data",
        metadata={"chat_action": sanitized_retest_action(_SOURCE_RUN_ID)},
    )

    failure_payload = failed_retest_turn(
        turn=turn,
        lifecycle_hooks=ChatTurnLifecycleHooks(
            owner="message_only",
            user_id=_USER_ID,
            conversation_id=_CONVERSATION_ID,
            request_id="retest-request",
            request_message=request_message,
        ),
        request_message=request_message,
        language="en",
    )

    assert failure_payload["recovery"]["code"] == "runtime_failure"
    assert failure_payload["recovery"]["retryable"] is True
    assert failure_payload["assistant_response"]
    # A live message-shaped retry keeps the amber assistant recovery block; the
    # request-linked shape stays in metadata for the anchored reload rendering.
    assert set(failure_payload["retry_last_turn"]) == {"message", "action"}
    replay = failure_payload["retry_last_turn"]["action"]
    assert replay["type"] == "retest_run"
    assert replay["payload"] == _valid_envelope(_SOURCE_RUN_ID)
    assert failure_payload["retest_receipt"]["source_run_id"] == _SOURCE_RUN_ID
    persisted = next(
        message
        for message in _recent_messages_for_conversation(
            user_id=_USER_ID,
            conversation_id=_CONVERSATION_ID,
            limit=20,
        )
        if message.id == failure_payload["message_id"]
    )
    assert persisted.metadata["retry_last_turn"]["request_message_id"] == (
        request_message.id
    )


def test_admitted_user_turn_persists_the_receipt_for_reload(stored_run: Any) -> None:
    from argus.api.chat.request_admission import prepare_chat_request_admission

    payload = _retest_request(_valid_envelope(_SOURCE_RUN_ID))
    turn = prepare_retest_turn(
        payload=payload,
        request=_FakeRequest(),
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        language="en",
        today=_TODAY,
    )
    assert turn is not None
    api_state.store.conversation_owners[_CONVERSATION_ID] = _USER_ID

    admission = prepare_chat_request_admission(
        payload=payload,
        request=_FakeRequest(),
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        display_message=chat_display_message(payload, language="en"),
        mention_provenance=[],
        enabled=True,
        language="en",
        owner="message_only",
        extra_user_metadata={"retest_receipt": dict(turn.receipt)},
    )
    request_message = admission.persist()

    assert request_message is not None
    assert request_message.content == "Retest with current data"
    assert request_message.metadata["retest_receipt"]["strategy_family"] == (
        "buy_and_hold"
    )
    assert request_message.metadata["chat_action"] == sanitized_retest_action(
        _SOURCE_RUN_ID
    )
