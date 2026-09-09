# Registry fixture-browser evidence at d5ad4b6e

Candidate: `d5ad4b6e1c3e475820a33fa1d55f4f6f1658e467`

Result: **14 passed in 21.5 seconds**, process exit 0. The complete console output is `browser.log`. All 12 PNGs in this directory were inspected after capture.

Working directory: `/Users/garces/.codex/worktrees/aa72/private-alpha-next/web`

Exact command:

```sh
NODE_OPTIONS='--require=/private/tmp/registry-browser-d5ad4b6e/scroll-capture.cjs' REGISTRY_SCREENSHOT_DIR=/private/tmp/registry-browser-d5ad4b6e bunx playwright test e2e/tool-registry.spec.ts --workers 1 > /private/tmp/registry-browser-d5ad4b6e/browser.log 2>&1
```

The external `scroll-capture.cjs` is the prior accepted helper from `/private/tmp/registry-browser-3c4f5aab`, with only its output-log path changed. It changes the actual browser viewport and transcript scroll position before delegating capture to Playwright's original screenshot implementation. The existing suite's screenshot options are preserved. No new DOM, style, card-data, source or fixture changes were made. `scroll-captures.jsonl` records the original/final viewports and actual scroll/card bounds.

| Final PNGs | Browser viewport | Visible evidence |
| --- | --- | --- |
| `tool-card-en-1280.png`, `tool-card-es-419-1280.png` | 1280 x 900 | Zero answer, editable known zero and other input, retained read-only blank, captured after live recompute/reload |
| `tool-card-en-390.png`, `tool-card-es-419-390.png` | 390 x 900 | Same facts and controls at mobile width |
| `tool-backtest-en.png`, `tool-backtest-es-419.png` | 1280 x 1500 | Full DCA answer and chart, contribution/cadence, zero start, modeled costs and SPY benchmark |
| `tool-progress-en.png`, `tool-progress-es-419.png` | 1280 x 720 | Actual executing-call progress with known-zero interpolation |
| `tool-jobs-en.png`, `tool-jobs-es-419.png` | 1280 x 1500 | Both independently completed repeated-call results after reload, earlier read-only and latest editable |
| `tool-history-en.png`, `tool-history-es-419.png` | 1280 x 900 | Full historical read-only card followed by a later saved user message |

The four editable card crops moved from top 0 to top 160 while transcript scrollTop changed from 188 to 28. DCA/history cards reached transcript top, with card top 104 and scrollTop 0. Repeated-call result cards were fully visible at the taller viewport: scrollTop 192, first result card top 340.75. A preceding job-status card extends above the viewport, while both computed result cards are fully visible. Progress retains the application's normal shimmer. User-authored fixture text is not automatically translated.

## Contract continuity

The following read-only comparison returned exit 0 with no diff against the prior evidenced head:

```sh
git diff --exit-code 3c4f5aab93f1928d999a20fc34c4b0a6bcecf5a8 d5ad4b6e1c3e475820a33fa1d55f4f6f1658e467 -- src/argus/domain/tool_contracts.py web/lib/tool-result-card.ts web/lib/chat-final-response-payload.ts web/components/chat/types.ts web/e2e/tool-registry.spec.ts docs/reports/evidence/registry/tool-cards.json docs/reports/evidence/registry/tool-progress.json docs/reports/evidence/registry/backtest-cards.json
```

The intervening frontend change only requires an actual typed answer before offering Share. Its separate focused proof already passed 41 unit cases plus scoped lint: completed zero is shareable, pending/null and omitted answers are not. This browser suite leaves sharing at its default-off setting and does not claim browser coverage of the enabled Share action.

## Limits and cleanup

This runs the real chat frontend against intercepted backend-shaped fixture API responses. It proves fixture-browser presentation, recompute/reload continuity, send cancellation and repeated asynchronous-call handling. It does not claim live backend/provider or backtest execution. No live API, provider calls or paid turns were made by this capture task.

The checkout was clean at the candidate SHA both before and after the run. The owned test server exited; port 3100 had no listener afterward. All new evidence is outside the checkout. The release captain will copy these artifacts into durable repository evidence after the separate live-evaluation provenance freeze ends.
