# R-lag-31db6f7c: independent review of PR #812, `20f31941..31db6f7c -- ios`

Reviewer: read-only, host only (no simulator, no xcodebuild, no phone). Source read with `git show` / `git diff`
from the `cuadrao-lag` worktree at `31db6f7cbc2a038f1b6b7002207f9ed67e0a2a9a`. Nothing edited, committed, pushed or posted.

## Verdict: CLEAN (no P1, no P2; three P3 notes, none blocking)

Both commits preserve output and behaviour for every input I could construct or reason about.

## 1. Money formatting (`931b3c299`, `ios/ArgusFoundation/Cuadrao/CanvasMoney.swift`)

**Old code** (`20f31941`, lines 8-19): `digits` built a `.currency` formatter on the default (device) locale, set
`currencyCode`, read `maximumFractionDigits`. `format` built an `en_US` `.decimal` formatter, set min then max
fraction digits to `digits(currency)`, converted.

**New code** (lines 8-11, 16-42): same two formatter configurations, same property order (locale, style, min, max
at lines 34-37), same `?? "—"` fallback (line 41). Only the lifetime changed.

- **Byte identity.** Ran `python3 ios/DesignPreviewTests/run_money_format.py` from a `git archive 31db6f7c` copy
  in scratch: **"Passed 12157 money format checks" nine times** (default en_US, en_US, es_419, es_DO, es_US, ja_JP,
  de_CH, ar_KW, en_US@currency=JPY), 5984 value and currency pairs each, exit 0. Covers every
  `Locale.commonISOCurrencyCodes` entry plus lowercase, empty, blank, `XXX`, `ZZZ`, `US`, `DOLLAR`, `€`; values
  include 0, -0, half-way cases (0.005, 0.015, 0.025, 2.675), negatives, 9999999.99, beyond the maximum, 1e-7, 7e12.
- **The "old path" in the check is the old code.** `LegacyMoney` (`MoneyFormatChecks.swift:4-17`) diffed against
  `git show 20f31941:…/CanvasMoney.swift` `digits` and `format` bodies: identical after stripping indentation.
- **Locale.** The author's description matches the old behaviour. The output locale was always fixed `en_US`
  (grouping `,`, decimal `.`, half-even), so es-419 and es_DO never changed the string; the device locale only
  entered through `digits`. My own probe confirms that dependence is real and only for codes the formatter does
  not accept: empty code gives 2 in en_US, 0 in ja_JP and en_US@currency=JPY, 3 in ar_KW; `USD`/`usd`/`ZZZ`/`DOLLAR`
  give 2 and `JPY` 0 in all four. New equals legacy in every row.
- **Cache key completeness.** Digits key = (`Locale.current.identifier`, code) (lines 20, 25); the identifier
  carries the `@currency=`/region keywords that drive the fallback. Decimal formatter key = digit count (line 33),
  the only variable input to a fixed-locale formatter. Nothing that affects output is outside the keys.
- **Nothing frozen at first use.** `Locale.current.identifier` is read on every `digits` call, outside the lock
  (line 25). A region or language change yields a new key. The cached decimal formatter has an explicit `en_US`
  locale, so it has nothing device-dependent to freeze. Not executable on the host: I tried to change the locale
  inside one process (defaults write and volatile argument domain plus the locale-change notification) and
  `Locale.current` did not move, so this is by reading, as the author also states.
- **Thread safety.** Every read and write of both dictionaries, the formatter construction and the
  `string(from:)` call are inside `lock` (lines 26, 32, `defer` unlock). `format` evaluates `digits(currency)` as
  an argument before calling `string`, so the non-recursive `NSLock` is taken twice in sequence, never nested
  (line 10). Inside the lock only Foundation formatter calls run: no closure from callers, no SwiftUI, no
  re-entry. The global is a Swift lazy `let` (thread-safe init). The check's 16-thread sweep passed.
- **Growth.** Decimal formatters: one per distinct digit count (0, 2, 3, 4 in practice). Digits map: one `Int`
  per (locale, code) seen. Codes come from account currencies and a picker; even arbitrary strings cost tens of
  bytes each. Not a defect.
- **Callers.** `CanvasMoney.digits` is still used by `CanvasDecimalInput.swift:100,129` and
  `CuadraoAmountField.swift:39` with the same signature and values.

## 2. Chart split (`7a3182488`, `ios/ArgusFoundation/Cuadrao/CuadraoHomeBalanceChart.swift`)

