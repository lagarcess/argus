---
name: Coding Standards
description: Python coding standards for the Argus engine. Enforces loguru logging, type hints, Pydantic validation, and line length limits.
---

# Coding Standards

## Logging
- **Always** use `loguru` for logging. Never use `print()` or the standard `logging` module.
- Use structured context: `logger.info("Processing symbol", symbol=symbol, asset_class=asset_class)`
- Use appropriate levels: `debug` for internals, `info` for lifecycle, `warning` for recoverable issues, `error` for failures.

## Type Hints
- **100% type hint coverage** on all function signatures (parameters + return types).
- Use modern syntax: `str | None` instead of `Optional[str]`, `list[str]` instead of `List[str]`.
- Complex types should use `TypeAlias` or Pydantic models.

## Code Style
- **90 character line limit** (enforced by ruff).
- Use double quotes for strings.
- Follow PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes.

## Validation
- Use **Pydantic** `BaseModel` for all data structures that cross boundaries (API, config, schemas).
- Use `pydantic-settings` for environment variable configuration.
- Validate early, fail explicitly with clear error messages.

## Imports
- Sort with `isort` (via ruff).
- Group: stdlib → third-party → local (`argus.*`).
- Never use wildcard imports (`from x import *`).

## File Organization
- One primary class per file when the class is substantial (>100 lines).
- Keep modules focused: analysis logic in `analysis/`, market data in `market/`, domain types in `domain/`.
