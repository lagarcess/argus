# ArgusSession

Registered-session ownership for the iPhone app. The package depends on the
`Auth` product from official `supabase-swift` **2.55.2**; `Package.resolved` pins
transitive dependencies. It contains no SwiftUI, financial rules, guest entry,
account-management endpoints, CAPTCHA acquisition or recovery callbacks.

## App boundary

Create one `SessionController` per app session. Its constructor makes no network
request. Call `restore()` explicitly when auth is enabled. Configure API and
Supabase **origins**, with no `/api/v1` or `/auth/v1` suffix. HTTPS is required
except for loopback development. Public publishable/anon keys are accepted;
secret/service-role keys are rejected. Keep development values in the app's
ignored configuration, never in this package.

Public methods are `snapshot`, `restore`, `login`, `signup`, `profile`, `signOut`
and `retryPendingSignOut`. Signup accepts an optional trailing `displayName`.
`SessionSnapshot` contains only a phase, the canonical Argus `/me` profile and an
account revision. It never exposes credentials. The phases are `signedOut`,
`authenticated`, `signOutPending` and `unsupportedAnonymousSession`.

Auth mutations are serialized; overlapping mutations return `busy`. Profile
reads may run concurrently. Before every retry or delivery, their original
account epoch must still be current. A stale request cannot refresh, deliver
another account's profile, or write/delete that account's SDK storage.

## Credential and error behavior

- Login/signup call existing Argus endpoints with a caller-supplied fresh CAPTCHA
  token. A confirmation-required signup does not log in automatically.
- Both Argus and SDK requests use an ephemeral, cookie-free transport. Redirects
  are rejected. Credentials are namespaced by the API/Supabase origin pair.
- SDK credentials use device-only Keychain storage. Writes update existing items
  before attempting an insert. The adapter detects SDK-swallowed storage errors.
- The SDK owns refresh. An authenticated 401 permits one logical refresh and
  request retry; another 401 or a refused refresh ends the usable session. A
  refused refresh without definitive revocation proof remains pending cleanup.
  Transport/5xx errors remain retryable. SDK refresh/logout requests independently have up to two internal
  transient retries in the pinned release.
- Sign-out journals pending revocation before local deletion. An isolated SDK
  client refreshes pending credentials, persists rotation, and revokes locally.
  Only observed logout HTTP success or terminal rejected-refresh proof clears
  the pending marker. SDK-suppressed logout 401/403/404 alone is insufficient.
- Pending revocation blocks entry and retries on restore or explicit retry. If
  Keychain refuses a write, issued credentials remain in memory and the failure
  stays visible. No application can promise crash-durable recovery while the OS
  refuses every durable write; a storage preflight reduces this window.
- An existing anonymous SDK session is preserved without network activity and
  blocks registration/account replacement. Guest transfer needs its own server
  contract. There are no guest endpoint calls in this package.

Only bounded `SessionFailure` values leave the package. SDK logging is disabled;
never log a session, request body, tokens or CAPTCHA values in callers. Recovery
belongs to the app's external browser flow, with no native verifier transfer.

## Tests

From the repository root:

```bash
swift test --package-path ios/Packages/ArgusSession
```

Ordinary tests inject only storage/HTTP boundaries and exercise the actual SDK.
They cover configuration, cookie policy, redirects, identity binding, refresh,
failed persistence, stale requests/storage writes, and pending revocation.

The separately enabled local suite reads the existing synthetic-account fixture:

```bash
ARGUS_SESSION_LIVE_CONFIG="$PWD/ios/.build/auth-local/client.json" \
  swift test --package-path ios/Packages/ArgusSession --filter LiveSessionTests
```

It refuses origins outside the lane's loopback ports 58400/58401 and skips when
the environment variable is absent. It uses real Keychain storage and unchanged
local Argus/Supabase: registered login/profile, new-controller restore, old-token
rejection after revoke, account switching, concurrent expiry refresh, invalid
login and confirmation-required signup. It consumes four login attempts and one
signup; coordinate the shared local attempt limit before running. The public
CAPTCHA test token exists only in the test target. Simulator/process-relaunch,
CAPTCHA widget, browser recovery and real-device proof belong to the app lane.
