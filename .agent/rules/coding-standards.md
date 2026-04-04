---
description: Python coding standards — loguru, type hints, 90 char limit, pydantic.
globs: ["src/**/*.py"]
---

# Coding Standards Rule

1. Use `loguru` for all logging. Prohibit standard `logging` module and `print()` calls.
2. 100% type hint coverage on all function signatures.
3. 90 character line limit (ruff enforced).
4. Use Pydantic `BaseModel` for data crossing boundaries.
5. Use `pydantic-settings` for configuration (never raw `os.environ`).
6. Modern Python: `str | None` not `Optional[str]`, `list[str]` not `List[str]`.

See: `.agent/skills/coding-standards/SKILL.md` for full details.
