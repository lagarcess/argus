"""Structural OpenAPI compatibility projection and gate primitives (#234).

FastAPI ``app.openapi()`` is the canonical machine-readable API source;
``docs/api/openapi.yaml`` is the checked compatibility artifact, never a second
authority. This module owns three things:

1. ``customize_openapi_document`` — corrects generated declarations so they
   describe real runtime behavior (required Idempotency-Key, RFC 9457 error
   bodies, the SSE success media type). Declaration-only; no behavior changes.
2. ``structural_projection`` — reduces either document to comparable structure:
   documentation-only fields removed, component references resolved, list
   ordering canonicalized, and the single approved streaming normalization
   applied.
3. ``structural_failures`` — the #234 gate: named, exact differences between
   the generated and checked artifacts, plus the prefix/server/exclusion rules
   from the approved #229 OpenAPI-authority contract.

The comparison is structural, never textual, and the only excluded operations
are the three individually named non-product operations from the contract.
"""

from __future__ import annotations

import copy
import json
from typing import Any

API_PREFIX = "/api/v1"

# The approved #229 exclusion list. No public /api/v1 product route may hide
# behind a prefix or wildcard allowlist.
EXCLUDED_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("get", "/health"),
        ("get", "/internal/readiness"),
        ("post", "/api/v1/dev/reset"),
    }
)

STREAMING_OPERATION = ("post", "/api/v1/chat/stream")
SSE_MEDIA_TYPE = "text/event-stream"

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")

# Annotation-only keys; the #229 contract keeps them out of the structural
# comparison. ``title`` is JSON Schema annotation noise FastAPI stamps on every
# generated schema.
_DOC_ONLY_KEYS = frozenset(
    {
        "description",
        "summary",
        "operationId",
        "tags",
        "examples",
        "example",
        "externalDocs",
        "title",
    }
)

ERROR_COMPONENT = {
    "type": "object",
    "description": "RFC 9457 Problem Details with code and request_id.",
    "required": ["type", "title", "status", "detail", "code", "request_id"],
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "code": {"type": "string"},
        "request_id": {"type": "string"},
        "context": {"type": "object"},
    },
}

_ERROR_REF = {"$ref": "#/components/schemas/Error"}


def _error_response(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {"application/json": {"schema": copy.deepcopy(_ERROR_REF)}},
    }


def customize_openapi_document(document: dict[str, Any]) -> dict[str, Any]:
    """Correct generated declarations to match real runtime behavior."""

    spec = copy.deepcopy(document)
    components = spec.setdefault("components", {}).setdefault("schemas", {})
    components["Error"] = copy.deepcopy(ERROR_COMPONENT)

    _rewrite_validation_errors(spec)

    run_op = spec.get("paths", {}).get(f"{API_PREFIX}/backtests/run", {}).get("post")
    if run_op is not None:
        for parameter in run_op.get("parameters", []):
            if parameter.get("name") == "Idempotency-Key":
                parameter["required"] = True
                parameter["schema"] = {"type": "string"}
        responses = run_op.setdefault("responses", {})
        responses.setdefault(
            "400", _error_response("Missing or blank Idempotency-Key header.")
        )
        responses.setdefault(
            "404", _error_response("Referenced conversation or strategy not found.")
        )
        responses.setdefault("429", _error_response("Backtest quota exceeded."))
        responses.setdefault(
            "503", _error_response("Backtest finished but finalization failed safely.")
        )

    stream_method, stream_path = STREAMING_OPERATION
    stream_op = spec.get("paths", {}).get(stream_path, {}).get(stream_method)
    if stream_op is not None:
        responses = stream_op.setdefault("responses", {})
        success = responses.setdefault("200", {})
        success["description"] = (
            "Canonical data-only SSE stream: stage_start, token, stage_outcome, "
            "final, then [DONE]."
        )
        success["content"] = {SSE_MEDIA_TYPE: {}}
        responses.setdefault(
            "409", _error_response("Stale or superseded chat action rejected.")
        )
        responses.setdefault("429", _error_response("Chat message quota exceeded."))

    return spec


