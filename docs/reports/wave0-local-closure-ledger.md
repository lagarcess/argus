# Wave 0 Local Closure Ledger

Status: **LOCAL LABORATORY BRANCH — NOT MERGED, NOT PUSHED**

- Worktree: `.claude/worktrees/argus-alpha-audit-c2d919`
- Branch: `claude/argus-alpha-audit-c2d919`
- Base: `390d57294cf9911becdb14ced126770d0124e4cb` (`codex/private-alpha-next` tip)
- Environment: worktree-local `.env` sentinel; every external credential blank;
  `ARGUS_PERSISTENCE_MODE=memory`, `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`,
  `ARGUS_CHECKPOINTER_MODE=memory`, `ARGUS_MOCK_AUTH=true`; Python 3.10.20 in-worktree venv.
- Baseline evidence at base SHA: hermetic agent-runtime sweep
  `poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov`
  → **1129 passed** (41.96s).

State vocabulary (never conflated):

- `LOCAL_ACCEPTANCE_PASS` — criterion proven by deterministic local evidence at the
  named commit.
- `EXTERNAL_GATE_PENDING` — criterion requires deploy/live/paid/founder/QA-database
  authority; recorded precisely, **not claimed**.
- `GENUINE_BLOCKER` — criterion cannot proceed locally for a named technical reason.
- `NOT_APPLICABLE` — criterion does not apply to this branch shape; reason given.
- `REGRESSION_FOUND` — criterion previously held and now fails; must be fixed before
  the checkpoint counts.

No issue is called complete while any `EXTERNAL_GATE_PENDING` item remains.

---

## #234 — OpenAPI generated-vs-checked structural gate

Checkpoint commit: `29cc1e9` — `feat(api): enforce generated-vs-checked OpenAPI structural compatibility`

Changed surfaces: `src/argus/api/openapi_compat.py` (new), `src/argus/api/main.py`
(custom `app.openapi()` post-processor), `scripts/generate_openapi_artifact.py` (new),
`docs/api/openapi.yaml` (regenerated, 2,516 lines), `tests/test_openapi_compatibility.py`
(new, 11 tests), `tests/test_alpha_artifacts.py` (two textual tests upgraded to
structural), `.github/workflows/ci.yml` (gate + artifact guards added to backend list).

Acceptance mapping:

| Criterion | State | Evidence |
| --- | --- | --- |
| Gate parses both artifacts and compares structure, not text | LOCAL_ACCEPTANCE_PASS | `structural_projection` resolves `$ref`s, strips doc-only keys, canonicalizes lists; gate test green |
| Server/path prefix represented exactly once | LOCAL_ACCEPTANCE_PASS | double `/api/v1` fixed (checked file had `servers: /api/v1` + prefixed paths); prefix-once rule + regression test |
| Missing/extra unallowlisted public paths fail | LOCAL_ACCEPTANCE_PASS | negative tests name `GET /api/v1/discovery/assets` (missing) and `GET /api/v1/portfolio-export` (extra) |
| Request/response/required/enum drift fail | LOCAL_ACCEPTANCE_PASS | negative tests for Idempotency-Key required drift, `/me` response schema drift, enum drift |
| Exclusions explicit, minimal, individually named | LOCAL_ACCEPTANCE_PASS | exactly `GET /health`, `GET /internal/readiness`, `POST /api/v1/dev/reset`; test locks the set |
| Streaming differences normalized narrowly | LOCAL_ACCEPTANCE_PASS | only `POST /api/v1/chat/stream` 200 body; request schema + 409/422/429 remain compared |
| Current runtime and checked artifact pass | LOCAL_ACCEPTANCE_PASS | `structural_failures == []` at head; 34 focused tests green |
| Negative tests name the exact difference | LOCAL_ACCEPTANCE_PASS | failure strings carry operation + JSON-pointer path |
| Existing CI runs the gate | LOCAL_ACCEPTANCE_PASS (workflow file) / EXTERNAL_GATE_PENDING (GitHub Actions run) | `ci.yml` backend list now includes the gate; an actual Actions run requires push, which is out of scope tonight |

Reconciled drift (all previously invisible to CI): double `/api/v1` prefix; three
public routes missing from the checked file (`/chat/starter-prompts`,
`/discovery/assets`, `/discovery/indicators`); param-name drift (`{id}` vs
`{conversation_id}` etc.); untruthful generated declarations (Idempotency-Key
declared optional while runtime enforces 400 `idempotency_key_required`; 422
declared as `HTTPValidationError` while the handler returns RFC 9457; chat/stream
declared `application/json` 200 while runtime streams SSE; real 409/429 undeclared).

