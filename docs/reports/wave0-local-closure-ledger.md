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

### Third correction pass (2026-07-18, remaining P1 failures)

All five commits red-first; states below are the honest post-pass positions.

1. **#242 identity before any execution** — `d5b5a97`. A `run_backtest`
   action whose confirmation artifact hash is missing or malformed now
   raises a typed `BacktestArtifactIdentityError` before durable admission,
   delegate execution, provider access, or compute; the dev fallback
   explicitly re-raises it, so it can never degrade into in-process
   execution. The `artifact_launch_hash or payload_digest` fallback
   expression is deleted — identity binds only to the immutable artifact
   hash. The by-action confirmation load composes the existing owner-scoped
   `user_id + conversation_id + message_id` boundary
   (`owned_conversation_message` / `gateway.get_message`) in both modes; the
   unscoped `get_message_row` surface is removed. Red-first: three
   malformed/missing-hash variants leave gateway, delegate, provider, and
   compute untouched; a foreign-owned message row visible to an unscoped
   lookup can never qualify as confirmation evidence.

2. **#230 one-transaction success finalization** — `bdba12b`. New migration
   `20260718000004_finalize_direct_backtest_success.sql`: one
   security-scoped function locks the owner-scoped direct job (`for
   update`), replays the terminal row untouched when reconciliation already
   won (zero Runs created or returned), fails closed (`missing`) when the
   row is gone, and otherwise composes `finalize_backtest_completion` and
   links + succeeds the job in the same transaction. The Python
   claim → client-side tuple → conditional-CAS sequence and
   `claim_running_direct_job` are deleted; the API validates the returned
   final job (`succeeded` + `result_run_id` linking the finalized run)
   before exposing any Run, and the memory twin fails closed on a missing
   job. This closes the second pass's recorded tuple-then-CAS residue.
   Red-first: Supabase superseded ⇒ 503 replay with no tuple write; missing
   job ⇒ 503 fail-closed (Supabase and memory); an inconsistent returned
   final job ⇒ finalization failure, never a 200 Run.

3. **#240 acceptance composes the canonical append** — `0096590`.
   `accept_chat_turn` no longer contains a second `messages` writer: it
   calls `append_conversation_message` (ownership, message identity +
   replay, `messages.user_id`, monotonic `created_at`, preview, conversation
   `updated_at`) and inserts the lifecycle row idempotently (`on conflict
   (turn_id) do nothing`) in the same transaction; the gateway supplies the
   writer's identity inputs (message id, created_at, computed preview). New
   `tests/test_migration_schema_compat.py` parses every migration into a
   column catalog and proves each insert list against the real schema
   (existence + NOT-NULL-without-default coverage) plus the lifecycle
   functions' alias-qualified references — the check that caught the
   acceptance insert omitting `messages.user_id` (a NOT NULL column: the old
   insert could never have succeeded on a real database).

4. **#240 owner-scoped reconciliation** — `2b7bb31`. The RPC now requires
   `p_user_id`, rejects an unowned conversation before touching any row,
   filters stale selection to the owner's rows, and the evidence predicate
   additionally requires `m.user_id = v_row.user_id`; the memory twin
   applies the same requester scope and message-user check. Both routes
   invoke reconciliation only after route ownership succeeds (the messages
   GET hook moved below its 404). Red-first: an unauthorized GET returns 404
   and leaves the owner's stale row untouched; a foreign `user_id` on an
   otherwise-matching terminal message abandons instead of reconciling.

5. **#240 page-scoped projection** — `a6f3356`. The recovery item is
   inserted directly after its owning user message by position — its
   `created_at` borrows the owning message's timestamp with the projection
   id as the `(created_at, id)` tiebreak, keeping cursor ordering monotonic
   — instead of a global re-sort that pushed it behind later turns.
   Reconciled turns project `turn_lifecycle_reconciled`
   (status/outcome/turn_id) onto the linked assistant message's response
   copy without mutating persistence. The lifecycle lookup is scoped by the
   page's user-turn ids in both modes (`list_projectable_*`), removing the
   permanent first-20 historical ceiling. Red-first: multi-turn adjacency,
   reconciled outcome on reload with unmutated storage, and a 21-abandoned
   history projecting all 21.

