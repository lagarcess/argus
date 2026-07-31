# Omnisearch run dossiers — browse prior evidence and effective decisions without opening chat

Status: **FOUNDER-LOCKED**

Depends on the delivered Full Omnisearch contract in
`docs/superpowers/specs/2026-07-29-omnisearch-memory-recall.md` and PR #306
(`b71f1eaf`). This is a focused follow-up, not unfinished #306 work.

## 1. Why — turn the dossier into a compact evidence archive

PR #306 made each conversation row a deterministic memory dossier, but the
right pane still mixes three different anchors:

- the latest completed run;
- the latest saved decision anywhere in the conversation;
- conversation-wide tested/run-count facts.

That is technically truthful but easy to misread when a conversation contains
many runs. The current pane also repeats the same decision as a header chip, a
`Decision` field, and a separate `Your note` field.

The decision memo says Argus wins when ideas become tested, remembered,
compared, and trusted rather than remaining one-off chat output. The next small
step is to let the user inspect every finalized run and its current judgment
from Omnisearch without entering the transcript.

One sentence for the surface:

> The dossier shows one run at a time; decision history lets the user move
> through the conversation's evidence without leaving search.

## 2. Locked product behavior

### 2.1 Default dossier is anchored to one run

The default right-pane dossier is anchored to the conversation's latest
finalized, evidence-backed run. Every visible fact and action in that view must
refer to that same run:

- run label and completion date;
- symbols, strategy family, cadence/timeframe, and tested window;
- bounded outcome metrics;
- the current decision state and verbatim note for that run, if any;
- Change/Add decision;
- the existing rerun/retest action slot;
- Open in conversation.

The header may show entity/context chips such as `Current` and `Conversation`.
It must not repeat the selected run's decision state.

The visual hierarchy communicates meaning without repeating field labels:

```text
Latest run · Jul 31

GLD · Buy and hold · 1D · 1-year window
8.4% return · −6.2% worst drop

[Watching]  “Hold through earnings.”

[Run it fresh / Retest with current data]  [Change decision]

Decision history                         5 of 7 decided ›
```

`What you tested`, `How it went`, `Decision`, and `Your note` are not visible
headings in the default view. The note remains the user's exact stored text,
with whitespace/newlines preserved and quote treatment. A visually hidden
accessible label may identify the note for assistive technology.

### 2.2 Decision state and note are one unit

When a decision exists, render one state chip immediately beside or above its
verbatim note. Do not render the same state elsewhere in the pane.

When no decision exists, show one quiet `No decision saved` state and expose
`Add decision`. Do not invent a neutral durable state.

The editor remains attached to the selected run's evidence artifact:

- Enter inserts a newline in the note;
- Cmd+Enter on macOS and Ctrl+Enter elsewhere saves;
- Cancel and Save stay visibly available in a compact action rail;
- iconography may support the labels but must not replace accessible names;
- successful save collapses the editor and briefly acknowledges `Saved`;
- the dossier, history tally, left-row chips, and decision filters refresh from
  the canonical response rather than optimistic client reconstruction.

Outside the note editor, the existing palette keyboard contract remains intact.

### 2.3 One disclosure opens run-level decision history

The last dossier row is the only disclosure:

```text
Decision history                         5 of 7 decided ›
```

`decided` counts finalized evidence-backed runs with a current `DecisionNote`.
The denominator counts finalized evidence-backed runs that are eligible for a
decision. Failed attempts and incomplete/non-finalized runs remain transcript
artifacts and do not inflate this denominator.

Activating the disclosure replaces the dossier body with a secondary view in
the same right pane. It does not expand an unbounded accordion and does not
open the conversation.

```text
← Dossier                            Decision history

Jul 31 · GLD long-term hold
[Watching] “Hold through earnings.”

Jun 18 · GLD inflation hedge
[Rejected] “Drawdown was too high.”

May 02 · GLD breakout
No decision saved
```

