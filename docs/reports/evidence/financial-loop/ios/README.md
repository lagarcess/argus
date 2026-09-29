# Native financial-loop evidence

This is a local component checkpoint. The founder’s physical iPhone, existing
identity and real data over the internet remain the delivery acceptance boundary.
The [execution manifest](../../../../specs/argus-execution-board.md) owns that status.

Native source: `d5299f65a5e9a49ccb50509b2d839107f7734f95`.
Backend source: `92020058d503459dbb7f9e2efa828dd5cddb1637`.
The evidence commit changes artifacts only. Both simulator and API used those
sources with the real local Supabase/Postgres stack and synthetic registered data.
See [sanitized results](verification.json) for exact runtime, counts and hashes.

## Demonstration

[Connected loop recording](connected-loop.mp4) is 2 minutes 9 seconds. It starts
immediately after creating the DOP 10,000 account, then shows expense, Home,
correction, balance check, recording an expense already in the checked balance,
reopening and Spanish review. It is a continuous 12-fps capture, compressed without
cuts or speed changes. It contains synthetic app UI, no credential entry or
terminal/debug output. Initial creation and the unknown-to-known journey are
covered by XCTest and the selected screenshots, not this recording.

## Observable results

- Unknown remains unknown after an expense. Establishing a signed balance of
  DOP -25.50 asks whether the existing expense is included and survives reopening.
- DOP 10,000 becomes 8,000 after a 2,000 expense, then 7,500 after correction to
  2,500. Home is checked against its captured baseline after the write and after
  returning from the background.
- A checked balance of 7,000 retains the original -500 difference. A late expense
  of 500, excluded from opening but included in the checked balance, leaves the
  account at 7,000 and brings the unexplained difference to zero. Reopening
  preserves the account and activity; Home shows the exact corresponding delta.
- Spanish Home and balance-check review use localized controls and source copy.
- Five production-model tests cover uncertain-write replay, expired-session
  recovery, stale Home reads, owner isolation and editable placement answers.

The final connected XCTest suite passed **3/3**. The session package had **39
executed, 4 skipped, 0 failures**. Production presentation-model tests passed
**5/5**. Screenshots are visual evidence; they do not substitute for those checks.

## Selected visual evidence

- [Compact account entry](account-entry-dark.png)
- [Opening inclusion review](opening-inclusion-dark.png)
- [Connected Home](home-dark.png)
- [Balance-check review](balance-check-dark.png)
- [Reopened reconciled account](reopened-account-dark.png)
- [Spanish Home](home-spanish-dark.png)
- [Spanish balance-check review](balance-check-spanish-dark.png)

The current mobile lock and MVEE quick-setup correction are the visual references.
No forecast or unimplemented commitment values are fabricated in connected Home.

## Reproduce and resume

[Connected setup and verification commands](../../../../../ios/ACCOUNTS_SETUP.md)
cover an isolated stack, existing CAPTCHA bridge, session tests, production-model
harness and the serial connected UI suite. Run the UI suite against one allocated
stack and simulator; it appends synthetic accounts and verifies Home deltas rather
than assuming an empty database. Do not reset another owner’s running stack.

At handoff, the native worker has stopped its CAPTCHA bridge (port 58405), log
reader and recorder; Xcode is idle. The simulator remains booted for review at
`197C9C31-77FD-4D31-A9C6-EACA55732B15`. The core owner retains API port 58400,
Supabase 58401 and Postgres 58402. Restart the local bridge with
`python3 ios/scripts/auth/bridge.py` before a fresh sign-in test. No hosted system
was changed by this native verification.

The full local result bundle is `/tmp/argus-loop-iphone-evidence/ui-1790671670.xcresult`.
Raw bundles/logs are not committed because auth diagnostics can contain synthetic
credentials. The selected evidence and sanitized summary here are durable.
