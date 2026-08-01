# Conversation Activity and Read Foundation Implementation Plan

> Execution owner: use the approved Conversation Activity specification and
> implement this slice test-first. Keep every commit independently reviewable.

**Goal:** Build the durable backend truth consumed by the later UI PR: which
conversations are working, which have unseen terminal activity, and which were
manually marked unread.

**Scope:** Backend, data, API contracts, tests, and canonical documentation
only. Do not change cards, Recents visuals, failure treatments, animations,
menus, frontend types, localization, LangGraph, SSE framing, backtest
finalization, PostHog, or provider code. PR #320 continues to own failure
visuals; this slice only maps existing typed lifecycle states.

**Integration base:** `codex/private-alpha-next` at
`403ea11410da2746f132223e44aac70c4a4b5534`.

**Authoritative specification:**
`docs/superpowers/specs/2026-08-01-conversation-activity-attention-unread-lifecycle.md`.

## Public contract

Add the optional, additive `activity` projection to every `Conversation`
response and chat `HistoryItem`; omit it from non-chat history items:

```json
{
  "operation": {
    "status": "idle | queued | running | checking",
    "kind": "chat_turn | backtest_job | null",
    "updated_at": "timestamp-or-null"
  },
  "attention": {
    "status": "none | new_activity | manual_unread | needs_input | needs_attention",
    "cursor": "opaque-cursor-or-null"
  }
}
```

Add:

```text
GET   /api/v1/conversations/{conversation_id}/activity
PATCH /api/v1/conversations/{conversation_id}/activity
```

Patch bodies:

```json
{ "action": "mark_unread" }
```

```json
{
  "action": "mark_read",
  "through_attention_cursor": "opaque-cursor-or-null"
}
```

Contract behavior:

- An accepted ordinary turn projects `queued`; a running turn or job projects
  `running`; and a queued job projects `queued`.
- A succeeded job whose completed Run cannot yet be validated projects
  `checking`, never ready.
- Operation precedence is `running > queued > checking > idle`; ties use the
  newest timestamp, then prefer the more specific backtest job.
- Existing typed `await_user_reply`, `needs_clarification`, and
  `await_approval` outcomes project `needs_input`.
- Existing lifecycle and job failure statuses project `needs_attention`; this
  plan adds no failure taxonomy or recovery behavior.
- Completed turns and fully hydrateable succeeded jobs project `new_activity`.
- No message-prose matching is allowed.
- The cursor is versioned and opaque and contains only source kind and UUID.
  The server revalidates ownership, conversation, terminal eligibility, and
  timestamp before advancing read state.
- Missing, deleted, foreign, or guest-out-of-workspace conversations return
  `404`; guest `mark_unread` returns `403`; a validly shaped but invalid or
  stale source returns `409`; malformed actions or cursor shapes return `422`.
- Existing list ordering, cursors, previews, and
  `conversations.updated_at` remain unchanged.

## Task 1: Typed projection and pure state rules

**Files:**

- Create `src/argus/domain/conversation_activity.py`.
- Modify `src/argus/api/schemas.py`.
- Modify `src/argus/domain/store.py`.
- Create `tests/test_conversation_activity.py`.

**Steps:**

1. Write failing pure tests for every operation and attention state, multiple
   operations in one conversation, deterministic ties, multiple conversations,
   typed needs-input outcomes, existing failures, hydrateable and missing Runs,
   manual unread, stale cursors, and task isolation.
2. Run `poetry run pytest tests/test_conversation_activity.py -q --no-cov` and
   retain the expected failure.
3. Add Pydantic activity models. Keep `Conversation.activity` and
   `HistoryItem.activity` optional for wire compatibility; later API tests must
   require the field on emitted chat records.
4. Implement operation precedence, attention classification, terminal-boundary
   ordering, and cursor encoding/decoding in the focused domain module.
5. Compare terminal boundaries by
   `(occurred_at, source_kind_rank, source_id)`, where `chat_turn = 1` and
   `backtest_job = 2`.
6. Add memory parity in `AlphaStore`: one read-state map keyed by
   `(user_id, conversation_id)` plus a dedicated lock, and clear it during
   development reset.
7. Re-run the focused tests until green, then run Ruff and mypy on the touched
   Python surfaces.

## Task 2: Additive Supabase migration and gateway

**Files:**

- Create
  `supabase/migrations/20260801000000_add_conversation_activity_read_states.sql`.
- Create `src/argus/domain/supabase_conversation_activity.py`.
- Modify `src/argus/domain/supabase_gateway.py` only to register the focused
  mixin and development-reset table.
- Create `tests/test_conversation_activity_migration.py`.
- Create `tests/test_conversation_activity_postgres.py`.
- Extend focused Supabase gateway tests where contract call evidence belongs.

**Steps:**

1. Write failing static/migration and gateway tests before adding production
   SQL or gateway methods.
2. Create `conversation_read_states` with the approved read-through fields,
   manual-unread timestamp, audit timestamps, and
   `(user_id, conversation_id)` primary key.
3. Add a composite conversation-owner foreign key with `ON UPDATE CASCADE` and
   `ON DELETE CASCADE`, plus the required unique composite target on
   conversations. This must preserve guest claim and cleanup atomically without
   rewriting the large guest-handoff RPC.
