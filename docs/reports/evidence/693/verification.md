# Local verification

Runtime commit: `f83f4124` (later evidence-only commits do not change runtime).
Original and freshly fetched integration base: `6747ff3193687c885f9647d0af265e0af906ceb0`.
No intervening integration commits; no reconciliation merge or semantic overlap.

| Check | Result |
| --- | --- |
| `cd web && bun test __tests__` | 2,155 passed |
| `cd web && bun run lint` | Passed; 8 existing warnings |
| `cd web && NEXT_DIST_DIR=.next-693-build NEXT_TELEMETRY_DISABLED=1 bun run build` | Passed, including production TypeScript check |
| Backend claim, calculation input, artifact continuity and complete mocked eval harness | 346 passed |
| `poetry run python scripts/check_modularity_budget.py` | Passed on current integration plus package tree |
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

Review flags: package 0B-1 requires Priya's written eval verdict before merge.
That internal verdict remains pending; this report does not supply it.
Analytics/event code is untouched for #702. The 0B-1 spec needs no new event.
The PR terminal audit records final head, CI and Codex review outcomes.
