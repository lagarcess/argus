# Native registered sessions

Authentication is **off by default**. Profile can connect to existing Argus
signup/login and `/me`; the five financial destinations remain local samples.
No guest bootstrap, financial records, calculations or provider calls are added.

## Configuration

`Config/Development.xcconfig` owns defaults; ignored `Config/Local.xcconfig`
accepts the public keys listed in its example. API, Supabase and web URLs are
root origins, without `/api/v1`. CAPTCHA is an exact bridge URL. HTTPS is required
except loopback HTTP for local development. Escape URL slashes in xcconfig as
`https:/$()/example.test` because `//` starts a comment.

Enable `ARGUS_AUTH_ENABLED = true` only for an explicitly allocated environment.
The anon/publishable key is public. Never add passwords, service-role keys or
session tokens. Disabled mode creates no client or requests. Production endpoints,
CAPTCHA hosting, identity, signing team and callbacks remain unapproved.

The simulator uses an **ad-hoc signature with no account/team**, with
`application-identifier` derived from the replaceable local bundle identity.
This lets Keychain work; an unsigned simulator executable fails with -34018.
The default project configuration remains simulator-only. The opt-in
[device configuration](../docs/reports/financial-loop-device-preparation.md)
requires approved signing access.

## Session behavior

`Packages/ArgusSession` owns cookie-free transport, device-only Keychain storage
and identity. Official Swift Auth SDK 2.55.2 is pinned, with resolved dependencies.
Argus owns login/signup policy and CAPTCHA; the SDK owns adoption/refresh/revoke;
`/me` owns displayed identity. Credentials are scoped to app and environment.

Failed sign-out remains pending and blocks another login until retry settles
revocation and cleanup. Unexpected anonymous SDK identity is retained and native
registration/switching blocked pending an accepted guest-transfer contract.
Confirmation-required signup shows email instructions; generic resend is absent.
Forgot password opens web `/auth/forgot-password`: request and finish in that
same browser, then sign in freshly in the app. No native recovery or callbacks.
PR #726 remains evidence, not production probe code.

## Local acceptance

Prerequisites: Xcode/iPhone Simulator, Docker, Supabase CLI, Python3.12, Poetry,
Bun. Reserve ports first: API58400, Supabase58401, DB58402, mail58403,
SMTP58404, CAPTCHA58405, internal58407–58411, and web127.0.0.1:3001.
The web port is required by the existing HTTP recovery allowlist. Do not change
shared config or stop another worker's listeners. Run from repository root:

```bash
uv venv --python 3.12 .venv
poetry install --only main --no-root
(cd web && bun install --frozen-lockfile)
python3 ios/scripts/auth/local_stack.py configure
python3 ios/scripts/auth/local_stack.py start
python3 ios/scripts/auth/local_stack.py seed
```

The helper copies canonical migrations/config into ignored scratch and creates
two synthetic accounts, mode600 `ios/.build/auth-local/client.json` and public
`Config/Local.xcconfig`. Existing fixture/config is not overwritten. No root
`.env` or web `.env.local` may be present. In separate terminals:

```bash
python3 ios/scripts/auth/local_stack.py api --python "$PWD/.venv/bin/python"
python3 ios/scripts/auth/bridge.py
python3 ios/scripts/auth/local_stack.py web
```

Only this local stack has 60-second JWTs and Cloudflare public always-pass test
keys. Native still acquires a WK widget token. The unchanged web dev flow uses
its canonical local QA CAPTCHA token. Neither proves production CAPTCHA.

```bash
swift test --package-path ios/Packages/ArgusSession
ARGUS_SESSION_LIVE_CONFIG="$PWD/ios/.build/auth-local/client.json" \
  swift test --package-path ios/Packages/ArgusSession --filter LiveSessionTests
xcrun simctl list devices available
python3 ios/scripts/auth/run-ui.py <lane-owned-iPhone-UDID>
SIMULATOR_ID=<UDID> ios/scripts/verify.sh test ARGUS_AUTH_ENABLED=false
```

Live package tests use four login attempts plus one signup; native journey uses
one login; browser recovery uses two. CAPTCHA-only checks need no account:

```bash
python3 ios/scripts/auth/run-ui.py <UDID> --captcha-mode hold --only ArgusFoundationUITests/AuthJourneyUITests/testCaptchaCancellationKeepsEntry
python3 ios/scripts/auth/run-ui.py <UDID> --captcha-mode fail --only ArgusFoundationUITests/AuthJourneyUITests/testCaptchaFailureShowsRetryableEntry
python3 ios/scripts/auth/run-ui.py <UDID> --only ArgusFoundationUITests/AuthUITests
```

Only the loopback bridge reads this test mode; native code has no bypass. Respect the server's eight-attempt/IP/
ten-minute limit. Do not relax it to obtain a pass. UI credentials are written to
a temporary mode600 `.xctestrun`, then removed. Passwords enter a local-only,
expiring clipboard, cleared afterward, rather than a logged `typeText` action.
Raw logs/results stay ignored. Promote only sanitized screenshots/summaries.

Browser recovery helper commands and source provenance accompany the durable
recovery evidence. Fresh snapshots must supply current Playwright element refs.
No native-account fixture is reused for password reset.

Stop own terminal processes with Ctrl-C, then
`python3 ios/scripts/auth/local_stack.py stop`. This stops only `ios-auth-8be2`
and retains its local data. Shut down only assigned simulators; never erase a
shared device or stop unrelated containers. Local synthetic evidence is not
hosted readiness. Guest transfer, resend, callbacks and financial wiring remain
separate work. See the [lane spec](../docs/superpowers/specs/2026-09-28-ios-auth-session.md)
for ownership and exact integration/design/auth reference commits.
