from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from argus.api import state as api_state
from argus.api.backtest_service import create_run_from_payload
from argus.api.dependencies import current_user, problem
from argus.api.schemas import (
    BacktestJob,
    BacktestJobResponse,
    BacktestRunRequest,
    BacktestRunResponse,
    User,
)
from argus.domain.supabase_gateway import QuotaExceededError

router = APIRouter(prefix="/api/v1", tags=["backtests"])


@router.post("/backtests/run", response_model=BacktestRunResponse)
def run_backtest(
    payload: BacktestRunRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    endpoint = "/api/v1/backtests/run"
    if idempotency_key:
        cached = api_state.store.idempotency.get((user.id, endpoint, idempotency_key))
        if cached:
            return BacktestRunResponse(run=cached)

    if api_state.supabase_gateway is not None:
        try:
            api_state.supabase_gateway.check_and_increment_usage(
                user_id=user.id,
                resource="backtest_runs",
                period="day",
                limit_count=50,
            )
            api_state.supabase_gateway.check_and_increment_usage(
                user_id=user.id,
                resource="backtest_runs",
                period="hour",
                limit_count=10,
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

    data = payload.model_dump(exclude_none=True)
    if payload.strategy_id:
        strategy = None
        if api_state.supabase_gateway is not None:
            strategy = api_state.supabase_gateway.get_strategy(
                user_id=user.id,
                strategy_id=payload.strategy_id,
            )
        else:
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
    run = create_run_from_payload(
        data,
        request,
        user=user,
        user_id=user.id,
        persist_in_memory=api_state.supabase_gateway is None,
        language=user.language,
    )
    if api_state.supabase_gateway is not None:
        run = api_state.supabase_gateway.create_backtest_run(user_id=user.id, run=run)
    if idempotency_key:
        api_state.store.idempotency[(user.id, endpoint, idempotency_key)] = run
    return BacktestRunResponse(run=run)


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

    run = None
    result_run_id = job.get("result_run_id")
    if isinstance(result_run_id, str) and result_run_id:
        run = api_state.supabase_gateway.get_backtest_run(
            user_id=user.id,
            run_id=result_run_id,
        )
    return BacktestJobResponse(job=BacktestJob.model_validate(job), run=run)


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
