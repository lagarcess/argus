# Live Eval Provenance Gate

Date: 2026-08-13

Status: Locked for implementation

Integration base: `0dc4034c0b8e2413639a347884412ec0f1f828c6`

## Why this lane exists

The promotion scorecard for candidate `b0f4ab4f` looked like paid live evidence,
but it recorded no provider mode, candidate SHA, Python version, or fixture
identity. The environment could therefore select synthetic market data while
the suite still spent live LLM tokens and emitted plausible product failures.

This lane makes that state unrepresentable. A scorecard is evidence only when
the harness can bind it to the evaluated code, runtime, fixtures, and effective
provider modes. A live scorecard also needs a provider-behavior probe before any
LLM call.

The same incident exposed a release-process hole. The runbook requires the live
suite for every `main` promotion candidate, but promotion manifests can omit its
scorecard without failing repository tests.

## Locked decisions

1. The measurement scorecard has one required provenance object containing:
   - resolved market-data provider mode;
   - resolved asset provider mode;
   - candidate Git SHA;
   - Python version;
   - SHA-256 identity of the complete measurement fixture set.
2. Scorecard serialization rejects absent, blank, or malformed provenance. It
   never fills missing evidence with an unverified placeholder.
3. A scorecard marked `live` requires market-data mode `live_provider` and a
   successful fixed calendar probe before any paid LLM case runs.
4. The probe uses the real default market-data and calendar boundaries for an
   equity window beginning on the 2024-01-01 market holiday. The only accepted
   result begins on 2024-01-02 with `calendar_alignment`.
5. Fixture loading and fixture hashing derive from the same ordered fixture-file
   list, so the scorecard cannot identify a different fixture set from the one
   the runner loads.
6. The release-docs test scans main-promotion manifests. Every new manifest must
   cite a durable live-eval scorecard, its candidate SHA, and a passing result.
   Existing manifests that already lack this proof are an explicit, exact
   legacy set in the test, not a date-based bypass.
7. One paid full-suite run is allowed after the code and review surface are
   stable. Both provider modes are forced to `live_provider`. Its exact cost and
   scorecard are committed as evidence.

## In scope

- `tests/evals/measurement_eval_harness.py`
- `tests/evals/test_measurement_eval_live.py`
- eval harness and environment tests under `tests/evals/`
- `tests/test_private_alpha_release_docs.py`
- eval documentation needed to explain the fail-closed invocation
- durable evidence under `docs/reports/evidence/`

## Out of scope

- Product runtime behavior or eval expectation changes
- Any change to a failed product case
- `render.yaml`
- Release-contract files
- Historical promotion-manifest rewrites
- Merge, deployment, production configuration, or secret mutation

## Failure and stop rules

- If the live probe does not reproduce the expected calendar behavior, stop
  before the first LLM call and emit no scorecard.
- If required provenance cannot be resolved, emit no scorecard.
- If the paid suite fails, preserve the scorecard and classify each failed
  check as regression, superseded expectation, or confound. Do not fix product
  code in this lane.
- Any review change to executable harness behavior invalidates live evidence.
  Complete code review before the single paid run.

## Acceptance

- Focused tests prove missing provenance cannot be serialized.
- Focused tests prove a synthetic calendar result cannot start a live run.
- The free mocked eval suite passes under Python 3.10.20.
- Release-docs tests reject an unlisted promotion manifest without live-eval
  evidence and expose the exact known historical gap.
- One full live run records both modes as `live_provider`, candidate SHA, Python
  version, fixture SHA-256, probe result, totals, and provider cost.
- A PR targets `codex/private-alpha-next`, passes CI, receives a Codex review,
  and has zero unresolved review threads. It remains unmerged and undeployed.
