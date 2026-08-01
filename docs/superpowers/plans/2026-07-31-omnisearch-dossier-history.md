# Omnisearch Dossier History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Omnisearch show one canonical finalized run dossier at a time and lazily browse every finalized evidence-backed run with its current effective decision.

**Architecture:** A shared deterministic projector assembles a bounded `RunDossier` from one completed run, its evidence artifact, current decision, and result-message anchor. Search uses that projector for its latest eligible run, while a new owner-scoped conversations endpoint reads paginated source rows through memory or an indexed Postgres reader; the frontend consumes both through extracted dossier, editor, history, and loading-state modules.

**Tech Stack:** Python 3.10, FastAPI, Pydantic v2, psycopg/Postgres, pytest, TypeScript, React/Next.js, i18next, Bun, Testing Library, Playwright.

## Global Constraints

- Base all work on exact integration commit `acbf1c3070f0e2b9dd3dd797eb80c119a87a6d6a`.
- Treat `docs/superpowers/specs/2026-07-31-omnisearch-dossier-history.md` as founder-locked even though its checked-in status line predates the founder's lock instruction.
- Project only existing `Conversation -> finalized BacktestRun -> EvidenceArtifact -> current DecisionNote -> result message` facts.
- Add no table, migration, durable summary, decision revision log, RAG layer, embedding, generated recap, LLM call, research call, or market-data provider call.
- Preserve the shipped `run_fresh` transport; do not add `retest_run`, receipt hydration, retry semantics, or sibling-lane behavior.
- Return only completed, evidence-backed, decision-eligible runs; failed, incomplete, and evidence-less runs do not affect `total_runs` or `decided_runs`.
- Default `limit` is 20 and maximum `limit` is 100; pagination uses the repository's opaque `(completed_at, run_id)` cursor.
- Missing, deleted, and unauthorized conversations use the existing non-leaking 404 contract; guests may read only their current workspace conversation.
- `ChatCommandPalette.tsx` retains orchestration and selection only and must shrink from its approximately 2,000-line starting point.
- Decision notes are rendered verbatim with newlines preserved; the client never reconstructs decision truth or totals optimistically.
- Static UI is equivalent in English (`en`) and Spanish (`es-419`) on desktop and mobile.

---

### Task 1: Typed run dossier projection and lazy read

**Files:**
- Create: `src/argus/domain/run_dossiers.py`
- Create: `src/argus/domain/postgres_run_dossier_reader.py`
- Create: `src/argus/api/memory_run_dossiers.py`
- Create: `tests/test_run_dossiers.py`
- Create: `tests/test_run_dossiers_postgres.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/conversation_recall.py`
- Modify: `src/argus/domain/postgres_search_reader.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Modify: `src/argus/api/routers/conversations.py`
- Modify: `tests/test_alpha_api.py`
- Modify: `tests/test_search_bounded_reads.py`
- Modify: `tests/test_search_postgres.py`
- Modify: `tests/test_openapi_compatibility.py`
- Modify: `docs/superpowers/specs/2026-07-31-omnisearch-dossier-history.md`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `docs/api/openapi.yaml`

**Interfaces:**
- Consumes: existing `SearchRunFreshAction`, `SearchDecisionAction`, `DecisionState`, `encode_cursor`, `decode_cursor`, and existing run/evidence/decision payloads.
- Produces: `project_run_dossier(*, run, artifact, decision, result_message_id, allow_decision_action, language) -> RunDossier`; `PostgresRunDossierReader.list_source_rows(*, user_id, conversation_id, limit, cursor_completed_at, cursor_run_id) -> RunDossierSourcePage`; `GET /api/v1/conversations/{conversation_id}/run-dossiers`; `PaginatedRunDossiers`.

- [ ] **Step 1: Lock the typed API contract in tests and prose**

Add schema assertions and endpoint examples that require this shape:

```python
class RunDossierTested(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=5)
    strategy_family: str | None = Field(default=None, max_length=80)
    cadence: str | None = Field(default=None, max_length=24)
    timeframe: str | None = Field(default=None, max_length=24)
    start_date: date | None = None
    end_date: date | None = None


