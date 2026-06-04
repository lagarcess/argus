from __future__ import annotations

import ast
from pathlib import Path

from argus.agent_runtime.artifacts.lifecycle import RetryLifecycleDecision

ROOT = Path(__file__).resolve().parents[1]


def _imports_symbol(source_path: Path, *, module: str, symbol: str) -> bool:
    tree = ast.parse(source_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            if any(alias.name == symbol for alias in node.names):
                return True
    return False


def test_render_python_runtime_avoids_python311_only_strenum() -> None:
    render_python_version = (ROOT / ".python-version").read_text().strip()
    lifecycle_module = ROOT / "src" / "argus" / "agent_runtime" / "artifacts" / "lifecycle.py"

    assert render_python_version.startswith("3.10.")
    assert not _imports_symbol(lifecycle_module, module="enum", symbol="StrEnum")


def test_render_python_runtime_keeps_string_enum_semantics() -> None:
    assert RetryLifecycleDecision.ACTIVE == "active"
    assert str(RetryLifecycleDecision.ACTIVE) == "active"
    assert RetryLifecycleDecision.ACTIVE.value == "active"
