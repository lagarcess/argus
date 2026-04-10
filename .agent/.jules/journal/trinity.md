## [2026-04-07] - Follow-up: Add Strategies API Endpoint Tests

- **Gap:** `/api/v1/strategies` endpoint had 43% coverage initially.
- **Current status:** Added mock tests for all strategy API endpoints using `TestClient` and unified with legacy schema/validation tests into `tests/test_strategies_api.py`.
- **Coverage gain:** `src/argus/api/strategies.py` 43% -> 100%, Overall 72% -> 73%
- **Result:** RESOLVED (New branch `core/test/trinity-strategies-api-endpoints`)

## [2026-04-10] - Proposal: Add Core API Endpoints Tests

- **Gap:** `/api/v1/auth/sso`, `/api/v1/auth/profile`, `/api/v1/simulations/{sim_id}`, `/api/v1/assets`, `/api/v1/usage`, and `/api/v1/auth/logout` endpoints had low coverage.
- **Proposed:** Implement 30+ tests in `tests/test_api.py`, `tests/test_auth_more.py` and `tests/test_persistence.py` mapping DB interactions with `mock_supabase_client`.
- **Status:** PENDING HUMAN REVIEW + PR

## [2026-04-10] - Follow-up: Core API Endpoints Tests Added

- **Previous:** proposed 2026-04-10 (add auth, sso, simulations, persistence and asset tests)
- **Current status:** ADDED + merged in PR (mock dependencies via FastAPI `dependency_overrides` and MagicMock).
- **Coverage gain:** `src/argus/api/main.py` 65% -> 98%, `src/argus/api/auth.py` 23% -> 97%, `src/argus/domain/persistence.py` 17% -> 66%
- **Result:** RESOLVED (New branch `core/test/trinity-api-auth-persistence`)
