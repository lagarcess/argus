---
description: Monorepo workspace conventions — temp/, Poetry, Bun, file organization, frontend/backend integration.
---

# Workspace Rule

## Backend (Python)

1. **Use `temp/`** for all scratch files, plans, issue dumps, and coverage reports. Never in project root.
2. **Poetry**: Use `poetry run` for all commands. Lock file (`poetry.lock`) is committed.
3. **No bytecode**: `DONT_WRITE_BYTECODE=1` in dev environments.
4. **Package structure**: All source in `src/argus/`, all tests in `tests/`.
5. **Environment**: Root `.env` for backend secrets only (ALPACA_API_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET).

## Frontend (Next.js / JavaScript)

6. **Bun**: Use Bun instead of npm (`bun install`, `bun run dev`, `bun run build`).
7. **Environment**: `web/.env.local` for frontend public config only (NEXT*PUBLIC*\* vars).
   - `NEXT_PUBLIC_API_URL` points to backend (http://localhost:8000/api/v1 in dev)
   - `NEXT_PUBLIC_MOCK_API=true` toggles fake data (development without backend)
   - `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` for client auth
8. **Never commit secrets** to `web/.env.local` or root `.env` (use `.env.example` templates).

## Monorepo Conventions

9. **API Contract First**: Before coding, update `docs/api_contract.md`. Backend Pydantic schema ↔ Frontend TypeScript types must stay synchronized.
10. **Mock Data**: Frontend uses `web/lib/mockApi.ts` (Faker-based) until backend is ready. Toggle via `NEXT_PUBLIC_MOCK_API` environment variable.
11. **Coordinated Deployment**: Run both via `setup.sh` → backend on 8000, frontend on 3000. Both read from same Supabase instance.
12. **GitHub scripts**: Agent context scripts live in `.agent/scripts/github/`. Agent definitions in `.agent/agents/`, skills in `.agent/skills/`, rules in `.agent/rules/`.
13. **Git workflow**: Use conventional commits with optional scopes (e.g., `feat(api):`, `feat(web):`). Branch names can include scope (e.g., `feat/api-custom-entry-condition`).
