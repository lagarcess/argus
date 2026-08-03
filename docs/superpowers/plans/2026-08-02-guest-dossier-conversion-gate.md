# Guest Omnisearch Dossier Conversion Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep guest dossier metrics and decision controls visually complete,
conversion-gate decision writes, and resume the same decision editor after
conversion without changing guest persistence capability.

**Architecture:** The backend continues to own both the evidence action identity
and its policy by projecting every eligible dossier decision action with a typed
availability. The existing guest conversion latch retains an ephemeral,
surface-specific resume target while its server handoff continues verifying the
existing artifact-bound summary. The frontend reopens the already-selected
dossier editor only after canonical account/search state reports that the action
is available.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.10, Next.js 16, React 19,
TypeScript, Bun test, Playwright, Tailwind CSS.

## Global Constraints

- The authoritative spec is
  `docs/superpowers/specs/2026-08-02-guest-dossier-conversion-gate.md`.
- Original integration base: `6533377c1a08539136a622a7d53eee20d0efd845`.
- `can_save_decision` remains `false` for guests; direct guest decision writes
  remain `403 account_conversion_required`.
- Issue #341, migrations, RLS, hosted configuration, deployment, and merge are
  no-touch.
- Backend action identity is canonical. Browser resume context never authorizes
  a mutation.
- Static UI behavior must work in English and `es-419`.
- Use TDD for every behavior change and commit only after fresh verification.

---

## File structure

- `src/argus/api/schemas.py`: public typed decision-action availability.
- `src/argus/domain/run_dossiers.py`: canonical action projection for one run.
- `src/argus/domain/conversation_recall.py`: forwards action policy into the
  shared projector.
- `src/argus/api/search_assembly.py`: normalizes injected/persistent projections
  to the request account policy without removing identity.
- `src/argus/api/routers/search.py`: maps account capability to action
  availability for Omnisearch.
- `src/argus/api/routers/conversations.py`: maps the same policy for dossier
  history.
- `tests/test_run_dossiers.py`: projection contract tests.
- `tests/test_alpha_api.py`, `tests/test_alpha_api_supabase.py`, and
  `tests/test_search_bounded_reads.py`: route/search regression coverage.
- `web/lib/run-dossier-contract.ts`: exact TypeScript mirror of the Pydantic
  action schema.
- `web/lib/guest-conversion.ts`: typed ephemeral resume target retained by the
  existing single-use latch.
- `web/components/guest/useGuestExperience.ts`: routes a resumed decision to
  the correct surface exactly once.
- `web/components/guest/useGuestShellActions.ts`: accepts a typed decision
  request rather than only an artifact string.
- `web/components/chat/ChatInterface.tsx`: passes request/resume state between
  the guest shell and Omnisearch.
- `web/components/sidebar/ChatCommandPalette.tsx`: conversion-gates unavailable
  actions and hands canonical resume state to the selected dossier.
- `web/components/sidebar/command-palette/RunDossierView.tsx`: balanced odd
  metric layout and controlled resume into the existing editor.
- `web/__tests__/run-dossier-view.test.tsx`,
  `web/__tests__/guest-conversion.test.ts`, and
  `web/__tests__/chat-command-palette.test.tsx`: observable frontend behavior.
- `web/e2e/issue-340-guest-dossier-conversion-gate.spec.ts`: focused guest UI
  flow with route-backed canonical fixtures and no provider calls.
- `docs/API_CONTRACT.md` and `docs/api/openapi.yaml`: human and generated public
  contract evidence.

### Task 1: Project a typed guest decision action

**Files:**
- Modify: `tests/test_run_dossiers.py`
- Modify: `tests/test_alpha_api.py`
- Modify: `tests/test_alpha_api_supabase.py`
- Modify: `tests/test_search_bounded_reads.py`
- Modify: `src/argus/api/schemas.py`
- Modify: `src/argus/domain/run_dossiers.py`
- Modify: `src/argus/domain/conversation_recall.py`
- Modify: `src/argus/api/search_assembly.py`
- Modify: `src/argus/api/routers/search.py`
- Modify: `src/argus/api/routers/conversations.py`

**Interfaces:**
- Produces: `DecisionActionAvailability = Literal["available",
  "account_conversion_required"]` and required
  `SearchDecisionAction.availability`.
