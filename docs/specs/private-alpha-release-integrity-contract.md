# Private Alpha Release Integrity Contract

Status: Founder-approved contract for implementation
Date: 2026-07-12
Branch family: `codex/private-alpha-next`
Issue: #193; blocks #194, #195, and #196
Verified baseline: `e52eeb35a9c0dc6a72519ff3bb0bda561f33e622`
Audience: founder, release captain, implementers, and reviewers

Read this after `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`,
`docs/API_CONTRACT.md`, and `docs/DATA_MODEL.md`. This document fixes the
behavioral boundary for the release-integrity repair. It does not claim that the
behavior is implemented yet.

## 1. Why this gate exists

The latest private-alpha candidate passed its existing checks while four parts
of one real user journey were still not proven as one coherent contract:

1. Render workflow completion could publish a successful job before the P1
   Idea, IdeaVersion, and EvidenceArtifact sidecars were finalized.
2. A Spanish choice made before signup was not part of the signup request, so
   the durable profile could still be created with English defaults.
3. Locale catalogs could both omit a static key and still satisfy the existing
   parity test; translated display labels were also being used as state on one
   enabled surface.
4. Release evidence proved deployed services and a backtest, but not the full
   signup-to-evidence-to-decision-to-recall journey for the same real user.

Issue #193 closes only the specification gap. Runtime repair belongs to #194,
#195, #196, and #197 in the dependency order in section 7.

## 2. Contract A: one backtest finalization boundary

### 2.1 Meaning of completion

A computed backtest is not yet a completed product artifact. A backtest is
**finalized** only when one typed finalizer has durably established this tuple:

- the canonical immutable `backtest_runs` row;
- the matching `ideas` row;
- the matching `idea_versions` row;
- the matching `evidence_artifacts` row; and
- the result-card metadata that names `idea_id`, `idea_version_id`,
  `evidence_artifact_id`, `evidence_lifecycle`, and `artifact_type`.

Local/in-process execution and Render Workflow execution must call the same
application finalizer. Neither path may independently recreate part of this
sequence.

### 2.2 Typed boundary

The finalizer consumes a typed input containing, at minimum:

- a stable `run_id` allocated before the first finalization attempt;
- execution identity (`backtest_job_id` when a durable job exists, otherwise
  the request idempotency identity);
- owner and parent identity;
- the canonical computed run payload; and
- the user-visible result-card payload.

It returns a typed finalized identity containing `run_id`, `idea_id`,
`idea_version_id`, and `evidence_artifact_id`. Callers publish only that returned
identity. They do not infer it from prose or repeat sidecar writes themselves.

### 2.3 Idempotency and behavioral atomicity

- Every retry reuses the same `run_id` and execution identity.
- Replaying an already-finalized input returns the same finalized identity.
- The existing `UNIQUE(user_id, source_run_id)` evidence constraint remains a
  required last-line defense; the finalizer must also prevent duplicate run or
  version creation.
- The tuple in section 2.1 is one logical transaction. Implementation may use a
  database transaction or an equivalent commit barrier, but no retrieval,
  reload, or search reader may observe a partially finalized tuple.
- A result-card message must not expose final artifact ids until the tuple is
  committed.

### 2.4 Job transition and failure semantics

A durable job may transition to `succeeded` only after finalization returns the
complete identity and `result_run_id` points to that run. `succeeded` therefore
means both computation and product-artifact finalization succeeded.

The public status enum remains:

- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`
- `expired`

Do not add a `finalization_failed` status. A recoverable finalization failure is:

```json
{
  "status": "failed",
  "result_run_id": null,
  "failure_code": "finalization_failed",
  "failure_detail": "execution_failed",
  "retryable": true
}
```

The failure must remain retryable with the same stable identities. Unknown or
non-recoverable failures keep the existing safe failure policy. A failed
finalization cannot be presented as a successful run even if metric computation
finished.

### 2.5 Acceptance owned by #194

#194 is complete only when focused tests prove:

- local and Render paths call the same finalizer;
- success exposes one run and exactly one evidence tuple;
- retry after each injected finalization failure converges on that same tuple;
- no partial result is returned by job retrieval, conversation reload, history,
  or Omnisearch; and
- a successful real Render result exposes **Add decision**, the saved note
  survives reload, and real Render browser evidence records that lifecycle; and
- the existing successful happy path and public status enum remain compatible.

## 3. Contract B: signup creates the authoritative language profile

### 3.1 Signup request

Private-alpha signup accepts `language` as a supported machine value: `en` or
`es-419`. The private-alpha web client must send the language currently selected
on the unauthenticated surface. The server validates it and derives the locale:

| language | derived locale |
|---|---|
| `en` | `en-US` |
| `es-419` | `es-419` |

The server does not trust a separately supplied locale during signup. Unsupported
language values return `422`; provider or allowlist failures retain the existing
generic signup error boundary.

For backward-compatible API callers that omit `language`, the server may use the
canonical English fallback. Omission is not acceptable for the private-alpha web
signup path and must fail its contract test.

### 3.2 Authority and hydration

- Browser detection and logged-out local storage are temporary pre-auth hints.
- Successful signup creates the profile with both language and derived locale in
  the same server-owned signup path.
- The frontend must not issue a second profile patch to repair signup language.
- After authentication, `profiles.language` and `profiles.locale` are the only
  product authorities for language and formatting.
- Login, session hydration, and reload must replace temporary browser state with
  the stored profile values before rendering the authenticated application.
- Later user changes still use the profile update endpoint and remain reversible.

### 3.3 Acceptance owned by #195

#195 is complete only when API, frontend, and browser tests prove Spanish signup
persists `es-419`/`es-419`, the first authenticated render is Spanish, reload
remains Spanish, English remains compatible, invalid values fail validation, and
no post-signup repair request is required.

## 4. Contract C: static localization parity is source-backed

### 4.1 Catalog coverage

Every literal static translation key used by an enabled private-alpha surface
must exist in both `en` and `es-419`. Equality between the two catalog key sets
is necessary but not sufficient: CI must also compare them with keys extracted
from the scoped frontend source.

- Literal translation calls are extracted from enabled source paths.
- Keys that cannot be extracted statically must live in one explicit, typed
  dynamic-key inventory covered by the same catalog test.
- Feature-disabled future surfaces are outside this gate until their release
  profile capability is enabled.
- Runtime fallback may prevent a broken render, but a fallback cannot make CI or
  release acceptance pass.

### 4.2 State is language-neutral

Translated labels are display values only. Selection, grouping, filtering, and
comparison logic must use typed state such as `isPinned`, an enum, or a stable
group key. Changing locale must never change application meaning.

### 4.3 Acceptance owned by #196

#196 is complete only when the source-backed catalog test catches a key omitted
from both catalogs, catches one-sided omissions, covers the dynamic inventory,
and focused frontend tests prove state logic does not compare translated labels.
The Spanish browser check must inspect the visible keys enumerated by the active
release profile, including the pinned conversation group.

## 5. Contract D: one authoritative release profile

### 5.1 Profile ownership

#197 will add one checked-in machine-readable profile at
`.github/private-alpha-release-profile.json`. It owns non-secret expectations for
the candidate:

- API, web, and workflow service identity;
- runtime modes and required feature capabilities;
- supported locales and required visible static keys;
- expected workflow task and health behavior; and
- the ordered real-user canary scenario.

The file must not contain credentials, account identifiers, deployment ids, or a
candidate SHA. The exact candidate SHA is a runtime input so one profile can be
applied to successive candidates without editing policy.

Release tooling validates the profile and computes a SHA-256 hash of its checked-
in bytes. The candidate release manifest records that hash, environment
fingerprints, the deployed SHA for API/web/workflow, and behavioral evidence.
All three deployed surfaces must resolve to the candidate SHA before the canary
can pass.

The profile is the desired non-secret release configuration. Release tooling
must fail when `render.yaml`, the live Render service configuration, or the
effective API/web/workflow modes disagree with it; secrets remain in the
deployment control plane and are checked only by presence/fingerprint.

### 5.2 Validation modes

Fast local development and release validation have different evidence value:

- **Fast local mode** uses memory persistence/checkpointing, synthetic unit
  fixtures, mock auth, and an in-process execution path. It proves deterministic
  behavior quickly but is not deployment or real-user evidence.
- **Production-parity Render mode** uses Supabase persistence, Postgres runtime
  checkpointing, real auth, live provider-backed resolution, and Render Workflow
  execution. It is the only mode accepted by the release canary.

The checked-in profile names the required release mode for each deployed
surface. `.github/dev.sh` and `.github/qa.sh` remain developer entry points; they
cannot override or substitute for effective-mode proof from the deployed
candidate.

### 5.3 Real-user canary

Against the branch-deployed private-alpha validation surface, one allowlisted
canary user must complete this ordered journey:

1. select Spanish and create a real account through signup;
2. prove the returned and reloaded profile is `es-419`/`es-419`;
3. submit and complete a real Render Workflow backtest;
4. prove job, run, Idea, IdeaVersion, EvidenceArtifact, and result-card identity
   agree;
5. choose **Add decision**, save a note, and prove the decision identity;
6. reload the conversation and prove the decision state and note hydrate;
7. retrieve the evidence through Omnisearch and prove source identity; and
8. inspect every required visible Spanish static key from the release profile,
   including `chat.history.pinned`.

The canary must clean up or use a documented isolated canary identity. It must
not invite testers, merge to `main`, or deploy production. Those remain founder-
directed actions after the technical gate.

### 5.4 Acceptance owned by #197

#197 is complete only when profile validation, exact-SHA deployment proof, the
full ordered canary, and a candidate manifest all pass for the same candidate.
A service-health-only or existing-user-only canary is insufficient.

## 6. Non-goals and stop conditions

This release-integrity repair must not introduce:

- a second conversational runtime or natural-language classifier;
- a new public job status;
- a second finalization service beside the existing persistence/runtime spine;
- generic RAG, vector memory, broker/export execution, or other deferred scope;
- runtime copy tables or translated-label state; or
- automatic `main` promotion, production deployment, or tester exposure.

Stop and return to the founder if implementation requires changing product
scope, weakening evidence identity, exposing partial finalization, or bypassing
the real-user canary.

## 7. Dependency and closure order

1. #193 lands this docs-only contract and closes.
2. #194 implements the shared finalization spine.
3. #195 and #196 may proceed in parallel after #193 closes.
4. #197 begins only after #194, #195, and #196 close.
5. #198 records as-built operational documentation and final release evidence.

#193 itself is done only when the founder approval is recorded on the issue,
this contract and its surgical canon updates pass review/checks, the docs-only PR
is merged into `codex/private-alpha-next`, and the closure record links the merge
commit. It does not wait for the child implementations and it does not close on
a draft alone.
