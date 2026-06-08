from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Event
from typing import Any

from loguru import logger

RuntimeEvent = dict[str, Any]
RuntimeEventFactory = Callable[[], AsyncIterator[RuntimeEvent]]
_QueueItem = tuple[str, RuntimeEvent | Exception | None]
_RUNTIME_EXECUTOR: ThreadPoolExecutor | None = None


def runtime_worker_enabled() -> bool:
    """Keep production chat streaming off the FastAPI event loop by default."""
    raw = os.getenv("ARGUS_RUNTIME_STREAM_WORKER", "auto").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    checkpointer_mode = os.getenv("ARGUS_CHECKPOINTER_MODE", "").strip().lower()
    persistence_mode = os.getenv("ARGUS_PERSISTENCE_MODE", "").strip().lower()
    return checkpointer_mode == "postgres" or persistence_mode == "supabase"


def threaded_runtime_event_source(
    runtime_event_factory: RuntimeEventFactory,
) -> AsyncIterator[RuntimeEvent]:
    return _threaded_runtime_event_source(runtime_event_factory)


async def _threaded_runtime_event_source(
    runtime_event_factory: RuntimeEventFactory,
) -> AsyncIterator[RuntimeEvent]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
    context = copy_context()
    worker_loop_ready = Event()
    worker_loop_box: dict[str, asyncio.AbstractEventLoop] = {}
    worker_task_box: dict[str, asyncio.Task[None]] = {}

    def send(kind: str, payload: RuntimeEvent | Exception | None = None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (kind, payload))

    def run_runtime() -> None:
        async def consume() -> None:
            async for event in runtime_event_factory():
                send("event", event)

        worker_loop = asyncio.new_event_loop()
        worker_loop_box["loop"] = worker_loop
        asyncio.set_event_loop(worker_loop)

        try:
            def run_in_context() -> None:
                worker_task = worker_loop.create_task(consume())
                worker_task_box["task"] = worker_task
                worker_loop_ready.set()
                worker_loop.run_until_complete(worker_task)

            context.run(run_in_context)
        except asyncio.CancelledError:
            logger.debug("Threaded chat runtime event source canceled")
        except Exception as exc:
            logger.exception("Threaded chat runtime event source failed")
            send("error", exc)
        finally:
            worker_loop_ready.set()
            worker_loop.close()
            asyncio.set_event_loop(None)
            send("done")

    future = _runtime_executor().submit(run_runtime)
    try:
        while True:
            kind, payload = await queue.get()
            if kind == "event":
                if isinstance(payload, dict):
                    yield payload
                continue
            if kind == "error":
                if isinstance(payload, Exception):
                    raise payload
                raise RuntimeError("threaded_runtime_event_source_failed")
            if kind == "done":
                return
    finally:
        if not future.done():
            if not worker_loop_ready.is_set():
                await asyncio.to_thread(worker_loop_ready.wait, 0.25)
            worker_loop = worker_loop_box.get("loop")
            worker_task = worker_task_box.get("task")
            if (
                worker_loop is not None
                and worker_task is not None
                and not worker_loop.is_closed()
            ):
                worker_loop.call_soon_threadsafe(worker_task.cancel)
        future.cancel()


def _runtime_executor() -> ThreadPoolExecutor:
    global _RUNTIME_EXECUTOR
    if _RUNTIME_EXECUTOR is not None:
        return _RUNTIME_EXECUTOR
    _RUNTIME_EXECUTOR = ThreadPoolExecutor(
        max_workers=_runtime_worker_count(),
        thread_name_prefix="argus-runtime",
    )
    return _RUNTIME_EXECUTOR


def _runtime_worker_count() -> int:
    raw = os.getenv("ARGUS_RUNTIME_STREAM_WORKERS", "2").strip()
    try:
        value = int(raw)
    except ValueError:
        return 2
    return max(1, min(value, 4))