Complexity reassessment (pass 3): net simplification again. Deleted:
`claim_running_direct_job`, `get_message_row`, the payload-digest identity
fallback, the hand-rolled two-branch confirmation load (now one call to the
existing owner boundary), the second SQL messages writer, and the projection
re-sort + unowned-tail append. Added surface is one SQL function that
composes an existing one, and the schema-compat test harness. No speculative
abstraction was kept.

Verification at `a6f3356`: hermetic sweep 1129/0; correction-surface
cumulative 126 + 183 (+2 Postgres proofs skip-gated as designed); API
contract + OpenAPI gate 147; web 402/0 from `web/` (frontend untouched this
pass); modularity budget, ruff, and `git diff --check` clean; worktree
clean.

External gates updated: migration `20260718000004` joins `20260718000001–3`
in the disposable-Postgres real-database proof (apply in order; exercise
`finalize_direct_backtest_success` superseded/missing/success branches and
`reconcile_stale_chat_turns` rejection on an unowned conversation, plus
`accept_chat_turn` replay through `append_conversation_message`). All other
recorded external gates stand unchanged.

### Fourth correction pass (2026-07-18, #240 read-projection contract)

The third-pass review cleared #230 finalization, #242 artifact identity,
#240 atomic acceptance, and #240 owner-scoped reconciliation. This pass
corrects the remaining #240 contract mismatch against
`docs/API_CONTRACT.md` 539-585 and `docs/DATA_MODEL.md` 8.1. All red-first.

1. **Read overlay on persisted messages** — `50ccd10`. Abandoned-turn reads
   return the persisted accepted user message exactly once with the exact
   contract overlay on its response copy: canonical `agent_runtime_turn`
   (turn_id, request_id, abandoned, terminal, reconciled_outcome null,
   failure_code, retryable), the `recovery` object, and typed
   `retry_last_turn` keyed by `request_message_id` with the exact
   `chat_action` copied when present (omitted otherwise). No synthetic
   assistant message is injected and persistence is never mutated, so
   adjacency and cursor attachment are properties of the persisted message
   itself (proven by a limit-1 paging red). Reconciled truth overlays the
   linked assistant message's canonical `metadata.agent_runtime_turn`
   (status reconciled, terminal true, reconciled_outcome, applicable
   failure/retry fields); the parallel `turn_lifecycle_reconciled` key from
   pass 3 is removed. The projection lookup is owner-scoped and keyed by the
   read's message ids (abandoned via turn_id, reconciled via
   assistant_message_id).

2. **Schema aligned with DATA_MODEL 8.1** — `5612448`. The unpublished
   candidate migrations were corrected in place (no compatibility layer):
   `turn_id` references the accepted `messages.id`; `assistant_message_id`
   is unique when present; `retryable` is non-null defaulting false;
   `reconciled_outcome` exists exactly when reconciled; abandoned requires a
   null assistant link; and the approved `terminal_at`/`reconciled_at`
   fields replace the silently substituted `finished_at` across the table,
   CAS, reconciliation branches, and memory twin. Every service-role
   lifecycle lookup is owner-scoped: the active-turn finder now requires the
   requesting user in both modes, joining the already-scoped reconciliation
   and projection reads.

3. **Presentation-only recovery row** — `593532d`. The smallest frontend
   surface for the approved contract: hydration derives one recovery
   attachment from the user message's abandoned overlay (reusing the
   existing recovery-display and retry-action helpers; the typed
   `retry_last_turn` action now carries `request_message_id`), and
   `ChatMessage` renders it immediately beneath the owning user bubble — not
   an assistant bubble, no API message identity, no feedback/copy
   affordances. Deriving from the message itself keeps it attached across
   cursor pages with no orphan possibility. Localized `turn_abandoned` copy
   added for EN and ES.

Complexity reassessment (pass 4): net simplification. Deleted: the
synthetic projection-message builder and its id scheme, the server-side
localized recovery content dependency, the parallel
`turn_lifecycle_reconciled` contract, and `finished_at`. The projection
module is now pure metadata overlays; the frontend addition reuses two
existing helpers plus one render block. No second lifecycle abstraction,
synthetic API message type, or background sweeper was introduced.

