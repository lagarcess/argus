# Registry browser fixtures

These files are generated through backend declarations and contain no provider
responses or newly implemented financial calculations.

- `tool-cards.json` uses a test-only echo declaration. It returns the supplied
  known value unchanged, preserves exactly one blank, and declares two editable
  fields. The fixture covers zero, coalesced edits, and independent repeated calls.
- `tool-progress.json` is the same declaration's progress fact, interpolated with
  a known zero. The browser holds the stream after this actual-call event so its
  English and Spanish display can be checked before the result arrives.
- `backtest-cards.json` derives from the existing canonical modeled-cost DCA test
  result, passes through the registered backtest return and presenter, and then
  the public receipt sanitizer. It preserves starting capital zero, recurring
  contributions, cadence, costs, benchmark facts, and the frozen equity visual.

Regenerate from the repository root:

```sh
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 poetry run python web/e2e/support/registry-fixture.py
```

Run the browser checks from `web/`:

```sh
bunx playwright test e2e/tool-registry.spec.ts --workers 1
```

The suite uses the real `/chat` page with fixture API responses. It makes no
provider calls and does not execute a backtest. It checks both languages,
desktop and mobile editable cards, plural live/reloaded results, out-of-order
asynchronous completions, actual-call progress, and the DCA facts and chart.
It also checks that later saved user messages make old cards read-only and that
sending a message cancels a queued input edit before it makes an API request.
The v2 receipt checks in `web/__tests__/tool-backtest-presentation.test.tsx`
render the sanitized presentation through the same card and chart components;
they are not browser checks of the public `/r/` route.

For durable candidate screenshots, run with `REGISTRY_SCREENSHOT_DIR` set to the
absolute path of this directory's `browser/` subdirectory. Capture or explicitly
revalidate them after the candidate commit and record that SHA in the lane audit.

The latest capture at `53ed45df` passed 14 cases. Its
[capture record](browser/53ed45df/README.md) documents the fixture boundary,
viewport adjustments, command, and clean candidate. View the
[English mobile card](browser/53ed45df/tool-card-en-390.png),
[Spanish mobile card](browser/53ed45df/tool-card-es-419-390.png),
[English DCA result](browser/53ed45df/tool-backtest-en.png), and
[Spanish call progress](browser/53ed45df/tool-progress-es-419.png).
