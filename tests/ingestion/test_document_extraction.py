from datetime import datetime, timezone

import pytest
from argus.domain.ingestion.documents.extractor import candidates_from_result
from argus.domain.ingestion.documents.models import (
    DocumentExtractionError,
    ExtractionResult,
)


def result(**changes):
    data = dict(
        complete=True,
        readable=True,
        pages_read=[1],
        observations=[
            dict(
                page=1,
                row=1,
                evidence="transaction",
                amount="120.50",
                currency="DOP",
                direction="outflow",
            ),
            dict(
                page=1,
                row=2,
                evidence="balance",
                amount="900.00",
                currency="USD",
                balance_scope="current",
            ),
        ],
    )
    return ExtractionResult.model_validate(data | changes)


def test_maps_balances_and_transactions_without_model_owned_identity():
    items = candidates_from_result(
        result(), "a" * 64, "owned-connection", datetime.now(timezone.utc), 1
    )
    assert items[0].source.connection_id == "owned-connection"
    assert items[0].source.external_id == "a" * 64 + ":p1:r1"
    assert items[0].direction == "outflow"
    assert items[1].evidence == "balance"
    assert items[1].direction == "unknown"
    assert "occurred_on" in items[0].uncertain


@pytest.mark.parametrize(
    "changes",
    [
        dict(complete=False),
        dict(readable=False),
        dict(pages_read=[1, 2]),
        dict(observations=[]),
    ],
)
def test_incomplete_extraction_never_yields_partial_candidates(changes):
    with pytest.raises(DocumentExtractionError):
        candidates_from_result(
            result(**changes), "a" * 64, "owner", datetime.now(timezone.utc), 1
        )


def test_model_cannot_choose_connection_or_owner():
    from pydantic import ValidationError

    body = result().model_dump(mode="json")
    body["observations"][0]["source"] = {"connection_id": "someone-else"}
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(body)


def test_provider_schema_avoids_unique_items_and_candidates_own_deduplication():
    import json

    # DeepInfra rejects this grammar keyword before generating any output.
    assert '"uniqueItems"' not in json.dumps(ExtractionResult.model_json_schema())
    body = result().model_dump(mode="json")
    body["observations"][0]["uncertain"] = ["amount", "amount"]
    items = candidates_from_result(
        ExtractionResult.model_validate(body),
        "a" * 64,
        "owner",
        datetime.now(timezone.utc),
        1,
    )
    assert isinstance(items[0].uncertain, frozenset)
    assert list(items[0].uncertain).count("amount") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "finish,valid", [("stop", True), ("length", True), ("stop", False)]
)
@pytest.mark.parametrize("model", ["test/vision", "openai/gpt-6-luna"])
async def test_single_private_provider_attempt_preserves_usage(
    monkeypatch, respx_mock, finish, valid, model
):
    import io
    import json

    import httpx
    from argus.domain.ingestion.documents.config import DocumentExtractionSettings
    from argus.domain.ingestion.documents.extractor import DocumentExtractor
    from PIL import Image

    monkeypatch.setenv("ARGUS_VISION_MODEL", model)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ARGUS_PROD_OPENROUTER_API_KEY", "registered-test-key")
    monkeypatch.setenv("ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY", "guest-test-key")
    raw = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(raw, format="PNG")
    route = respx_mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": finish,
                        "message": {
                            "content": result().model_dump_json() if valid else "{invalid"
                        },
                    }
                ],
                "usage": {"cost": 0.002, "prompt_tokens": 31, "completion_tokens": 25},
            },
        )
    )
    extractor = DocumentExtractor(DocumentExtractionSettings(enabled=True))
    if finish == "stop" and valid:
        batch = await extractor.extract(
            raw.getvalue(),
            "private-name.png",
            "image/png",
            "owned",
            datetime.now(timezone.utc),
        )
        metadata = batch.metadata
        assert batch.candidates[0].source.connection_id == "owned"
    else:
        with pytest.raises(DocumentExtractionError) as error:
            await extractor.extract(
                raw.getvalue(),
                "private-name.png",
                "image/png",
                "owned",
                datetime.now(timezone.utc),
            )
        assert str(error.value) == "extraction_provider_failed"
        metadata = error.value.metadata
    assert route.call_count == 1
    request = route.calls[0].request
    payload = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer registered-test-key"
    assert payload["provider"] == {
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
        "allow_fallbacks": False,
    }
    if model.startswith("openai/"):
        assert "max_completion_tokens" in payload
        assert "max_tokens" not in payload and "temperature" not in payload
    else:
        assert "max_tokens" in payload
    assert "reasoning" not in payload
    assert payload["messages"][1]["content"][2]["type"] == "image_url"
    assert metadata["route_receipts"][0]["usage_cost_usd"] == 0.002
    assert "private-name" not in json.dumps(metadata)


