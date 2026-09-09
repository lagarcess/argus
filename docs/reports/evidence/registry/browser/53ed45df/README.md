# Registry fixture-browser evidence at 53ed45df

Candidate: `53ed45df3bf32848a52bb05f45b3d1faa411d08c`

Result: **14 passed in 21.0 seconds**, process exit 0. Full console output: `browser.log`. All 12 final PNGs were inspected after capture.

Working directory: `/Users/garces/.codex/worktrees/aa72/private-alpha-next/web`

Exact command:

```sh
NODE_OPTIONS='--require=/private/tmp/registry-browser-53ed45df/scroll-capture.cjs' REGISTRY_SCREENSHOT_DIR=/private/tmp/registry-browser-53ed45df bunx playwright test e2e/tool-registry.spec.ts --workers 1 > /private/tmp/registry-browser-53ed45df/browser.log 2>&1
```

The external helper was copied from the prior accepted `/private/tmp/registry-browser-d5ad4b6e/scroll-capture.cjs`, changing only its output-log path. It changes the real browser viewport and transcript scroll position before calling Playwright's original screenshot implementation. Existing suite screenshot options are preserved. No new DOM, style, card-data, source or fixture changes were made. `scroll-captures.jsonl` records original/final viewports and actual scroll/card bounds.

| Final PNGs | Browser viewport | Visible evidence |
| --- | --- | --- |
| `tool-card-en-1280.png`, `tool-card-es-419-1280.png` | 1280 x 900 | Zero answer, editable known zero and other input, retained read-only blank after live recompute/reload |
| `tool-card-en-390.png`, `tool-card-es-419-390.png` | 390 x 900 | Same facts and controls at mobile width |
| `tool-backtest-en.png`, `tool-backtest-es-419.png` | 1280 x 1500 | Full DCA result and chart, contribution/cadence, zero starting capital, modeled costs and SPY benchmark |
| `tool-progress-en.png`, `tool-progress-es-419.png` | 1280 x 720 | Actual executing-call progress with known-zero interpolation |
| `tool-jobs-en.png`, `tool-jobs-es-419.png` | 1280 x 1500 | Both independently completed repeated-call results after reload, earlier read-only and latest editable |
| `tool-history-en.png`, `tool-history-es-419.png` | 1280 x 900 | Full historical read-only card followed by a later saved user message |

Editable card crops moved from top 0 to top 160 while transcript scrollTop changed from 188 to 28. DCA/history cards reached transcript top, with card top 104 and scrollTop 0. Repeated-call result cards were fully visible in the taller viewport: scrollTop 192 and first result card top 340.75. A preceding job-status card extends above the viewport while both computed result cards remain fully visible. Progress retains the application's normal shimmer. User-authored fixture text is not automatically translated.

## Continuity and limits

The following read-only comparison returned exit 0 with no diff against the prior evidenced head:

```sh
git diff --exit-code d5ad4b6e1c3e475820a33fa1d55f4f6f1658e467 53ed45df3bf32848a52bb05f45b3d1faa411d08c -- web/lib/tool-result-card.ts web/lib/chat-final-response-payload.ts web/components/chat/types.ts web/components/chat/ToolResultCard.tsx web/e2e/tool-registry.spec.ts docs/reports/evidence/registry/tool-cards.json docs/reports/evidence/registry/tool-progress.json docs/reports/evidence/registry/backtest-cards.json
```

This is fresh evidence at the current candidate despite unchanged UI presentation contracts and fixtures. It runs the real chat frontend against intercepted backend-shaped fixture API responses. It covers presentation, recompute/reload continuity, send cancellation and repeated asynchronous-call handling. It does not claim execution of the changed runtime return declarations or private queue context, live backend/provider execution, or a real backtest. Sharing remains default-off in this matrix; its separate focused unit proof is retained.

No live API/provider calls or paid turns were made by this capture task. The checkout was clean at the candidate SHA before and after the run. The owned test server exited and port 3100 had no listener afterward. All evidence deliverables are outside the checkout, ready for the release captain's durable copy after the provenance freeze.
