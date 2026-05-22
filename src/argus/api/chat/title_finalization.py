from __future__ import annotations

import asyncio
import os

from loguru import logger

from argus.api.artifact_naming import (
    maybe_generate_conversation_title,
    maybe_generate_saved_strategy_name,
)
from argus.api.chat.route_receipts import persist_route_receipts
from argus.api.schemas import BacktestRun
from argus.llm.openrouter import (
    begin_openrouter_route_receipt_capture,
    end_openrouter_route_receipt_capture,
    record_openrouter_route_receipt,
)


def finalize_conversation_title_after_turn(
    *,
    user_id: str,
    conversation_id: str,
    language: str | None,
    current_run: BacktestRun | None = None,
    user_message: str | None = None,
    assistant_message: str | None = None,
    message_id: str | None = None,
    run_id: str | None = None,
) -> str | None:
    """Finalize a conversation title as fail-open utility-tier polish."""

    receipt_token = begin_openrouter_route_receipt_capture()
    fallback_outcome = "skipped"
    fallback_failure_mode = "title_not_generated"
    try:
        title = maybe_generate_conversation_title(
            user_id=user_id,
            conversation_id=conversation_id,
            language=language,
            current_run=current_run,
            user_message=user_message,
            assistant_message=assistant_message,
        )
        if title is not None:
            fallback_failure_mode = None
        return title
    except Exception:
        fallback_outcome = "failed"
        fallback_failure_mode = "title_finalization_failed"
        logger.opt(exception=True).warning(
            "Conversation title finalization failed",
            user_id=user_id,
            conversation_id=conversation_id,
        )
        return None
    finally:
        receipts = end_openrouter_route_receipt_capture(receipt_token)
        if not receipts and fallback_failure_mode:
            receipts = [
                record_openrouter_route_receipt(
                    task="name_suggestion",
                    model_name=None,
                    mode="json_schema",
                    schema_name="name_suggestion",
                    latency_ms=0,
                    outcome=fallback_outcome,
                    failure_mode=fallback_failure_mode,
                )
            ]
        persist_route_receipts(
            receipts=receipts,
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run_id,
            message_id=message_id,
            metadata={"runtime_artifact": "conversation_title"},
        )


def finalize_saved_strategy_name_after_turn(
    *,
    user_id: str,
    conversation_id: str,
    strategy_id: str,
    run: BacktestRun,
    language: str | None,
    message_id: str | None = None,
) -> str | None:
    """Finalize saved strategy names without affecting run truth."""

    receipt_token = begin_openrouter_route_receipt_capture()
    try:
        return maybe_generate_saved_strategy_name(
            user_id=user_id,
            strategy_id=strategy_id,
            run=run,
            language=language,
        )
    except Exception:
        logger.opt(exception=True).warning(
            "Saved strategy name finalization failed",
            user_id=user_id,
            conversation_id=conversation_id,
            strategy_id=strategy_id,
        )
        return None
    finally:
        persist_route_receipts(
            receipts=end_openrouter_route_receipt_capture(receipt_token),
            user_id=user_id,
            conversation_id=conversation_id,
            run_id=run.id,
            message_id=message_id,
            metadata={"runtime_artifact": "saved_strategy_name"},
        )


def schedule_artifact_naming_after_stream(
    *,
    user_id: str,
    conversation_id: str,
    language: str | None,
    current_run: BacktestRun | None = None,
    saved_strategy_id: str | None = None,
    user_message: str | None = None,
    assistant_message: str | None = None,
    message_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Start fail-open artifact naming after the canonical stream is complete."""

    if _artifact_naming_disabled_for_pytest():
        return

    async def _run() -> None:
        await asyncio.to_thread(
            finalize_conversation_title_after_turn,
            user_id=user_id,
            conversation_id=conversation_id,
            language=language,
            current_run=current_run,
            user_message=user_message,
            assistant_message=assistant_message,
            message_id=message_id,
            run_id=run_id,
        )
        if saved_strategy_id is not None and current_run is not None:
            await asyncio.to_thread(
                finalize_saved_strategy_name_after_turn,
                user_id=user_id,
                conversation_id=conversation_id,
                strategy_id=saved_strategy_id,
                run=current_run,
                language=language,
                message_id=message_id,
            )

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        logger.warning(
            "Artifact naming skipped because no running event loop was available",
            user_id=user_id,
            conversation_id=conversation_id,
            saved_strategy_id=saved_strategy_id,
        )


def _artifact_naming_disabled_for_pytest() -> bool:
    return (
        "PYTEST_CURRENT_TEST" in os.environ
        and os.getenv("ARGUS_ENABLE_ARTIFACT_NAMING_IN_TESTS") != "1"
    )