The list is newest first and contains one row per finalized evidence-backed
run. Each row shows only that run's current effective decision and current
note. Today the data model stores one current decision per evidence artifact;
this view is not an edit-revision audit log and must not imply that older note
revisions exist.

### 2.4 Selecting history changes the dossier anchor, not the route

From the history view:

- Up/Down moves focus between run rows.
- Enter or Space selects the focused run and loads that run's dossier in the
  same pane.
- Escape or the Back control returns to the conversation's default dossier.
- Selecting a run never changes the browser route or opens the transcript.
- `Open in conversation` is the explicit navigation action. It opens the source
  conversation at the selected run's result/assistant artifact, not merely at
  the conversation bottom.
- Cmd/Ctrl+Enter is a save shortcut only while the decision editor owns focus;
  it is not a navigation shortcut.

The selected historical dossier exposes Change/Add decision for its own
evidence artifact. The rerun/retest action also targets the selected run. This
spec preserves the currently shipped `run_fresh` transport; the sibling typed
retest spec owns replacing it with `retest_run`.

### 2.5 Large histories are lazy and bounded

Do not attach every run dossier to every search result. The existing search row
keeps only its bounded default dossier and counts.

Opening Decision history performs a lazy owner-scoped read for the selected
conversation. The typed contract is:

```text
GET /conversations/{conversation_id}/run-dossiers
  ?limit=<bounded>
  &cursor=<opaque optional cursor>
```

The response contains:

- `items`: newest-first run dossier rows;
- `next_cursor`: opaque or null;
- `total_runs`;
- `decided_runs`.

The default and maximum limits must follow the existing bounded-read doctrine.
The initial target is 20 rows with an explicit `Load older` control when a
cursor remains. The client never synthesizes totals across cursor pages.

Each item contains only the bounded, sanitized facts needed to render and act:

- run identity and label;
- completed timestamp;
- message/result anchor for explicit transcript navigation;
- tested setup summary;
- bounded outcome metrics;
- current decision state and verbatim note, if any;
- backend-projected decision action for that evidence artifact;
- the existing backend-projected rerun action until the typed-retest lane
  replaces it.

Memory and Supabase/Postgres modes must produce the same ordered typed shape.
Guest access stays current-workspace and owner-scoped. Missing, deleted, or
unauthorized conversations return the existing conversation ownership/not-found
contract without leaking existence.

## 3. Architecture and ownership

### 3.1 Canonical truth

Project only existing durable facts:

```text
Conversation
  -> finalized BacktestRun
  -> EvidenceArtifact
  -> current DecisionNote (optional)
  -> source result message anchor
```

No new table, durable summary, decision revision log, RAG layer, embedding, or
generated recap is permitted.

### 3.2 Backend boundary

The conversations/API layer owns authentication, typed transport, bounded
cursor validation, and error shaping. Conversation recall/search-domain code
owns deterministic assembly from runs, evidence, decisions, and message
anchors. The endpoint must not become a second chat orchestrator.

Postgres reads must be bounded and indexed by existing ownership, conversation,
run, evidence, and decision relationships. If the required query cannot meet
the existing bounded-read budget without a migration, stop and present the
query plan and proposed index before adding schema.

### 3.3 Frontend modularity boundary

`web/components/sidebar/ChatCommandPalette.tsx` is already approximately 2,000
lines. This lane must reduce its responsibility rather than add the history
surface inline.

Extract cohesive dossier modules under the sidebar/command-palette surface,
including:

- the single-run dossier;
- decision history list;
- decision editor/action rail;
- lazy history loading state.

`ChatCommandPalette.tsx` retains palette orchestration and selection only.
Pure projections/formatting stay in focused library modules with direct tests.
New files should have one clear purpose; do not replace one oversized component
with another.

### 3.4 Parallel-lane edit ownership

This is the first integration lane and owns, until its PR merges:

