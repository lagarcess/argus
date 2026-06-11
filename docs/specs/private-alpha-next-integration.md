# Private Alpha Next Integration

Status: Active integration staging baseline
Date: 2026-06-10
Branch: `codex/private-alpha-next`
Audience: Founder, Codex, external async agents, reviewers

## Purpose

This document is the working source of truth for the next integration branch
after the private-alpha conversation trust checkpoint. It exists so every agent
starts from the current `main` reality, not from stale milestone debt.

The integration branch is a staging lane. It is allowed to collect reviewed work
before a future PR, but it is not a release branch and must not be merged or
deployed automatically.

## Branch Model

Use this flow:

```text
main
  -> codex/private-alpha-next
       -> codex/<focused-high-leverage-slice>
       -> codex/<focused-low-risk-debt-slice>
       -> codex/private-alpha-next-jules-intake
            -> jules/<focused-low-risk-debt-slice>
```

Rules:

- `main` remains the clean release checkpoint.
- `codex/private-alpha-next` is the only integration staging branch.
- `codex/private-alpha-next-jules-intake` is a downstream quarantine lane for
  low-risk Jules work. It is not the source of truth.
- Codex worker branches start from `codex/private-alpha-next`.
- Jules worker branches start from `codex/private-alpha-next-jules-intake`.
- Workers do not push directly to `main`.
- External async agents do not push directly to `codex/private-alpha-next`.
- Jules branches use the `jules/**` branch namespace and open PRs targeting
  `codex/private-alpha-next-jules-intake`.
- CI runs on pushes to `jules/**` and on PRs targeting
  `codex/private-alpha-next-jules-intake` so Jules can self-correct before
  Codex review.
- Codex reviews worker diffs before they are merged or cherry-picked into the
  integration branch.
- High-leverage work lands in `codex/private-alpha-next` first. Periodically
  merge or fast-forward `codex/private-alpha-next` down into
  `codex/private-alpha-next-jules-intake` so Jules does not work from stale
  context.
- Every slice ends with tests run, browser QA notes when relevant, known
  caveats, and a conventional commit.
- No production deploy happens from this branch unless the founder explicitly
  asks for a deploy check.

## Current Closed Items

Do not reopen these as debt unless a new bug is reproduced:

- Fast GitHub CI baseline exists.
- Manual CD remains manual.
- Post-merge `argus-app` deploy smoke passed on `2fc4773`.
- Empty composer send tooltip exists.
- Composer caret, placeholder, and `@` button alignment were polished for the
  known empty/focused/clicked states.
- Restored archived/recently-deleted chats refresh without the original stale
  list smell.
- The old static `@` preview was replaced with provider-backed discovery plus
  the supported indicator catalog.
- Asset discovery quality is closed for this batch: provider and indicator
  search results rank exact ticker/alias matches first, common crypto/currency
  aliases replace the full typed phrase, repeated browser-session discovery
  queries use the local cache, and stale visible results cannot be selected
  while a newer query is loading.
- The misleading "share conversation id" pseudo-action was removed.
- Status/action parity is closed for this batch: confirmation, queued/running,
  terminal job, result-card, feedback, retry, and more-menu surfaces now follow
  one artifact lifecycle, internal Copy ID is hidden, and terminal job actions
  remain scoped to the durable artifact instead of transcript prose.
- Result voice cleanup is closed for this batch: Quick take and Explain result
  remain distinct, Explain result uses the deeper fact-grounded breakdown
  surface, visible Try next result actions are removed, and normal follow-up
  guidance stays with the LLM chat brain.
- Local live QA proof was captured on 2026-06-11 in QA mode with real Supabase
  auth and API persistence: a GOOG buy-and-hold conversation rendered the
  confirmation card, completed result card, Quick take, and Explain result;
  no visible Try next, Quick Breakdown, Copy ID, or console/API regression was
  observed.
- Pre-merge internet readiness passed on 2026-06-11 for commit `dd65bf6`:
  Render `argus-api` deploy `dep-d8lj6ureo5us73fanrcg` and `argus-app` deploy
  `dep-d8lj8cjtqb8s738jf28g` both reached `live`; warmup passed in
  `real-workflow` mode; the authenticated canary conversation
  `d2fba747-bb93-45be-a48d-0fc944982423` completed durable job
  `93c89ccf-fb88-4ae2-ba93-4e0ab7b821c6` with run
  `e654ed96-efc0-44d6-86fe-033383c2d625`; and a deployed browser shell smoke
  rendered the unauthenticated front door without new console errors after
  reload.
- `docs/LAUNCH_GATE_FINAL_CLOSURE_PLAN.md` is marked historical.

## Remaining High-Leverage Work

Codex should own or closely supervise this:

1. **Research Lab product spec**
   - Perplexity, citations, research-to-testable-hypothesis loops, inbox briefs,
     saved research, and monitoring belong in a dedicated spec before code.
   - The active refined draft is
     `docs/specs/evidence-aware-idea-loop.md`. It supersedes the narrower
     "research first" framing by defining direct test, education, light
     evidence, deep research, and monitoring lanes.
   - This branch may refine that spec, but it must not implement the
     evidence-aware idea loop without explicit approval.

## Low-Risk Work Suitable For External Async Agents

External async agent `Jules` may work on these only within focused
`jules/**` branches:

- Docs classification proposals: canon, active plan, historical evidence,
  archive candidate.
- Dead-code candidate inventories outside `archive-v0.1/`.
- Large-file inventory with proposed extraction seams, without performing broad
  refactors.
- Small test coverage additions around already-stable behavior.
- i18n/key consistency reports and narrow copy fixes.

External agents must not touch:

- Supabase migrations, RLS, auth, or service-role behavior.
- Render config, deploy scripts, workflow env sync, or production env names.
- `src/argus/agent_runtime/stages/interpret.py` or runtime routing without
  explicit approval.
- LLM provider plumbing, OpenRouter profiles, Perplexity integrations, or model
  fallback chains.
- Backtest engine execution semantics.
- Frontend state that invents backend facts.

## Documentation Hygiene Backlog

The next docs pass should classify existing docs into:

- **Canon**: `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
  `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`,
  `.agent/designs/argus/DESIGN.md`, and `AGENTS.md`.
- **Active specs**: current milestone docs, including this file and approved
  future specs.
- **Historical evidence**: completed launch/milestone closure reports and
  browser/canary evidence.
- **Archive candidates**: stale plans superseded by merged implementation or
  newer specs.

Do not delete historical docs casually. Prefer adding a short status banner that
points to the active source of truth, then archive only after review.

## Verification Expectations

For docs-only changes:

- `git diff --check`
- link/path sanity check for referenced docs

For frontend changes:

- focused `bun test` suites for touched behavior
- `cd web && bun run build`
- browser QA in the Codex browser for visible behavior

For backend/runtime changes:

- focused pytest suite for touched behavior
- `poetry run ruff check src tests workflows scripts`
- local or live smoke only when the change affects runtime/deploy behavior

## Stop Conditions

Stop and ask before proceeding if a task:

- requires new Supabase schema, RLS, or production data writes;
- changes runtime routing or result readout provenance;
- changes Render service topology, env var names, or deploy behavior;
- starts implementing Perplexity Research Lab features;
- needs a product decision about public sharing, privacy, or revocation.
