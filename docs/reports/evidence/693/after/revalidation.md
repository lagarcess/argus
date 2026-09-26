# Browser revalidation

## Current consistent AM/PM formatting

Validated source commit: `b56ce0bd4eb0a397cfc1900727abcb75de5e8ef4`.
The complete package suite passed **22 tests**, with the
[output retained](playwright-day-period.txt). All 16 after images were
recaptured on that exact commit. Four Spanish daily-cap images changed to
`8:00 PM`; the four English daily-cap images and eight claim-recovery images
remained byte-for-byte unchanged.

Both languages now assert the same uppercase, unpunctuated `PM` marker,
with one separating space and one sentence-ending period. EN and es-419
mobile captures were visually inspected: the quiet notice fits at 360px,
the reset time is readable, and no answer controls appear.

The browser was set to `America/Santo_Domingo`. The mocked receipt time
was `2026-08-13T18:17:32Z`; `Retry-After: 20548` reaches the next UTC
midnight, displayed as `8:00 PM`. The missing-header cases reached that
same reset using the browser clock. These browser checks exercise display
behavior; backend quota-policy verification is recorded separately by the
main task.

All API responses were mocked, with no backend or provider calls. The owned
mock web server was stopped after capture. This run supersedes the after
images referenced by the historical runs below.

## Quiet daily-cap notice history

Validated source commit: `b9404df285f210587c6fb586dd6478bff7f707a9`.
The complete package acceptance run passed **22 tests**, with the
[output retained](playwright-quiet-notice.txt). All 16 after images were
recaptured on that exact source commit. Eight daily-cap images now show the
quiet bordered failure notice; the eight claim-recovery images remained
byte-for-byte unchanged.

Every daily-cap case, including a new chat, now asserts:

- One visible `recovery-failure-notice` with `role="status"` and exact
  English or Spanish reset-time text.
- No buttons in the containing message, including hidden Copy, rating,
  and More Actions controls.
- The question remains visible, with no raw backend error or vague wait.

EN and es-419 mobile images were visually inspected. The notice fits the
360px viewport, the reset time is readable, and there are no answer controls.
Both account kinds and the existing 503 retry behavior passed. The run used
only mocked API responses; no backend or provider calls were made. The owned
mock web server was stopped after capture.

## Initial implementation history

The following run predates the quiet-notice change and does not validate its
appearance. The current run above supersedes its after screenshots.

Validated source commit: `d604a816f5415f0681541befb7baa09fd7d986f9`.
The 22-case run began at `f83f4124`; the only intervening commit changed
evidence documentation. `git diff f83f4124 d604a816 -- web` is empty.

- Package acceptance: **22 passed in 21.4 seconds**. The
  [complete output](playwright-exact-head.txt) is retained.
- All **16** newly captured after PNGs were byte-for-byte identical to
  the committed after evidence (SHA-256 comparison, zero mismatches).
- Existing #681 guest recovery tests: **3 passed**. The
  [complete output](guest-regression.txt) is retained.
- The #681 spec was copied temporarily with only its screenshot output
  directory changed to `/private/tmp/argus-693-guest-regression-shots`.
  Assertions and fixtures were unchanged. The copy was removed after the run;
  `docs/reports/evidence/677` has no diff.

Both runs used the mock web server and Chromium. The package run used the
documented Dominican Republic time zone; #681 retained its existing default
browser time zone. No paid provider or backend calls were made. The owned
local web server was stopped after validation.
