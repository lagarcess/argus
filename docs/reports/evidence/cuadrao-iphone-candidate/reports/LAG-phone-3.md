# LAG-phone-3: Insights history, spending highlights and Search

Worker: lag. Date: October 4. Branch `claude/cuadrao-lag-fixes` (PR #812), head **`b56c56d344d840b92f18d804e9a94f2627c1b810`**,
pushed with the explicit refspec, no force. Build **3427** (tree `5753b5d7c`, clean) is on the iPhone 15.
Status: three fixes committed and pushed, host identity check added, 19 simulator UI tests green, launch and idle
re-recorded with no regression. The interaction re-measurement (`run-3`) waits for Lucas.

## What the lead does next

```bash
~/.claude/orchestrate/cuadrao-iphone-candidate/lag-phone/tools/part2.sh run-3
```

`reports/LAG-needs-founder.md` now names build 3427 and `run-3`, and asks Lucas not to quit the app and to
perform the script once. Callees afterwards: `python3 lag-phone/tools/callees.py lag-phone/part2/run-3.trace
"CanvasBalanceHistory.points" "CuadraoHomeInsights.body" "CuadraoSpendingHighlights.body" "CuadraoSearchCanvas.body"`.

## run-2 analysis (build 3426, `lag-phone/part2/run-2.trace`)

Hitches 258 to 67, hitch time ratio 62.0 to 29.6 ms/s against run-1. Main thread 16696 ms sampled over 87.7 s
(samples run from 3.38 s to 91.12 s). Callee tables: `lag-phone/part2/run-2.callees.txt`.

**The big hitches are not shown to be a quit and relaunch.** The trace holds one process for its whole
length: one process id (12188) on every time-profile sample and every hitch row, one launch sequence, and the
life-cycle table reads "Foreground - Active" for 1.50 min with no Inactive or Background period. What the
trace does show is that the time profiler has **no samples on any thread of the app between second 77 and
second 85**. The 733 ms hitch (83.248 s) and the 167 ms hitch (83.998 s) fall inside that gap, so "0 ms of
main-thread time" means no data, not an idle thread. The hitch instrument's own update rows show app updates
of 29 ms and 64 ms at 83.03 to 83.06 s, so the app was drawing then. The four 50 ms hitches at 99.5 to 100.5 s
are after the last sample for the same reason (hitch rows continue about 9 s past the last time-profile
sample). I cannot say from the trace what happened on the phone at 77 to 85 s; if a quit and relaunch
happened, it is not recorded as a process end in this trace. These six hitches cannot be attributed to app code.

Top ten app symbols by inclusive main-thread time (closures of one body counted under that body):

| # | Symbol | Inclusive | Share of 16696 ms |
| --- | --- | --- | --- |
| 1 | `CanvasBalanceHistory.points` | 1059 ms | 6.3% |
| 2 | `CuadraoHomeInsights.body` and its closures | 691 ms | 4.1% |
| 3 | per-point closure in `CuadraoHomeBalanceChartContent.chartBase` | 599 ms | 3.6% |
| 4 | `CuadraoHomeInsights.oldest` | 526 ms | 3.2% |
| 5 | `CanvasBalancePeriod.init` | 329 ms | 2.0% |
| 6 | `CuadraoHomeBalanceChartContent.body` | 290 ms | 1.7% |
| 7 | `CuadraoHomeBalanceChartContent.reading` | 255 ms | 1.5% |
| 8 | `CuadraoSpendingHighlights.body` | 248 ms | 1.5% |
| 9 | `CuadraoHomeBalanceChart.body` | 240 ms | 1.4% |
| 10 | `CanvasSpendingStory.longitudinalInsights` | 224 ms | 1.3% |

Rows overlap: 4, 5 and 9 are the three callers of row 1, and row 10 sits inside row 8. App frames are a
small share of the main thread; the rest is SwiftUI, AttributeGraph and Swift runtime work.

| Cost | Callers | Where the time goes |
| --- | --- | --- |
| `CanvasBalanceHistory.points` 1059 ms | `CuadraoHomeInsights.oldest` 498 ms; `CanvasBalancePeriod.init` 323 ms (241 ms from the expanded chart's `period`, 88 ms from `periodContent`, the distribution page); `CuadraoHomeBalanceChart.body` 238 ms | `NSDecimal./` 705 ms, `*` 113 ms, dictionary find 62 ms |
| `CuadraoHomeInsights.body` 691 ms | body update 541 ms, ForEach page closures 150 ms | `oldest` 526 ms (211 ms from the body, 315 ms from the TabView closure), `periodContent` 123 ms |
| `CuadraoHomeInsights.oldest` 526 ms | as above | `points` 498 ms, spending expenses 18 ms |
| `CanvasBalancePeriod.init` 329 ms | chart content 241 ms, Insights 88 ms | `points` 323 ms, snapshot 3 ms |
| `CuadraoSpendingHighlights.body` 248 ms | body update | `longitudinalInsights` 224 ms: `featured` 145 ms, "See all" destination 34 ms, emptiness test 24 ms, `hasMore` 21 ms. Inside it `completedMonths` 218 ms (entries filter 71 ms, calendar month intervals 58 ms) |
| `CuadraoSearchCanvas.body` 43 ms | `NavigationStack` content at first appearance | `activity` 38 ms (25 ms from the list, 13 ms from `count`), 30 ms of it `availableAccounts` |

Sampled hitches: 48.238 s (67 ms, main thread 79 ms, history builder 50 ms under Insights); 56.225 s (67 ms,
79 ms, `longitudinalInsights` 30 ms); 68.522 s (117 ms, 98 ms, Search body 16 ms, `activity` 8 ms, "expensive
render, 12 offscreen passes"); 19.635 s and 29.635 s (33 ms each, history builder 20 and 26 ms).

## What changed

1. `0bd55440d` perf(ios): build one balance history per Insights pass and hand it to its pages and periods.
   Files: `CuadraoBalanceHistory.swift` (new value `CanvasBuiltBalanceHistory`: the points and the day they
   were built for, `points(on:)` returns them only on that day), `CuadraoBalancePeriod.swift` (second
   initializer taking the history; the existing one builds it and delegates, so its other callers and the
   host checks are untouched), `CuadraoHomeBalanceChart.swift` (optional `history:` parameter; the content
   view takes one `now` per `reading`, and gives the same history to its period), `CuadraoHomeInsights.swift`
   (one build per body pass in balance mode, `oldest` read once for the page range and `onChange`, the
   distribution page builds its period once instead of twice), `HomeBalanceChecks.swift`.
   The shape is the one in `R-lag-20f31941.md` item 5: about eight builds per Insights pass, now one.
   Activity mode builds no balance history, as before. Event handlers (`movePeriod`, the metric setter,
   `onAppear`) still read live.
2. `8a3f28480` perf(ios): walk the spending story's months once per highlights pass.
   `CuadraoSpendingHighlights.swift`: the body reads `story.longitudinalInsights` once and passes it to
   `featuredInsights`, `hasMore` and the "See all" destination. The story stores its own `now`, so every read
   in a pass already returned the same value.
3. `5753b5d7c` perf(ios): filter the Search account list once per activity pass, not once per row.
   `CuadraoSearchCanvas.swift`, one local in `activity`.
4. `b56c56d34` docs: `docs/reports/evidence/cuadrao-lag/phone-insights-highlights-search.md`.

Not touched: `CanvasDecimalInput`, money typing, any modifier, identifier, copy, gesture or transition.

Exactness, stated plainly. Every derived value keeps its expression. Two timing details differ from the old
code and neither changes a result inside one day: the expanded chart's period now uses the same `now` as the
rest of its `reading` (it used to read the clock a few microseconds later), and a page uses the history its
owner built in the same pass. A pass that straddles midnight used to mix two days; a handed history is now
refused on the next day and the reader builds its own.

## Test results (commands as run)

| Command | Result |
| --- | --- |
| `python3 ios/DesignPreviewTests/run_home_balance.py` | Passed 82 Home balance projection checks (81 before; the new one compares a period given a history built earlier the same day with one that builds its own, 3 ranges x offsets 0 to -14 x 5 fixtures, and that the history is refused the next day) |
| `ios/scripts/cuadrao-design-mac-pass.sh checks` (tree of `5753b5d7c`, before commit) | `== checks: ok`; money format 9 x Passed 12157 |
| `SIMULATOR_ID=0335699A-… ios/scripts/verify.sh build` (Debug) | BUILD SUCCEEDED |
| Under the lock, `verify.sh test -collect-test-diagnostics never` on iPhone 18 Pro Max with `-only-testing:` `CuadraoHomeChartUITests` (class), `CuadraoSupportUITests/{testSearchPlansChatReturnAndRecovery, testActivityDetailsReturnToSearchAndAccount, testGroupSearchFiltersArchiveAndReturn, testFirstUseSavedChatAppearsInSearch}`, `CuadraoHistoryDesignUITests/testSharedDatesInSearchAndLargerText`, `CuadraoContextUITests/testChartContextKeepsPeriodAndDistributionSelection` | 19 tests, 0 failures, TEST SUCCEEDED. Log and xcresult: `lag-phone/sim-fix3-insights-highlights-search/` |
| `lag-phone/tools/build-install.sh 3427` | `head=5753b5d7c… dirty=0`, CFBundleVersion 3427, "App installed", `devicectl device info apps` reads 3427 |
| `lag-phone/tools/part1.sh lag-phone/fix3-3427` | nine recordings, all exit 0 |

Which classes cover what: Insights paging, ranges, distribution, breakdown and spending highlights are all in
`CuadraoHomeChartUITests` (13 tests, including `testSpendingHighlightsAndReturn`, `testSpendingHighlightsLargeEnglish`,
`testHistoryRangesAndDistribution`, `testInteractivePagingAndBalanceMeaning`, `testBalanceBreakdownAndAccountReturn`).
Search is in `CuadraoSupportUITests` (four search tests) and `CuadraoHistoryDesignUITests/testSharedDatesInSearchAndLargerText`.
The distribution selection across periods is also in `CuadraoContextUITests/testChartContextKeepsPeriodAndDistributionSelection`.

Observed, not explained: `testFirstUseSavedChatAppearsInSearch` took 441 s and passed. I have no duration for
it at the previous head, so I cannot say whether that is normal. The other 18 took 7 to 39 s each.

Not run: the rest of `CuadraoSupportUITests`, `CuadraoHistoryDesignUITests` and `CuadraoContextUITests` (not
related to the change), and the full UI suite (rule 16).

## Part 1 on build 3427 (`lag-phone/fix3-3427/`)

| Measurement | fix2-3426 | fix3-3427 |
| --- | --- | --- |
| Initial Frame Rendering, 5 cold launches | 286, 319, 317, 171, 179 ms | 277, 169, 165, 167, 167 ms |
| UIKit Initialization, same launches | 204, 178, 190, 70, 73 ms | 165, 68, 65, 68, 67 ms |
| Initial Frame Rendering in the 40 s hitches recording | 167 ms | 171 ms |
| Hitches, 40.9 s | 0 | 0 |
| Hangs or interaction delays recorded | 34 ms at launch | none |
| Main thread CPU, first 3 s | 370 ms | 381 ms |
| Process CPU, first 3 s | 643 ms | 685 ms |
| `CanvasBalanceHistory.points`, first 3 s | 2 ms | 2 ms |
| Idle Home, process CPU, seconds 10 to 40 | 5 ms | 6 ms |
| Idle Home, main thread CPU, seconds 10 to 40 | 1 ms | 1 ms |
| Thermal state | Nominal | Nominal |

No regression. The first launch after the install is slow in the system's UIKit Initialization phase again
(165 ms against about 67 ms), the same pattern as 3426. First-3-s CPU is 11 ms and 42 ms higher on one
recording each; nothing this change touches runs at launch except the Home chart's one history build, which
reads 2 ms in both. SwiftUI and Activity Monitor traces were recorded and not summarised.

## Expected effect on run-3 (prediction, not a measurement)

Range, period and metric changes in Insights lose most of the history cost: about 50 ms of 79 ms in the
48.2 s frame becomes about 6 ms (one build). The highlights frame loses about 25 of 30 ms. The Search first
frame loses about 6 of 98 ms and will still hitch. Scrub frames are unchanged by this round.

## Deferred, with measured cost (run-2)

| Item | Cost | Why deferred |
| --- | --- | --- |
| Search tab first frame: offscreen passes | 117 ms hitch, 12 offscreen passes; main thread 98 ms, of which app code 16 ms | Polish: the render cost of the drawn design. Out of this round by brief |
| Other frames flagged for offscreen passes | 20, 39 and 48 passes on 16 to 50 ms hitches at 86.0, 100.1 and 89.1 s | Same |
| Per-point closure in the Home chart | 599 ms over the run | Swift Charts builders and eager accessibility strings; see LAG-phone-2 item 3 |
| `NSDecimal./` in `CanvasBalanceHistory.contribution` | 705 ms over the run | Arithmetic rewrite with its own equality proof. After this round it is reached once per Insights pass instead of about eight times |
| Home chart outer body builds one history per Home pass | inside the 238 ms | The floor without a stored cache |
| `CuadraoSearchCanvas.activity` read from up to four places in the body | about 8 ms left of 38 ms | Small against a 98 ms frame |
| `CanvasSpendingHistory.expenses` rebuilt per Insights page in activity mode | 43 ms over the run | Not in a sampled hitch |
| `completedMonths` walks all expenses per month and category | 218 ms over the run before this round, about a quarter of that after | One pass per body is left; a single bucketing pass is an arithmetic rewrite |
| Six hitches with no samples (83.2 s 733 ms, 84.0 s 167 ms, four at 99.5 to 100.5 s) | 1100 ms of the 2582 ms of hitch time | No samples; needs the clean run-3 |
| Money typing (`-[UITextField setText:]`) | not re-read this round | Not touched by brief |

## Decision log

1. Ran `callees.py` on run-2 before reading source. It showed three callers of the history builder, the
   highlights reading one expensive story property from four places, and Search rebuilding an account list
   per row.
2. Checked the quit and relaunch claim against the process id, the life-cycle table and the sample
   timestamps. Found a sampling gap, not a process end.
3. For the history, one small value type carries the points and their day, replacing the two loose fields the
   chart content had. Rejected a stored cache again. Rejected passing a bare array, which would lose the day
   guard at each reader.
4. Kept the existing `CanvasBalancePeriod` initializer and delegated it, so the 11 host-check call sites and
   their results are untouched; added one check that compares both initializers.
5. Highlights and Search: hoists only. Did not hoist the four `activity` reads in the Search body (8 ms).
6. Did not use a helper agent or the panel skills: six small files inside an 80 minute box.
7. Removed a line I had first added to the founder script asking for extra steps; the script stays identical
   to run-1 and run-2 so run-3 compares.

## Final head

`b56c56d344d840b92f18d804e9a94f2627c1b810` on `claude/cuadrao-lag-fixes`, equal to `origin`. On top of `31db6f7cb`:
`0bd55440d` (Insights history), `8a3f28480` (highlights), `5753b5d7c` (Search, the tree build 3427 was made from),
`b56c56d34` (evidence).
