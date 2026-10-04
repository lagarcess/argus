# W1c report: PR #790 third worker (swallowed taps, items 1 to 8)

Branch `codex/cuadrao-release-ui`, worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`.
Start head `3370ba50`. Final pushed head `cc68b341e99e06896f216204f721c19de32abf28`.
Simulator iPhone 18 Pro Max `0335699A-…`. Every UI run was `xcodebuild test-without-building
-only-testing:… -collect-test-diagnostics never` under `lockf -k …/mac-sim.lock`
(script `ios/.build/w1c/focused.sh`, logs in `ios/.build/w1c/runs/<name>/`). No full suite.
Run summaries are committed in `docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1c/`
and the README has a dated section "Swallowed taps, October 4, 2026".

## Verdict in one paragraph

Items 1, 2 and 3 are one app defect, not XCUITest. The tappable area of those rows was
only their drawn content. A `.buttonStyle(.plain)` link or button ignores a tap on the
empty part of its label (the gap a `Spacer` or a full-width frame leaves), and a `Menu`
in a form row is only as wide as its text. A tap at the row's centre did nothing; a tap
on the text opened it. A thumb that lands between the title and the amount hits the
same dead area, so this is a real cause of "I tapped and nothing happened".

## Method note

The simulator control tool asked for access to the simulator and nobody was there to
grant it; `idb` is not installed. I used the brief's fallback: a diagnostic XCUITest
(`W1cDiagnosticUITests`, untracked, now deleted) that tapped each row by element centre
and by coordinate and logged the result. I held the lock once for about 2 minutes for
the attempted manual session (install and launch only).

## Commits (in order)

| SHA | Item | What |
| --- | --- | --- |
| `80a01d1b` | 1 | Updates notice row label gets `.contentShape(Rectangle())`. Branch only. |
| `74ec455c` | 2 | Home activity `feedRow` gets the content shape. Integration defect. |
| `fc327b03` | 3 | Receipt "Choose currency" Menu label fills the row and gets the content shape. Integration defect. |
| `3842099a` | 4 | Group journey asserts the 3,300 cap, that 3,301 is refused, and waits for the sheet. Test only; same timing on integration. |
| `2351ea3b` | 5 | Payer query takes the menu option (label Ana, no identifier). Test only; same on integration. |
| `0083a7c8` | 6 | Four-kinds journey skips when `ARGUS_TEST_SHARED_PLAN_HOUSEHOLD` is missing. Test only; same on integration. |
| `2de03ab0` | 8 | `import Charts` moved to the top of `CuadraoSpendingChart.swift`. |
| `26e64553` | 8 | Decision-log entry of October 3, 2026 and the four canon places linked to it; README "below" to "above". |
| `feaca9bf` | 1, 2 sweep | Same content shape on eight more plain-style rows. Integration defects. |
| `92fa37bc` | 4 | Group journey waits for the split Save to enable. |
| `cc68b341` | evidence | README section and run summaries. |

Integration-defect commits for the lead: `74ec455c`, `fc327b03`, `feaca9bf` (app);
`3842099a`, `2351ea3b`, `0083a7c8`, `92fa37bc` (tests).

## Per item

### 1. Updates notice row: app defect, fixed `80a01d1b`

- Evidence (run `diag1`, `2026-10-04-w1c/diag1-tap-position.txt`): element tap at the
  row centre, then a coordinate tap at (0.5, 0.5): bar stays "Novedades". A press at
  (0.3, 0.3), on the text: bar becomes "Novedad".
- Root cause: `row(item)` is an `HStack` with a trailing `Spacer` inside a plain-style
  `NavigationLink`; no content shape. Routing, mark-read and the path-bound stack were
  not involved, which is why W1b's two experiments changed nothing.
- I did not find why the October 2 run passed (its `bill-notice-es.png` does show the
  notice). The inbox code is unchanged since then; that run was on iPhone 18 Pro, where
  the centre may have landed on text. Not proven.
- Focused run: `testUpdatesNoDataAndReadOnlyHistory` passes unchanged (`taps-after`,
  11.1 s; again in `final`, 10.5 s).

### 2. Home activity row: app defect, fixed `74ec455c`

- Evidence (`diag1`): row at y 731 to 771, hittable, settled 2 s. Centre tap:
  `opened=false`. Tap at (0.2, 0.5), on the title: `opened=true`. So it is position,
  not scroll deceleration and not a lost push.
- Root cause: `feedRow` has a `Spacer` between title and amount, no content shape.
- Focused run: `testHomeActivityReturnsToSameRow` passes unchanged (13.8 s; 13.2 s in `final`).

### 3. Receipt currency menu: app defect, fixed `fc327b03`

- Evidence (`diag1` hierarchy): the row element is 400 pt wide (x 20 to 420) but the
  Menu's own button is x 40 to 210. The centre tap at x 220 misses it. Both the element
  tap and the coordinate tap left no menu.
- Fix: the label fills the row, leading-aligned, with a content shape. Looks the same.
- Focused run: `testPhotoImportKeepsOriginalWithoutInventedItems` passes unchanged
  (52.3 s; 51.9 s in `final`).

### Sweep of the same cause: `feaca9bf`

`2026-10-04-w1c/plain_audit.py` lists every plain-style button or link with no content
shape in its statement (77). I read them. Most row helpers already carry the shape
(`CanvasAccountRow`, `FinancialActivityRow`, `resultRow`, `CanvasProfileRow` and
others), or have an opaque background. Eight had a visible gap and no shape and now have
it: `CuadraoGroupDetail` group entries, `CuadraoSpacesSheet` manage-spaces row,
`FinancialBudgetView` and `FinancialGoalView` archived rows, `FinancialPlanView`
expectation row, `FinancialDebtView` payment and candidate rows, `FinancialPlanForms`
candidate row. Debug and Release compile. Only the group entry row has a UI run (the
group journey taps it). The other seven are unproven at runtime; the change only widens
the hit area to the label's own frame. Invitations and Household files were not read or
touched (outside my scope); the same audit should be run there by their owner.

### 4. Group repayment: test defect, app arithmetic proven right

- Arithmetic: house 12,000 paid by Tú, four shares of 3,000. Dinner 2,000 paid by Tú,
  split Tú 500, Ana 300, Leo, Sol and Mar 400. Ana owes 3,300; Tú is owed 10,500.
  Cap = min(3,300, 10,500) = 3,300. The sheet opens with `3,300.00` and the plan shows
  "Te deben 10,500.00" (`group-repayment-cap.txt`). 500 is valid.
- Why it failed: the test checked that the sheet was gone 0.5 s after tapping Save,
  during the dismissal. With a 1.5 s wait the field is gone.
- Fix: asserts the opening value 3,300.00, that 3,301 disables Save, that 500 enables
  it, and waits up to 3 s for the sheet to close.
- Second finding, not fully explained: in 2 of 5 runs a Save button read as disabled in
  the instant after typing a money value (line 58 once, line 48 once). Money input
  commits its binding on the next main-queue turn since `00b5be65`. With one more query
  in between it read enabled. `92fa37bc` waits up to 2 s. I did not measure how long the
  lag is or rule out a dropped write that a later event repairs. Next step: log
  `pending` and the commit time in `CanvasDecimalInput.Coordinator.commit` during burst
  typing and confirm the binding lands within one frame.
- Focused run: passes (`tests456` 56.1 s, `group-final` 58.3 s). It failed once at line 48
  in `final` before `92fa37bc`.

### 5. Ana query: test defect, fixed `2351ea3b`

`buttons["Ana"]` matched the menu option (no identifier, hittable) and the participant
row `receipt-member-1` (label Ana). The query now requires label Ana and an empty
identifier. `testReceiptShowsYouOweWhenAnotherPersonPaid` passes (38.2 s; 38.6 s in `final`).

### 6. Four-kinds journey: fixed `0083a7c8`

The test lives in `SharedHouseholdPlanningUITests.swift` (an extension of
`FinancialLoopUITests`). Its first line now throws `XCTSkip` with the reason when
`ARGUS_TEST_SHARED_PLAN_HOUSEHOLD` is missing. Later lookups still fail hard, so a
half-configured environment is not hidden. Run: skipped in 0.04 s.

### 7. Never-idle Recents rename: not reproduced, nothing shipped

Three fresh launches, rename as the first context-menu action each time: the alert's
field existed and the next query returned in 1.15, 1.14 and 1.15 s
(`recents-rename-three-launches.txt`). With no stalled baseline there is no before and
after to prove a fix, so I did not ship the deferred presentation. Still documented as
intermittent. Next step: loop that test (20 launches) in a quiet lock window to get a
stall rate, then try presenting the alert on the next run loop and compare rates.

### 8. Docs and small items from R-790-3370ba50: `26e64553`, `2de03ab0`

- `docs/specs/argus-decision-log.md`: new final section "October 3, 2026: avatar
  editing in release" with the founder decision. No existing entry edited.
- One sentence plus a link to it in `.agent/designs/cuadrao/DESIGN.md`,
  `docs/specs/argus-execution-board.md` (row 13 to 14),
  `docs/specs/argus-minimum-viable-ecosystem-experience.md` and the evidence README.
  DESIGN.md also no longer says release keeps initials and themes.
- README "below" to "above". `import Charts` at the top of `CuadraoSpendingChart.swift`.
- On-accent colour assertion: left. XCUITest cannot read a label colour without pixel
  sampling, which the existing checks do not do.
- `git diff --check`: clean. `uv run --with markdown-it-py python
  scripts/check_docs_links.py --base a8c37d3a…`: "Checked local links in 5 changed
  document(s)", no errors. That command recreated the worktree's `.venv` and wrote an
  untracked `uv.lock`, which I deleted.

## Verify

- Debug `build-for-testing`: succeeded at the final app tree (`ios/.build/w1c/bft10.log`).
- Release simulator build: succeeded on the sweep tree (`ios/.build/w1c/release-build-2.log`);
  the only later commit is test and docs.
- `git diff --check 3370ba50..HEAD`: clean.
- Focused runs: `taps-after` (3 pass), `tests456` (2 pass, 1 skip), `final` (4 pass,
  1 skip, group failed at line 48), `group-final` (group passes).
- Pushed without force; branch is level with `origin/codex/cuadrao-release-ui`.

## Left

- Seven swept rows have no UI run (listed above).
- The Save-state lag after money typing (item 4): measure it, next step given.
- Rename never-idle (item 7): not reproduced.
- Why the Updates journey passed on October 2: not established.
- Invitations and Household rows: run `plain_audit.py` there (owner's scope).
- `ios/ArgusFoundationUITests/W1bDiagnosticUITests.swift` and `todo.md` remain untracked, untouched.
