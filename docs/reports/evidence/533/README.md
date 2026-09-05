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
  of result payload shapes and returns the engine's gap with the returns. The
  fact bank, the relative-truth claim, the deterministic readout, and the
  Try next sidecar read it. Only payload shapes with no engine block (the
  offline default tool's two fractions) still derive a difference.
- Backend owns the digits too. `display_figure` is Python's own float
  rounding, the rounding every backend-voiced copy of these figures already
  uses, and the benchmark comparison prose derives from it.
  `result_display_figures` projects the engine metrics into one-decimal
  `figures` at the reader boundary, from the metrics the payload already
  carries: `reader_payload` attaches them to every result and breakdown fact
  bank, `reader_run` to every public run including the live final frame, and
  the dossier to its outcome bank and metric rows. Try next reason params are
  the same figures. Nothing is persisted and no second metrics owner exists.
- Frontend never rounds. `web/lib/result-figures.ts` applies only the
  workspace locale's decimal separator and grouping to figures it received,
  and the card, the Quick Take, the breakdown, the Try next reason, and the
  dossier grid all read those figures. A payload without figures has no
  printable figure.

The first round shipped a client-side mirror of Python's rounding pinned by a
shared table; the Codex review round replaced it with the backend owner above.

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
| `after-en.png` (707f1524) | 315.6 | 315.6 | 315.6 | -18.4% / -18.4% |
| `after-es-419.png` (707f1524) | 315.6 | 315.6 | 315.6 | -18.4% / -18.4% |

The recorded Try next row already carried a rounded `points` value from the
old backend, so the recording cannot show the subtraction split on that row;
the AAPL case (card 46.4, reason 46.3, claim flip at 0.06) is pinned in
`tests/agent_runtime/test_benchmark_gap_owner.py`, `tests/test_result_figures.py`,
and `web/__tests__/result-figures.test.ts` with the issue's own numbers. The
after captures were re-taken at `707f1524` and are byte-identical to the
first-round captures because the visible output did not change; the replay
seeds no run, so the figures on screen came from the read-time derivation.

The replay (`browser/replay_api.py`, `browser/capture.js`) seeds memory
persistence with the recorded conversation and hydrates it through the normal
Recents path. It made no model, market-data provider, hosted database, DCA, or
backtest call, loaded no credential file, and reported zero console errors.

## Gates at the fix commit (707f1524)

- `bun test __tests__`: 1,563 passed. eslint clean on touched files.
- Full hermetic backend suite: 5,990 passed, 541 skipped, 0 failed.
- `tests/evals` offline: 260 passed, 2 skipped (live-only), unchanged from
  #551. No prompt text changed.
- OpenAPI artifact regenerated for the public run's `figures` field; the
  compatibility gate passes. `scripts/check_modularity_budget.py`: no
  violations.

## Left where it was, on purpose

- The public receipt page (`web/lib/receipt-plan.ts`) still rounds its
  frozen two-decimal `delta_vs_benchmark_pct` string with `toFixed(1)`. That
  page renders an immutable snapshot owned by the receipt-sharing lane and is
  flag-off in production; it is reported, not changed here.
- `supabase/migrations/`, `conversation_activity.py`, and `job_settlement.py`
  were not touched.
