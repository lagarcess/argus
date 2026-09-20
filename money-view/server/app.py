"""Local-only HTTP composition root. Hosted identity is intentionally absent."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .calculator import CalculationError
from .interpreter import create_interpreter
from .models import PlacementInputs
from .providers import FixtureProvider
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
        service = PlacementService(Store(path))
        service.bootstrap()
        application.state.service = service
        yield

    application = FastAPI(title="Clara local demo", lifespan=lifespan)

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
        return request.app.state.service.home(semantic_interpreter.mode)

    @application.post("/api/interpret")
    async def interpret(body: InterpretBody, request: Request):
        interpretation = await semantic_interpreter.interpret(
            body.message, body.locale, body.demo_example_id
        )
        if interpretation.status == "confirmation":
            return {
                "status": "confirmation",
                "confirmation": request.app.state.service.create_confirmation(
                    interpretation.inputs
                ),
            }
        return interpretation.model_dump(
            mode="json", exclude={"inputs"}, exclude_none=True
        )

    @application.post("/api/confirmations/{confirmation_id}/compute")
    def compute(confirmation_id: str, body: ComputeBody, request: Request):
        return request.app.state.service.compute(confirmation_id, body.inputs)

    @application.post("/api/comparisons/{comparison_id}/save")
    def save(comparison_id: str, request: Request):
        return request.app.state.service.save(comparison_id)

    @application.get("/api/decisions/{decision_id}")
    def decision(decision_id: str, request: Request):
        return request.app.state.service.decision(decision_id)

    @application.get("/api/notices")
    def notices(request: Request):
        return request.app.state.service.notices()

    @application.post("/api/notices/{notice_id}/read")
    def read_notice(notice_id: str, request: Request):
        return request.app.state.service.read_notice(notice_id)

    @application.get("/api/sources/{source_id}")
    def source(source_id: str, request: Request):
        return request.app.state.service.source(source_id)

    @application.post("/api/demo/events", status_code=202)
    def demo_event(
        body: DemoEventBody, request: Request, background_tasks: BackgroundTasks
    ):
        service = request.app.state.service
        load_id = service.begin_load(body.scenario)
        background_tasks.add_task(
            service.finish_load, load_id, FixtureProvider(body.scenario)
        )
        return {"load_id": load_id}

    # Only a built local app is mounted; API routes always take precedence.
    dist = Path(__file__).resolve().parents[1] / "web" / "dist"
    if dist.is_dir():
        application.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return application


app = create_app()
