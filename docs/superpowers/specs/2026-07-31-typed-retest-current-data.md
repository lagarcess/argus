# Typed retest with current data — deterministic confirmation, durable receipt, existing recovery

Status: **PROPOSED — awaiting founder lock**

Depends on the delivered Full Omnisearch contract in
`docs/superpowers/specs/2026-07-29-omnisearch-memory-recall.md` and PR #306
(`b71f1eaf`). It is designed to develop alongside the run-dossier-history lane
and to reconcile after that lane lands.

## 1. Why — make a supported product action behave like one

PR #306's `Run it fresh` action correctly preserves a prior supported setup,
moves the window to the present, opens the source conversation, and asks for a
new Ready-to-run confirmation without auto-executing.

Its current transport is intentionally transitional: the frontend submits a
long generated natural-language prompt and asks the ordinary interpreter to
reconstruct the expected confirmation. That makes a deterministic product
action depend on LLM interpretation and exposes the transcript to noisy raw
prompt text. In the live demo, an interpretation/composition failure rendered
the existing amber recovery block and in-place Retry button.

The product intent is already structured. The transport should be structured
too.

One sentence for the surface:

> Retest replays a stored supported experiment onto today's matching window,
> shows the user exactly what was requested, and always stops for confirmation.

## 2. Locked product behavior

### 2.1 Rename the action around user intent

The visible action becomes:

```text
Retest with current data
```

After selection, the user turn is a neutral structured receipt rather than the
generated raw prompt:

```text
↻ Retest with current data
GLD · Buy and hold · same 1-year duration
```

The icon is decorative; accessible text names the action. The second line is
backend-derived, sanitized display context:

- bounded symbols;
- strategy family;
- same-duration description.

The receipt is neutral because the user's request is valid. Amber belongs to a
system recovery response, not to the submitted action.

### 2.2 Typed request envelope

The client submits only stable identity and policy:

```json
{
  "type": "retest_run",
  "labelKey": "command_palette.retest_current_data",
  "payload": {
    "source_run_id": "uuid",
    "window_policy": "same_duration_ending_today",
    "contract_version": "argus_retest_run/v1"
  }
}
```

The only accepted values in v1 are:

- `type = "retest_run"`;
- `window_policy = "same_duration_ending_today"`;
- `contract_version = "argus_retest_run/v1"`.

The frontend must not submit an executable canonical setup, dates, symbols,
strategy parameters, benchmark, sizing, costs, or assumptions as authority.
Any client-provided display label is non-authoritative.

### 2.3 Backend reloads and validates canonical truth

After normal authentication/admission, the backend:

1. validates the bounded typed envelope;
2. owner-checks the source run and its source conversation;
3. requires the action conversation to equal the source conversation;
4. requires a finalized completed run with canonical supported setup and
   evidence identity;
5. reloads all executable fields from the stored run/result artifact;
6. reruns the existing deterministic support checks used by `run_fresh`;
7. computes the new window using the server clock;
8. materializes the normal Ready-to-run confirmation artifact;
9. persists the canonical structured user receipt and assistant confirmation;
10. returns without execution.

The window preserves the original calendar-day span:

```text
new_end = server_today
new_start = server_today - (original_end - original_start)
```

The clock must be injectable in deterministic tests. Existing same-asset,
maximum-symbol, supported-strategy, benchmark, sizing, execution-realism, and
date/data-window guardrails remain authoritative.

The action does not call the LLM, research provider, asset-discovery provider,
or market-data provider. Market data is fetched only if the user subsequently
approves the ordinary confirmation and launches the backtest.

### 2.4 LangGraph remains the only chat brain

`retest_run` is an explicit product operation, like other structured artifact
actions. The FastAPI router owns auth, admission, quota/idempotency where
applicable, persistence, transport, and error shaping. A focused deterministic
runtime action handler owns canonical reload and confirmation materialization.

Do not add a second orchestrator in the router and do not send the action
through natural-language interpretation. The typed action enters the existing
LangGraph/action path with an explicit semantic operation and zero LLM calls.

### 2.5 Receipt persistence and reload

The API must replace untrusted client display fields with a backend-generated
receipt projection before persistence. Persist structured values, not localized
prose:

- action type/version/policy;
- source run identity;
- bounded symbols;
- canonical strategy-family identifier;
- original duration in calendar days;
- optional cadence/timeframe identifiers needed for the compact receipt.

