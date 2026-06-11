# Jules Agent Instructions

This folder is the small instruction surface Jules auto-loads for Argus work.
It must stay current, narrow, and subordinate to `AGENTS.md`.

## Branch Model

Jules works only in the downstream intake lane:

```text
main
  -> codex/private-alpha-next
       -> codex/private-alpha-next-jules-intake
            -> jules/<focused-low-risk-task>
```

Rules:

- Start Jules task branches from `codex/private-alpha-next-jules-intake`.
- Name Jules branches `jules/<short-focused-task>`.
- Open Jules PRs back to `codex/private-alpha-next-jules-intake`.
- Do not push to `main`, `codex/private-alpha-next`, or the intake branch.
- Do not rebase Jules work directly on `main`.
- Treat `codex/private-alpha-next` as the integration source of truth. Codex
  will periodically merge or fast-forward it down into the intake branch.

## Required Reading

Before changing files, read:

1. `AGENTS.md`
2. `docs/specs/private-alpha-next-integration.md`
3. `.agent/.jules/realignment.md`
4. The canon docs listed in `AGENTS.md` when the task touches product behavior,
   architecture, API contracts, data model, or design.

## Scope

Jules is for low-risk, focused debt work unless a task says otherwise.

Good Jules tasks:

- docs hygiene and stale-reference cleanup
- small test coverage additions
- i18n string consistency
- local-only script cleanup
- narrow dead-code removal with tests
- small UI polish that does not change runtime behavior

Avoid unless explicitly authorized:

- Argus runtime or LangGraph behavior changes
- Supabase schema/RLS migrations
- Render deploy or workflow configuration changes
- live Supabase writes
- production env or secret changes
- broad large-file refactors
- Perplexity Research Lab implementation

## Setup

Run the project bootstrap first:

```bash
.github/setup.sh
```

If `.env` or `web/.env.local` are missing, use safe development defaults. Do
not require production secrets for low-risk debt work.

## Verification

Every Jules PR must report:

- branch base and target branch
- files changed
- exact verification commands run
- browser QA notes when UI changed
- known caveats

Use focused checks by default. Run broader checks when the task touches shared
contracts, runtime behavior, frontend rendering primitives, or CI setup.

## Safety

- MCP access is read-only by default.
- Render or Supabase write operations require explicit task authorization.
- Never commit `.env`, `web/.env.local`, credentials, API keys, tokens, or local
  admin scripts.
- Keep generated scratch output under `temp/`.
- If instructions conflict, stop and report the conflict instead of guessing.
