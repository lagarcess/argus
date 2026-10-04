# R-lag-b56c56d3: independent review of the Insights, highlights and Search changes

Reviewer: independent, read-only. PR #812, head `b56c56d344d840b92f18d804e9a94f2627c1b810`.
Scope: `git diff 31db6f7c..b56c56d3 -- ios` (commits `0bd55440d`, `8a3f28480`, `5753b5d7c`).
Method: `git show` / `git diff` in the `cuadrao-lag` worktree, plus the host check run from `git archive` copies.
No simulator, no xcodebuild, no phone, no edits, no GitHub comments.

## Verdict: CLEAN

No P1, no P2. One P3 note (pairing of a handed history with its inputs is by convention, all call sites
confirmed). Line numbers below are at `b56c56d3` unless marked "old" (`31db6f7c`).

## 1. Same inputs, same expressions; staleness traced

Key fact everything rests on: `CanvasBalanceHistory.points` reads the clock and the calendar only through
`today = Calendar.current.startOfDay(for: now)` (`CuadraoBalanceHistory.swift:30-31`, used at :36 and :49).
Two builds with the same accounts and observations whose `startOfDay` instants are equal return equal points.
`CanvasBuiltBalanceHistory` stores that instant (`:99`) and `points(on:)` returns the points only when the
instant matches (`:101-103`). This is the same rule the old chart used (`builtDay`, old
`CuadraoHomeBalanceChart.swift:56-59`), now in one value.

| Value | Old | New | Result |
| --- | --- | --- | --- |
| Compact Home chart history | outer body builds at `.now`, content reuses while the day matches | `CuadraoHomeBalanceChart.swift:33`, `:56-58` | identical (Home passes no `history`, `CuadraoHomeOverview.swift:11-14`) |
| Expanded chart points, ranges, x domain, bounds, selection | `reading` from `history` | `:71-94`, same expressions on `history(now)` | identical |
| Expanded chart period | `CanvasBalancePeriod(..., offset: periodOffset)` with default `now: .now`, building its own history | `:87-88`, same accounts, observations, range, offset; `now` is the one read at `:71`; history is the one from `:72` | identical inside a day |
| `onAppear` clamp | `range.oldestOffset(history)` | `:150` `range.oldestOffset(history(.now))` | identical |
| Insights page range and `onChange(of: oldest)` | `oldest` property read twice per pass | `CuadraoHomeInsights.swift:75`, one local; balance mode uses `built.points`, activity mode never evaluates the autoclosure (`:37-39`) | identical |
| Distribution page | `balancePeriod(offset)` twice (accounts, `closing?.date`) | `:62-64`, once, both fields from the same period | identical |
| Event handlers (`movePeriod` `:51`, metric setter `:25`) | live read | unchanged, still live | identical |

`CanvasBalancePeriod`: the old body moved verbatim into the new initializer; the only removed line is the
`let history = ...` build, which the old initializer now passes in (`CuadraoBalancePeriod.swift:27-31`).
`window`, `closing`, `opening`, `today`, snapshots, `changes`, `isPartial` are unchanged (`:36-55`).

Staleness, each path:

- **Period swipes (up to three live pages).** `periodOffset` is read only inside the `ForEach` closure
  (`:85`), so a swipe can re-run page closures with the `built` captured at the last body pass. Each page
  passes its own `offset` and the live `range`; the history is not a function of offset or range, so one
  history for three pages is exact. The captured history can only go stale through data, clock or time zone:
  - data: `CuadraoAccountsPreview` is `@Observable` (`CuadraoAccountsPreview.swift:51`) and the body reads
    `data.active` and `data.balanceObservations` at `:74`, so a data change invalidates the body and the
    pages are rebuilt from the new closure before they are read;
  - clock: guarded by `points(on:)` at both readers (`CuadraoHomeInsights.swift:42`, chart `:57`);
  - time zone: guarded the same way, see below.
- **Distribution selection.** `distribution` is read in the page closure; same analysis. The fallback at
  `:42-43` builds its own history when the handed one is refused or absent.
- **Range change.** `range` is read in the body (`:98`), body re-runs, new `built`. Even without that, the
  history does not depend on range.