The transcript hydrates EN or es-419 copy from those structured values. Reload,
retry, conversation switching, and browser refresh must render the same receipt
without reloading the old raw prompt and without reconstructing execution state
in the client.

The long `send_text` and client-authoritative `canonical_setup` fields are
removed from the Omnisearch action after the frontend migrates. Search projects
a bounded typed `retest_run` action for the anchored run instead.

### 2.6 Success path

Selecting Retest:

1. disables while another turn is in flight;
2. opens/loads the source conversation using the shipped conversation-isolation
   contract;
3. submits the typed action only after that conversation is ready;
4. appends the neutral user receipt;
5. appends the normal Ready-to-run confirmation card;
6. never launches the run automatically.

The confirmation clearly shows the new concrete dates and the preserved setup.
The user can approve, change assumptions through existing controls, or cancel.

When run-dossier history is present, the action targets whichever run dossier
is selected, not necessarily the latest run.

### 2.7 Failure and retry reuse the existing family

Do not invent a generic `retest_failed` taxonomy. Map failures to the closest
existing canonical behavior:

- stale, deleted, unauthorized, wrong-conversation, or no-longer-actionable
  source: existing `artifact_action_invalid_state`, non-retryable;
- transient runtime/materialization failure after the accepted user turn:
  existing retryable `runtime_failure` plus the shipped `retry_last_turn`
  projection;
- missing or unavailable execution data after the user later confirms:
  existing `execution_data_unavailable` / failed-action behavior;
- stale confirmation or later failed run: existing confirmation-stale and
  failed-action retry behavior.

Do not repurpose a code whose semantics do not fit. If no current recovery code
truthfully represents a reachable failure, stop and present the gap before
adding a new code.

For retryable failure, render the shipped amber assistant recovery block
directly beneath the neutral receipt:

```text
↻ Retest with current data
GLD · Buy and hold · same 1-year duration

┌ amber recovery ─────────────────────────┐
│ Argus could not prepare that retest.    │
│                                [Retry]  │
└─────────────────────────────────────────┘
```

The existing in-place Retry control must replay the persisted typed
`retest_run` action, not send the raw label or reconstruct a prose prompt.
Successful retry supersedes/replaces the failure in place and must not append a
second visible user receipt. Non-retryable invalid-state recovery does not show
Retry.

## 3. Architecture and ownership

### 3.1 Reuse the shipped canonical projection

The existing deterministic `run_fresh` setup extraction in conversation recall
already proves whether a stored run can be faithfully reconstructed. Move or
reuse that logic behind one server-owned helper that can serve:

- Omnisearch action eligibility/projection;
- typed-action admission/materialization;
- deterministic tests.

Do not keep two independently drifting setup builders.

### 3.2 Backend modularity boundary

Create a focused retest action module in the existing chat/runtime boundary for:

- typed payload validation beyond schema shape;
- owner/conversation/source-run resolution;
- canonical setup reload;
- same-duration date transformation;
- receipt projection;
- Ready-to-run confirmation materialization;
- recovery mapping.

`src/argus/api/routers/agent.py`, shared runtime stages, and
`src/argus/api/schemas.py` receive only the narrow wiring/types they own. Do not
grow a large router or interpreter file with retest-specific orchestration.

### 3.3 Frontend modularity boundary

`web/components/chat/ChatInterface.tsx` is already approximately 2,600 lines.
Put typed retest request/receipt behavior in focused helpers/hooks and keep
ChatInterface wiring small.

The extracted dossier component from the sibling lane owns the visible button.
After that lane merges, this lane may add only the final typed callback/action
wiring there. Receipt rendering should extend the existing structured user-turn
projection rather than introduce a second message renderer.

### 3.4 Parallel-lane edit ownership and reconciliation

This lane may develop in parallel before the dossier-history PR lands and owns:

- retest domain/runtime action handler;
- chat request admission/persistence for `retest_run`;
- structured receipt projection/hydration;
- retry replay and failure supersession;
- focused backend/frontend tests;
- eventual API/OpenAPI/action-type/localization updates.

Until the dossier-history PR merges, this lane must not edit:

- `web/components/sidebar/ChatCommandPalette.tsx`;
- extracted dossier/history/editor components owned by that lane;
- the dossier response shape;
- `src/argus/api/schemas.py` while that lane owns the shared schema surface.

