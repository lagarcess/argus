"""Local-only HTTP composition root with separate fixture credentials."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .calculator import CalculationError
from .interpreter import create_interpreter
from .models import PlacementInputs
from .platform import composition
from .platform.common import PlatformError, get_context, require_editor, require_owner
from .platform.jobs_runtime import enqueue_job, run_worker
from .platform.runtime import RuntimeMiddleware
from .service import PlacementService, ServiceError
from .store import Store


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InterpretBody(RequestBody):
    message: str = Field(min_length=1, max_length=4000)
    locale: Literal["es-419", "en"] = "es-419"
    demo_example_id: str | None = Field(default=None, max_length=100)


class ComputeBody(RequestBody):
    inputs: PlacementInputs


class DemoEventBody(RequestBody):
    scenario: Literal["same_winner", "leader_changed", "inflation_crossed", "failure"]
    idempotency_key: str = Field(
        default_factory=lambda: uuid4().hex, min_length=1, max_length=128
    )


def create_app(database_path: str | Path | None = None, interpreter=None) -> FastAPI:
    path = (
        database_path
        or os.environ.get("CLARA_DATABASE_PATH")
        or (Path(__file__).resolve().parents[1] / ".local" / "clara.sqlite3")
    )
    semantic_interpreter = (
        interpreter if interpreter is not None else create_interpreter()
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        store = Store(path)
        service = PlacementService(store)
        composition.initialize(application, store)
        service.bootstrap()
        application.state.service = service
        stop_worker = asyncio.Event()
        worker = asyncio.create_task(run_worker(store, stop_worker))
        try:
            yield
        finally:
            stop_worker.set()
            await worker

    application = FastAPI(title="Clara local demo", lifespan=lifespan)
    application.add_middleware(RuntimeMiddleware)
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )
    composition.mount(application)

    @application.exception_handler(PlatformError)
    async def platform_error(_request: Request, exc: PlatformError):
        return JSONResponse(status_code=exc.status, content={"code": exc.code})

    def placement(request: Request, *, write: bool = False) -> PlacementService:
        context = get_context(request)
        if write:
            require_editor(context)
        return PlacementService(
            request.app.state.store, context.household_id, context=context
        )

    @application.exception_handler(ServiceError)
    async def service_error(_request: Request, exc: ServiceError):
        body = {"code": exc.code}
        if exc.detail:
            body["detail"] = exc.detail
        return JSONResponse(status_code=exc.status, content=body)

    @application.exception_handler(CalculationError)
    async def calculation_error(_request: Request, exc: CalculationError):
        return JSONResponse(status_code=422, content={"code": exc.code})

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"code": "invalid_request"})

    @application.get("/api/home")
    def home(request: Request):
        return placement(request).home(semantic_interpreter.mode)

    @application.post("/api/confirmations")
    def prepare(body: ComputeBody, request: Request):
        return placement(request, write=True).create_confirmation(body.inputs)

    @application.post("/api/interpret")
    async def interpret(body: InterpretBody, request: Request):
        context = await run_in_threadpool(get_context, request)
        require_editor(context)
        service = PlacementService(
            request.app.state.store, context.household_id, context=context
        )
        interpretation = await semantic_interpreter.interpret(
            body.message,
            body.locale,
            body.demo_example_id,
            admission=(request.app.state.store, context),
        )
        if interpretation.status == "confirmation":
            return {
                "status": "confirmation",
                "confirmation": await run_in_threadpool(
                    service.create_confirmation, interpretation.inputs
                ),
            }
        return interpretation.model_dump(
            mode="json", exclude={"inputs"}, exclude_none=True
        )

    @application.post("/api/confirmations/{confirmation_id}/compute")
    def compute(confirmation_id: str, body: ComputeBody, request: Request):
        return placement(request, write=True).compute(confirmation_id, body.inputs)

    @application.post("/api/comparisons/{comparison_id}/save")
    def save(comparison_id: str, request: Request):
        return placement(request, write=True).save(comparison_id)

    @application.get("/api/decisions/{decision_id}")
    def decision(decision_id: str, request: Request):
        return placement(request).decision(decision_id)

    @application.get("/api/notices")
    def notices(request: Request):
        return placement(request).notices()

    @application.get("/api/notices/summary")
    def notice_summaries(
        request: Request,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        return placement(request).notice_summaries(limit=limit, offset=offset)

    @application.post("/api/notices/{notice_id}/read")
    def read_notice(notice_id: str, request: Request):
        return placement(request).read_notice(notice_id)

    @application.get("/api/sources/{source_id}")
    def source(source_id: str, request: Request):
        return request.app.state.service.source(source_id)

    @application.post("/api/demo/events", status_code=202)
    def demo_event(body: DemoEventBody, request: Request):
        context = get_context(request)
        require_owner(context)
        load_id = uuid5(
            NAMESPACE_URL, f"clara-deposit:{context.household_id}:{body.idempotency_key}"
        ).hex
        job = enqueue_job(
            request.app.state.store,
            context,
            "deposit_load",
            {"scenario": body.scenario, "load_id": load_id},
            body.idempotency_key,
            request.state.request_id,
        )
        return {"load_id": load_id, "job_id": job["id"]}

    # Only a built local app is mounted; API routes always take precedence.
    dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return application


app = create_app()
