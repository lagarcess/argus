"""Default-off durable dispatch and recovery for document preparation (#823).

``ARGUS_DOCUMENT_JOBS_ENABLED`` off leaves the routes on FastAPI background
tasks, exactly as before. On, each accepted preparation becomes a recorded
attempt: a Render Workflow task when ``ARGUS_DOCUMENT_JOBS_WORKFLOW_TASK`` is
set in durable mode (the local Render dev server under ``RENDER_USE_LOCAL_DEV``),
otherwise a task on this process's event loop. A sweep in this process
re-dispatches attempts whose worker died, every
``ARGUS_DOCUMENT_JOBS_SWEEP_SECONDS`` and once at startup.
"""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from argus.api import state as api_state
from argus.api.financial_accounts import TRUE_VALUES
from argus.domain.ingestion.documents.jobs import (
    Dispatch,
    PreparationJobs,
    run_attempt,
)
from argus.domain.ingestion.documents.service import DocumentsService

FLAG = "ARGUS_DOCUMENT_JOBS_ENABLED"
TASK_ENV = "ARGUS_DOCUMENT_JOBS_WORKFLOW_TASK"
SWEEP_ENV = "ARGUS_DOCUMENT_JOBS_SWEEP_SECONDS"
DEFAULT_SWEEP_SECONDS = 30.0

_jobs: PreparationJobs | None = None
_sweeper: asyncio.Task[None] | None = None


def document_jobs_enabled() -> bool:
    return os.getenv(FLAG, "").strip().lower() in TRUE_VALUES


def document_jobs() -> PreparationJobs | None:
    return _jobs


def _sweep_seconds() -> float:
    try:
        return max(0.01, float(os.getenv(SWEEP_ENV, "") or DEFAULT_SWEEP_SECONDS))
    except ValueError:
        return DEFAULT_SWEEP_SECONDS


class InProcessDispatcher:
    """Local fallback: each attempt runs as a task on the API's event loop."""

    def __init__(
        self, loop: asyncio.AbstractEventLoop, service: DocumentsService
    ) -> None:
        self.loop, self.service = loop, service
        self.tasks: set[asyncio.Task[str]] = set()

    def __call__(self, connection_id: str, attempt_id: str) -> None:
        self.loop.call_soon_threadsafe(self._spawn, connection_id, attempt_id)

    def _spawn(self, connection_id: str, attempt_id: str) -> None:
        task = self.loop.create_task(run_attempt(self.service, connection_id, attempt_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


def render_dispatcher(task_id: str) -> Dispatch:
    from argus.api.chat.backtest_jobs import RenderWorkflowDispatcher

    dispatcher = RenderWorkflowDispatcher(task_id=task_id)

    def dispatch(connection_id: str, attempt_id: str) -> None:
        run = dispatcher.dispatch(job_id=connection_id, nonce=attempt_id)
        logger.info(
            "Document preparation dispatched",
            connection_id=connection_id,
            task_run_id=run.get("id"),
        )

    return dispatch


async def sweep_forever(jobs: PreparationJobs, interval: float) -> None:
    while True:
        try:
            await asyncio.to_thread(jobs.sweep)
        except Exception as error:
            logger.warning(
                "Document preparation sweep failed",
                failure_mode=type(error).__name__,
            )
        await asyncio.sleep(interval)


def start_document_jobs(service: DocumentsService) -> None:
    global _jobs, _sweeper
    stop_document_jobs()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("Document jobs need a running event loop; jobs stay off")
        return
    task_id = os.getenv(TASK_ENV, "").strip()
    dispatch: Dispatch = (
        render_dispatcher(task_id)
        if task_id and api_state.PERSISTENCE_MODE == "supabase"
        else InProcessDispatcher(loop, service)
    )
    _jobs = PreparationJobs(service, dispatch)
    _sweeper = loop.create_task(sweep_forever(_jobs, _sweep_seconds()))


def stop_document_jobs() -> None:
    global _jobs, _sweeper
    if _sweeper is not None:
        _sweeper.cancel()
    if _jobs is not None and isinstance(_jobs.dispatch, InProcessDispatcher):
        for task in list(_jobs.dispatch.tasks):
            task.cancel()
    _jobs, _sweeper = None, None
