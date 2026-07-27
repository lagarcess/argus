# Issue #232 Bounded Postgres Pagination Implementation Plan

Status: **ACCEPTANCE GREEN — PUBLICATION PENDING**

> **For agentic workers:** every behavioral slice starts with a focused failing
> regression, records the exact red, implements the smallest correction, proves
> the focused test green, and ends as an independently revertible conventional
> commit. The release captain owns sequencing, integration, publication, and
> every stop gate.

**Goal:** Stop Conversations, Messages, History, and Omnisearch / Idea Ledger
from loading every owned row before returning one page, while preserving owner
scope, existing opaque cursors, visible ordering, search completeness/ranking,
ledger counts, grouping, and canonical artifact identity.

**Starting integration SHA:** `94296ab8fccb9cdf7334bd2ef3e58dc3ec5543db`
from the exact then-current `origin/codex/private-alpha-next`.

**Architecture:** Keep the public routes and cursor encoding unchanged. Add
cohesive bounded read helpers at the Supabase/Postgres adapter boundary:
PostgREST keyset reads where its query language preserves the full ordering,
and private parameterized Psycopg SQL for the cross-source History/Search read
models. Every query repeats explicit owner/workspace predicates. Candidate
pages use `limit + 1`; exact Idea Ledger counts use a separate aggregate query.
Python continues to own response-model projection and artifact assembly.

**Tech stack:** Python 3.10, FastAPI, Supabase/PostgREST, PostgreSQL 17,
Psycopg 3, pytest, Ruff, Bun/React hydration tests, Playwright.

## Proven baseline

- Conversations: five product queries; 2,000 owned rows returned to produce a
  20-row page; p95 45.376 ms.
- Messages: 418 product queries; 5,302 rows returned to produce a 50-row page;
  p95 793.525 ms. The query fan-out included 100 jobs, 100 runs, 205 lifecycle
  records, and 11 message ranges.
- History: 14 queries; 5,000 rows returned before merge. The scale fixture
  triggered an oversized PostgREST request while joining 1,000 conversation
  ids, proving the current projection is not merely slow but operationally
  unbounded.
- Search: 23 queries; 8,000 rows returned to produce a 20-row page; p95
  386.730 ms.
- Plans showed full-owner sequential scans for the baseline fixture. Evidence
  is privacy-safe under `temp/issue-232/`.
- The private SQL normalizer was exhaustively checked across all Unicode scalar
  values plus random strings: zero mismatches against
  `normalize_search_text()`. PostgreSQL used the expression trigram index. This
  avoids a public RPC/view, generated column, or new cursor meaning.

## Non-negotiable contracts

- Conversations retain `(pinned, updated_at, id) DESC`. `updated_at` is the
  existing cursor timestamp and Recents activity clock; `created_at` would be a
  user-visible reorder.
- Messages retain `(created_at, id) ASC`.
- History retains
  `(pinned, activity_at, search_type_rank(type), id) DESC`.
- Search retains
  `(pinned, exact_title, exact_symbol, type_rank, updated_at,
  text_relevance, id) DESC`.
- Existing `base64(timestamp|id)` cursors remain accepted and emitted.
- Guest scope, PR #277 stale-card settlement, one canonical result owner,
  completed-only Run identity, and durable Idea/Evidence/Decision identity
  remain unchanged.
- No client caching/prefetch/cancellation, Recents disclosure UI, hidden
  feature activation, collection-count changes, semantic search, cache,
  materialized view, denormalization, provider/runtime work, or frontend polish.

## Accepted private-alpha History Run boundary

Founder decision on 2026-07-27 accepts one measured physical-work limitation
for this lane:

- every History source returns at most its bounded candidate limit before the
  Python merge;
- the measured normal 64-row and 12,000-row distributions remain bounded and
  performant;
- sparse, deep, or final Run pages may inspect more ordered Run rows because
  mutable Conversation archive/delete eligibility and Run ordering live in
  separate tables;
- ordering, archive/delete semantics, owner scope, and complete pages must not
  be weakened to reduce that work;
- the private reader's statement timeout remains the operational backstop; and
- issue #232 must not claim universal constant physical work for this
  cross-table Run path.

Maintaining Conversation state on Run rows or adding a maintained History read
model is a deferred scale-architecture option, not unfinished issue #232 work.
This lane must not add denormalized Run state, synchronization triggers, or a
maintained read model.

---

### Task 0: Baseline, feasibility, and execution ledger

**Files:** privacy-safe ignored evidence under `temp/issue-232/`; this plan.

- [x] Verify the clean, non-nested exact-integration worktree and canonical
  environment links.
