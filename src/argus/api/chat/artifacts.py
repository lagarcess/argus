from __future__ import annotations

from collections.abc import Callable
from typing import Any

from loguru import logger

from argus.agent_runtime.confirmation_artifacts import (
    confirmation_id_from_payload,
    new_confirmation_id,
)
from argus.agent_runtime.state.models import ArtifactReference
from argus.api.schemas import BacktestRun
from argus.domain.backtest_admission import CHAT_RUN_SCOPE
from argus.domain.backtest_message_projection import result_fact_bank


def result_followup_metadata_from_run(run: BacktestRun) -> dict[str, Any]:
    context_packets = (
        run.conversation_result_card.get("context_packets")
        if isinstance(run.conversation_result_card, dict)
        else None
    )
    return {
        "run_id": run.id,
        "symbols": list(run.symbols),
        "benchmark_symbol": run.benchmark_symbol,
        "metrics": run.metrics,
        "config_snapshot": run.config_snapshot,
        "result_card": run.conversation_result_card,
        "context_packets": context_packets if isinstance(context_packets, list) else [],
        "chart": run.chart,
        "trades": run.trades,
    }


def result_reference_from_run(run: BacktestRun) -> ArtifactReference:
    return ArtifactReference(
        artifact_kind="backtest_result",
        artifact_id=run.id,
        artifact_status=run.status,
        metadata=result_fact_bank(run),
    )


def confirmation_id_for_runtime_card(
    runtime_result: dict[str, Any],
    *,
    new_id: Callable[[], str],
) -> str:
    references = runtime_result.get("artifact_references")
    fallback = None
    if isinstance(references, list):
        for reference in references:
            if (
                isinstance(reference, dict)
                and reference.get("artifact_kind") == "confirmation"
            ):
                artifact_id = reference.get("artifact_id")
                if isinstance(artifact_id, str) and artifact_id.strip():
                    fallback = artifact_id.strip()
                    break
    payload = runtime_result.get("confirmation_payload")
    if isinstance(payload, dict):
        return confirmation_id_from_payload(payload, fallback=fallback)
    return fallback or new_id()


def ensure_unspent_confirmation_identity(
    runtime_result: dict[str, Any],
    *,
    gateway: Any | None,
    user_id: str,
    new_id: Callable[[], str] = new_confirmation_id,
) -> str:
    """A durable run reservation spends its confirmation identity forever.

    Normal turn retries replay their persisted assistant message before this
    boundary. Reaching this function means a new confirmation card is about to
    be appended, so an identity already owned by a job must be replaced.
    """

    proposed_id = confirmation_id_for_runtime_card(runtime_result, new_id=new_id)
    payload = runtime_result.get("confirmation_payload")
    if gateway is None or not isinstance(payload, dict):
        return proposed_id
    reservation_reader = getattr(gateway, "get_backtest_job_reservation", None)
    if not callable(reservation_reader):
        return proposed_id
    reservation = reservation_reader(
        user_id=user_id,
        operation_scope=CHAT_RUN_SCOPE,
        idempotency_key=proposed_id,
    )
    if not isinstance(reservation, dict):
        return proposed_id

    replacement_id = new_id()
    payload["confirmation_id"] = replacement_id
    payload["artifact_id"] = replacement_id
    _replace_confirmation_reference_identity(
        runtime_result,
        replacement_id=replacement_id,
        confirmation_payload=payload,
    )
    logger.warning(
        "Spent confirmation identity replaced before card publication",
        prior_confirmation_id=proposed_id,
        replacement_confirmation_id=replacement_id,
        reservation_job_id=reservation.get("id"),
    )
    return replacement_id


def _replace_confirmation_reference_identity(
    runtime_result: dict[str, Any],
    *,
    replacement_id: str,
    confirmation_payload: dict[str, Any],
) -> None:
    references = runtime_result.get("artifact_references")
    if not isinstance(references, list):
        return
    for reference in references:
        if not isinstance(reference, dict):
            continue
        if reference.get("artifact_kind") != "confirmation":
            continue
        reference["artifact_id"] = replacement_id
        metadata = reference.get("metadata")
        if isinstance(metadata, dict):
            metadata["confirmation_id"] = replacement_id
            metadata["confirmation_payload"] = confirmation_payload


def saved_strategy_metadata(run: BacktestRun, strategy_id: str) -> dict[str, Any]:
    return {
        "saved_strategy_id": strategy_id,
        "result_strategy_id": strategy_id,
        "result_run_id": run.id,
        "latest_run_id": run.id,
    }


def saved_strategy_metadata_from_sources(
    *,
    run: BacktestRun,
    message_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy_id = _saved_strategy_id_from_message(message_metadata)
    if strategy_id is None:
        strategy_id = _saved_strategy_id_from_result_card(run.conversation_result_card)
    if strategy_id is None:
        return {}
    return saved_strategy_metadata(run, strategy_id)


def _saved_strategy_id_from_message(metadata: dict[str, Any] | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    for key in ("saved_strategy_id", "result_strategy_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _saved_strategy_id_from_result_card(card: dict[str, Any]) -> str | None:
    if not isinstance(card, dict):
        return None
    for key in ("saved_strategy_id", "savedStrategyId", "result_strategy_id"):
        value = card.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("saved_state", "savedState"):
        saved_state = card.get(key)
        if not isinstance(saved_state, dict):
            continue
        value = saved_state.get("strategy_id") or saved_state.get("strategyId")
        if isinstance(value, str) and value:
            return value
    return None