- **Metric change.** `activity` is read at `:74`. In activity mode `built` is nil and no balance history is
  built, as before. A nil `built` reaching a balance page would only fall back to a fresh build.
- **Scrub (content re-evaluates without the parent).** `reading` takes a fresh `now` each time (`:71`) and
  checks the day, as the old `history` property did.

Author claim "the expanded chart's period now uses the same `now` as the rest of its pass": **true**
(`:71`, `:72`, `:87-88`). Old code read `.now` once for the day check and again in the period's default
argument. The results differ only if midnight falls between those two reads; then the old code drew points
from day D beside a period from day D+1, and the new code is consistent. Note `range.interval(offset:)` for
the x domain (`:78`) and `range.points(history, offset:)` (`:75`) still take their own default `.now`; that
is unchanged from the old code and not in scope.

Author claim "a handed history carries its day and is refused on the next day": **true**.
- Exactly at midnight: `startOfDay(midnight D+1)` is that instant, not `day` D, so `points(on:)` is nil and
  the reader builds for D+1. The host check asserts this (`HomeBalanceChecks.swift:188`, `later + 3600` is
  the next midnight on the fixture days).
- After a refusal the chart rebuilds on every `reading` until the owner's body runs again. Cost only, and the
  old chart did the same after its `builtDay` stopped matching.
- Time zone change: `Calendar.current` is read at call time on both sides. The stored `day` is midnight in
  the old zone; the check computes midnight in the new zone. If the instants differ the history is refused
  and rebuilt. If they are equal (same offset, or zones exactly 24 h apart such as Apia and Pago Pago), a
  fresh build would use the same `today` instant and return the same points, so accepting is exact.
- The page range (`oldest`) is not re-derived at midnight or on a zone change unless the body runs; the old
  code had the same property (both `oldest` reads were in the body pass).

## 2. Can the new initializer receive a history from other inputs?

**By convention, not by construction.** `CanvasBalancePeriod.init(..., now:, history:)` takes any
`[CanvasBalancePoint]`; the contract is the doc comment at `CuadraoBalancePeriod.swift:33`. Likewise
`CuadraoHomeBalanceChart.history` (`CuadraoHomeBalanceChart.swift:16-17`). `CanvasBuiltBalanceHistory` has
one explicit initializer, so it cannot be assembled from loose points, but it does not carry its accounts or
observations. All call sites at head:

