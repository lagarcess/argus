from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from argus.api import state as api_state
from argus.api.dependencies import current_user, problem
from argus.api.memory_ownership import memory_object_visible
from argus.api.schemas import (
    BacktestJob,
    BacktestJobResponse,
    BacktestRunRequest,
    BacktestRunResponse,
    User,
)
from argus.domain import backtest_admission
from argus.domain.backtest_finalization import (
    BacktestFinalizationError,
    stable_backtest_run_id,
)

router = APIRouter(prefix="/api/v1", tags=["backtests"])


@router.post("/backtests/run", response_model=BacktestRunResponse)
def run_backtest(
    payload: BacktestRunRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    clean_idempotency_key = _clean_required_idempotency_key(
        request=request,
        idempotency_key=idempotency_key,
    )

    if payload.conversation_id:
        conversation = None
        if api_state.supabase_gateway is not None:
            conversation = api_state.supabase_gateway.get_conversation(
                user_id=user.id,
                conversation_id=payload.conversation_id,
            )
        else:
            owner_id = api_state.store.conversation_owners.get(payload.conversation_id)
            if owner_id in {None, user.id}:
                conversation = api_state.store.conversations.get(payload.conversation_id)
        if conversation is None:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Conversation not found.",
            )

    data = payload.model_dump(exclude_none=True)
    if payload.strategy_id:
        strategy = None
        if api_state.supabase_gateway is not None:
            strategy = api_state.supabase_gateway.get_strategy(
                user_id=user.id,
                strategy_id=payload.strategy_id,
            )
        else:
            if memory_object_visible(
                owner_map=api_state.store.strategy_owners,
                object_id=payload.strategy_id,
                user_id=user.id,
            ):
                strategy = api_state.store.strategies.get(payload.strategy_id)

        if not strategy:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Strategy not found.",
            )
        strategy_data = strategy.model_dump()
        data = {
            **strategy_data,
            **data,
            "template": strategy.template,
            "asset_class": strategy.asset_class,
            "symbols": data.get("symbols") or strategy.symbols,
            "parameters": strategy.parameters,
            "benchmark_symbol": strategy.benchmark_symbol,
        }
    if not data.get("template"):
        data["template"] = "rsi_mean_reversion"
    from argus.api.backtest_service import (
        create_run_from_payload,
        prepare_run_from_payload,
    )
    from argus.api.chat.evidence import finalize_completed_backtest

    _validate_direct_payload_shape(data, request)
    normalized_payload = backtest_admission.normalize_direct_launch_payload(data)
    identity_hash = backtest_admission.direct_run_identity_hash(
        conversation_id=payload.conversation_id,
        strategy_id=payload.strategy_id,
        normalized_payload=normalized_payload,
    )
    launch_payload_digest = backtest_admission.canonical_hash(normalized_payload)

    # Exact replay resolves before quota, capacity, or compute; a collision
    # returns before any boundary can disclose or mutate state.
    existing = _find_direct_reservation(user=user, idempotency_key=clean_idempotency_key)
    if existing is not None:
        # The atomic operation re-resolves the replay (and reconciles a stale
        # running direct row) without charging; a mismatched identity conflicts.
        decision, job = _admit_direct_run(
            request,
            user=user,
            idempotency_key=clean_idempotency_key,
            identity_hash=identity_hash,
            payload_hash=launch_payload_digest,
            launch_payload=normalized_payload,
            conversation_id=payload.conversation_id,
        )
        if decision == "replay":
            return _replay_direct_job(request, user=user, job=job or {})

    # Non-consuming allowance precheck: exhausted quota rejects before any
    # provider preflight and mutates nothing (#251 locked decision).
    _precheck_direct_allowance(request, user=user)

    # Coverage/provider preflight consumes no allowance and creates no job;
    # only successful durable admission charges (#251 locked decision).
    prepared_execution = prepare_run_from_payload(data, request)

    decision, job = _admit_direct_run(
        request,
        user=user,
        idempotency_key=clean_idempotency_key,
        identity_hash=identity_hash,
        payload_hash=launch_payload_digest,
        launch_payload=normalized_payload,
        conversation_id=payload.conversation_id,
    )
    if decision == "replay":
        return _replay_direct_job(request, user=user, job=job or {})

    job_id = str((job or {}).get("id") or "").strip()
    execution_identity = backtest_admission.direct_execution_identity(
        clean_idempotency_key
    )
    try:
        run = create_run_from_payload(
            data,
            request,
            user=user,
            user_id=user.id,
            persist_in_memory=False,
            language=user.language,
            run_id=stable_backtest_run_id(user.id, execution_identity),
            prepared_execution=prepared_execution,
        )
        run = finalize_completed_backtest(
            user_id=user.id,
            conversation_id=run.conversation_id,
            run=run,
            execution_identity=execution_identity,
        ).run
    except BacktestFinalizationError as exc:
        _finalize_direct_job(
            user=user,
            job_id=job_id,
            status="failed",
            failure_code="finalization_failed",
            failure_detail="finalization_failed",
            retryable=True,
            failure_status=503,
        )
        raise problem(
            request,
            status_code=503,
            code="finalization_failed",
            title="Backtest Finalization Failed",
            detail="The backtest finished, but its result could not be saved safely.",
            context={"retryable": True},
            headers={"Retry-After": "1"},
        ) from exc
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        _finalize_direct_job(
            user=user,
            job_id=job_id,
            status="failed",
            failure_code=str(detail.get("code") or "execution_failed"),
            failure_detail=str(detail.get("detail") or "execution_failed"),
            retryable=False,
            failure_status=exc.status_code,
        )
        raise
    except Exception:
        # An unexpected crash still transitions the durable row to a terminal
        # state; the admitted unit stays consumed and replay returns the
        # durable failure rather than re-executing.
        _finalize_direct_job(
            user=user,
            job_id=job_id,
            status="failed",
            failure_code="execution_failed",
            failure_detail="execution_interrupted",
            retryable=True,
            failure_status=500,
        )
        raise

    _finalize_direct_job(
        user=user,
        job_id=job_id,
        status="succeeded",
        result_run_id=run.id,
    )
    return BacktestRunResponse(run=run)


