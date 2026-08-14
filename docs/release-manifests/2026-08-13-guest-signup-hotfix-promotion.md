# Guest Signup Hotfix Promotion, 2026-08-13

## Candidate

- Promotion target: `main`
- Candidate SHA: `7c843f364833ad16cf1c7b5a69ed3e703df085e5`
- Source branch: `codex/private-alpha-next`
- Rollback target: `5f8b372b7892a9a93d4586462c6bc5984c7e8354`
- Approver: founder, 2026-08-13

## Why this promotion exists

The 2026-08-13 promotion shipped #492, which replaced the guest conversion
mechanism. Guest signup then failed for **every user on every browser**, and
never once succeeded: two attempts in production, zero handoffs bound, zero
consumed.

The app and the API are separate registrable domains and the browser calls the
API directly, so a cookie the API sets is third-party to the app.
`SameSite=Lax` is never returned on a cross-site fetch, so
`POST /auth/guest/signup` arrived with no cookies and failed its first check
before touching the database. Every handoff row was valid, pending, correctly
email-bound, and permanently unbound.

The user saw "This conversation transfer is no longer valid", which was wrong
twice: the transfer was fine, and the real reason was discarded by the
unknown-code default in `_guest_handoff_problem`.

Found by the founder within minutes of the promotion, on the one path only
production can exercise.

## What ships

- One policy owns how every Argus browser cookie crosses origins, applied to
  both handoff cookies, their deletion, and the `sb-auth-token` /
  `sb-refresh-token` session cookies carrying the same latent defect. Those do
  not break today only because auth rides the `Authorization` header.
- `SameSite=None` requires `Secure`, so plain-http local development keeps
  `Lax`.
- The privacy policy's guest-handoff cookie disclosure is corrected in both
  languages. It claimed ten minutes; #492 added a signup handoff that expires
  with the guest workspace, so the cookie can live up to seven days. Verified
  against production: `existing_account` is exactly 10 minutes,
  `new_account_signup` is about 7 days. The disclosure now also states that the
  cookies travel to the Argus API on its own domain.

The no-consent-banner position is unchanged. The cookie carries the user's own
conversation to their own account: functional, not tracking, not advertising.

## Gate Evidence

- Live eval scorecard: `docs/reports/evidence/2026-08-13-guest-signup-hotfix/live-eval-scorecard.json`
- Baseline eval scorecard: `docs/reports/evidence/2026-08-13-guest-signup-hotfix/baseline-eval-scorecard-5f8b372b.json`
- Evaluation mode: `live`, both provider modes `live_provider`

| | Passed | Failed |
| --- | ---: | ---: |
| Deployed `5f8b372b` | 34 | 12 |
| Candidate `7c843f36` | 35 | 11 |

The baseline scorecard records `d4d2ac14` rather than `5f8b372b` because the
merge to `main` mints a new commit for identical content. Its product tree is
byte-identical to the deployed build, so it measures what production runs.
The release-docs gate asserts that equivalence directly rather than comparing
commit strings, since every future promotion has the same shape.

- **10 failures shared** with the deployed build.
- **2 improvements**: `action_chip_change_asset_no_active_ref_asset_and_date_issue_188`
  and `capability_honesty_options_straddle_tsla`.
- **1 case flips the other way**:
  `action_chip_change_asset_remove_aapl_issue_188`.

That flip is variance, not regression, and the proof is mechanical: this
change touches four files, two cookie-policy lines and two locale strings.
`git diff d4d2ac14 7c843f36 -- src/argus/agent_runtime/ src/argus/domain/` is
**empty**, so the interpreter and edit paths that decide asset-edit semantics
are byte-identical. Nothing here can alter that case.

The same case has now flipped on three consecutive runs: FAIL at `5d8ba7a5`,
pass at `d4d2ac14`, FAIL at `7c843f36`. It is the noisiest case in the suite.

Both shared families remain filed as #498 and #499. Neither is made worse here.

## Deploy Proof

- [ ] `argus-api` deployed at candidate SHA, carries the cookie policy
- [ ] `argus-app` deployed at candidate SHA, carries the privacy copy
- [ ] `argus-backtests` released at candidate SHA for release coherence
- [ ] Autodeploy remains `off` on all three

`argus-backtests` runs no auth code and needs nothing from this change, but the
release-coherence canary compares all three, and it silently ran a week behind
once already.

## Acceptance

The only test production can run: a guest conversation converting to an
account. Expect a `guest_workspace_handoffs` row that reaches
`destination_user_id`, a Supabase `user_signedup` audit action, and no
change-email confirmation.

## Release Decision

- [ ] Founder approval to deploy