4. Enable RLS. Grant owner `SELECT`; deny authenticated/anon writes; keep
   mutations service-role only.
5. Add bounded lifecycle/job indexes for owner, conversation, status, and
   terminal ordering.
6. Add service-only RPCs that:
   - reconcile at most 20 stale turns across supplied owned conversation ids
     using the existing evidence predicate;
   - read activity sources for at most 100 owned conversation ids in one
     bounded batch;
   - atomically mark unread or advance read-through after locking and
     revalidating the supplied source.
7. Add an idempotent keyset baseline of 500 conversations per batch. Capture a
   migration-start cutoff and mark only terminal boundaries at or before it as
   read so completions during rollout stay unread.
8. Do not mutate messages, conversations, jobs, runs, artifacts, or any sort
   timestamp.
9. Implement a focused gateway mixin; do not grow the main gateway with the
   feature logic. Register `conversation_read_states` in development reset
   before conversations.
10. Run focused static and mocked gateway tests. Then start/reset disposable
    Supabase and prove owner select, foreign/anon denial, stale-read safety,
    baseline behavior, post-cutoff unread behavior, guest-claim cascade,
    cleanup cascade, and bounded query counts.

## Task 3: API orchestration and projections

**Files:**

- Create `src/argus/api/conversation_activity.py`.
- Create `src/argus/api/routers/conversation_activity.py`.
- Modify `src/argus/api/main.py`.
- Modify `src/argus/api/routers/conversations.py`.
- Modify `src/argus/api/routers/history.py`.
- Extend `tests/test_alpha_api.py` and `tests/test_alpha_api_supabase.py`.

**Steps:**

1. Write failing API tests for activity on every emitted chat record, both
   actions, ordering preservation, guest rules, deleted/foreign `404`s, and
   validation/conflict responses.
2. Create one API service that selects memory or Supabase persistence. Reuse it
   from the activity routes, conversation responses, and history responses.
3. Register the focused router in FastAPI.
4. Project one bounded activity batch after conversation/history pagination;
   never query once per row.
5. Include activity on create, guest replacement, patch, conversation list,
   registered chat history rows, and the guest workspace history row. Omit it
   from non-chat history records.
6. Keep `mark_unread` idempotent and preserve read-through.
7. Make `mark_read(null)` clear only the manual flag. Make
   `mark_read(cursor)` advance monotonically through the verified boundary so a
   newer terminal boundary remains unread.
8. GET may invoke the approved bounded stale-turn reconciliation but must not
   mutate read state.
9. Run the focused API suites and verify existing pagination/order responses
   are byte-equivalent apart from the additive chat field.

## Task 4: Canonical docs and generated OpenAPI

**Files:**

- Modify `docs/PRODUCT.md`.
- Modify `docs/ARCHITECTURE.md`.
- Modify `docs/API_CONTRACT.md`.
- Modify `docs/DATA_MODEL.md`.
- Regenerate `docs/api/openapi.yaml`.
- Extend `tests/test_openapi_compatibility.py`.

**Steps:**

1. Document durable conversation activity/read truth and explicitly preserve
   chat-first, backend-canonical, bounded-read, ownership, and no-reordering
   rules.
2. Update OpenAPI tests for enums, optional additive fields, new routes,
   request unions, responses, and RFC 9457 errors.
3. Regenerate the artifact with
   `poetry run python scripts/generate_openapi_artifact.py`.
4. Defer DESIGN, locales, predecessor visual pointers, and roadmap completion
   claims to the UI/landing work.

## Task 5: Verification and Draft PR handoff

Run:

```bash
poetry run pytest \
  tests/test_conversation_activity.py \
  tests/test_conversation_activity_migration.py \
  tests/test_alpha_api.py \
  tests/test_alpha_api_supabase.py \
  tests/test_openapi_compatibility.py \
  tests/test_alpha_artifacts.py \
  -q --no-cov

supabase start
supabase db reset
eval "$(supabase status -o env)"
ARGUS_DISPOSABLE_DATABASE_URL="$DB_URL" \
  poetry run pytest tests/test_conversation_activity_postgres.py -q --no-cov

poetry run python scripts/generate_openapi_artifact.py
poetry run ruff check src tests
poetry run mypy src
poetry run python scripts/check_modularity_budget.py
poetry run pytest tests -q --no-cov
git diff --check
```

No browser QA or live LLM eval is required because this PR has no interpreter-
facing or visible UI change. Record exact-SHA evidence and finish at a Draft PR
targeting `codex/private-alpha-next`. Do not merge, apply a hosted migration,
deploy, or expose the change to testers.

## Atomic commit sequence

1. Existing rebased spec commit.
2. `docs(chat): plan activity and read foundation`.
3. `feat(data): add conversation read state`.
4. `feat(api): project conversation activity`.
5. `docs(chat): document activity API contract`.

## Stop conditions

- Stop if projection requires transcript prose scanning, N+1 reads, new failure
  semantics, changes to stale-turn evidence, or any conversation-order change.
- Stop if the composite ownership cascade cannot preserve guest claim and
  cleanup atomically.
- Stop if a missing-schema fallback would be required. Render auto-deploy is
  off; a later manual backend deployment must apply and read back the migration
  first.
- Do not continue into UI behavior, frontend types, failure styling,
  localization, browser QA, hosted migration, deploy, merge, or tester
  exposure.
