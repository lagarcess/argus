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

## [2026-04-11] - Frontend Speedrun (Unblocking the UI)

### Context
The Python backend is currently under reconstruction and considered broken. To unblock frontend development and establish a type-safe, mock-driven environment, we decoupled the UI from the backend completely.

### Approach
1.  **Type-Safe Generation**: Utilized `@hey-api/openapi-ts` with the `@tanstack/react-query` plugin to parse the existing `docs/api/openapi.yaml`. This generated fully-typed TypeScript fetch clients and `useQuery`/`useMutation` hooks in `web/lib/api`.
2.  **Mock-Driven Environment**: Deployed `@stoplight/prism-cli` (`prism mock`) on port 4010 to serve spec-compliant responses dynamically. We intercepted Next.js server requests using this URL.
3.  **UI Reconstruction (Stitch)**: Leveraged the Stitch AI agent to generate the "Strategy Builder v1" and "Simulation History" pages based on the *Obsidian Prism* and *Emerald Zenith* themes, targeting a high-tech "Robinhood/Linear" glassmorphic aesthetic.
4.  **Data Wiring & Verification**: Stripped out legacy hardcoded data from `mockApi.ts`. Wired the generated components directly to the TanStack queries. To verify the setup, a Playwright test (`v1-ecosystem.vrt.ts`) was added that successfully stubs the Supabase auth session and performs end-to-end interactions with the mock-driven UI.

### Outcomes
- Frontend development can now proceed continuously without relying on a functional Python server.
- The UI components correctly interact with mock API endpoints utilizing strict `Zod`-like typing from the OpenAPI spec, eliminating undefined property crashes.
- The Golden Path Playwright E2E tests pass reliably in the CI-like headless mode.

## [2026-04-12] - Proposal: Add Main API Endpoints Tests

- **Gap:** `/api/v1/auth/session`, `/api/v1/usage`, `/api/v1/auth/sso`, `/api/v1/auth/profile`, `/api/v1/auth/logout`, and `/api/v1/simulations/{sim_id}` endpoints lacked coverage.
- **Proposed:** Implement test cases in `tests/test_api.py` to cover standard requests, missing dependencies (like supabase_client), "latest" fallbacks, and exception handling.
- **Status:** ADDED + merged in PR (mock dependencies via FastAPI `dependency_overrides` and MagicMock).
- **Coverage gain:** `src/argus/api/main.py` 62% -> 82%
- **Result:** RESOLVED (New branch `core/test/trinity-api-endpoints`)