- [x] Read canon, issue #232/comments, issue #252, tests, and migrations.
- [x] Capture realistic isolated-Postgres baseline metrics and plans.
- [x] Prove an exact indexable private SQL search normalizer.
- [x] Initialize the subagent-driven-development execution ledger.
- [x] Commit this active plan as
  `docs(history): add issue 232 bounded query execution plan`.

**Rollback:** revert the documentation commit; no runtime behavior changes.

---

### Task 1: Conversation keyset pagination

**Owned files:**

- Modify `src/argus/domain/supabase_gateway.py`, or extract one cohesive bounded
  read helper if that keeps the gateway smaller.
- Modify `src/argus/api/routers/conversations.py`.
- Modify `tests/test_supabase_gateway_pagination.py`.
- Modify/add focused API/Postgres pagination tests only as needed.

**Red matrix:**

```text
conversation_page_fetches_only_limit_plus_one
conversation_page_uses_pinned_updated_at_id_desc
conversation_first_middle_final_and_empty_pages
conversation_equal_timestamps_are_stable
conversation_soft_deleted_pivot_does_not_skip_or_duplicate
conversation_foreign_or_missing_pivot_fails_closed
conversation_owner_scope_is_present_in_every_query
```

- [x] Add the regressions and record the focused red output.
- [x] Add an owner-scoped pivot lookup for legacy cursors and push the complete
  keyset predicate plus `limit + 1` to Postgres.
- [x] Keep the memory-store path behaviorally unchanged.
- [x] Prove focused unit/API/real-Postgres tests green.
- [x] Commit
  `perf(conversations): push keyset pagination into Postgres`.

**Stop:** any requirement to replace `updated_at`, enrich/version the public
cursor, or make hard-deleted pivots silently guess their pinned tier.

**Rollback:** revert this commit; the former route-local slicing returns.

---

### Task 2: Message keyset pagination

**Owned files:**

- Modify `src/argus/domain/supabase_gateway.py` and/or one cohesive message read
  helper.
- Modify `src/argus/api/routers/conversations.py`.
- Modify `tests/test_supabase_gateway_pagination.py`.
- Add focused Message API/Postgres pagination regressions where required.

**Red matrix:**

```text
message_page_fetches_only_limit_plus_one
message_page_uses_created_at_id_asc_after_cursor
message_first_middle_final_and_empty_pages
message_equal_timestamps_and_deleted_pivot_are_stable
message_owner_and_conversation_scope_are_present
```

- [x] Add regressions and capture the exact red.
- [x] Query the raw page with `(created_at,id)` keyset ordering and
  `limit + 1`.
- [x] Preserve transcript-wide lifecycle truth with bounded existence/batch
  reads where the page boundary otherwise depends on later work; never infer
  artifacts from prose.
- [x] Prove focused API, Guest, lifecycle, and real-Postgres pagination tests
  green.
- [x] Commit `perf(messages): push keyset pagination into Postgres`.

**Stop:** any need to hydrate each frontend page independently or change the
public message/result metadata contract.

**Rollback:** revert this commit; the previous full-transcript adapter path
returns.

---

### Task 3: Bounded completed-job and Run projection

**Owned files:**

- Modify `src/argus/domain/backtest_message_projection.py`.
- Modify the minimum cohesive Supabase batch-read helper.
- Modify `tests/test_backtest_message_projection.py`.
- Add focused Guest/reload/result-owner/stale-card regressions where required.

**Red matrix:**

```text
completed_job_and_run_hydration_is_two_bounded_batch_reads
query_count_does_not_grow_with_completed_message_count
batch_reads_are_owner_and_conversation_scoped
durable_result_owner_beats_projected_alias
stale_confirmation_settles_only_its_exact_owner
guest_and_registered_reload_projection_match_prior_behavior
later_work_and_represented_request_checks_remain_transcript_correct
```

- [x] Add regressions and capture the exact red.
- [x] Replace per-identity job/run loaders with owner/conversation-scoped batch
  reads while keeping the current completed-job eligibility checks.
- [x] Preserve message, action, job, Run, result, EvidenceArtifact, and
  DecisionNote identity; never infer artifacts from prose.
- [x] Prove focused projection, API, Guest, stale-card, and result-owner tests
  green.
- [x] Commit `perf(messages): batch completed result hydration`.

**Stop:** any change to public message/result metadata, Guest settlement,
stale-card meaning, or one-result-owner behavior.

**Rollback:** revert this commit independently; Message keyset paging remains
useful without the batch-hydration optimization.

---

### Task 4: Bounded merged History

