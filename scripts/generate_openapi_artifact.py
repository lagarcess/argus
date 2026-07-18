"""Regenerate docs/api/openapi.yaml from the canonical runtime document.

The checked artifact is a compatibility artifact, not a second authority: it is
produced from ``app.openapi()`` with the three approved non-product operations
removed and generation-noise keys (``summary``, ``operationId``) stripped.
Structural equivalence is enforced by tests/test_openapi_compatibility.py.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs" / "api" / "openapi.yaml"

_ARTIFACT_NOISE_KEYS = ("summary", "operationId")

_TOP_LEVEL_TAGS = [
    {"name": "backtest_runs", "description": "Immutable Alpha simulation results."},
]

_DESCRIPTION = (
    "Contract-first Alpha API for chat-first investing idea validation. "
    "Durable results persist as backtest_runs; result cards render as "
    "conversation_result_card artifacts."
)

_METHOD_ORDER = ("get", "post", "put", "patch", "delete", "head", "options", "trace")


def _strip_noise(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: _strip_noise(value)
            for key, value in node.items()
            if key not in _ARTIFACT_NOISE_KEYS
        }
    if isinstance(node, list):
        return [_strip_noise(item) for item in node]
    return node


def build_artifact_document() -> dict[str, Any]:
    from argus.api.main import app
    from argus.api.openapi_compat import EXCLUDED_OPERATIONS

    document = copy.deepcopy(app.openapi())
    for method, path in EXCLUDED_OPERATIONS:
        path_item = document.get("paths", {}).get(path)
        if isinstance(path_item, dict):
            path_item.pop(method, None)
            if not any(m in path_item for m in _METHOD_ORDER):
                document["paths"].pop(path, None)

    document["info"]["description"] = _DESCRIPTION
    document["tags"] = copy.deepcopy(_TOP_LEVEL_TAGS)
    document.pop("servers", None)

    ordered_paths: dict[str, Any] = {}
    for path in sorted(document.get("paths", {})):
        path_item = document["paths"][path]
        ordered_item = {
            method: path_item[method] for method in _METHOD_ORDER if method in path_item
        }
        for key in sorted(set(path_item) - set(ordered_item)):
            ordered_item[key] = path_item[key]
        ordered_paths[path] = ordered_item
    document["paths"] = ordered_paths

    components = document.get("components", {}).get("schemas", {})
    document.setdefault("components", {})["schemas"] = {
        name: components[name] for name in sorted(components)
    }
    return _strip_noise(document)


def main() -> int:
    document = build_artifact_document()
    rendered = yaml.safe_dump(
        document,
        sort_keys=False,
        allow_unicode=True,
        width=88,
    )
    header = (
        "# Checked OpenAPI compatibility artifact. Generated from the canonical\n"
        "# FastAPI app.openapi() document by scripts/generate_openapi_artifact.py.\n"
        "# Structural gate: tests/test_openapi_compatibility.py (#234).\n"
    )
    ARTIFACT.write_text(header + rendered, encoding="utf-8")
    print(f"wrote {ARTIFACT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