- Consumes: request-scoped `context.capabilities.can_save_decision`; does not
  change that capability.

- [ ] **Step 1: Write failing projection and route tests**

Add a projection test equivalent to:

```python
dossier = project_run_dossier(
    run=run,
    artifact=artifact,
    decision=None,
    result_message_id=None,
    decision_action_availability="account_conversion_required",
    language="en",
)
decision = next(action for action in dossier.actions if action.type == "decision")
assert decision.evidence_artifact_id == artifact["id"]
assert decision.availability == "account_conversion_required"
```

Change guest route/search expectations from an omitted action to the same
artifact-bound action with `availability == "account_conversion_required"`.
Keep a registered expectation for `availability == "available"`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
poetry run pytest tests/test_run_dossiers.py tests/test_alpha_api.py \
  tests/test_alpha_api_supabase.py tests/test_search_bounded_reads.py \
  -q --no-cov
```

Expected: failures because guest actions are still removed and the availability
field/parameter does not exist.

- [ ] **Step 3: Implement the minimal shared projection**

Define the literal type beside the dossier action schemas, add availability to
`SearchDecisionAction`, and make `project_run_dossier` always append the
decision action:

```python
class SearchDecisionAction(BaseModel):
    type: Literal["decision"] = "decision"
    availability: DecisionActionAvailability = "available"
    evidence_artifact_id: str
    # existing state, note, and label fields remain unchanged
```

Replace each `allow_decision_action` boundary with the typed availability.
Persistent injected rows must rewrite only the action policy for the request;
they must preserve the server-projected artifact identity and action order.

- [ ] **Step 4: Run the focused backend tests and verify GREEN**

Run the Step 2 command and confirm zero failures.

- [ ] **Step 5: Commit the backend slice**

```bash
git add src/argus/api/schemas.py src/argus/domain/run_dossiers.py \
  src/argus/domain/conversation_recall.py src/argus/api/search_assembly.py \
  src/argus/api/routers/search.py src/argus/api/routers/conversations.py \
  tests/test_run_dossiers.py tests/test_alpha_api.py \
  tests/test_alpha_api_supabase.py tests/test_search_bounded_reads.py
git commit -m "fix(api): conversion-gate guest dossier decisions"
```

### Task 2: Balance sparse dossier metrics

**Files:**
- Modify: `web/__tests__/run-dossier-view.test.tsx`
- Modify: `web/components/sidebar/command-palette/RunDossierView.tsx`

**Interfaces:**
- Consumes: formatted metric count from `formatRunDossierMetrics`.
- Produces: odd final metric element with `data-dossier-metric-span="full"` and
  `col-span-2`; even grids remain two balanced columns.

- [ ] **Step 1: Write failing one-, three-, and four-metric markup tests**

Render literal dossier fixtures and assert:

```typescript
expect(metricRows(threeMetricHtml)).toHaveLength(3);
expect(threeMetricHtml).toContain('data-dossier-metric-span="full"');
expect(threeMetricHtml.match(/data-dossier-metric-span="full"/g)).toHaveLength(1);
expect(fourMetricHtml).not.toContain('data-dossier-metric-span="full"');
```

The production mutation caught is removing the odd-count span and recreating a
half-empty last row.

- [ ] **Step 2: Run the component test and verify RED**

```bash
cd web && bun test __tests__/run-dossier-view.test.tsx
```

Expected: odd-count full-span assertions fail.

- [ ] **Step 3: Add the minimal odd-row layout rule**

Compute `isFullWidthTrailingMetric` from `metrics.length` and `index`. Add
`col-span-2` only to the last item when the count is odd, keep the existing
separator rules, and expose the semantic test attribute only on that item.

- [ ] **Step 4: Rerun the test and verify GREEN**

Run the Step 2 command and confirm zero failures.

### Task 3: Resume the exact Omnisearch dossier decision editor

**Files:**
- Modify: `web/lib/run-dossier-contract.ts`
- Modify: `web/lib/guest-conversion.ts`
- Modify: `web/components/guest/useGuestShellActions.ts`
- Modify: `web/components/guest/useGuestExperience.ts`
- Modify: `web/components/chat/ChatInterface.tsx`
- Modify: `web/components/sidebar/ChatCommandPalette.tsx`
- Modify: `web/components/sidebar/command-palette/RunDossierView.tsx`
- Modify: `web/__tests__/guest-conversion.test.ts`
- Modify: `web/__tests__/run-dossier-view.test.tsx`
- Modify: `web/__tests__/chat-command-palette.test.tsx`

**Interfaces:**
- Produces: `GuestDecisionResumeTarget`, discriminated by `surface` with
  `result_card` and `omnisearch_dossier` variants.
- The dossier variant carries `artifactId`, `runId`, `decisionState`, and `note`
  only as ephemeral UI state; `pendingGuestActionSummary` still serializes only
  the existing verified `artifact_id`.
- `RunDossierView` consumes an optional matching resume target and calls
  `onDecisionResumeHandled` after opening the editor once.

- [ ] **Step 1: Write failing single-use and UI resume tests**

Cover these literal behaviors:

```typescript
const pending: GuestPendingAction = {
  reason: "save_decision",
  conversationId: "conversation-1",
  actionId: "decision-1",
  target: {
    surface: "omnisearch_dossier",
    artifactId: "artifact-1",
    runId: "run-1",
    decisionState: "watching",
    note: "Keep this exact note",
  },
};
expect(pendingGuestActionSummary(pending)).toEqual({
  reason: "save_decision",
  conversation_id: "conversation-1",
  action_id: "decision-1",
  artifact_id: "artifact-1",
});
```

Render the dossier with `availability: "account_conversion_required"` and
assert Add/Edit calls the conversion callback without calling the mutation.
Then render it with `availability: "available"` plus a matching resume target
and assert the editor contains the exact state and note and consumes the target
once. A mismatched run/artifact must remain closed.

- [ ] **Step 2: Run focused frontend tests and verify RED**

```bash
cd web && bun test __tests__/guest-conversion.test.ts \
  __tests__/run-dossier-view.test.tsx \
  __tests__/chat-command-palette.test.tsx
