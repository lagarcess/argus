# Native auth and session proof probes

Isolated probes behind
[the native auth session proof report](../../docs/reports/native-auth-session-proof.md).
Nothing here is imported by the Argus API, the web app, or tests under
`tests/`. The probes run against a disposable local Supabase stack and the
unchanged Argus API.

## Layout

| Path | What it is | Evidence level |
| --- | --- | --- |
| `stack/` | Lane-owned Supabase stack (`argus-native-auth-proof`, ports 57450 to 57459) and the Argus API launcher (port 57460) | Environment |
| `http_probe/` | Language-neutral Python probe. It is not a native client | 3, against unchanged Argus |
| `adapter/` | SYNTHETIC reverse proxy that adds the proposed handoff header transport (port 57461) | 2 |
| `ios/ArgusNativeAuth/` | Swift package: the client under test, plus XCTest scenarios | 4 on the simulator |
| `ios/ArgusAuthProbeApp/` | Host app: hosts the XCTests, runs Turnstile in `WKWebView`, receives callback URLs | 4 on the simulator |
| `ios/turnstile/` | Local page that renders the Turnstile widget (port 57462) | 4 with test keys |
| `android/` | Kotlin probe source. Never compiled here | Unverified |
| `expectations.json`, `evidence_gate.py` | The declared check list per suite, the only documented failures, and the gate every runner exits through | Gate |
| `tests/` | Regression tests for the gate | Unit |

## Safety properties

- The stack copies `supabase/` into `temp/native-auth-proof/stack` with its own
  project id and ports. `stack/down.sh` removes only that project's containers
  and volumes.
- `stack/api.sh` blanks every provider key and pins synthetic market data. No
  model, market, email, or analytics provider can be reached. No chat turn is
  sent: guest conversations are created empty.
- Test users are created per run with random passwords that exist only in
  memory. The Python writer refuses to write evidence that contains any token,
  password, handoff secret, PKCE verifier, or email link the run handled. The
  iOS collector refuses any JWT-shaped value.
- Captcha runs use Cloudflare's published test secrets and test sitekeys only.

## Evidence gate

Every runner exits with the verdict of `evidence_gate.py`, not with the raw
tool status. The gate compares each evidence file with `expectations.json` and
fails on a missing, repeated, or undeclared check, on any failure other than
the documented ones (A14 and I11), on a documented failure that now passes, on
an iOS run whose xcodebuild counts disagree, on an app log that departs from
the declared steps, and on a capture taken from a dirty tree or from runtime
code that differs from HEAD. Markdown changes do not make evidence stale.

```bash
python3 probes/native-auth/evidence_gate.py docs/reports/evidence/native-auth-session-proof
```

```bash
.venv/bin/python -m pytest probes/native-auth/tests -q --no-cov -c /dev/null --rootdir probes/native-auth
```

## Reproduce

Requirements: Docker, Supabase CLI 2.117 or later, Poetry environment for this
repository (`poetry install`), and Xcode 27 with an iOS 27 simulator runtime.

```bash
bash probes/native-auth/stack/up.sh off
```

```bash
bash probes/native-auth/run-all.sh temp/native-auth-proof/final
```

`run-all.sh` runs these in order, stops at the first failing gate, and ends
with the gate over the whole directory: session, guest, and adapter suites; callbacks;
captcha in three test-secret modes, restarting the API after each switch; then
the iOS XCTests hosted in the probe app on a simulator named
"Argus Native Auth Proof", which it creates if missing.

App-level demos (Turnstile in the web view and callback delivery) need the
pass-mode test secret and the page server. The cancel demo runs as a UI test
(`ArgusAuthProbeUITests`) that taps Cancel without completing the challenge.
If iOS asks "Open in ArgusAuthProbeApp?" before a callback, someone must tap
Open; otherwise the script fails after 90 seconds:

```bash
bash probes/native-auth/stack/restart-auth.sh turnstile-pass
```

```bash
python3 -m http.server 57462 --bind 127.0.0.1 --directory probes/native-auth/ios/turnstile
```

```bash
bash probes/native-auth/ios/run-app-demos.sh temp/native-auth-proof/final
```

Restart the API after `restart-auth.sh`: the switch also restarts Postgres, and
the API's session-check pool does not reconnect by itself.

## Clean up

```bash
bash probes/native-auth/stack/down.sh
```

```bash
xcrun simctl delete "Argus Native Auth Proof"
```

Then stop the processes on ports 57460, 57461, and 57462.