def _precheck_direct_allowance(request: Request, *, user: User) -> None:
    gateway = api_state.supabase_gateway
    if gateway is None:
        return
    from argus.domain.supabase_gateway import QuotaExceededError

    try:
        gateway.check_usage_limits(
            user_id=user.id,
            resource="backtest_runs",
            limits=[("day", 50)],
        )
    except QuotaExceededError as exc:
        raise problem(
            request,
            status_code=429,
            code="too_many_requests",
            title="Quota Exceeded",
            detail=str(exc),
            headers={"Retry-After": "60"},
        ) from exc


def _find_direct_reservation(
    *, user: User, idempotency_key: str
) -> dict[str, Any] | None:
    gateway = api_state.supabase_gateway
    if gateway is not None:
        return gateway.get_backtest_job_by_reservation(
            user_id=user.id,
            operation_scope=backtest_admission.DIRECT_RUN_SCOPE,
            idempotency_key=idempotency_key,
        )
    with api_state.store.backtest_admission_lock:
        backtest_admission.reconcile_stale_direct_jobs_memory(api_state.store)
        reservation = api_state.store.backtest_job_reservations.get(
            (user.id, backtest_admission.DIRECT_RUN_SCOPE, idempotency_key)
        )
        if reservation is None:
            return None
        job = api_state.store.backtest_jobs.get(reservation)
        return dict(job) if job is not None else None


def _validate_direct_payload_shape(data: dict[str, Any], request: Request) -> None:
    """The #229 contract validates and materializes the launch request before
    hashing; invalid shapes reject before admission and consume nothing."""

    from argus.api.backtest_service import (
        ensure_same_asset_or_raise,
        raise_backtest_problem,
    )

    symbols = data.get("symbols") or []
    if not symbols:
        raise problem(
            request,
            status_code=400,
            code="validation_error",
            title="Validation Error",
            detail="Symbol is required.",
        )
    inferred_asset_class, classified_symbols = ensure_same_asset_or_raise(
        symbols, request
    )
    requested_asset_class = data.get("asset_class")
    if requested_asset_class and requested_asset_class != inferred_asset_class:
        raise_backtest_problem(
            request,
            "asset_class_conflict",
            context={
                "requested_asset_class": requested_asset_class,
                "inferred_asset_class": inferred_asset_class,
                "symbols": [entry.symbol for entry in classified_symbols],
            },
        )


