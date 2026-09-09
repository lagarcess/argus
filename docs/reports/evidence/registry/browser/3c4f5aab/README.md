# Registry fixture-browser evidence

Candidate: `3c4f5aab93f1928d999a20fc34c4b0a6bcecf5a8`

Working directory: `/Users/garces/.codex/worktrees/aa72/private-alpha-next/web`

The existing `e2e/tool-registry.spec.ts` battery passed all 14 cases. The retained console output is `recapture-browser.log`: 14 passed in 21.0 seconds. These captures were inspected by the presentation worker; the parent also inspected the English mobile card, Spanish DCA card, and English progress image.

Initial command:

```sh
REGISTRY_SCREENSHOT_DIR=/private/tmp/registry-browser-3c4f5aab bunx playwright test e2e/tool-registry.spec.ts --workers 1
```

Recapture command:

```sh
NODE_OPTIONS='--require=/private/tmp/registry-browser-3c4f5aab/scroll-capture.cjs' REGISTRY_SCREENSHOT_DIR=/private/tmp/registry-browser-3c4f5aab bunx playwright test e2e/tool-registry.spec.ts --workers 1 > /private/tmp/registry-browser-3c4f5aab/recapture-browser.log 2>&1
```

The external `scroll-capture.cjs` preload only changes the browser viewport and scroll position immediately before a screenshot. It delegates capture to Playwright's original screenshot implementation. No application DOM, styles, card data, source, or fixtures were changed. `scroll-captures.jsonl` records the original/final viewports and actual scroll/card bounds for each repositioned image.

## Final images

These 12 PNGs at this directory's top level are the final inspected captures to retain. Earlier occluded captures were superseded and are not used as acceptance evidence.

| Files | Browser viewport | Visible evidence |
| --- | --- | --- |
| `tool-card-en-1280.png`, `tool-card-es-419-1280.png` | 1280 x 900 | Editable known zero, another numeric input, read-only blank input, and zero answer after live recompute/reload |
| `tool-card-en-390.png`, `tool-card-es-419-390.png` | 390 x 900 | Same card facts and controls at mobile width |
| `tool-backtest-en.png`, `tool-backtest-es-419.png` | 1280 x 1500 | Complete DCA card, contribution return, chart, contribution/cadence, zero starting capital, modeled costs and benchmark |
| `tool-progress-en.png`, `tool-progress-es-419.png` | 1280 x 720 | Actual executing-call progress, interpolating the known zero |
| `tool-jobs-en.png`, `tool-jobs-es-419.png` | 1280 x 1500 | Both independently completed repeated-call result cards, latest editable and earlier read-only |
| `tool-history-en.png`, `tool-history-es-419.png` | 1280 x 900 | Entire historical read-only card followed by a later saved user message |

The four editable card crops were physically moved from top 0 to top 160, with transcript scrollTop changing from 188 to 28. The DCA/history cards reached transcript top: card top 104 and scrollTop 0. The repeated-job result cards were fully visible in the taller viewport; scrollTop remained 192 and the first result card top was 340.75. A preceding job-status card can extend above the viewport; both computed result cards are fully visible. These are faithful rendered-browser captures, with no compositing or image edits.

All 12 final images were inspected. The progress text uses the application's normal animated shimmer. User-authored fixture text is not automatically translated.

## Limits and cleanup

This is the real chat frontend running against intercepted, backend-shaped fixture API responses. It proves fixture-browser behavior and presentation, including reload, but does not claim live backend, provider, or calculation execution. No provider calls or paid turns were made. The fixture itself is the test-only echo declaration plus canonical generated DCA facts.

The checkout remained clean at the candidate SHA after the final run. No listener remained on the test server's port 3100. Source, fixtures and repository documentation were left untouched. The parent preserved these files after the live provenance freeze ended. This records browser evidence at this candidate, not a current-head release-readiness claim. The preload preserves the exact environment-specific paths used for this capture; adjust its two filesystem paths when reproducing from a different checkout.
