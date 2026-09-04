"""Thorough research through the existing job lifecycle.

Chat never hangs on a thorough run: the turn ends with a queued job envelope,
the provider works in background mode, and an in-process poller finalizes by
persisting the answer as an ordinary assistant message and marking the job
succeeded. The job row is the same ``backtest_jobs`` lifecycle that serves
backtests, under ``operation_scope = 'chat.research'``; no second progress
mechanism exists. A process loss leaves the row for the existing stale-job
scan, which fails it honestly.

Dev memory persistence has no job endpoint, so the thorough shape degrades to
a synchronous call there; production always takes the background path.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

from loguru import logger

from argus.api import state as api_state
from argus.api.chat.backtest_job_envelopes import public_backtest_job_payload
from argus.api.chat.research_evidence import record_research_turn_evidence

# Re-exported: the scope literal is owned by the settlement rule the SQL is
# rendered from.
from argus.domain.job_settlement import RESEARCH_OPERATION_SCOPE
from argus.domain.research.admission import (
    ResearchCapacityExhausted,
    claim_current_research_attempt,
)
from argus.domain.research.config import (
    BACKGROUND_POLL_INTERVAL_SECONDS,
    RESEARCH_CONFIG_SPECS,
    background_deadline_seconds,
)
from argus.domain.research.contracts import ResearchPacket, ResearchUnavailableError
from argus.domain.research.credentials import perplexity_api_key
from argus.domain.research.perplexity_agent import PerplexityAgentClient

# Keep strong references so in-flight pollers never get garbage collected.
_POLLER_TASKS: set[asyncio.Task[None]] = set()


def _client() -> PerplexityAgentClient | None:
    api_key = perplexity_api_key()
    if not api_key:
        return None
    return PerplexityAgentClient(api_key)


def apply_research_job_request(
    runtime_result: dict[str, Any],
    *,
    user_id: str,
    conversation_id: str,
    request_message_id: str | None,
    request_id: str | None,
) -> dict[str, Any] | None:
    """Consume a typed research job request from the runtime result.

    Returns the public job payload for the background path. The synchronous
    dev fallback and the failure note mutate ``runtime_result`` in place so
    the stream and metadata carry the finalized artifacts, and return None.
    """
    from argus.agent_runtime.research_answer import (
        compose_completed_research,
        research_capacity_exhausted_for_job,
        research_failure_note,
        store_research_packet_for_job,
    )

    job_request = runtime_result.pop("research_job_request", None)
    if not isinstance(job_request, dict):
        return None
    try:
        job, sync_packet = start_research_job(
            job_request=job_request,
            user_id=user_id,
            conversation_id=conversation_id,
            request_message_id=request_message_id,
            request_id=request_id,
        )
    except ResearchCapacityExhausted as exc:
        composed = research_capacity_exhausted_for_job(
            job_request,
            guest_allowance_exhausted=exc.admission.guest_exhausted,
        )
        runtime_result["assistant_response"] = composed["answer"]
        runtime_result["research"] = composed["research"]
        return None
    if job is not None:
        return job
    if sync_packet is not None:
        store_research_packet_for_job(job_request, sync_packet)
        composed = compose_completed_research(job_request=job_request, packet=sync_packet)
        runtime_result["assistant_response"] = composed["answer"]
        runtime_result["research"] = composed["research"]
        if composed.get("next_experiments") is not None:
            runtime_result["next_experiments"] = composed["next_experiments"]
        return None
    runtime_result["assistant_response"] = research_failure_note(
        str(job_request.get("language") or "en")
    )
    return None


def start_research_job(
    *,
    job_request: dict[str, Any],
    user_id: str,
    conversation_id: str,
    request_message_id: str | None,
    request_id: str | None,
) -> tuple[dict[str, Any] | None, ResearchPacket | None]:
    """Submit the background run and create the queued job row.

    Returns ``(public_job_payload, None)`` on the background path,
    ``(None, packet)`` for the synchronous dev fallback, and ``(None, None)``
    when the provider is unavailable.
    """
    from argus.agent_runtime.research_answer import research_prompt_for_job

    client = _client()
    if client is None:
        return None, None
    spec = RESEARCH_CONFIG_SPECS["thorough"]
    prompt = research_prompt_for_job(job_request)
    if api_state.supabase_gateway is None:
        # Dev memory persistence has no durable job surface; run the same
        # documented configuration synchronously instead of inventing one.
        admission = claim_current_research_attempt()
        if not admission.available:
            raise ResearchCapacityExhausted(admission)
        try:
            sync_spec = spec.model_copy(update={"timeout_seconds": 110.0})
            packet = client.run_research(prompt, sync_spec)
        except ResearchUnavailableError as exc:
            logger.warning(
                "Synchronous thorough research failed"
                f" reason={exc.reason} detail={exc.detail or ''}"
            )
            return None, None
        return None, packet
    replay = _replayed_research_job(
        user_id=user_id,
        request_message_id=request_message_id,
    )
    if replay is not None:
        # The same request message already admitted a research job. Its row is
        # the answer whatever its status: a live row has its own poller, a
        # terminal row already names its message. Spawning a second poller
        # would finalize a second answer nobody links to, and submitting
        # first would spend provider budget on a run that could not land.
        return public_backtest_job_payload(replay), None
    admission = claim_current_research_attempt()
    if not admission.available:
        raise ResearchCapacityExhausted(admission)
    try:
        background_id = client.submit_background(prompt, spec)
    except ResearchUnavailableError as exc:
        logger.warning(
            "Research background submission failed"
            f" reason={exc.reason} detail={exc.detail or ''}"
        )
        return None, None
    launch_payload = {
        "schema_version": "research_job_launch/v1",
        "research_request": job_request,
        "perplexity_background_id": background_id,
    }
    payload_hash = (
        "sha256:"
        + hashlib.sha256(json.dumps(launch_payload, sort_keys=True).encode()).hexdigest()
    )
    try:
        job = api_state.supabase_gateway.create_backtest_job(
            user_id=user_id,
            conversation_id=conversation_id,
            payload_hash=payload_hash,
            launch_payload=launch_payload,
            request_message_id=request_message_id,
            idempotency_key=request_message_id,
            execution_metadata={
                "capability_class": job_request.get("capability_class"),
                "perplexity_background_id": background_id,
            },
            operation_scope=RESEARCH_OPERATION_SCOPE,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Research job row creation failed", error=str(exc))
        return None, None
    _spawn_poller(
        job_id=str(job.get("id")),
        background_id=background_id,
        job_request=job_request,
        user_id=user_id,
        conversation_id=conversation_id,
        request_id=request_id,
    )
    return public_backtest_job_payload(job), None


def _replayed_research_job(
    *,
    user_id: str,
    request_message_id: str | None,
) -> dict[str, Any] | None:
    gateway = api_state.supabase_gateway
    if gateway is None or not request_message_id:
        return None
    try:
        return gateway.find_backtest_job_by_idempotency_key(
            user_id=user_id,
            operation_scope=RESEARCH_OPERATION_SCOPE,
            idempotency_key=request_message_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Research job replay lookup failed", error=str(exc))
        return None


def _spawn_poller(
    *,
    job_id: str,
    background_id: str,
    job_request: dict[str, Any],
    user_id: str,
    conversation_id: str,
    request_id: str | None,
) -> None:
    task = asyncio.create_task(
        _poll_and_finalize(
            job_id=job_id,
            background_id=background_id,
            job_request=job_request,
            user_id=user_id,
            conversation_id=conversation_id,
            request_id=request_id,
        ),
        name=f"research-job-{job_id}",
    )
    _POLLER_TASKS.add(task)
    task.add_done_callback(_POLLER_TASKS.discard)


async def _poll_and_finalize(
    *,
    job_id: str,
    background_id: str,
    job_request: dict[str, Any],
    user_id: str,
    conversation_id: str,
    request_id: str | None,
) -> None:
    client = _client()
    if client is None:
        _fail_job(job_id=job_id, user_id=user_id, detail="provider key missing")
        return
    deadline = time.monotonic() + background_deadline_seconds()
    marked_running = False
    try:
        while True:
            await asyncio.sleep(BACKGROUND_POLL_INTERVAL_SECONDS)
            try:
                poll = await asyncio.to_thread(client.poll_background, background_id)
            except ResearchUnavailableError as exc:
                # No reason class is provably deterministic from one poll: a
                # 401/403 can be an edge or WAF in front of the provider and a
                # malformed body can be a 200 interstitial, so every reason
                # earns the rest of the deadline and the deadline alone owns
                # giving up.
                if time.monotonic() > deadline:
                    _fail_job(
                        job_id=job_id,
                        user_id=user_id,
                        detail=f"poll: {exc.reason}: {exc.detail or ''}",
                        post_note=True,
                        job_request=job_request,
                        conversation_id=conversation_id,
                    )
                    return
                continue
            if not marked_running and poll.status == "in_progress":
                marked_running = True
                _mark_running(job_id=job_id, user_id=user_id)
            if poll.terminal:
                if poll.status == "completed" and poll.packet is not None:
                    await _finalize_success(
                        job_id=job_id,
                        job_request=job_request,
                        packet=poll.packet,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        request_id=request_id,
                    )
                else:
                    _fail_job(
                        job_id=job_id,
                        user_id=user_id,
                        detail=poll.failure_detail or poll.status,
                        post_note=True,
                        job_request=job_request,
                        conversation_id=conversation_id,
                    )
                return
            if time.monotonic() > deadline:
                _fail_job(
                    job_id=job_id,
                    user_id=user_id,
                    detail="background deadline exceeded",
                    post_note=True,
                    job_request=job_request,
                    conversation_id=conversation_id,
                )
                return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Research job poller crashed", job_id=job_id, error=str(exc))
        _fail_job(job_id=job_id, user_id=user_id, detail="poller crash")


def _mark_running(*, job_id: str, user_id: str) -> None:
    gateway = api_state.supabase_gateway
    if gateway is None:
        return
    try:
        gateway.mark_backtest_job_running(user_id=user_id, job_id=job_id)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Research job running mark skipped", error=str(exc))


# The completion mark is the row's only way out of running once the answer is
# persisted; no scheduled janitor revisits a research row. Retry it, and if it
# still fails, fail the row with the answer linked so the conversation settles
# and the answer still paints.
COMPLETION_MARK_ATTEMPTS = 3
COMPLETION_MARK_RETRY_SECONDS = 2.0


async def _finalize_success(
    *,
    job_id: str,
    job_request: dict[str, Any],
    packet: ResearchPacket,
    user_id: str,
    conversation_id: str,
    request_id: str | None,
) -> None:
    from argus.agent_runtime.research_answer import (
        compose_completed_research,
        store_research_packet_for_job,
    )
    from argus.api.message_store import create_message

    store_research_packet_for_job(job_request, packet)
    composed = compose_completed_research(job_request=job_request, packet=packet)
    metadata: dict[str, Any] = {
        "conversation_mode": "guide",
        "research": composed["research"],
    }
    if composed.get("next_experiments") is not None:
        metadata["next_experiments"] = composed["next_experiments"]
    try:
        message = create_message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content=composed["answer"],
            metadata=metadata,
            settle_usage=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Research result message persistence failed",
            job_id=job_id,
            error=str(exc),
        )
        _fail_job(job_id=job_id, user_id=user_id, detail="result persistence failed")
        return
    await _mark_completed(job_id=job_id, user_id=user_id, message_id=message.id)
    record_research_turn_evidence(
        research=composed["research"],
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message.id,
        request_id=request_id,
    )


async def _mark_completed(*, job_id: str, user_id: str, message_id: str) -> None:
    gateway = api_state.supabase_gateway
    if gateway is None:
        return
    for attempt in range(1, COMPLETION_MARK_ATTEMPTS + 1):
        try:
            gateway.complete_research_job(
                user_id=user_id,
                job_id=job_id,
                execution_metadata={"research_result_message_id": message_id},
            )
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Research job completion mark failed",
                job_id=job_id,
                attempt=attempt,
                error=str(exc),
            )
            if attempt < COMPLETION_MARK_ATTEMPTS:
                await asyncio.sleep(COMPLETION_MARK_RETRY_SECONDS)
    _fail_job(
        job_id=job_id,
        user_id=user_id,
        detail="completion mark failed",
        result_message_id=message_id,
    )


def _fail_job(
    *,
    job_id: str,
    user_id: str,
    detail: str,
    post_note: bool = False,
    job_request: dict[str, Any] | None = None,
    conversation_id: str | None = None,
    result_message_id: str | None = None,
) -> None:
    # The note is persisted first so the failed row can name it: a terminal
    # research row's message, answer or note, is served as the job's
    # result_message and painted in place.
    message_id = result_message_id
    if post_note and conversation_id and job_request is not None:
        message_id = _persist_failure_note(
            job_id=job_id,
            user_id=user_id,
            conversation_id=conversation_id,
            job_request=job_request,
        )
    gateway = api_state.supabase_gateway
    if gateway is None:
        return
    try:
        gateway.mark_backtest_job_failed(
            user_id=user_id,
            job_id=job_id,
            failure_code="research_failed",
            failure_detail=detail[:500],
            retryable=False,
            execution_metadata=(
                {"research_result_message_id": message_id} if message_id else None
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Research job failure mark failed; the row stays active until an"
            " operator settles it",
            job_id=job_id,
            error=str(exc),
        )


def _persist_failure_note(
    *,
    job_id: str,
    user_id: str,
    conversation_id: str,
    job_request: dict[str, Any],
) -> str | None:
    from argus.agent_runtime.research_answer import research_failure_note
    from argus.api.message_store import create_message

    try:
        note = create_message(
            user_id=user_id,
            conversation_id=conversation_id,
            role="assistant",
            content=research_failure_note(str(job_request.get("language") or "en")),
            metadata={"conversation_mode": "guide"},
            settle_usage=None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Research failure note persistence failed",
            job_id=job_id,
            error=str(exc),
        )
        return None
    return note.id
