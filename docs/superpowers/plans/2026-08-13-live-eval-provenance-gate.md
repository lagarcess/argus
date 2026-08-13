# Live Eval Provenance Gate Implementation Plan

> Execute this plan in the isolated sibling worktree
> `/private/tmp/argus-eval-scorecard-provenance`.

**Goal:** Make false live scorecards impossible to emit, make future main
promotion manifests fail CI without live-eval evidence, and produce one valid
full-suite scorecard.

**Architecture:** The eval harness owns a typed run-provenance record. It derives
fixture identity from the same fixture enumeration used by the loader, resolves
the current Git and Python identities locally, and includes a fixed real-provider
calendar probe for live runs. The live test builds this record before iterating
cases, then passes it into the only scorecard writer. Release-doc tests scan
promotion manifests with an exact legacy exception set.

**Runtime:** Python 3.10.20, pytest, PyYAML, existing Argus market-data provider.

---

### Task 1: Lock the lane

**Files:**
- Add: `docs/superpowers/specs/2026-08-13-live-eval-provenance-gate.md`
- Add: `docs/superpowers/plans/2026-08-13-live-eval-provenance-gate.md`

1. Record the integration base, allowed surfaces, forbidden surfaces, one-run
   cost boundary, and stop rules.
2. Commit the locked lane before implementation.

### Task 2: Require scorecard provenance

**Files:**
- Modify: `tests/evals/test_measurement_eval_harness.py`
- Modify: `tests/evals/measurement_eval_harness.py`

1. Add tests showing `scorecard_for_results` and `write_scorecard` reject missing
   or malformed provenance.
2. Run the focused tests and observe the expected failure.
3. Add the smallest typed provenance model and validation boundary.
4. Derive the fixture SHA-256 from the exact ordered files loaded by the runner.
5. Derive the candidate SHA and Python version without caller-supplied values.
6. Re-run the focused tests to green.

### Task 3: Fail before paid calls when live is not live

**Files:**
- Modify: `tests/evals/test_measurement_eval_live_environment.py`
- Modify: `tests/evals/test_measurement_eval_live.py`
- Modify: `tests/evals/measurement_eval_harness.py`

1. Add tests for accepted 2024-01-02 plus `calendar_alignment` behavior and
   rejected 2024-01-01 plus no-adjustment behavior.
2. Prove the rejection test is red before implementation.
3. Add a fixed real-provider probe that runs before case iteration.
4. Bind the successful probe to live provenance and revalidate it at scorecard
   serialization.
5. Re-run the environment and harness tests to green without provider calls.

### Task 4: Enforce promotion-manifest evidence

**Files:**
- Modify: `tests/test_private_alpha_release_docs.py`

1. Add an exact set of existing main-promotion manifests that predate the gate
   and already omit live-eval evidence.
2. Add a parser-level test showing an unlisted manifest without a durable
   scorecard path, matching candidate SHA, and passing result fails.
3. Scan every repository main-promotion manifest so a new omission fails CI.
4. Run the release-docs test and keep release-contract files unchanged.

### Task 5: Free verification and code review

**Files:** all changed code and tests

1. Run Ruff on changed Python files.
2. Run the mocked eval suite, live-environment test, and release-docs tests.
3. Run the relevant broader deterministic suite required by CI.
4. Review the diff for secret exposure, product-runtime changes, duplicated
   provider truth, and historical-manifest bypasses.
5. Commit and push the code-only head, open a Draft PR, wait for CI, request one
   Codex review, and exhaust all validated findings to zero unresolved threads.

### Task 6: Run exactly one paid full suite

**Files:**
- Add: `docs/reports/evidence/live-eval-provenance-gate/<code-sha>/...`

1. Confirm the reviewed code head and clean worktree.
2. Source the canonical env read-only and explicitly force
   `ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider` and
   `ARGUS_ASSET_PROVIDER_MODE=live_provider`.
3. Run the full sanctioned suite once.
4. Record the accepted and actual provider cost.
5. Commit the corrected scorecard and a concise evidence report.
6. Run free exact-head verification, confirm the evidence-only commit did not
   change executable code, wait for CI, and request a delta-scoped Codex review.
7. If the suite fails, classify every failed check into regression, superseded
   expectation, or confound and stop without product fixes.
