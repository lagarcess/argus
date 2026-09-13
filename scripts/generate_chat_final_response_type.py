"""Derive the frontend final-response payload from its graph-state owner."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from argus.agent_runtime.state.models import FinalResponsePayload

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "web" / "lib" / "chat-final-response-payload.ts"
TYPE_REFERENCES = {
    "#/$defs/ToolResultCard": ("ToolResultCard", "./tool-result-card"),
}


def _typescript_type(schema: dict[str, Any], imports: set[tuple[str, str]]) -> str:
    if "$ref" in schema:
        reference = TYPE_REFERENCES.get(schema["$ref"])
        if reference is None:
            raise ValueError(f"Unknown frontend type reference: {schema['$ref']}")
        imports.add(reference)
        return reference[0]
    if "anyOf" in schema:
        return " | ".join(_typescript_type(item, imports) for item in schema["anyOf"])
    if schema.get("type") == "array":
        return f"Array<{_typescript_type(schema['items'], imports)}>"
    if schema.get("type") in {"string", "null"}:
        return str(schema["type"])
    if schema.get("type") == "object" and schema.get("additionalProperties") is True:
        return "Record<string, unknown>"
    raise ValueError(f"Unsupported final-response schema: {schema!r}")


def render_final_response_type() -> str:
    schema = FinalResponsePayload.model_json_schema()
    required = set(schema.get("required", []))
    imports: set[tuple[str, str]] = set()
    fields = [
        f"  {name}{'' if name in required else '?'}: {_typescript_type(field, imports)};"
        for name, field in schema["properties"].items()
    ]
    return "\n".join(
        [
            "// Generated from FinalResponsePayload in agent_runtime/state/models.py.",
            "// Run: poetry run python scripts/generate_chat_final_response_type.py",
            "// Do not edit by hand; the backend model owns these fields.",
            "",
            *[
                f'import type {{ {name} }} from "{source}";'
                for name, source in sorted(imports)
            ],
            *([""] if imports else []),
            "export type ChatFinalResponsePayload = {",
            *fields,
            "};",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_final_response_type()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != expected:
            parser.exit(1, "Final-response TypeScript is stale; run the generator.\n")
        return
    TARGET.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    main()
