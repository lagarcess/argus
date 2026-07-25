from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.guest_access import AccountContext
from argus.domain.usage_limits import MESSAGE_USAGE_RESOURCE, read_memory_usage
from argus.observability.guest_funnel import (
    GuestFunnelCapabilityCategory,
    GuestFunnelConversionReason,
    GuestFunnelEventKind,
    GuestFunnelLanguage,
    GuestFunnelStrategyCategory,
    GuestFunnelSurface,
    GuestFunnelTerminalOutcome,
    capture_guest_funnel_event,
)


def emit_guest_funnel_event(
    *,
    account: AccountContext,
    kind: GuestFunnelEventKind,
    user_id: str,
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
) -> None:
    if account.kind != "guest":
        return
    optional_fields = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "job_id": job_id,
        "backtest_run_id": backtest_run_id,
        "language": language,
        "surface": surface,
        "strategy_category": strategy_category,
        "capability_category": capability_category,
        "conversion_reason": conversion_reason,
        "terminal_outcome": terminal_outcome,
    }
    emit_verified_guest_funnel_event(
        kind,
        user_id=user_id,
        **{key: value for key, value in optional_fields.items() if value is not None},
    )


def emit_verified_guest_funnel_event(
    kind: GuestFunnelEventKind,
    *,
    user_id: str,
    **kwargs: Any,
) -> None:
    try:
        capture_guest_funnel_event(
            kind,
            user_id=user_id,
            **kwargs,
        )
    except Exception:
        logger.opt(exception=True).warning(
            "Guest funnel event emission failed",
            product_event=kind,
        )


def guest_session_allowance_present(
    allowance_limits: list[dict[str, object]] | None,
) -> bool:
    return any(
        str(window.get("period") or "") == "guest_session"
        for window in allowance_limits or []
    )


def current_guest_usage_count(
    *,
    account: AccountContext,
    user_id: str,
    resource: str,
) -> int | None:
    if account.kind != "guest" or account.expires_at is None:
        return None
    now = datetime.now(timezone.utc)
    period_start = account.expires_at - timedelta(days=7)
    if api_state.supabase_gateway is not None:
        rows = api_state.supabase_gateway.list_current_usage_counters(
            user_id=user_id,
            resources=(resource,),
            period="guest_session",
            at=now,
            period_start=period_start,
        )
        row = next(
            (item for item in rows if str(item.get("resource")) == resource),
            None,
        )
        return int(row.get("used_count", 0)) if row is not None else 0
    row = read_memory_usage(
        api_state.store.usage_counters,
        user_id=user_id,
        resource=resource,
        period="guest_session",
        at=now,
        period_start=period_start,
    )
    return int(row.get("used_count", 0)) if row is not None else 0


def emit_first_guest_message_event(
    *,
    account: AccountContext,
    user_id: str,
    conversation_id: str,
    message_id: str,
    language: GuestFunnelLanguage,
) -> None:
    try:
        used_count = current_guest_usage_count(
            account=account,
            user_id=user_id,
            resource=MESSAGE_USAGE_RESOURCE,
        )
    except Exception:
        logger.opt(exception=True).warning(
            "Guest first-message counter read failed",
        )
        return
    if used_count != 1:
        return
    emit_guest_funnel_event(
        account=account,
        kind="first_useful_assistant_response_completed",
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        language=language,
        surface="chat",
        capability_category="chat",
        terminal_outcome="completed",
    )