| Call site | History source | Same inputs |
| --- | --- | --- |
| `CuadraoBalancePeriod.swift:29-30` | built from the initializer's own arguments | yes, by construction |
| `CuadraoHomeBalanceChart.swift:87-88` | `history(now)`: `built` (line 33 from the view's own `accounts`/`observations`, or handed) or a fresh build from the same properties (`:57`) | yes |
| `CuadraoHomeInsights.swift:45` | `built` from `:74`: `accounts`, `data.balanceObservations` | yes, same two expressions as the period's arguments |
| `CuadraoHomeInsights.swift:66-68` (hands `built` to the chart) | `:74` | yes, chart gets `accounts`, `data.balanceObservations` |
| `CuadraoHomeOverview.swift:11-14` | passes no history | chart builds its own |
| `HomeBalanceChecks.swift:193` | `built` from the same `accounts`, `observations` | yes |

In Insights the build (`:74`, body) and the uses (`:45`, `:66`, page closure) evaluate `accounts` and
`data.balanceObservations` at different moments; they agree because any change to them invalidates the body
first (item 1). **P3, optional:** let `CanvasBuiltBalanceHistory` keep its accounts and observations and
vend the period (`built.period(range:offset:now:)`), which would make the pairing unbreakable. Not needed
for this candidate.

## 3. View tree, identity, modifiers, accessibility, gestures

Unchanged. Insights: the only body edits are two `let`s before `NavigationStack` (`:74-75`) and the `built`
argument (`:88`); the distribution branch gains a `let` inside the same `@ViewBuilder` branch (`:62`), which
does not change the view type. `.id(range.rawValue + String(activity))`, tags, identifiers, hidden flags,
accessibility actions, sheet, dialog, `onChange` are byte-identical. Chart: the content view's two `let`s
became one (`:49`); `@State compactRange`, `@State selectedDate`, bindings and every modifier are unchanged;
the outer view gains one plain `var history` (not state; the view already holds closures, so its comparison
behaviour is unchanged). Highlights: two `let`s before the `if`, `allHighlights` became a function with the
same body; identifiers and `ForEach(featured)` identity (`CanvasSpendingInsight.id` is derived from
category, kind and month count, `CuadraoSpendingStory.swift:71`) unchanged. **No stored cache, no new
`@State`, no new `@Binding`.**

## 4. Spending highlights and Search

Highlights: `story` is a `let` value with a stored `now` (`CuadraoSpendingStory.swift:9`);
`longitudinalInsights` and `completedMonths` read only `expenses`, `coverageStart`, `interval`, `now`
(`:76-112`), so every read in one pass already returned the same array in the same order. The body reads it
once (`CuadraoSpendingHighlights.swift:19`) and hands it to `featuredInsights` (`:7-11`), `hasMore`
(`:12-16`) and `allHighlights` (`:39`); the three expressions are unchanged. Empty list: `insights` empty
and no changed category hides the section (`:21`); empty `insights` with a changed category gives
`featured == []`, comparison card shown, `hasMore` true only if a largest expense exists: same arithmetic as
before. The "See all" destination was already evaluated eagerly in the body, so no laziness changed.

Search: `availableAccounts` depends on `data.accounts`, `data.spaces`, `currency`, `scope`
(`CuadraoSearchCanvas.swift:29-35`). The `activity` filter now reads it once (`:40`) instead of once per
entry; the predicate, `matches`, `subtitle` and the sort (`:41-44`) are unchanged. Empty account list gives
an empty result in both versions. Accounts cannot change between rows: the filter is one synchronous
main-thread call inside one body pass, nothing mutates state during it.

## 5. Host check

Run from `git archive b56c56d3 ios` in the scratch area:
`python3 ios/DesignPreviewTests/run_home_balance.py` -> **Passed 82 Home balance projection checks**.
Same command on `git archive 31db6f7c ios` -> Passed 81. I also compiled the same sources by hand and ran
the binary under `TZ=` America/Santo_Domingo, America/New_York, Europe/Madrid, Pacific/Apia, Asia/Kolkata,
UTC, America/Sao_Paulo, Africa/Cairo: 82 each.

The 82nd check (`HomeBalanceChecks.swift:185-205`) does exercise the new initializer: for 5 fixtures x 3
ranges x offsets 0 to -14 it builds a history at `now`, then at 23:00 the same day compares a period given
that history (`:193`) with one that builds its own (`:192`) on interval, opening, closing, partial flag,
change, closing account ids and balances, and per-account opening and closing. It also asserts the history
is accepted at 23:00, refused at the next midnight, and equal to a fresh build at 23:00 (`:187-189`).
Limit, stated plainly: the "own" side now delegates to the new initializer, so the check proves "history
built earlier that day equals history built now", not parity with the pre-change body. That parity rests on
the diff (one line moved) and on the 81 older checks, which all pass through the delegating initializer
unchanged. It does not cover a time zone change. Neither is a defect.

## 6. Nothing else changed

`git diff --stat 31db6f7c..b56c56d3 -- ios` lists seven files: `CuadraoBalanceHistory.swift`,
`CuadraoBalancePeriod.swift`, `CuadraoHomeBalanceChart.swift`, `CuadraoHomeInsights.swift`,
`CuadraoSearchCanvas.swift`, `CuadraoSpendingHighlights.swift`, `DesignPreviewTests/HomeBalanceChecks.swift`
(85 insertions, 32 deletions). `CanvasDecimalInput` is untouched. The only file outside `ios` is the
evidence note under `docs/reports/evidence/cuadrao-lag/`.

## Findings

| Sev | Where | Finding | Smallest fix |
| --- | --- | --- | --- |
| P3 | `CuadraoBalancePeriod.swift:33-35`, `CuadraoHomeBalanceChart.swift:16-17` | A handed history is tied to its accounts and observations by a doc comment only. All six call sites are correct today. | Optional: carry accounts and observations in `CanvasBuiltBalanceHistory` and vend the period from it. Can wait. |

Not verified here: on-device behaviour (no simulator or phone by brief). The 19 UI tests and the phone
recordings are the author's, not re-run.
