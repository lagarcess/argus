"""#234 — structural generated-vs-checked OpenAPI compatibility gate."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from argus.api import openapi_compat
from argus.api.main import app

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs" / "api" / "openapi.yaml"


@pytest.fixture(scope="module")
def generated() -> dict:
    return app.openapi()


@pytest.fixture(scope="module")
def checked() -> dict:
    return yaml.safe_load(ARTIFACT.read_text(encoding="utf-8"))


def test_generated_and_checked_artifacts_are_structurally_compatible(
    generated: dict, checked: dict
) -> None:
    failures = openapi_compat.structural_failures(generated, checked)
    assert failures == [], "\n".join(failures)


def test_search_declares_bounded_visible_conversation_recall(
    generated: dict,
) -> None:
    operation = generated["paths"]["/api/v1/search"]["get"]
    parameters = {
        parameter["name"]: parameter for parameter in operation["parameters"]
    }

    query = parameters["q"]
    assert query["in"] == "query"
    assert query["required"] is True
    assert query["schema"]["maxLength"] == 512

    conversation_ids = parameters["conversation_id"]
    assert conversation_ids["in"] == "query"
    assert conversation_ids["required"] is False
    assert conversation_ids["schema"] == {
        "anyOf": [
            {
                "items": {"type": "string", "format": "uuid"},
                "type": "array",
                "minItems": 1,
                "maxItems": 50,
            },
            {"type": "null"},
        ],
        "title": "Conversation Id",
    }
    search_item = generated["components"]["schemas"]["SearchItem"]
    assert search_item["properties"]["archived"] == {
        "type": "boolean",
        "title": "Archived",
    }
    assert "archived" in search_item["required"]
    unavailable = operation["responses"]["503"]
    assert "search temporarily unavailable" in unavailable["description"].lower()
    assert unavailable["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Error"
    }


def test_prefix_appears_exactly_once_per_public_operation(
    generated: dict, checked: dict
) -> None:
    for document in (generated, checked):
        for method, path in openapi_compat.public_operations(document):
            assert path.startswith("/api/v1/"), (method, path)
            assert path.count("/api/v1") == 1, (method, path)
    assert checked.get("servers") in (None, [])


def test_exclusions_are_exactly_the_three_named_operations(checked: dict) -> None:
    assert openapi_compat.EXCLUDED_OPERATIONS == frozenset(
        {
            ("get", "/health"),
            ("get", "/internal/readiness"),
            ("post", "/api/v1/dev/reset"),
        }
    )
    for method, path in openapi_compat.EXCLUDED_OPERATIONS:
        assert checked.get("paths", {}).get(path, {}).get(method) is None, (
            method,
            path,
        )


def test_unapproved_exclusion_of_a_public_route_fails_as_missing(
    generated: dict, checked: dict
) -> None:
    """A checked artifact may only omit the three named operations.

    Hiding any other public route by deleting it from the checked file (an
    unapproved exclusion, not a #229-approved one) must surface as a missing
    operation, exactly like any other undeclared drift.
    """

    broken = copy.deepcopy(checked)
    target_path = "/api/v1/discovery/indicators"
    assert "get" in broken["paths"][target_path]
    del broken["paths"][target_path]["get"]
    if not broken["paths"][target_path]:
        del broken["paths"][target_path]

    failures = openapi_compat.structural_failures(generated, broken)
    assert (
        f"missing operation in checked artifact: GET {target_path}" in failures
    ), failures


def test_missing_public_route_fails_with_named_operation(
    generated: dict, checked: dict
) -> None:
    broken = copy.deepcopy(checked)
    del broken["paths"]["/api/v1/discovery/assets"]

    failures = openapi_compat.structural_failures(generated, broken)
    assert (
        "missing operation in checked artifact: GET /api/v1/discovery/assets" in failures
    )


def test_extra_unallowlisted_route_fails_with_named_operation(
    generated: dict, checked: dict
) -> None:
    broken = copy.deepcopy(checked)
    broken["paths"]["/api/v1/portfolio-export"] = {
        "get": {"responses": {"200": {"description": "bogus"}}}
    }

    failures = openapi_compat.structural_failures(generated, broken)
    assert (
        "unexpected operation in checked artifact: GET /api/v1/portfolio-export"
        in failures
    )


def test_method_drift_fails_with_named_operation(generated: dict, checked: dict) -> None:
    """Changing the HTTP method of a real route must fail on both sides."""

    broken = copy.deepcopy(checked)
    operation = broken["paths"]["/api/v1/discovery/assets"].pop("get")
    broken["paths"]["/api/v1/discovery/assets"]["put"] = operation

    failures = openapi_compat.structural_failures(generated, broken)
    assert (
        "missing operation in checked artifact: GET /api/v1/discovery/assets" in failures
    )
    assert (
        "unexpected operation in checked artifact: PUT /api/v1/discovery/assets"
        in failures
    )


def test_double_prefix_regression_fails_the_server_rule(
    generated: dict, checked: dict
) -> None:
    broken = copy.deepcopy(checked)
    broken["servers"] = [{"url": "/api/v1"}]

    failures = openapi_compat.structural_failures(generated, broken)
    assert any(
        "servers must be origin-relative" in failure for failure in failures
    ), failures


def test_required_parameter_drift_fails_with_named_difference(
    generated: dict, checked: dict
) -> None:
    broken = copy.deepcopy(checked)
    run_parameters = broken["paths"]["/api/v1/backtests/run"]["post"]["parameters"]
    for parameter in run_parameters:
        if parameter["name"] == "Idempotency-Key":
            parameter["required"] = False

    failures = openapi_compat.structural_failures(generated, broken)
    assert any(
        "POST /api/v1/backtests/run" in failure and "required" in failure
        for failure in failures
    ), failures


def test_required_field_drift_on_a_component_schema_fails_with_named_difference(
    generated: dict, checked: dict
) -> None:
    broken = copy.deepcopy(checked)
    schema = broken["components"]["schemas"]["AccountCapabilities"]
    assert "can_submit_feedback" in schema["required"]
    schema["required"] = [
        field for field in schema["required"] if field != "can_submit_feedback"
    ]

    failures = openapi_compat.structural_failures(generated, broken)
    assert any(
        "required" in failure and "can_submit_feedback" in failure for failure in failures
    ), failures


def test_enum_drift_fails_with_named_difference(generated: dict, checked: dict) -> None:
    schemas = checked.get("components", {}).get("schemas", {})
    enum_owner = None
    for name, schema in sorted(schemas.items()):
        for property_name, property_schema in sorted(
            schema.get("properties", {}).items()
        ):
            if isinstance(property_schema, dict) and property_schema.get("enum"):
                enum_owner = (name, property_name)
                break
        if enum_owner:
            break
    assert enum_owner is not None, "expected at least one enum in the checked artifact"

    broken = copy.deepcopy(checked)
    name, property_name = enum_owner
    broken["components"]["schemas"][name]["properties"][property_name]["enum"].append(
        "drifted_enum_value"
    )

    failures = openapi_compat.structural_failures(generated, broken)
    assert any("drifted_enum_value" in failure for failure in failures), failures


def test_response_schema_drift_fails_with_named_difference(
    generated: dict, checked: dict
) -> None:
    broken = copy.deepcopy(checked)
    operation = broken["paths"]["/api/v1/me"]["get"]
    operation["responses"]["200"]["content"]["application/json"]["schema"] = {
        "type": "string"
    }

    failures = openapi_compat.structural_failures(generated, broken)
    assert any(
        "GET /api/v1/me/responses/200" in failure for failure in failures
    ), failures


def test_streaming_normalization_is_narrow(generated: dict, checked: dict) -> None:
    projection = openapi_compat.structural_projection(checked)
    stream = projection["POST /api/v1/chat/stream"]
    assert stream["responses"]["200"] == {"text/event-stream": {}}
    # The request schema and error responses remain structural gate inputs.
    assert stream["request"], "chat stream request schema must stay compared"
    assert "409" in stream["responses"]
    assert "422" in stream["responses"]
    assert "503" in stream["responses"]


def test_chat_stream_declares_the_approved_request_boundary_failures(
    generated: dict,
) -> None:
    responses = generated["paths"]["/api/v1/chat/stream"]["post"]["responses"]
    for status in ("413", "500"):
        assert responses[status]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/Error"
        }


def test_regeneration_script_matches_checked_artifact() -> None:
    from scripts.generate_openapi_artifact import build_artifact_document

    checked_document = yaml.safe_load(ARTIFACT.read_text(encoding="utf-8"))
    failures = openapi_compat.structural_failures(
        build_artifact_document(), checked_document
    )
    assert failures == [], "\n".join(failures)
