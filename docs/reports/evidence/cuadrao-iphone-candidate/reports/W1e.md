# W1e: final correction pass, PR #790 (applies R-790-c45e1eb7)

Worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`, branch `codex/cuadrao-release-ui`.
Start `c45e1eb765a6305c80ee5f56129ece008ee2f405`. Final head `e694d5da249147c67ea7333b28b6204fd95bb5df`, pushed fast-forward (`c45e1eb76..e694d5da2`), no force.
No simulator, no `xcodebuild test`. Untracked `todo.md` and `W1bDiagnosticUITests.swift` left alone.

## Commits
- `7965417dd` fix(ios): voice message Cancel takes taps across its frame and the tap-target check reads every control (items 1 and 3)
- `567f59819` fix(ios): split member row keeps the cc68b341 layout while the row stays tappable (item 2)
- `e694d5da2` docs(cuadrao): W1e evidence and dated README note

## Item 1 (P2): DONE, finding confirmed
- Confirmed at c45e1eb7: `CuadraoVoiceMessagePanel.swift:104-105` had `.frame(minWidth: 80, minHeight: 48)` outside a plain-style `Button(title, role:)`, style from the container at :114.
- Cancel is now `Button(role: .destructive) { … } label: { Text(…).frame(minWidth: 80, minHeight: 48).contentShape(Rectangle()) }.buttonStyle(.plain).fixedSize(horizontal: false, vertical: true)`, identifier kept on the button. Same frame, same text, same order of frame then fixedSize.
- `.buttonStyle(.plain)` moved from the container onto each button at all four sites: LiveVoice header (2), OrderedCollection (2), VoiceBar (3), VoiceMessagePanel (2). Same environment value per button, so no visual change.
- Reviewed list: `6e1228b1526b` replaced by `b868490ad918` ("Stop only, filled capsule"); the LiveVoice container entry replaced by one entry per header button; the PlanCurrencyChoice entry rekeyed (see item 3).
- Check rewrite (`ios/DesignPreviewTests/run_tap_targets.py`): each `.buttonStyle(.plain)` is traced back through its modifier chain (bracket matching on text with strings and comments blanked) to the statement it styles. A Button, NavigationLink or Menu must contain `contentShape` or be reviewed. A styled statement that is not a control but contains controls prints `CONTAINER` and fails; no review entry can pass it. A styled helper call with no control in it (one case, `CuadraoChoiceMenu`) needs a review.
- A side effect worth knowing: the check now counts 127 plain-style statements, 43 without a shape (was 42; the two LiveVoice header buttons are now separate entries).

## Item 2 (P3): DONE, with a different fix than the review suggested
- Confirmed the layout change. I measured before choosing: the review's `.padding(.trailing, 20)` on a full-width button is NOT identical to cc68b341 in constrained rows. It differed in 5 of 60 probe cases, all at a 280 pt row in exact mode (share field 134 pt against 124 to 140 pt, name 55 against 62.5 pt). It matched at 320 pt and wider.
- Shipped instead: the cc68b341 row structure restored exactly (label `.frame(minHeight: 44)`, `Spacer()`, trailing column), plus `.contentShape(Rectangle())` on the label and a tap area in an `.overlay` on the Spacer (`Color.clear.frame(height: 44).contentShape(Rectangle()).onTapGesture { toggle(member.id) }.padding(.trailing, 8).offset(x: -12).accessibilityHidden(true)`). Overlay, contentShape and onTapGesture take no part in layout, so the layout is the cc68b341 layout by construction.
- How layout was confirmed: a macOS SwiftUI host probe (`docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1e/member-row-layout-probe.swift`) lays out the old row, the c45e1eb7 row, the padding variant and the shipped row in an NSHostingView and compares icon, avatar, name and trailing frames over 6 widths x 5 names x 2 split modes. Shipped row: 60 of 60 identical. c45e1eb7: 22 differ. Padding variant: 5 differ.
- Tap area: starts at the label's trailing edge and ends exactly 32 pt before the trailing column (0 wide when the Spacer is at its 8 pt minimum). Synthesized clicks at a 343 pt row hit at x=112..168 and miss at x=174..210 (field starts at 203).
- Limits, stated plainly: the probe uses stand-in children (a circle for the avatar, a 90 to 140 pt clear frame for the money field) and runs on macOS, not iOS. The tap area is a gesture, not part of the Button, and is hidden from accessibility; the Button keeps its label and its XCUITest centre is where it was at cc68b341. An off-centre tap on the iPhone simulator is still owed.

## Item 3 (P3): DONE as a simple pattern check
- A reviewed reason ending in "X carries the shape" is parsed for X; every `struct X`, `func X(` or `var X` body in the call-site file (else anywhere under ArgusFoundation) must contain `contentShape`, or the check prints `HELPER` and fails. A reason ending that way that names no helper also fails.
- It found one wrong reason on first run: PlanCurrencyChoice said "CuadraoChoiceMenu carries the shape", but the shape lives in `CuadraoChoiceLabel`, the menu's label. Reason corrected. No dead area there.
- Not done, follow-ups: free-text reasons ("filled capsule, opaque across its frame") are still not verified; identical statements still share one digest; Invitations and Household are still not read (other lanes).

## Mutation proof (scratch copy, never the worktree)
`docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1e/tap-target-mutations.sh`, output in `tap-target-mutations.txt`. Each line is the check's exit code on the mutated copy:
- voice bar mute, shape removed: exit 1, `UNREVIEWED 7bb0741ab7db CuadraoVoiceBar.swift:35-37` (was exit 0 at c45e1eb7 per the review)
- ordered collection Edit, shape removed: exit 1, `UNREVIEWED 835884728ad5 CuadraoOrderedCollection.swift:48-48` (was exit 0)
- voice message Cancel, shape removed: exit 1, `UNREVIEWED c36d14f19969`
- voice bar, style moved back to the container: exit 1, `CONTAINER 9735eab53ddc CuadraoVoiceBar.swift:20-42`
- FinancialActivityRow, shape removed: exit 1, three `HELPER` lines (was exit 0)
- CuadraoChoiceLabel, shape removed: exit 1, two `HELPER` lines
- unmutated copy: exit 0

## Commands and results
All compiles ran on the tree whose Swift sources equal `567f59819` (the head commit adds evidence only). Each xcodebuild ran as its own command.
- `SIMULATOR_ID=0335699A-C522-492B-A8C3-8FD3D7CAC06A ios/scripts/verify.sh build` -> `** BUILD SUCCEEDED **`, exit 0
- `xcodebuild build -project ios/ArgusFoundation.xcodeproj -scheme ArgusFoundation -configuration Release -destination "platform=iOS Simulator,id=0335699A-C522-492B-A8C3-8FD3D7CAC06A" -derivedDataPath ios/.build/DerivedData CODE_SIGNING_REQUIRED=NO` -> `** BUILD SUCCEEDED **`, exit 0
- `xcodebuild build-for-testing` with the same project, scheme, destination and derived data, Debug -> `** TEST BUILD SUCCEEDED **`, exit 0. The untracked `W1bDiagnosticUITests.swift` was present on disk during this compile.
- `ios/scripts/cuadrao-design-mac-pass.sh checks` -> `== checks: ok`, exit 0; tap-target line: `plain-style statements: 127, without a content shape: 43, reviewed: 43, unreviewed: 0, stale entries: 0, container styles: 0, helpers without a shape: 0`
- `git diff --check` -> clean before each commit
- `git push origin codex/cuadrao-release-ui` -> `c45e1eb76..e694d5da2`
- No command was refused by the permission system.

## Not run
- No simulator, no UI test, no off-centre tap on device or simulator. GitHub CI on the new head not checked.
- Full xcodebuild logs are in /tmp (`w1e-debug-build.out`, `w1e-release-build.out`, `w1e-bft.out`), not committed; result lines are in `2026-10-04-w1e/compiles.txt`.

## Evidence
`docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1e/` and the README section "Tap-target check corrected after review, October 4, 2026".
