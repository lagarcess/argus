"""Structural guard for the research sidecar's single construction boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src" / "argus"
BUILDER_NAME = "build_research_sidecar"


def _function_nodes(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.AST]:
    """Return one function's nodes without borrowing nested function bodies."""
    nodes: list[ast.AST] = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        nodes.append(node)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            pending.append(child)
    return nodes


def _is_builder_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    function = node.func
    return (
        isinstance(function, ast.Name)
        and function.id == BUILDER_NAME
        or isinstance(function, ast.Attribute)
        and function.attr == BUILDER_NAME
    )


def _is_research_passthrough(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "research"
    )


def _bound_builder_names(nodes: list[ast.AST]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Assign) and _is_builder_call(node.value):
            names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
            and _is_builder_call(node.value)
        ):
            names.add(node.target.id)
    return names


def _research_values(nodes: list[ast.AST]) -> list[tuple[int, ast.AST]]:
    values: list[tuple[int, ast.AST]] = []
    for node in nodes:
        if isinstance(node, ast.Dict):
            values.extend(
                (node.lineno, value)
                for key, value in zip(node.keys, node.values, strict=True)
                if isinstance(key, ast.Constant) and key.value == "research"
            )
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if node.value is None:
                continue
            if any(
                isinstance(target, ast.Subscript)
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "research"
                for target in targets
            ):
                values.append((node.lineno, node.value))
    return values


def _producer_violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    violations: list[str] = []
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        nodes = _function_nodes(function)
        builder_names = _bound_builder_names(nodes)
        for lineno, value in _research_values(nodes):
            if _is_builder_call(value):
                continue
            if _is_research_passthrough(value):
                continue
            if isinstance(value, ast.Name) and value.id in builder_names:
                continue
            violations.append(f"{filename}:{lineno}:{function.name}")
    return violations


def test_a_research_producer_skipping_the_builder_is_rejected() -> None:
    bypass = """
def future_producer():
    sidecar = {"schema_version": "argus_research/v1"}
    return {"research": sidecar}
"""

    violations = _producer_violations(bypass, "future_producer.py")

    assert len(violations) == 1
    assert violations[0].endswith(":future_producer")


def test_every_research_sidecar_producer_uses_the_shared_builder() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        violations.extend(
            _producer_violations(
                path.read_text(encoding="utf-8"),
                str(path.relative_to(ROOT)),
            )
        )

    assert violations == [], (
        "research sidecars must come from build_research_sidecar: " f"{violations}"
    )