```

Expected: compile or assertion failures because availability and dossier resume
targets are not yet represented.

- [ ] **Step 3: Implement typed request and resume routing**

Mirror the API action availability exactly. Generalize the existing result-card
resume id into a discriminated target while preserving result-card behavior.
The palette must call the existing conversion request with a dossier target
when availability is conversion-required. It must never call
`createEvidenceDecision` on that branch.

After conversion, account refresh changes the request policy to `available`;
refresh canonical search if needed, retain the selected run, and pass the
matching resume target into `RunDossierView`. Open the existing `DecisionEditor`
with the action's state/note and clear the target only after it opens.

- [ ] **Step 4: Rerun the focused frontend tests and verify GREEN**

Run the Step 2 command and confirm zero failures and no unhandled warnings.

- [ ] **Step 5: Run React lint/type evidence**

```bash
cd web && bun run lint -- \
  components/sidebar/ChatCommandPalette.tsx \
  components/sidebar/command-palette/RunDossierView.tsx \
  components/guest/useGuestExperience.ts \
  components/guest/useGuestShellActions.ts \
  components/chat/ChatInterface.tsx \
  lib/guest-conversion.ts lib/run-dossier-contract.ts
cd web && bunx tsc --noEmit
```

- [ ] **Step 6: Commit the frontend slice**

```bash
git add web/lib/run-dossier-contract.ts web/lib/guest-conversion.ts \
  web/components/guest/useGuestShellActions.ts \
  web/components/guest/useGuestExperience.ts \
  web/components/chat/ChatInterface.tsx \
  web/components/sidebar/ChatCommandPalette.tsx \
  web/components/sidebar/command-palette/RunDossierView.tsx \
  web/__tests__/guest-conversion.test.ts \
  web/__tests__/run-dossier-view.test.tsx \
  web/__tests__/chat-command-palette.test.tsx
