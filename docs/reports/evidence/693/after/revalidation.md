# Browser revalidation

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
