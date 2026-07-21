# Issue #247 — Allowance Truth Evidence

Implementation lane: `codex/issue-247-allowance-truth`.
Base: PR #259 head `9752825c` merged with integration `7d92fb40`
(`origin/codex/private-alpha-next`) at `8899dc7c`.

This report records the local implementation and verification evidence for
the truthful Usage limits and allowance accounting slice. Live production-
parity browser QA status is recorded in the final section; deterministic
green alone is not completion.

## Current-state impact map (before this lane)

- Chat messages were charged at route entry in `chat_stream`
  (`check_and_increment_usage_limits` before conversation lookup and runtime
  work), so an Argus infrastructure failure consumed a message unit and both
  windows were charged whether or not any durable terminal response existed.
- Direct `POST /backtests/run` charged `backtest_runs` between the provider
  preflight and execution through Python count-then-increment under a
  process-local `threading.Lock`; replay was an in-process dictionary; no
  durable job existed on that path.
- Chat-launched simulations charged nothing: the shadow-job path applied
  count-then-insert concurrency backpressure only, and on backpressure it
  silently skipped the durable job and executed in-process anyway.
- `GET /me/usage` returned the daily messages window only and deliberately
  hid simulations.
- No `chat_turn_lifecycles` table exists (#240 open). The durable terminal
  boundary for ordinary turns is terminal assistant persistence through the
  serialized `append_conversation_message` function
  (`20260717000001_serialize_conversation_message_append.sql`).
- No atomic admission function existed (#230 open); `create_backtest_job`
  resolved idempotency by select-then-insert.
- Quota limits were duplicated as inline literals at every call site.

## Implemented boundaries

### Message accounting (settle at durable terminal outcome)

- Route entry performs a non-consuming hour+day check
  (`argus.api.chat.allowance.check_message_allowance`) and still returns 429
  when a window is exhausted. Run actions skip the message check.
- Exactly one message unit settles atomically with the first durable insert
  of the turn's terminal product message through
  `public.append_conversation_message_settling_usage`
  (`20260722000001_settle_message_allowance.sql`): it delegates to the
  serialized append boundary and, only when the append durably inserted a
  new row (not a replay), upserts the hour and day `usage_counters` rows in
  the same transaction.
- Settlement call sites: the main runtime terminal persist, the two
  onboarding clarification/follow-up persists, and the cancel-confirmation
  acknowledgment. Failure-guard persists (`agent_runtime_turn.status =
  "failed"`), the missing-confirmation-checkpoint recovery persist, and
  suppressed late artifacts settle nothing.
- `chat.run_backtest` turns settle no message unit; their allowance is the
  simulation charge at durable admission.
- Memory mode mirrors settlement through `AlphaStore.usage_counters`.

### Simulation accounting (charge at unique durable admission)

- `public.admit_backtest_job`
  (`20260722000002_atomic_backtest_admission.sql`) resolves, under one
  advisory transaction lock, in the approved order: exact replay or identity
  collision; hour and day allowance exhaustion; per-user capacity; global
  capacity; then inserts the durable job and charges both windows in the
  same transaction. Limits arrive as required parameters from the one
  backend policy module (`argus.domain.usage_limits`).
- Chat run actions route through the same operation
  (`argus.api.chat.backtest_admission_flow`); an unadmitted run returns a
  typed rejection envelope (`simulation_allowance_exhausted`,
  `backtest_capacity_exceeded`, `idempotency_conflict`) through the existing
  execute-stage failure contract instead of executing for free.
- Direct `POST /backtests/run` resolves an existing reservation before
  quota, preflight, or compute; keeps the contractual non-consuming
  allowance precheck ahead of the provider preflight (coverage rejection
  still consumes zero); admits as `running` after preflight; finishes as a
  durable terminal job on success and failure; and replays return prior
  durable truth (`200` run, `409 idempotency_in_progress`, or the terminal
  failure) without charging. The in-process idempotency dictionary is no
  longer used in durable mode.
- `argus.domain.backtest_admission` provides the approved #229 canonical
  identity serializer, key validation, direct-payload materialization, and a
  deterministic in-process twin for memory mode.

### Read contract

- `GET /me/usage` returns, for `messages` and `backtests`, both active UTC
  windows (`limit`, `used`, `remaining`, exact `period_end`) plus
  backend-derived `available_now` and `limiting_window` (smaller remaining;
  `day` on ties). Missing rows read zero without creating counters. `used`
  may truthfully exceed `limit` after concurrent settlements; `remaining`
  clamps at zero. Documented in `docs/API_CONTRACT.md` and
  `docs/api/openapi.yaml`.

### Settings → Usage UI

- The Usage panel renders messages and simulations from the backend response
  only: the daily window is the primary story per card, and the hourly
  window appears exactly when the backend marks it limiting. States:
  loading, error+retry, zero, active, hourly-limited, daily-exhausted.
  EN and es-419 localized, including what consumes each allowance. Focus
  trap, Escape, focus restoration, flat styling, and 44px controls
  preserved. No quota constant or reset computation exists in the frontend.

## Donor extraction ledger

| Donor surface | Decision | Current-base evidence | Reason |
| --- | --- | --- | --- |
| `84fc0d6` migration `admit_backtest_job` | Adapt | select-then-insert in `create_backtest_job`; no durable direct-path job | Extended to check and charge hour+day windows; UTC pinned; limits required parameters (no literals in SQL) |
| `84fc0d6` `backtest_admission.py` | Adapt | no counterpart on base | Memory-twin allowance rewired to shared `usage_counters` twin |
| `84fc0d6` direct-route rework | Adapt with reorder | direct replay was process-local; charge preceded durable state | Donor admitted before preflight, which would have made coverage rejection consume a unit; reordered to reservation pre-read → precheck → preflight → admission |
| `84fc0d6` chat flow | Adapt with fix | chat charged nothing; backpressure silently bypassed durable jobs | Donor collapsed rejections to `None`, which fell through to free in-process execution; replaced with typed rejection envelopes |
| `a7238b1` `/me/usage` + reader | Reject shape, reuse patterns | daily-messages-only on base | #247 requires two windows plus `available_now`/`limiting_window`; donor was daily-only |
| `a7238b1` UI/i18n/e2e | Extend in place | #259 material already merged on this branch | Extended to two resources and two windows |
| `29cc1e9` OpenAPI structural gate | Reject | #234 is its own lane | #247 needs only checked-artifact consistency for the touched surface |
| Audit-branch #240 lifecycle train | Reject | `chat_turn_lifecycles` absent on base | Settlement attaches to the existing serialized append boundary; the full lifecycle remains #240 |

## Red-before-fix evidence

`tests/test_allowance_accounting.py` on the untouched base
(commit `74482ed`): 11 failed in 3.95s — entry charge existed, no
settlement seam, no atomic admission (`admit_backtest_job` absent), legacy
increment on the direct route, `/me/usage` daily-messages-only.

Pre-existing baseline finding: `tests/test_modularity_budget.py` was
already red on the untouched branch head because `web/lib/argus-api.ts`
exceeded its budget by 9 lines after the #259 merge; fixed by moving the
usage types onto `web/lib/usage-allowance.ts` (`b31723e`).

## Deterministic verification (exact counts)

All backend runs hermetic: provider keys blanked,
`ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`, Python 3.10.20
(pinned runtime).

| Gate | Result |
| --- | --- |
| Focused backend set (alpha API, gateway, jobs, finalization, admission, artifacts, allowance, chat stream, import boundary) | 296 passed |
| Hermetic agent-runtime sweep + spine guardrails | 1129 passed |
| Mocked eval harness + i18n coverage + localization | 43 passed |
| Disposable-Postgres proofs (`tests/test_allowance_accounting_postgres.py`) | 11 passed, three consecutive runs (skip cleanly without the gate URL) |
| Full backend suite `tests/` at the final candidate | 2276 passed, 1 failed (pre-existing), 2 skipped, 38.19s |
| Ruff check (`src`, `tests`) | clean |
| Frontend unit suite (`bun test __tests__/`) | 421 passed |
| Frontend lint (`eslint`) | clean |
| Frontend production build (`next build`) | success |
| Playwright usage journeys (mock-auth, Chromium) | 4 passed |
| `git diff --check` | clean |

The one full-suite failure,
`tests/test_backtest_state_machine.py::test_text_approval_uses_llm_turn_act_but_defers_to_card_action`,
is pre-existing at the untouched branch head: `git diff 8899dc7..HEAD`
contains no file on its execution path (the test file, `agent_runtime/`,
and every interpret-stage domain import are byte-identical), and the lane's
clean-checkout baseline is known to carry pre-existing full-suite failures
outside CI's fixed file list. It is not normalized into this lane.

## Disposable-Postgres and ownership evidence

Container: `public.ecr.aws/supabase/postgres:17.6.1.140` (fresh, disposable,
port 54999; the founder's `supabase_db_argus-qa` stack untouched). All 17
`supabase/migrations` files applied in order with `ON_ERROR_STOP`, zero
errors. Proofs (11 passed):

- settlement charges hour and day exactly once with exact UTC period
  boundaries, replays zero, and rolls back atomically with its message;
- ten barriered concurrent settlements of distinct turns count exactly ten;
- ten barriered same-identity admissions admit once, charge one unit, and
  replay nine times with one durable job;
- ten barriered distinct-identity admissions admit exactly the queued
  capacity (2) and reject the rest with zero extra charge;
- same key with a different identity conflicts without disclosure or
  mutation;
- hourly and daily exhaustion reject before any charge or insert;
- a post-admission failure keeps exactly one unit and its replay returns
  the durable failed job without charging;
- a stale running direct job reconciles to a retryable
  `direct_execution_abandoned` failure on the next admission;
- reservations and counters are owner-isolated across users sharing a key;
- both functions are executable by `service_role` only.

## Complexity reassessment

- Added: two forward migrations (one settling wrapper, one admission
  function), one policy module extension, one small chat allowance helper,
  the admission domain module with its memory twin, the gateway adapter,
  and the chat admission flow. Each maps to a locked contract requirement
  (atomic charge boundaries, one policy source, typed rejection).
- Removed/avoided: the process-local direct-route idempotency map (durable
  mode), the count-then-insert chat backpressure bypass, duplicated limit
  literals across routers, and the donor's full #234 OpenAPI gate and #240
  lifecycle train (out of lane).
- Deliberately not built: billing/entitlement machinery, frontend quota
  logic, background sweepers, GET-path stale reconciliation
  (`GET /backtest-jobs/{id}` reconcile remains #230/#231 follow-up; it
  affects staleness visibility, not accounting truth), and quota-specific
  runtime recovery copy (typed codes flow through the existing recovery
  contract; copy polish is a follow-up).

## Remaining risks and rollback boundary

- Chat capacity rejection now surfaces as a typed recoverable failure
  instead of silently executing in-process; the recovery prose is the
  existing generic typed copy, not quota-specific wording.
- Message settlement can overshoot a window by the number of concurrently
  in-flight turns admitted before exhaustion (entry check is non-consuming
  by design); `remaining` clamps at zero and the read surface reports
  truthful `used`.
- Rollback: revert commits per surface — UI (`a052bf5`), read contract
  (`24ee78c`), admission (`5cb80ce`), settlement (`1add789`) — each is
  independently revertible; the migrations are forward-only and preserve
  historical counters and job evidence (reverting callers restores prior
  paths without dropping rows).

## Acceptance matrix (issue #247 checkboxes)

| # | Acceptance item | Status |
| --- | --- | --- |
| 1 | Hourly and daily `limit`/`used`/`remaining`/exact `period_end` for messages and simulations | PASS — `tests/test_allowance_accounting.py` window tests; PG proof of exact UTC bounds |
| 2 | Backend-derived `available_now` and limiting-window truth; frontend never computes quota truth | PASS — router derivation tests; frontend source pins reject quota constants and reset math |
| 3 | Normal answers, clarifications, supported/unsupported responses consume one unit at durable terminal completion | PASS — settlement seam tests; PG same-transaction proof (live-browser confirmation pending) |
| 4 | Malformed, unauthenticated, abandoned, duplicate-replay, infrastructure-failed turns consume zero | PASS — FastAPI validation/auth reject pre-handler; runtime-failure zero test; replay-zero PG proof; abandoned turns never reach the settling append (generator cancellation precedes terminal persistence) |
| 5 | Committed terminal response + transport disconnect = exactly one unit | PASS (structural) — the charge commits with the terminal message transaction, independent of delivery; disconnect drill remains for live QA |
| 6 | First unique durable admission = one unit | PASS — PG proof |
| 7 | Ten concurrent same-identity requests = one admission, one unit | PASS — barriered PG proof (1 admitted + 9 replay) |
| 8 | Exact replays return durable prior truth, zero additional units | PASS — PG proofs for running/succeeded/failed replay semantics |
| 9 | Pre-admission rejection including #251 preflight = zero | PASS — coverage-rejection and quota-precheck tests unchanged and green; admission runs after preflight |
| 10 | Post-admission execution/finalization failure = one unit + truthful durable terminal job | PASS — PG proof + direct-route failure finalization tests |
| 11 | Direct and chat/workflow launches share the rule | PASS — both routes call the same `admit_backtest_job`; chat rejection envelopes prevent free execution |
| 12 | Settings → Usage enabled, Security preserved, daily-primary + contextual hourly, EN and es-419 | PASS deterministically — unit + Playwright journeys; alpha-frontend pins prove the Security route untouched (live browser pass pending) |
| 13 | Zero, available, hourly-limited, daily-exhausted, loading, unavailable, reload, keyboard, focus, desktop, mobile states | PASS deterministically — unit + Playwright (zero, hourly-limited, exhausted EN/ES, focus trap); live matrix pending |
| 14 | Owner isolation and missing-counter behavior on real Postgres | PASS — PG owner-isolation and zero-state proofs; service-role-only function grants |
| 15 | Production-parity local browser QA with real auth proving before/after counters | BLOCKED — worktree-local QA configuration absent (root `.env`); see below |
| 16 | Focused API, migration, concurrency, lifecycle, workflow, frontend, OpenAPI, hermetic gates | PASS — table above |
| 17 | Final diff proportionality: no billing machinery, duplicate counters, frontend quota logic, unrelated refactors | PASS — complexity reassessment above |

## Live product QA — completed on the isolated local Supabase stack

Executed 2026-07-21 after founder-authorized configuration. Hosted
Supabase was never mutated; the connected cloud database predates the
required migration chain (PGRST202 on the serialized append function), so
the functional matrix ran against the local `argus-qa` Docker stack
(Kong 54331 / Postgres 54332), brought forward with the repo migration
flow (`supabase migration up --local`: exactly `20260722000001` and
`20260722000002` applied; history was a clean prefix). Runtime-only env
overrides isolated both processes to the local stack; the symlinked
integration env files were untouched. The QA identity was a fresh normal
local user (`is_admin = false`) created through real local Supabase Auth
signup (allowlist row seeded locally).

Functional matrix results (sanitized; counters verified in the UI, the
`/me/usage` response, and the local database):

1. Initial truth: zero state read from zero rows; UI matched the server
   JSON exactly (hour end 21:00Z → 4:00 PM CDT, day end 00:00Z → 7:00 PM
   CDT; `available_now` true; `limiting_window` "hour").
2. One completed chat response settled exactly one unit in both windows
   (hour 0→1, day 0→1) and persisted across reload.
3. Injected pre-terminal runtime failure (test-only
   `ARGUS_RUNTIME_EVENT_TIMEOUT_SECONDS` on the local process) rendered
   the honest recovery message and consumed zero (counters unchanged).
4. The persisted Retry completed and settled one unit for the one
   delivered outcome (no double charge across the failed attempt).
5. Simulation admission (durable-jobs flag on): one run action charged
   hour 0→1 and day 0→1 with one durable `chat.run_backtest` job,
   identity hash, and linked run; the run action itself consumed no
   message unit.
6. Two concurrent same-key run posts (client-derived confirmation key)
   produced one durable job, one linked run, and exactly one unit; a
   same-key different-payload probe returned the non-disclosing conflict
   with zero charge; a post-completion action replay rejected
   pre-admission (`confirmation_required`) with zero charge.
7. Provider preflight rejection (AAPL 1990) returned the honest
   boundary clarification: one message unit, zero simulations.
8. Read purity: an md5 fingerprint over all counter rows (including
   `updated_at`) was identical before and after repeated panel opens,
   closes, reloads, and disclosure toggles; the panel issues GETs only.
9. Genuine hourly exhaustion (controlled local fixture, restored to the
   organic value afterward): rose "limit reached" presentation and a
   429-at-entry send that consumed nothing. Healthy and zero states are
   neutral.
10. Security page fully reachable and rendered in EN and ES.
11. EN and es-419 rendered identical backend truth with locale-correct
    reset formatting; desktop and mobile clean.
12. No 401-after-login occurred on the local stack.

Two live findings were corrected in `ac90500` (rose hourly line at zero
usage; run actions sent random idempotency keys instead of the
confirmation identity, leaving the concurrent-retry window able to
double-admit). Environment gates recorded for rollout: production must
run with `ARGUS_BACKTEST_JOBS_SHADOW_ENABLED=true` (with the flag off,
chat runs take the legacy uncharged in-process path), and the deployed
database must carry the migration chain through `20260722000002`. In
synchronous no-dispatch mode a concurrent replay can re-execute compute
(accounting stays exactly-once; the finalizer dedupes the run identity).

## Approved presentation (Phase B, `28ccdf9`)

The Usage modal is one flat surface: per allowance, backend remaining
capacity leads ("193 left today"), a thin daily bar carries truthful
ARIA values, the reset instant renders through the existing localized
formatter, and hourly capacity is secondary text. Badges, icon tiles,
and repeated explanations were removed; one "What counts?" disclosure
owns both counting rules. Live-verified on real post-matrix counts in
EN/ES, desktop/mobile, dark/light, with zero mutations from panel
interactions. Red-before-fix evidence: the rewritten presentation pins
failed 2/8 against the prior card-based modal (badges present, bordered
tiles, no disclosure) before the implementation turned them green.

## Historical note — first hosted attempt

The original live pass was BLOCKED at READY FOR QA CONFIG. `.github/qa.sh` fails closed without a
root `.env` carrying real Supabase/OpenRouter/Alpaca credentials and
`DATABASE_URL`. This worktree has no `.env` and no `web/.env.local`, and
copying credentials from another worktree is out of bounds for this lane.
Once the founder places the approved worktree-local QA configuration, the
prepared session is: `.github/qa.sh` backend, `bun run dev` frontend with
`NEXT_PUBLIC_MOCK_AUTH=false`, founder login, then the 13-step live matrix
(usage panel before/after one completed chat turn, one clarification, one
injected pre-terminal failure, one admission, one replay, one preflight
rejection, reload persistence, EN/ES, desktop/mobile, UTC reset
verification). Hourly-limited and daily-exhausted live states use an
isolated stack only; the disposable proof container recipe is
`docker run -d --rm -p 54999:5432 -e POSTGRES_PASSWORD=… supabase/postgres
17.6.1.140` plus the migration chain.
