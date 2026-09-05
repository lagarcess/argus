"""Read-time repair of old result transport from owner-scoped canonical runs."""

from collections.abc import Callable, Mapping
from typing import Any

from argus.api.schemas import BacktestRun, Message
from argus.domain.artifact_presentation_kind import artifact_presentation_kind
from argus.domain.backtest_message_projection import result_fact_bank


def repair_result_message_facts(
    messages: list[Message],
    *,
    conversation_id: str,
    load_runs: Callable[[list[str]], Mapping[str, BacktestRun]],
) -> list[Message]:
    """One bounded load, no persistence changes, and no cross-thread repair."""
    missing: dict[str, str] = {}
    for message in messages:
        metadata = message.metadata or {}
        if message.role != "assistant" or artifact_presentation_kind(metadata) not in {
            "result",
            "breakdown",
        }:
            continue
        bank = metadata.get("result_fact_bank")
        if (
            isinstance(bank, dict)
            and isinstance(bank.get("metrics"), dict)
            and isinstance(bank.get("config_snapshot"), dict)
        ):
            continue
        card = metadata.get("result_card")
        identities = {
            candidate
            for candidate in (
                metadata.get("result_run_id"),
                bank.get("run_id") if isinstance(bank, dict) else None,
                card.get("run_id") if isinstance(card, dict) else None,
            )
            if isinstance(candidate, str) and candidate
        }
        if len(identities) == 1:
            missing[message.id] = identities.pop()
    if not missing:
        return messages
    runs = load_runs(sorted(set(missing.values())))
    repaired: list[Message] = []
    for message in messages:
        run_id = missing.get(message.id)
        run = runs.get(run_id) if run_id is not None else None
        if (
            run is None
            or run.id != run_id
            or run.conversation_id != conversation_id
            or run.status != "completed"
        ):
            repaired.append(message)
            continue
        metadata: dict[str, Any] = dict(message.metadata or {})
        metadata["result_fact_bank"] = result_fact_bank(run)
        repaired.append(message.model_copy(update={"metadata": metadata}))
    return repaired


def owned_result_message_facts(
    messages: list[Message],
    *,
    user_id: str,
    conversation_id: str,
) -> list[Message]:
    from loguru import logger

    from argus.api import state as api_state

    def load_runs(run_ids: list[str]) -> Mapping[str, BacktestRun]:
        if api_state.supabase_gateway is not None:
            try:
                return api_state.supabase_gateway.get_backtest_runs_by_ids(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    run_ids=run_ids,
                )
            except Exception:
                logger.warning(
                    "Historical result facts unavailable during reader projection"
                )
                return {}
        return {
            run_id: api_state.store.backtest_runs[run_id]
            for run_id in run_ids
            if api_state.store.backtest_run_owners.get(run_id) == user_id
            and run_id in api_state.store.backtest_runs
        }

    return repair_result_message_facts(
        messages, conversation_id=conversation_id, load_runs=load_runs
    )
