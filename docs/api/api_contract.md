# API Contract – Argus Narrow MVP (Private Beta)

**Status**: Active Source of Truth (Narrow MVP)
**Version**: 1.1.0-narrow
**Last Updated**: 2026-04-16
**Base URL**: `https://api.argus.app/api/v1/`
**OpenAPI Spec**: [openapi.yaml](openapi.yaml)
**Full Vision Archive**: [api_contract_full_vision.md](api_contract_full_vision.md)

## Scope (10-day private beta loop)
This contract covers only the release-critical loop:
1. Onboarding
2. AI strategy draft
3. Save/edit strategy
4. Run backtest
5. Backtest results + history
6. Logout

## Canonical response decisions
- `GET /strategies` returns `{ "strategies": StrategyResponse[], "next_cursor": string | null }`.
- `POST /agent/draft` returns `{ "draft": StrategyCreate, "ai_explanation": string }`.
- `UserResponse` includes onboarding state (`onboarding_completed`, `onboarding_step`, `onboarding_intent`).
- `win_rate` is serialized as a decimal ratio (0..1) in history and detail reads.
- `fidelity_score` is serialized as decimal ratio (0..1).

## Narrow endpoint surface
- `GET /health`
- `GET /auth/session`
- `PATCH /auth/profile`
- `POST /auth/logout`
- `GET /usage`
- `GET /assets`
- `POST /agent/draft`
- `GET /strategies`
- `POST /strategies`
- `GET /strategies/{id}`
- `PUT /strategies/{id}`
- `DELETE /strategies/{id}`
- `POST /backtests`
- `GET /backtests/{id}`
- `GET /history`

## Delta to Full Vision
| Area | Full Vision | Narrow MVP Decision |
|---|---|---|
| Sharing/Billing/Feedback/Screeners | Planned endpoints in v1 vision | Deferred; not in active OpenAPI |
| TradingView UDF depth | Full UDF parity target | Minimal `/market/bars` passthrough only |
| Quotas | Bucket + weighted + slot roadmap | Bucket model only |
| Walk-forward automation | Full orchestration target | Deferred for beta stability |
| AI journaling/memos loop | Integrated psych layer | Deferred; draft-only AI flow |

## Release gate semantics
- No OpenAPI/client drift.
- History and backtest detail must agree on metric units.
- Manual builder must remain functional when AI draft fails or quota is exhausted.
- Logout clears local UX session even if remote revoke fails.
