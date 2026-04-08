**API Spec - MVP (DRAFT)**

**Overview**

- **Purpose**: Argus is a mobile-first PWA for retail trading backtesting. It provides high-fidelity, price-action-focused simulations with Numerai-level honesty (slippage, fees, walk-forward validation, explicit entry/exit criteria, pattern confluence).
- **Scope**: Single-symbol only (models prepared for multi-asset via feature flag). Minimum 15m timeframe. Focus on patterns + price action (no code upload or advanced options in MVP).
- **Tiers**: Free (50 backtests/month, basic metrics), Pro (high/unlimited quota, reality gap), Max (priority + future multi-asset).
- **Admin Override**: Founder (is_admin = true) gets unlimited quota, no rate limits, full feature access, and **zero PostHog events** (analytics exclusion). Subscription_tier remains “max” for UI, but is_admin is the master bypass.
- **User Experience**: Persisted theme + lang. PostHog only for non-admin users.
- **Optimal User Flow** (matches 2026 free-tool baselines + our edge):
  1. Discovery: Search valid assets (/assets — includes data horizon).
  2. Builder: Create/load draft strategy (/strategies) with explicit entry/exit + patterns + optional fee_model.
  3. Simulation: Run via /backtests (sync, <3s).
  4. Analysis: View full results (equity curve + reality gap + pattern breakdown + trades snippet). Strategy becomes immutable.
  5. Review: Cursor-paginated history with sparklines + paginated trades.
  6. Feedback: Quick bug/suggestion reporting.

**General Conventions (applied everywhere)**

- **Versioning**: All routes under `/api/v1/`. OpenAPI 3.1 schema auto-generated for TanStack Query + TS client regeneration.
- **JSON style**: snake_case, plural nouns, no verbs.
- **Success responses**: Return data object directly.
- **Error responses** (one format only):
  ```json
  {
    "error": "QUOTA_EXCEEDED",
    "message": "You have 0 backtests remaining this month.",
    "details": { "next_reset": "2026-05-01T00:00:00Z" }
  }
  ```
  Feature-disabled:
  ```json
  {
    "error": "FEATURE_DISABLED",
    "message": "Multi-asset backtesting is not enabled for your tier.",
    "details": { "feature": "multi_asset_beta", "available_in": "pro_tier" }
  }
  ```
