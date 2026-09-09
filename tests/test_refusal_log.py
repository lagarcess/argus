"""Private observations preserve supplied facts without classifying answers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from argus.observability.refusal_log import (
    RefusalObservation,
    persist_refusal_observation,
)
from faker import Faker
from loguru import logger
from pydantic import ValidationError

from supabase import ClientOptions, create_client

fake = Faker()


@pytest.fixture
def identity() -> dict[str, str]:
    return {key: fake.uuid4() for key in ("user_id", "conversation_id", "request_id")}


@pytest.fixture
def recorded_store() -> tuple[SimpleNamespace, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []

    def transport(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            row = json.loads(request.content)
            if row.get("response_message_id") and any(
                item.get("response_message_id") == row["response_message_id"]
                for item in rows
            ):
                return httpx.Response(
                    409,
                    json={
                        "code": "23505",
                        "message": "duplicate",
                        "details": None,
                        "hint": None,
                    },
                )
            rows.append(row)
            return httpx.Response(201, json=[row])
        response_id = request.url.params["response_message_id"].removeprefix("eq.")
        return httpx.Response(
            200,
            json=[
                {key: row[key] for key in request.url.params["select"].split(",")}
                for row in rows
                if row.get("response_message_id") == response_id
            ],
        )

    client = create_client(
        "https://argus.local",
        "local-test-key",
        options=ClientOptions(
            httpx_client=httpx.Client(transport=httpx.MockTransport(transport))
        ),
    )
    return SimpleNamespace(client=client), rows


def test_linked_observation_stores_only_exact_message_pointers(
    identity: dict[str, str], recorded_store: tuple[SimpleNamespace, list[dict[str, Any]]]
) -> None:
    gateway, rows = recorded_store
    observation = RefusalObservation(
        **identity, request_message_id=fake.uuid4(), response_message_id=fake.uuid4()
    )

    assert persist_refusal_observation(gateway=gateway, observation=observation)
    assert len(rows) == 1
    assert rows[0]["request_message_id"] == observation.request_message_id
    assert rows[0]["response_message_id"] == observation.response_message_id
    assert all(rows[0].get(key) is None for key in ("asked", "action", "outcome"))


def test_rejections_retain_new_shapes_and_count_independently_with_same_request_id(
    identity: dict[str, str], recorded_store: tuple[SimpleNamespace, list[dict[str, Any]]]
) -> None:
    gateway, rows = recorded_store
    shape = {fake.word(): {fake.word(): [fake.pyint(), None, False]}}
    fields = {
        **identity,
        "asked": fake.sentence(),
        "action": {"type": fake.word(), "payload": shape},
        "outcome": {"detail": fake.sentence(), "shape": shape},
        "status_code": 409,
    }

    for _ in range(2):
        assert persist_refusal_observation(
            gateway=gateway, observation=RefusalObservation(**fields)
        )

    assert len(rows) == 2
    assert rows[0]["id"] != rows[1]["id"]
    for row in rows:
        assert {key: row[key] for key in fields} == fields


@pytest.mark.parametrize(
    "changes",
    [
        {"response_message_id": None},
        {"asked": "copied content"},
        {"action": {}},
        {"outcome": {}},
        {"status_code": 409},
        {"category": "unsupported"},
    ],
)
def test_invalid_or_classified_linked_shapes_are_rejected(
    identity: dict[str, str], changes: dict[str, Any]
) -> None:
    fields = {
        **identity,
        "request_message_id": fake.uuid4(),
        "response_message_id": fake.uuid4(),
        **changes,
    }
    with pytest.raises(ValidationError):
        RefusalObservation(**fields)


def test_repeated_terminal_pair_does_not_inflate_frequency(
    identity: dict[str, str], recorded_store: tuple[SimpleNamespace, list[dict[str, Any]]]
) -> None:
    gateway, rows = recorded_store
    fields = {
        **identity,
        "request_message_id": fake.uuid4(),
        "response_message_id": fake.uuid4(),
    }
    for _ in range(2):
        assert persist_refusal_observation(
            gateway=gateway, observation=RefusalObservation(**fields)
        )
    assert len(rows) == 1


def test_duplicate_response_does_not_accept_a_different_request_pair(
    identity: dict[str, str], recorded_store: tuple[SimpleNamespace, list[dict[str, Any]]]
) -> None:
    gateway, rows = recorded_store
    fields = {
        **identity,
        "request_message_id": fake.uuid4(),
        "response_message_id": fake.uuid4(),
    }
    assert persist_refusal_observation(
        gateway=gateway, observation=RefusalObservation(**fields)
    )
    fields["request_message_id"] = fake.uuid4()
    assert not persist_refusal_observation(
        gateway=gateway, observation=RefusalObservation(**fields)
    )
    assert len(rows) == 1


def test_persistence_failure_is_content_free_and_best_effort(
    identity: dict[str, str],
) -> None:
    secret = fake.sentence()

    class UnavailableGateway:
        @property
        def client(self) -> Any:
            raise RuntimeError(secret)

    observation = RefusalObservation(
        **identity, asked=secret, outcome={"detail": secret}, status_code=400
    )
    records: list[str] = []
    sink = logger.add(lambda message: records.append(str(message)))
    try:
        assert not persist_refusal_observation(
            gateway=UnavailableGateway(), observation=observation
        )
    finally:
        logger.remove(sink)
    assert len(records) == 1
    assert "RuntimeError" in records[0]
    assert secret not in records[0]
    assert not any(value in records[0] for value in identity.values())


def test_memory_mode_does_not_report_a_storage_outage(identity: dict[str, str]) -> None:
    records: list[str] = []
    sink = logger.add(lambda message: records.append(str(message)))
    try:
        assert not persist_refusal_observation(
            gateway=None,
            observation=RefusalObservation(
                **identity, asked=fake.sentence(), outcome={}, status_code=400
            ),
        )
    finally:
        logger.remove(sink)
    assert records == []