class RunDossier(BaseModel):
    run_id: str
    run_label: str = Field(max_length=160)
    completed_at: datetime
    result_message_id: str | None = None
    tested: RunDossierTested
    outcome: SearchDossierOutcome
    decision: SearchDossierDecision | None = None
    actions: list[SearchDossierAction] = Field(default_factory=list, max_length=2)


class PaginatedRunDossiers(BaseModel):
    items: list[RunDossier]
    next_cursor: str | None = None
    total_runs: int = Field(ge=0)
    decided_runs: int = Field(ge=0)
```

Change `SearchItem.dossier` to `RunDossier | None`, add server-owned `total_runs` and `decided_runs`, and remove the duplicate item-level `actions`; ordinary recalled conversations with no finalized evidence-backed run retain a null dossier and `0/0` counts, while every present default fact and action must share the dossier's `run_id`.

Document the exact `GET /api/v1/conversations/{conversation_id}/run-dossiers?limit=20&cursor=...` request, response, limits, eligibility rule, owner/guest rule, nullable result anchor, and non-leaking errors in `docs/API_CONTRACT.md`. Clarify in `docs/DATA_MODEL.md` that the endpoint is a projection over existing records and stores nothing.
Update only the spec's stale status metadata to `FOUNDER-LOCKED`; do not rewrite its product behavior.

- [ ] **Step 2: Run contract tests to verify RED**

Run:

```bash
poetry run pytest tests/test_run_dossiers.py tests/test_alpha_api.py tests/test_openapi_compatibility.py -q --no-cov
```

Expected: FAIL because `RunDossier`, `PaginatedRunDossiers`, and the endpoint do not exist and the search dossier is still conversation-mixed.

- [ ] **Step 3: Implement one-run deterministic assembly**

Move the one-run-only projections out of `conversation_recall.py` into `run_dossiers.py`. The public projector must:

```python
def project_run_dossier(
    *,
    run: Mapping[str, Any],
    artifact: Mapping[str, Any],
    decision: Mapping[str, Any] | None,
    result_message_id: str | None,
    allow_decision_action: bool,
    language: str,
) -> RunDossier:
    ...
```

It returns symbols, one strategy family, cadence/timeframe, tested dates, at most four metrics, current state/note, the artifact-specific decision action, and the existing run-specific `run_fresh` action. Preserve note text except the existing 2,000-character storage/transport bound; do not strip or normalize internal whitespace.

Refactor `project_conversation_recall` to:

```python
eligible = newest_evidence_backed_completed_runs(...)
latest_run, latest_artifact = eligible[0]
dossier = project_run_dossier(
    run=latest_run,
    artifact=latest_artifact,
    decision=current_decision_for(latest_artifact),
    result_message_id=result_message_id_for(latest_run, conversation_messages),
    allow_decision_action=allow_decision_action,
    language=language,
)
```

Search must return `total_runs` and `decided_runs` from canonical backend summaries or deterministic owned rows, never from client-side page accumulation.
Update `_CONVERSATION_HYDRATION_SQL` in `postgres_search_reader.py` so its latest selected run is completed and evidence-backed and its decision belongs to that selected run; keep the existing bounded search hydration discipline.

- [ ] **Step 4: Implement bounded memory and Postgres reads**

Create `memory_run_dossiers.py` for the bounded in-memory source selection and a focused Postgres reader with parameterized SQL that returns at most `limit + 1` eligible rows plus scalar total/decided counts. Keyset ordering is:

```sql
ORDER BY br.completed_at DESC, br.id DESC
```

Eligibility joins one evidence artifact to a completed run owned by the conversation owner, chooses the current effective decision for that artifact, and resolves the latest assistant message whose metadata points to the run. Use existing indexes only; do not add a migration. Wire the reader through `SupabaseGateway.from_env`.

The route must:

```python
@router.get(
    "/conversations/{conversation_id}/run-dossiers",
    response_model=PaginatedRunDossiers,
)
def list_run_dossiers(
    conversation_id: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),
) -> PaginatedRunDossiers:
    ...
