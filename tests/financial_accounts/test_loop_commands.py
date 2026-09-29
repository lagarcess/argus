from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from argus.domain.recording.errors import (
    IdempotencyConflict,
    RecordingInputError,
    StaleVersion,
)
from argus.domain.recording.loop_schemas import (
    ActivityRequest,
    CheckRequest,
    LoopOpeningRequest,
)
from argus.domain.recording.repository import InMemoryFinancialAccountRepository
from argus.domain.recording.schemas import CreateFinancialAccountRequest, account_response
from argus.domain.recording.service import FinancialAccountService

NOW = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)


@pytest.fixture
def scene():
    service = FinancialAccountService(
        InMemoryFinancialAccountRepository(lambda: NOW), lambda: NOW
    )
    user = str(uuid4())
    account = service.create(
        user_id=user,
        idempotency_key="create",
        request=CreateFinancialAccountRequest(
            type="checking",
            currency="DOP",
            amount="10000",
            as_of=NOW - timedelta(days=10),
        ),
    ).stored
    return service, user, account.account.id


def expense(scene, amount, day, coverage=None, record_id=None, reason=None):
    service, user, account = scene
    current = service.get(user_id=user, account_id=account)
    body = ActivityRequest(
        expected_version=current.account.version,
        expected_revision=1 if record_id else None,
        amount=amount,
        occurred_at=NOW - timedelta(days=day),
        coverage=coverage or [],
        reason=reason,
    )
    preview = service.loop.preview_activity(
        user_id=user, account_id=account, request=body, record_id=record_id
    )
    body = body.model_copy(update={"preview_token": preview["preview_token"]})
    return service.loop.write_activity(
        user_id=user,
        account_id=account,
        request=body,
        idempotency_key=str(uuid4()),
        record_id=record_id,
    ), body


def checked(scene, amount, day):
    service, user, account = scene
    current = service.get(user_id=user, account_id=account)
    body = CheckRequest(
        expected_version=current.account.version,
        amount=amount,
        as_of=NOW - timedelta(days=day),
    )
    preview = service.loop.preview_check(user_id=user, account_id=account, request=body)
    return service.loop.write_check(
        user_id=user,
        account_id=account,
        request=body.model_copy(update={"preview_token": preview["preview_token"]}),
        idempotency_key=str(uuid4()),
    )


def test_complete_loop_correction_late_partial_and_new_spending(scene):
    e, _ = expense(scene, "2000", 8)
    c = checked(scene, "7500", 5)
    expense(scene, "200", 7, [{"observation_id": c.record_id, "included": True}])
    result, _ = expense(scene, "500", 2)
    assert account_response(result.stored).balance.amount_minor == 700000
    fixed, _ = expense(
        scene,
        "1800",
        8,
        [{"observation_id": c.record_id, "included": True}],
        e.record_id,
        "wrong amount",
    )
    assert account_response(fixed.stored).balance.amount_minor == 700000
    assert len(fixed.stored.expenses[-1].revisions) == 2


def test_response_loss_replay_precedes_stale_version_and_does_not_repeat_expense(scene):
    service, user, account = scene
    result, body = expense(scene, "500", 8)
    key = "response-loss"
    current = service.get(user_id=user, account_id=account)
    request = ActivityRequest(
        expected_version=current.account.version,
        amount="100",
        occurred_at=NOW - timedelta(days=6),
    )
    preview = service.loop.preview_activity(
        user_id=user, account_id=account, request=request
    )
    request = request.model_copy(update={"preview_token": preview["preview_token"]})
    first = service.loop.write_activity(
        user_id=user, account_id=account, request=request, idempotency_key=key
    )
    expense(scene, "200", 3)
    replay = service.loop.write_activity(
        user_id=user, account_id=account, request=request, idempotency_key=key
    )
    assert replay.replayed and replay.record_id == first.record_id
    assert len(replay.stored.expenses) == 3
    with pytest.raises(IdempotencyConflict):
        service.loop.write_activity(
            user_id=user,
            account_id=account,
            request=request.model_copy(update={"amount": "101"}),
            idempotency_key=key,
        )


def test_missing_coverage_is_previewable_but_cannot_commit(scene):
    service, user, account = scene
    body = ActivityRequest(
        expected_version=1, amount="10", occurred_at=NOW - timedelta(days=10)
    )
    preview = service.loop.preview_activity(
        user_id=user, account_id=account, request=body
    )
    assert not preview["ready"] and preview["observations"][0]["included"] is None
    with pytest.raises(RecordingInputError, match="coverage_required"):
        service.loop.write_activity(
            user_id=user, account_id=account, request=body, idempotency_key="no"
        )
    assert service.get(user_id=user, account_id=account).account.version == 1


def test_later_confirmed_same_day_check_becomes_current(scene):
    checked(scene, "9000", 5)
    service, user, account = scene
    current = service.get(user_id=user, account_id=account)
    request = CheckRequest(
        expected_version=current.account.version,
        amount="8000",
        as_of=(NOW - timedelta(days=5)).replace(hour=8),
    )
    preview = service.loop.preview_check(
        user_id=user, account_id=account, request=request
    )
    result = service.loop.write_check(
        user_id=user,
        account_id=account,
        request=request.model_copy(update={"preview_token": preview["preview_token"]}),
        idempotency_key="same-day",
    )
    assert account_response(result.stored).balance.amount_minor == 800000
