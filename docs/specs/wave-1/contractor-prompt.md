# Wave 1 contractor prompt

Start every contractor session with one line:

> Implement package `<ID>` following `docs/specs/wave-1/contractor-prompt.md`.

One session builds one package and opens one PR. Packages merge one at a time,
in the order below. Stage 1 starts only after every stage 0 package is merged
and reviewed (see `README.md`, stage unlock rule).

## Package queue

Contractor packages only. Packages marked internal in the specs are done by the
Argus team and are not in this list.

| Stage | Order | Package | Spec file |
| --- | --- | --- | --- |
| 0 | 1 | 0B-2 | `01-stage-0-safety-and-analytics.md` |
| 0 | 2 | 0B-1 | `01-stage-0-safety-and-analytics.md` |
| 0 | 3 | 0C-1 | `01-stage-0-safety-and-analytics.md` |
| 0 | 4 | 0C-2 | `01-stage-0-safety-and-analytics.md` |
| 0 | 5 | 0C-9 | `01-stage-0-safety-and-analytics.md` |
| 0 | 6 | 0C-3 | `01-stage-0-safety-and-analytics.md` |
| 0 | 7 | 0C-4 | `01-stage-0-safety-and-analytics.md` |
| 0 | 8 | 0C-5 | `01-stage-0-safety-and-analytics.md` |
| 0 | 9 | 0C-8 | `01-stage-0-safety-and-analytics.md` |
| 0 | 10 | 0C-7 | `01-stage-0-safety-and-analytics.md` |
| 1 | 1 | 1C-1 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 2 | 1F-1 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 3 | 1C-2 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 4 | 1C-4 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 5 | 1A-1 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 6 | 1A-2 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 7 | 1B-1 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 8 | 1B-3 | `02-stage-1-layout-ai-landing-card-payoff.md` |
| 1 | 9 | 1B-2 | `02-stage-1-layout-ai-landing-card-payoff.md` |

Packages whose "Depends on" line is already satisfied may be built in parallel
sessions. They still merge in this order. A branch that is already published
(pushed, PR open, or has screenshots or eval evidence) is never rebased: bring
in the new tip by merging `origin/codex/private-alpha-next` into it (AGENTS.md,
reconciliation rules).

## Instructions for the session

You are implementing ONE package of Argus wave 1: the package named in your
first line, defined in the spec file listed for it above.

Read first, in this order: `docs/specs/wave-1/README.md`,
`docs/specs/wave-1/00-shared-rules.md`, then your package section and the
product text it references. The spec is the source of truth. Where code and
spec disagree, follow the spec's "Clashes resolved" table. If something is
still unclear, stop and say so in the PR. Do not guess.

1. Branch from `origin/codex/private-alpha-next` after a fresh fetch, and record
   that SHA as your integration base in the PR. Name the
   branch `<type>/<package-id>-<short-name>`, for example
   `fix/0B-2-cap-copy`. Never push to `codex/private-alpha-next`; it is
   protected and only accepts PRs.
2. Build only this package. Touch only the files it lists. Reuse what the
   reuse map (RM entries) points to instead of writing new versions.
3. Follow-up questions and missing-input questions must keep working
   (rule E8). Their existing tests must stay green.
4. Write the named tests from the package's "done when". Run the backend and
   web checks locally before opening the PR.
5. Before opening the PR, fetch again. If integration moved, merge (or, only
   if nothing is pushed yet, rebase) the latest `origin/codex/private-alpha-next`
   into your branch. Once the branch is pushed, never rebase or force-push it;
   reconcile by merging the tip. In the PR, record the original base and the
   current integration SHA, and name any overlap with what merged in between
   (shared runtime owner, API or data contract, UI state, migration, env var,
   affected tests), not just Git conflicts.
6. Open ONE PR into `codex/private-alpha-next` with these headings: TL;DR,
   Motivation (link the spec package and issue), Changes, Out of scope,
   Testing (es-419 and EN screenshots for anything visible), Risks/Rollback,
   Docs affected, Status. Add a type label and a priority label
   (`low-priority`, `med-priority` or `high-priority`).
7. Stop. Do not merge. Do not start the next package.
8. If resumed with review comments: reply to every review thread with
   "Fixed in <sha>", "Won't fix: <reason>" or "Deferred to #<issue>", then
   resolve it.

## Environment

- Local worktree: run `bash .github/setup-worktree-env.sh`, then
  `bash .github/setup-worktree-env.sh --check "$PWD"`. Stop if it reports
  `missing` or `conflicting-link`, and fix the link before running tests or
  services. Then run `bash .github/setup.sh`.
- Cloud session: setup script `bash .github/setup.sh`. Use dev-safe variables
  only: mock auth (`ARGUS_MOCK_AUTH`, `NEXT_PUBLIC_MOCK_AUTH`), in-memory
  persistence (`ARGUS_PERSISTENCE_MODE`), and a capped dev OpenRouter key if a
  task needs real chat. Never production keys, the Supabase service-role key,
  the ops token, or the Render key (rule E5).
