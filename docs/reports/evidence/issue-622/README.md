# Ranked leader gaps, issue #622

The leader retains `gap_0 = 0` as a comparison-only supporting fact. Each item
therefore pairs with itself after a leader change. The shared card renderer,
copy text and receipt projection omit this row. Comparison differences retain
it. No tool description, model-facing text or provider behavior changes.

## Reproduction and verification

- Original integration base: `5cb360c1bb09ce75ab09559a47c7518026ef2fcf`.
- Tests added before production edits failed on that base: 18 failed, 7 passed.
  Two-item swaps had no gap differences; three-item swaps retained only the
  non-leader's gap. The presenter also omitted `gap_0`, including for ties.
- Domain calculations, comparison, declaration and prompt freeze: 183 passed.
- Receipt projection and the documented mocked eval harness: 277 passed.
- Full frontend suite: 1,981 passed. Frontend lint: no errors (8 existing warnings).
- Backend lint, branch ownership and modularity checks passed.
- Standalone `tsc --noEmit` reports existing repository-wide test typing errors;
  the CI frontend build remains the production type/build gate.
- `web/e2e/ranked-comparison-gap.spec.ts`: 2 browser flows passed, English and
  Spanish at 390 x 844, through the actual chat compare action. Generated
  backend cards and differences stub every API response; no paid runs.

The PNGs show each card and the signed gap differences. The fixture's supplied
labels remain its original input text; static UI uses the selected language.
Captures were made from the implementation tree committed alongside them.
The PR's terminal audit records exact-head revalidation after reconciliation
and the final CI/Codex review result; this file is not a readiness declaration.

Re-run the browser check from `web/` with:

```sh
RANKED_GAP_SCREENSHOT_DIR=../temp/issue-622/browser \
NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_MOCK_API=false \
NEXT_PUBLIC_ENABLE_SPANISH=true PLAYWRIGHT_PORT=3222 \
node node_modules/@playwright/test/cli.js test \
  e2e/ranked-comparison-gap.spec.ts --workers=1
```

Production commit `3d98057c` does not contain
`src/argus/domain/calculations/ranked_comparison.py`. The founder confirmed that
ranked comparisons have never shipped and pre-change cards exist only in
development data. The legacy-card review finding was therefore declined:
no production backfill or compatibility normalization is needed for this lane.
New calculations and recomputes produce the complete fact set.