**Owned files:**

- Create/modify a cohesive private bounded-read module under
  `src/argus/domain/`.
- Modify `src/argus/domain/supabase_gateway.py`.
- Modify `src/argus/api/routers/history.py`.
- Add focused History API/query-budget/Postgres tests.

**Red matrix:**

```text
history_each_source_returns_at_most_limit_plus_one
history_first_middle_final_and_empty_pages
history_equal_timestamps_use_type_rank_then_id
history_soft_deleted_pivot_preserves_legacy_cursor_boundary
history_pages_have_no_skip_or_duplicate_after_deletion
history_chat_requires_message_exists_before_limit
history_run_parent_archive_delete_filter_applies_before_limit
history_owner_scope_is_present_in_every_source
history_guest_single_workspace_behavior_is_unchanged
history_query_and_row_budget_are_constant_as_volume_grows
```

- [x] Add regressions and capture the exact red.
- [x] Resolve legacy cursor pivots owner-scoped across the eligible source
  types; fail closed when absent or ambiguous.
- [x] Fetch no more than `limit + 1` ranking-compatible candidates per source,
  applying parent state/message existence before each source limit.
- [x] Merge only bounded candidates in Python with the existing sort key.
- [x] Prove focused API/real-Postgres/scale tests green.
- [x] Commit `perf(history): bound merged source queries in Postgres`.

**Stop:** any need to change cursor meaning, History grouping/order, or add a
public view/RPC.

**Rollback:** revert the commit; no durable writes or schema dependencies.

---

### Task 5: Bounded Omnisearch and exact Idea Ledger

**Owned files:**

- Create/modify the private bounded-read module and a generated/checked-in
  search SQL expression helper if needed.
- Modify `src/argus/domain/supabase_gateway.py`.
- Modify `src/argus/api/routers/search.py`.
- Modify focused search assembly/text tests and add real-Postgres scale tests.

**Red matrix:**

```text
sql_normalizer_matches_python_for_unicode_and_random_text
search_each_source_returns_at_most_limit_plus_one_candidates
search_preserves_all_token_matching_and_rank_buckets
old_pinned_exact_title_and_exact_symbol_beat_newer_plain_matches
search_first_middle_final_equal_timestamp_and_empty_pages
search_cursor_pivot_preserves_existing_query_specific_behavior
search_guest_scope_is_applied_before_candidate_limit
completed_runs_and_all_artifact_identities_are_preserved
decision_evidence_batch_is_bounded_and_owner_scoped
latest_decision_equal_timestamp_tie_uses_id_deterministically
ledger_groups_are_exact_and_not_candidate_or_decision_filter_relative
search_query_and_row_budget_are_constant_as_volume_grows
```

- [x] Add parity, scale, cursor, ranking, identity, and ledger regressions; record
  the exact red.
- [x] Use parameterized private SQL with explicit owner/workspace predicates.
  Build a top `limit + 1` candidate set per source using the exact existing
  matcher/rank dimensions.
- [x] Fetch Decision-linked Evidence in one bounded batch.
- [x] Keep exact ledger counts on a separate aggregate path computed before the
  optional decision-state result filter.
- [x] Continue projecting typed response models in Python.
- [x] Prove focused unit/API/real-Postgres/scale tests green.
- [x] Commit
  `perf(search): bound ranked candidates and preserve ledger counts`.

**Stop:** any mismatch in search completeness/ranking/group counts, or need for
a public RPC/view, generated search column, new product semantic, or new cursor
meaning.

**Rollback:** revert the commit; the prior Python all-row assembly returns.

---

### Task 6: Query-plan-justified indexes and measurement proof

**Owned files:**

- Add one forward migration under `supabase/migrations/` only for indexes whose
  before/after plans prove they are required.
- Add migration catalog/reset and query-budget tests.
- Add/update privacy-safe benchmark tooling under `scripts/qa/` only if it is
  generally reusable; otherwise keep evidence ignored under `temp/issue-232/`.

- [x] Capture post-implementation `EXPLAIN (ANALYZE, BUFFERS)` before adding
  indexes.
- [x] Add only the minimum composite/expression indexes proven necessary.
- [x] Capture plan improvement after each index.
- [x] Reset the isolated Supabase project from zero and verify the full
  migration chain/catalog/RLS.
- [x] Compare small and large fixtures: query count and returned rows remain
  bounded.
- [x] Record database, artifact projection, serialization, and endpoint p50/p95
  separately. The seeded uncached message endpoint must be at or below 250 ms
  p95. Exact-head Message p50/p95 total was 29.075/37.827 ms; database
  26.010/34.487 ms; artifact projection 0.128/0.166 ms; serialization
  0.081/0.093 ms.