def _admit_direct_run(
    request: Request,
    *,
    user: User,
    idempotency_key: str,
    identity_hash: str,
    payload_hash: str,
    launch_payload: dict[str, Any],
    conversation_id: str | None,
) -> tuple[str, dict[str, Any] | None]:
    gateway = api_state.supabase_gateway
    if gateway is not None:
        outcome = gateway.admit_backtest_job(
            user_id=user.id,
            operation_scope=backtest_admission.DIRECT_RUN_SCOPE,
            idempotency_key=idempotency_key,
            identity_hash=identity_hash,
            payload_hash=payload_hash,
            launch_payload=launch_payload,
            initial_status="running",
            conversation_id=conversation_id,
            execution_metadata={"source": "api_direct"},
        )
        decision = str(outcome.get("decision") or "")
        job = outcome.get("job") if isinstance(outcome.get("job"), dict) else None
        outcome_detail = outcome.get("detail")
    else:
        memory_outcome = backtest_admission.admit_backtest_job_memory(
            api_state.store,
            user_id=user.id,
            operation_scope=backtest_admission.DIRECT_RUN_SCOPE,
            idempotency_key=idempotency_key,
            identity_hash=identity_hash,
            payload_hash=payload_hash,
            launch_payload=launch_payload,
            initial_status="running",
            conversation_id=conversation_id,
            execution_metadata={"source": "api_direct"},
        )
        decision = memory_outcome.kind
        job = memory_outcome.job
        outcome_detail = None

    if decision in ("admitted", "replay"):
        return decision, job
    if decision == "conflict":
        raise problem(
            request,
            status_code=409,
            code="idempotency_conflict",
            title="Idempotency Conflict",
            detail=(
                "This Idempotency-Key is already reserved for a different "
                "request. Use a new key for a new execution."
            ),
        )
    if decision == "allowance_exhausted":
        raise problem(
            request,
            status_code=429,
            code="too_many_requests",
            title="Quota Exceeded",
            detail=str(
                (outcome_detail if isinstance(outcome_detail, str) else "")
                or "Daily simulation allowance exhausted."
            ),
            headers={"Retry-After": "60"},
        )
    if decision == "per_user_capacity":
        raise problem(
            request,
            status_code=429,
            code="backtest_capacity_exceeded",
            title="Backtest Capacity Exceeded",
            detail="Your other simulations are still in progress. Retry shortly.",
            headers={"Retry-After": "15"},
        )
    if decision == "global_capacity":
        raise problem(
            request,
            status_code=503,
            code="backtest_capacity_exceeded",
            title="Backtest Capacity Exceeded",
            detail="Simulation capacity is briefly saturated. Retry shortly.",
            headers={"Retry-After": "15"},
        )
    raise problem(
        request,
        status_code=500,
        code="internal_error",
        title="Internal Error",
        detail="Backtest admission returned an unknown decision.",
    )


def _replay_direct_job(
    request: Request, *, user: User, job: dict[str, Any]
) -> BacktestRunResponse:
    status = str(job.get("status") or "").strip().lower()
    job_id = str(job.get("id") or "").strip()
    if status == "succeeded":
        run_id = str(job.get("result_run_id") or "").strip()
        run = (
            api_state.supabase_gateway.get_backtest_run(user_id=user.id, run_id=run_id)
            if api_state.supabase_gateway is not None
            else api_state.store.backtest_runs.get(run_id)
        )
        if run is not None:
            return BacktestRunResponse(run=run)
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Admitted job is succeeded but its Run is unavailable.",
        )
    if status in ("queued", "running"):
        raise problem(
            request,
            status_code=409,
            code="idempotency_in_progress",
            title="Idempotency In Progress",
            detail="This execution is still in progress. Retry shortly.",
            context={"backtest_job_id": job_id},
            headers={"Retry-After": "1"},
        )
    metadata = job.get("execution_metadata")
    failure_status = 503
    if isinstance(metadata, dict):
        recorded = metadata.get("failure_status")
        if isinstance(recorded, int) and 400 <= recorded <= 599:
            failure_status = recorded
    raise problem(
        request,
        status_code=failure_status,
        code=str(job.get("failure_code") or "execution_failed"),
        title="Backtest Execution Failed",
        detail=str(job.get("failure_detail") or "execution_failed"),
        context={"retryable": bool(job.get("retryable"))},
        headers={"Retry-After": "1"} if job.get("retryable") else None,
    )


def _finalize_direct_job(
    *,
    user: User,
    job_id: str,
    status: str,
    result_run_id: str | None = None,
    failure_code: str | None = None,
    failure_detail: str | None = None,
    retryable: bool = False,
    failure_status: int | None = None,
) -> None:
    if not job_id:
        return
    gateway = api_state.supabase_gateway
    if gateway is not None:
        metadata: dict[str, Any] | None = None
        if failure_status is not None:
            job = gateway.get_backtest_job(user_id=user.id, job_id=job_id) or {}
            metadata = dict(job.get("execution_metadata") or {})
            metadata["failure_status"] = failure_status
        gateway.finalize_direct_backtest_job(
            user_id=user.id,
            job_id=job_id,
            status=status,
            result_run_id=result_run_id,
            failure_code=failure_code,
            failure_detail=failure_detail,
            retryable=retryable,
            execution_metadata=metadata,
        )
        return
    with api_state.store.backtest_admission_lock:
        job = api_state.store.backtest_jobs.get(job_id)
        if job is not None and failure_status is not None:
            metadata = dict(job.get("execution_metadata") or {})
            metadata["failure_status"] = failure_status
            job["execution_metadata"] = metadata
    backtest_admission.finalize_direct_job_memory(
        api_state.store,
        job_id=job_id,
        status=status,  # type: ignore[arg-type]
        result_run_id=result_run_id,
        failure_code=failure_code,
        failure_detail=failure_detail,
        retryable=retryable,
    )


