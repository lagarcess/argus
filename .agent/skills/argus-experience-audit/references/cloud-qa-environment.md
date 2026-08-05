# Argus all-purpose cloud QA environment

Use one reusable, non-production environment for most Argus implementation and
experience-audit tasks. The environment supplies capabilities; each task still
owns its scope, evidence, and provider budget.

## Required capabilities

1. Linux runner with Docker, Git worktrees, a headed browser, Python `3.10.20`,
   Poetry, Bun, and repository dependencies.
2. Fresh branch from `codex/private-alpha-next` with the repository's canonical
   worktree environment setup and topology check.
3. Unique local Supabase project, ports, containers, volumes, and disposable
   Guest/registered identities per task.
4. Browser-accessible frontend, backend, and local workflow service from the
   exact candidate SHA.
5. Artifact storage for sanitized screenshots, JSON evidence, logs, hashes,
   and reports.

## Safe configuration

Provide task-scoped non-production values through the cloud secret store:

- OpenRouter interpreter credentials;
- Alpaca market-data credentials;
- Perplexity credentials for grounded discovery;
- Supabase local-development configuration;
- Turnstile test credentials when the tested surface requires CAPTCHA.

Inject process-only local QA tokens at launch. Do not persist them in tracked
or shared environment files. Never provide production database, Render,
founder, or hosted Supabase credentials by default.

Mirror integration feature defaults. Override a flag only for a named scenario
and record the override in the evidence.

## Execution tiers

1. **Deterministic:** synthetic market data, provider keys blanked, mocked eval
   harness, unit/integration tests.
2. **Provider-backed browser:** real interpreter/search/market-data calls inside
   the task's explicit turn and dollar cap.
3. **Paid live eval:** disabled unless the active roadmap or founder explicitly
   requires the interpreter-facing gate.
4. **Hosted mutation/deployment:** disabled unless separately authorized.

## Provider-free preflight

Before spending a turn, prove:

- expected branch, exact SHA, clean tree, and environment topology;
- migrations applied from zero;
- unique project/container names and free ports;
- backend started after database reset;
- frontend origin accepted by CORS;
- Guest bootstrap and registered non-admin authentication;
- feature flags and provider mode;
- browser navigation and health endpoints;
- empty or deliberately seeded accounting state.

If preflight fails, fix the QA harness or launch wiring and rerun it. Examples
include missing CORS origin, absent local CAPTCHA token, stale database pool,
wrong service URL, detached environment link, or fixture shape mismatch. These
are not product blockers.

## Guardrails

- Keep a per-task provider ledger and stop at the lower of the turn or dollar
  cap.
- Permit at most one replacement provider-backed journey after a proven QA
  wiring failure; do not retry product failures to manufacture green evidence.
- Stop immediately for production/hosted mutation, destructive Git/database
  action, unresolved founder choice, or unavailable required provider.
- Do not run multiple Playwright configs against a shared `.next` directory.
- Never print secrets or retain raw traces containing cookies or headers.
- Teardown only task-owned identities, processes, ports, containers, networks,
  volumes, and browser profiles.

## Cloud task suitability

No special label is required. A cloud agent can deliver the issue end to end
when all of the following are true:

1. The expected product behavior is locked in the issue, canon, or founder
   addendum.
2. The task does not require main promotion, deployment, or hosted data repair.
3. Its dependencies are available in this environment.
4. Its provider budget and exact acceptance journey are stated.
5. The agent may correct disposable QA wiring without another permission turn.

If only product taste is unresolved, use the audit to present the smallest set
of materially different choices. Do not disguise that decision as an
environment blocker.