- [x] Commit
  `perf(postgres): add proven indexes for bounded history reads`.

**Stop:** any schema/RLS redesign beyond forward indexes, or a p95 miss without
an identified measured owner.

**Rollback:** each index migration contains explicit `DROP INDEX` guidance in
its comments/PR notes; runtime commits remain independently revertible.

---

### Task 7: Exact indexed Search execution

**Owned files:**

- Modify `src/argus/domain/postgres_search_reader.py` and its focused tests.
- Add one forward migration only for expression indexes whose before/after
  plans prove they remove the measured normalized source scans.
- Update the Task 6 measurement evidence without weakening Search semantics,
  its two-second statement ceiling, or any public contract.

**Red matrix:**

```text
search_large_common_query_completes_below_statement_timeout
search_exact_all_token_match_survives_index_prefilter
search_short_and_mixed_tokens_have_no_false_negatives
search_phrase_score_rank_and_opaque_cursor_are_unchanged
search_expression_indexes_are_selected_and_owner_scope_is_preserved
search_zero_reset_catalog_and_rls_remain_valid
```

- [x] Record the exact timeout and source-scan plans as RED.
- [x] Replace row-by-row regexp token splitting with parameterized, exact
  per-token predicates and an exact final recheck.
- [x] Add only plan-proven normalized-expression trigram indexes. The
  index-enabling extension is private database machinery; it must not add a
  public RPC/view, generated search column, or API dependency.
- [x] Preserve arbitrary substring completeness, including one- and two-
  character tokens, the complete rank tuple, exact ledger groups, Guest scope,
  and artifact identity.
- [x] Prove the focused parity, cursor, scale, RLS, reset, plan, and endpoint
  tests green.
- [x] Commit independently as
  `perf(search): index exact bounded candidates`.

**Stop:** any need to change Search completeness, rank/group semantics, the
opaque cursor, add a public RPC/view or generated search column, or redesign
schema/RLS beyond plan-proven forward expression indexes.

**Rollback:** revert the runtime commit and its forward index migration; the
prior exact reader remains independently restorable.

---

### Task 8: Physically bounded deep keysets and History sources

**Owned files:**

- Modify only the cohesive persistent Conversation/Message page helpers and
  `src/argus/domain/postgres_history_reader.py`.
- Add focused unit, API, real-Postgres, and plan regressions.
- Add forward source-order indexes only if specialized exact plans prove they
  materially reduce physical rows.

**Red matrix:**

```text
conversation_deep_page_uses_tuple_keyset_and_constant_candidate_rows
message_deep_page_uses_tuple_keyset_and_constant_candidate_rows
history_specialized_sources_preserve_first_middle_final_pages
history_equal_timestamps_deletion_and_owner_scope_remain_exact
history_small_and_large_plan_rows_are_page_bounded_per_source
```

- [x] Record the exact PostgREST OR and generic History plans as RED.
- [x] Move persistent Conversation and Message candidate pages to private,
  owner-scoped parameterized tuple-keyset SQL while keeping their opaque
  cursor meaning and response projection unchanged.
- [x] Specialize History source SQL for first/deep and archive/delete shapes
  so existing order indexes can stop at `limit + 1`.
- [x] Add only source-order indexes selected by exact before/after plans.
- [x] Prove cursor compatibility, deletion stability, equal-timestamp ordering,
  owner isolation, artifact hydration, scale, RLS, reset, and endpoint timing.
- [x] Commit Conversation/Message and History corrections as independently
  revertible commits.

**Stop:** any public cursor change, public RPC/view, schema/RLS redesign, or
History ordering/grouping/collection-count change.

**Rollback:** revert each runtime/index commit separately.

---

### Task 9: Fresh review and proportional corrections

- [x] Request fresh database/query correctness review.
- [x] Request fresh API/cursor compatibility review.
- [x] Request fresh RLS/security review.
- [x] Request fresh artifact identity/hydration review.
- [x] Request fresh QA/performance methodology review.
- [x] Reproduce every actionable finding at candidate HEAD.
- [x] Apply only the smallest correction for confirmed reachable findings.
- [x] Re-review only the bounded delta.

Use both `superpowers:requesting-code-review` and `argus-review-contract`.

---

### Task 10: Final integration, acceptance, and publication

- [x] Fetch `origin/codex/private-alpha-next` and merge it normally; never
  rebase. The first final merge incorporated `7b00e747`; a second normal
  catch-up incorporated `059f8e82` after that relevant provider-free CI commit
  landed during acceptance. No rebase occurred.