- `web/components/sidebar/ChatCommandPalette.tsx`;
- extracted dossier/history/editor components;
- `web/lib/command-palette-items.ts` and focused successors;
- the search/conversation dossier response shape in `src/argus/api/schemas.py`;
- deterministic run-dossier assembly/read paths;
- dossier/history API contract, OpenAPI artifact, locales, and focused tests.

The sibling typed-retest lane may develop runtime/action work in parallel but
must not edit the palette, the dossier response shape, or shared schema file
until this lane lands. This lane must not implement `retest_run`, chat receipt
hydration, or retry semantics.

## 4. Acceptance

- A conversation with seven finalized evidence-backed runs opens on the latest
  run and shows `5 of 7 decided` when five have current decisions.
- Decision state appears exactly once in the selected dossier and is paired
  with the selected run's current verbatim note.
- Decision history opens and paginates inside the right pane without opening
  the conversation or loading the full transcript.
- History has one row per finalized evidence-backed run, newest first; two
  undecided runs render `No decision saved`.
- Selecting a prior run replaces the dossier anchor. Metrics, decision,
  Change/Add decision, rerun action, and explicit transcript jump all refer to
  that selected run.
- Editing a selected historical decision updates its existing history row;
  there is never an extra revision row.
- Enter creates a note newline; Cmd/Ctrl+Enter saves; mouse/touch users always
  have visible Cancel and Save controls.
- Search/Recents behavior, left-row match highlighting, decision filters,
  asset rollups, conversation isolation, and jump-to-match from PR #306 do not
  regress.
- Memory and Supabase/Postgres modes return equivalent typed results.
- EN and es-419 behave equivalently on desktop and mobile.
- Hover, focus, disclosure, history loading, decision save, and navigation make
  zero LLM, research, or market-data provider calls.

## 5. Verification gates

Before marking the PR ready:

- focused backend tests cover ordering, counts, ownership, cursor bounds,
  memory/Postgres parity, missing artifacts, and selected-run actions;
- focused frontend tests cover the default hierarchy, one decision rendering,
  history navigation, lazy pagination, previous-run selection, editor keyboard
  behavior, mutation refresh, route stability, and explicit transcript jump;
- `docs/API_CONTRACT.md` and `docs/api/openapi.yaml` are updated for every typed
  addition;
- full backend suite passes hermetically with the canonical `.env` moved aside
  and `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`;
- `bun test` passes in `web/`;
- ruff and `scripts/check_modularity_budget.py` pass;
- EN/es-419 browser QA passes on the mock-auth memory-mode stack;
- desktop and mobile evidence covers latest dossier, history, prior-run
  selection, decision edit/save, keyboard flow, and explicit transcript jump;
- the final review round addresses only confirmed, reachable findings
  proportional to this lane.

## 6. Execution contract

Mode: `normal_feature_branch`.

One branch and one PR deliver this entire spec from the current remote
`codex/private-alpha-next` head at dispatch time. Recommended branch:
`codex/omnisearch-dossier-history`.

Recommended internal commit order:

1. typed lazy run-dossier read and deterministic assembly;
2. extracted single-run dossier and decision editor;
3. decision-history secondary view and keyboard navigation;
4. API/OpenAPI/localization/QA closure.

Merge this lane before the sibling typed-retest PR. The founder merges.

## 7. Stop conditions

Stop and report if the implementation requires:

- a new durable dossier, summary, memory, or decision-revision model;
- loading the whole transcript or all runs without a cursor;
- client-computed totals or decision truth;
- hover/focus-time LLM, research, or provider calls;
- semantic/RAG retrieval;
- a migration without a measured bounded-query need and founder review;
- changing the existing decision states or inventing historical note revisions;
- growing `ChatCommandPalette.tsx` with the new history/editor implementation
  instead of extracting cohesive modules;
- shared palette/schema edits by both follow-up lanes at the same time.
