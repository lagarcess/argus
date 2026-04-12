---
name: Coding Standards
description: Python coding standards for the Argus engine. Enforces loguru logging, type hints, Pydantic validation, and line length limits.
---

# Coding Standards

**When to use:** Writing or refactoring any backend Python code to ensure uniformity, robustness, and maintainability.

## Logging
- **Always** use `loguru` for logging. Never use `print()` or the standard `logging` module.
- Use structured context: `logger.info("Processing symbol", symbol=symbol, asset_class=asset_class)`
- Use appropriate levels: `debug` for internals, `info` for lifecycle, `warning` for recoverable issues, `error` for failures.

**Example:**
```python
from loguru import logger

def process_data(symbol: str) -> None:
    logger.info("Starting processing", symbol=symbol)
    try:
        # processing logic...
        pass
    except Exception as e:
        logger.error("Processing failed", symbol=symbol, error=str(e))
```

## Type Hints
- **100% type hint coverage** on all function signatures (parameters + return types).
- Use modern syntax: `str | None` instead of `Optional[str]`, `list[str]` instead of `List[str]`.
- Complex types should use `TypeAlias` or Pydantic models.

**Example:**
```python
def get_user_config(user_id: str) -> dict[str, str | int] | None:
    pass
```

## Code Style
- **90 character line limit** (enforced by ruff).
- Use double quotes for strings.
- Follow PEP 8 naming: `snake_case` for functions/variables, `PascalCase` for classes.

## Validation
- Use **Pydantic** `BaseModel` for all data structures that cross boundaries (API, config, schemas).
- Use `pydantic-settings` for environment variable configuration.
- Validate early, fail explicitly with clear error messages.

**Example:**
```python
from pydantic import BaseModel, Field

class StrategySchema(BaseModel):
    name: str = Field(..., max_length=120)
    timeframe: str
    symbols: list[str] = Field(default_factory=list)
```

## Imports
- Sort with `isort` (via ruff).
- Group: stdlib → third-party → local (`argus.*`).
- Never use wildcard imports (`from x import *`).

## File Organization
- One primary class per file when the class is substantial (>100 lines).
- Keep modules focused: analysis logic in `analysis/`, market data in `market/`, domain types in `domain/`.
