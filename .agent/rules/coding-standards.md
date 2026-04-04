---
description: Coding standards and stylistic constraints (Model Decision - Trigger anytime code is written or reviewed)
---

# Coding Standards

Enforce these standards strictly across the entire Python codebase.

## 1. Logging
- **Rule**: Standard `print()` is prohibited in production source code.
- **Implementation**: You must use `loguru` (`from loguru import logger`).
- **Context**: Always bind context to logs when dealing with entities.
  - `logger.info(f"Processing symbol {symbol}")`
  - Even better: `logger.bind(symbol=symbol).info("Processing")`

## 2. Types and Parsing
- **Rule**: 100% type hint coverage is required (enforced by `mypy`).
- **Data Validation**: Avoid raw `dict` passing between boundaries. Use Pydantic schemas (`crypto_signals.domain.schemas`) to validate shapes and types.

## 3. Formatting
- **Rule**: Maximum line length is 90 characters.
- **Exceptions**: Long URLs in comments or strings that cannot be broken.

## 4. Defensive Programming
- **Rule**: Always handle `None`. If a dictionary lookup (`.get()`) or a database fetch could return `None`, you must explicitly handle that branch before accessing properties.
