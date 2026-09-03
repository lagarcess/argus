from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from argus.api.chat.allowance import check_message_allowance
from argus.api.dependencies import current_user
from argus.api.guest_access import guest_account_context
from argus.api.guest_observability import (
    emit_first_guest_message_event,
    emit_first_guest_simulation_event,
    emit_guest_funnel_event,
)
from argus.api.main import app
from argus.api.routers import analytics as analytics_router
from argus.api.schemas import GuestFunnelClientEventRequest, OnboardingState, User
from argus.domain.guest_workspaces import GuestWorkspace
from argus.domain.usage_limits import MESSAGE_USAGE_RESOURCE
from argus.observability import sanitize_observability_attributes
from argus.observability.guest_funnel import (
    GUEST_FUNNEL_EVENT_MAP,
    build_guest_funnel_event,
)
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

APPROVED_GUEST_FUNNEL_EVENTS = {
    "guest_session_started",
    "starter_action_selected",
    "first_useful_assistant_response_completed",
    "confirmation_reached",
    "first_simulation_admitted",
    "first_result_completed",
    "conversion_prompt_shown",
    "account_creation_completed",
    "existing_account_sign_in_completed",
    "temporary_workspace_claimed",
    "guest_limit_reached",
    "guest_feedback_submitted",
    "guest_session_expired",
}

GUEST_USER_ID = "00000000-0000-0000-0000-000000000091"


def _guest_profile() -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=GUEST_USER_ID,
        email=None,
        language="en",
        locale="en-US",
        theme="dark",
        is_admin=False,
        onboarding=OnboardingState(),
        created_at=now,
        updated_at=now,
    )


def _guest_context():
    profile = _guest_profile()
    return guest_account_context(
        GuestWorkspace(
            user_id=profile.id,
            conversation_id="conversation-1",
            status="active",
            created_at=profile.created_at,
            expires_at=profile.created_at.replace(year=profile.created_at.year + 1),
            claimed_by=None,
            claimed_at=None,
            updated_at=profile.updated_at,
        )
    )


def test_guest_funnel_event_contract_is_complete_and_uses_the_shared_envelope() -> None:
    assert set(GUEST_FUNNEL_EVENT_MAP) == APPROVED_GUEST_FUNNEL_EVENTS

    for kind in sorted(APPROVED_GUEST_FUNNEL_EVENTS):
        envelope = build_guest_funnel_event(
            kind,
            user_id="guest-user-1",
            language="es-419",
            surface="chat",
            terminal_outcome="completed",
        )

        assert envelope.schema_version == "argus_observability_event/v1"
        assert envelope.feature_area == "guest_acquisition"
        assert envelope.privacy_mode == "metadata_only"
        assert envelope.actor_hash
        assert envelope.actor_hash != "guest-user-1"
        assert envelope.provider is None
        assert envelope.model is None
        assert envelope.route_receipt_id is None
        assert envelope.attributes == {
            "language": "es-419",
            "product_event": kind,
            "surface": "chat",
            "terminal_outcome": "completed",
        }


def test_guest_funnel_sanitizer_removes_every_forbidden_property() -> None:
    sanitized = sanitize_observability_attributes(
        {
            "language": "en",
            "surface": "conversion_modal",
            "conversion_reason": "save_decision",
            "terminal_outcome": "shown",
            "prompt": "Buy $100,000 of AAPL from 2024-01-01",
            "assistant_prose": "Private response",
            "capital": 100_000,
            "start_date": "2024-01-01",
            "end_date": "2025-01-01",
            "email": "person@example.com",
            "display_name": "Private Person",
            "conversation_title": "Private title",
            "conversation_preview": "Private preview",
            "cookie": "session=secret",
            "authorization_header": "Bearer secret",
            "ip_address": "203.0.113.8",
            "url": "https://argus.test/chat?token=secret",
            "auth_material": {"session": "secret"},
            "model": "internal-model",
            "provider": "internal-provider",
        }
    )

    assert sanitized == {
        "language": "en",
        "surface": "conversion_modal",
        "conversion_reason": "save_decision",
        "terminal_outcome": "shown",
    }