Verification at `593532d`: hermetic runtime gate 1129/0; focused +
cumulative correction surface 291/0; API contract + OpenAPI gate 106/0;
web 408/0 from `web/` plus `bun run lint` (0 errors, 1 pre-existing
warning) and a green production build; modularity budget, ruff, and
`git diff --check` clean; worktree clean.

External gates after this pass: disposable-Postgres real-database proof now
covers the reworked migrations `20260718000002/3` (messages FK, unique
assistant link, status checks, terminal_at/reconciled_at, acceptance
replay through `append_conversation_message`, owner-scoped reconcile) plus
`20260718000004`; real-auth/RLS matrix; deployed-browser EN/ES QA now
including the abandoned-recovery row and its retry; GitHub Actions run;
exact-SHA Render canary; the #244 paid probe and #251 live QA stand
unchanged.

### Fifth pass (2026-07-18, #240 end-to-end lifecycle closure)

Bounded assignment: finish issue #240's durable ordinary chat-turn
lifecycle end to end against `contract-chat-turn-lifecycle`, the retry
semantics, and DATA_MODEL 8.1. The fourth pass's schema alignment,
persisted-message overlay, and recovery-row design are preserved
unchanged. All corrections red-first; `tests/test_chat_turn_route_matrix.py`
is the route-matrix suite.

Route matrix (acceptance / running / terminal owner per accepted
non-backtest POST /api/v1/chat/stream path):

1. Normal message → LangGraph: persist()+accept_chat_turn / route
   transitions running immediately before consuming runtime events /
   terminal assistant write (canonical completed) drives the CAS.
2. Onboarding-required prompt: acceptance as above / no graph work /
   completes directly with the durable prompt (the accepted-forever
   HTTP-200 reproduction, now fixed). The onboarding goal-selection
   control message remains a non-accepted protocol path (no user message
   is persisted today).
3. Runtime-fallback / missing-checkpoint early response: acceptance /
   none / completes directly with the durable recovery answer.
4. select_response_option: atomic claim now commits the lifecycle row in
   the same transaction (acceptance SQL gained the writer's option-claim
   parameters; memory claim creates the row under the same lock with
   rollback) / running before runtime / terminal as (1).
5. cancel_confirmation: now participates in ordinary admission (user
   action message + lifecycle) / none / completes with the durable
   cancellation tombstone carrying canonical metadata.
6. Successful terminal response: terminal message writes status
   completed (legacy "succeeded" is no longer written).
7. Recoverable terminal failure: canonical recoverable_failed with
   failure_code and retryable inside the turn envelope; lifecycle carries
   the same evidence.
8. Initialization/pre-graph failure: accepted, then recoverable_failed
   with canonical metadata; no running transition.
9. chat.run_backtest: user message persists with no chat lifecycle row —
   backtest_jobs owns durable state (route-level proof retained).
   A final with no persisted message/artifact stays genuinely incomplete
   for stale reconciliation.

Commits:
- `d4eaa94` acceptance coverage (A): cancel admission + tombstone
  completion, response-option atomic lifecycle (SQL + memory rollback),
  run_backtest exclusion proof.
- `ab72194` running + canonical terminal truth (B+C): running before the
  first graph operation; early responders complete; canonical
  completed/recoverable_failed envelopes with turn_id/request_id/failure
  fields; read-compatible legacy mapping (suppression guard + CAS both
  accept historical succeeded/failed; nothing writes them anymore).
- `f0434f3` CAS + reconciliation (D+E): no-op comparison includes
  failure_code/retryable in both backends (different terminal failure
  truth conflicts); reconciled recoverable failures copy the winner's
  canonical failure evidence; memory reconciliation enforces the same
  required-owner boundary as the database function; the unused direct
  lifecycle writer (hooks accept_turn + gateway upsert) is removed with a
  guard test.
- `20633b6` retry supersession (F): a later user turn, confirmation,
  result, or cancellation removes the abandoned overlay's actionable
  retry_last_turn while preserving the historical recovery state;
  retry_last_turn stays keyed by request_message_id; frontend renders the
  recovery row without a button when the backend withheld the action.
- `2d41fcb` modularity extractions (onboarding texts →
  chat/onboarding.py, terminal turn envelope → turn_lifecycle_hooks,
  missing-result-action message → chat/actions.py); behavior-preserving,
  budget back to zero violations.