```

Reject missing/deleted/not-owned conversations as 404 before projection. In guest mode also require the active guest workspace's `conversation_id` to match. The memory path must take bounded snapshots under the store lock and project the same ordered typed shape as Postgres. Generate `next_cursor` only from the final returned row when the reader fetched `limit + 1`.
Validate that a cursor pivot still identifies an eligible run in the same owned conversation; malformed, stale, or foreign pivots return the existing invalid-cursor response without revealing ownership.

- [ ] **Step 5: Cover ordering, counts, isolation, parity, and actions**

Add focused tests with seven completed evidence-backed runs, five current decisions, two undecided runs, one failed run, one incomplete run, and one completed run without evidence. Assert:

```python
assert [item.run_id for item in page.items] == newest_first_ids[:20]
assert page.total_runs == 7
assert page.decided_runs == 5
assert page.items[0].actions[0].source_run_id == page.items[0].run_id
assert decision_action(page.items[0]).evidence_artifact_id == latest_artifact_id
assert page.items[0].result_message_id == latest_result_message_id
```

Also assert page 2 has no duplicate IDs; invalid/over-bound cursors return validation errors; missing/deleted/other-owner conversations return indistinguishable 404s; guest access is limited to its active workspace; missing evidence is excluded; a missing result message yields `result_message_id=None`; note newlines survive; memory and fake-Postgres sources serialize identically; and search's default dossier/counts match the first history item/page totals.

- [ ] **Step 6: Regenerate OpenAPI and verify GREEN**

Run:

```bash
poetry run python scripts/generate_openapi_artifact.py
poetry run pytest tests/test_run_dossiers.py tests/test_run_dossiers_postgres.py tests/test_alpha_api.py tests/test_search_bounded_reads.py tests/test_search_postgres.py tests/test_openapi_compatibility.py -q --no-cov
poetry run ruff check src/argus/domain/run_dossiers.py src/argus/domain/postgres_run_dossier_reader.py src/argus/api/routers/conversations.py src/argus/api/schemas.py tests/test_run_dossiers.py tests/test_run_dossiers_postgres.py
```

Expected: PASS with no provider credentials and no schema migration.

- [ ] **Step 7: Commit the typed backend slice**

```bash
git add docs/superpowers/plans/2026-07-31-omnisearch-dossier-history.md docs/superpowers/specs/2026-07-31-omnisearch-dossier-history.md docs/API_CONTRACT.md docs/DATA_MODEL.md docs/api/openapi.yaml src/argus/api/schemas.py src/argus/api/routers/conversations.py src/argus/api/memory_run_dossiers.py src/argus/domain/conversation_recall.py src/argus/domain/postgres_search_reader.py src/argus/domain/run_dossiers.py src/argus/domain/postgres_run_dossier_reader.py src/argus/domain/supabase_gateway.py tests/test_run_dossiers.py tests/test_run_dossiers_postgres.py tests/test_alpha_api.py tests/test_search_bounded_reads.py tests/test_search_postgres.py tests/test_openapi_compatibility.py
git commit -m "feat(api): add lazy run dossier history"
```

### Task 2: Extract the single-run dossier and decision editor

**Files:**
- Create: `web/components/sidebar/command-palette/RunDossierView.tsx`
- Create: `web/components/sidebar/command-palette/DecisionEditor.tsx`
- Create: `web/lib/run-dossier-items.ts`
- Create: `web/lib/run-dossier-contract.ts`
- Create: `web/lib/run-dossiers-api.ts`
- Create: `web/__tests__/run-dossier-items.test.ts`
- Create: `web/__tests__/run-dossier-view.test.tsx`
- Modify: `web/lib/search-contract.ts`
- Modify: `web/lib/command-palette-items.ts`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`

