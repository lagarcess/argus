"""Structural guard for the research sidecar's single construction boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "src" / "argus"
BUILDER_NAME = "build_research_sidecar"
MUTATING_METHODS = frozenset(
    {"__delitem__", "__setitem__", "clear", "pop", "popitem", "setdefault", "update"}
)


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


def _is_research_get_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "research"
    )


def _is_research_access(node: ast.AST) -> bool:
    return _is_research_passthrough(node) or _is_research_get_call(node)


def _contains_research_access(node: ast.AST) -> bool:
    return any(_is_research_access(child) for child in ast.walk(node))


def _research_alias_names(nodes: list[ast.AST]) -> set[str]:
    aliases: set[str] = set()
    while True:
        previous = aliases.copy()
        for node in nodes:
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets = [node.target]
                value = node.value
            else:
                continue
            if not (
                _is_research_access(value)
                or isinstance(value, ast.Name)
                and value.id in aliases
            ):
                continue
            aliases.update(
                target.id for target in targets if isinstance(target, ast.Name)
            )
        if aliases == previous:
            return aliases


def _target_mutates_research(
    target: ast.AST,
    aliases: set[str],
    *,
    include_bare_alias: bool,
) -> bool:
    if isinstance(target, ast.Name):
        return include_bare_alias and target.id in aliases
    return _contains_research_access(target) or any(
        isinstance(child, ast.Name) and child.id in aliases for child in ast.walk(target)
    )


def _research_mutation_lines(nodes: list[ast.AST]) -> set[int]:
    aliases = _research_alias_names(nodes)
    lines: set[int] = set()
    for node in nodes:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_research_passthrough(target):
                    continue
                if _target_mutates_research(target, aliases, include_bare_alias=False):
                    lines.add(node.lineno)
        elif isinstance(node, ast.AnnAssign):
            if not _is_research_passthrough(node.target) and _target_mutates_research(
                node.target, aliases, include_bare_alias=False
            ):
                lines.add(node.lineno)
        elif isinstance(node, ast.AugAssign):
            if _target_mutates_research(node.target, aliases, include_bare_alias=True):
                lines.add(node.lineno)
        elif isinstance(node, ast.Delete):
            if any(
                _target_mutates_research(target, aliases, include_bare_alias=False)
                for target in node.targets
            ):
                lines.add(node.lineno)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in MUTATING_METHODS
            and _target_mutates_research(
                node.func.value, aliases, include_bare_alias=True
            )
        ):
            lines.add(node.lineno)
    return lines


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
    violations: set[str] = set()
    for function in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        nodes = _function_nodes(function)
        for lineno, value in _research_values(nodes):
            if _is_builder_call(value):
                continue
            if _is_research_passthrough(value):
                continue
            violations.add(f"{filename}:{lineno}:{function.name}")
        violations.update(
            f"{filename}:{lineno}:{function.name}"
            for lineno in _research_mutation_lines(nodes)
        )
    return sorted(violations)


def test_a_research_producer_skipping_the_builder_is_rejected() -> None:
    bypass = """
def future_producer():
    sidecar = {"schema_version": "argus_research/v1"}
    return {"research": sidecar}
"""

    violations = _producer_violations(bypass, "future_producer.py")

    assert len(violations) == 1
    assert violations[0].endswith(":future_producer")


@pytest.mark.parametrize(
    "bypass",
    [
        pytest.param(
            """
def future_producer():
    sidecar = build_research_sidecar()
    sidecar = {"schema_version": "argus_research/v1", "unexpected": True}
    return {"research": sidecar}
""",
            id="reassignment",
        ),
        pytest.param(
            """
def future_producer(use_raw):
    sidecar = build_research_sidecar()
    if use_raw:
        sidecar = {"schema_version": "argus_research/v1", "unexpected": True}
    return {"research": sidecar}
""",
            id="conditional-reassignment",
        ),
        pytest.param(
            """
def future_producer():
    sidecar = build_research_sidecar()
    sidecar["unexpected"] = True
    return {"research": sidecar}
""",
            id="item-mutation",
        ),
        pytest.param(
            """
def future_producer():
    sidecar = build_research_sidecar()
    sidecar.update({"unexpected": True})
    return {"research": sidecar}
""",
            id="method-mutation",
        ),
        pytest.param(
            """
def future_producer():
    sidecar = build_research_sidecar()
    del sidecar["sources"]
    return {"research": sidecar}
""",
            id="item-deletion",
        ),
        pytest.param(
            """
def future_producer():
    payload = {"research": build_research_sidecar()}
    payload["research"]["unexpected"] = True
    return payload
""",
            id="emitted-container-mutation",
        ),
        pytest.param(
            """
def future_producer():
    payload = {"research": build_research_sidecar()}
    payload["research"].update({"unexpected": True})
    return payload
""",
            id="emitted-container-method-mutation",
        ),
        pytest.param(
            """
def future_producer():
    payload = {"research": build_research_sidecar()}
    sidecar = payload["research"]
    sidecar.update({"unexpected": True})
    return payload
""",
            id="emitted-alias-mutation",
        ),
    ],
)
def test_a_builder_result_cannot_be_laundered_or_mutated(bypass: str) -> None:
    assert _producer_violations(bypass, "future_producer.py")


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
