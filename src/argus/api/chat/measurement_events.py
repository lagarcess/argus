from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from argus.api.guest_access import AccountContext, current_account_context
from argus.api.guest_observability import emit_guest_turn_funnel_events


def schedule_runtime_measurement_events_after_stream(
    *,
    user_id: str,
    conversation_id: str,
    runtime_result: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    runtime_result_snapshot = dict(runtime_result)
    metadata_snapshot = dict(metadata)
    account = current_account_context()

    async def _run() -> None:
        try:
            await asyncio.to_thread(
                emit_runtime_measurement_events,
                user_id=user_id,
                conversation_id=conversation_id,
                runtime_result=runtime_result_snapshot,
                metadata=metadata_snapshot,
                account=account,
            )
        except Exception as exc:
            logger.warning(
                "Runtime measurement event emission failed",
                error=str(exc),
                conversation_id=conversation_id,
            )

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        logger.warning(
            "Runtime measurement event emission skipped without running loop",
            conversation_id=conversation_id,
        )


def emit_runtime_measurement_events(
    *,
    user_id: str,
    conversation_id: str,
    runtime_result: dict[str, Any],
    metadata: dict[str, Any],
    account: AccountContext | None = None,
) -> None:
    if account is not None:
        raw_action = metadata.get("chat_action")
        emit_guest_turn_funnel_events(
            account=account,
            user_id=user_id,
            conversation_id=conversation_id,
            language=None,
            assistant_message_id=_clean_event_string(runtime_result.get("message_id")),
            is_run_backtest_turn=(
                isinstance(raw_action, dict) and raw_action.get("type") == "run_backtest"
            ),
        )


def _clean_event_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