def _clean_required_idempotency_key(
    *,
    request: Request,
    idempotency_key: str | None,
) -> str:
    state, key = backtest_admission.validate_idempotency_key(idempotency_key)
    if state == "ok" and key is not None:
        return key
    if state == "invalid":
        raise problem(
            request,
            status_code=422,
            code="validation_error",
            title="Validation Error",
            detail=(
                "Idempotency-Key must be 1-128 visible ASCII characters "
                "with no whitespace."
            ),
        )
    raise problem(
        request,
        status_code=400,
        code="idempotency_key_required",
        title="Idempotency Key Required",
        detail="POST /backtests/run requires an Idempotency-Key header.",
    )


@router.get(
    "/backtest-jobs/by-action/{confirmation_id}",
    response_model=BacktestJobResponse,
)
def get_backtest_job_by_action(
    confirmation_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestJobResponse:
    """#242: owner-scoped durable lookup for an ambiguous Run action.

    Transport ambiguity resolves against durable truth: 404 means no
    reservation exists (the client may replay the action once); 409 means the
    key was paired with different identity data; 500 means required
    confirmation-artifact integrity failed and the client must not replay.
    """

    gateway = api_state.supabase_gateway
    if gateway is not None:
        job = gateway.get_backtest_job_by_reservation(
            user_id=user.id,
            operation_scope=backtest_admission.CHAT_RUN_SCOPE,
            idempotency_key=confirmation_id,
        )
    else:
        with api_state.store.backtest_admission_lock:
            reservation = api_state.store.backtest_job_reservations.get(
                (user.id, backtest_admission.CHAT_RUN_SCOPE, confirmation_id)
            )
            job = (
                dict(api_state.store.backtest_jobs[reservation])
                if reservation is not None
                and reservation in api_state.store.backtest_jobs
                else None
            )
    if job is None:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="No durable Run reservation exists for this action.",
        )

    artifact_conversation_id, artifact_launch_hash = _confirmation_artifact_identity(
        request, user=user, job=job, confirmation_id=confirmation_id
    )

    # Expected identity recomputes from the immutable confirmation artifact,
    # never from mutable job fields.
    expected_identity = backtest_admission.chat_run_identity_hash(
        conversation_id=artifact_conversation_id,
        confirmation_id=confirmation_id,
        launch_payload_hash=artifact_launch_hash,
    )
    if job.get("identity_hash") != expected_identity:
        raise problem(
            request,
            status_code=409,
            code="idempotency_conflict",
            title="Idempotency Conflict",
            detail="The action identity does not match the durable reservation.",
        )

    run = None
    result_run_id = str(job.get("result_run_id") or "")
    if job.get("status") == "succeeded" and result_run_id:
        run = (
            gateway.get_backtest_run(user_id=user.id, run_id=result_run_id)
            if gateway is not None
            else api_state.store.backtest_runs.get(result_run_id)
        )
    return BacktestJobResponse(job=BacktestJob.model_validate(job), run=run)


def _confirmation_artifact_identity(
    request: Request,
    *,
    user: User,
    job: dict[str, Any],
    confirmation_id: str,
) -> tuple[str, str]:
    """Load the immutable confirmation artifact linked by the chat job and
    return its identity inputs. A missing link, missing message, ownership or
    conversation mismatch, absent confirmation card, mismatched
    confirmation_id, or absent full-width launch hash is inconsistent durable
    state: 500, never a replay signal."""

    integrity_failure = problem(
        request,
        status_code=500,
        code="internal_error",
        title="Internal Error",
        detail=(
            "Durable confirmation-artifact integrity failed; do not replay "
            "the Run action."
        ),
    )

    message_id = str(job.get("confirmation_message_id") or "").strip()
    conversation_id = str(job.get("conversation_id") or "").strip()
    if not message_id or not conversation_id:
        raise integrity_failure

    gateway = api_state.supabase_gateway
    if gateway is not None:
        row = gateway.get_message_row(message_id=message_id)
        message_conversation = str((row or {}).get("conversation_id") or "")
        metadata = (row or {}).get("metadata")
    else:
        message = next(
            (
                candidate
                for candidate in api_state.store.messages.get(conversation_id, [])
                if candidate.id == message_id
            ),
            None,
        )
        message_conversation = message.conversation_id if message else ""
        metadata = message.metadata if message else None

    if message_conversation != conversation_id:
        raise integrity_failure
    if (
        api_state.store.conversation_owners.get(conversation_id)
        not in (
            None,
            user.id,
        )
        and gateway is None
    ):
        raise integrity_failure

    artifact = metadata if isinstance(metadata, dict) else {}
    card = artifact.get("confirmation_card")
    if not isinstance(card, dict):
        raise integrity_failure
    artifact_confirmation = str(card.get("confirmation_id") or "").strip()
    if artifact_confirmation != confirmation_id:
        raise integrity_failure
    launch_hash = card.get("launch_payload_hash_full")
    if not isinstance(launch_hash, str) or not launch_hash.startswith("sha256:"):
        raise integrity_failure
    return message_conversation, launch_hash


