# Native auth session proof evidence

Sanitized output from `probes/native-auth/`, cited by
[the report](../../native-auth-session-proof.md). Files hold statuses, error
codes, counts, and booleans. Every writer refuses to persist a token,
password, handoff secret, PKCE verifier, or email link.

## Current acceptance

Every file here was captured at `8f4b05de0` from a clean tree, and each
records that head and `source_dirty: false`. The evidence gate verifies the
set against `probes/native-auth/expectations.json`. It fails on a missing,
repeated, or undeclared check, on any failure other than the documented ones,
on a documented failure that now passes, on an iOS run whose xcodebuild
counts disagree, on an app log that departs from the declared steps, and on
runtime code that changed after the capture. Re-verify at any later head:

```bash
python3 probes/native-auth/evidence_gate.py docs/reports/evidence/native-auth-session-proof
```

Documented failures, and only these, are expected:

- **A14.** The API's shared Supabase Auth client refreshes sessions it
  returned. PR #728 fixes it; this branch does not contain that fix.
- **I11.** supabase-swift logs tokens when given a logger, and a `Session`
  description contains them.

| File | Client | Level | Checks |
| --- | --- | --- | --- |
| `http-session.json` | Python HTTP probe, not native | 3 | A1 to A14 |
| `http-guest.json` | Python HTTP probe | 3 | C1 to C10 |
| `http-callbacks.json` | Python HTTP probe | 3 | D1 to D7 |
| `http-captcha-turnstile-*.json` | Python HTTP probe, Cloudflare test secrets | 3 | B1 to B4 |
| `http-guest-adapter.json` | Python HTTP probe through the synthetic adapter | 2 | S1 to S7 |
| `ios-simulator.json` | Swift XCTest hosted in the probe app, iOS 27.0 simulator | 4 (I8 is 2) | I1 to I11 |
| `app/run.json` | Capture record for the app demos, including how many "Open in" prompts the UI test accepted | 4 | T1 to T5 |
| `app/turnstile-test-pass.*` | Probe app, `WKWebView`, pass test sitekey | 4 with test keys | T1 |
| `app/turnstile-test-fail.*` | Probe app, fail test sitekey | 4 with test keys | T2 |
| `app/turnstile-test-interactive.png`, `app/turnstile-cancelled.*` | Interactive test sitekey; a UI test taps Cancel without completing the challenge | 4 with test keys | T3, T4 |
| `app/callback-delivery*.png`, `app/callback-delivery.json` | Issued, repeated, and forged `argusnativeproof://` callbacks via `simctl openurl`; a UI test stood ready to accept an "Open in" prompt and recorded 0 | 4, custom scheme only | T5 |

## Not current acceptance

`historical/callback-prompt-9045f4798.png` shows iOS asking "Open in
ArgusAuthProbeApp?" during a clean-tree run at `9045f4798`. That run stopped
at the prompt, so it is a historical observation. The current capture saw no
prompt.

Captures from `8e88294f7` and earlier were replaced. They were taken before
the gate existed, from a tree the runners did not record as clean, and are not
cited. Android has no evidence: its source has never been compiled or run.
