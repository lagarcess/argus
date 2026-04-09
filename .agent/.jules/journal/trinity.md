## [2026-04-07] - Follow-up: Add Strategies API Endpoint Tests

- **Gap:** `/api/v1/strategies` endpoint had 43% coverage initially.
- **Current status:** Added mock tests for all strategy API endpoints using `TestClient` and unified with legacy schema/validation tests into `tests/test_strategies_api.py`.
- **Coverage gain:** `src/argus/api/strategies.py` 43% -> 100%, Overall 72% -> 73%
- **Result:** RESOLVED (New branch `core/test/trinity-strategies-api-endpoints`)
