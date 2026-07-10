from __future__ import annotations

import os
from pathlib import Path

from argus.env import load_project_dotenv


def _write_project_marker(root: Path) -> None:
    (root / "pyproject.toml").write_text("[tool.poetry]\nname = \"argus-test\"\n")
    (root / "src" / "argus").mkdir(parents=True)


def test_project_dotenv_does_not_walk_above_project_root(
    tmp_path: Path, monkeypatch
) -> None:
    parent = tmp_path / "parent"
    child = parent / "child-worktree"
    parent.mkdir()
    child.mkdir()
    _write_project_marker(child)
    (parent / ".env").write_text("ARGUS_DOTENV_SENTINEL=parent\n")
    nested_module = child / "src" / "argus" / "api" / "state.py"

    monkeypatch.delenv("ARGUS_DOTENV_SENTINEL", raising=False)

    loaded = load_project_dotenv(start=nested_module)

    assert loaded is False
    assert "ARGUS_DOTENV_SENTINEL" not in os.environ


def test_project_dotenv_loads_project_root_without_overriding_process_env(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_project_marker(project)
    (project / ".env").write_text(
        "ARGUS_DOTENV_SENTINEL=project\n"
        "ARGUS_DOTENV_PROCESS_VALUE=dotenv\n"
    )
    nested_dir = project / "src" / "argus" / "llm"

    monkeypatch.delenv("ARGUS_DOTENV_SENTINEL", raising=False)
    monkeypatch.setenv("ARGUS_DOTENV_PROCESS_VALUE", "process")

    loaded = load_project_dotenv(start=nested_dir)

    assert loaded is True
    assert os.environ["ARGUS_DOTENV_SENTINEL"] == "project"
    assert os.environ["ARGUS_DOTENV_PROCESS_VALUE"] == "process"
