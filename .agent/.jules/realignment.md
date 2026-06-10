# Jules Realignment Protocol

Jules must keep its work aligned with the intake branch, not directly with
`main`.

## When To Realign

Run this protocol:

1. At the beginning of every task.
2. After a pause or resumed session.
3. Before opening or updating a PR.
4. If `AGENTS.md`, canon docs, API contracts, database schema, CI, or setup
   scripts changed while the task was in progress.
5. After long-running work where branch state may have drifted.

## 1. Synchronize With Intake

If working on a `jules/*` branch:

```bash
git fetch origin codex/private-alpha-next-jules-intake
git rebase origin/codex/private-alpha-next-jules-intake
```

If inspecting the intake branch itself:

```bash
git fetch origin codex/private-alpha-next-jules-intake
git pull --ff-only origin codex/private-alpha-next-jules-intake
```

Do not rebase directly onto `main`. Do not merge `main` yourself. If the intake
branch appears stale relative to `codex/private-alpha-next`, report that to
Codex instead of repairing it ad hoc.

## 2. Re-check The Task

Before editing, confirm:

- the task is low-risk and focused enough for Jules
- the target PR base is `codex/private-alpha-next-jules-intake`
- the planned files match the requested scope
- the task does not require live Supabase writes, Render deploys, production
  secrets, or schema migrations unless explicitly authorized

If any answer is unclear, stop and ask for clarification.

## 3. Re-read Relevant Truth

Always read:

- `AGENTS.md`
- `docs/specs/private-alpha-next-integration.md`
- the active task prompt

Also read the relevant canon doc when touching:

- product behavior: `docs/PRODUCT.md`
- architecture or service ownership: `docs/ARCHITECTURE.md`
- request/response contracts: `docs/API_CONTRACT.md`
- persistence, RLS, or ownership: `docs/DATA_MODEL.md`
- UI, typography, color, or interaction: `.agent/designs/argus/DESIGN.md`

## 4. Validate Proportionally

Use focused verification first:

- docs-only: `git diff --check`
- Python/test changes: focused `poetry run pytest ... -q --no-cov` plus ruff
- frontend changes: focused `cd web && bun test ...`, and browser QA when visual
- CI/setup changes: run `.github/setup.sh` or the relevant workflow test

Run broader checks when touching shared runtime, contracts, CI, or frontend
rendering primitives.

## 5. Final Report

Every Jules handoff must include:

- branch name and target branch
- short summary of changes
- exact tests/checks run
- browser QA notes if UI changed
- known caveats or skipped checks
- whether any live systems were read or mutated