**Interfaces:**
- Consumes: Task 1 `RunDossier`, `SearchDecisionAction`, `SearchRunFreshAction`, and `SearchItem.total_runs/decided_runs`.
- Produces: `RunDossierView`; `DecisionEditor`; `formatRunDossierSetup`; `formatRunDossierMetrics`; `listRunDossiers(conversationId, options)`.

- [ ] **Step 1: Add failing projection and component tests**

Define the reusable run-dossier client contract exactly once in `run-dossier-contract.ts`; import it into `search-contract.ts` so `result_message_id`, dossier-owned `actions`, and server counts cannot drift. Use the repository's dependency-free frontend test pattern: `renderToStaticMarkup` for presentation and pure exported keyboard/state helpers for interaction logic. Test the default view with:

```tsx
const html = renderToStaticMarkup(
  <RunDossierView
    dossier={dossierWithWatchingDecisionAndMultilineNote}
    totalRuns={7}
    decidedRuns={5}
    onOpenHistory={onOpenHistory}
    onOpenConversation={onOpenConversation}
    onRunFresh={onRunFresh}
    onSaveDecision={onSaveDecision}
  />,
);
```

Assert `Watching` appears exactly once, the note preserves its newline, and visible text does not contain `What you tested`, `How it went`, `Decision`, or `Your note`. Assert the header has context chips but no decision chip. For an undecided run assert one `No decision saved` and `Add decision`.

- [ ] **Step 2: Run frontend tests to verify RED**

Run:

```bash
cd web
bun test __tests__/run-dossier-items.test.ts __tests__/run-dossier-view.test.tsx
```

Expected: FAIL because the extracted modules and new contract do not exist.

- [ ] **Step 3: Implement pure one-run formatting**

Create side-effect-free helpers:

```ts
export function formatRunDossierSetup(
  dossier: RunDossier,
  t: TFunction,
  locale: string,
): string[];

export function formatRunDossierMetrics(
  dossier: RunDossier,
  t: TFunction,
  locale: string,
): Array<{ name: string; value: string }>;
```

They format only backend-provided values, never infer a decision, total, setup, or metric. Retain bounded arrays and use locale-aware dates/numbers.

- [ ] **Step 4: Implement the extracted dossier and editor**

`RunDossierView` renders:

```text
<run label> · <localized completion date>
<symbols> · <strategy family> · <cadence/timeframe> · <tested window>
<bounded metric values>
<one decision chip> <verbatim note>
[Run it fresh] [Change/Add decision]
Decision history <decidedRuns> of <totalRuns> decided
Open in conversation
```

Use `white-space: pre-wrap` plus a visually hidden note label. Keep `Decision history` as the last dossier row and only disclosure. Disable `Open in conversation` accessibly when `result_message_id` is absent.

`DecisionEditor` is controlled and attached to the dossier's backend decision action. A plain Enter changes the textarea. Only `event.metaKey || event.ctrlKey` with Enter calls save and prevents the newline. Cancel and Save remain visible. A successful save collapses and exposes a brief polite `Saved` status; errors preserve draft text and show the existing mutation error treatment.

- [ ] **Step 5: Reduce palette orchestration**

Remove the inline dossier field rendering, decision editor, and decision header chip from `ChatCommandPalette.tsx`. It may own selected search item, current anchored dossier, secondary-view mode, and callbacks, but delegates presentation. Update `command-palette-items.ts` to stop building the removed repeated dossier headings.

Add a focused API wrapper that imports the existing exported `apiFetch`:

```ts
export async function listRunDossiers(
  conversationId: string,
  options: { limit?: number; cursor?: string } = {},
): Promise<PaginatedRunDossiers>;
```

Use the same authenticated API client and Problem Details handling as other reads.