After the dossier-history PR merges, bring this branch forward from the new
remote integration tip without rewriting reviewed history. Add a small
reconciliation commit for:

- `ChatActionType = "retest_run"` and final typed schemas;
- replacing the search `run_fresh` action with `retest_run`;
- the dossier button callback;
- API/OpenAPI and frontend contract synchronization.

## 4. Acceptance

- Omnisearch latest-run and historical-run dossiers show `Retest with current
  data` only when the backend can faithfully reconstruct the selected run.
- Selection creates a neutral structured user receipt and a Ready-to-run
  confirmation with the same setup and same calendar-day duration ending on
  the server's current date.
- The raw generated `Test this exact supported setup again...` prompt never
  appears in new user turns, persisted message previews, or reload.
- The request contains no client-authoritative executable setup; tampered
  symbols, dates, parameters, labels, or cross-conversation run ids cannot
  change or expose canonical state.
- The action and confirmation path make zero LLM, research, discovery, and
  market-data provider calls.
- The action never auto-executes.
- EN and es-419 receipts hydrate equivalently from structured metadata.
- Browser refresh and conversation switching preserve the receipt and
  confirmation.
- A transient materialization failure renders the existing amber recovery with
  in-place Retry; Retry replays the typed action without a duplicate receipt.
- Stale/unauthorized source behavior uses the existing non-retryable invalid
  state contract and leaks no object existence.
- Later confirmed-run data failures retain the existing amber failed-action and
  retry behavior.
- Existing natural-language turns still reach the LLM-first interpreter; this
  typed action does not create language phrase matching or a parallel runtime.

## 5. Verification gates

Before marking the PR ready:

- backend tests cover valid supported strategies, unsupported/incomplete setup,
  deterministic clock math, ownership, conversation mismatch, tampered payload,
  stale/deleted source, zero-provider execution, persistence, reload,
  idempotent retry, and failure-code mapping;
- frontend tests cover typed submission, neutral receipt, no raw prompt,
  conversation readiness, latest/historical run targeting, reload, EN/es-419,
  amber retry, non-retryable invalid state, and no duplicate receipt;
- contract tests prove the old search action cannot remain silently accepted
  after the checked frontend migrates;
- `docs/API_CONTRACT.md` and `docs/api/openapi.yaml` are updated for every typed
  addition/removal;
- full backend suite passes hermetically with the canonical `.env` moved aside
  and `ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`;
- `bun test` passes in `web/`;
- ruff and `scripts/check_modularity_budget.py` pass;
- EN/es-419 mock-auth memory-mode browser QA covers desktop and mobile success,
  refresh, transient amber Retry, and a stale/non-retryable source;
- browser/network evidence confirms zero LLM, research, discovery, or market
  provider calls before explicit confirmation;
- the final review round addresses only confirmed, reachable findings
  proportional to this lane.

## 6. Execution contract

Mode: `normal_feature_branch`.

One branch and one PR deliver this entire spec from the same current remote
`codex/private-alpha-next` head used to start the dossier-history lane.
Recommended branch: `codex/typed-retest-current-data`.

Most runtime, persistence, receipt, and retry work may proceed while the
dossier-history lane is under review. This PR remains Draft and does not claim
complete integration until the dossier-history PR merges, the branch is brought
forward, the shared schema/palette seam is wired, and all gates rerun at the
final exact SHA.

Recommended internal commit order:

1. deterministic retest domain/materializer with clock and ownership tests;
2. chat admission, persistence, receipt hydration, and retry replay;
3. forward reconciliation with dossier-history plus typed API/OpenAPI action;
4. localization, browser QA, full gates, and review closure.

The founder merges.

## 7. Stop conditions

Stop and report if the implementation requires:

- any LLM/provider call to interpret, compose, preview, or confirm the action;
- trusting client-provided canonical setup, dates, symbols, or parameters;
- auto-executing the backtest;
- a new durable run, dossier, summary, memory, or retry model;
- a new failure code when an existing semantic class fits;
- replaying localized display prose instead of the persisted typed action;
- duplicating canonical setup extraction;
- growing `ChatInterface.tsx`, a router, or a runtime stage with the full retest
  implementation instead of extracting a focused unit;
- editing the palette/shared schema concurrently with the dossier-history lane;
- merging before the dossier-history lane and exact-head reconciliation.
