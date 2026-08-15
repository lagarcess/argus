"""Every piece of text this repo sends to an interpretation model.

Two channels reach the model: the instruction text in prompt builders, and the
schema field descriptions it fills in. Both steer interpretation for every turn,
so both are frozen together by `test_interpreter_prompt_freeze.py`.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

MEASURED_ROOTS = (
    "src/argus/agent_runtime",
    "src/argus/domain",
    "src/argus/llm",
    "src/argus/context",
    "src/argus/nlp",
)

FINGERPRINT_PATH = Path(".agent/interpreter_prompt_fingerprint.json")

_MESSAGE_CONSTRUCTORS = frozenset({"SystemMessage", "HumanMessage", "AIMessage"})
_PROMPT_FUNCTION_SUFFIXES = ("_prompt", "_instructions", "_directive")


def _callee_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _joined_constants(node: ast.AST) -> str:
    """Concatenate every string constant under a node, in source order."""

    parts = [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    return "".join(parts)


def _model_facing_strings(tree: ast.AST) -> list[tuple[str, str]]:
    """(kind, text) for every string this module hands to a model."""

    found: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.endswith(_PROMPT_FUNCTION_SUFFIXES):
                body = _joined_constants(node)
                if body:
                    found.append((f"def {node.name}", body))
            continue

        if not isinstance(node, ast.Call):
            continue

        callee = _callee_name(node)

        if callee in _MESSAGE_CONSTRUCTORS:
            text = _joined_constants(node)
            if text:
                found.append((callee, text))
            continue

        if callee == "Field":
            for keyword in node.keywords:
                if keyword.arg != "description":
                    continue
                text = _joined_constants(keyword.value)
                if text:
                    found.append(("Field.description", text))

    return found


def model_facing_surface(repository_root: Path) -> dict[str, dict[str, object]]:
    """Per-file digest of everything the interpretation model reads."""

    surface: dict[str, dict[str, object]] = {}

    for root in MEASURED_ROOTS:
        for path in sorted((repository_root / root).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue

            strings = _model_facing_strings(tree)
            if not strings:
                continue

            payload = chr(10).join(kind + chr(31) + text for kind, text in strings)
            relative = str(path.relative_to(repository_root))
            surface[relative] = {
                "entries": len(strings),
                "chars": sum(len(text) for _, text in strings),
                "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            }

    return surface


def load_fingerprint(repository_root: Path) -> dict[str, object]:
    return json.loads((repository_root / FINGERPRINT_PATH).read_text(encoding="utf-8"))


def surface_drift(
    recorded: dict[str, dict[str, object]],
    observed: dict[str, dict[str, object]],
) -> tuple[list[str], list[str], list[str]]:
    """(changed, added, removed) files, comparing digests only."""

    changed = sorted(
        name
        for name in recorded.keys() & observed.keys()
        if recorded[name]["sha256"] != observed[name]["sha256"]
    )
    return (
        changed,
        sorted(observed.keys() - recorded.keys()),
        sorted(recorded.keys() - observed.keys()),
    )
