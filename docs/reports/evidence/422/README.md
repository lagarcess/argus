# Issue #422 breakpoint repair evidence

The `before` and `after` folders contain one 390 by 844 real-viewport frame
for each confirmed finding, plus rendered text and geometry metadata where an
image alone is ambiguous. The branch-point runtime was
`360d7bc6c93ab4b90c1b58ab08fd8a68553500a5`; the before frames were captured
from the runtime-equivalent docs-only head
`397235006ec8cbc50f5a113170437917853e632e`.

The `after` folder was regenerated and every rendered-text and geometry file
was re-read at product-and-harness capture head
`88a1d9882775197c61983824df990590018611cb`. All nine focused browser checks
passed, including the 720px and 1024px no-regression checks, and the command
changed only the known auth antialias frame described below. The following
evidence-manifest commit changes this README and that recaptured PNG, not the
rendered product or capture harness. The same capture command must be rerun on
the published PR head and recorded in the PR terminal audit; a commit cannot
contain its own final SHA.

| Finding | Before | After | Acceptance proof |
| --- | --- | --- | --- |
| 2 | [`finding-2-omnisearch-title.png`](before/finding-2-omnisearch-title.png) | [`finding-2-omnisearch-title.png`](after/finding-2-omnisearch-title.png) | The title grows from 92 of 191 pixels to 280 of 280 pixels, so the full title renders. |
| 3 | [`finding-3-omnisearch-date-menu-gap.png`](before/finding-3-omnisearch-date-menu-gap.png) | [`finding-3-omnisearch-date-menu-gap.png`](after/finding-3-omnisearch-date-menu-gap.png) | The two intervening lanes had partially masked the original overlap, but only 4 pixels remained at this branch point. The fixed layout reserves 12 pixels. |
| 4 | [`finding-4-confirmation-symbol.png`](before/finding-4-confirmation-symbol.png) | [`finding-4-confirmation-symbol.png`](after/finding-4-confirmation-symbol.png) | Rendered `AAPL` occurrences fall from two to one while the entity token remains. |
| 5 | [`finding-5-spanish-usage-singular.png`](before/finding-5-spanish-usage-singular.png) | [`finding-5-spanish-usage-singular.png`](after/finding-5-spanish-usage-singular.png) | `Quedan 1` and `1 disponibles` become `Queda 1` and `1 disponible`. Only the two issue-approved reachable key families changed. |
| 6 | [`finding-6-spanish-auth-diacritics.png`](before/finding-6-spanish-auth-diacritics.png) | [`finding-6-spanish-auth-diacritics.png`](after/finding-6-spanish-auth-diacritics.png) | Placeholders and password-control labels now include the required Spanish accents. |
| 7 | [`finding-7-dossier-title.png`](before/finding-7-dossier-title.png) | [`finding-7-dossier-title.png`](after/finding-7-dossier-title.png) | Visible title count falls from two to one. The sheet keeps one screen-reader-only heading as its accessible dialog name. |
| 8 | [`finding-8-chart-leading-label.png`](before/finding-8-chart-leading-label.png) | [`finding-8-chart-leading-label.png`](after/finding-8-chart-leading-label.png) | The chart's leading year changes from clipped `023` to fully visible `2023`. |

The deliberate visual baseline changes are:

- `login-390-es-light.png`, `signup-390-es-light.png`, and
  `account-security-390-es-light.png` for the corrected Spanish diacritics.
- `issue-422-chart-390-chromium-darwin.png` for the 24-pixel chart edge gutter.
  That baseline moves 930 pixels because the visible range and line scale both
  change. The suite budget remains `maxDiffPixels: 100`.
- `result-chart-responsive-resize-chromium-darwin.png` for the review repair
  that reapplies the semantic window and 24-pixel gutter after a wide chart
  narrows. It is a new capture, not an update to an existing baseline, and uses
  the same `maxDiffPixels: 100` ceiling.

After the review repair separated visual padding from semantic chart facts,
the durable finding 8 frame was recaptured with the same fixed screenshot
settings as its baseline. It now matches that baseline byte-for-byte. The
superseded evidence frame differed at 42 pixels by one color-channel step; the
visual baseline itself did not move and the tolerance was not changed.

The Spanish auth evidence frame uses the same shared capture settings and now
matches `login-390-es-light.png` byte-for-byte. A prior exact-head recapture
differed at 34 grayscale antialias pixels on the button edge; its RGB channels
moved together by at most 33, with no changed text or geometry. Both raw frames
pass the fixed-budget visual matcher, the final frame was visually inspected,
and neither the baseline nor the tolerance moved.

The final-head capture command rewrites the `after` folder and must leave the
worktree clean before the lane is reported ready.
