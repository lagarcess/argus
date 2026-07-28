from __future__ import annotations

from typing import Literal, cast

from argus.observability.envelope import (
    ArgusEventEnvelope,
    EventAction,
    EventCaptureResult,
    EventType,
    build_event_envelope,
    capture_event,
)
from argus.observability.product_events import actor_hash_for_user

GuestFunnelEventKind = Literal[
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
]
GuestFunnelLanguage = Literal["en", "es-419"]
GuestFunnelSurface = Literal[
    "guest_entry",
    "starter_actions",
    "chat",
    "confirmation",
    "backtest",
    "conversion_modal",
    "account_conversion",
    "feedback",
    "cleanup",
]
GuestFunnelStrategyCategory = Literal[
    "buy_and_hold",
    "buy_the_dip",
    "dca_accumulation",
    "moving_average_crossover",
    "rsi_mean_reversion",
]
GuestFunnelCapabilityCategory = Literal[
    "chat",
    "simulation",
    "decision",
    "history",
    "account",
    "feedback",
]
GuestFunnelTerminalOutcome = Literal[
    "started",
    "selected",
    "completed",
    "admitted",
    "shown",
    "claimed",
    "limit_reached",
    "expired",
]
GuestFunnelConversionReason = Literal[
    "second_simulation",
    "message_limit",
    "save_decision",
    "new_conversation",
    "keep_history",
    "discovery_searches",
]

GUEST_FUNNEL_EVENT_MAP: dict[
    GuestFunnelEventKind,
    tuple[EventType, EventAction],
] = {
    "guest_session_started": ("system", "started"),
    "starter_action_selected": ("user_message", "started"),
    "first_useful_assistant_response_completed": ("ai_response", "completed"),
    "confirmation_reached": ("tool_result", "completed"),
    "first_simulation_admitted": ("tool_call", "started"),
    "first_result_completed": ("tool_result", "completed"),
    "conversion_prompt_shown": ("system", "started"),
    "account_creation_completed": ("storage", "completed"),
    "existing_account_sign_in_completed": ("system", "completed"),
    "temporary_workspace_claimed": ("storage", "completed"),
    "guest_limit_reached": ("system", "suppressed"),
    "guest_feedback_submitted": ("storage", "completed"),
    "guest_session_expired": ("system", "failed"),
}


def build_guest_funnel_event(
    kind: GuestFunnelEventKind | str,
    *,
    user_id: str | None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    job_id: str | None = None,
    backtest_run_id: str | None = None,
    language: GuestFunnelLanguage | None = None,
    surface: GuestFunnelSurface | None = None,
    strategy_category: GuestFunnelStrategyCategory | None = None,
    capability_category: GuestFunnelCapabilityCategory | None = None,
    conversion_reason: GuestFunnelConversionReason | None = None,
    terminal_outcome: GuestFunnelTerminalOutcome | None = None,
) -> ArgusEventEnvelope:
    event_kind = cast(GuestFunnelEventKind, kind)
    event_type, event_action = GUEST_FUNNEL_EVENT_MAP[event_kind]
    attributes = {
        "product_event": event_kind,
        "language": language,
        "surface": surface,
        "strategy_category": strategy_category,
        "capability_category": capability_category,
        "conversion_reason": conversion_reason,
        "terminal_outcome": terminal_outcome,
    }
    return build_event_envelope(
        event_type=event_type,
        event_action=event_action,
        feature_area="guest_acquisition",
        actor_hash=actor_hash_for_user(user_id),
        conversation_id=conversation_id,
        message_id=message_id,
        job_id=job_id,
        backtest_run_id=backtest_run_id,
        status=terminal_outcome,
        attributes={key: value for key, value in attributes.items() if value is not None},
    )


def capture_guest_funnel_event(
    kind: GuestFunnelEventKind | str,
    **kwargs: object,
) -> EventCaptureResult:
    return capture_event(build_guest_funnel_event(kind, **kwargs))
