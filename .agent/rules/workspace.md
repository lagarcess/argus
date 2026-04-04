---
description: Workspace conventions — temp/, Poetry, file organization.
---

# Workspace Rule

1. **Use `temp/`** for all scratch files, plans, issue dumps, and coverage reports. Never in project root.
2. **Poetry**: Use `poetry run` for all commands. Never install globally.
3. **No bytecode**: `DONT_WRITE_BYTECODE=1` in dev environments.
4. **Package structure**: All source in `src/argus/`, all tests in `tests/`.
5. **GitHub scripts**: Agent context scripts live in `.agent/scripts/github/`.
6. **Environment**: All config via `.env` loaded by `pydantic-settings`.
