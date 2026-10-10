"""Business API fixtures: the real auth dependency, documents on, a local receipt stub."""

from collections.abc import Iterator

import pytest
from argus.api.documents import documents_service
from fastapi.testclient import TestClient

from tests.business.receipt_stub import ReceiptStub
from tests.ingestion.conftest import (  # noqa: F401
    ALICE,
    BOB,
    client,
    gateway,
    identities,
    ingestion_env,
    surface_env,
)


@pytest.fixture
def business_env(ingestion_env, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: ANN001, F811
    monkeypatch.setenv("ARGUS_DOCUMENT_EXTRACTION_ENABLED", "true")
    monkeypatch.setenv("ARGUS_BUSINESS_PILOT_ENABLED", "true")


@pytest.fixture
def stub(business_env, client: TestClient, monkeypatch) -> ReceiptStub:  # noqa: ANN001, F811
    extractor = ReceiptStub()
    monkeypatch.setattr(documents_service(), "extractor", extractor)
    return extractor


@pytest.fixture
def biz(stub: ReceiptStub, client: TestClient) -> Iterator[TestClient]:  # noqa: F811
    yield client