- [x] Rerun affected focused tests, real Postgres/RLS, migration reset, scale
  benchmarks, Ruff/format/modularity, `git diff --check`, frontend hydration
  tests, and production build when types/hydration are affected.
- [x] Run production-parity authenticated browser/API QA with controlled
  fixtures and no provider-backed interpreter turns.
- [x] Record exact runtime candidate SHA and privacy-safe evidence.
- [ ] Push `codex/issue-232-bounded-pagination`.
- [ ] Open a Draft PR targeting `codex/private-alpha-next`.
- [ ] Wait for terminal CI.
- [ ] Update issue #232 criterion by criterion; check only direct proof and
  leave the issue open.

**Never:** merge, deploy, promote to `main`, close the issue, mutate hosted
Supabase, or change unrelated flags.

## Exact-head acceptance evidence

Verified runtime head:
`9a5047c62dd9d98e2891a2c48b4d7b594ec6455f`.

- Complete isolated migration reset from zero passed through
  `20260727161406_add_history_state_page_indexes.sql`; catalog, explicit
  rollback text, RLS, grants, and authenticated two-owner isolation passed.
- Focused hermetic backend/CI: 251 passed, 2 expected database skips.
- Real Postgres pagination/History/Search/index suite: 93 passed. It covers
  first/middle/final/empty pages, equal timestamps, deletion between requests,
  owner isolation, exact ranking, exact ledger counts, and plan/catalog checks.
- Frontend hydration/Search compatibility: 188 passed. Production build and
  TypeScript compilation passed.
- Quality: Ruff passed; 18 candidate-owned formatted files passed the formatter;
  the extracted readers/message helper passed mypy; modularity passed with
  `supabase_gateway.py` at 1,920 lines versus its 2,113-line limit; diff check
  passed. Whole-file formatter deviations that also exist on integration were
  not rewritten as unrelated churn.
- Search SQL construction is constant-shape: 160,346 rendered bytes and 73
  normalizer occurrences for 1, 20, 100, 400, and 500 tokens. Before the fix,
  one token rendered 147,705 bytes while 500 tokens rendered 18,000,346 bytes.
  Arbitrary all-token matching, rank order, and exact ledger groups remain
  covered by unit and real-Postgres tests.
- The 12,000-row/source endpoint benchmark uses 20 sequential uncached samples
  and records no transcript, raw owner id, token, credential, or provider call.
  Conversations returned 21 rows with one query and 4.426 ms p95 total; History
  returned 84 bounded source candidates with one query and 4.336 ms p95 total;
  Messages returned 80 database rows with 11 fixed queries and 37.827 ms p95
  total; Search returned 193 rows with 10 fixed queries and 3,860.752 ms p95
  total for the deliberately all-matching `alpha` corpus. Every Search source
  statement remains below the unchanged two-second statement timeout; selective
  queries use the six plan-proven GIN indexes.
- Dense History Run measurement returned the 21-row candidate-plus-sentinel
  page after inspecting 85 Runs and 85 parents in 0.193 ms. The accepted sparse
  first page inspected 2,101 Runs/parents and returned 21 candidates in
  2.444 ms; its final page inspected 2,100 Runs and 2,099 parents, returned the
  complete final 20 with no sentinel, and completed in 1.897 ms. This is the
  accepted private-alpha exception, not a universal constant-work claim.
- Authenticated exact-head API QA returned History 256/256 across 11 pages,
  Search 448/448 across five pages, Messages 12,001/12,001 across 121 pages,
  exact 16-by-four small-owner ledger counts, 50/50 canonical completed-result
  hydrations, and clean two-owner isolation. Message p50/p95 was
  66.998/81.555 ms.
- Browser QA as a normal non-admin user visibly showed exact 3,000-by-four
  ledger counts, ranked the expected all-token Idea first, rendered all 12,001
  long-thread artifacts, switched to the one-item short thread, and recorded
  zero console errors or warnings. Reload was exercised, but the artificial
  12,001-item client hydration did not finish inside the fixed four-second
  observation; no completion claim is made. Client render/caching work remains
  separately owned by issue #252.
- The final bounded database/security review approved
  `52237f67..9a5047c6` with no candidate-owned correctness, ownership/RLS,
  privacy, migration-safety, or data-loss finding. The QA rereview approved the
  separate database/artifact-projection/serialization/total timing method.

Maintaining Conversation state on Run rows or adding a maintained History read
model remains a deferred scale-architecture option. It is not unfinished issue
#232 work and is not implemented by this lane.
