"""Document preparation jobs recover a dead worker while the API keeps running.

The worker is this process's in-process fallback; the provider is scripted, so
no model is called. The sweep runs on its own cadence inside the running app.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from argus.api.document_jobs import InProcessDispatcher, document_jobs
from argus.api.documents import documents_service
from argus.domain.ingestion.documents.jobs import DISPATCH_WINDOW, MAX_ATTEMPTS

from tests.ingestion.conftest import ALICE, bearer

DOCUMENTS = "/api/v1/financial-documents"
IMPORTS = "/api/v1/financial-imports"
RECEIPT = Path(__file__).parents[1] / "document_extraction_fixtures/receipt-dop.png"


def observation(amount: str) -> dict[str, object]:
    return {
        "complete": True,
        "readable": True,
        "pages_read": [1],
        "observations": [
            {
                "page": 1,
                "row": 1,
                "evidence": "transaction",
                "status": "posted",
                "amount": amount,
                "currency": "DOP",
                "occurred_on": "2026-09-10",
                "direction": "outflow",
                "kind_hint": "expense",
            }
        ],
    }


class Provider:
    """Scripted provider: each call takes the next behavior from ``script``."""

    def __init__(self, *script: str) -> None:
        self.script, self.calls = list(script), 0
        self.release = threading.Event()

    async def __call__(self, **kwargs: object) -> object:
        import asyncio

        from argus.domain.ingestion.documents.models import ExtractionResult

        behavior = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if behavior == "fail":
            raise TimeoutError("provider timed out")
        if behavior == "hang":
            while not self.release.is_set():
                await asyncio.sleep(0.01)
            return ExtractionResult.model_validate(observation("999.00"))
        return ExtractionResult.model_validate(observation("250.50"))


class Clock:
    def __init__(self) -> None:
        self.start = datetime.now(timezone.utc)
        self.offset = timedelta()

    def __call__(self) -> datetime:
        return self.start + self.offset


@pytest.fixture
def jobs_env(monkeypatch):
    monkeypatch.setenv("ARGUS_DOCUMENT_JOBS_ENABLED", "true")
    monkeypatch.setenv("ARGUS_DOCUMENT_JOBS_SWEEP_SECONDS", "0.02")


@pytest.fixture
def jobs_client(jobs_env, client):
    return client


@pytest.fixture
def jobs_off(monkeypatch):
    monkeypatch.setenv("ARGUS_DOCUMENT_JOBS_ENABLED", "")


@pytest.fixture
def flag_off_client(jobs_off, client):
    return client


def install(monkeypatch, provider: Provider) -> Clock:
    from argus.domain.ingestion.documents import extractor
    from argus.domain.ingestion.documents.config import DocumentExtractionSettings

    monkeypatch.setenv("ARGUS_DOCUMENT_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("ARGUS_VISION_MODEL", "test/vision")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-test-key")
    service = documents_service()
    monkeypatch.setattr(extractor, "invoke_openrouter_json_schema", provider)
    monkeypatch.setattr(
        service,
        "extractor",
        extractor.DocumentExtractor(DocumentExtractionSettings(enabled=True)),
    )
    clock = Clock()
    monkeypatch.setattr(service.hub, "clock", clock)
    return clock


def wait_for(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.01)


def upload(client) -> str:
    response = client.post(
        DOCUMENTS,
        content=RECEIPT.read_bytes(),
        headers={
            **bearer(ALICE),
            "Content-Type": "image/png",
            "X-Extraction-Consent": "true",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    return response.json()["connection_id"]


def document(client, connection: str) -> dict:
    return client.get(f"{DOCUMENTS}/{connection}", headers=bearer(ALICE)).json()


def imports(client) -> list[dict]:
    return client.get(IMPORTS, headers=bearer(ALICE)).json()["items"]


def job(connection: str):
    service = documents_service()
    user = service.store.owner(connection_id=connection)
    return service.store.job(user_id=user, connection_id=connection)


def dead_worker_recovered(jobs_client, monkeypatch) -> tuple[str, Provider]:
    provider = Provider("hang", "succeed")
    clock = install(monkeypatch, provider)
    connection = upload(jobs_client)
    wait_for(lambda: provider.calls == 1)
    assert document(jobs_client, connection)["status"] == "preparing"

    clock.offset = DISPATCH_WINDOW - timedelta(seconds=1)
    time.sleep(0.2)
    assert provider.calls == 1, "a live lease is never superseded"
    assert document(jobs_client, connection)["status"] == "preparing"

    clock.offset = DISPATCH_WINDOW + timedelta(seconds=1)
    wait_for(lambda: document(jobs_client, connection)["status"] == "review_ready")
    assert provider.calls == 2, "re-dispatched exactly once"
    assert job(connection).attempt == 2
    return connection, provider


def test_dead_worker_is_redispatched_once_within_the_lease_window(
    jobs_client, monkeypatch
):
    connection, provider = dead_worker_recovered(jobs_client, monkeypatch)
    prepared = document(jobs_client, connection)
    assert [c["amount"] for c in prepared["preparation"]["candidates"]] == ["250.5"]
    assert len(imports(jobs_client)) == 1
    time.sleep(0.2)
    assert provider.calls == 2
    for task in list(document_jobs().dispatch.tasks):
        task.cancel()


def test_late_result_from_superseded_attempt_is_refused(jobs_client, monkeypatch):
    connection, provider = dead_worker_recovered(jobs_client, monkeypatch)
    before = document(jobs_client, connection)
    dispatcher = document_jobs().dispatch
    assert isinstance(dispatcher, InProcessDispatcher)
    [stale] = list(dispatcher.tasks)

    provider.release.set()
    wait_for(stale.done)

    assert stale.result() == "document_lease_lost"
    after = document(jobs_client, connection)
    assert after == before
    assert [c["amount"] for c in after["preparation"]["candidates"]] == ["250.5"]
    assert len(imports(jobs_client)) == 1
    assert job(connection).retry is False


def test_cancelled_worker_is_recovered_by_the_next_sweep(jobs_client, monkeypatch):
    provider = Provider("hang", "succeed")
    install(monkeypatch, provider)
    connection = upload(jobs_client)
    wait_for(lambda: provider.calls == 1)
    [worker] = list(document_jobs().dispatch.tasks)

    worker.cancel()

    wait_for(lambda: document(jobs_client, connection)["status"] == "review_ready")
    assert provider.calls == 2
    assert len(imports(jobs_client)) == 1


def test_retries_stop_at_the_bound_and_stay_recoverable(jobs_client, monkeypatch):
    provider = Provider("fail")
    install(monkeypatch, provider)
    connection = upload(jobs_client)

    wait_for(lambda: provider.calls == MAX_ATTEMPTS and job(connection).retry is False)
    exhausted = document(jobs_client, connection)
    assert exhausted["status"] == "needs_attention"
    assert exhausted["error_code"] == "extraction_provider_failed"
    time.sleep(0.2)
    assert provider.calls == MAX_ATTEMPTS, "no automatic attempt past the bound"
    assert imports(jobs_client) == []

    provider.script = ["succeed"]
    retried = jobs_client.post(
        f"{DOCUMENTS}/{connection}/resume",
        headers={**bearer(ALICE), "X-Extraction-Consent": "true"},
    )
    assert retried.status_code == 200, retried.text
    wait_for(lambda: document(jobs_client, connection)["status"] == "review_ready")
    assert provider.calls == MAX_ATTEMPTS + 1
    assert job(connection).attempt == 1
    assert len(imports(jobs_client)) == 1


def test_dead_attempts_exhaust_to_interrupted_needs_attention(jobs_client, monkeypatch):
    provider = Provider("hang")
    clock = install(monkeypatch, provider)
    connection = upload(jobs_client)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        wait_for(lambda attempt=attempt: provider.calls == attempt)
        clock.offset += DISPATCH_WINDOW + timedelta(seconds=1)
    wait_for(lambda: document(jobs_client, connection)["status"] == "needs_attention")
    assert document(jobs_client, connection)["error_code"] == (
        "document_preparation_interrupted"
    )
    assert provider.calls == MAX_ATTEMPTS
    provider.release.set()


def test_flag_off_prepares_through_background_tasks_only(flag_off_client, monkeypatch):
    provider = Provider("succeed")
    install(monkeypatch, provider)
    service = documents_service()
    calls = []
    original = service.background_prepare

    async def spy(**kwargs):
        calls.append(kwargs)
        await original(**kwargs)

    monkeypatch.setattr(service, "background_prepare", spy)
    assert document_jobs() is None
    assert service.jobs_recover_interruptions is False

    connection = upload(flag_off_client)

    user = service.store.owner(connection_id=connection)
    assert calls == [{"user_id": user, "connection_id": connection}]
    assert document(flag_off_client, connection)["status"] == "review_ready"
    assert service.store.job(user_id=user, connection_id=connection) is None
    assert provider.calls == 1
