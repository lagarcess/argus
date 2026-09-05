# Issue #533: one number for the benchmark gap

The result card and the Quick Take beside it reported two different numbers
for the same comparison. This directory holds the reproduction on the
integration head, the fix evidence, and the local-only replay that produced
both.

## What the arithmetic actually was

The engine (`src/argus/domain/backtesting/metrics.py`) rounds the strategy
return and the benchmark return to two decimals and publishes their
difference beside them as `delta_vs_benchmark_pct`, also rounded to two
decimals. The issue's own AAPL numbers reproduce as: returns 53.44% and 7.1%,
engine gap 46.35. On integration head `e3b98690`:

- The result card printed the engine gap at one decimal: **46.4**.
- The explain stage subtracted the two rounded returns (46.34) for the LLM
  fact bank, the relative-truth claim the draft is held to, and the
  deterministic readout: **46.3**. That prose is private since #551, but the
  same subtraction still fed the Try next reason on screen: **46.3 points**.
- #551 moved the visible Quick Take to the frontend, reading the engine gap
  but printing it at two decimals: **46.35**, and the worst drop as -18.35%
  beside the card's -18.4%.
- A gap of 0.06 was "beat" on the card and "matched" in the claim gate,
  because 53.44 - 7.1 differs from the engine's 0.06.

So the issue's diagnosis was right about the shape and had moved one layer:
three readers re-derived the gap, and the one that read the engine value
rounded it differently from the card.

## The fix

One owner for the value, one owner for the digits.

- Backend: `_resolved_return_metrics` in the explain stage is the only reader
  of result payload shapes and now returns the engine's gap with the returns.
  The fact bank, the relative-truth claim, the deterministic readout, and the
  Try next sidecar read it. Sidecar reason params carry engine facts at
  persisted precision instead of a second rounding, and a gap inside the
  in-line cut carries no benchmark reason. Only payload shapes with no engine
  block (the offline default tool's two fractions) still derive a difference.
- Frontend: `web/lib/result-figures.ts` is the one place a shared result
  figure becomes text. It mirrors Python's fixed-point formatting, ties to
  even, so backend-voiced figures (follow-up answers, breakdown facts) and the
  screen cannot disagree either. The card, the Quick Take, the breakdown, and
  the Try next reason all print through it, and the in-line claim is the
  magnitude rounding to nothing.
- `web/test-fixtures/tenth-figure-parity.json` is one table read by
  `tests/test_result_figure_parity.py` and `web/__tests__/result-figures.test.ts`.

## Browser evidence

`browser/` holds unedited headless Playwright captures of the real UI at the
integration head and at the fix commit, both languages, on the same recorded
real META result (`docs/reports/evidence/411/browser/en-discovery-messages.json`,
engine gap 315.64, worst drop -18.35). See `browser/provenance.json` for
digests, environment, and steps.

| Capture | Card | Quick Take | Try next reason | Worst drop (card / prose) |
| :--- | :--- | :--- | :--- | :--- |
| `before-en.png` (e3b98690) | 315.6 | **315.64** | 315.6 | -18.4% / **-18.35%** |
| `before-es-419.png` (e3b98690) | 315.6 | **315.64** | 315.6 | -18.4% / **-18.35%** |
| `after-en.png` (4288c5f5) | 315.6 | 315.6 | 315.6 | -18.4% / -18.4% |
| `after-es-419.png` (4288c5f5) | 315.6 | 315.6 | 315.6 | -18.4% / -18.4% |

The recorded Try next row already carried a rounded `points` value from the
old backend, so the recording cannot show the subtraction split on that row;
the AAPL case (card 46.4, reason 46.3, claim flip at 0.06) is pinned in
`tests/agent_runtime/test_benchmark_gap_owner.py` and
`web/__tests__/result-figures.test.ts` with the issue's own numbers.

The replay (`browser/replay_api.py`, `browser/capture.js`) seeds memory
persistence with the recorded conversation and hydrates it through the normal
Recents path. It made no model, market-data provider, hosted database, DCA, or
backtest call, loaded no credential file, and reported zero console errors.

## Gates at the fix commit

- `bun test __tests__`: 1,563 passed. eslint clean on touched files.
- Full hermetic backend suite: 6,003 passed, 541 skipped, 0 failed.
- `tests/agent_runtime tests/test_spine_guardrails.py`: 1,983 passed.
- `tests/evals` offline: 260 passed, 2 skipped (live-only), the same counts
  #551 recorded. No prompt text changed.
- `scripts/check_modularity_budget.py`: no violations.

## Left where it was, on purpose

- The dossier metrics list (`web/lib/run-dossier-items.ts`) prints `_pct`
  metrics through a locale-styled Intl percent, a different surface owner
  with its own tests; it can drift from the fixed-point figure on x.x5
  values and belongs to that lane.
- `supabase/migrations/`, `conversation_activity.py`, and `job_settlement.py`
  were not touched.