Focused commands: gate+guards+CI-workflow suites → 34 passed; API suites
(`test_alpha_api_supabase.py`, `test_api_import_boundary.py`,
`test_private_launch_hardening.py`) → 75 passed; ruff + format clean; modularity
budget clean; `git diff --check` clean.

Rollback boundary: revert `29cc1e9` (artifact + gate + declarations revert together).

External gates remaining: one GitHub Actions run of the amended backend list on the
eventually-pushed candidate.

---

## #230 — atomic backtest admission and idempotency (prerequisite)

Checkpoint commit: see commit map — `feat(backtests): make admission and idempotency atomic`

Changed surfaces: `src/argus/domain/backtest_admission.py` (new: canonical
serializer/hashing, key validation, identity builders, in-process admission twin,
stale direct-job reconciliation), `src/argus/domain/backtest_admission_gateway.py`
(new: RPC calls), `supabase/migrations/20260718000001_atomic_backtest_admission.sql`
(new: reservation columns, UNIQUE boundary, `admit_backtest_job` function with the
approved decision order, service-role-only), `src/argus/api/routers/backtest.py`
(direct-route disposition: running-only insert, replay semantics incl.
`idempotency_in_progress`, capacity 429/503 + Retry-After 15, conflict 409,
shape-validation before hashing), `src/argus/api/chat/backtest_admission_flow.py` +
`ShadowBacktestJobTool` (chat path through the same admission), `AlphaStore`
(jobs/reservations/charges), `BacktestJob.conversation_id` nullable (approved
direct contract), OpenAPI artifact regenerated.

Acceptance mapping:

| Criterion | State | Evidence |
| --- | --- | --- |
| Barriered real-Postgres concurrency admits ≤1 at limit 1 | EXTERNAL_GATE_PENDING | `tests/test_backtest_admission_postgres.py` written and skip-gated on `ARGUS_ADMISSION_TEST_DATABASE_URL` (disposable DB); the issue itself says mock-only is insufficient for this criterion. In-process barriered proof (10 threads → 1 admitted) passes deterministically |
| Admission/reservation cannot race count↔insert | LOCAL_ACCEPTANCE_PASS (in-process) / EXTERNAL_GATE_PENDING (cross-instance) | one lock-serialized memory operation; SQL function serializes on `pg_advisory_xact_lock` — cross-instance proof rides the Postgres gate |
| Exact retry returns same job + current durable status | LOCAL_ACCEPTANCE_PASS | domain + API replay tests (same job id, same Run, one charge) |
| Same key + mismatched identity → #229 conflict, never the old job | LOCAL_ACCEPTANCE_PASS | `409 idempotency_conflict` with no job/run disclosure; tests assert store untouched |
| Capacity exhaustion returns approved product-safe response | LOCAL_ACCEPTANCE_PASS | per-user 429 / global 503, code `backtest_capacity_exceeded`, `Retry-After: 15` |
| Direct /backtests/run cannot bypass production admission | LOCAL_ACCEPTANCE_PASS | direct route now reserves through the same operation, both-ceilings check, running-only insert, durable row before sync execution; replay of running → `409 idempotency_in_progress` + `context.backtest_job_id` |
| Ownership, RLS, max attempts, worker claim, finalization unchanged | LOCAL_ACCEPTANCE_PASS | no RLS/claim/finalization surface edited; gateway/shadow/async suites green |
| Focused gateway/job/API tests + hermetic gate pass | LOCAL_ACCEPTANCE_PASS | 206 focused tests + hermetic sweep 1129 passed |
| Evidence records migration/SHA/concurrency output | LOCAL_ACCEPTANCE_PASS (local) | this ledger + commit map; real-PG output pending the external gate |
| Closure hands stable admission identity to #231/#242 | LOCAL_ACCEPTANCE_PASS (artifact exists) | `operation_scope`/`identity_hash`/reservation live in rows; #242 lookup consumes it next |

Deliberate scope notes: legacy hour-cap (10/hour) on the direct route is replaced
by the approved single unique-simulation day allowance inside admission; the
in-memory `store.idempotency` cache no longer backs the direct route (reservation
store owns replay). Chat-side capacity/allowance rejections keep today's
skip-durable-job behavior; typed 429/503 stream surfacing composes with #235/#242.