def _rewrite_validation_errors(spec: dict[str, Any]) -> None:
    """The runtime returns RFC 9457 bodies for 422s, not HTTPValidationError."""

    for operations in spec.get("paths", {}).values():
        for method, operation in operations.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            validation = operation.get("responses", {}).get("422")
            if not isinstance(validation, dict):
                continue
            content = validation.get("content", {}).get("application/json")
            if isinstance(content, dict):
                content["schema"] = copy.deepcopy(_ERROR_REF)
    schemas = spec.get("components", {}).get("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)


def public_operations(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    operations: dict[tuple[str, str], dict[str, Any]] = {}
    for path, path_item in sorted(document.get("paths", {}).items()):
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue
            if (method, path) in EXCLUDED_OPERATIONS:
                continue
            operations[(method, path)] = operation
    return operations


def _resolve(node: Any, components: dict[str, Any], stack: tuple[str, ...]) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            name = ref.rsplit("/", 1)[-1]
            if name in stack:
                return {"$circular": name}
            target = components.get(name)
            if target is None:
                return {"$unresolved": name}
            return _resolve(target, components, stack + (name,))
        resolved: dict[str, Any] = {}
        for key, value in node.items():
            if key in _DOC_ONLY_KEYS:
                continue
            resolved[key] = _resolve(value, components, stack)
        for list_key in ("required", "enum"):
            if list_key in resolved and isinstance(resolved[list_key], list):
                resolved[list_key] = sorted(
                    resolved[list_key], key=lambda item: json.dumps(item, sort_keys=True)
                )
        for combinator in ("anyOf", "oneOf", "allOf"):
            if combinator in resolved and isinstance(resolved[combinator], list):
                resolved[combinator] = sorted(
                    resolved[combinator],
                    key=lambda item: json.dumps(item, sort_keys=True),
                )
        return resolved
    if isinstance(node, list):
        return [_resolve(item, components, stack) for item in node]
    return node


def structural_projection(document: dict[str, Any]) -> dict[str, Any]:
    """Reduce a document to the approved comparable structure."""

    components = document.get("components", {}).get("schemas", {})
    projection: dict[str, Any] = {}
    for (method, path), operation in public_operations(document).items():
        parameters = []
        for parameter in operation.get("parameters", []):
            parameters.append(
                {
                    "name": parameter.get("name"),
                    "in": parameter.get("in"),
                    "required": bool(parameter.get("required", False)),
                    "schema": _resolve(parameter.get("schema", {}), components, ()),
                }
            )
        parameters.sort(key=lambda item: (str(item["in"]), str(item["name"])))

        request_body: dict[str, Any] = {}
        body = operation.get("requestBody")
        if isinstance(body, dict):
            for media, media_item in sorted(body.get("content", {}).items()):
                request_body[media] = _resolve(
                    media_item.get("schema", {}), components, ()
                )

        responses: dict[str, Any] = {}
        for status, response in sorted(operation.get("responses", {}).items()):
            media_map: dict[str, Any] = {}
            if isinstance(response, dict):
                for media, media_item in sorted(response.get("content", {}).items()):
                    media_map[media] = _resolve(
                        media_item.get("schema", {}), components, ()
                    )
            responses[str(status)] = media_map

        if (method, path) == STREAMING_OPERATION and "200" in responses:
            # Approved manual streaming difference: the success body is SSE and
            # only that success body schema is excluded from comparison.
            responses["200"] = {SSE_MEDIA_TYPE: {}}

        projection[f"{method.upper()} {path}"] = {
            "parameters": parameters,
            "request": request_body,
            "responses": responses,
        }
    return projection


def _diff(pointer: str, generated: Any, checked: Any, failures: list[str]) -> None:
    if isinstance(generated, dict) and isinstance(checked, dict):
        for key in sorted(set(generated) | set(checked)):
            child = f"{pointer}/{key}"
            if key not in generated:
                failures.append(f"{child}: present only in checked artifact")
            elif key not in checked:
                failures.append(f"{child}: present only in generated document")
            else:
                _diff(child, generated[key], checked[key], failures)
        return
    if isinstance(generated, list) and isinstance(checked, list):
        if generated != checked:
            failures.append(
                f"{pointer}: generated={json.dumps(generated, sort_keys=True)} "
                f"checked={json.dumps(checked, sort_keys=True)}"
            )
        return
    if generated != checked:
        failures.append(
            f"{pointer}: generated={json.dumps(generated, sort_keys=True)} "
            f"checked={json.dumps(checked, sort_keys=True)}"
        )


def _server_rule_failures(document: dict[str, Any], label: str) -> list[str]:
    failures: list[str] = []
    servers = document.get("servers")
    if servers not in (None, []):
        urls = [server.get("url") for server in servers if isinstance(server, dict)]
        if urls not in (["/"], [""]):
            failures.append(
                f"{label} servers must be origin-relative; found {urls!r} "
                f"(the {API_PREFIX} prefix must appear exactly once, in paths)"
            )
    return failures


def _prefix_rule_failures(document: dict[str, Any], label: str) -> list[str]:
    failures: list[str] = []
    for method, path in public_operations(document):
        if not path.startswith(f"{API_PREFIX}/"):
            failures.append(
                f"{label} operation {method.upper()} {path} is outside {API_PREFIX} "
                "and is not an approved named exclusion"
            )
        elif path.count(API_PREFIX) != 1:
            failures.append(
                f"{label} operation {method.upper()} {path} repeats the "
                f"{API_PREFIX} prefix"
            )
    return failures


def structural_failures(generated: dict[str, Any], checked: dict[str, Any]) -> list[str]:
    """The #234 gate. Empty list means the artifacts are compatible."""

    failures: list[str] = []
    failures.extend(_server_rule_failures(generated, "generated"))
    failures.extend(_server_rule_failures(checked, "checked"))
    failures.extend(_prefix_rule_failures(generated, "generated"))
    failures.extend(_prefix_rule_failures(checked, "checked"))

    for method, path in sorted(EXCLUDED_OPERATIONS):
        if checked.get("paths", {}).get(path, {}).get(method) is not None:
            failures.append(
                f"excluded non-product operation {method.upper()} {path} must not "
                "appear in the checked artifact"
            )

    generated_projection = structural_projection(generated)
    checked_projection = structural_projection(checked)

    for operation in sorted(set(generated_projection) | set(checked_projection)):
        if operation not in checked_projection:
            failures.append(f"missing operation in checked artifact: {operation}")
        elif operation not in generated_projection:
            failures.append(f"unexpected operation in checked artifact: {operation}")
        else:
            _diff(
                operation,
                generated_projection[operation],
                checked_projection[operation],
                failures,
            )
    return sorted(failures)
