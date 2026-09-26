# Local verification

Runtime commit: `b56ce0bd` (consistent AM/PM and server-reset verification).
Original and freshly fetched integration base: `6747ff3193687c885f9647d0af265e0af906ceb0`.
No intervening integration commits; no reconciliation merge or semantic overlap.

| Check | Result |
| --- | --- |
| `cd web && bun test __tests__` | 2,157 passed |
| `cd web && bun run lint` | Passed; 8 existing warnings |
| `cd web && NEXT_DIST_DIR=.next-693-build NEXT_TELEMETRY_DISABLED=1 bun run build` | Passed, including production TypeScript check |
| Backend claim, calculation input, artifact continuity and complete mocked eval harness | 346 passed |
| Configured chat reset contract plus guest/signed-in claim regressions | 38 passed |
| `poetry run python scripts/check_modularity_budget.py` | Passed on current integration plus package tree |
| `poetry run pytest tests/test_modularity_budget.py -q --no-cov` | 8 passed |
| Playwright package acceptance | 22 passed; EN/es-419; 360px/1280px; DR time zone |
| Baseline screenshot capture | 12 passed on integration runtime |

Backend command:

```sh
poetry run pytest tests/test_guest_compute_ceiling.py \
  tests/test_registered_compute_ceiling.py \
  tests/domain/test_calculation_driving_inputs.py \
  tests/agent_runtime/test_artifact_continuity.py \
  tests/evals/test_measurement_eval_harness.py \
  tests/evals/test_measurement_eval_dca_semantics.py \
  tests/evals/test_measurement_eval_scorecard.py \
  tests/evals/test_measurement_eval_live_environment.py \
  tests/evals/test_chat_runtime_eval_manifest.py \
  tests/evals/test_chat_runtime_trajectory_harness.py \
  tests/evals/test_measurement_availability.py \
  tests/evals/test_measurement_delivery.py \
  tests/evals/test_measurement_outcome.py \
  tests/evals/test_prose_evidence.py -q --no-cov
```

Environment notes: the locked SciPy 1.15.3 required the official macOS 12 ARM
wheel locally. No dependency file was changed. The sandboxed production build
stalled; restarting the same check outside the sandbox passed. Next.js's
build-generated local tsconfig additions were discarded. Direct `tsc --noEmit`
reports existing Bun test-shim and legacy E2E type diagnostics; production
build TypeScript passed, and no runtime-source diagnostics were reported.
The production build and backend checks preceded the final notice and AM/PM treatment;
those changes select the existing quiet panel, hide daily-cap answer controls,
and normalize the day period to AM/PM in both languages. Web unit tests, lint, modularity checks, and browser acceptance were
rerun afterward. The 38-case backend check also verifies real chat response
headers at both configured limits and UTC-day boundaries. Final-head CI covers the production build and backend again.

Review flags: package 0B-1 requires Priya's written eval verdict before merge.
That internal verdict remains pending; this report does not supply it.
Analytics/event code is untouched for #702. The 0B-1 spec needs no new event.
The PR terminal audit records final head, CI and Codex review outcomes.

CI follow-up: the first backend run passed 9,037 tests but detected that
`chat-recovery-display.test.ts` had crossed the 1,000-line registration
threshold. Its duplicated catalog translator now lives in shared test support
and both recovery suites reuse it. All 2,155 web tests and all eight modularity
unit checks pass after extraction. No assertion was removed, no budget was
raised. Browser evidence was retained for that test-support extraction, then
recaptured for the daily-cap notice refinement. Final CI is recorded in the PR
audit.