git commit -m "fix(web): resume guest dossier decisions after conversion"
```

### Task 4: Synchronize public contracts

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Modify: `docs/api/openapi.yaml`
- Test: `tests/test_openapi_compatibility.py`

**Interfaces:**
- Documents the exact `availability` enum and guest client behavior.
- Generated OpenAPI remains structurally identical to `app.openapi()`.
- Documents the optional `X-Argus-Client-Capabilities` header and additive
  `dossier_decision_conversion_v1` rollout handshake on both dossier reads;
  missing support preserves the legacy guest omission while registered action
  projection and write authorization remain unchanged.

- [ ] **Step 1: Update the human contract**

Replace “Guest responses omit the decision action” with the rule that eligible
guest dossiers retain the action with
`availability: "account_conversion_required"`, activation opens conversion,
and only `availability: "available"` may reach the decision mutation.

- [ ] **Step 2: Regenerate OpenAPI**

```bash
poetry run python scripts/generate_openapi_artifact.py
```

- [ ] **Step 3: Verify contract compatibility**

```bash
poetry run pytest tests/test_openapi_compatibility.py -q --no-cov
```

- [ ] **Step 4: Commit contract evidence**

```bash
git add docs/API_CONTRACT.md docs/api/openapi.yaml
git commit -m "docs(api): describe guest dossier action availability"
```

### Task 5: Prove the guest interaction in a browser

**Files:**
- Create: `web/e2e/issue-340-guest-dossier-conversion-gate.spec.ts`

**Interfaces:**
- Uses complete route fixtures for guest `/me`, Omnisearch dossier reads,
  conversion, registered `/me`, and refreshed dossier action availability.
- Makes zero LLM, market-data, decision-mutation-before-conversion, or hosted
  calls.

- [ ] **Step 1: Write a failing focused Playwright scenario**

The scenario must cover English and `es-419` with three metrics. For each
locale:

1. Open guest Omnisearch and select the dossier.
2. Assert three metric rows and a full-width final metric.
3. Assert Add decision/Edit is visible.
4. Activate it and assert the localized conversion dialog appears.
5. Assert no decision mutation request occurred.
6. Complete the deterministic conversion fixture.
7. Assert the same run dossier is selected and its editor opens with the exact
   pre-conversion note.

- [ ] **Step 2: Run the focused scenario and verify RED**

```bash
cd web && bun run test:e2e -- \
  e2e/issue-340-guest-dossier-conversion-gate.spec.ts --project=chromium
```

Expected: fail before the frontend implementation satisfies the full flow.

- [ ] **Step 3: Finish only test-harness wiring needed by the real UI**

Do not add production-only test switches. Reuse existing route fixture and auth
patterns from guest E2E tests.

- [ ] **Step 4: Run the scenario and verify GREEN**

Run the Step 2 command. Capture final desktop and mobile screenshots outside
the repository during the later Browser-plugin QA pass.

- [ ] **Step 5: Commit browser coverage**

```bash
git add web/e2e/issue-340-guest-dossier-conversion-gate.spec.ts
git commit -m "test(web): cover guest dossier conversion resume"
```

### Task 6: Exact-head review, reconciliation, CI, and Draft PR

**Files:**
- Review all files changed since `6533377c`.

- [ ] **Step 1: Run the focused exact-head gate**

```bash
poetry run pytest tests/test_run_dossiers.py tests/test_alpha_api.py \
  tests/test_alpha_api_supabase.py tests/test_search_bounded_reads.py \
  tests/test_openapi_compatibility.py -q --no-cov
cd web && bun test __tests__/run-dossier-view.test.tsx \
  __tests__/guest-conversion.test.ts __tests__/chat-command-palette.test.tsx \
  __tests__/guest-shell.test.tsx
cd web && bunx tsc --noEmit
git diff --check 6533377c...HEAD
```

- [ ] **Step 2: Perform independent review**

Use `argus-review-contract`. Re-read every locked decision, inspect the final
code rather than trusting tests, and fix only validated, proportionate findings.

- [ ] **Step 3: Use the Browser plugin for rendered QA**

Run the target flow:
`guest Omnisearch -> three-metric dossier -> Add/Edit -> conversion modal ->
successful conversion -> same dossier editor with preserved note`.
Verify page identity, meaningful DOM, no framework overlay, console health,
desktop/mobile screenshots, English, and Spanish.

- [ ] **Step 4: Reconcile integration**

Fetch `origin/codex/private-alpha-next`. If it advanced, compare semantic
overlap across the dossier, guest conversion, API schema, and affected tests;
merge integration one-way only, then rerun invalidated evidence.

- [ ] **Step 5: Push and open the Draft PR**

Push the worker branch and create a Draft PR targeting
`codex/private-alpha-next`. Use the required Argus PR template, include
`Closes #340`, add existing `bug`, `web`, `api`, and `confirmed` labels, then
wait for terminal exact-head CI. Do not merge.
