from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import httpx
import pytest
from server.fixtures import get_examples
from server.interpreter import (
    FixtureInterpreter,
    OpenAICompatibleInterpreter,
    configured_interpreter,
)


def _example(example_id: str) -> dict[str, object]:
    return next(example for example in get_examples() if example["id"] == example_id)


def _completion(output: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps(output)}}]},
    )


def _model_interpreter(
    handler: httpx.MockTransport,
) -> OpenAICompatibleInterpreter:
    return OpenAICompatibleInterpreter(
        api_key="test-key",
        base_url="https://model.test/v1",
        model="test-model",
        transport=handler,
        timeout_seconds=0.25,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("locale", ["es-419", "en"])
async def test_fixture_replays_only_the_recorded_bilingual_example(
    locale: str,
) -> None:
    example = _example("do-180-day-placement")
    messages = example["messages"]
    assert isinstance(messages, dict)
    message = messages[locale]
    assert isinstance(message, str)

    result = await FixtureInterpreter().interpret(
        f"  {message}\n",
        locale,
        demo_example_id="do-180-day-placement",
    )

    assert result.status == "confirmation"
    assert result.code is None
    assert result.missing_fields == []
    assert result.inputs is not None
    assert result.inputs.amount == Decimal("250000")
    assert result.inputs.currency == "DOP"
    assert result.inputs.horizon_days == 180
    assert result.inputs.country == "DO"
    assert result.inputs.current_annual_rate_pct == Decimal("5.25")


@pytest.mark.asyncio
async def test_edited_demo_message_cannot_reuse_fixture_inputs() -> None:
    example = _example("do-180-day-placement")
    messages = example["messages"]
    assert isinstance(messages, dict)
    message = messages["es-419"]
    assert isinstance(message, str)

    result = await FixtureInterpreter().interpret(
        f"{message} pero por 90 dias",
        "es-419",
        demo_example_id="do-180-day-placement",
    )

    assert result.model_dump(mode="json") == {
        "status": "model_unavailable",
        "inputs": None,
        "code": "demo_text_mismatch",
        "missing_fields": [],
    }


@pytest.mark.asyncio
async def test_arbitrary_text_without_example_id_is_not_guessed() -> None:
    result = await FixtureInterpreter().interpret(
        "Tengo 500000 DOP por 90 dias en Republica Dominicana",
        "es-419",
    )

    assert result.model_dump(mode="json") == {
        "status": "model_unavailable",
        "inputs": None,
        "code": "model_unavailable",
        "missing_fields": [],
    }


@pytest.mark.asyncio
async def test_model_schema_rejection_returns_machine_metadata() -> None:
    transport = httpx.MockTransport(
        lambda request: _completion(
            {
                "status": "confirmation",
                "inputs": None,
                "code": None,
                "missing_fields": [],
            }
        )
    )

    result = await _model_interpreter(transport).interpret(
        "Place my savings",
        "en",
    )

    assert result.status == "model_unavailable"
    assert result.code == "invalid_model_response"
    assert result.inputs is None


@pytest.mark.asyncio
async def test_model_reports_exact_typed_missing_inputs() -> None:
    transport = httpx.MockTransport(
        lambda request: _completion(
            {
                "status": "needs_input",
                "inputs": None,
                "code": None,
                "missing_fields": ["currency", "country"],
            }
        )
    )

    result = await _model_interpreter(transport).interpret(
        "I have 1000 for 30 days",
        "en",
    )

    assert result.model_dump(mode="json") == {
        "status": "needs_input",
        "inputs": None,
        "code": None,
        "missing_fields": ["currency", "country"],
    }


@pytest.mark.asyncio
async def test_missing_current_rate_remains_a_confirmable_null_baseline() -> None:
    transport = httpx.MockTransport(
        lambda request: _completion(
            {
                "status": "confirmation",
                "inputs": {
                    "amount": "1000",
                    "currency": "USD",
                    "horizon_days": 30,
                    "country": "US",
                    "current_annual_rate_pct": None,
                },
                "code": None,
                "missing_fields": [],
            }
        )
    )

    result = await _model_interpreter(transport).interpret(
        "Compare my 1000 USD for 30 days in the US",
        "en",
    )

    assert result.status == "confirmation"
    assert result.inputs is not None
    assert result.inputs.current_annual_rate_pct is None
    assert result.missing_fields == []


@pytest.mark.asyncio
async def test_model_owns_the_non_deposit_unsupported_code() -> None:
    transport = httpx.MockTransport(
        lambda request: _completion(
            {
                "status": "unsupported",
                "inputs": None,
                "code": "stock_purchase_request",
                "missing_fields": [],
            }
        )
    )

    result = await _model_interpreter(transport).interpret(
        "Buy the best technology stock",
        "en",
    )

    assert result.model_dump(mode="json") == {
        "status": "unsupported",
        "inputs": None,
        "code": "stock_purchase_request",
        "missing_fields": [],
    }


@pytest.mark.asyncio
async def test_model_output_cannot_add_rate_quotes_or_institutions() -> None:
    transport = httpx.MockTransport(
        lambda request: _completion(
            {
                "status": "confirmation",
                "inputs": {
                    "amount": "1000",
                    "currency": "USD",
                    "horizon_days": 30,
                    "country": "US",
                    "current_annual_rate_pct": None,
                },
                "code": None,
                "missing_fields": [],
                "institution": "Example Bank",
                "quoted_rate_pct": "9.5",
            }
        )
    )

    result = await _model_interpreter(transport).interpret(
        "Compare my 1000 USD for 30 days in the US",
        "en",
    )

    assert result.status == "model_unavailable"
    assert result.code == "invalid_model_response"
    assert result.inputs is None


@pytest.mark.asyncio
async def test_timeout_is_bounded_and_never_retried() -> None:
    attempts = 0

    def timeout(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    result = await _model_interpreter(httpx.MockTransport(timeout)).interpret(
        "Compare my deposit", "en"
    )

    assert attempts == 1
    assert result.status == "model_unavailable"
    assert result.code == "model_timeout"


@pytest.mark.asyncio
async def test_missing_clara_config_ignores_parent_model_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "CLARA_LLM_API_KEY",
        "CLARA_LLM_BASE_URL",
        "CLARA_LLM_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("ARGUS_LLM_API_KEY", "must-not-be-used")

    interpreter = configured_interpreter()
    result = await interpreter.interpret(
        "Compare 1000 USD for 30 days in the US",
        "en",
    )

    assert interpreter.mode == "fixture"
    assert result.model_dump(mode="json") == {
        "status": "model_unavailable",
        "inputs": None,
        "code": "model_unavailable",
        "missing_fields": [],
    }
