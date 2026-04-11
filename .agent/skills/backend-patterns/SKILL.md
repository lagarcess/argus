---
name: Backend Patterns
description: API design, data provider patterns, caching strategies, and Pydantic schema conventions for the Argus engine.
---

# Backend Patterns

## Data Provider Pattern
The `MarketDataProvider` in `src/argus/market/data_provider.py` is the single interface for all market data. Follow these patterns:

### Retry with Backoff
```python
@retry_with_backoff(max_retries=3, base_delay=1.0)
def fetch_bars(symbol, timeframe, start, end):
    ...
```
- Always use the `@retry_with_backoff` decorator for external API calls.
- Log failures with `loguru`, never swallow exceptions silently.

### Caching
- Disk caching via `joblib.Memory` when `ENABLE_MARKET_DATA_CACHE=true`.
- Cache location: `.gemini/cache/` (gitignored).
- Cache only for development/backtesting, never in production API paths.

## Configuration Pattern
All settings flow through `src/argus/config.py`:
```python
settings = get_settings()  # Singleton via lru_cache
```
- Use `pydantic-settings` with `.env` file loading.
- Validate on startup, fail fast with clear error messages.
- Never read `os.environ` directly — always go through `Settings`.

## Schema Design
- Domain schemas live in `src/argus/domain/schemas.py`.
- Use `str` enums for serialization safety: `class AssetClass(str, Enum)`.
- All API-facing models must be Pydantic `BaseModel`.

## Error Handling
- Define custom exceptions in `market/exceptions.py`.
- Raise specific exceptions (`MarketDataError`), not generic `Exception`.
- Always include context in error messages.

## Future: API Layer
When adding FastAPI/Next.js API routes:
- Place API routes in `src/argus/api/`.
- Use dependency injection for settings and clients.
- Return Pydantic models from all endpoints.
- Add OpenAPI metadata (summary, description, tags).
