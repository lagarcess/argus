from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def find_project_root(start: Path | str | None = None) -> Path | None:
    current = Path(start) if start is not None else Path(__file__)
    current = current.resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "argus"
        ).is_dir():
            return candidate

    return None


def load_project_dotenv(start: Path | str | None = None) -> bool:
    project_root = find_project_root(start)
    if project_root is None:
        return False

    dotenv_path = project_root / ".env"
    if not dotenv_path.is_file():
        return False

    return load_dotenv(dotenv_path=dotenv_path, override=False)
