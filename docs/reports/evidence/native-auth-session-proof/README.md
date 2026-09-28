# Native auth session proof evidence

Sanitized output from `probes/native-auth/`, cited by
[the report](../../native-auth-session-proof.md). Files hold statuses, error
codes, and booleans only. Every writer refuses to persist a token, password,
handoff secret, PKCE verifier, or email link.

| File | Client | Level | Checks |
| --- | --- | --- | --- |
| `http-session.json` | Python HTTP probe, not native | 3 | A1 to A14 |
| `http-guest.json` | Python HTTP probe | 3 | C1 to C10 |
| `http-callbacks.json` | Python HTTP probe | 3 | D1 to D7 |
| `http-captcha-turnstile-*.json` | Python HTTP probe, Cloudflare test secrets | 3 | B1 to B4 |
| `http-guest-adapter.json` | Python HTTP probe through the synthetic adapter | 2 | S1 to S7 |
| `ios-simulator.json` | Swift XCTest hosted in the probe app, iOS 27.0 simulator | 4 (I8 is 2) | I1 to I11 |
| `app/turnstile-test-pass.*` | Probe app, `WKWebView`, pass test sitekey | 4 with test keys | T1 |
| `app/turnstile-test-fail.*` | Probe app, fail test sitekey | 4 with test keys | T2 |
| `app/turnstile-test-interactive.*` | Probe app, interactive test sitekey; the challenge was not completed | 4 with test keys | T3 |
| `app/turnstile-cancelled.*` | Probe app, user taps Cancel. Captured before the reconciliation merge; the merge did not change the app | 4 | T4 |
| `app/callback-delivery.*` | Probe app receiving issued, repeated, and forged `argusnativeproof://` callbacks via `simctl openurl` | 4, custom scheme only | T5 |
| `app/callback-from-other-app.png` | A callback delivered while Settings was frontmost | 4, custom scheme only | T5 |

Everything except `app/turnstile-cancelled.*` was captured at `8e88294f7`. A14 and I11 are expected failures: each records a failed assumption
(findings F1 and F5 in the report).
