---
name: Security Review
description: Security checklist for API boundaries, secret handling, .env safety, and dependency auditing.
---

# Security Review

## Secret Management
- **Never** commit secrets to git. All secrets go in `.env` (gitignored).
- `.env.example` contains placeholder values only — never real keys.
- Use `pydantic-settings` to load secrets; never read `os.environ` directly.
- API keys must be validated on startup: fail fast if missing.

## .env Safety Checklist
- [ ] `.env` is in `.gitignore`
- [ ] `.env.example` has no real values
- [ ] No secrets in `pyproject.toml`, CI configs, or source code
- [ ] No secrets in git history (check with `git log -p -- .env`)

## API Boundaries (Future)
When adding the API layer:
- Validate all input with Pydantic models (never trust raw request data).
- Rate-limit expensive endpoints (backtests).
- Use CORS allowlists — never `Access-Control-Allow-Origin: *` in production.
- Return generic error messages to clients; log detailed errors server-side.

## Authentication (Future)
- Use NextAuth.js with Google/Facebook OAuth providers.
- Store sessions server-side (not JWT in localStorage).
- Protect all API routes with auth middleware.
- Role-based access: free tier vs pro tier rate limits.

## Dependency Auditing
- Run `pip-audit` periodically to check for known vulnerabilities.
- Pin major versions in `pyproject.toml` (e.g., `^2.7.0`).
- Review dependency changelogs before major upgrades.

## Code Review Security Flags
When reviewing PRs, flag:
- Hardcoded secrets or API keys
- SQL/NoSQL injection vectors
- Unvalidated user input
- Overly permissive CORS or auth
- Logging of sensitive data (passwords, tokens, PII)
