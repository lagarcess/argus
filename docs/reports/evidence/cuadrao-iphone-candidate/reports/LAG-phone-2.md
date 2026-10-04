# LAG-phone-2: money formatting and balance history under interaction

Worker: lag. Date: October 4. Branch `claude/cuadrao-lag-fixes` (PR #812), head **`31db6f7cb`** (pushed with the explicit refspec, no force).
Status: two fixes committed, pushed and installed on the iPhone as build 3426. Identity proven on the host,
simulator tests green, launch and idle re-recorded. The interaction re-measurement waits for Lucas.

## What the lead does next

Phone is on build **3426** (built from `7a3182488`, clean tree; `devicectl device info apps` reads 3426).
With Lucas ready to repeat the same 90 s script (`reports/LAG-needs-founder.md`, which still says 3425 in
its "Before starting" list; the build is now 3426):

```bash
~/.claude/orchestrate/cuadrao-iphone-candidate/lag-phone/tools/part2.sh run-2
```

Callees for any frame afterwards: `python3 lag-phone/tools/callees.py lag-phone/part2/run-2.trace "CanvasMoney.format" "CanvasBalanceHistory.points" "chartBase"`.

## Cause of each cost (build 3425, `part2/run-1.trace`, 87 s, main thread 13312 ms)

Callee tables: `lag-phone/part2/run-1.callees.txt`, produced by the new `lag-phone/tools/callees.py`.

| Cost | Measured | Cause, from the callees |
| --- | --- | --- |
| `CanvasMoney.format` | 3621 ms inclusive; 3510 ms from `closure #1 in closure #1 in chartBase`, 42 ms amount row, 43 ms balance breakdown, 10 ms `CanvasDecimalInput.updateUIView` | Three `NumberFormatter`s per call. `-[NSNumberFormatter _regenerateFormatter]` 3025 ms; `maximumFractionDigits` 2629 ms (the two `digits(currency)` reads on a fresh currency formatter); `setMinimumFractionDigits:` 419 ms; `CFNumberFormatterCreate` 2140 ms; `unum_open` 1594 ms; `icu::DecimalFormatSymbols` 923 ms. The string conversion itself is 175 ms |
| Chart closure in `chartBase` | 4051 ms inclusive | 3510 ms is the formatter above, called once per plotted point for the mark's accessibility value. `dateLabel` 73 ms. The rest is Swift Charts builders |
| `CanvasBalanceHistory.points` | 1261 ms inclusive: 879 ms `CuadraoHomeBalanceChart.reading`, 206 ms `CuadraoHomeInsights.oldest`, 123 ms `CanvasBalancePeriod.init`, 53 ms `closure #4` in the chart body | 877 ms is `NSDecimal./` in `contribution` (`/ 100` per observation). About 6 ms per scrub frame, 25 to 40 ms on range and period changes where Insights and the period add their own builds |
| Money typing | `textField(_:shouldChangeCharactersIn:replacementString:)` 160 ms total, 28 ms in the sampled hitch | **Not the formatter.** 148 ms is `-[UITextField setText:]` (field editor, then `_UIKeyboardStateManager textDidChange`, 106 ms, and keyboard assistant view update, 78 ms). `maximumFractionDigits` is 6 ms, the regex 3 ms |
| `CuadraoHomeInsights` (asked for either way) | body 228 ms inclusive, 213 ms of it `oldest` then `points` | Same history builder, called twice per Insights body pass |

## What changed

1. `931b3c299` perf(ios): reuse the money formatters instead of building three per call.
   `ios/ArgusFoundation/Cuadrao/CanvasMoney.swift`. Fraction digits are read once per (device locale identifier,
   currency code); one `en_US` decimal formatter is kept per fraction-digit count; both behind one `NSLock`, and
   the string conversion runs inside the lock. The locale identifier is read on every call, so a region change
   takes a new key. Callers and signatures unchanged.
2. `7a3182488` perf(ios): build the Home balance history when its inputs change, not per scrub frame.
   `ios/ArgusFoundation/Cuadrao/CuadraoHomeBalanceChart.swift`. `CuadraoHomeBalanceChart` keeps its initializer
   and now only builds the history and hands it to a private `CuadraoHomeBalanceChartContent`, which is the
   previous view with its state (`selectedDate`, `compactRange`). Scrubbing changes only the inner view's state,
   so the outer body and the history build do not run. No stored cache: the history is a `let` rebuilt whenever
   the owner re-evaluates the chart. The projection reads the clock only through `startOfDay`, so the inner view
   uses the built history while `startOfDay(now)` equals the day it was built for and rebuilds otherwise.
3. Fix 2 of the brief (per-point strings in the chart closure): left as is. After change 1 the trace's own split
   puts that work at about 3 ms per frame (175 ms conversion and 73 ms date labels against 3510 ms). Swift Charts
   takes `accessibilityLabel` and `accessibilityValue` as eager strings, and the `Reading` is rebuilt on every
   pass, so "once per Reading" is the same frequency. Any lazier form changes what VoiceOver receives.
4. Fix 4 of the brief (money typing): confirmed by reading and by callees that change 1 covers only 6 ms of it.
   Nothing in `CanvasDecimalInput` was edited; the deferred commit from `00b5be65` is untouched.
5. `16ef91206` and `31db6f7cb` (docs only): evidence at `docs/reports/evidence/cuadrao-lag/phone-interaction-money-and-history.md`.
   `ios/scripts/cuadrao-design-mac-pass.sh checks` now also runs `run_money_format`.

## Identity proof

`python3 ios/DesignPreviewTests/run_money_format.py` (new, with `MoneyFormatChecks.swift`). The check file holds
a private copy of the old implementation and compares bytes with the new path for every
`Locale.commonISOCurrencyCodes` entry plus `usd`, `dop`, empty, blank, `XXX`, `ZZZ`, `US`, `DOLLAR`, `€`,
times 34 values (0, -0, half-way cases, 9999999.99, beyond the maximum, tiny, 7e12): 5984 pairs, then the whole
table again in reverse (reused formatter), then 16 threads, plus 11 literal strings and 3 known digit counts.
Run under nine device locales via `-AppleLocale`: default, `en_US`, `es_419`, `es_DO`, `es_US`, `ja_JP`, `de_CH`,
`ar_KW`, `en_US@currency=JPY`. Result: "Passed 12157 money format checks" nine times.

I ran the same check first against the unchanged `CanvasMoney` (old against old) to prove the harness and the
literal strings; it passed with "per call 51.0 µs before, 49.1 µs now". With the fix: "48.6 µs before, 1.1 µs now".

Not exercised: a locale change inside one running process (the check sets the locale per process).

## Test results (commands as run)

| Command | Result |
| --- | --- |
| `python3 ios/DesignPreviewTests/run_money_format.py` | 9 × Passed 12157 |
| `python3 ios/DesignPreviewTests/run_home_balance.py` | Passed 81 (run at `931b3c299` in the checks step and again with the split) |
| `ios/scripts/cuadrao-design-mac-pass.sh checks` at `931b3c299` | `== checks: ok` (home 81, plan 58, group 50, release updates 25, the rest silent on success, money 9 × 12157). Not rerun after the split, which no host runner compiles except through `run_home_balance.py`, and that one was |
| `SIMULATOR_ID=0335699A-… ios/scripts/verify.sh build` (Debug, tree of `7a3182488`) | BUILD SUCCEEDED |
| Under the lock, `verify.sh test -collect-test-diagnostics never -only-testing:ArgusFoundationUITests/CuadraoHomeChartUITests -only-testing:…/CuadraoConsistencyUITests/testMoneyEntryAndBlankCreationSpanish -only-testing:…/CuadraoPlanCurrencyUITests`, iPhone 18 Pro Max, tree of `7a3182488` | 16 tests, 0 failures, TEST SUCCEEDED. Log and xcresult: `lag-phone/sim-fix2-931b3c299-plus-split/` |
| `lag-phone/tools/build-install.sh 3426` | BUILD SUCCEEDED, `head=7a3182488… dirty=0`, "App installed", phone reads 3426 |
| `lag-phone/tools/part1.sh lag-phone/fix2-3426` | all nine recordings exit 0 |

## Part 1 on build 3426 (`lag-phone/fix2-3426/`)

| Measurement | fix1-3425 | fix2-3426 |
| --- | --- | --- |
| Initial Frame Rendering, 5 cold launches | 209, 192, 192, 191, 191 ms | 286, 319, 317, 171, 179 ms |
| UIKit Initialization, same launches | 85, …, 69, 71 ms | 204, 178, 190, 70, 73 ms |
| Initial Frame Rendering in the 40 s hitches recording | not read | 167 ms |
| Launch hitch | 250 ms | none (0 hitches in 40.9 s) |
| Hitch time ratio, 40 s | 6.1 ms/s | 0.0 ms/s |
| Interaction delay at launch | 35 ms | 34 ms |
| Main thread CPU, first 3 s | 385 ms | 370 ms |
| Process CPU, first 3 s | 692 ms | 643 ms |
| `CanvasBalanceHistory.points`, first 3 s | 26 ms | 2 ms |
| Idle Home, process CPU, seconds 10 to 40 | 1 ms | 5 ms |
| Idle Home, main thread CPU, seconds 10 to 40 | 0 ms | 1 ms |
| Thermal state | Nominal | Nominal |

Reading: no regression that I can attribute to the code. Launches 1 to 3 were slower, and in exactly those the
system's UIKit Initialization phase (before any app view code) took 178 to 204 ms instead of about 70 ms; they
were the first launches after the install and ran while another worker's simulator suite alternated with mine on
the Mac. Launches 4 and 5 and the hitches recording are at 167 to 179 ms, below 3425. No app frame is larger in
the slow launches. This is an explanation from the phase table, not a controlled re-run: if the lead wants it
closed, repeat `part1.sh` into a new directory with the phone settled.

Odd event, cause unknown: in `launch-4.trace` the app went Inactive 1.1 s after its first frame and Background
at 3.2 s. The phone reported unlocked afterwards and the later recordings stayed in the foreground for their
full length.

SwiftUI and Activity Monitor traces were recorded (`idle-swiftui.trace`, `idle-activity.trace`) but not
summarised this round.

## Expected effect on the interaction run (prediction, not a measurement)

A sampled scrub frame on 3425 cost 61 to 67 ms of main-thread work: formatting 35 to 43 ms, history 6 ms, the
rest Charts and SwiftUI. With both changes that is about 18 to 24 ms. That is still above one 16.7 ms frame on
this 60 Hz phone, so `run-2` should show far fewer and shorter scrub hitches, not zero. The remaining cost is
framework work re-evaluating the chart, which needs its own look in `run-2` before anyone touches it.

## Deferred, with measured cost (run-1)

| Item | Cost | Why deferred |
| --- | --- | --- |
| `CuadraoHomeInsights.oldest` builds the history twice per Insights body pass | 213 ms over 87 s; 11 ms in the 44.155 s hitch | Range and period changes only. Out of the brief's scope unless named; it is named, but small. A hoist to one local per pass is the fix |
| `CanvasBalancePeriod.init` builds its own history per expanded chart pass | 123 ms over 87 s | Needs a history parameter on the period type and its other callers |
| `NSDecimal./` in `CanvasBalanceHistory.contribution` | 877 ms over 87 s before change 2 | Arithmetic rewrite with its own equality proof. Change 2 removes its per-frame occurrences |
| `-[UITextField setText:]` per money keystroke | 148 ms over the typing step, 28 ms in the 87.019 s hitch | UIKit and keyboard work for the regrouped text. Avoiding it means not rewriting the text when grouping is unchanged, which touches caret handling |
| Per-point accessibility strings in the chart | about 3 ms per frame after change 1 | Eager API in Swift Charts; see item 3 above |
| Charts and SwiftUI per scrub frame | about 14 to 20 ms | Framework cost; measure in `run-2` |
| `CuadraoSearchCanvas.activity` | 113 ms over 87 s (75 ms `availableAccounts`) | Seen in the table, not in any sampled hitch |

## Decision log

1. Read `run-1` summaries, then exported callees under the hot frames before reading source. That showed three
   formatters per call, and that typing was UIKit, not the formatter.
2. Kept `NumberFormatter` (not `FormatStyle`) so the output path is the same class with the same settings in the
   same order; only its lifetime changed.
3. Keyed the digits on the device locale identifier because an empty or unknown code falls back to the locale's
   currency. Keyed the decimal formatter on the digit count because its locale is fixed.
4. Wrote the check with the old implementation inside it and ran it old against old before changing anything.
5. For the history, rejected a stored cache in the owner (invalidates on accounts, observations and midnight)
   and rejected building it in the chart's initializer (runs even when SwiftUI would not evaluate the body).
   Chose the two-view split: strictly fewer builds than before, and exact through the day guard.
6. Left the Insights callers, the period type and the division alone: each is measured above and none is on the
   per-frame path after change 2.
7. Did not delegate the edits to a subagent or run the panel skills the working style suggests for larger
   changes: two small files inside a 100 minute box.

## Final head

`31db6f7cbc2a038f1b6b7002207f9ed67e0a2a9a` on `claude/cuadrao-lag-fixes`, equal to `origin`. Commits on top of `20f31941b`:
`931b3c299` (formatters), `7a3182488` (history, the tree build 3426 was made from), `16ef91206` and `31db6f7cb` (evidence).
