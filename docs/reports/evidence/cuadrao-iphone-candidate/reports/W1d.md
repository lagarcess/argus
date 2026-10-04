# W1d: last fix pass for PR #790

Worktree `/Users/garces/.codex/worktrees/cuadrao-release-ui/private-alpha-next`, branch `codex/cuadrao-release-ui`.
Start `cc68b341e99e06896f216204f721c19de32abf28`. Final head `c45e1eb765a6305c80ee5f56129ece008ee2f405`, pushed without force (`cc68b341e..c45e1eb76`).
No simulator ran. No `xcodebuild test` ran. `todo.md` and `W1bDiagnosticUITests.swift` are untouched and still untracked.

## Not done: Release compile and UI test target compile

I sent one command that ran `xcodebuild build -configuration Release` and then `xcodebuild build-for-testing`. The permission system refused it ("Interfere With Workloads") before anything ran. I did not retry either part. So:

- The Release compile did NOT run on this head.
- The UI test target was NOT compiled. `verify.sh build` builds the app only (the Debug log has no mention of `CuadraoGroupDesignUITests`), so the T1 line in `4cd4512fa` is uncompiled and unrun. It uses the predicate-expectation form already in `ConnectedBudgetUITests.swift:172`.

The lead should run the Release compile and the focused tests below.

## Per item

1. **Docs D1, D2, D3: done** (`1fd2e67fd`).
   - `DESIGN.md` 659-661 now states the current rule in one sentence with the October 3 decision link. The "personal-photo controls" wording a few lines below now reads "the avatar-editing entry". The `fc7650ea` history sentence is unchanged.
   - Board C08 states the current rule with the decision link. C07 says "the avatar-editing entry". Row 81 credits `fc7650ea` with photos and `26055a28` with the avatar-editing entry.
2. **Tap targets: done, compiled in Debug only** (`901874e2e`), **lever built** (`e0fe26a75`).
   - Confirmed each of the three by reading the code. M1 split member toggle (`CuadraoGroupExpenseEditor.swift`): label is now `.frame(maxWidth: .infinity, minHeight: 44, alignment: .leading).contentShape(Rectangle())` and the outer `Spacer()` is removed, as the review proposed. One honest difference: the old row spent a Spacer minimum plus one extra 12 pt gap, so a very long name gets about 20 pt more room before truncating. Nothing moves otherwise. M2 Manage spaces link (`CuadraoSpacesSheet.swift`): `maxWidth: .infinity, alignment: .leading` plus the shape inside a leading VStack, so the text stays where it was. Sign in (`ConnectedCuadraoAuth.swift`): shape after the outline overlay.
   - The audit at `cc68b341` reported 69 statements (the review counted 57 because it skipped Accounts, Plan, Search and root files). 27 had a dead area and are fixed with the same content shape: the preview Sign in, both "New here?/Already have an account?" links, chat new/share/attach icon buttons, chat suggestion chips, attachment tiles, the context chip remove button, account options ellipsis, Ask Cuadrao link, Home household avatars and Accounts header, voice preview link and voice controls, voice bar mute and end, avatar choices, search scope tabs, plan Explore link, receipt assignment chips, the Argus plan and search tabs. Two needed label form so the shape could sit on the label: the ordered-collection Edit and Archive buttons and the spending chart "All" button. Same rendering, no accessibility identifier or label changed.
   - 42 statements remain without an inline shape. Each is a label whose helper carries the shape or whose fill is opaque across its frame. I checked every helper definition by grep.
   - Lever: `ios/DesignPreviewTests/run_tap_targets.py` plus `tap_targets_reviewed.txt`, wired into `cuadrao-design-mac-pass.sh checks`. It exits 1 on any plain-style statement with neither a content shape nor a reviewed reason, and on stale reviewed entries. Entries are keyed by a digest of the statement, so an edit forces a new review. Limits: it reads one statement per `buttonStyle(.plain)` line, so a style set on a container of several buttons is read once (I fixed the voice bar's sibling by hand); it does not read Invitations or Household; it cannot see non-plain styles.
3. **T1: edited, not compiled, not run** (`4cd4512fa`). `CuadraoGroupDesignUITests.swift:56` waits up to 3 s for `value == "3,301"` on the repayment field before the disabled wait. If the focused field reads something other than `3,301` (for example `3301`), this line fails loudly and needs the literal changed.
4. **Money input: untouched.**

## Audit output (final)

`python3 ios/DesignPreviewTests/run_tap_targets.py`:

    plain-style statements without a content shape: 42, reviewed: 42, unreviewed: 0, stale entries: 0   (exit 0)

Original `plain_audit.py ios/ArgusFoundation`: 69 hits at `cc68b341`, 42 at final head. Both listings and the per-statement review reasons are in `docs/reports/evidence/cuadrao-release-ui/2026-10-04-w1d/` (`plain-audit-before-cc68b341.txt`, `plain-audit-after.txt`, `tap-target-check.txt`, `design-preview-checks.txt`, `debug-compile-tail.txt`). The evidence README has a dated section "Tap-target class closed by a check, October 4, 2026" (`c45e1eb76`).

## Commands and results

- `SIMULATOR_ID=0335699A-C522-492B-A8C3-8FD3D7CAC06A ios/scripts/verify.sh build`: `** BUILD SUCCEEDED **`, exit 0. Ran after every app Swift edit.
- Release compile: refused by the permission system, not run.
- `xcodebuild build-for-testing`: same refused command, not run.
- `ios/scripts/cuadrao-design-mac-pass.sh checks`: exit 0, `== checks: ok`, nine runners including `run_tap_targets`. Host only (`xcrun swiftc` and python), no simulator.
- `git diff --check`: clean.
- `uv run --with markdown-it-py python scripts/check_docs_links.py --base a8c37d3a182fbdb3228f6003272418e65286bc1a`: "Checked local links in 5 changed document(s)", exit 0. The `uv.lock` it wrote was deleted both times.

## Commits

- `901874e2e` fix(ios): plain-style controls take taps across their whole frame
- `e0fe26a75` test(ios): design checks fail on a plain-style control without a content shape
- `4cd4512fa` test(ios): repayment refusal waits for the over-cap amount to be in the field
- `1fd2e67fd` docs(cuadrao): state the current avatar rule in DESIGN and board C07, C08 and row 81
- `c45e1eb76` docs(cuadrao): record the tap-target audit and check output for W1d

## Focused UI tests for the lead (under the lock)

- T1 and the split member toggle's screen: `-only-testing:ArgusFoundationUITests/CuadraoGroupDesignUITests/testSharedJourneySpanish`
- Split member toggle tapped by label ("Ana, included"): `-only-testing:ArgusFoundationUITests/CuadraoReceiptUITests/testExpenseEditsSurviveReceiptCapture`
- Outlined Sign in: `-only-testing:ArgusFoundationUITests/CuadraoSignInPresentationUITests/testDefaultLaunchOffersNoAppleSignIn` and `-only-testing:ArgusFoundationUITests/FoundationUITests/testDesignPreviewOffersNoAppleSignIn`
- Manage spaces link: no UI test references it. It needs a hand tap on the empty part of the row, or a new test.
- XCUITest taps element centres, so these runs prove nothing broke. They do not prove the dead areas are gone; that needs an off-centre coordinate tap like W1c's diagnostic.
- Wider regression for the other 24 fixed controls, if wanted: `CuadraoHomeChartUITests`, `CuadraoVoiceDesignUITests`, `CuadraoCollectionUITests`, `CuadraoReceiptUITests`, `CuadraoProfileFollowupUITests`.
- First: a Release compile, which did not run here.
