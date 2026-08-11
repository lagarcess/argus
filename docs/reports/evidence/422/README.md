# Issue #422 breakpoint repair evidence

The `before` and `after` folders contain one 390 by 844 real-viewport frame
for each confirmed finding, plus rendered text and geometry metadata where an
image alone is ambiguous. The branch-point runtime was
`360d7bc6c93ab4b90c1b58ab08fd8a68553500a5`; the before frames were captured
from the runtime-equivalent docs-only head
`397235006ec8cbc50f5a113170437917853e632e`.

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

The final-head capture command rewrites the `after` folder and must leave the
worktree clean before the lane is reported ready.