@pytest.mark.asyncio
async def test_missing_vision_config_does_not_call_provider(monkeypatch, respx_mock):
    from argus.domain.ingestion.documents.config import DocumentExtractionSettings
    from argus.domain.ingestion.documents.extractor import DocumentExtractor

    monkeypatch.delenv("ARGUS_VISION_MODEL", raising=False)
    with pytest.raises(DocumentExtractionError, match="missing_vision_model"):
        await DocumentExtractor(DocumentExtractionSettings(enabled=True)).extract(
            b"content", "source.png", "image/png", "owned", datetime.now(timezone.utc)
        )
    assert not respx_mock.calls


@pytest.mark.parametrize("amount", ["-12.00", "1e999999999", "NaN", "1,200.00"])
def test_non_decimal_amount_cannot_reach_canonical_conversion(amount):
    from pydantic import ValidationError

    body = result().model_dump(mode="json")
    body["observations"][0]["amount"] = amount
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(body)


def document_payload(model="openai/gpt-6-luna", task="document_extraction"):
    from argus.llm.openrouter import _json_schema_payload, openrouter_profile_for_task

    return _json_schema_payload(
        model=model,
        messages=[{"role": "user", "content": "extract"}],
        schema_model=ExtractionResult,
        schema_name="document",
        profile=openrouter_profile_for_task(task),
    )


def test_openai_document_wire_schema_is_closed_required_and_preserves_nullability():
    original = ExtractionResult.model_json_schema()
    payload = document_payload()
    wire = payload["response_format"]["json_schema"]["schema"]
    unsupported = {"default", "pattern", "format", "minimum", "maximum", "maxItems"}

    def check(node):
        if isinstance(node, list):
            for child in node:
                check(child)
        elif isinstance(node, dict):
            assert not unsupported.intersection(node)
            if "properties" in node:
                assert set(node["required"]) == set(node["properties"])
                assert node["additionalProperties"] is False
            for child in node.values():
                check(child)

    check(wire)
    amount = wire["$defs"]["ExtractedObservation"]["properties"]["amount"]
    assert {branch["type"] for branch in amount["anyOf"]} == {"string", "null"}
    assert ExtractionResult.model_json_schema() == original
    assert "default" in original["$defs"]["ExtractedObservation"]["properties"]["amount"]
    assert "max_tokens" not in payload and "temperature" not in payload
    assert payload["max_completion_tokens"] > 0


@pytest.mark.parametrize(
    "model,task",
    [("test/vision", "document_extraction"), ("openai/gpt-6-luna", "interpretation")],
)
def test_other_model_and_task_wire_contracts_are_unchanged(model, task):
    payload = document_payload(model, task)
    assert (
        payload["response_format"]["json_schema"]["schema"]
        == ExtractionResult.model_json_schema()
    )
    assert "max_tokens" in payload and "max_completion_tokens" not in payload


@pytest.mark.parametrize(
    "field,value", [("amount", "-1"), ("occurred_on", "not-a-date"), ("page", 9)]
)
def test_wire_projection_does_not_weaken_local_field_validation(field, value):
    from pydantic import ValidationError

    document_payload()
    body = result().model_dump(mode="json")
    body["observations"][0][field] = value
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(body)


def test_wire_projection_does_not_weaken_local_array_validation():
    from pydantic import ValidationError

    document_payload()
    body = result().model_dump(mode="json")
    body["observations"] = [body["observations"][0]] * 301
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(body)