- [ ] **Step 6: Verify GREEN and modularity improvement**

Run:

```bash
cd web
bun test __tests__/run-dossier-items.test.ts __tests__/run-dossier-view.test.tsx __tests__/command-palette-items.test.ts
cd ..
python scripts/check_modularity_budget.py
wc -l web/components/sidebar/ChatCommandPalette.tsx web/components/sidebar/command-palette/RunDossierView.tsx web/components/sidebar/command-palette/DecisionEditor.tsx
```

Expected: tests and budget PASS; `ChatCommandPalette.tsx` is materially below 1,977 lines and no new extracted component becomes an oversized replacement.

- [ ] **Step 7: Commit the extracted dossier slice**

```bash
git add web/components/sidebar/ChatCommandPalette.tsx web/components/sidebar/command-palette/RunDossierView.tsx web/components/sidebar/command-palette/DecisionEditor.tsx web/lib/search-contract.ts web/lib/run-dossier-contract.ts web/lib/run-dossiers-api.ts web/lib/command-palette-items.ts web/lib/run-dossier-items.ts web/__tests__/run-dossier-items.test.ts web/__tests__/run-dossier-view.test.tsx
git commit -m "refactor(web): extract Omnisearch run dossier"
```

### Task 3: Lazy decision history and selected-run navigation

**Files:**
- Create: `web/components/sidebar/command-palette/DecisionHistoryView.tsx`
- Create: `web/components/sidebar/command-palette/useRunDossierHistory.ts`
- Create: `web/__tests__/decision-history-view.test.tsx`
- Create: `web/__tests__/run-dossier-history.test.tsx`
- Modify: `web/components/sidebar/command-palette/RunDossierView.tsx`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Create: `web/__tests__/chat-command-palette.test.tsx`

**Interfaces:**
- Consumes: Task 2 `RunDossierView`, `listRunDossiers`, and selected search-row orchestration.
- Produces: `DecisionHistoryView`; `useRunDossierHistory`; selected historical dossier state without route mutation.

- [ ] **Step 1: Write failing lazy-load and keyboard tests**

Assert the endpoint is not called until the disclosure is activated, then called with `limit=20`. Seed page 1 with five rows and `next_cursor`, page 2 with two rows, while both responses retain server values `total_runs=7` and `decided_runs=5`.

Test:

```tsx
await user.click(screen.getByRole("button", { name: /decision history/i }))
expect(listRunDossiers).toHaveBeenCalledTimes(1)
await user.keyboard("{ArrowDown}{Enter}")
expect(onSelectRun).toHaveBeenCalledWith(secondRun)
expect(onOpenConversation).not.toHaveBeenCalled()
```

Also cover Space selection, ArrowUp bounds, Escape/Back restoration, explicit `Load older`, no duplicate page rows, loading/error/retry states, and no route/history API mutation while selecting.

- [ ] **Step 2: Run history tests to verify RED**

Run:

```bash
cd web
bun test __tests__/decision-history-view.test.tsx __tests__/run-dossier-history.test.tsx __tests__/chat-command-palette.test.tsx
```

Expected: FAIL because the secondary view and lazy state do not exist.

- [ ] **Step 3: Implement lazy canonical history state**

`useRunDossierHistory` owns:

```ts
type RunDossierHistoryState = {
  items: RunDossier[];
  nextCursor: string | null;
  totalRuns: number;
  decidedRuns: number;
  status: "idle" | "loading" | "ready" | "error";
};
```

It fetches only after `open()`, appends older pages by `run_id`, always replaces totals from the latest server response, supports retry, and exposes `refresh()` after a decision mutation. It does not fetch messages/transcripts or reconstruct dossiers.

- [ ] **Step 4: Implement the same-pane history view**

Render newest-first compact rows with localized date/run label and exactly one current state/note unit, or `No decision saved`. Use roving focus with `aria-activedescendant` or direct row focus:

- ArrowDown/ArrowUp moves within loaded rows.
- Enter/Space selects the focused row.
- Escape and the visible Back control restore the default latest-run dossier.
- `Load older` is a visible button only when `next_cursor` exists.

Selecting changes `anchoredDossier` and renders `RunDossierView` in the same pane. It does not call `router.push`, `history.pushState`, the transcript loader, or the open-conversation callback.

- [ ] **Step 5: Wire canonical mutation refresh and transcript jump**

When a historical decision saves:

```ts
await createEvidenceDecision(...);
await Promise.all([
  refreshCanonicalSearch(),
  history.refresh(),
]);
```

Replace the selected dossier with the refreshed item having the same `run_id`; if it no longer exists, return to the canonical default dossier. This refreshes the dossier, history row/tally, left-row chip, and decision filters from backend truth.

`Open in conversation` must pass the selected dossier's `result_message_id` to the existing source-conversation opening path. It may close the palette and change route only for this explicit action. Cmd/Ctrl+Enter remains owned by the focused editor and must not trigger palette navigation.

- [ ] **Step 6: Verify history GREEN and regressions**

Run:

```bash
cd web
bun test __tests__/decision-history-view.test.tsx __tests__/run-dossier-history.test.tsx __tests__/run-dossier-view.test.tsx __tests__/chat-command-palette.test.tsx __tests__/command-palette-items.test.ts
cd ..
python scripts/check_modularity_budget.py
```

Expected: PASS with lazy reads, stable route selection, exact transcript anchor, and no palette file-budget regression.

- [ ] **Step 7: Commit decision history**

```bash
git add web/components/sidebar/ChatCommandPalette.tsx web/components/sidebar/command-palette/RunDossierView.tsx web/components/sidebar/command-palette/DecisionHistoryView.tsx web/components/sidebar/command-palette/useRunDossierHistory.ts web/__tests__/decision-history-view.test.tsx web/__tests__/run-dossier-history.test.tsx web/__tests__/chat-command-palette.test.tsx
git commit -m "feat(web): add dossier decision history"
```

### Task 4: Localization, browser acceptance, and verification closure

**Files:**
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Create: `web/__tests__/locales.test.ts`
- Create: `docs/qa/2026-07-31-omnisearch-dossier-history.md`
- Modify: focused files only if a verification gate reveals a confirmed, reachable issue.

**Interfaces:**
- Consumes: Tasks 1-3 complete dossier-history feature.
- Produces: equivalent EN/es-419 copy, desktop/mobile browser evidence, hermetic suite evidence, final review evidence.

- [ ] **Step 1: Add failing locale parity assertions**

Add every new key to both locales, including:

```text
Decision history
{decided} of {total} decided
Dossier
No decision saved
Add decision
Change decision
Open in conversation
Load older
Saved
Could not load decision history
Try again
```

Spanish must use natural es-419 equivalents and identical interpolation variables. Run:

```bash
cd web
bun test __tests__/locales.test.ts
```

Expected before implementation: FAIL on missing keys/parity.

- [ ] **Step 2: Implement localization and verify focused suites**

Add the locale values, replace hard-coded visible strings in extracted components, and run:

```bash
cd web
bun test __tests__/locales.test.ts __tests__/run-dossier-view.test.tsx __tests__/decision-history-view.test.tsx __tests__/run-dossier-history.test.tsx
cd ..
poetry run pytest tests/test_run_dossiers.py tests/test_run_dossiers_postgres.py tests/test_alpha_api.py tests/test_search_bounded_reads.py tests/test_search_postgres.py tests/test_openapi_compatibility.py -q --no-cov
```

Expected: PASS in both locales.

- [ ] **Step 3: Run hermetic backend and frontend gates**

Move only the worktree `.env` symlink aside, restore it with a shell trap, and never read or print its target values:

```bash
env_link_backup="$(mktemp -d)/argus-env-link"
mv .env "$env_link_backup"
trap 'mv "$env_link_backup" .env' EXIT
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
poetry run pytest tests/ -q
```

Then run:

```bash
cd web
bun test
cd ..
poetry run ruff check .
python scripts/check_modularity_budget.py
poetry run pytest tests/agent_runtime tests/test_spine_guardrails.py -q --no-cov
poetry run pytest tests/test_openapi_compatibility.py tests/test_alpha_artifacts.py -q --no-cov
git diff --check
```

Expected: every gate PASS without an LLM, research, or market-data provider call.

- [ ] **Step 4: Perform EN/es-419 desktop and mobile browser QA**

Start the mock-auth memory-mode backend with blank provider keys and synthetic data, and start the frontend without editing the linked env files. Seed one conversation with seven finalized evidence-backed runs, five decisions, two undecided runs, and anchored assistant result messages through local test/setup APIs or an in-memory fixture.

At desktop width 1440 and mobile width 390, verify in both locales:

- latest dossier opens with `5 of 7 decided`;
- decision state appears once beside a newline-preserving note;
- history loads lazily in the same right pane and paginates;
- selecting a prior run leaves the route unchanged;
- selected metrics, decision action, `run_fresh`, and transcript anchor share one run ID;
- Enter inserts a newline and Cmd/Ctrl+Enter saves;
- visible Cancel/Save work by mouse/touch;
- save shows `Saved` and canonical refresh updates the row/tally/filters;
- explicit Open in conversation lands on the selected result message;
- hover, focus, disclosure, editing, and navigation make zero provider calls.

Save screenshots and request/network evidence under `output/playwright/omnisearch-dossier-history/` and record exact commands, viewport, locale, result, and evidence paths in the QA note.

- [ ] **Step 5: Run proportional final review and fix only confirmed findings**

Review the complete diff against the locked spec, issue #309, security/owner scope, API/OpenAPI consistency, no-new-model/provider boundaries, selected-run action correctness, keyboard accessibility, localization, and modularity. For every finding record reachability, severity, affected users/artifacts, evidence, and the smallest safe fix. Do not expand scope into typed retest or unchanged code.

After any fix, rerun the smallest affected focused test plus:

```bash
git diff --check
python scripts/check_modularity_budget.py
```

- [ ] **Step 6: Commit verification closure**

```bash
git add web/public/locales/en/common.json web/public/locales/es-419/common.json web/__tests__/locales.test.ts docs/qa/2026-07-31-omnisearch-dossier-history.md
git add -u
git commit -m "test(search): close dossier history acceptance"
```

### Task 5: Founder-approved dossier refinement