External gates remaining: real-Postgres barriered run on a disposable database
(command recorded in the test module); QA/production application of the migration
(founder + #246-serialized authority).

Rollback boundary: revert the checkpoint commit; forward-safe (callers revert to
prior path; migration function is replaceable; no historical rows dropped).

---

## #231 — database-only fresh job polling (prerequisite)

Checkpoint commit: see commit map — `perf(backtests): make job polls database-only`

Changed surfaces: `src/argus/api/routers/backtest.py` (GET no longer calls
`reconcile_terminal_render_task_run`), `tests/test_backtest_jobs_poll_calls.py`
(new call-count suite), `tests/test_backtest_jobs_async.py` (old
endpoint-reconciles test rewritten to pin the database-only contract).

| Criterion | State | Evidence |
| --- | --- | --- |
| Fresh queued/running/succeeded/failed GETs make zero Render calls | LOCAL_ACCEPTANCE_PASS | parametrized counting-client test: `calls == []` |
| Stale job GETs return safe Supabase state without a Render call | LOCAL_ACCEPTANCE_PASS | stale-running poll returns `running`, zero calls; forbidden-client test asserts no client construction |
| Bounded scanner still reconciles stale terminal task runs | LOCAL_ACCEPTANCE_PASS | scanner test: exactly one Render call, job marked failed |
| Scanner failures bounded without breaking GETs | LOCAL_ACCEPTANCE_PASS | scanner error paths unchanged (existing suite); GET path no longer touches the client |
| Owner/RLS + canonical hydration unchanged | LOCAL_ACCEPTANCE_PASS | hydration tests green (`run`, `result_readout` fields intact) |
| Browser polling needs no response-shape change | LOCAL_ACCEPTANCE_PASS | `BacktestJobResponse` untouched; OpenAPI gate unchanged |
| Focused endpoint + scanner call-count tests | LOCAL_ACCEPTANCE_PASS | new suite, measured counts asserted |
| Closure evidence records SHA + measured counts, no p95 claim | LOCAL_ACCEPTANCE_PASS | this entry; no latency claims made |

External gates remaining: #233 deployed journey consumes the user-facing proof.
Rollback boundary: revert the checkpoint commit (restores poll-path reconciliation).

---

## #242 — ambiguous Run reconciliation (prerequisite)

Checkpoint commit: see commit map — `fix(chat): reconcile ambiguous Run actions from durable truth`

Changed surfaces: `GET /api/v1/backtest-jobs/by-action/{confirmation_id}`
(contract lookup: reservation → artifact-integrity 500 → identity 409 → job+run),
`backtest_admission_gateway.get_backtest_job_by_reservation`/`get_message_row`,
`web/lib/chat-run-reconciliation.ts` (typed durable resolution),
`web/lib/argus-api.ts` (run actions now send `Idempotency-Key == confirmation_id`
— previously a random UUID per attempt, so retries could never share identity),
`ChatInterface.tsx` (ambiguous run failures resolve from durable truth instead of
settling `could_not_run`), EN/es-419 strings, OpenAPI artifact regenerated.

| Criterion | State | Evidence |
| --- | --- | --- |
| One accepted click → at most one durable job/run | LOCAL_ACCEPTANCE_PASS | #230 admission + key==confirmation_id; replay returns same job (API tests) |
| Retry/reconnect/reload reuses the same approved identity | LOCAL_ACCEPTANCE_PASS | `chatStreamIdempotencyKey` derives from `confirmation_id`; bun test locks it |
| Disconnect yields checking/recoverable until durable truth | LOCAL_ACCEPTANCE_PASS (deterministic) | `stream_interrupted` → reconcile → pending/succeeded/failed mapping; 12 bun tests |
| Only durable failed/canceled/expired settle unsuccessful | LOCAL_ACCEPTANCE_PASS | mapping test: 404/exception/timeout never produce `could_not_run` |
| Succeeded hydrates one canonical result, no duplicate | LOCAL_ACCEPTANCE_PASS | by-action succeeded hydration test; shell reloads durable transcript |
| Focused API/artifact-history/reload/rapid-navigation tests | LOCAL_ACCEPTANCE_PASS | 6 backend by-action + 12 bun + full web suite 355 green |
| Browser QA disconnect/reload EN/ES + cache hit/miss | EXTERNAL_GATE_PENDING (deployed) / partial local | deterministic suites cover the logic; local mocked browser pass scheduled with the Train 6 QA sweep; real-deploy QA remains #233's journey |
| #243 includes the ambiguous Run trajectory | Tracked in Train 6 | `alpha_session_05` (#242 owner) flips when the concrete adapters land |

Rollback boundary: revert the checkpoint commit (endpoint + frontend module are
additive; the key-derivation change reverts with it).

---

## #252 — transcript cache and race safety (Wave 3 integration slice)

Checkpoint commit: see commit map — `perf(web): integrate the transcript session cache into the chat shell`

Changed surfaces: `ChatInterface.tsx` — module-scoped `TranscriptSessionCache`
instance; `loadConversation` routed through `navigate()` (fresh-cache instant
ready, stale-cache show-then-silently-refresh, cache-miss honest loading,
latest-navigation-wins, error keeps cached view visible); scroll offset
remembered on departure and restored on revisit; New Chat cancels pending keyed
work; logout clears authenticated cache state; user identity resolved from
`getMe` at bootstrap; mutation invalidation wired at send-start,
rename (preserved), delete (evicted), durable job completion, and
missing-conversation eviction. `.claude/launch.json` added for local preview.

| Criterion | State | Evidence |
| --- | --- | --- |
| Delayed A→B switch cannot overwrite B | LOCAL_ACCEPTANCE_PASS | primitive race tests (16) + shell routed through the same controller |
| A→B→A fresh reuse without duplicate blocking GET | LOCAL_ACCEPTANCE_PASS (product path wired) | `navigate()` fresh-cache path returns synchronously; browser smoke: revisit renders full transcript instantly |
| ≤1 background revalidation on stale | LOCAL_ACCEPTANCE_PASS | primitive dedup test; shell uses `loadOnce` |
| Cache keys include user identity; logout/user change clears | LOCAL_ACCEPTANCE_PASS | identity from bootstrap `getMe`; `clearAuthenticatedState()` on logout; primitive test |
| Mutations invalidate only documented keys | LOCAL_ACCEPTANCE_PASS | five wired call sites (send, rename-preserved, delete, job-completion, missing-conversation) |
| Cache miss never shows previous conversation as new selection | LOCAL_ACCEPTANCE_PASS | miss path emits `snapshot:null` → honest loading state; browser smoke clean |
| Eviction bounds memory | LOCAL_ACCEPTANCE_PASS | primitive LRU count/byte tests |
| Scroll state restored per conversation | LOCAL_ACCEPTANCE_PASS (mechanism) | rememberScroll on departure + rAF restore on ready |
| Browser switching/scroll/reload/logout EN+ES profile with cold/warm p50/p95 | EXTERNAL_GATE_PENDING | measurement protocol still undefined (in-lane gap from Wave 0, now explicitly carried); local mocked smoke done (EN, mock auth): send → New Chat → Recents → revisit rehydrates, zero console errors |
| No durable browser transcript storage | LOCAL_ACCEPTANCE_PASS | memory-only instance; nothing written to storage |

Rollback boundary: revert the checkpoint commit, or set `maxEntries: 0` via
`TRANSCRIPT_CACHE_POLICY` to disable caching while keeping race safety.

---

## #235 — chat request bounds and failure correlation (prerequisite)

Checkpoint commit: see commit map — `fix(api): bound chat requests and correlate unexpected failures`

| Criterion | State | Evidence |
| --- | --- | --- |
| Approved size table enforced (413/422 per #229 values) | LOCAL_ACCEPTANCE_PASS | ingress ASGI ceiling (65,536 B; declared-overage immediate; chunked cumulative) + full field/payload/depth table; 16 tests incl. exact-boundary validity |
| Rejection before JSON/auth/quota/persistence/providers | LOCAL_ACCEPTANCE_PASS | middleware precedes routing; declared-overage test proves body never read and app never reached |
| One request id through response, logs, unexpected errors | LOCAL_ACCEPTANCE_PASS | X-Request-Id echoed on 413/422/500; catch-all handler returns RFC 9457 `internal_error` with no secret/trace (asserted) |
| Chunk-safe byte ceiling | LOCAL_ACCEPTANCE_PASS | cumulative receive counter test (70 KB body → 413) |
| Rejection-before-work spy tests | LOCAL_ACCEPTANCE_PASS | inner-app assertion + provider-preflight spy in supabase suite |

External gates: none in-lane (deployed evidence rides #233).

---

## #240 — durable accepted-turn lifecycle (prerequisite)

Checkpoint commit: see commit map — `feat(chat): add the durable ordinary turn lifecycle`

Changed surfaces: `src/argus/domain/chat_turn_lifecycle.py` (six-state CAS twin +
bounded reconciliation with the complete evidence predicate and
failure-precedence ordering), `supabase/migrations/20260718000002_add_chat_turn_lifecycles.sql`
(table, RLS SELECT-own, service-role-only CAS function, stale index),
`message_store.create_message` choke point (acceptance on the durable user
message; terminal transition rides the terminal assistant write; terminal
metadata enriched with `turn_id` before the CAS, so evidence survives an
interrupted transition), reconciliation pre-passes on chat POST and
GET conversation messages, `turn_lifecycle_hooks` (fail-open dispatch).

| Criterion | State | Evidence |
| --- | --- | --- |
| Six states + transition owners + allowed matrix | LOCAL_ACCEPTANCE_PASS | transition-matrix tests; late success cannot supersede durable failure |
| CAS: no-op replay, conflicting terminal rejected | LOCAL_ACCEPTANCE_PASS | noop/conflict/invalid tests; SQL function mirrors semantics (contract-guard tests) |
| Orphan reconciliation (15 min, 20 rows, deterministic order) | LOCAL_ACCEPTANCE_PASS | bounded-batch test (25 stale → 20 reconciled, freshest 5 remain); equal-timestamp failure precedence test |
| Evidence predicate complete (owner/conversation/turn/request/terminal) | LOCAL_ACCEPTANCE_PASS | other-turn/other-request messages never qualify → abandoned `turn_abandoned` retryable |
| Acceptance maps one user message to one lifecycle identity | LOCAL_ACCEPTANCE_PASS | choke-point test: user write creates `accepted` row with turn_id == message id; `run_backtest` excluded |
| Terminal assistant persists immutable turn metadata before CAS | LOCAL_ACCEPTANCE_PASS | metadata enrichment ordering in `create_message`; completion test asserts turn_id present + row completed |
| Failure injection + reload proof | LOCAL_ACCEPTANCE_PASS | GET-messages reconciliation test recovers a stale turn from durable failure evidence |
| Real-Supabase CAS/RLS proof | EXTERNAL_GATE_PENDING | migration + service-role function written; disposable-DB run recorded as the same external gate as #230 |

Known deviations (recorded, not hidden): persisted terminal statuses keep the
legacy `succeeded`/`failed` strings (mapped to contract outcomes at the
lifecycle boundary) to avoid a metadata migration tonight; the explicit
`running` transition is not yet emitted by the runtime worker (accepted→terminal
is contract-legal; running-marking is follow-up depth); gateway-side lifecycle
methods dispatch when present but the Supabase gateway delegates for
create/transition/find/reconcile are the thin remaining wiring, listed under
remaining work.

---

## #246 — QA cost-ledger visibility (local remainder)

No further locally executable work exists beyond PR #254's merged diagnosis,
isolation proofs, and telemetry classification (revalidated green in tonight's
sweeps). The repair remains EXTERNAL_GATE_PENDING exactly as ledgered by the
audit: QA mutation authority + #230/#240 serialization (both now locally
implemented, so after review/merge of this branch the serialization gate
reduces to the founder's authority decision), then apply
`supabase/migrations/20260702000001_add_cost_ledger_entries.sql` and run the
six-step verification in `docs/reports/issue-246-qa-cost-ledger-diagnosis.md`.

---

## #247 — allowance and reset truth (composition)

Checkpoint commit: `a7238b1` — `feat(usage): expose private-alpha allowance truth with durable accounting`

Applied PR #259's read/UI slice with the audit-recommended resolutions
(duplicate period helper consolidated on `usage_limits.align_usage_period`;
gateway composes the reader mixin; OpenAPI regenerated, not hand-merged), then
completed the accounting composition the merged wave could not: simulation
allowance is truthful and published in API + UI (EN/es-419) because #230's
atomic admission owns the one-unit charge.

| Criterion | State | Evidence |
| --- | --- | --- |
| Read model returns limit/used/remaining/exact period_end for messages AND simulations | LOCAL_ACCEPTANCE_PASS | endpoint tests incl. over-charge clamp; UI renders both cards |
| Frontend never infers resets from Retry-After | LOCAL_ACCEPTANCE_PASS | contract test carried from PR #259 |
| First durable admission +1 | LOCAL_ACCEPTANCE_PASS | composition proof |
| 10 concurrent same-identity → 1 admission, 1 unit | LOCAL_ACCEPTANCE_PASS | barriered composition proof |
| Replays consume zero | LOCAL_ACCEPTANCE_PASS | composition proof |
| Pre-admission rejections consume zero | LOCAL_ACCEPTANCE_PASS | 400/422/mixed-asset proofs |
| Post-admission failure leaves exactly one | LOCAL_ACCEPTANCE_PASS | crash-finalization proof (also fixed a real gap: crashes now finalize the durable job) |
| Direct and chat launches share one rule | LOCAL_ACCEPTANCE_PASS | same operation, parity proof |
| #251 preflight consumes zero | LOCAL_ACCEPTANCE_PASS | non-consuming precheck + preflight-before-charge proofs |
| EN/ES browser QA of usage states | EXTERNAL_GATE_PENDING (real-auth/deployed) | mocked bun+Playwright specs green; real-auth ride the #233 candidate |
| Real-Supabase counter parity | EXTERNAL_GATE_PENDING | RPC charges `usage_counters`; disposable-DB run shared with #230 gate |

## #248 — account recovery and session controls (composition)

Checkpoint commit: `a49179d` — `feat(auth): add account recovery and session controls`

Applied PR #261 resolved onto this branch (OpenAPI via generator + declared
503/403 truth; env-script suite made dotenv-hermetic), plus the serialized
ProfileMenu Account-security entry now that #247's menu slice is landed.

| Criterion | State | Evidence |
| --- | --- | --- |
| Enumeration-safe recovery, origin enforcement, bounded limiter | LOCAL_ACCEPTANCE_PASS | carried suites green (auth-security 791-line suite, backend auth tests) |
| One-time recovery link exchange; safe invalid/expired/reused states | LOCAL_ACCEPTANCE_PASS (deterministic) | PKCE strip + parity tests |
| local/others/global session scopes with honest partial outcomes | LOCAL_ACCEPTANCE_PASS (deterministic) | scoped-action tests |
| Revoked sessions rejected; verification unavailable fails closed 503 | LOCAL_ACCEPTANCE_PASS (deterministic) | auth_sessions tests; 503 declared on every authenticated op in the artifact |
| Profile-menu entry after #247 | LOCAL_ACCEPTANCE_PASS | live `/account/security` link; menu guard test updated to the truthful state |
| Real Supabase Auth QA (real emails/links, two-browser revocation, deployed auth.sessions role proof) | EXTERNAL_GATE_PENDING | founder-gated exactly as PR #261 recorded |

## #251 — remaining in-lane items (status tonight)

Core implementation remains merged from PR #262 and revalidated green in
tonight's sweeps. The two truly-external criteria (#230/#247 accounting — now
locally satisfiable pending review; #243/#233 evidence) stand. The two
audit-flagged unblocked items — the async drift→confirmation recovery bridge
and the live-provider EN/ES QA session — were **not reached tonight**
(GENUINE_BLOCKER: none; prioritization under finite runtime). They remain the
first #251 follow-ups.

## Train 4 (#238, #239, #241, #244 runtime) — NOT REACHED

No interpreter-spine work was attempted tonight (deliberate: the spine is the
highest-risk surface and the composition/evidence trains carried more provable
acceptance per hour). No code claims exist. #244's paid provider comparison and
founder activation checkpoint remain exactly as the audit recorded.

## Train 6 (#243 adapters, #233 completion) — NOT REACHED

The concrete mocked-runtime trajectory adapters and the #233 charge-delta
authoring remain undone; the audit's finding that the #243 gate cannot register
owner progress until adapters exist still stands and is the highest-leverage
next slice after review of this branch.

---

## Final verification at the functional tip `a49179d`

- Hermetic agent-runtime sweep: `poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov` → **1129 passed** (keys blanked, synthetic fixture).
- Mocked evals: `poetry run pytest tests/evals -q --no-cov` → **58 passed, 1 sanctioned live-skip**.
- Cumulative backend gate (CI list + every suite added tonight): → **660 passed**.
- Web: `bun test __tests__` → **395 passed** (3,735 assertions); `bun run lint` → 0 errors (1 pre-existing warning); `bun run build` → production build green.
- `ruff check src tests scripts workflows` clean; modularity budget clean; `git diff --check` clean.
- Local mocked browser smoke (mock auth, sentinel env): chat turn with honest
  degraded recovery, New Chat → Recents → revisit rehydration, zero console
  errors (Train 2).

## Commit map (base `390d572`)

1. `29cc1e9` feat(api): OpenAPI structural gate (#234)
2. `1149f76` docs(reports): ledger open
3. `84fc0d6` feat(backtests): atomic admission (#230)
4. `8bfc702` perf(backtests): database-only polls (#231)
5. `3995cf2` fix(chat): ambiguous Run reconciliation (#242)
6. `673d763` perf(web): transcript cache integration (#252)
7. `3025e78` refactor(web): transcript hydration extraction (#252)
8. `b1415ac` fix(api): chat request bounds + correlation (#235)
9. `c384d29` feat(chat): durable turn lifecycle (#240)
10. `a7238b1` feat(usage): allowance truth + durable accounting (#247)
11. `a49179d` feat(auth): recovery and session controls (#248)
12. (this commit) docs(reports): ledger completion

Recommended review order: as listed (each commit is independently revertible;
7 depends on 6; 10–11 depend on 3).

## Consolidated external gates for tomorrow

1. Real-Postgres barriered admission + CAS proofs on a disposable database
   (`ARGUS_ADMISSION_TEST_DATABASE_URL`; tests are pre-written and skip-gated).
2. QA cost-ledger repair under founder mutation authority (#246 runbook).
3. #244: founder decision — bounded paid provider probe (proposed cap: ≤ $5)
   and rubric threshold approval; then the real empirical comparison.
4. #251: authorized live-provider EN/ES QA session; async bridge slice.
5. #248: founder-approved test accounts + deployed recovery redirect +
   deployed `auth.sessions` role proof; real-auth browser matrix.
6. GitHub Actions run of the amended CI on the pushed candidate; then the
   exact-SHA deployed Render browser canary (#233) after #243 adapters/green.
7. Founder decisions: ratify this branch's scope, then review/integration.

No GitHub state, external environment, production data, integration branch,
or tester exposure was changed by this laboratory branch. The two open PR
branches and all founder stashes were left untouched.

---

## Review-blocker correction pass (2026-07-18)

Five confirmed review blockers, one bounded TDD pass, minimal commits:

1. **#235 safe failure logging** — `24306bd`. Unexpected exceptions now emit
   one structured error log with the exact response `request_id`, exception
   class, method, and path — never the exception message, body, secrets,
   provider details, or a traceback. Captured-log correlation regression
   proves the log/response ids match and that a secret-bearing message stays
   out of the log stream. LOCAL_ACCEPTANCE_PASS.

2. **#240 production gateway wiring** — `0c599b4` + `e3b4356`. The optional
   `getattr` hooks are gone: acceptance upserts `chat_turn_lifecycles`
   (idempotent on `turn_id`), transitions call the database CAS function,
   terminal enrichment queries the active turn, and bounded reconciliation
   runs the shared predicate/order/batch through PostgREST with CAS-guarded
   transitions (`chat_turn_lifecycle_gateway`). Eight tests pin the wiring
   and each gateway operation's shape. Real-database proof: still
   EXTERNAL_GATE_PENDING (unchanged). Known nuance: gateway staleness
   selection compares ISO strings computed from the API clock; the CAS
   function's own timestamps remain database-clock owned.

3. **#230 stale-direct-job contract completeness** — `80149fd`.
   Reconciliation now resolves the stable job-derived finalized Run/evidence
   tuple before failing, in the memory twin and in both database paths
   (`finalized_direct_run_id` via uuid5, checked in the replay branch and the
   bounded pass); a durable tuple links its Run and completes the row as
   `succeeded` with failure fields cleared. Finalizer and reconciler
   serialize on the same row (shared lock in memory; row lock in SQL), and a
   late finalization can no longer supersede a terminal reconciliation
   decision (memory guard + `queued/running` filter on the gateway update).
   Supabase GET reconciliation stays database-only. LOCAL_ACCEPTANCE_PASS;
   real-Postgres run unchanged as the external gate.

4. **#242 artifact-bound identity** — `7e0cd5e`. The confirmation artifact
   persists the full-width canonical launch hash (card + action payload);
   chat admission binds the reservation identity to the artifact hash; the
   by-action lookup requires the linked message to contain the confirmation
   card and recomputes expected identity from the artifact's conversation,
   confirmation_id, and full-width hash — never from mutable job fields.
   Absent card or absent hash → integrity 500; artifact-hash mismatch → 409.
   Regressions added for all three. LOCAL_ACCEPTANCE_PASS.

### Second correction pass (2026-07-18, approved-contract alignment)

Three further confirmed blockers, one bounded TDD pass:

- **#242 artifact identity hardening** — `117f300`. Ownership of the
  confirmation message is now enforced (owner-scoped conversation read in
  Supabase mode; cross-owner rejection in memory); the artifact hash must be
  exactly `sha256:` + 64 lowercase hex; and the payload-digest fallback is
  gone — an action without the artifact's full-width hash cannot create a
  durable reservation the by-action lookup could never reproduce. Red-first:
  cross-owner 500, five malformed-hash variants 500, missing-hash
  no-reservation with the gateway untouched.

- **#230 job-aware atomic finalization** — `10b254c`. Direct success
  finalization locks/checks the job before creating the Run/evidence tuple:
  the memory twin holds the admission lock across check, tuple creation, and
  the success transition (fully serialized with the reconciler); Supabase
  mode claims the still-running row (row-locking conditional update) first.
  If stale reconciliation already won, no Run is created, exposed, or
  returned — the durable terminal decision replays. Red-first: a reconciler
  win during execution yields `direct_execution_abandoned` with zero new
  runs and zero finalization records. Remaining gateway-mode depth
  (recorded, not hidden): the tuple-then-success tail is claim-guarded but
  not yet one database transaction; closing it fully belongs to the
  finalization RPC and rides the existing real-database external gate.

- **#240 database-owned lifecycle boundaries** — `443d4a6`.
  `accept_chat_turn` persists the accepted user message and lifecycle row in
  one transaction (memory twin rolls the message back on lifecycle failure —
  acceptance is fail-closed per contract; terminal persistence stays
  fail-open because durable evidence reconciles it).
  `reconcile_stale_chat_turns` in SQL owns database-clock stale selection,
  20-row deterministic ordering, row locks, the post-lock stale recheck that
  spares freshly running turns, the complete
  owner/conversation/request/turn/terminal evidence predicate (owner via the
  conversations join; foreign-owner evidence abandons), failure precedence,
  and the terminal transition; the Python gateway is one RPC and the memory
  twin mirrors the same rules under a single lock. Abandoned truth projects
  into GET messages as an ephemeral typed retry-recovery item after the
  owning user message (nothing persisted, nothing mutated). Hook logs carry
  safe type/correlation fields only. Red-first: orphaned-acceptance
  rollback, cross-owner evidence abandonment, RPC-boundary shape (no
  client-side table orchestration), abandoned-turn GET projection with
  `retry_last_turn`, and secret-free hook logs.

Complexity reassessment: net simplification — the Python-side gateway
reconciliation orchestration (row adapter + evidence ranking) was deleted in
favor of the database boundary; the duplicate acceptance path in the message
choke point was removed; the payload-digest identity fallback was removed;
six gateway delegates collapsed into one mixin. Nothing speculative was kept.

Verification at `443d4a6`: hermetic sweep 1129; evals 58 + 1 skip; API and
reload regression 264; correction-surface cumulative 163; lint/budget/diff
clean. New external-gate note: migration `20260718000003` (acceptance +
reconciliation functions) joins the existing real-database proof gate;
`uuid_generate_v5` (uuid-ossp) availability is asserted there for
`finalized_direct_run_id`.

5. **#252 neutral miss surface + measured profile** — `163c94d`. A
   new-key cache miss clears to a neutral loading surface and never shows the
   previous conversation under the new selection; stale same-key content
   stays visible during silent revalidation. The contradictory source test
   was replaced by behavior-level coverage of the navigation mapper (six
   cases). The locally executable p50/p95 protocol is defined in
   `docs/reports/transcript-cache-profile.md` and ran: warm revisit p50
   0.0006 ms / p95 0.0065 ms with zero loader calls; cold miss p50 0.0138 ms
   / p95 0.0588 ms (50 samples each, budgets asserted in-suite). The
   deployed-browser EN/ES profile remains the external gate.
