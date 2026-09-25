"""Regression tests for Loguru diagnostic locals and ops token compare (#682)."""

from __future__ import annotations

import hmac
import io

import pytest
from argus.api.main import app
from argus.observability.log_sink import configure_logging
from faker import Faker
from fastapi.testclient import TestClient
from loguru import logger

fake = Faker()

_SENTINEL_SECRET = "SENTINEL_LOCAL_SECRET_VALUE_682"


def _raise_with_sentinel() -> None:
    expected_header = _SENTINEL_SECRET
    authorization = "Bearer token-\u00e9"
    hmac.compare_digest(authorization, expected_header)


def test_logger_exception_does_not_render_local_values() -> None:
    stream = io.StringIO()
    configure_logging(sink=stream)
    try:
        try:
            _raise_with_sentinel()
        except TypeError:
            logger.exception("forced exception through logging path")
    finally:
        configure_logging()

    output = stream.getvalue()
    assert "forced exception through logging path" in output
    assert _SENTINEL_SECRET not in output


def test_non_ascii_ops_authorization_is_rejected_without_exception_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[str] = []
    sink_id = logger.add(lambda message: records.append(str(message)), level="ERROR")
    monkeypatch.setenv("ARGUS_OPS_TOKEN", fake.uuid4())
    try:
        response = TestClient(app, raise_server_exceptions=False).get(
            "/internal/readiness",
            headers={"Authorization": "Bearer token-\u00e9".encode("latin-1")},
        )
    finally:
        logger.remove(sink_id)

    assert response.status_code == 404
    assert all("Unexpected API failure" not in record for record in records)