@pytest.mark.parametrize(
    ("payload", "forbidden_value"),
    [
        ({"prompt": "private prompt"}, "private prompt"),
        ({"assistant_prose": "private response"}, "private response"),
        ({"capital": 100_000}, 100_000),
        ({"start_date": "2024-01-01"}, "2024-01-01"),
        ({"email": "person@example.com"}, "person@example.com"),
        ({"display_name": "Private Person"}, "Private Person"),
        ({"conversation_title": "Private title"}, "Private title"),
        ({"cookie": "secret"}, "secret"),
        ({"ip_address": "203.0.113.8"}, "203.0.113.8"),
        ({"url": "https://argus.test/chat?token=secret"}, "token=secret"),
        ({"model": "internal-model"}, "internal-model"),
        ({"provider": "internal-provider"}, "internal-provider"),
    ],
)
def test_browser_guest_event_schema_rejects_forbidden_fields(
    payload: dict[str, object],
    forbidden_value: object,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        GuestFunnelClientEventRequest.model_validate(
            {
                "event": "conversion_prompt_shown",
                "language": "en",
                "surface": "conversion_modal",
                "conversion_reason": "save_decision",
                "terminal_outcome": "shown",
                **payload,
            }
        )

    assert str(forbidden_value) not in repr(exc_info.value.errors(include_input=False))


def test_browser_guest_event_schema_accepts_only_ui_owned_facts() -> None:
    request = GuestFunnelClientEventRequest.model_validate(
        {
            "event": "conversion_prompt_shown",
            "language": "es-419",
            "surface": "conversion_modal",
            "conversion_reason": "simulation_limit",
            "terminal_outcome": "shown",
        }
    )

    assert request.model_dump(mode="json", exclude_none=True) == {
        "event": "conversion_prompt_shown",
        "language": "es-419",
        "surface": "conversion_modal",
        "conversion_reason": "simulation_limit",
        "terminal_outcome": "shown",
    }


def test_guest_event_endpoint_projects_verified_user_and_typed_properties() -> None:
    captured: list[tuple[str, dict[str, object]]] = []

    def fake_capture(kind: str, **kwargs: object) -> None:
        captured.append((kind, kwargs))

    app.dependency_overrides[current_user] = _guest_profile
    try:
        with (
            patch.object(
                analytics_router, "account_context", return_value=_guest_context()
            ),
            patch.object(
                analytics_router,
                "capture_guest_funnel_event",
                side_effect=fake_capture,
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/analytics/guest-events",
                json={
                    "event": "conversion_prompt_shown",
                    "language": "es-419",
                    "surface": "conversion_modal",
                    "conversion_reason": "save_decision",
                    "terminal_outcome": "shown",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert captured == [
        (
            "conversion_prompt_shown",
            {
                "user_id": GUEST_USER_ID,
                "language": "es-419",
                "surface": "conversion_modal",
                "strategy_category": None,
                "conversion_reason": "save_decision",
                "terminal_outcome": "shown",
            },
        )
    ]


def test_guest_event_endpoint_caps_authenticated_browser_relay_volume() -> None:
    app.dependency_overrides[current_user] = _guest_profile
    analytics_router.reset_guest_event_limiter_for_tests()
    try:
        with (
            patch.object(
                analytics_router, "account_context", return_value=_guest_context()
            ),
            patch.object(analytics_router, "capture_guest_funnel_event") as capture,
            TestClient(app) as client,
        ):
            responses = [
                client.post(
                    "/api/v1/analytics/guest-events",
                    json={
                        "event": "conversion_prompt_shown",
                        "language": "en",
                        "surface": "conversion_modal",
                        "conversion_reason": "keep_history",
                        "terminal_outcome": "shown",
                    },
                )
                for _ in range(analytics_router.GUEST_EVENT_ATTEMPT_LIMIT + 1)
            ]
    finally:
        app.dependency_overrides.clear()
        analytics_router.reset_guest_event_limiter_for_tests()

    assert responses[-1].status_code == 429
    assert responses[-1].json()["code"] == "too_many_requests"
    assert capture.call_count == analytics_router.GUEST_EVENT_ATTEMPT_LIMIT


def test_guest_event_endpoint_rejects_unapproved_browser_properties() -> None:
    app.dependency_overrides[current_user] = _guest_profile
    try:
        with (
            patch.object(
                analytics_router, "account_context", return_value=_guest_context()
            ),
            patch.object(analytics_router, "capture_guest_funnel_event") as capture,
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/analytics/guest-events",
                json={
                    "event": "starter_action_selected",
                    "language": "en",
                    "surface": "starter_actions",
                    "strategy_category": "buy_and_hold",
                    "terminal_outcome": "selected",
                    "prompt": "private prompt",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    capture.assert_not_called()


def test_guest_event_endpoint_rejects_foreign_browser_origin() -> None:
    app.dependency_overrides[current_user] = _guest_profile
    try:
        with (
            patch.object(
                analytics_router,
                "account_context",
                return_value=_guest_context(),
            ),
            patch.object(analytics_router, "capture_guest_funnel_event") as capture,
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/analytics/guest-events",
                headers={"Origin": "https://foreign.example"},
                json={
                    "event": "starter_action_selected",
                    "language": "en",
                    "surface": "starter_actions",
                    "strategy_category": "buy_and_hold",
                    "terminal_outcome": "selected",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_origin_rejected"
    capture.assert_not_called()


def test_guest_event_endpoint_rejects_registered_account_context() -> None:
    from argus.api.guest_access import registered_account_context

    app.dependency_overrides[current_user] = _guest_profile
    try:
        with (
            patch.object(
                analytics_router,
                "account_context",
                return_value=registered_account_context(GUEST_USER_ID),
            ),
            patch.object(analytics_router, "capture_guest_funnel_event") as capture,
            TestClient(app) as client,
        ):
            response = client.post(
                "/api/v1/analytics/guest-events",
                json={
                    "event": "starter_action_selected",
                    "language": "en",
                    "surface": "starter_actions",
                    "strategy_category": "buy_and_hold",
                    "terminal_outcome": "selected",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["code"] == "guest_account_required"
    capture.assert_not_called()


def test_first_useful_response_emits_only_at_the_first_settled_unit() -> None:
    account = _guest_context()
    with (
        patch(
            "argus.api.guest_observability.current_guest_usage_count",
            side_effect=[1, 2],
        ),
        patch("argus.api.guest_observability.capture_guest_funnel_event") as capture,
    ):
        emit_first_guest_message_event(
            account=account,
            user_id=GUEST_USER_ID,
            conversation_id="conversation-1",
            message_id="message-1",
            language="en",
        )
        emit_first_guest_message_event(
            account=account,
            user_id=GUEST_USER_ID,
            conversation_id="conversation-1",
            message_id="message-2",
            language="en",
        )

    capture.assert_called_once_with(
        "first_useful_assistant_response_completed",
        user_id=GUEST_USER_ID,
        conversation_id="conversation-1",
        message_id="message-1",
        language="en",
        surface="chat",
        product_capability="chat",
        terminal_outcome="completed",
    )


def test_first_simulation_milestones_emit_only_for_the_first_usage_unit() -> None:
    account = _guest_context()
    with (
        patch(
            "argus.api.guest_observability.current_guest_usage_count",
            side_effect=[1, 2, 1, 2],
        ),
        patch("argus.api.guest_observability.capture_guest_funnel_event") as capture,
    ):
        for kind, outcome in (
            ("first_simulation_admitted", "admitted"),
            ("first_simulation_admitted", "admitted"),
            ("first_result_completed", "completed"),
            ("first_result_completed", "completed"),
        ):
            emit_first_guest_simulation_event(
                account=account,
                kind=kind,
                user_id=GUEST_USER_ID,
                conversation_id="conversation-1",
                job_id="job-1",
                terminal_outcome=outcome,
            )

    assert [call.args[0] for call in capture.call_args_list] == [
        "first_simulation_admitted",
        "first_result_completed",
    ]


def test_registered_context_never_emits_a_guest_event() -> None:
    from argus.api.guest_access import registered_account_context

    with patch("argus.api.guest_observability.capture_guest_funnel_event") as capture:
        emit_guest_funnel_event(
            account=registered_account_context("registered-user"),
            kind="guest_limit_reached",
            user_id="registered-user",
            surface="chat",
            product_capability="chat",
            terminal_outcome="limit_reached",
        )

    capture.assert_not_called()


def test_guest_message_limit_emits_from_authoritative_precheck() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/chat/stream",
            "headers": [],
        }
    )
    request.state.request_id = "request-1"
    account = _guest_context()
    gateway = Mock()

    class _ExhaustedVisitorClient:
        def table(self, name):
            assert name == "visitor_usage_counters"
            return self

        def select(self, *_args):
            return self

        def eq(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            from types import SimpleNamespace

            return SimpleNamespace(data=[{"used_count": 10}])

    gateway.client = _ExhaustedVisitorClient()

    with (
        patch("argus.api.chat.allowance.api_state.supabase_gateway", gateway),
        patch("argus.api.chat.allowance.account_context", return_value=account),
        patch("argus.api.chat.allowance.emit_guest_funnel_event") as emit,
        pytest.raises(HTTPException) as exc_info,
    ):
        check_message_allowance(request, _guest_profile())

    assert exc_info.value.status_code == 429
    emit.assert_called_once_with(
        account=account,
        kind="guest_limit_reached",
        user_id=GUEST_USER_ID,
        surface="chat",
        product_capability="chat",
        conversion_reason="message_limit",
        terminal_outcome="limit_reached",
    )


@pytest.mark.parametrize(
    ("relative_path", "events"),
    [
        (
            "src/argus/api/routers/auth.py",
            {
                "guest_session_started",
                "account_creation_completed",
                "existing_account_sign_in_completed",
                "temporary_workspace_claimed",
            },
        ),
        (
            "src/argus/api/guest_observability.py",
            {
                "first_useful_assistant_response_completed",
                "confirmation_reached",
                "first_result_completed",
            },
        ),
        (
            "src/argus/api/chat/backtest_admission_flow.py",
            {"first_simulation_admitted", "guest_limit_reached"},
        ),
        (
            "src/argus/api/routers/backtest.py",
            {
                "first_simulation_admitted",
                "first_result_completed",
                "guest_limit_reached",
            },
        ),
        (
            "src/argus/api/routers/feedback.py",
            {"guest_feedback_submitted", "guest_limit_reached"},
        ),
        (
            "src/argus/domain/guest_cleanup.py",
            {"guest_session_expired"},
        ),
    ],
)
def test_authoritative_server_owners_emit_guest_funnel_events(
    relative_path: str,
    events: set[str],
) -> None:
    source = (Path(__file__).parents[1] / relative_path).read_text()

    for event in events:
        assert f'"{event}"' in source


def test_chat_owner_calls_first_settled_response_observer() -> None:
    source = (
        Path(__file__).parents[1] / "src/argus/api/chat/measurement_events.py"
    ).read_text()

    assert "emit_guest_turn_funnel_events(" in source


def test_first_message_reader_uses_guest_session_counter_truth() -> None:
    account = _guest_context()
    with patch(
        "argus.api.guest_observability.current_guest_usage_count",
        return_value=1,
    ) as count:
        emit_first_guest_message_event(
            account=account,
            user_id=GUEST_USER_ID,
            conversation_id="conversation-1",
            message_id="message-1",
            language="en",
        )

    count.assert_called_once_with(
        account=account,
        user_id=GUEST_USER_ID,
        resource=MESSAGE_USAGE_RESOURCE,
    )


def test_checked_openapi_pins_the_guest_browser_event_contract() -> None:
    checked = (Path(__file__).parents[1] / "docs/api/openapi.yaml").read_text(
        encoding="utf-8"
    )
    generated = app.openapi()

    assert "/api/v1/analytics/guest-events" in generated["paths"]
    assert "GuestFunnelClientEventRequest" in generated["components"]["schemas"]
    assert "/api/v1/analytics/guest-events:" in checked
    assert "GuestFunnelClientEventRequest:" in checked
