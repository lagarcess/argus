from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from argus.api import state as api_state
from argus.api.chat.backtest_jobs import reconcile_terminal_render_task_run
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
from argus.domain.supabase_gateway import QuotaExceededError
from argus.domain.usage_limits import SIMULATION_ALLOWANCE_LIMITS

router = APIRouter(prefix="/api/v1", tags=["backtests"])


@router.post("/backtests/run", response_model=BacktestRunResponse)
def run_backtest(
    payload: BacktestRunRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    endpoint = "/api/v1/backtests/run"
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
    from argus.api.chat.evidence import finalize_completed_direct_backtest

    _validate_direct_payload_shape(data, request)
    normalized_payload = backtest_admission.normalize_direct_launch_payload(data)
    identity_hash = backtest_admission.direct_run_identity_hash(
        conversation_id=payload.conversation_id,
        strategy_id=payload.strategy_id,
        normalized_payload=normalized_payload,
    )
    launch_payload_digest = backtest_admission.canonical_hash(normalized_payload)

    # An exact replay resolves before quota, preflight, or compute. The
    # reservation pre-read only decides whether preflight may run; the atomic
    # admission operation stays the authority for replay/collision races.
    if _direct_reservation_exists(user=user, idempotency_key=clean_idempotency_key):
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

    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.check_usage_limits(
                user_id=user.id,
                resource="backtest_runs",
                limits=SIMULATION_ALLOWANCE_LIMITS,
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
    execution_identity = f"{endpoint}:{clean_idempotency_key}"
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
        finalized = finalize_completed_direct_backtest(
            user_id=user.id,
            conversation_id=run.conversation_id,
            run=run,
            execution_identity=execution_identity,
            job_id=job_id,
        )
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
        _finalize_direct_job(
            user=user,
            job_id=job_id,
            status="failed",
            failure_code="execution_failed",
            failure_detail="unexpected_error",
            retryable=False,
            failure_status=500,
        )
        raise

    if finalized is None:
        # A reconciled terminal outcome is final; a late success is discarded.
        raise problem(
            request,
            status_code=503,
            code="direct_execution_abandoned",
            title="Backtest Execution Abandoned",
            detail=(
                "This execution ran past the staleness boundary and was "
                "reconciled as abandoned. Start it again with a new "
                "Idempotency-Key."
            ),
            context={"backtest_job_id": job_id, "retryable": True},
        )
    return BacktestRunResponse(run=finalized.run)


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


def _direct_reservation_exists(*, user: User, idempotency_key: str) -> bool:
    gateway = api_state.supabase_gateway
    if gateway is not None:
        return (
            gateway.get_backtest_job_reservation(
                user_id=user.id,
                operation_scope=backtest_admission.DIRECT_RUN_SCOPE,
                idempotency_key=idempotency_key,
            )
            is not None
        )
    with api_state.store.backtest_admission_lock:
        return (
            user.id,
            backtest_admission.DIRECT_RUN_SCOPE,
            idempotency_key,
        ) in api_state.store.backtest_job_reservations


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
            allowance_limits=SIMULATION_ALLOWANCE_LIMITS,
        )
        decision = memory_outcome.kind
        job = memory_outcome.job

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
            detail="Simulation allowance exhausted for the current window.",
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
) -> dict[str, Any] | None:
    if not job_id:
        return None
    gateway = api_state.supabase_gateway
    if gateway is not None:
        metadata: dict[str, Any] | None = None
        if failure_status is not None:
            job = gateway.get_backtest_job(user_id=user.id, job_id=job_id) or {}
            metadata = dict(job.get("execution_metadata") or {})
            metadata["failure_status"] = failure_status
        return gateway.finalize_direct_backtest_job(
            user_id=user.id,
            job_id=job_id,
            status=status,
            result_run_id=result_run_id,
            failure_code=failure_code,
            failure_detail=failure_detail,
            retryable=retryable,
            execution_metadata=metadata,
        )
    with api_state.store.backtest_admission_lock:
        job = api_state.store.backtest_jobs.get(job_id)
        if job is not None and failure_status is not None:
            metadata = dict(job.get("execution_metadata") or {})
            metadata["failure_status"] = failure_status
            job["execution_metadata"] = metadata
    return backtest_admission.finalize_direct_job_memory(
        api_state.store,
        job_id=job_id,
        status=status,  # type: ignore[arg-type]
        result_run_id=result_run_id,
        failure_code=failure_code,
        failure_detail=failure_detail,
        retryable=retryable,
    )


@router.get("/backtest-jobs/{job_id}", response_model=BacktestJobResponse)
def get_backtest_job(
    job_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestJobResponse:
    if api_state.supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for backtest job status.",
        )

    job = api_state.supabase_gateway.get_backtest_job(user_id=user.id, job_id=job_id)
    if not job:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Backtest job not found.",
        )
    job = reconcile_terminal_render_task_run(
        gateway=api_state.supabase_gateway,
        user_id=user.id,
        job=job,
    )
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
