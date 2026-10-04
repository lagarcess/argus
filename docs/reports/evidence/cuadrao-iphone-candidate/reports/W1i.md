# W1i: can money entry undo a keystroke? (PR #790)

Branch `codex/cuadrao-release-ui`, worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`.
Start head `c2b47c6612d6639f393c76520d902bc67255e387`. Final head `53a4d67d6bbac3dc9d21fe79f2af685462f0ba69` (docs only, pushed without force).
Taken over from a stopped worker; its runs and section 1 were checked against the logs and kept.

## Verdict

NOT REPRODUCED. No fix. Both Swift files equal `c2b47c66` (`git diff HEAD -- <files>` empty), the probe is deleted,
`git status` shows only the two untracked files the brief said to leave (`todo.md`, `W1bDiagnosticUITests.swift`).

The re-sync window the reviewers traced did not open in 1,571 chances, 80 of them with the exact setup it needs. The
range guard at `CanvasDecimalInput.swift:80` refused 0 of 3,180 keystrokes. The suite's "40" stays unexplained on the app
side; the surviving candidate is two synthesized deletes not delivered under whole-machine load, which a main-thread
stall does not exercise.

## 1. Event ordering (read from the code, then confirmed from the stalled logs)

Files: `ios/ArgusFoundation/Cuadrao/CanvasDecimalInput.swift` (UIKit field, coordinator) and
`ios/ArgusFoundation/Cuadrao/CanvasMoneyValueInput.swift` (`@State raw` text, `@Binding value: Double`).

One keystroke k, all on the main thread:

1. UIKit calls `textField(_:shouldChangeCharactersIn:replacementString:)` (`:78-123`). It reads the field's own text as
   `old`, builds the proposed text, validates it, and on accept sets `coordinator.raw = normalized`, calls
   `commit(raw:error:)` (`pending += 1`, enqueue main-queue block B_k), sets `field.text` to the grouped text, places the
   caret, and returns `false`. UIKit never applies its own edit; the field is correct the instant the key is handled.
2. B_k runs on a later main-queue turn: `parent.raw = raw_k` (the `CanvasMoneyValueInput` `@State raw`), the error, then
   `pending -= 1`. Blocks run in enqueue order.
3. SwiftUI's update flush (run-loop observer, before the loop sleeps): `CanvasMoneyValueInput.body` re-evaluates,
   `onChange(of: raw)` writes `value = numericValue` (for a split share this writes the editor's `exactShares`
   `@State`), `updateUIView` runs (refreshes `coordinator.parent`; rewrites the field only when `pending == 0` and bound
   `raw != coordinator.raw`), the parent re-evaluates, and `onChange(of: value)` runs and calls `syncValue()` only when
   `numericValue != value`.

Several keystrokes can be handled before their blocks run (a burst after a stall). The blocks then drain in order, and
the update flush sees only the last raw.

Writers of the field's text from outside the keystroke itself:

- `updateUIView` (`:60-63`): when `pending == 0` and the bound `raw` differs from `coordinator.raw`.
- `textFieldDidEndEditing` (`:125-134`): reformats to the currency's decimals when the field loses focus.

Writers of the bound `raw` other than the keystroke's own block B_k (each can reach the field through `updateUIView`):

- `CanvasMoneyValueInput.onAppear` (`:19`): unconditional `syncValue()` from `value`.
- `CanvasMoneyValueInput.onChange(of: value)` (`:20-22`): `syncValue()` when `numericValue != value`.
- The end-editing block (`commit(raw:)` from `textFieldDidEndEditing`).

Places a keystroke can be refused or dropped:

- `:80` `guard let r = Range(range, in: old) else { return false }`: silent, no error, no write.
- `:89-92` pasted text with commas that do not group correctly (error shown).
- `:94-97` anything but digits and one point (error shown).
- `:99-102` more decimals than the currency allows (error shown).
- `:103-105` above the maximum or over 24 characters (error shown).
- Outside the delegate: a delete on an empty field is never delivered (UIKit does not call the delegate), and a
  synthesized key that the system never delivers leaves no trace in the app.

The reviewers' window needs a queued keystroke write (step 2 of key k+1) to land between the update that writes
`value` (step 3 `onChange(of: raw)`) and the update that reports it (`onChange(of: value)`).

## 2. Reproduction attempt

Throwaway DEBUG hooks (never committed): a launch-argument-gated repeating main-queue block that sleeps (`-W1iStall`
60 to 150 ms every 20 to 120 ms; `-W1iStallHeavy` 250 to 600 ms every 5 to 60 ms) and an os_log line at every keystroke,
accept, refusal, queued write, `updateUIView` with a lagging binding, field rewrite, `onChange(of: raw)`,
`onChange(of: value)`, `syncValue` and end-editing. Throwaway XCUITest `W1iMoneyStallProbeUITests`: `probe` replaces
Ana's share and the expense amount in one open editor, 50 rounds, ten amounts; `freshEditor` reopens the saved expense
each round and replaces Tú then Ana (the failing journey's shape). Each replace is a tap, a burst of deletes, a read
back, a burst of digits, a read back.

Built once per change with `xcodebuild build-for-testing ... -derivedDataPath .build/DerivedData-w1i` (no lock), run
with `lockf -k .../mac-sim.lock w1i/run.sh <xctestrun> <name> <test>` (one `xcodebuild test-without-building
-collect-test-diagnostics never`, then a log export).

| Run | Stall | Replacements | Keystrokes | Handled with writes queued | Wrong field values |
| --- | --- | --- | --- | --- | --- |
| probe-nostall-1 (inherited) | none | 101 | 956 | 12 | 0 |
| probe-stall-1 (inherited) | 60 to 150 ms | 101 | 956 | 245 (max 5 queued) | 0 |
| fresh-stall-1 (inherited) | 60 to 150 ms | 101 | 904 | 197 | 0 |
| fresh-heavy-1 (mine, 20 rounds) | 250 to 600 ms | 41 | 364 | 128 | 0 |

Totals: 344 replacements, 3,180 keystrokes, 2,224 stalled, 582 handled while earlier writes were queued. Refused at the
range guard 0, refused by validation 0, sent but not handled 0, update rewrites onto a non-empty field 0,
`onChange(of: value)` asking for a re-sync 0.

- The inherited `fresh-nostall-1` was interrupted at 61 of 101 replacements, 0 mismatches. Not counted, not rerun: the
  no-stall case is covered by probe-nostall-1 and the simulator is shared.
- `fresh-heavy-1` is recorded as a failed test: one `W1I-MISMATCH fresh 9 Ana deletes: before '500.00' left '0.00'`.
  It is the probe's own read. The XCUITest element query retried and timed out under the heavy stall, and the value
  read afterwards is the empty field's placeholder. The app log for that burst shows six deletes handled
  (`500.00` to empty), then `3`, `0`, `0`, no rewrite, `resync=false`, and the typed read-back was `300`.

### The re-sync window, measured

Of 1,571 value writes that changed the value, 80 happened when a later keystroke was already handled and its write was
queued (the update between them logged `pending=1` with the binding behind the field). In all 80, `onChange(of: value)`
ran before that queued write, 2 to 8 ms after the value write, with only view updates between. `onChange(of: raw)` and
`onChange(of: value)` run in the same SwiftUI update flush; the queued write is a main-queue block and did not run
inside it. So `raw` and `value` agreed at every report and the re-sync was never requested. This is observation, not a
SwiftUI guarantee.

### Also checked

`NSDecimalNumber(decimal:).doubleValue` disagrees with the cents round trip for more than half of two-decimal amounts
(0.07 gives 0.06999999999999999; checked on the Mac with a script). The two receipt call sites round to cents in their
binding setter, so there `numericValue != value` is true after a self-write and the re-sync does run. It rewrites `raw`
with the same two-decimal text, so nothing visible changes; no one-decimal amount in 0.0 to 9999.9 mismatches. Not a
defect today. It would become one for a currency whose digits differ from the cents the receipt stores.

## 3. Cause

Not established. Ruled out under a stalled main thread at 3,180 keystrokes: the re-sync rewrite, an `updateUIView`
rewrite from a lagging binding (the `pending == 0` guard from 00b5be65 held every time it was tested), and the range
guard refusal. Remaining candidates for the suite's "40":

1. Two of the six synthesized deletes were never delivered to the app under whole-machine load (the full suite beside
   other work). Any two, since each delete at the end of the field does the same thing. The stall slows only the app.
2. An app path that needs suite state the probe does not create. Nothing in the two files points to one.

## 4. Cheapest instrument for a full suite

Apply `docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1i/stall-and-log-instrumentation.diff.txt` to a throwaway
build (it applies cleanly at this head; DEBUG only), add `-W1iLog` to `CuadraoPreviewLaunch.arguments`, run the suite
with the log export in `run-probe.sh.txt`, then `summarize.sh.txt`. On a recurrence (the group journeys already fail at
the field since 211b3d732): a burst with fewer handled keystrokes than sent is candidate 1; a `REWRITE` onto a non-empty
field or a `REFUSED` line is the app, with the line that did it.

## 5. Proofs and state

- `git diff HEAD -- ios/ArgusFoundation/Cuadrao/CanvasDecimalInput.swift ios/ArgusFoundation/Cuadrao/CanvasMoneyValueInput.swift`: empty (checked before the commit, at c2b47c66).
- Commit `53a4d67d6` adds 34 lines to the lane README (0 deleted) and five text files under `2026-10-04-w1i/`.
  `git diff --cached --check` clean. Pushed: `c2b47c661..53a4d67d6  codex/cuadrao-release-ui`.
- Not run: the three focused test targets, Debug and Release compiles, build-for-testing at the final head, and the
  `strings` check. The app and test sources are byte-identical to c2b47c66, so they would repeat recorded results.
  The stall flag exists in no committed source file.
- Raw logs and result bundles: `~/.claude/orchestrate/cuadrao-iphone-candidate/w1i/`. Throwaway derived data
  `ios/.build/DerivedData-w1i` is left in the worktree (ignored by git) and can be deleted.
- Simulator time used by me: one 744 s hold. One helper agent: none.