Complexity reassessment (pass 5): one acceptance boundary now covers
plain, option-claim, and cancellation turns (the SQL function gained four
optional pass-through parameters instead of a second writer); the
standalone lifecycle writer was deleted; supersession reuses the existing
authoritative-artifact predicate; no parallel lifecycle writer,
orchestration layer, or sweeper was added. agent.py shrank under its
budget via cohesive extractions.

Verification at `2d41fcb`: hermetic runtime gate 1129/0; focused
lifecycle/router/migration battery 323/0 (route matrix 9/9);
contract + OpenAPI 103/0; web 409/0 with lint (0 errors, 1 pre-existing
warning) and green production build; modularity budget, ruff, and
`git diff --check` clean; worktree clean.

External gates updated: the disposable-Postgres proof must additionally
exercise the extended `accept_chat_turn` option-claim parameters (claim
replay, not-claimable outcome, lifecycle-on-conflict), the CAS
failure-evidence no-op/conflict branches, and reconciliation's
failure-evidence copy. Real-auth/RLS, deployed-browser EN/ES QA (now
including cancel-turn transcript rows and retry supersession), GitHub
Actions, exact-SHA Render canary, #244 probe, and #251 live QA stand.

### Sixth correction pass (2026-07-18, verified #240 gaps)

Accounting correction first: the fifth pass changed **22 files**
(+1377/−312 over `f8898d6`, including its ledger commit; 21 code/test
files at `2d41fcb`). This sixth pass changes **16 code/test files**
(+429/−45 at `5cc09b2`) plus this ledger update. The earlier
"Local Wave 0 implementation candidate ready for review" claim is
**retired**: it overstated the branch, because locally executable work
remains unfinished (listed below) independent of any external gate.

1. **Onboarding controls are durable accepted turns** — `9468ef3`.
   `__ONBOARDING_GOAL__`/`__ONBOARDING_SKIP__` are supported message-only
   paths and can no longer bypass the lifecycle: admission is enabled for
   every supported request, the control message and lifecycle row persist
   atomically through the existing acceptance boundary, and the localized
   assistant response completes the turn with canonical terminal metadata.
   Both preview writers suppress raw control tokens; live and reload
   render through the existing localized mapping (pinned by the frontend
   contract suite). Red-first: goal and skip durable turns with completed
   lifecycles and token-free previews; a persistence interruption leaves
   an accepted row that the stale reconciler settles to abandoned.

2. **Abandoned retry actually bound to its owning message** — `cff6c69`.
   Hydration exposes the retry only when `request_message_id`, the API
   user-message id, and `agent_runtime_turn.turn_id` all agree (mismatch
   renders historical recovery with no button); the action id is keyed by
   `request_message_id`; the ChatInterface click path resolves the replay
   through `resolveRetryLastTurnReplay`, consuming the owning persisted
   user message's content/action — tampered client text is never trusted
   and a mismatched historical action replays nothing; legacy unbound
   assistant-failure retries keep payload semantics. No new backend
   ChatActionType or public-contract change was required.

3. **Exact null-safe CAS terminal truth** — `5cc09b2`. Memory and SQL
   no-op comparisons now compare complete effective truth: failure_code
   exact and null-safe (`IS NOT DISTINCT FROM`), retryable effective with
   omitted meaning false. Red-first: replays omitting or changing stored
   failure_code or retryable=true conflict; exact evidence and
   completed-with-effective-defaults replays stay no-ops; both backends
   match.

Complexity reassessment (pass 6): no new abstractions — admission lost
its last carve-out (enabled is now unconditionally true), the retry
binding is one resolver reusing existing helpers, and the CAS change is
comparison-only.

Verification at `5cc09b2`: hermetic runtime gate 1129/0; focused
lifecycle/route-matrix/onboarding/retry/migration/reload battery 327/0
(route matrix 12/12); contract + OpenAPI 103/0; mocked eval harness
58 passed + 1 skipped; trajectory harness subset 17/0; web 412/0 with
lint (0 errors, 1 pre-existing warning) and a green production build;
modularity budget, ruff, and `git diff --check` clean; worktree clean.

#### Unfinished local work (not external gates)

These are locally executable and remain **not implemented** on this
branch; they must not be conflated with external acceptance authority:

- **#243 concrete runtime adapters** — the concrete adapter
  implementations and trajectory flips beyond the recorded harness
  remain unwritten (Train 6 was reached only for its test scaffolding).
- **#233 local canary authoring** — the deterministic local canary
  script/spec authoring remains unwritten.
- **#251 local async bridge** — the in-lane async-bridge remainder
  recorded at "#251 — remaining in-lane items" is still local work, not
  a deploy gate.

#### External gates (authority outside this laboratory)

Disposable-Postgres real-database proof (migrations `20260718000001–4`,
including the option-claim acceptance branches, exact-truth CAS
branches, and reconciliation evidence copy); real-auth/RLS matrix;
deployed-browser EN/ES QA (recovery row, cancel-turn transcript rows,
onboarding-control transcript rendering, retry supersession and
binding); GitHub Actions run; exact-SHA Render canary; the #244 paid
probe; #251 live EN/ES QA.

### Seventh correction pass (2026-07-18, verified #240 hydration + protocol gaps)

Bounded to #240 only; #243/#233/#251 untouched. **13 code/test files**
(+287/−36 at `505e0af`) plus this ledger update. All red-first.

1. **Abandoned recovery survives canonical action hydration** — `0a464c7`.
   `hydrateMessagesFromApi` short-circuited user messages carrying a
   structured `chat_action` into bare action rows, dropping the abandoned
   recovery that the lower-level text hydrator attached. The action branch
   now composes the exported `abandonedRecoveryFromApiMessage` (the same
   derivation the text hydrator uses — no duplicated retry/recovery
   parsing), and ChatMessage's two user branches merged so the recovery row
   renders beneath both the action chip and the plain bubble. Red-first: a
   canonical-hydration behavior suite proving an abandoned `change_dates`
   action keeps its action-row presentation, carries its identity-bound
   retry (`retry-last-turn-<id>`), and renders recovery with no button on a
   mismatched identity; plus a structural pin that no early action-kind
   return can bypass the row.

2. **Typed onboarding protocol state; clean runtime history; live/reload
   parity** — `505e0af`. Acceptance stamps
   `metadata.onboarding_control = {kind, goal}` (typed
   `onboarding_control_state` parser) on the durable control turn;
   `load_runtime_thread_history` filters user turns by that owned state so
   `__ONBOARDING_*` tokens never become LLM conversation context (localized
   assistant responses remain); both preview writers switched from the raw
   prefix check to the typed state. The skip choice now renders its
   localized user bubble live exactly like goal selections, and live/reload
   share the same i18n keys in English and Spanish (four goal cards +
   `onboarding.skip`; `surprise_me` is only reachable through skip).
   Red-first: durable-control tests extended to require the typed metadata;
   a runtime-history test driving goal + skip through the accepted route
   and proving zero protocol tokens in history; a frontend parity pin
   (skip bubble live, shared keys, EN/ES locale coverage); and the
   interruption test extended to prove the abandoned control remains
   retryable through its owning durable message (the overlay replays the
   exact persisted token). No new public ChatActionType; no onboarding
   redesign.

Complexity reassessment (pass 7): compositional only — one exported
hydration entry reused by both transcript shapes, one typed parser that
the legacy goal parser now delegates to, and filters keyed off owned
metadata replacing prefix heuristics. No new writer, action type, or
abstraction.

Verification at `505e0af`: focused
lifecycle/route-matrix/onboarding/retry/migration/reload battery 328/0
(route matrix 14/14); hermetic runtime gate 1129/0; mocked eval harness
58 + 1 skipped; trajectory harness 17/0; web 416/0 from `web/` with lint
(0 errors, 1 pre-existing warning) and a green production build;
modularity budget, ruff, and `git diff --check` clean; worktree clean.

Unfinished local work and external gates are unchanged from the sixth
pass: **local** — #243 concrete runtime adapters, #233 local canary
authoring, #251 local async bridge; **external** — disposable-Postgres
proof (migrations `20260718000001–4` with the extended acceptance/CAS/
reconciliation branches), real-auth/RLS matrix, deployed-browser EN/ES
QA (now also covering the abandoned-action recovery row and onboarding
live/reload parity), GitHub Actions run, exact-SHA Render canary, #244
paid probe, #251 live EN/ES QA.