- **View tree.** The diff moves no line of the old body. The outer `body` (lines 27-34) returns exactly one
  `CuadraoHomeBalanceChartContent`; everything from `reading` down (lines 60-268) is unchanged text. Modifiers,
  identifiers (`home-chart-amount`, `-date`, `-takeaway`, `-today`, `-empty`, `home-range-*`, `home-balance-chart`,
  `home-chart-currency`, `home-history-expand`), accessibility labels and values, both gesture paths (lines
  240-262), `onChange`, `onAppear`, and both `sensoryFeedback` triggers are byte-identical. A custom wrapper view
  adds no layout, accessibility or gesture node.
- **Identity and state lifetime.** `compactRange` and `selectedDate` moved from the outer to the inner view
  (lines 51, 54), both with constant initial values, none derived from a parameter, so nothing can go stale. The
  inner is the outer's only, unconditional child, so its structural identity lives exactly as long as the outer's.
  Home: `.id(data.selectedSpaceID + currency)` (`CuadraoHomeOverview.swift:15`) is on the outer, so space or
  currency change still resets both states, and nothing else does. Insights: the chart sits in the same
  `if/else` branch inside `ForEach(offset)` (`CuadraoHomeInsights.swift:58`), so page, range and
  distribution toggles create and destroy it exactly as before. Parent re-render, accounts or observations change:
  state persists, as before. Range and period changes still clear the scrub through the unchanged `onChange`
  handlers (lines 150-151).
- **History inputs.** Outer builds with `accounts`, `observations`, `now` (line 32) and passes the same
  `accounts` and `observations` to the inner in the same body pass (line 29), so the inner can never hold a
  history built from different inputs than the ones it draws. `CanvasBalanceHistory.points` reads `now` only via
  `Calendar.current.startOfDay(for: now)` (`CuadraoBalanceHistory.swift:30-31, 36, 49`), which is exactly what the
  guard compares (line 57, `builtDay` at line 33). The outer struct holds closures, so SwiftUI re-evaluates it on
  every parent update: builds are the same or fewer, never missing.
- **Day change.** "Rebuilds" means the inner's computed `history` falls back to the old per-pass build when
  `startOfDay(.now) != builtDay` (lines 56-59). It is a computed value, not a view or state reset: a scrub in
  flight across midnight keeps `selectedDate` and simply reads the new day's history, which is what the old code
  did on every frame. A time-zone change takes the same fallback. It cannot fire more often than a day or zone
  change.
- **Transitions, matched geometry.** None crossed the old view boundary: the file has no `matchedGeometryEffect`,
  `transition` or `animation`; the callers apply `.id` and `.fullScreenCover` to the outer, unchanged.
- **Access change.** `typeSize`, `compactRange`, `selectedDate` lost `private` so the private struct's memberwise
  initializer is reachable from the outer; the type itself is `private`, the outer never passes them. No effect.

## 3. Would the checks catch a divergence

- `run_money_format.py`: yes for strings, digits, reuse state and concurrent readers, per process locale. No for
  a locale change inside one process (not reproducible on the host; covered by reading the key).
- `run_home_balance.py` (ran: "Passed 81 Home balance projection checks"): covers `CanvasBalanceHistory` and
  `CanvasBalancePeriod` only. It does **not** compile `CuadraoHomeBalanceChart.swift` (file list at
  `run_home_balance.py:13-15`), so it says nothing about the split.
- `CuadraoHomeChartUITests` (read, not run here): asserts the hero string `153,920.00` / `43,500.00`, tap and
  long-press-drag scrub changing `home-chart-date`, `home-chart-today` reset, space switch, expanded paging,
  "inspection must not page", "returning restores the history period". That would catch a broken scrub, a lost
  gesture, or a wrong hero. It would not catch the midnight fallback or a state reset on parent re-render in
  compact mode; both are equal to the old code by construction.

## 4. Nothing else changed

`git diff --stat 20f31941..31db6f7c -- ios`: `CanvasMoney.swift`, `CuadraoHomeBalanceChart.swift`, the two new
check files, and one added runner name in `ios/scripts/cuadrao-design-mac-pass.sh`. `CanvasDecimalInput.swift`
has an empty diff. Outside `ios` the range adds one evidence document. No visual or interaction change.

## P3 notes (no action needed for the candidate)

1. `LAG-phone-2.md` says the split is compiled on the host "through `run_home_balance.py`". It is not; only the
   simulator build and UI tests compile it. Correct the sentence if the report is reused as evidence.
2. The in-process locale change is unexercised by any test. Acceptable: the key is read per call (`CanvasMoney.swift:25`).
3. `run_money_format.py` prints a timing line; it is not asserted, so it cannot flake the check.
