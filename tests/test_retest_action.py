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
from argus.domain.retest_setup import (
    RETEST_CONTRACT_VERSION,
    RETEST_WINDOW_POLICY,
    retest_setup_from_run,
)
from fastapi import HTTPException

_USER_ID = "retest-owner"
_OTHER_USER_ID = "retest-intruder"
_CONVERSATION_ID = "retest-conversation"
_TODAY = date(2026, 7, 31)
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


def _valid_envelope(source_run_id: str = "run-1") -> dict[str, Any]:
    return {
        "source_run_id": source_run_id,
        "window_policy": RETEST_WINDOW_POLICY,
        "contract_version": RETEST_CONTRACT_VERSION,
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
        run_id="retest-source-run",
    )
    assert run is not None
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
            "chat_action": sanitized_retest_action("retest-source-run"),
            "retest_receipt": {"source_run_id": "retest-source-run"},
        },
    )
    return ChatTurnLifecycleHooks(
        owner="message_only",
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        request_id="retest-request",
        request_message=request_message,
    )


def test_only_the_bounded_v1_envelope_is_accepted() -> None:
    assert retest_action_source_run_id(_valid_envelope()) == "run-1"
    assert retest_action_source_run_id({**_valid_envelope(), "symbols": ["NVDA"]}) is None
    assert (
        retest_action_source_run_id(
            {**_valid_envelope(), "date_range": {"start": "2020-01-01"}}
        )
        is None
    )
    assert (
        retest_action_source_run_id({**_valid_envelope(), "window_policy": "since_ipo"})
        is None
    )
    assert (
        retest_action_source_run_id(
            {**_valid_envelope(), "contract_version": "argus_retest_run/v2"}
        )
        is None
    )
    assert retest_action_source_run_id({**_valid_envelope(), "source_run_id": " "}) is None


def test_client_display_copy_never_reaches_storage() -> None:
    payload = _retest_request(
        _valid_envelope("retest-source-run"),
        label="Delete everything",
        label_key="chat.result_card.save",
    )

    assert is_retest_action(payload)
    assert persisted_chat_action(payload) == {
        "type": "retest_run",
        "label": None,
        "labelKey": RETEST_ACTION_LABEL_KEY,
        "payload": _valid_envelope("retest-source-run"),
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
        "contract_version": RETEST_CONTRACT_VERSION,
        "window_policy": RETEST_WINDOW_POLICY,
        "source_run_id": "retest-source-run",
        "symbols": ["TSLA"],
        "strategy_family": "buy_and_hold",
        "timeframe": "1D",
        "duration_days": 365,
        "duration": {"unit": "year", "count": 1},
    }


def test_admission_reloads_canonical_truth_from_the_owned_run(
    stored_run: Any,
) -> None:
    turn = prepare_retest_turn(
        payload=_retest_request(_valid_envelope("retest-source-run")),
        request=_FakeRequest(),
        user_id=_USER_ID,
        conversation_id=_CONVERSATION_ID,
        language="en",
        today=_TODAY,
        confirmation_id="confirmation-retest",
    )

    assert turn is not None
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
        {**_valid_envelope("retest-source-run"), "symbols": ["NVDA"]}
        if case == "tampered_envelope"
        else _valid_envelope(
            "missing-run" if case == "unknown_run" else "retest-source-run"
        )
    )
    if case == "unfinished_run":
        api_state.store.backtest_runs[stored_run.id] = stored_run.model_copy(
            update={"status": "running"}
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
        payload=_retest_request(_valid_envelope("retest-source-run")),
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
        payload=_retest_request(_valid_envelope("retest-source-run")),
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
        metadata={"chat_action": sanitized_retest_action("retest-source-run")},
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
    assert replay["payload"] == _valid_envelope("retest-source-run")
    assert failure_payload["retest_receipt"]["source_run_id"] == "retest-source-run"
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

    payload = _retest_request(_valid_envelope("retest-source-run"))
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
        "retest-source-run"
    )