**Files:**
- Create: `web/components/sidebar/command-palette/DecisionNoteDisplay.tsx`
- Create: `web/lib/decision-note.ts`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/search_text.py`
- Modify: `web/lib/search-text.ts`
- Modify: `web/components/chat/StrategyResultCard.tsx`
- Modify: `web/components/sidebar/command-palette/DecisionEditor.tsx`
- Modify: `web/components/sidebar/command-palette/RunDossierView.tsx`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Modify: `web/components/sidebar/command-palette/DecisionHistoryView.tsx`
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Modify: `web/public/locales/en/common.json`
- Modify: `web/public/locales/es-419/common.json`
- Test: focused backend, OpenAPI, frontend projection, component, and locale suites.

**Interfaces:**
- Consumes: the existing `DecisionNoteCreate`, `search_query_is_indexable`,
  `SearchRunFreshAction`, `SearchDecisionAction`, and canonical mutation refresh.
- Produces: a 500-character write contract, two-character symbol-only search,
  `DecisionNoteDisplay`, and the founder-approved dossier hierarchy/copy.

- [ ] **Step 1: Lock write compatibility and symbol-only search in failing tests**

Assert that `DecisionNoteCreate` accepts exactly 500 characters and rejects
501, while response projections still accept a legacy note up to the existing
2,000-character read bound. Assert that two-character symbol-shaped queries are
eligible, two-character multi-word/text queries remain deferred, and the
Postgres and memory paths return only the owner-scoped asset rollup for a
symbol-only query.

- [ ] **Step 2: Verify backend RED, then implement the minimal contract**

Run the focused schema/search/OpenAPI tests and confirm failures are caused by
the old 2,000-character request cap and shared three-character symbol gate.
Introduce separate text-token and symbol-query minimums, change only the write
schema to 500, regenerate OpenAPI, and rerun the focused tests to green.

- [ ] **Step 3: Lock UI behavior in failing component and locale tests**

Require the shared 500-character constant and near-limit counter in both
existing editors; a five-line `DecisionNoteDisplay` with accessible expanded
state; state and compact `Edit` action in one row; `Retest setup` in the card
header with localized confirmation tooltip; registered/guest asset-rollup
scope copy; two-character search helper copy; and arrow-only accessible backs.

- [ ] **Step 4: Implement the extracted UI and verify focused GREEN**

Create `DecisionNoteDisplay.tsx` rather than growing `RunDossierView.tsx`.
Keep the note in normal document flow, retain exact whitespace in the DOM, and
reset disclosure when the selected run/note changes. Move only the existing
`run_fresh` control; do not change its action payload or handler. Use the shared
note limit in the chat and Omnisearch editors and keep chat decision capture
add-only.

- [ ] **Step 5: Verify both locales in the browser**

At desktop and mobile widths, exercise a 500-character multiline note, expand
and collapse it, open the editor, confirm the compact target and counter, use a
two-character stored symbol query, and inspect registered and guest scope copy.
Confirm the panel alone scrolls and every interaction makes zero provider/LLM
calls.

- [ ] **Step 6: Commit the refinement as one reversible product slice**

Stage only the approved spec, contract, implementation, tests, locales, and QA
evidence. Use a conventional commit and keep the previously approved compact
metrics/scroll commit independent.

### Task 6: Ready pull request and CI

**Files:**
- Modify: no product files unless CI or review finds a confirmed in-scope defect.

**Interfaces:**
- Consumes: verified commits from Tasks 1-4.
- Produces: one pushed branch and one ready PR targeting `codex/private-alpha-next`; no merge.

- [ ] **Step 1: Confirm exact lineage and clean state**

Run:

```bash
git fetch origin codex/private-alpha-next
git merge-base --is-ancestor acbf1c3070f0e2b9dd3dd797eb80c119a87a6d6a HEAD
git diff --check origin/codex/private-alpha-next...HEAD
git status --short
git log --oneline --decorate origin/codex/private-alpha-next..HEAD
```

Expected: exact requested base is an ancestor, changes are only issue #309, and the worktree is clean.

- [ ] **Step 2: Push and open a ready PR**

Push `codex/omnisearch-dossier-history`, then create a non-draft PR targeting `codex/private-alpha-next` with:

- Summary, Changes, Motivation, Impact, Testing, Risks/Rollback, and Checklist sections;
- `Closes #309`;
- exact base and head SHAs;
- explicit no-migration, no-provider/LLM, no-typed-retest statements;
- backend/frontend/OpenAPI/modularity/browser-QA evidence;
- labels `enhancement`, `api`, and `web`.

- [ ] **Step 3: Wait for all required CI and review signals**

Use bounded CI polling. If a check fails, inspect the exact failing log, fix only a confirmed in-scope defect with a focused test, commit, push, and rerun the affected local gate. Do not merge, deploy, call `/validate`, or weaken a test/gate.

Expected terminal state: PR is open, ready for review, mergeable, all required checks green, and no unresolved actionable review threads.

- [ ] **Step 4: Stop at founder handoff**

Record the PR URL, branch/head SHA, green checks, browser evidence, and any non-blocking residual risk. Do not merge the PR or close issue #309; the founder performs the merge.