@router.get("/backtest-jobs/{job_id}", response_model=BacktestJobResponse)
def get_backtest_job(
    job_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestJobResponse:
    if api_state.supabase_gateway is None:
        with api_state.store.backtest_admission_lock:
            backtest_admission.reconcile_stale_direct_jobs_memory(
                api_state.store, only_job_id=job_id
            )
            memory_job = api_state.store.backtest_jobs.get(job_id)
        if memory_job is None or memory_job.get("user_id") != user.id:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Backtest job not found.",
            )
        memory_run = None
        result_run_id = str(memory_job.get("result_run_id") or "")
        if memory_job.get("status") == "succeeded" and result_run_id:
            memory_run = api_state.store.backtest_runs.get(result_run_id)
        return BacktestJobResponse(
            job=BacktestJob.model_validate(memory_job),
            run=memory_run,
        )

    # #231: ordinary polls are database-only. The bounded stale scanner is the
    # single Render reconciliation owner; fresh and stale reads alike return
    # canonical Supabase state without provider calls.
    job = api_state.supabase_gateway.get_backtest_job(user_id=user.id, job_id=job_id)
    if not job:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Backtest job not found.",
        )

    run = None
    result_run_id = job.get("result_run_id")
    if (
        job.get("status") == "succeeded"
        and isinstance(result_run_id, str)
        and result_run_id
    ):
        run = api_state.supabase_gateway.get_backtest_run(
            user_id=user.id,
            run_id=result_run_id,
        )
    readout = _result_readout_from_job(job) if run is not None else None
    readout_metadata = _result_readout_metadata_from_job(job) if run is not None else {}
    return BacktestJobResponse(
        job=BacktestJob.model_validate(job),
        run=run,
        result_readout=readout,
        **readout_metadata,
    )


@router.get("/backtests/{run_id}", response_model=BacktestRunResponse)
def get_backtest(
    run_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    run = (
        api_state.supabase_gateway.get_backtest_run(user_id=user.id, run_id=run_id)
        if api_state.supabase_gateway is not None
        else api_state.store.backtest_runs.get(run_id)
    )
    if not run:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Backtest run not found.",
        )
    return BacktestRunResponse(run=run)


def _result_readout_from_job(job: dict[str, object]) -> str | None:
    execution_metadata = job.get("execution_metadata")
    if not isinstance(execution_metadata, dict):
        return None
    workflow_metadata = execution_metadata.get("workflow_backtest")
    if not isinstance(workflow_metadata, dict):
        return None
    result_readout = workflow_metadata.get("result_readout")
    if not isinstance(result_readout, str):
        return None
    normalized = result_readout.strip()
    return normalized or None


def _result_readout_metadata_from_job(job: dict[str, object]) -> dict[str, object]:
    execution_metadata = job.get("execution_metadata")
    if not isinstance(execution_metadata, dict):
        return {}
    workflow_metadata = execution_metadata.get("workflow_backtest")
    if not isinstance(workflow_metadata, dict):
        return {}
    metadata: dict[str, object] = {}
    source = workflow_metadata.get("result_readout_source")
    if isinstance(source, str) and source.strip():
        metadata["result_readout_source"] = source.strip()
    fallback_used = workflow_metadata.get("result_readout_fallback_used")
    if isinstance(fallback_used, bool):
        metadata["result_readout_fallback_used"] = fallback_used
    failure_mode = workflow_metadata.get("result_readout_failure_mode")
    if isinstance(failure_mode, str) and failure_mode.strip():
        metadata["result_readout_failure_mode"] = failure_mode.strip()
    return metadata
