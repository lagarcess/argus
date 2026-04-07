---
description: Conventional commits, branch naming, monorepo coordination, feature flags, PR process.
---

# Git Workflow Rule

## Branch Naming

`<type>/issue-<num>-<short-desc>` — e.g., `feat/issue-42-backtest-api` or `feat/issue-43-ui-custom-entry`

**Optional scope for monorepo clarity:**

- `feat/issue-42-api-custom-entry` (backend focus)
- `feat/issue-43-web-custom-entry-form` (frontend focus)

**Types:** `feat`, `fix`, `refactor`, `chore`, `docs`, `perf`, `test`, `strip`

## Commit Messages

```
<type>(<scope>): <concise description> (#<issue>)

- Detail 1
- Detail 2
```

**Scope examples:** `api`, `web`, `analysis`, `auth`, `db`, `migrations`

### Types

| Type       | When                                   |
| ---------- | -------------------------------------- |
| `feat`     | New feature                            |
| `fix`      | Bug fix                                |
| `refactor` | Code restructure (no behavior change)  |
| `chore`    | Build, CI, tooling, dependency updates |
| `docs`     | Documentation, API contract updates    |
| `perf`     | Performance improvement                |
| `test`     | Adding/fixing tests                    |

## Monorepo Guidelines

1. **API Contract Changes First**: If updating API schema (Pydantic), commit that separately with scope `docs(api-contract)` before backend/frontend implementation PRs.
2. **Parallel PRs OK**: Backend (`feat/api-...`) and frontend (`feat/web-...`) can have open PRs simultaneously against same issue. Merge API contract PR first, then both can merge together.
3. **Feature Flags**: Use `NEXT_PUBLIC_<FLAG_NAME>` convention (e.g., `NEXT_PUBLIC_FEATURE_MULTI_ASSET`). Commit flag to `web/.env.example` so it's discoverable.
4. **Environment Consistency**: Backend + frontend must be able to run together after `setup.sh`. Commit `.env.example` files (never actual secrets).

## PR Process

1. Pass `/verify` before opening PR.
2. Reference issue number in PR title and body.
3. One logical change per PR — avoid mega-PRs (but related backend + frontend changes can be in one PR if they touch the API contract).
4. If PR touches API schema, include link to `docs/api_contract.md` update.
5. Squash merge to main.

See: `.agent/workflows/pr.md` for full PR workflow, `.agent/skills/monorepo-patterns/SKILL.md` for coordination details.