- **Timestamps**: Always ISO 8601 UTC with `Z`.
- **UUIDs**: Always UUIDv4.
- **Pagination**: Cursor-based (opaque base64 string of `timestamp+id`) on **all** list endpoints.
- **Rate-limit headers** (returned on every response): `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, `Retry-After`.
- **Feature flags**: Return 403 Forbidden if a flagged feature is used when disabled (bypassed for is_admin = true).
- **Quota**: `remaining_quota` decrements in real-time on successful `POST /backtests` (bypassed for is_admin = true). Monthly reset via Supabase Edge Function cron.
- **Rate Limiting (Beyond Quota)**: All endpoints return X-RateLimit-\* headers. Exceeding limits returns 429 Too Many Requests with Retry-After header.
  - Per-minute limits (Tier 2): Asset searches (100), Strategy CRUD (30), Feedback (10)
  - Per-minute auth limits (Tier 3): Login (5), SSO (20)
  - Per-hour limit (Tier 4): 1000 req/hour (ecosystem protection)
    **is_admin = true** bypasses all rate limits and quotas.
- **Admin Bypass**: Any user with `is_admin: true` in profiles gets unlimited access and is excluded from PostHog tracking (set once for founder email).
- **Data fetching**: All market data always sourced from Alpaca (with retries and exponential backoff); no user uploads or alternative providers in V1.
- **Corporate actions**: Automatically handled using Alpaca's adjusted close/volume data for stocks/ETFs (splits, dividends); explicit flag planned for V2.

**Endpoints (API Version: /api/v1/)**

**1. Authentication & Identity**
Supabase JWT delivered via httpOnly cookies (SameSite=Strict, Secure=true). No manual CSRF token required.

- **GET /api/v1/auth/session**
  Purpose: Current user + limits + flags.
  Response (UserResponse):

  ```json
  {
    "id": "uuid-v4",
    "email": "trader@argus.app",
    "is_admin": true,
    "subscription_tier": "max",
    "theme": "dark",
    "lang": "en",
    "backtest_quota": 999999,
    "remaining_quota": 999999,
    "last_quota_reset": "2026-04-01T00:00:00Z",
    "feature_flags": { "multi_asset_beta": true, "advanced_harmonics": true }
  }
  ```

  **is_admin = true** silently bypasses quota checks, rate limits, and PostHog events in every backend handler.

- **POST /api/v1/auth/sso**
  Request: `{ "provider": "google" | "facebook" | "apple", "redirect_to": "string" }`
  Response: `{ "auth_url": "https://..." }` (frontend redirects immediately).
  Note: Supabase-native Turnstile CAPTCHA required on forms. 409 Conflict on identity linking (see error details).

- **PATCH /api/v1/auth/profile**
  Request: `{ "theme": "dark", "lang": "es" }`
  Purpose: Persist preferences (is_admin cannot be changed via API).

- **POST /api/v1/auth/logout**
  Request: `{}`
  Response: 204 No Content.
  Purpose: Clear httpOnly cookie + revoke Supabase session.

**2. Market Assets**

- **GET /api/v1/assets**
  Query: `search=string&timeframe=string` (min "15m").
  Purpose: Alpaca-validated lookup (used in builder). Returns array of matching symbols.

**3. Strategies (CRUD — editable until executed)**
All list endpoints use cursor pagination.

- **POST /api/v1/strategies**
  Request (StrategyCreate):

  ```json
  {
    "name": "Golden Cross DR",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2026-04-01T00:00:00Z",
    "entry_criteria": [
      {
        "indicator": "SMA",
        "period": 50,
        "condition": "crosses_above",
        "target": "SMA_200"
      }
    ],
    "exit_criteria": { "stop_loss_pct": 0.02, "take_profit_pct": 0.06 },
    "indicators_config": { "rsi": { "period": 14 } },
    "patterns": ["gartley", "morning_star"]
  }
  ```

  Response: `{ "id": "uuid-v4", "name": "..." }`

- **GET /api/v1/strategies**
  Query: `cursor=string&limit=10`.
  Response: Paginated list of editable drafts.

- **GET /api/v1/strategies/{id}**
  Response: Full Strategy object (for builder load/edit).

- **PUT /api/v1/strategies/{id}**
  Same request body as POST. Returns 403 if `executed_at` is set.

- **DELETE /api/v1/strategies/{id}**
  Returns 204 No Content if `executed_at` is null; else 403.

**4. Backtesting (Simulations)**
**Sync execution** (engine <3s).

- **POST /api/v1/backtests**
  Request (BacktestRequest — strict XOR):

  ```json
  {
    "strategy_id": "uuid-v4"
    // OR full inline StrategyCreate object (NEVER both — 422 error)
  }
  ```

  Purpose: Run + emit PostHog event + decrement quota immediately.
  Response (BacktestResponse):

  ```json
  {
    "id": "uuid-v4",
    "config_snapshot": { "...frozen_strategy..." },
    "results": {
      "total_return_pct": 14.5,
      "win_rate": 0.62,
      "sharpe_ratio": 1.8,
      "sortino_ratio": 2.1,
      "calmar_ratio": 1.2,
      "profit_factor": 1.5,
      "expectancy": 0.45,
      "max_drawdown_pct": 0.05,
      "equity_curve": [100, 101.5, 100.2, ...],   // portfolio value, starts at 100
      "trades": [ { "entry_time": "...", "entry_price": 65000, "exit_price": 67000, "pnl_pct": 3.1 } ],  // first 5 trades only (snippet)
      "reality_gap_metrics": { "slippage_impact_pct": 1.2, "fee_impact_pct": 0.4 },
      "pattern_breakdown": { "gartley_hits": 4, "morning_star_hits": 2 }
    }
  }
  ```

  Errors: 402 (Quota), 422 (Invalid entry/exit/timeframe/symbol or both fields present), 429 (Rate limit).

- **GET /api/v1/backtests/{id}**
  Response: Full BacktestResponse (full trades array inside `full_result` JSONB; used from history clicks).

**5. History & Feedback**

- **GET /api/v1/history**
  Query: `cursor=string&limit=10`.
  Response (PaginatedHistory):

  ```json
  {
    "simulations": [
      {
        "id": "uuid-v4",
        "strategy_name": "Golden Cross DR",
        "symbols": ["BTC/USDT"],
        "timeframe": "1h",
        "status": "completed",
        "total_return_pct": 14.5,
        "sharpe_ratio": 1.8,
        "max_drawdown_pct": 5.2,
        "win_rate_pct": 62.0,
        "total_trades": 42,
        "created_at": "2026-04-07T13:15:00Z",
        "completed_at": "2026-04-07T13:15:45Z"
      }
    ],
    "total": 100,
    "next_cursor": "base64-opaque-string"
  }
  ```

  **Note**: Sparkline (exactly 15 portfolio-value points, evenly downsampled) is computed client-side from full_result equity_curve when user clicks into backtest detail.

- **POST /api/v1/feedback**
  Request: `{ "type": "bug" | "suggestion" | "feature", "message": "string", "simulation_id": "uuid-v4?" }`

**6. Development & Monitoring**

- **GET /api/v1/health**
  Response: `{ "status": "ok", "version": "1.0" }` (no auth required).

- **GET /api/v1/\_mocks/backtest**
  Returns faker-generated BacktestResponse (dev-only, gated by feature flag).

**Patterns Enum (valid values for strategies.patterns)**
`["gartley", "butterfly", "crab", "bat", "cypher", "shark", "morning_star", "evening_star", "three_white_soldiers", "three_black_crows", "hammer", "shooting_star", "doji", "engulfing"]` (exact values from harmonics.py + structural.py).

**Database Schema (PostgreSQL + RLS)**

- **profiles**: id (PK), is_admin (boolean, default false), subscription_tier, theme, lang, backtest_quota, last_quota_reset, feature_flags (JSONB).
- **strategies**: id (PK), user_id (FK), name, symbol, timeframe, start_date, end_date, entry_criteria (JSONB), exit_criteria (JSONB), indicators_config (JSONB), patterns (text[]), executed_at (nullable timestamp → immutable).
- **simulations**: id (PK), strategy_id (FK), config_snapshot (JSONB), summary (JSONB — sparkline + basic metrics), reality_gap_metrics (JSONB), full_result (JSONB — full trades + curve; capped <10MB or moved to Supabase Storage), created_at.
- **features**: id (PK — flag name), is_enabled (bool).

**RLS Policy Summary**: Users see/edit only their own rows (user_id = auth.uid()). Admins (is_admin = true) see all via RLS policy exception.

**Dependency Order**

1. Supabase migrations (add is_admin column + index + RLS admin exception + quota cron, profiles, strategies, simulations, features).
2. Auth layer + session/profile/logout.
3. Asset lookup.
4. Strategy CRUD (builder).
5. Backtest core + PostHog.
6. History + feedback (mobile UX).

**Code Audit Results**
**Reusable (keep exactly as-is)**: harmonics.py, structural.py, engine.py, indicators.py.
**Needs Modification**: (add is_admin to UserResponse + bypass guards), domain/persistence.py (immutability + sparkline sampling + JSONB size guard + trades pagination), + one-time migration for founder email.
**Delete/Archive**: deprecated routes + old schemas.py.

**Developer Experience & Observability**

- **PostHog events**: `backtest_run` (properties: tier, duration_ms, profitable, pattern_count). — skipped entirely when is_admin = true.
- **Correlation IDs**: All responses include `X-Correlation-ID` header (echoed from request or generated).
- **JWT lifetime**: Access token 1h, refresh token 7d (auto-refresh via Supabase client).
- **Retry strategy**: Retry 429/503 (exponential backoff); never retry 402/422/403.
- **OpenAPI client generation**: Run `openapi-ts --input http://localhost:8000/openapi.json --output web/lib/api.ts` after every backend change (TanStack Query hooks included). OpenAPI security scheme: `cookieAuth` (httpOnly).

# Review Checklist for the Spec

- [ ] All user flows covered? (backtest, history, strategies, auth)

- [ ] Request/response shapes clear and specific?

- [ ] Error cases documented?

- [ ] Database schema matches the API needs?

- [ ] Excalidraw diagrams make sense?

- [ ] Clear which code gets reused, which gets rewritten?

- [ ] Endpoint dependency order clear?

If all ✅, lock it. If ❌ on any, send back for revision.

**Next Iteration Briefing**  
V2 (informed by this V1 contract as source-of-truth): optional `data_adjusted: false` raw mode + corporate-action impact breakdown, multi-asset (behind flag), basic options with Greeks (Pro+ tier), custom indicator uploads, and full walk-forward/OOS in engine (addressing 2026 overfitting gaps). Engine rebuild will expose these via feature flags without breaking V1 clients.